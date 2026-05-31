import asyncio

import pytest
from django.test import override_settings
from massless._request import MasslessRequest, RequestCore

from massless.bridge import BridgeHandler


def _req(path=b"/bridged"):
    core = RequestCore.py_create(b"GET", path, b"", [(b"host", b"ex.com")], b"")
    return MasslessRequest(core, {})


async def _view():
    return {"ok": True}


@override_settings(MIDDLEWARE=["tests.bridge_mw.AddHeaderMiddleware"])
def test_bridge_runs_real_sync_middleware():
    # Promote before running the bridge (the protocol does this for bridge routes).
    req = _req()
    req._promote()
    handler = BridgeHandler()
    resp = asyncio.run(handler.run(req, _view, {}))
    # The real Django middleware set the header...
    assert resp["X-Bridge"] == "1"
    # ...and observed the (promoted) request's path.
    assert resp["X-Bridge-Path"] == "/bridged"
    assert req._bridge_saw_path == "/bridged"
    # The request promoted (the middleware ran against a real HttpRequest).
    assert req._is_django is True
    # The view's dict became a JSON response.
    assert resp.status_code == 200
    assert b'"ok"' in resp.content


@override_settings(MIDDLEWARE=["tests.bridge_mw.AsyncAddHeaderMiddleware"])
def test_bridge_runs_real_async_middleware():
    req = _req(b"/async-bridged")
    req._promote()
    handler = BridgeHandler()
    resp = asyncio.run(handler.run(req, _view, {}))
    assert resp["X-Bridge-Async"] == "1"
    assert resp["X-Bridge-Path"] == "/async-bridged"
    assert req._is_django is True


@override_settings(MIDDLEWARE=["tests.bridge_mw.AddHeaderMiddleware"])
def test_bridge_passes_view_kwargs():
    async def echo(item_id):
        return {"item_id": item_id}

    req = _req(b"/items/9")
    req._promote()
    handler = BridgeHandler()
    resp = asyncio.run(handler.run(req, echo, {"item_id": 9}))
    assert resp.status_code == 200
    assert b'"item_id": 9' in resp.content or b'"item_id":9' in resp.content


@override_settings(
    MIDDLEWARE=[
        "tests.bridge_mw.AsyncAddHeaderMiddleware",
        "tests.bridge_mw.AddHeaderMiddleware",
    ],
)
def test_bridge_mixed_sync_and_async_middleware():
    # Async middleware outermost, sync middleware inner: Django's adapt_method_mode
    # bridges the sync one with sync_to_async. Both headers must appear.
    req = _req(b"/mixed")
    req._promote()
    handler = BridgeHandler()
    resp = asyncio.run(handler.run(req, _view, {}))
    assert resp["X-Bridge"] == "1"
    assert resp["X-Bridge-Async"] == "1"
    assert req._is_django is True


@pytest.mark.django_db
@override_settings(
    MIDDLEWARE=[
        "django.contrib.auth.middleware.AuthenticationMiddleware",
        "tests.bridge_mw.AddHeaderMiddleware",
    ],
)
def test_bridge_with_auth_middleware_sets_request_user():
    # AuthenticationMiddleware assigns request.user; our property setter must
    # honor it without blowing up. SessionMiddleware is not installed, so
    # AuthenticationMiddleware falls back to setting an AnonymousUser lazily.
    from django.contrib.sessions.middleware import SessionMiddleware  # noqa: F401

    req = _req(b"/secured")
    req._promote()
    # AuthenticationMiddleware needs request.session; provide an empty dict-like.
    req.session = {}
    handler = BridgeHandler()
    resp = asyncio.run(handler.run(req, _view, {}))
    assert resp["X-Bridge"] == "1"
    # request.user is now set (lazy AnonymousUser) without raising.
    assert req.user is not None


@override_settings(MIDDLEWARE=["tests.bridge_mw.AddHeaderMiddleware"])
def test_bridge_path_runs_fast_tier_after_hooks():
    # A bridged route that is ALSO CORS-wrapped must still get the fast-tier after()
    # response headers (after() runs uniformly on the bridge path, not just the
    # fast path). Exercises dispatch end-to-end for a bridge=True route.
    from massless._middleware import CORS
    from massless._protocol import dispatch

    from massless.app import MasslessAPI

    api = MasslessAPI()

    @api.get("/b", middleware=[CORS(allow_origins=["https://ex.com"])], bridge=True)
    async def view():
        return {"ok": True}

    core = RequestCore.py_create(
        b"GET",
        b"/b",
        b"",
        [(b"host", b"ex.com"), (b"origin", b"https://ex.com")],
        b"",
    )
    raw = asyncio.run(dispatch(api, core, 0, -1))
    assert b"X-Bridge: 1" in raw  # the Django middleware ran (bridge promoted + chained)
    assert b"Access-Control-Allow-Origin: https://ex.com" in raw  # fast-tier after() ran on the bridge path
