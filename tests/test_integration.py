import asyncio
import socket
import threading
import time
import urllib.error
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


def test_bench_phase3_endpoints_registered():
    import importlib

    bench = importlib.import_module("benchmarks.app")
    router = bench.api.build_router()
    for path in (b"/auth/context", b"/auth/me", b"/cors/ping", b"/limited"):
        rid = router.match(path)[0]
        assert rid != -1, f"{path!r} did not match"
        # The fast-tier endpoints carry a compiled middleware chain.
        assert bench.api.routes[rid].middleware


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


# --- Phase 3 Task 8/9: fast-tier middleware + bridge through the server ---


def _make_jwt(claims, secret):
    import hashlib
    import hmac
    import json
    from base64 import urlsafe_b64encode

    def b64(data):
        return urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

    header = b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = b64(json.dumps(claims).encode())
    signing_input = f"{header}.{payload}".encode("ascii")
    sig = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
    return f"{header}.{payload}.{b64(sig)}"


def _req(url, headers=None, method="GET"):
    req = urllib.request.Request(url, method=method)
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def test_sync_view_serves_200_through_executor():
    # A sync (def) view dispatches through the thread-pool executor over the real
    # server and serves a 200 with the JSON body.
    api = MasslessAPI()

    @api.get("/sync-hello")
    def sync_hello():
        return {"message": "Hello World"}

    base_url, stop = _serve(api)
    try:
        status, body = _get(base_url + "/sync-hello")
    finally:
        stop()
    assert status == 200
    assert body == b'{"message":"Hello World"}'


def test_bench_sync_endpoint_registered():
    import importlib

    bench = importlib.import_module("benchmarks.app")
    router = bench.api.build_router()
    rid = router.match(b"/sync-hello")[0]
    assert rid != -1
    # It is registered as a sync route (runs on the executor).
    assert bench.api.routes[rid].is_async is False


@pytest.fixture
def mw_server():
    from massless._middleware import CORS, JWTAuth

    api = MasslessAPI()
    secret = "s3cret"

    @api.get("/auth/context", middleware=[CORS(allow_origins=["https://ex.com"]), JWTAuth(secret=secret)])
    async def auth_context(request):
        return {"sub": request.auth["sub"]}

    base_url, stop = _serve(api)
    yield base_url, secret
    stop()


def test_cors_preflight_204_through_server(mw_server):
    base_url, _ = mw_server
    status, headers, _ = _req(
        base_url + "/auth/context",
        method="OPTIONS",
        headers={"Origin": "https://ex.com", "Access-Control-Request-Method": "GET"},
    )
    assert status == 204
    assert headers.get("Access-Control-Allow-Origin") == "https://ex.com"


def test_valid_jwt_200_with_cors_header(mw_server):
    import time as _t

    base_url, secret = mw_server
    token = _make_jwt({"sub": "99", "exp": _t.time() + 3600}, secret)
    status, headers, body = _req(
        base_url + "/auth/context",
        headers={"Authorization": "Bearer " + token, "Origin": "https://ex.com"},
    )
    assert status == 200
    assert body == b'{"sub":"99"}'
    # CORS after() added the header to the real response.
    assert headers.get("Access-Control-Allow-Origin") == "https://ex.com"


def test_bad_token_401_through_server(mw_server):
    base_url, _ = mw_server
    status, _, _ = _req(base_url + "/auth/context", headers={"Authorization": "Bearer not.a.jwt"})
    assert status == 401


def test_missing_token_401_through_server(mw_server):
    base_url, _ = mw_server
    status, _, _ = _req(base_url + "/auth/context")
    assert status == 401


def test_jwt_endpoint_no_promotion(mw_server):
    # A JWT endpoint that only reads request.auth must not promote.
    from massless._request import MasslessRequest

    base_url, secret = mw_server
    import time as _t

    token = _make_jwt({"sub": "5", "exp": _t.time() + 3600}, secret)

    created = []
    orig_init = MasslessRequest.__init__

    def spy_init(self, core, path_params):
        created.append(self)
        orig_init(self, core, path_params)

    MasslessRequest.__init__ = spy_init
    try:
        _req(base_url + "/auth/context", headers={"Authorization": "Bearer " + token})
        time.sleep(0.2)
    finally:
        MasslessRequest.__init__ = orig_init

    assert created
    for req in created:
        assert req._is_django is False


def test_bridged_route_through_server():
    from django.test import override_settings

    with override_settings(MIDDLEWARE=["tests.bridge_mw.AddHeaderMiddleware"]):
        api = MasslessAPI()

        @api.get("/bridged", bridge=True)
        async def bridged(request):
            return {"path_seen": request.path}

        base_url, stop = _serve(api)
        try:
            status, headers, body = _req(base_url + "/bridged")
        finally:
            stop()

    assert status == 200
    assert headers.get("X-Bridge") == "1"
    assert headers.get("X-Bridge-Path") == "/bridged"
    assert body == b'{"path_seen": "/bridged"}'
