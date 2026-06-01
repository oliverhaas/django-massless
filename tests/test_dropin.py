"""Drop-in end-to-end: a normal Django project (settings/urls.py views + MIDDLEWARE)
served by the real uvloop server through MasslessHandler returns responses matching
Django. Proves a sync view AND an async view both serve correctly, plus a 404 from
the resolver, and parity against Django's own response for the same request."""

import socket
import threading
import time
import urllib.error
import urllib.request

import pytest


@pytest.fixture
def server():
    import asyncio

    import uvloop
    from massless._protocol import MasslessProtocol

    from massless.handler import MasslessHandler

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
        handler = MasslessHandler()
        srv = loop.run_until_complete(loop.create_server(lambda: MasslessProtocol(handler), "127.0.0.1", port))
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
    yield f"http://127.0.0.1:{port}"
    hold["loop"].call_soon_threadsafe(hold["loop"].stop)
    t.join(5)


def _get(url):
    with urllib.request.urlopen(url, timeout=5) as r:
        return r.status, r.read()


def test_normal_django_view_served(server):
    status, body = _get(server + "/items/7?q=hi")
    assert status == 200
    assert b'"item_id": 7' in body and b'"q": "hi"' in body


def test_sync_view_served(server):
    status, body = _get(server + "/sync")
    assert status == 200
    assert body == b"sync-ok"


def test_cbv_async_view_served(server):
    status, body = _get(server + "/cbv")
    assert status == 200
    assert b'"cbv": true' in body


def test_unknown_path_404(server):
    with pytest.raises(urllib.error.HTTPError) as e:
        _get(server + "/missing")
    assert e.value.code == 404


def test_responses_match_django_test_client(server):
    # FIDELITY: the body served through massless matches Django's own response for
    # the same request, for both an async and a sync view.
    from django.test import Client

    client = Client()

    massless_status, massless_body = _get(server + "/items/7?q=hi")
    dj = client.get("/items/7?q=hi", HTTP_HOST="testserver")
    assert massless_status == dj.status_code
    assert massless_body == dj.content

    msl_status, msl_body = _get(server + "/sync")
    dj_sync = client.get("/sync", HTTP_HOST="testserver")
    assert msl_status == dj_sync.status_code
    assert msl_body == dj_sync.content


def test_streaming_response_returns_clear_501(server):
    # Streaming is a later phase; massless must return a clear 501, not an opaque 500
    # from the serializer hitting a StreamingHttpResponse (which has no .content).
    with pytest.raises(urllib.error.HTTPError) as e:
        _get(server + "/stream")
    assert e.value.code == 501


def test_request_finished_signal_fires(server):
    # FIDELITY: the Django response is closed after serializing, so request_finished
    # fires and per-request resources (DB connections, temp files) are released, as
    # under Django's own handlers.
    from django.core.signals import request_finished

    fired = []

    def receiver(**kwargs):
        fired.append(True)

    request_finished.connect(receiver)
    try:
        _get(server + "/sync")
        time.sleep(0.2)  # let the response task finish on the server loop
    finally:
        request_finished.disconnect(receiver)
    assert fired, "request_finished should fire after the response is served"
