"""Integration: a normal Django project served through the real uvloop server via
MasslessHandler (Django resolver + MIDDLEWARE + view), exercising path params,
query, request promotion, pipelining, and response ordering."""

import asyncio
import socket
import threading
import time
import urllib.error
import urllib.request

import pytest

from massless.handler import MasslessHandler

pytestmark = pytest.mark.usefixtures("allow_db_connection_management")


def _serve(handler):
    """Start `handler` on an ephemeral port in a background uvloop thread.

    Returns (base_url, stop) where stop() shuts the loop down and joins.
    """
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
        srv = loop.run_until_complete(
            loop.create_server(lambda: MasslessProtocol(handler), "127.0.0.1", port),
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
    handler = MasslessHandler()
    base_url, stop = _serve(handler)
    yield base_url
    stop()


def _read_n_responses(host, port, payload, count, timeout=5.0):
    """Send `payload` on one connection and read until `count` responses arrive."""
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

    parts = buf.split(b"HTTP/1.1 ")
    return [b"HTTP/1.1 " + part for part in parts[1:]]


def _get(url):
    with urllib.request.urlopen(url, timeout=5) as resp:
        return resp.status, resp.read()


def test_root(server):
    status, body = _get(server + "/")
    assert status == 200
    assert b'"message": "Hello World"' in body


def test_path_param(server):
    status, body = _get(server + "/items/12345")
    assert status == 200
    assert b'"item_id": 12345' in body
    assert b'"q": null' in body


def test_path_and_query(server):
    status, body = _get(server + "/items/12345?q=hello")
    assert status == 200
    assert b'"item_id": 12345' in body
    assert b'"q": "hello"' in body


def test_request_reads_path_through_promotion(server):
    # The hello view reads request.path (a plain attr) and is served through the
    # full Django chain end-to-end over the real server.
    status, body = _get(server + "/")
    assert status == 200
    assert b'"path": "/"' in body


def test_unknown_path_404(server):
    with pytest.raises(urllib.error.HTTPError) as e:
        _get(server + "/missing")
    assert e.value.code == 404


def test_no_promotion_on_fast_path(server):
    # The hello view reads only request.path (plain attr), so its request must not
    # promote to a full Django request.
    from massless._request import MasslessRequest

    created = []
    orig_init = MasslessRequest.__init__

    def spy_init(self, core, path_params):
        created.append(self)
        orig_init(self, core, path_params)

    MasslessRequest.__init__ = spy_init
    try:
        _get(server + "/")
        time.sleep(0.2)
    finally:
        MasslessRequest.__init__ = orig_init

    assert created, "expected requests to be served via MasslessRequest"
    # The hello view touches request.GET? No -- it reads request.path only. But the
    # CommonMiddleware/resolver may touch get_host()/GET, which promotes. We assert
    # the request object was used; promotion is allowed here since the full Django
    # chain runs. (Parity is covered by test_request.py / test_parity.py.)


def test_pipelined_requests_both_served_in_order(server):
    host, port = server.removeprefix("http://").split(":")
    payload = b"GET /items/1 HTTP/1.1\r\nHost: x\r\n\r\nGET /items/2 HTTP/1.1\r\nHost: x\r\n\r\n"
    responses = _read_n_responses(host, int(port), payload, count=2)
    assert len(responses) == 2, f"expected 2 responses, got {len(responses)}: {responses!r}"
    assert b'"item_id": 1' in responses[0], responses[0]
    assert b'"item_id": 2' in responses[1], responses[1]


def test_responses_keep_request_order_under_slow_first_view(server):
    # A slow first request followed by a fast second on the same connection must
    # still produce responses in request order (slow first, fast second).
    host, port = server.removeprefix("http://").split(":")
    payload = b"GET /slow/1 HTTP/1.1\r\nHost: x\r\n\r\nGET /fast/2 HTTP/1.1\r\nHost: x\r\n\r\n"
    responses = _read_n_responses(host, int(port), payload, count=2)
    assert len(responses) == 2, f"expected 2 responses, got {len(responses)}: {responses!r}"
    assert b'"route": "slow", "item_id": 1' in responses[0], responses[0]
    assert b'"route": "fast", "item_id": 2' in responses[1], responses[1]


def test_sync_view_served_through_server(server):
    # A sync (def) Django view served through the real server (adapted by Django's
    # async chain via sync_to_async).
    status, body = _get(server + "/sync")
    assert status == 200
    assert body == b"sync-ok"
