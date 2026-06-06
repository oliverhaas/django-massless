"""Ceiling probes: how fast can the HTTP layer go single-core with NO Django?

Two modes, both uvloop + httptools (massless's exact C stack), one connection =
one asyncio.Protocol just like MasslessProtocol:

  MODE=raw     parse the request, then write a precomputed response. The absolute
               floor of httptools+uvloop+Python-glue: no request object, no
               serialization, no framework. This is the "is the C library the
               bottleneck?" number.

  MODE=cython  parse, build a massless RequestCore from the C buffers, wrap a
               static payload in a massless Response, and serialize via the same
               Response.to_bytes the real server uses -- but skip Django entirely.
               Isolates massless's own Cython parse+build+serialize overhead from
               Django's Python request pipeline.

Run pinned to one core (the runner does the taskset). PORT/MODE via env.
"""

import asyncio
import os

import httptools
import msgspec
import uvloop
from massless._request import RequestCore
from massless._response import Response, build_http_response

MODE = os.environ.get("MODE", "raw")
PORT = int(os.environ.get("PORT", "8600"))

# Same logical payload as bench root: JsonResponse({"message": "Hello World"}).
_PAYLOAD = {"message": "Hello World"}
_BODY = msgspec.json.encode(_PAYLOAD)
# Precomputed full wire response for raw mode (keep-alive, no Date refresh cost).
_RAW_RESPONSE = build_http_response(200, b"application/json", _BODY, True)


class _Proto(asyncio.Protocol):
    def __init__(self):
        self._t = None
        self._url = b""
        self._headers = []
        self._parser = httptools.HttpRequestParser(self)

    def connection_made(self, transport):
        self._t = transport

    def connection_lost(self, exc):
        self._t = None

    def on_message_begin(self):
        self._url = b""
        self._headers = []

    def on_url(self, url):
        self._url += url

    def on_header(self, name, value):
        self._headers.append((name, value))

    def on_body(self, body):
        pass

    def on_message_complete(self):
        if self._t is None or self._t.is_closing():
            return
        if MODE == "raw":
            self._t.write(_RAW_RESPONSE)
            return
        # cython mode: real massless parse->build->serialize, no Django.
        method = self._parser.get_method()
        parsed = httptools.parse_url(self._url)
        query = parsed.query if parsed.query is not None else b""
        RequestCore.py_create(method, parsed.path, query, self._headers, b"")
        resp = Response(200, {}, _BODY, b"application/json", b"OK")
        self._t.write(resp.to_bytes(True, method))

    def data_received(self, data):
        self._parser.feed_data(data)


async def _main():
    loop = asyncio.get_running_loop()
    server = await loop.create_server(_Proto, "127.0.0.1", PORT)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    uvloop.install()
    asyncio.run(_main())
