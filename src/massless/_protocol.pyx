import asyncio

import httptools

from massless._request cimport RequestCore
from massless._request import MasslessRequest
from massless._response import build_http_response, serialize_body


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
    cdef public list requests   # list[tuple[method, url, headers]], one per complete message
    cdef object _parser         # the HttpRequestParser, for get_method()

    def __cinit__(self):
        self.headers = []
        self.url = b""
        self.requests = []
        self._parser = None

    def set_parser(self, parser):
        self._parser = parser

    def on_message_begin(self):
        # New request in this buffer: reset per-message accumulators.
        self.url = b""
        self.headers = []

    def on_url(self, bytes url):
        self.url += url   # httptools may deliver the URL in multiple chunks

    def on_header(self, bytes name, bytes value):
        self.headers.append((name, value))

    def on_message_complete(self):
        # Snapshot this message's method/url/headers, then reset per-message state.
        method = self._parser.get_method() if self._parser is not None else b"GET"
        self.requests.append((method, self.url, self.headers))
        self.url = b""
        self.headers = []

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
    method, url, headers = collector.requests[0]
    parsed = httptools.parse_url(url)
    cdef bytes path = parsed.path
    cdef bytes query = parsed.query if parsed.query is not None else b""
    return RequestCore.create(method, path, query, headers)


async def dispatch(api, core, int route_id, long param):
    """Run the matched view and return full HTTP response bytes."""
    route = api.routes[route_id]
    path_params = {route.param_name: param} if route.param_name is not None else {}
    request = MasslessRequest(core, path_params)
    kwargs = route.binder(path_params, request.query_param)
    result = await route.view(**kwargs)
    body, ctype = serialize_body(result)
    return build_http_response(200, ctype, body, True)


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
        for method, url, headers in self._collector.take():
            parsed = httptools.parse_url(url)
            query = parsed.query if parsed.query is not None else b""
            core = RequestCore.create(method, parsed.path, query, headers)
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
