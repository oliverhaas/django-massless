import asyncio
import socket
import threading
import time
import urllib.request

import pytest

from massless.app import MasslessAPI


def _serve(api):
    """Start `api` on an ephemeral port in a background uvloop thread.

    Returns (base_url, stop) where stop() shuts the loop down and joins.
    """
    # bind an ephemeral port
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()

    import uvloop
    from massless._protocol import MasslessProtocol

    ready = threading.Event()
    loop_holder = {}

    def run():
        loop = uvloop.new_event_loop()
        asyncio.set_event_loop(loop)
        loop_holder["loop"] = loop
        router = api.build_router()
        srv = loop.run_until_complete(
            loop.create_server(lambda: MasslessProtocol(api, router), "127.0.0.1", port),
        )
        ready.set()
        try:
            loop.run_forever()
        finally:
            srv.close()
            loop.run_until_complete(srv.wait_closed())

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    ready.wait(timeout=5)
    time.sleep(0.1)

    def stop():
        loop_holder["loop"].call_soon_threadsafe(loop_holder["loop"].stop)
        thread.join(timeout=5)

    return f"http://127.0.0.1:{port}", stop


@pytest.fixture
def server():
    api = MasslessAPI()

    @api.get("/")
    async def root():
        return {"message": "Hello World"}

    @api.get("/items/{item_id}")
    async def item(item_id: int, q: str | None = None):
        return {"item_id": item_id, "q": q}

    @api.get("/whoami")
    async def whoami(request):
        # Touches Django state (get_host()), proving request injection drives
        # promotion through the real pipeline.
        return {"host": request.get_host(), "method": request.method}

    base_url, stop = _serve(api)
    yield base_url
    stop()


@pytest.fixture
def ordering_server():
    """Two routes: /slow/{id} sleeps before returning, /fast/{id} returns at once."""
    api = MasslessAPI()

    @api.get("/slow/{item_id}")
    async def slow(item_id: int):
        await asyncio.sleep(0.2)
        return {"route": "slow", "item_id": item_id}

    @api.get("/fast/{item_id}")
    async def fast(item_id: int):
        return {"route": "fast", "item_id": item_id}

    base_url, stop = _serve(api)
    yield base_url
    stop()


def _read_n_responses(host, port, payload, count, timeout=5.0):
    """Send `payload` on one connection and read until `count` responses arrive.

    Returns the list of response byte blobs (status line + headers + body),
    split on the Content-Length boundary, in the order received.
    """
    sock = socket.create_connection((host, port), timeout=timeout)
    sock.settimeout(timeout)
    try:
        sock.sendall(payload)
        buf = b""
        deadline = time.monotonic() + timeout
        while buf.count(b"HTTP/1.1") < count and time.monotonic() < deadline:
            chunk = sock.recv(65536)
            if not chunk:
                break
            buf += chunk
    finally:
        sock.close()

    # split the concatenated responses on each status line
    parts = buf.split(b"HTTP/1.1 ")
    return [b"HTTP/1.1 " + part for part in parts[1:]]


def _get(url):
    with urllib.request.urlopen(url, timeout=5) as resp:
        return resp.status, resp.read()


def test_root(server):
    status, body = _get(server + "/")
    assert status == 200
    assert body == b'{"message":"Hello World"}'


def test_path_param(server):
    status, body = _get(server + "/items/12345")
    assert status == 200
    assert body == b'{"item_id":12345,"q":null}'


def test_path_and_query(server):
    status, body = _get(server + "/items/12345?q=hello")
    assert status == 200
    assert body == b'{"item_id":12345,"q":"hello"}'


def test_request_injection_and_promotion_end_to_end(server):
    # A view declaring `request` receives the injected MasslessRequest and
    # promotes when it touches a Django attr (get_host()), end-to-end over the
    # real server. The Host header is "127.0.0.1:<port>" for urllib requests.
    host = server.removeprefix("http://")
    status, body = _get(server + "/whoami")
    assert status == 200
    assert body == f'{{"host":"{host}","method":"GET"}}'.encode()


def test_no_promotion_on_fast_path(server):
    from massless._request import MasslessRequest

    created = []
    orig_init = MasslessRequest.__init__

    def spy_init(self, core, path_params):
        created.append(self)
        orig_init(self, core, path_params)

    MasslessRequest.__init__ = spy_init
    try:
        _get(server + "/")
        _get(server + "/items/12345?q=hello")
        import time

        time.sleep(0.2)  # let the response tasks finish
    finally:
        MasslessRequest.__init__ = orig_init

    assert created, "expected requests to be served via MasslessRequest"
    for req in created:
        # No promotion: the latch was never flipped (Phase 2 initializes it to
        # False at construction; only a Django-state access sets it True). The
        # fast-path endpoints never touch Django state, so it stays False.
        assert req._is_django is False


def test_bench_app_importable_and_serves(tmp_path):
    import importlib

    bench = importlib.import_module("benchmarks.app")
    router = bench.api.build_router()
    assert router.match(b"/")[0] != -1
    assert router.match(b"/10k-json")[0] != -1
    assert router.match(b"/items/5")[0] != -1


def test_pipelined_requests_both_served_in_order(server):
    # C2: two requests in one buffer must both be served, in arrival order.
    host, port = server.removeprefix("http://").split(":")
    payload = b"GET /items/1 HTTP/1.1\r\nHost: x\r\n\r\nGET /items/2 HTTP/1.1\r\nHost: x\r\n\r\n"
    responses = _read_n_responses(host, int(port), payload, count=2)
    assert len(responses) == 2, f"expected 2 responses, got {len(responses)}: {responses!r}"
    assert responses[0].endswith(b'{"item_id":1,"q":null}'), responses[0]
    assert responses[1].endswith(b'{"item_id":2,"q":null}'), responses[1]


def test_responses_keep_request_order_under_slow_first_view(ordering_server):
    # C1: a slow first request followed by a fast second on the same connection
    # must still produce responses in request order (slow first, fast second).
    host, port = ordering_server.removeprefix("http://").split(":")
    payload = b"GET /slow/1 HTTP/1.1\r\nHost: x\r\n\r\nGET /fast/2 HTTP/1.1\r\nHost: x\r\n\r\n"
    responses = _read_n_responses(host, int(port), payload, count=2)
    assert len(responses) == 2, f"expected 2 responses, got {len(responses)}: {responses!r}"
    assert responses[0].endswith(b'{"route":"slow","item_id":1}'), responses[0]
    assert responses[1].endswith(b'{"route":"fast","item_id":2}'), responses[1]
