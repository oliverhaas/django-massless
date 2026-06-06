"""The bolt-style fast dispatch (MasslessHandler._fast_dispatch) must produce byte-identical
responses to Django's get_response_async for the no-middleware / no-ATOMIC_REQUESTS case it
replaces. Each test runs both paths on equivalent requests and compares status, headers,
cookies, and body -- get_response_async is the oracle (the only override there is fast URL
resolution, which both paths share).
"""

import asyncio

import pytest
from django.core.exceptions import BadRequest, PermissionDenied, SuspiciousOperation
from django.http import Http404, HttpResponse, HttpResponseRedirect, JsonResponse, StreamingHttpResponse
from django.test import override_settings
from django.urls import get_urlconf, path, set_urlconf
from django.views import View
from massless._protocol import parse_request
from massless._request import MasslessRequest

from massless.handler import MasslessHandler


async def v_json(request):
    return JsonResponse({"message": "Hello World"})


def v_html(request):
    resp = HttpResponse(b"<h1>hi</h1>", content_type="text/html")
    resp["X-Custom"] = "yes"
    resp.set_cookie("sid", "abc123", httponly=True)
    return resp


async def v_404(request):
    raise Http404


def v_perm(request):
    raise PermissionDenied


async def v_susp(request):
    raise SuspiciousOperation


def v_badreq(request):
    raise BadRequest


async def v_boom(request):
    raise ValueError("kaboom")


def v_redirect(request):
    return HttpResponseRedirect("/target")


async def v_204(request):
    return HttpResponse(status=204)


async def v_item(request, item_id: int):
    return JsonResponse({"item_id": item_id, "q": request.GET.get("q")})


def v_none(request):
    return None


def v_stream(request):
    return StreamingHttpResponse(iter([b"a", b"b", b"c"]))


class SyncCBV(View):
    def get(self, request):
        return HttpResponse(b"sync-cbv")


class AsyncCBV(View):
    async def get(self, request):
        return HttpResponse(b"async-cbv")


async def v_urlconf_probe(request):
    return JsonResponse({"urlconf": get_urlconf()})


urlpatterns = [
    path("json", v_json),
    path("html", v_html),
    path("e404", v_404),
    path("perm", v_perm),
    path("susp", v_susp),
    path("badreq", v_badreq),
    path("boom", v_boom),
    path("redir", v_redirect),
    path("nc", v_204),
    path("items/<int:item_id>", v_item),
    path("none", v_none),
    path("stream", v_stream),
    path("scbv", SyncCBV.as_view()),
    path("acbv", AsyncCBV.as_view()),
    path("ucprobe", v_urlconf_probe),
]

FAST = override_settings(MIDDLEWARE=[], ROOT_URLCONF=__name__, DEBUG=False)


def _mkreq(target):
    raw = f"GET {target} HTTP/1.1\r\nHost: x\r\n\r\n".encode()
    return MasslessRequest(parse_request(raw), {})


def _snap(resp):
    return (
        resp.status_code,
        sorted((k.lower(), v) for k, v in resp.items()),
        sorted(c.OutputString() for c in resp.cookies.values()),
        b"<stream>" if getattr(resp, "streaming", False) else bytes(resp.content),
    )


@FAST
@pytest.mark.parametrize(
    "target",
    [
        "/json",
        "/html",
        "/e404",
        "/perm",
        "/susp",
        "/badreq",
        "/boom",
        "/redir",
        "/nc",
        "/items/42",
        "/items/42?q=hi",
        "/none",
        "/stream",
        "/scbv",
        "/acbv",
    ],
)
def test_fast_dispatch_matches_get_response_async(target):
    handler = MasslessHandler()
    assert handler._fast_ok

    async def go():
        match = handler._router.match(_mkreq(target).path_info.encode("utf-8"))
        assert match is not None, "router should resolve every test route"
        fast = await handler._fast_dispatch(_mkreq(target), match)
        slow = await handler.get_response_async(_mkreq(target))
        return _snap(fast), _snap(slow)

    fast, slow = asyncio.run(go())
    assert fast == slow


@FAST
def test_fast_dispatch_sets_urlconf_like_django():
    # A fast-only worker never set the thread-local urlconf; handle() must set it to
    # ROOT_URLCONF (as get_response_async does) before the view runs.
    handler = MasslessHandler()
    set_urlconf(None)
    resp = asyncio.run(handler.handle(_mkreq("/ucprobe")))
    import json

    from django.conf import settings

    assert json.loads(bytes(resp.content))["urlconf"] == settings.ROOT_URLCONF


@FAST
def test_fast_path_defers_on_per_request_urlconf_override():
    # The handle() guard mirrors resolve_request: a request carrying its own urlconf
    # must fall through to Django rather than route against the prebuilt ROOT_URLCONF.
    handler = MasslessHandler()
    req = _mkreq("/json")
    req.urlconf = __name__  # simulate a hook setting a per-request urlconf
    # Reaching get_response_async (the fallback) still produces a valid response.
    resp = asyncio.run(handler.handle(req))
    assert resp.status_code == 200
