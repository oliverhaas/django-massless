import asyncio
import logging

import httptools
from asgiref.sync import iscoroutinefunction, sync_to_async
from django.conf import settings as _settings
from django.core.handlers.exception import response_for_exception as _response_for_exception
from django.core.signals import request_started
from django.db import close_old_connections as _close_old_connections
from django.urls import get_urlconf as _get_urlconf
from django.utils.log import log_response as _log_response

try:
    from django.db import aclose_old_connections as _aclose_old_connections
except ImportError:  # stock Django has no async-native connection teardown
    _aclose_old_connections = None

_logger = logging.getLogger("massless")

from massless._request cimport RequestCore
from massless._request import MasslessRequest
from massless._response cimport Response
from massless._response import build_http_response
from massless.responses import _Fast as _FastResponse
from massless.handler import _LazyResolverMatch

cdef bytes _CONTINUE = b"HTTP/1.1 100 Continue\r\n\r\n"

# Pushed into a connection's queue when a graceful drain begins, so an idle worker
# blocked on queue.get() wakes and exits without a per-request task race.
cdef object _DRAIN_SENTINEL = object()


cdef class _Collector:
    """httptools callback target that accumulates requests into a list.

    httptools fires one message cycle (on_message_begin .. on_message_complete)
    per request, even when several requests arrive in a single ``data_received``
    buffer (HTTP/1.1 pipelining). Per-message state is reset on each
    ``on_message_begin`` and snapshotted on ``on_message_complete``, so every
    request in the buffer is captured independently.

    The attributes are `cdef public` so the plain-Python MasslessProtocol can read
    them; bare `cdef` fields are invisible to Python and would raise AttributeError.
    """
    cdef public bytes url
    cdef public list headers
    cdef public bytes body      # accumulated request body for the current message
    cdef public list requests   # list[tuple[method, url, headers, body, keep_alive]], one per complete message
    cdef object _parser         # the HttpRequestParser, for get_method()
    cdef object _transport      # the connection transport, for writing 100 Continue

    def __cinit__(self):
        self.headers = []
        self.url = b""
        self.body = b""
        self.requests = []
        self._parser = None
        self._transport = None

    def set_parser(self, parser):
        self._parser = parser

    def set_transport(self, transport):
        self._transport = transport

    def on_message_begin(self):
        # New request in this buffer: reset per-message accumulators.
        self.url = b""
        self.headers = []
        self.body = b""

    def on_url(self, bytes url):
        self.url += url   # httptools may deliver the URL in multiple chunks

    def on_header(self, bytes name, bytes value):
        self.headers.append((name, value))

    def on_headers_complete(self):
        # Answer Expect: 100-continue as soon as the headers are in, so a client that
        # withholds its body until it sees 100 (curl auto-adds this for larger bodies)
        # proceeds instead of stalling. Only for HTTP/1.1, written at most once here.
        cdef bytes hname
        cdef bytes hvalue
        if self._transport is None or self._parser is None:
            return
        if self._parser.get_http_version() != "1.1":
            return
        for hname, hvalue in self.headers:
            if hname.lower() == b"expect" and b"100-continue" in hvalue.lower():
                if not self._transport.is_closing():
                    self._transport.write(_CONTINUE)
                return

    def on_body(self, bytes body):
        self.body += body   # httptools may deliver the body in multiple chunks

    def on_message_complete(self):
        # Snapshot this message's method/url/headers/body + keep-alive, then reset state.
        method = self._parser.get_method() if self._parser is not None else b"GET"
        self.requests.append((method, self.url, self.headers, self.body, self._keep_alive()))
        self.url = b""
        self.headers = []
        self.body = b""

    cdef bint _keep_alive(self):
        # uvicorn's policy: default keep-alive off only for HTTP/1.0; then honor an
        # explicit request "Connection: close". (HTTP/1.0 + "Connection: keep-alive"
        # is intentionally NOT honored, matching uvicorn.)
        cdef bytes hname
        cdef bytes hvalue
        if self._parser is not None and self._parser.get_http_version() == "1.0":
            return False
        for hname, hvalue in self.headers:
            if hname.lower() == b"connection" and hvalue.lower() == b"close":
                return False
        return True

    def take(self):
        """Return and clear the requests captured so far."""
        captured = self.requests
        self.requests = []
        return captured


def parse_request(bytes raw):
    """Parse a full HTTP/1.1 request into a RequestCore (test + glue helper)."""
    collector = _Collector()
    parser = httptools.HttpRequestParser(collector)
    collector.set_parser(parser)
    parser.feed_data(raw)
    method, url, headers, body, _keep_alive = collector.requests[0]
    parsed = httptools.parse_url(url)
    cdef bytes path = parsed.path
    cdef bytes query = parsed.query if parsed.query is not None else b""
    return RequestCore.create(method, path, query, headers, body)


cdef Response _django_response_to_massless(object dj_resp):
    """Fold a Django HttpResponse into a massless Response for the C serializer:
    status, exact reason phrase, headers (minus Content-Type/Length/Connection, which
    the serializer sets), and each Set-Cookie line so logins/sessions/CSRF survive.
    Content-Type is carried only when Django set one (a 304 carries none)."""
    cdef int status = dj_resp.status_code
    cdef bytes body = dj_resp.content
    cdef object ctype = dj_resp.headers.get("Content-Type")
    cdef bytes ctype_b
    if ctype is None:
        ctype_b = b""
    elif isinstance(ctype, str):
        ctype_b = ctype.encode("latin1")
    else:
        ctype_b = ctype
    cdef Response resp = Response(status, {}, body, ctype_b, dj_resp.reason_phrase.encode("latin1"))
    resp.ct_present = ctype is not None  # distinguish a present-but-empty Content-Type from an absent one (304)
    cdef str name
    cdef object value
    cdef str low
    for name, value in dj_resp.headers.items():
        low = name.lower()
        if low == "content-type" or low == "content-length" or low == "connection":
            continue
        resp.headers[name] = value
    # Django keeps cookies in .cookies (a SimpleCookie), separate from .headers.
    cdef object morsel
    for morsel in dj_resp.cookies.values():
        resp.cookies.append(morsel.OutputString())
    return resp


async def dispatch(handler, RequestCore core, bint keep_alive=True):
    """Build a lazy MasslessRequest from the C buffers, run it through Django's
    real middleware chain + resolver + view (the handler), and serialize the
    Django response to HTTP/1.1 wire bytes.

    Sync (def) views are adapted by Django's own async middleware chain (via
    sync_to_async, thread-sensitive), so no separate executor branch is needed
    here; async views are awaited on the loop. Returns (wire_bytes, keep_alive),
    where keep_alive reflects a "Connection: close" the response itself may carry.

    With ``MASSLESS_POOL_LIFECYCLE`` the per-request signal dispatch is skipped:
    request_started is not fired and teardown returns connections directly (the
    pool-mode teardown branch below). This drops the lifecycle-signal overhead
    (~the bulk of the no-DB pipeline tax) and matches django-bolt, which relies
    on a pool instead.
    """
    cdef bint fast = getattr(handler, "_pool_lifecycle", False)
    cdef bint took_fast = False
    cdef object rmatch
    cdef object callback
    request = MasslessRequest(core, {})
    dj_resp = None
    # Fast path inlined: when the handler has no middleware and no ATOMIC_REQUESTS, route
    # with the Cython router and run the view here -- a faithful copy of
    # MasslessHandler._fast_dispatch (verified by the differential tests). Inlining it
    # collapses the dispatch -> handle -> _fast_dispatch -> view -> teardown coroutine
    # chain into this one coroutine, which is the bulk of the per-request cost.
    # The gate already establishes the active urlconf == the router's (ROOT_URLCONF), so an
    # explicit set_urlconf would be redundant: an unset thread-local resolves to
    # ROOT_URLCONF anyway (get_resolver(None) -> default), so error-handler resolution and
    # reverse() are correct without paying a per-request thread-local write.
    if getattr(handler, "_fast_ok", False) and "urlconf" not in request.__dict__ \
            and _get_urlconf(_settings.ROOT_URLCONF) == handler._router_urlconf:
        rmatch = handler._router.match(request.path_info.encode("utf-8"))
        if rmatch is not None:
            took_fast = True
            callback = rmatch[0]
            request.resolver_match = _LazyResolverMatch(callback, rmatch[1], rmatch[2], rmatch[3])
            if not fast:
                await request_started.asend(sender=type(handler))
            try:
                if rmatch[4]:  # is_async, precomputed at router build
                    dj_resp = await callback(request, *rmatch[1], **rmatch[2])
                else:
                    dj_resp = await sync_to_async(callback, thread_sensitive=True)(request, *rmatch[1], **rmatch[2])
                handler.check_response(dj_resp, callback)
                if hasattr(dj_resp, "render") and callable(dj_resp.render):
                    if iscoroutinefunction(dj_resp.render):
                        dj_resp = await dj_resp.render()
                    else:
                        dj_resp = await sync_to_async(dj_resp.render, thread_sensitive=True)()
                if asyncio.iscoroutine(dj_resp):
                    raise RuntimeError("Response is still a coroutine.")
            except Exception as exc:
                dj_resp = await sync_to_async(_response_for_exception, thread_sensitive=False)(request, exc)
            dj_resp._resource_closers.append(request.close)
            if dj_resp.status_code >= 400:
                await sync_to_async(_log_response, thread_sensitive=False)(
                    "%s: %s", getattr(dj_resp, "reason_phrase", ""), request.path,
                    response=dj_resp, request=request)
    if not took_fast:
        # request_started pairs with request_finished (teardown below); together they
        # drive Django's per-request DB connection / query-log management. In pool mode
        # the pool owns that, so the signal is skipped on both ends.
        if not fast:
            await request_started.asend(sender=type(handler))
        dj_resp = await handler.handle(request)
    cdef Response resp
    cdef object conn
    cdef object body
    cdef object ctype
    if isinstance(dj_resp, _FastResponse):
        # Fast-tier response: serialize the body with msgspec at the C layer (no json.dumps,
        # no Django body re-fold). It is a real HttpResponse subclass, so any header/cookie a
        # middleware set lives on .headers/.cookies; carry them over, letting the C serializer
        # own Content-Type (from _serialize), Content-Length, and Connection.
        body, ctype = dj_resp._serialize()
        resp = Response(dj_resp.status_code, {}, body, ctype, b"")
        resp.ct_present = bool(ctype)
        for _hname, _hvalue in dj_resp.headers.items():
            _hlow = _hname.lower()
            if _hlow == "content-type" or _hlow == "content-length" or _hlow == "connection":
                continue
            resp.headers[_hname] = _hvalue
        for _morsel in dj_resp.cookies.values():
            resp.cookies.append(_morsel.OutputString())
    elif getattr(dj_resp, "streaming", False):
        # Streaming responses are a later phase (the C serializer reads .content, which
        # a StreamingHttpResponse does not have). Return a clear 501 instead of letting
        # the missing .content surface as an opaque 500.
        _logger.warning("streaming responses are not supported yet (path=%s)", request.path)
        resp = Response(501, {}, b"Streaming responses are not supported yet",
                        b"text/plain; charset=utf-8", b"Not Implemented")
    else:
        resp = _django_response_to_massless(dj_resp)
        conn = dj_resp.headers.get("Connection")
        if conn is not None and conn.lower() == "close":
            keep_alive = False
    # Tear down per-request resources and fire request_finished. An async-capable Django
    # (e.g. django-asyncio) exposes response.aclose(), which dispatches request_finished via
    # asend so its async-only aclose_old_connections receiver runs on THIS event loop and
    # returns the async DB connection to its pool; closing on the executor thread instead
    # would skip that receiver and leak the connection, exhausting the pool under load.
    # Stock Django has only sync receivers, so close() runs on the thread-sensitive executor
    # where the sync ORM's connections live, matching its own ASGIHandler.
    if fast:
        # Pool mode: run resource closers + return the DB connection directly, no
        # request_finished signal dispatch (bolt-style pool teardown, no extra frame).
        for closer in dj_resp._resource_closers:
            try:
                closer()
            except Exception:
                pass
        dj_resp._resource_closers.clear()
        dj_resp.closed = True
        if _aclose_old_connections is not None:
            await _aclose_old_connections()
        else:
            await sync_to_async(_close_old_connections, thread_sensitive=True)()
    elif hasattr(dj_resp, "aclose"):
        await dj_resp.aclose()
    else:
        await sync_to_async(dj_resp.close, thread_sensitive=True)()
    return resp.to_bytes(keep_alive, core._method), keep_alive


class MasslessProtocol(asyncio.Protocol):
    """One instance per connection.

    Parses requests and serves them strictly in arrival order: a single worker
    task per connection drains a queue, builds each response, and writes it to
    the transport before starting the next request. Responses therefore never
    reorder within a connection (HTTP/1.1 matches responses to requests by
    order), and all pipelined requests in one buffer are served in order.

    Different connections each get their own protocol instance and worker task,
    so they still run concurrently. The shared per-worker lifecycle state
    (in-flight registry, drain latch + event) lives on the handler.
    """

    def __init__(self, handler):
        self._handler = handler
        self._transport = None
        self._peer = None
        self._sockname = None
        self._collector = _Collector()
        self._parser = httptools.HttpRequestParser(self._collector)
        self._collector.set_parser(self._parser)
        self._queue = asyncio.Queue()
        self._worker = None
        self._drain_waker = None

    def connection_made(self, transport):
        self._transport = transport
        self._collector.set_transport(transport)
        # The TCP peer address -> REMOTE_ADDR (and the trust gate for forwarded headers).
        # IPv6 peernames are 4-tuples; keep just (host, port). Unix sockets have no peer.
        peer = transport.get_extra_info("peername")
        if isinstance(peer, tuple) and len(peer) >= 2:
            self._peer = (peer[0], peer[1])
        else:
            self._peer = None
        # The local bind address -> SERVER_NAME/SERVER_PORT (Django's scope["server"]).
        sock = transport.get_extra_info("sockname")
        if isinstance(sock, tuple) and len(sock) >= 2:
            self._sockname = (sock[0], sock[1])
        else:
            self._sockname = None
        self._worker = asyncio.get_running_loop().create_task(self._process_loop())

    def connection_lost(self, exc):
        # During a graceful drain we must NOT cancel a worker that is mid-response:
        # the server is waiting for that in-flight request to finish. The worker
        # loop exits on its own once its queue is idle (see _process_loop). Outside
        # a drain (e.g. a client drops a keep-alive connection), cancel promptly to
        # free the blocked ``queue.get()``.
        if self._worker is not None and not self._handler._draining:
            self._worker.cancel()
            self._worker = None
        self._transport = None

    def data_received(self, bytes data):
        try:
            self._parser.feed_data(data)
        except httptools.HttpParserError:
            # Malformed request: answer 400 and close, like uvicorn's send_400_response.
            if self._transport is not None and not self._transport.is_closing():
                self._transport.write(
                    build_http_response(400, b"text/plain; charset=utf-8", b"Bad Request", False),
                )
                self._close_transport()
            return
        for method, url, headers, body, keep_alive in self._collector.take():
            parsed = httptools.parse_url(url)
            query = parsed.query if parsed.query is not None else b""
            core = RequestCore.create(method, parsed.path, query, headers, body, self._peer, self._sockname)
            self._queue.put_nowait((core, keep_alive))

    async def _wake_on_drain(self):
        # One task per connection (not per request): when the shared drain begins, push
        # a sentinel so an idle worker blocked on queue.get() wakes and exits.
        if self._handler._drain_event is None:
            self._handler._drain_event = asyncio.Event()
        try:
            await self._handler._drain_event.wait()
            self._queue.put_nowait(_DRAIN_SENTINEL)
        except asyncio.CancelledError:
            pass

    async def _process_loop(self):
        loop = asyncio.get_running_loop()
        inflight = self._handler._inflight
        self._drain_waker = loop.create_task(self._wake_on_drain())
        cdef RequestCore core
        try:
            while True:
                # If a drain has begun and this connection has no queued work,
                # close the connection and stop so it is neither mistaken for
                # in-flight work nor left holding the server open via wait_closed.
                if self._handler._draining and self._queue.empty():
                    self._close_transport()
                    return
                item = await self._queue.get()
                if item is _DRAIN_SENTINEL:
                    # Woken by the drain with no queued work: close + exit cleanly.
                    self._close_transport()
                    return
                core = item[0]
                keep_alive = item[1]
                # Mark this one request as in-flight for the duration of handling
                # it, so the server's graceful drain can await real request work
                # (and only real request work) before running shutdown hooks.
                done = loop.create_future()
                inflight.add(done)
                try:
                    try:
                        raw, keep_alive = await dispatch(self._handler, core, keep_alive)
                    except Exception:
                        _logger.exception("request error")
                        # A failure outside Django's own exception handling leaves the
                        # connection in an unknown state; close it after the 500, as
                        # uvicorn does (send_500_response always closes).
                        keep_alive = False
                        raw = build_http_response(
                            500, b"text/plain; charset=utf-8", b"Internal Server Error",
                            keep_alive, core._method,
                        )
                    if self._transport is not None and not self._transport.is_closing():
                        self._transport.write(raw)
                        if not keep_alive:
                            # Client asked to close (HTTP/1.0 or Connection: close), or the
                            # response forced it: honor it by closing after the write.
                            self._close_transport()
                            return
                finally:
                    inflight.discard(done)
                    if not done.done():
                        done.set_result(None)
        except asyncio.CancelledError:
            pass
        finally:
            if self._drain_waker is not None and not self._drain_waker.done():
                self._drain_waker.cancel()

    def _close_transport(self):
        """Close this connection's transport if still open (used when a worker
        loop exits during a graceful drain so the listener's wait_closed can
        complete)."""
        if self._transport is not None and not self._transport.is_closing():
            self._transport.close()
