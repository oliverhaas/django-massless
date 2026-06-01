"""HTTP fidelity parity: massless must construct the request and serialize the response
the way uvicorn+Django's ASGIHandler does. Covers REMOTE_ADDR / forwarded scheme, header
folding + underscore drop + cookie folding, percent-decoded path resolution, the exact
reason phrase, HEAD / 204 / 304 framing, the Date header, keep-alive / Connection close,
Expect: 100-continue, and the request_started/request_finished signal pair.
"""

import asyncio
import json
import socket
import threading
import time
import urllib.request
from email.utils import parsedate_to_datetime
from types import SimpleNamespace

import httptools
import pytest
from massless._protocol import _Collector, dispatch, parse_request
from massless._request import MasslessRequest, RequestCore

from massless.handler import MasslessHandler

pytestmark = pytest.mark.usefixtures("allow_db_connection_management")


# --------------------------------------------------------------------------- helpers


def _req(method=b"GET", path=b"/", query=b"", headers=None, body=b"", client=None, server=None):  # noqa: PLR0913
    core = RequestCore.py_create(method, path, query, headers or [], body, client, server)
    return MasslessRequest(core, {})


@pytest.fixture(scope="module")
def handler():
    return MasslessHandler()


def _dispatch(handler, raw):
    return asyncio.run(dispatch(handler, parse_request(raw)))


def _collector_keep_alive(raw):
    c = _Collector()
    p = httptools.HttpRequestParser(c)
    c.set_parser(p)
    p.feed_data(raw)
    return c.requests[0][4]


# --------------------------------------------------- request: client address & scheme


def test_remote_addr_from_peer():
    req = _req(client=("203.0.113.7", 5555))
    assert req.META["REMOTE_ADDR"] == "203.0.113.7"
    assert req.META["REMOTE_HOST"] == "203.0.113.7"
    assert req.META["REMOTE_PORT"] == "5555"


def test_no_remote_addr_without_peer():
    # No TCP peer (e.g. a unix socket) -> absent, mirroring Django's guarded set.
    assert _req(client=None).META.get("REMOTE_ADDR") is None


def test_x_forwarded_proto_from_trusted_peer_sets_https():
    req = _req(headers=[(b"x-forwarded-proto", b"https"), (b"host", b"ex.com")], client=("127.0.0.1", 9))
    assert req.scheme == "https"
    assert req.is_secure() is True


def test_x_forwarded_proto_from_untrusted_peer_ignored():
    req = _req(headers=[(b"x-forwarded-proto", b"https")], client=("203.0.113.9", 9))
    assert req.scheme == "http"
    assert req.is_secure() is False


def test_duplicate_x_forwarded_proto_ignored():
    # Two copies -> spoofing risk, so neither is trusted (uvicorn parity).
    req = _req(
        headers=[(b"x-forwarded-proto", b"https"), (b"x-forwarded-proto", b"https")],
        client=("127.0.0.1", 9),
    )
    assert req.scheme == "http"


def test_x_forwarded_for_from_trusted_peer_sets_remote_addr():
    req = _req(headers=[(b"x-forwarded-for", b"8.8.8.8"), (b"host", b"ex.com")], client=("127.0.0.1", 9))
    assert req.META["REMOTE_ADDR"] == "8.8.8.8"


def test_server_name_port_from_local_address_not_host_header():
    # SERVER_NAME/SERVER_PORT track the bind address (Django scope["server"]); the Host
    # header is HTTP_HOST / get_host(), a separate thing.
    req = _req(headers=[(b"host", b"example.com:9999")], server=("127.0.0.1", 8000))
    assert req.META["SERVER_NAME"] == "127.0.0.1"
    assert req.META["SERVER_PORT"] == "8000"
    assert req.get_host() == "example.com:9999"


# ------------------------------------------------------- request: header construction


def test_duplicate_request_headers_comma_joined():
    req = _req(headers=[(b"accept", b"a"), (b"accept", b"b"), (b"host", b"ex.com")])
    assert req.META["HTTP_ACCEPT"] == "a,b"


def test_underscore_header_dropped():
    # A header whose name contains "_" is dropped (underscore/hyphen spoofing guard).
    req = _req(headers=[(b"x_evil", b"1"), (b"host", b"ex.com")])
    assert "HTTP_X_EVIL" not in req.META


def test_multiple_cookie_headers_folded():
    req = _req(headers=[(b"cookie", b"a=1"), (b"cookie", b"b=2"), (b"host", b"ex.com")])
    assert req.META["HTTP_COOKIE"] == "a=1; b=2"
    assert req.COOKIES == {"a": "1", "b": "2"}


def test_path_percent_decoded_to_unicode():
    req = _req(path=b"/caf%C3%A9/", headers=[(b"host", b"ex.com")])
    assert req.path == "/café/"
    req._promote()
    assert req.path_info == "/café/"
    assert req.path == "/café/"


# -------------------------------------------------------- response: status & framing


def test_redirect_reason_phrase(handler):
    raw, _ = _dispatch(handler, b"GET /redirect HTTP/1.1\r\nHost: x\r\n\r\n")
    assert raw.startswith(b"HTTP/1.1 302 Found\r\n")


def test_created_reason_phrase(handler):
    raw, _ = _dispatch(handler, b"GET /created HTTP/1.1\r\nHost: x\r\n\r\n")
    assert raw.startswith(b"HTTP/1.1 201 Created\r\n")
    assert raw.endswith(b"\r\n\r\nmade")


def test_head_request_returns_headers_only(handler):
    raw, _ = _dispatch(handler, b"HEAD /sync HTTP/1.1\r\nHost: x\r\n\r\n")
    head, _, body = raw.partition(b"\r\n\r\n")
    assert head.startswith(b"HTTP/1.1 200 OK\r\n")
    assert b"Content-Length: 7" in head  # the would-be GET body length
    assert body == b""


def test_204_no_body_but_content_length_like_django(handler):
    from django.test import Client

    raw, _ = _dispatch(handler, b"GET /no-content HTTP/1.1\r\nHost: x\r\n\r\n")
    head, _, body = raw.partition(b"\r\n\r\n")
    assert head.startswith(b"HTTP/1.1 204 No Content\r\n")
    assert body == b""
    # Django's CommonMiddleware sets Content-Length: 0 on the 204, and uvicorn forwards
    # it; massless must emit the same value, not drop it.
    dj = Client().get("/no-content", HTTP_HOST="x")
    assert (b"\r\nContent-Length: %d\r\n" % len(dj.content)) in head
    assert b"\r\nContent-Type: text/html" in head  # 204 keeps Content-Type under Django


def test_304_no_body_no_content_type_but_content_length_like_django(handler):
    from django.test import Client

    raw, _ = _dispatch(handler, b"GET /not-modified HTTP/1.1\r\nHost: x\r\n\r\n")
    head, _, body = raw.partition(b"\r\n\r\n")
    assert head.startswith(b"HTTP/1.1 304 Not Modified\r\n")
    assert body == b""
    # 304 carries no Content-Type (HttpResponseNotModified strips it) but, like
    # Django+CommonMiddleware under uvicorn, does carry Content-Length: 0.
    assert b"\r\nContent-Type:" not in head
    dj = Client().get("/not-modified", HTTP_HOST="x")
    assert (b"\r\nContent-Length: %d\r\n" % len(dj.content)) in head


def test_present_but_empty_content_type_is_emitted(handler):
    # Django keeps a present-but-empty Content-Type; massless must emit it (not drop it
    # the way it correctly drops a 304's absent one).
    raw, _ = _dispatch(handler, b"GET /empty-ct HTTP/1.1\r\nHost: x\r\n\r\n")
    head = raw.partition(b"\r\n\r\n")[0]
    assert b"\r\nContent-Type: \r\n" in head


def test_date_header_present_and_valid(handler):
    raw, _ = _dispatch(handler, b"GET /sync HTTP/1.1\r\nHost: x\r\n\r\n")
    line = next(line for line in raw.split(b"\r\n") if line.startswith(b"Date: "))
    assert line.endswith(b" GMT")
    assert parsedate_to_datetime(line[len(b"Date: ") :].decode()) is not None


def test_non_ascii_path_resolves_like_django(handler):
    raw, _ = _dispatch(handler, b"GET /caf%C3%A9/ HTTP/1.1\r\nHost: x\r\n\r\n")
    assert raw.startswith(b"HTTP/1.1 200 OK\r\n")
    assert b'"path"' in raw


# ----------------------------------------------------- response: keep-alive lifecycle


def test_keep_alive_default_http11():
    assert _collector_keep_alive(b"GET / HTTP/1.1\r\nHost: x\r\n\r\n") is True


def test_keep_alive_false_on_connection_close():
    assert _collector_keep_alive(b"GET / HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n") is False


def test_keep_alive_false_on_http10():
    assert _collector_keep_alive(b"GET / HTTP/1.0\r\nHost: x\r\n\r\n") is False


def test_dispatch_no_connection_header_when_keep_alive(handler):
    raw, keep_alive = asyncio.run(dispatch(handler, parse_request(b"GET /sync HTTP/1.1\r\nHost: x\r\n\r\n"), True))
    assert keep_alive is True
    assert b"Connection:" not in raw


def test_dispatch_connection_close_when_not_keep_alive(handler):
    raw, keep_alive = asyncio.run(dispatch(handler, parse_request(b"GET /sync HTTP/1.1\r\nHost: x\r\n\r\n"), False))
    assert keep_alive is False
    assert b"Connection: close\r\n" in raw


# ------------------------------------------------- request_started + request_finished


def test_request_started_and_finished_fire_in_order(handler):
    from django.core.signals import request_finished, request_started

    events = []
    on_start = lambda **kw: events.append("start")  # noqa: E731
    on_finish = lambda **kw: events.append("finish")  # noqa: E731
    request_started.connect(on_start)
    request_finished.connect(on_finish)
    try:
        asyncio.run(dispatch(handler, parse_request(b"GET /sync HTTP/1.1\r\nHost: x\r\n\r\n")))
    finally:
        request_started.disconnect(on_start)
        request_finished.disconnect(on_finish)
    assert events == ["start", "finish"]


# --------------------------------------------------------------- end-to-end over a socket


@pytest.fixture
def server():
    import uvloop
    from massless._protocol import MasslessProtocol

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    ready = threading.Event()
    hold = {}

    def run():
        loop = uvloop.new_event_loop()
        asyncio.set_event_loop(loop)
        hold["loop"] = loop
        h = MasslessHandler()
        srv = loop.run_until_complete(loop.create_server(lambda: MasslessProtocol(h), "127.0.0.1", port))
        ready.set()
        try:
            loop.run_forever()
        finally:
            srv.close()
            loop.run_until_complete(srv.wait_closed())

    t = threading.Thread(target=run, daemon=True)
    t.start()
    ready.wait(5)
    time.sleep(0.1)
    yield SimpleNamespace(url=f"http://127.0.0.1:{port}", host="127.0.0.1", port=port)
    hold["loop"].call_soon_threadsafe(hold["loop"].stop)
    t.join(5)


def test_remote_addr_is_loopback_end_to_end(server):
    with urllib.request.urlopen(server.url + "/remote", timeout=5) as r:
        body = json.loads(r.read())
    assert body["remote_addr"] == "127.0.0.1"
    assert body["scheme"] == "http"
    assert body["secure"] is False


def test_expect_100_continue_answered(server):
    s = socket.create_connection((server.host, server.port), timeout=5)
    try:
        s.sendall(b"POST /sync-body HTTP/1.1\r\nHost: x\r\nContent-Length: 5\r\nExpect: 100-continue\r\n\r\n")
        s.settimeout(2)
        interim = s.recv(64)
        assert interim.startswith(b"HTTP/1.1 100 Continue\r\n\r\n")
        s.sendall(b"hello")
        rest = b""
        while b"hello" not in rest and b"\r\n\r\n" not in rest:
            chunk = s.recv(4096)
            if not chunk:
                break
            rest += chunk
        assert b"200" in rest
        assert rest.endswith(b"hello")
    finally:
        s.close()


def test_malformed_request_gets_400_and_closes(server):
    # e.g. a TLS handshake sent to the plaintext port. httptools rejects it; massless
    # answers 400 and closes instead of dropping the connection with no response.
    s = socket.create_connection((server.host, server.port), timeout=5)
    try:
        s.sendall(b"\x16\x03\x01\x00\x50\x01\x00\x00")
        s.settimeout(3)
        data = s.recv(4096)
        assert data.startswith(b"HTTP/1.1 400 Bad Request\r\n")
    finally:
        s.close()


def test_connection_close_closes_the_socket(server):
    s = socket.create_connection((server.host, server.port), timeout=5)
    try:
        s.sendall(b"GET /sync HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n")
        s.settimeout(3)
        data = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:  # server closed the connection after responding
                break
            data += chunk
        assert b"Connection: close\r\n" in data
        assert data.endswith(b"sync-ok")
    finally:
        s.close()
