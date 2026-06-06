"""The massless-owned middleware chain (massless._chain.MasslessChain) must be
observationally identical to Django's get_response_async for any middleware stack.

Phase 1 builds the chain as pure delegation: every settings.MIDDLEWARE entry is the
real Django middleware instance, wrapped exactly as Django's load_middleware wraps it.
So chain.run(request) and handler.get_response_async(request) -- which runs Django's own
self._middleware_chain -- must produce byte-identical responses. get_response_async is the
oracle. These tests fix that equivalence before any fast re-implementation is substituted.

Two kinds of test:
- the differential: real, deterministic middleware over many view/request shapes, asserting
  identical status/headers/cookies/body from both paths.
- ordering: instrumented synthetic middleware, asserting the chain runs the request/response/
  view/exception/template hooks in Django's documented order.
"""

import asyncio

import pytest
from asgiref.sync import iscoroutinefunction, markcoroutinefunction
from django.core.exceptions import MiddlewareNotUsed
from django.http import Http404, HttpResponse, HttpResponseRedirect, JsonResponse
from django.template.response import SimpleTemplateResponse
from django.test import override_settings
from django.urls import path
from django.views import View
from massless._protocol import parse_request
from massless._request import MasslessRequest

from massless.handler import MasslessHandler

# --------------------------------------------------------------------------- views


async def v_json(request):
    return JsonResponse({"message": "Hello World"})


def v_html(request):
    resp = HttpResponse(b"<h1>hi</h1>", content_type="text/html")
    resp["X-Custom"] = "yes"
    resp.set_cookie("sid", "abc123", httponly=True)
    return resp


def v_redirect(request):
    return HttpResponseRedirect("/target")


async def v_404(request):
    raise Http404


def v_boom(request):
    raise ValueError("kaboom")


async def v_204(request):
    return HttpResponse(status=204)


async def v_item(request, item_id: int):
    return JsonResponse({"item_id": item_id, "q": request.GET.get("q")})


def v_etag(request):
    resp = HttpResponse(b"cacheable")
    resp["ETag"] = '"abc"'
    return resp


def v_big(request):
    return HttpResponse(b"x" * 500, content_type="text/plain")


class SyncCBV(View):
    def get(self, request):
        return HttpResponse(b"sync-cbv")


class AsyncCBV(View):
    async def get(self, request):
        return HttpResponse(b"async-cbv")


# ----------------------------------------------------------------- synthetic middleware
# Module-level so MIDDLEWARE dotted paths resolve. They record into RECORD (reset per test)
# and set response headers so the differential sees their effect, not just their order.

RECORD: list[str] = []


class MwA:
    async_capable = True
    sync_capable = False

    def __init__(self, get_response):
        self.get_response = get_response
        if iscoroutinefunction(get_response):
            markcoroutinefunction(self)

    async def __call__(self, request):
        RECORD.append("A:req")
        response = await self.get_response(request)
        RECORD.append("A:resp")
        response["X-A"] = "1"
        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        RECORD.append("A:view")


class MwB:
    async_capable = True
    sync_capable = False

    def __init__(self, get_response):
        self.get_response = get_response
        if iscoroutinefunction(get_response):
            markcoroutinefunction(self)

    async def __call__(self, request):
        RECORD.append("B:req")
        response = await self.get_response(request)
        RECORD.append("B:resp")
        response["X-B"] = "1"
        return response

    def process_exception(self, request, exception):
        RECORD.append("B:exc")
        if isinstance(exception, ValueError):
            return HttpResponse(b"handled-by-B", status=500)
        return None


class MwC:
    async_capable = True
    sync_capable = False

    def __init__(self, get_response):
        self.get_response = get_response
        if iscoroutinefunction(get_response):
            markcoroutinefunction(self)

    async def __call__(self, request):
        RECORD.append("C:req")
        response = await self.get_response(request)
        RECORD.append("C:resp")
        response["X-C"] = "1"
        return response


class MwShortCircuit:
    async_capable = True
    sync_capable = False

    def __init__(self, get_response):
        self.get_response = get_response
        if iscoroutinefunction(get_response):
            markcoroutinefunction(self)

    async def __call__(self, request):
        return await self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        if request.path == "/sc":
            return HttpResponse(b"short-circuited", status=200)
        return None


class MwAsyncView:
    """A middleware using the fork's native-async aprocess_view hook (ignored by stock)."""

    async_capable = True
    sync_capable = False

    def __init__(self, get_response):
        self.get_response = get_response
        if iscoroutinefunction(get_response):
            markcoroutinefunction(self)

    async def __call__(self, request):
        return await self.get_response(request)

    async def aprocess_view(self, request, view_func, view_args, view_kwargs):
        if request.path == "/sc":
            return HttpResponse(b"async-view-sc", status=200)
        return None


class MwNotUsed:
    def __init__(self, get_response):
        raise MiddlewareNotUsed


def _django_honors_aprocess_view():
    import inspect

    from django.core.handlers.base import BaseHandler

    return "aprocess_view" in inspect.getsource(BaseHandler.load_middleware)


class _DeferredResponse(SimpleTemplateResponse):
    """A deferred-render response with no template engine: render() fills content from
    rendered_content (overridden) so the chain's template-response branch is exercised
    without configuring TEMPLATES."""

    def __init__(self):
        super().__init__(template="unused", content_type="text/plain")

    @property
    def rendered_content(self):
        return "rendered-body"


def v_template(request):
    return _DeferredResponse()


class MwTemplate:
    async_capable = True
    sync_capable = False

    def __init__(self, get_response):
        self.get_response = get_response
        if iscoroutinefunction(get_response):
            markcoroutinefunction(self)

    async def __call__(self, request):
        return await self.get_response(request)

    def process_template_response(self, request, response):
        RECORD.append("T:tpl")
        response["X-Template"] = "seen"
        return response


M = __name__
SECURITY = "django.middleware.security.SecurityMiddleware"
COMMON = "django.middleware.common.CommonMiddleware"
XFRAME = "django.middleware.clickjacking.XFrameOptionsMiddleware"
CONDITIONAL = "django.middleware.http.ConditionalGetMiddleware"
GZIP = "django.middleware.gzip.GZipMiddleware"

urlpatterns = [
    path("json", v_json),
    path("html", v_html),
    path("redir", v_redirect),
    path("e404", v_404),
    path("boom", v_boom),
    path("nc", v_204),
    path("items/<int:item_id>", v_item),
    path("etag", v_etag),
    path("scbv", SyncCBV.as_view()),
    path("acbv", AsyncCBV.as_view()),
    path("sc", v_json),
    path("tpl", v_template),
    path("slash/", v_json),
    path("big", v_big),
]

REAL_STACK = [SECURITY, COMMON, XFRAME, CONDITIONAL, GZIP]
SYNTH_STACK = [f"{M}.MwA", f"{M}.MwB", f"{M}.MwC"]


def _mkreq(target, method="GET", headers=()):
    lines = [f"{method} {target} HTTP/1.1", "Host: x"]
    lines += [f"{k}: {v}" for k, v in headers]
    raw = ("\r\n".join(lines) + "\r\n\r\n").encode()
    return MasslessRequest(parse_request(raw), {})


def _snap(resp):
    return (
        resp.status_code,
        sorted((k.lower(), v) for k, v in resp.items()),
        sorted(c.OutputString() for c in resp.cookies.values()),
        b"<stream>" if getattr(resp, "streaming", False) else bytes(resp.content),
    )


def _run_both(stack, target, method="GET", headers=()):
    """Build a handler under `stack`, run the request through the chain and through
    Django's get_response_async on fresh equivalent requests, return both snapshots."""
    with override_settings(MIDDLEWARE=stack, ROOT_URLCONF=M, DEBUG=False):
        handler = MasslessHandler()

        async def go():
            chain = await handler._chain.run(_mkreq(target, method, headers))
            oracle = await handler.get_response_async(_mkreq(target, method, headers))
            return _snap(chain), _snap(oracle)

        return asyncio.run(go())


# --------------------------------------------------------------------------- differential

_REQUESTS = [
    ("/json", "GET", ()),
    ("/html", "GET", ()),
    ("/redir", "GET", ()),
    ("/e404", "GET", ()),
    ("/boom", "GET", ()),
    ("/nc", "GET", ()),
    ("/items/42", "GET", ()),
    ("/items/42?q=hi", "GET", ()),
    ("/etag", "GET", ()),
    ("/etag", "GET", (("If-None-Match", '"abc"'),)),  # ConditionalGet -> 304
    ("/scbv", "GET", ()),
    ("/acbv", "GET", ()),
    ("/missing", "GET", ()),  # resolver 404 through the chain
    ("/slash", "GET", ()),  # CommonMiddleware APPEND_SLASH 301 -> /slash/
    ("/etag", "POST", ()),  # ConditionalGet bails on non-GET
    ("/big", "GET", ()),  # >=200 body, no gzip accept: GZip adds Vary only (deterministic)
]


@pytest.mark.parametrize(("target", "method", "headers"), _REQUESTS)
def test_chain_matches_get_response_async_real_stack(target, method, headers):
    chain, oracle = _run_both(REAL_STACK, target, method, headers)
    assert chain == oracle


@pytest.mark.parametrize(("target", "method", "headers"), _REQUESTS)
def test_chain_matches_get_response_async_synth_stack(target, method, headers):
    chain, oracle = _run_both(SYNTH_STACK, target, method, headers)
    assert chain == oracle


@pytest.mark.parametrize(("target", "method", "headers"), _REQUESTS)
def test_chain_matches_get_response_async_combined_stack(target, method, headers):
    chain, oracle = _run_both([*REAL_STACK, *SYNTH_STACK], target, method, headers)
    assert chain == oracle


def test_chain_matches_with_short_circuit_and_notused():
    stack = [f"{M}.MwNotUsed", f"{M}.MwShortCircuit", f"{M}.MwA"]
    # /sc is short-circuited by MwShortCircuit.aprocess_view; /json is not.
    for target in ("/sc", "/json"):
        chain, oracle = _run_both(stack, target)
        assert chain == oracle


def test_chain_matches_empty_stack():
    chain, oracle = _run_both([], "/json")
    assert chain == oracle


def test_chain_gzip_compression_matches():
    # GZip's BREACH random padding makes compressed bytes non-deterministic, so compare the
    # decompressed plaintext, not raw bytes. Both paths must gzip, set Vary, and round-trip.
    import gzip as gziplib

    headers = (("Accept-Encoding", "gzip"),)
    with override_settings(MIDDLEWARE=REAL_STACK, ROOT_URLCONF=M, DEBUG=False):
        handler = MasslessHandler()

        async def go():
            c = await handler._chain.run(_mkreq("/big", headers=headers))
            o = await handler.get_response_async(_mkreq("/big", headers=headers))
            return c, o

        c, o = asyncio.run(go())
    assert c["Content-Encoding"] == o["Content-Encoding"] == "gzip"
    assert c["Vary"] == o["Vary"] == "Accept-Encoding"
    assert c.status_code == o.status_code == 200
    assert gziplib.decompress(bytes(c.content)) == gziplib.decompress(bytes(o.content)) == b"x" * 500


def test_chain_substitutes_fast_implementations():
    # The registered stock middleware must be replaced by their FastLayer in the chain;
    # an unregistered (synthetic) one must stay as-is. This guards against the registry
    # silently no-op'ing, which would make the differential a meaningless real-vs-real check.
    from massless._middleware import CommonFast, GZipFast, SecurityFast, XFrameFast

    with override_settings(MIDDLEWARE=[*REAL_STACK, f"{M}.MwA"], ROOT_URLCONF=M, DEBUG=False):
        handler = MasslessHandler()
        classes = {type(layer) for layer in handler._chain.layers}
    assert {SecurityFast, CommonFast, XFrameFast, GZipFast} <= classes
    assert any(t.__name__ == "MwA" for t in classes)  # unregistered: not substituted


@pytest.mark.skipif(
    not _django_honors_aprocess_view(),
    reason="needs a Django whose load_middleware honors aprocess_view (the django-asyncio fork)",
)
def test_chain_matches_with_aprocess_view_middleware():
    # On a fork that honors the native-async aprocess_view hook, the chain and
    # get_response_async must both invoke it and short-circuit identically.
    stack = [f"{M}.MwAsyncView", f"{M}.MwA"]
    for target in ("/sc", "/json"):
        chain, oracle = _run_both(stack, target)
        assert chain == oracle


def test_chain_matches_with_template_response_middleware():
    # A deferred-render view + process_template_response middleware exercises the chain's
    # template-response branch; both paths must render and apply the hook identically.
    stack = [f"{M}.MwTemplate", f"{M}.MwA"]
    chain, oracle = _run_both(stack, "/tpl")
    assert chain == oracle
    assert chain[3] == b"rendered-body"
    assert ("x-template", "seen") in chain[1]


# --------------------------------------------------------------------------- ordering


def _order_for(target, headers=()):
    """Run only the chain under the synthetic stack and return the recorded hook order."""
    with override_settings(MIDDLEWARE=SYNTH_STACK, ROOT_URLCONF=M, DEBUG=False):
        handler = MasslessHandler()
        RECORD.clear()
        asyncio.run(handler._chain.run(_mkreq(target, headers=headers)))
        return list(RECORD)


def test_chain_request_phase_outer_to_inner_response_inner_to_outer():
    order = _order_for("/json")
    # request phase A->B->C (outermost first), response phase C->B->A (reverse).
    assert order == ["A:req", "B:req", "C:req", "A:view", "C:resp", "B:resp", "A:resp"]


def test_chain_process_exception_runs_reverse_for_view_error():
    # v_boom raises ValueError; MwB.process_exception handles it. Exception middleware
    # runs in reverse MIDDLEWARE order, and the handled response still unwinds C->B->A.
    order = _order_for("/boom")
    assert "B:exc" in order
    assert order[-3:] == ["C:resp", "B:resp", "A:resp"]
