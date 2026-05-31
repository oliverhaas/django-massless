import asyncio

import httptools

from massless._request cimport RequestCore
from massless._middleware cimport run_after, run_before
from massless._request import MasslessRequest
from massless._response cimport Response
from massless._response import build_http_response


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
    cdef public list requests   # list[tuple[method, url, headers, body]], one per complete message
    cdef object _parser         # the HttpRequestParser, for get_method()

    def __cinit__(self):
        self.headers = []
        self.url = b""
        self.body = b""
        self.requests = []
        self._parser = None

    def set_parser(self, parser):
        self._parser = parser

    def on_message_begin(self):
        # New request in this buffer: reset per-message accumulators.
        self.url = b""
        self.headers = []
        self.body = b""

    def on_url(self, bytes url):
        self.url += url   # httptools may deliver the URL in multiple chunks

    def on_header(self, bytes name, bytes value):
        self.headers.append((name, value))

    def on_body(self, bytes body):
        self.body += body   # httptools may deliver the body in multiple chunks

    def on_message_complete(self):
        # Snapshot this message's method/url/headers/body, then reset per-message state.
        method = self._parser.get_method() if self._parser is not None else b"GET"
        self.requests.append((method, self.url, self.headers, self.body))
        self.url = b""
        self.headers = []
        self.body = b""

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
    method, url, headers, body = collector.requests[0]
    parsed = httptools.parse_url(url)
    cdef bytes path = parsed.path
    cdef bytes query = parsed.query if parsed.query is not None else b""
    return RequestCore.create(method, path, query, headers, body)


cdef Response _wrap_result(object result):
    """Fold a view return value into a Response (200), unless it already is one."""
    if isinstance(result, Response):
        return <Response>result
    return Response.from_view_result(result)


cdef Response _django_response_to_massless(object dj_resp):
    """Fold a Django HttpResponse (from the bridge) into a massless Response, so the
    fast-tier after() hooks run uniformly on the bridge path too."""
    cdef int status = dj_resp.status_code
    cdef bytes body = dj_resp.content
    cdef object ctype = dj_resp.headers.get("Content-Type", "application/octet-stream")
    cdef bytes ctype_b = ctype.encode("latin1") if isinstance(ctype, str) else ctype
    cdef Response resp = Response(status, {}, body, ctype_b)
    cdef str name
    cdef object value
    for name, value in dj_resp.headers.items():
        if name.lower() == "content-type" or name.lower() == "content-length":
            continue
        resp.headers[name] = value
    return resp


async def dispatch(api, core, int route_id, long param):
    """Run the matched view through the fast-tier middleware and return full
    HTTP response bytes.

    Flow: build request -> run_before (short-circuit on a Response) -> if
    bridge: promote + run through Django's real middleware chain -> else call
    the view -> wrap the return in a Response -> run_after (reverse) -> serialize.
    """
    route = api.routes[route_id]
    path_params = {route.param_name: param} if route.param_name is not None else {}
    request = MasslessRequest(core, path_params)

    cdef list chain = route.middleware
    cdef object short = run_before(chain, request) if chain else None
    cdef Response resp
    if short is not None:
        resp = <Response>short
        if chain:
            run_after(chain, request, resp)
        return resp.to_bytes(True)

    kwargs = route.binder(request, path_params, request.query_param)

    if route.bridge:
        request._promote()
        handler = _get_bridge(api)
        dj_resp = await handler.run(request, route.view, kwargs)
        resp = _django_response_to_massless(dj_resp)
        if chain:
            run_after(chain, request, resp)
        return resp.to_bytes(True)

    result = await route.view(**kwargs)
    resp = _wrap_result(result)
    if chain:
        run_after(chain, request, resp)
    return resp.to_bytes(True)


cdef object _get_bridge(api):
    """Lazily build and cache the BridgeHandler on the api (once per process)."""
    handler = getattr(api, "_bridge_handler", None)
    if handler is None:
        from massless.bridge import BridgeHandler
        handler = BridgeHandler()
        api._bridge_handler = handler
    return handler


class MasslessProtocol(asyncio.Protocol):
    """One instance per connection.

    Parses requests and serves them strictly in arrival order: a single worker
    task per connection drains a queue, builds each response, and writes it to
    the transport before starting the next request. Responses therefore never
    reorder within a connection (HTTP/1.1 matches responses to requests by
    order), and all pipelined requests in one buffer are served in order.

    Different connections each get their own protocol instance and worker task,
    so they still run concurrently.
    """

    def __init__(self, api, router):
        self._api = api
        self._router = router
        self._transport = None
        self._collector = _Collector()
        self._parser = httptools.HttpRequestParser(self._collector)
        self._collector.set_parser(self._parser)
        self._queue = asyncio.Queue()
        self._worker = None

    def connection_made(self, transport):
        self._transport = transport
        self._worker = asyncio.get_running_loop().create_task(self._process_loop())

    def connection_lost(self, exc):
        if self._worker is not None:
            self._worker.cancel()
            self._worker = None
        self._transport = None

    def data_received(self, bytes data):
        self._parser.feed_data(data)
        for method, url, headers, body in self._collector.take():
            parsed = httptools.parse_url(url)
            query = parsed.query if parsed.query is not None else b""
            core = RequestCore.create(method, parsed.path, query, headers, body)
            route_id, param = self._router.match(parsed.path)
            self._queue.put_nowait((core, route_id, param))

    async def _process_loop(self):
        try:
            while True:
                core, route_id, param = await self._queue.get()
                if route_id == -1:
                    raw = build_http_response(
                        404, b"text/plain; charset=utf-8", b"Not Found", True
                    )
                else:
                    try:
                        raw = await dispatch(self._api, core, route_id, param)
                    except Exception:
                        raw = build_http_response(
                            500, b"text/plain; charset=utf-8", b"Internal Server Error", True
                        )
                if self._transport is not None and not self._transport.is_closing():
                    self._transport.write(raw)
        except asyncio.CancelledError:
            pass
