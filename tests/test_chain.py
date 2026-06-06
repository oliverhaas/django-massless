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
import threading

import pytest
from asgiref.sync import iscoroutinefunction, markcoroutinefunction
from django.contrib.messages.storage.base import BaseStorage
from django.contrib.sessions.middleware import SessionMiddleware as _StockSessionMiddleware
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


def v_session_write(request):
    request.session["k"] = "v"  # modifies the session -> Set-Cookie on response
    return HttpResponse(b"sw")


def v_session_read(request):
    request.session.get("k")  # accesses but does not modify -> Vary: Cookie, no Set-Cookie
    return HttpResponse(b"sr")


def v_user(request):
    # Exercises AuthenticationMiddleware's lazy user (AnonymousUser, no DB hit).
    return HttpResponse(b"auth" if request.user.is_authenticated else b"anon")


def v_message(request):
    from django.contrib import messages

    messages.add_message(request, messages.INFO, "hi")  # cookie storage -> Set-Cookie
    return HttpResponse(b"msg")


def v_session_write_500(request):
    request.session["k"] = "v"  # modified, but a 5xx response must skip the save
    return HttpResponse(b"err", status=500)


def v_session_flush(request):
    request.session["k"] = "v"
    request.session.flush()  # empties the session + clears the key -> delete-cookie branch
    return HttpResponse(b"sf")


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
SESSION = "django.contrib.sessions.middleware.SessionMiddleware"
CSRF = "django.middleware.csrf.CsrfViewMiddleware"
AUTH = "django.contrib.auth.middleware.AuthenticationMiddleware"
MESSAGES = "django.contrib.messages.middleware.MessageMiddleware"

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
    path("sw", v_session_write),
    path("sr", v_session_read),
    path("user", v_user),
    path("msg", v_message),
    path("sw500", v_session_write_500),
    path("sf", v_session_flush),
]

REAL_STACK = [SECURITY, COMMON, XFRAME, CONDITIONAL, GZIP]
SYNTH_STACK = [f"{M}.MwA", f"{M}.MwB", f"{M}.MwC"]
# A realistic production stack whose stateful members (Session/CSRF/Auth/Messages) are the
# ones the chain now substitutes with native-async re-impls. signed_cookies + cookie messages
# keep it DB-free so the differential needs no database.
STATEFUL_STACK = [SECURITY, SESSION, COMMON, CSRF, AUTH, MESSAGES, XFRAME]
_NO_DB_SESSION = {
    "SESSION_ENGINE": "django.contrib.sessions.backends.signed_cookies",
    "SESSION_EXPIRE_AT_BROWSER_CLOSE": True,  # no time-dependent expires -> deterministic Set-Cookie
    "MESSAGE_STORAGE": "django.contrib.messages.storage.cookie.CookieStorage",
}


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


def _run_both(stack, target, method="GET", headers=(), *, freeze_time=False, **extra):
    """Build a handler under `stack`, run the request through the chain and through
    Django's get_response_async on fresh equivalent requests, return both snapshots.

    `extra` is merged into override_settings (e.g. SESSION_ENGINE). `freeze_time` pins
    time.time() for both runs so TimestampSigner-stamped cookies (signed_cookies sessions)
    come out byte-identical instead of racing the clock between the two calls."""
    import contextlib
    from unittest import mock

    with override_settings(MIDDLEWARE=stack, ROOT_URLCONF=M, DEBUG=False, **extra):
        handler = MasslessHandler()

        async def go():
            chain = await handler._chain.run(_mkreq(target, method, headers))
            oracle = await handler.get_response_async(_mkreq(target, method, headers))
            return _snap(chain), _snap(oracle)

        clock = mock.patch("time.time", return_value=1_700_000_000.0) if freeze_time else contextlib.nullcontext()
        with clock:
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
    # The registered stock middleware must be replaced by our same-named native-async class in
    # the chain; an unregistered (synthetic) one must stay as-is. This guards against the registry
    # silently no-op'ing, which would make the differential a meaningless real-vs-real check.
    from massless import _middleware as mw

    with override_settings(MIDDLEWARE=[*REAL_STACK, f"{M}.MwA"], ROOT_URLCONF=M, DEBUG=False):
        handler = MasslessHandler()
        classes = {type(layer) for layer in handler._chain.layers}
    assert {mw.SecurityMiddleware, mw.CommonMiddleware, mw.XFrameOptionsMiddleware, mw.GZipMiddleware} <= classes
    # The substitutes are massless classes, not Django's, despite the matching names.
    assert all(t.__module__ == "massless._middleware" for t in (mw.SecurityMiddleware, mw.GZipMiddleware))
    assert any(t.__name__ == "MwA" for t in classes)  # unregistered: not substituted


def test_chain_substitutes_stateful_fast_implementations():
    # The stateful built-ins (Session/CSRF/Auth/Messages) are substituted too, by our same-named
    # native-async subclasses -- not left as the stock MiddlewareMixin classes that thread-hop.
    from massless import _middleware as mw

    with override_settings(MIDDLEWARE=STATEFUL_STACK, ROOT_URLCONF=M, DEBUG=False, **_NO_DB_SESSION):
        handler = MasslessHandler()
        classes = {type(layer) for layer in handler._chain.layers}
    assert {
        mw.SessionMiddleware,
        mw.CsrfViewMiddleware,
        mw.AuthenticationMiddleware,
        mw.MessageMiddleware,
    } <= classes
    assert all(t.__module__ == "massless._middleware" for t in classes if t.__name__.endswith("Middleware"))


# ----------------------------------------------------------------- stateful middleware differential

_STATEFUL_REQUESTS = [
    ("/json", "GET", ()),  # CSRF safe-method accept; session/auth/messages attach but no cookie
    ("/user", "GET", ()),  # AuthenticationMiddleware lazy AnonymousUser (no DB)
    ("/sr", "GET", ()),  # session accessed, not modified -> Vary: Cookie, no Set-Cookie
    ("/msg", "GET", ()),  # message added -> messages cookie (Signer, no timestamp -> deterministic)
    ("/json", "POST", ()),  # CSRF enforcement: no cookie/token -> 403 reject
]


@pytest.mark.parametrize(("target", "method", "headers"), _STATEFUL_REQUESTS)
def test_chain_matches_stateful_stack(target, method, headers):
    chain, oracle = _run_both(STATEFUL_STACK, target, method, headers, **_NO_DB_SESSION)
    assert chain == oracle


def test_chain_matches_session_write():
    # A session-modifying view must produce a byte-identical Set-Cookie from both paths. The
    # signed_cookies key is TimestampSigner-stamped, so freeze the clock for a stable comparison.
    chain, oracle = _run_both(STATEFUL_STACK, "/sw", freeze_time=True, **_NO_DB_SESSION)
    assert chain == oracle
    assert any(c.startswith("sessionid=") for c in chain[2])  # the session cookie was actually set


def test_chain_stateful_outcomes_are_meaningful():
    # Guard the differential isn't passing on a shared error: the POST is a real CSRF 403, the GET
    # a real 200, and the lazy user is anonymous -- so identical snapshots mean identical success.
    post, _ = _run_both(STATEFUL_STACK, "/json", "POST", **_NO_DB_SESSION)
    assert post[0] == 403
    get_, _ = _run_both(STATEFUL_STACK, "/json", "GET", **_NO_DB_SESSION)
    assert get_[0] == 200
    user, _ = _run_both(STATEFUL_STACK, "/user", **_NO_DB_SESSION)
    assert user[3] == b"anon"


def _signed_session_cookie(data: dict) -> str:
    """Mint a signed_cookies sessionid value for `data` at the frozen test clock, so a re-save
    under freeze_time reproduces it byte-for-byte."""
    from unittest import mock

    from django.contrib.sessions.backends.signed_cookies import SessionStore

    with (
        override_settings(SESSION_ENGINE="django.contrib.sessions.backends.signed_cookies"),
        mock.patch("time.time", return_value=1_700_000_000.0),
    ):
        store = SessionStore()
        store.update(data)
        return store._get_session_key()


def test_chain_matches_session_delete_cookie():
    # An incoming session cookie + a session emptied by the view (flush) drives the delete-cookie
    # branch of _aprocess_response (mirrors stock SessionMiddleware: delete_cookie + Vary: Cookie).
    headers = (("Cookie", "sessionid=whatever"),)
    chain, oracle = _run_both(STATEFUL_STACK, "/sf", headers=headers, freeze_time=True, **_NO_DB_SESSION)
    assert chain == oracle
    assert any(c.startswith("sessionid=") for c in chain[2])  # a delete (expired) cookie was emitted


def test_chain_matches_session_save_every_request():
    # SESSION_SAVE_EVERY_REQUEST forces a save of a non-empty, accessed-but-unmodified session.
    cookie = _signed_session_cookie({"x": "y"})
    headers = (("Cookie", f"sessionid={cookie}"),)
    chain, oracle = _run_both(
        STATEFUL_STACK,
        "/sr",
        headers=headers,
        freeze_time=True,
        SESSION_SAVE_EVERY_REQUEST=True,
        **_NO_DB_SESSION,
    )
    assert chain == oracle
    assert any(c.startswith("sessionid=") for c in chain[2])  # saved despite no modification


def test_chain_matches_session_modified_5xx_skips_save():
    # A modified session on a 5xx response must NOT save / set the session cookie (status_code<500
    # guard), but must still patch Vary: Cookie. Both paths agree.
    chain, oracle = _run_both(STATEFUL_STACK, "/sw500", freeze_time=True, **_NO_DB_SESSION)
    assert chain == oracle
    assert chain[0] == 500
    assert not any(c.startswith("sessionid=") for c in chain[2])  # no session cookie on a 5xx


class MySessionSubclass(_StockSessionMiddleware):
    """A user subclass of a substituted middleware: must run as itself, never be swapped out."""


def test_chain_substitutes_only_exact_dotted_paths():
    # Substitution is keyed on the EXACT stock dotted path. A user subclass of a substituted
    # middleware, and a builtin deliberately left out of the registry (Locale), must NOT be swapped.
    from massless import _middleware as mw

    locale = "django.middleware.locale.LocaleMiddleware"
    stack = [SECURITY, SESSION, f"{M}.MySessionSubclass", locale]
    with override_settings(MIDDLEWARE=stack, ROOT_URLCONF=M, DEBUG=False, **_NO_DB_SESSION):
        handler = MasslessHandler()
        layer_types = {type(layer) for layer in handler._chain.layers}
    assert mw.SessionMiddleware in layer_types  # exact path -> substituted
    assert MySessionSubclass in layer_types  # user subclass -> NOT substituted (runs as itself)
    from django.middleware.locale import LocaleMiddleware

    assert LocaleMiddleware in layer_types  # not in the registry -> NOT substituted


def test_chain_matches_csrf_valid_token_accept():
    # The positive CSRF path: a request with a matching cookie secret + masked header token must be
    # ACCEPTED (200), exercising aprocess_view -> the inherited _check_token, byte-identical to stock.
    from django.middleware.csrf import _get_new_csrf_string, _mask_cipher_secret

    secret = _get_new_csrf_string()
    headers = (("Cookie", f"csrftoken={secret}"), ("X-CSRFToken", _mask_cipher_secret(secret)))
    chain, oracle = _run_both(STATEFUL_STACK, "/json", "POST", headers, **_NO_DB_SESSION)
    assert chain == oracle
    assert chain[0] == 200  # valid token accepted (contrast the no-token 403 in _STATEFUL_REQUESTS)


# A non-cookie message storage that records the thread its store ran on -- used to prove the chain
# runs a storage that isn't pure-CPU CookieStorage OFF the event loop (via sync_to_async), not inline.
_MSG_THREADS: dict[str, threading.Thread] = {}


class _ThreadSpyMessageStorage(BaseStorage):
    def _get(self, *args, **kwargs):
        return [], True

    def _store(self, messages, response, *args, **kwargs):
        _MSG_THREADS["store"] = threading.current_thread()
        return []


@pytest.mark.skipif(
    hasattr(BaseStorage, "aupdate"),
    reason="storage has a native aupdate (django-asyncio fork) -> the chain awaits it directly "
    "(async, non-blocking on-loop); the sync_to_async off-loop fallback under test is stock-only",
)
def test_messages_non_cookie_storage_runs_off_the_loop():
    # Regression: on stock Django a session/fallback/custom message storage can touch the session
    # or do I/O in update(); running it inline would block the event loop. The fix routes it
    # through sync_to_async (off-loop) exactly as stock does. Prove the store ran on a non-loop thread.
    _MSG_THREADS.clear()
    with override_settings(
        MIDDLEWARE=[MESSAGES],
        ROOT_URLCONF=M,
        DEBUG=False,
        MESSAGE_STORAGE=f"{M}._ThreadSpyMessageStorage",
    ):
        handler = MasslessHandler()

        async def go():
            _MSG_THREADS["loop"] = threading.current_thread()
            return await handler._chain.run(_mkreq("/msg"))

        asyncio.run(go())
    assert "store" in _MSG_THREADS  # the storage actually ran
    assert _MSG_THREADS["store"] is not _MSG_THREADS["loop"]  # off the loop -> not blocking it


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
