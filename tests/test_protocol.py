import asyncio

import pytest
from massless._protocol import dispatch, parse_request

from massless.handler import MasslessHandler

pytestmark = pytest.mark.usefixtures("allow_db_connection_management")


def test_parse_get_request_to_core():
    raw = b"GET /items/12345?q=hello HTTP/1.1\r\nHost: x\r\nX-Test: val\r\n\r\n"
    core = parse_request(raw)
    assert core.method == "GET"
    assert core.path == "/items/12345"
    assert core.query_param("q") == "hello"
    assert core.get_header("x-test") == "val"


def test_dispatch_runs_request_through_handler():
    core = parse_request(b"GET /items/7?q=hi HTTP/1.1\r\nHost: x\r\n\r\n")
    handler = MasslessHandler()
    raw, keep_alive = asyncio.run(dispatch(handler, core))
    assert raw.startswith(b"HTTP/1.1 200 OK\r\n")
    assert b'"item_id": 7' in raw
    assert keep_alive is True
