import asyncio

from massless._protocol import dispatch, parse_request

from massless.app import MasslessAPI


def test_parse_get_request_to_core():
    raw = b"GET /items/12345?q=hello HTTP/1.1\r\nHost: x\r\nX-Test: val\r\n\r\n"
    core = parse_request(raw)
    assert core.method == "GET"
    assert core.path == "/items/12345"
    assert core.query_param("q") == "hello"
    assert core.get_header("x-test") == "val"


def _api():
    api = MasslessAPI()

    @api.get("/items/{item_id}")
    async def item(item_id: int, q: str | None = None):
        return {"item_id": item_id, "q": q}

    return api


def test_dispatch_runs_view_and_builds_response():
    api = _api()
    router = api.build_router()
    core = parse_request(b"GET /items/7?q=hi HTTP/1.1\r\nHost: x\r\n\r\n")
    route_id, param = router.match(b"/items/7")
    raw = asyncio.run(dispatch(api, core, route_id, param))
    assert raw.startswith(b"HTTP/1.1 200 OK\r\n")
    assert raw.endswith(b'{"item_id":7,"q":"hi"}')
