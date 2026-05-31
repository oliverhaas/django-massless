import asyncio

import httptools

from massless._request cimport RequestCore
from massless._request import MasslessRequest
from massless._response import build_http_response, serialize_body


cdef class _Collector:
    """httptools callback target that accumulates one request into a RequestCore.

    The attributes are `cdef public` so the plain-Python MasslessProtocol can read
    them; bare `cdef` fields are invisible to Python and would raise AttributeError.
    """
    cdef public bytes url
    cdef public list headers
    cdef public bint complete

    def __cinit__(self):
        self.headers = []
        self.url = b""
        self.complete = False

    def on_url(self, bytes url):
        self.url += url   # httptools may deliver the URL in multiple chunks

    def on_header(self, bytes name, bytes value):
        self.headers.append((name, value))

    def on_message_complete(self):
        self.complete = True


def parse_request(bytes raw):
    """Parse a full HTTP/1.1 request into a RequestCore (test + glue helper)."""
    collector = _Collector()
    parser = httptools.HttpRequestParser(collector)
    parser.feed_data(raw)
    method = parser.get_method()  # bytes
    parsed = httptools.parse_url(collector.url)
    cdef bytes path = parsed.path
    cdef bytes query = parsed.query if parsed.query is not None else b""
    return RequestCore.create(method, path, query, collector.headers)


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
    """One instance per connection. Parses requests and writes responses."""

    def __init__(self, api, router):
        self._api = api
        self._router = router
        self._transport = None
        self._reset()

    def _reset(self):
        self._collector = _Collector()
        self._parser = httptools.HttpRequestParser(self._collector)

    def connection_made(self, transport):
        self._transport = transport

    def data_received(self, bytes data):
        self._parser.feed_data(data)
        if self._collector.complete:
            method = self._parser.get_method()
            parsed = httptools.parse_url(self._collector.url)
            query = parsed.query if parsed.query is not None else b""
            core = RequestCore.create(method, parsed.path, query, self._collector.headers)
            route_id, param = self._router.match(parsed.path)
            self._reset()
            asyncio.get_event_loop().create_task(self._respond(core, route_id, param))

    async def _respond(self, core, route_id, param):
        if route_id == -1:
            self._transport.write(build_http_response(404, b"text/plain; charset=utf-8", b"Not Found", True))
            return
        try:
            raw = await dispatch(self._api, core, route_id, param)
        except Exception:
            raw = build_http_response(500, b"text/plain; charset=utf-8", b"Internal Server Error", True)
        self._transport.write(raw)
