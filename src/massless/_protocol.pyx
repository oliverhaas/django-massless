import asyncio
import contextlib
import logging

import httptools
from asgiref.sync import sync_to_async
from django.core.signals import request_started

_logger = logging.getLogger("massless")

from massless._request cimport RequestCore
from massless._request import MasslessRequest
from massless._response cimport Response
from massless._response import build_http_response

cdef bytes _CONTINUE = b"HTTP/1.1 100 Continue\r\n\r\n"


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
    """
    request = MasslessRequest(core, {})
    # request_started pairs with request_finished (fired by dj_resp.close() below);
    # together they drive Django's per-request DB connection / query-log management.
    await request_started.asend(sender=type(handler))
    dj_resp = await handler.handle(request)
    cdef Response resp
    if getattr(dj_resp, "streaming", False):
        # Streaming responses are a later phase (the C serializer reads .content, which
        # a StreamingHttpResponse does not have). Return a clear 501 instead of letting
        # the missing .content surface as an opaque 500.
        _logger.warning("streaming responses are not supported yet (path=%s)", request.path)
        resp = Response(501, {}, b"Streaming responses are not supported yet",
                        b"text/plain; charset=utf-8", b"Not Implemented")
    else:
        resp = _django_response_to_massless(dj_resp)
    cdef object conn = dj_resp.headers.get("Connection")
    if conn is not None and conn.lower() == "close":
        keep_alive = False
    # Tear down per-request resources and fire request_finished. An async-capable Django
    # (e.g. django-asyncio) exposes response.aclose(), which dispatches request_finished via
    # asend so its async-only aclose_old_connections receiver runs on THIS event loop and
    # returns the async DB connection to its pool; closing on the executor thread instead
    # would skip that receiver and leak the connection, exhausting the pool under load.
    # Stock Django has only sync receivers, so close() runs on the thread-sensitive executor
    # where the sync ORM's connections live, matching its own ASGIHandler.
    if hasattr(dj_resp, "aclose"):
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

    async def _process_loop(self):
        loop = asyncio.get_running_loop()
        inflight = self._handler._inflight
        cdef RequestCore core
        try:
            while True:
                # If a drain has begun and this connection has no queued work,
                # close the connection and stop so it is neither mistaken for
                # in-flight work nor left holding the server open via wait_closed.
                if self._handler._draining and self._queue.empty():
                    self._close_transport()
                    return
                item = await self._next_item()
                if item is None:
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

    def _close_transport(self):
        """Close this connection's transport if still open (used when a worker
        loop exits during a graceful drain so the listener's wait_closed can
        complete)."""
        if self._transport is not None and not self._transport.is_closing():
            self._transport.close()

    async def _next_item(self):
        """Return the next queued (core,), or ``None`` if a drain wakes an idle
        connection that has nothing queued.

        We race ``queue.get()`` against the shared drain event so an idle
        keep-alive worker loop, otherwise blocked here forever, exits promptly
        once a graceful shutdown begins instead of stalling the server's drain.
        """
        loop = asyncio.get_running_loop()
        # The drain event is normally created by serve_async; create one lazily
        # for serving paths (e.g. tests) that drive the protocol directly.
        if self._handler._drain_event is None:
            self._handler._drain_event = asyncio.Event()
        get_task = loop.create_task(self._queue.get())
        drain_wait = loop.create_task(self._handler._drain_event.wait())
        try:
            await asyncio.wait(
                {get_task, drain_wait}, return_when=asyncio.FIRST_COMPLETED
            )
        finally:
            drain_wait.cancel()
        if get_task.done():
            return get_task.result()
        # Drain fired first; cancel the pending get. ``Queue.get`` may have
        # already dequeued an item just before cancellation lands -- if so it is
        # held in the task result, so re-check rather than dropping a request.
        get_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await get_task
        if get_task.cancelled():
            if not self._queue.empty():
                return self._queue.get_nowait()
            return None
        return get_task.result()
