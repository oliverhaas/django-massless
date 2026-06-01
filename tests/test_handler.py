import asyncio

from massless._request import MasslessRequest, RequestCore

from massless.handler import MasslessHandler


def _req(method=b"GET", path=b"/items/7", query=b"q=hi", headers=None):
    headers = headers or [(b"host", b"ex.com")]
    return MasslessRequest(RequestCore.py_create(method, path, query, headers, b""), {})


def test_handler_routes_through_django_resolver_and_middleware():
    handler = MasslessHandler()
    resp = asyncio.run(handler.handle(_req()))
    assert resp.status_code == 200
    assert b'"item_id": 7' in resp.content
    assert b'"q": "hi"' in resp.content


def test_handler_404_for_unknown_path():
    handler = MasslessHandler()
    resp = asyncio.run(handler.handle(_req(path=b"/nope", query=b"")))
    assert resp.status_code == 404


def test_handler_runs_sync_view_without_blocking():
    handler = MasslessHandler()
    resp = asyncio.run(handler.handle(_req(method=b"GET", path=b"/sync", query=b"")))
    assert resp.status_code == 200
    assert resp.content == b"sync-ok"
