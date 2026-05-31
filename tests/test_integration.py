import socket
import threading
import time
import urllib.request

import pytest

from massless.app import MasslessAPI


@pytest.fixture
def server():
    api = MasslessAPI()

    @api.get("/")
    async def root():
        return {"message": "Hello World"}

    @api.get("/items/{item_id}")
    async def item(item_id: int, q: str | None = None):
        return {"item_id": item_id, "q": q}

    # bind an ephemeral port
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()

    import asyncio

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
    yield f"http://127.0.0.1:{port}"
    loop_holder["loop"].call_soon_threadsafe(loop_holder["loop"].stop)
    thread.join(timeout=5)


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
        # No promotion: the latch attribute was never set, and Django state was never
        # materialized (touching .GET still raises, as on a pristine fast-path request).
        assert not hasattr(req, "_is_django")
        with pytest.raises(AttributeError):
            _ = req.GET
