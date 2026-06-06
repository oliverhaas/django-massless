"""Native-async re-implementations of the common Django middleware, and the substitution registry.

Each class is named *exactly* like the Django middleware it replaces (``SecurityMiddleware``,
``SessionMiddleware``, ``CsrfViewMiddleware``, ...) so the registry reads as a one-to-one
replacement map and it is obvious which stock class each one stands in for. Each runs the *same*
hook logic as its stock counterpart but in the event loop instead of through ``sync_to_async``
(which stock ``MiddlewareMixin`` uses for every hook, a thread hop per middleware per request).
Behavior is byte-identical to the real middleware (proven by the differential tests in
tests/test_chain.py, which compare a chain that substitutes these against Django's
``get_response_async`` running the real classes).

Two flavours. The pure header/redirect middleware (Security/Common/XFrame/GZip/ConditionalGet)
re-implement the hook logic with settings cached at init. The stateful built-ins
(Session/CSRF/Auth/Messages) instead *subclass* the real Django middleware so every
security-sensitive hook (CSRF token comparison, session save, the lazy-user attach) is inherited
verbatim; only the thread-hopping ``__acall__`` is replaced with a native-async one. Where a hook
does backend I/O -- the session save, a session-backed message store -- the async mirror awaits
the backend's async API (``asave``/``aupdate``) or, for a backend without one, falls back to
``sync_to_async`` exactly as stock does, so the loop is not blocked. (One known passthrough still
blocks: the ``file`` session backend's ``asave`` is literally ``self.save()``, matching
django-asyncio's trade-off.) Locale (i18n catalog loading) and any third-party middleware are
never substituted: they run as the real Django class through the chain.
"""

from __future__ import annotations

import re
import time
from importlib import import_module
from typing import TYPE_CHECKING

from asgiref.sync import iscoroutinefunction, markcoroutinefunction, sync_to_async
from django.conf import settings
from django.contrib.auth.middleware import AuthenticationMiddleware as _DjangoAuthenticationMiddleware
from django.contrib.messages.middleware import MessageMiddleware as _DjangoMessageMiddleware
from django.contrib.messages.storage.cookie import CookieStorage as _CookieStorage
from django.contrib.sessions.backends.base import UpdateError
from django.contrib.sessions.exceptions import SessionInterrupted
from django.contrib.sessions.middleware import SessionMiddleware as _DjangoSessionMiddleware
from django.core.exceptions import PermissionDenied
from django.http import HttpResponsePermanentRedirect
from django.middleware.csrf import CsrfViewMiddleware as _DjangoCsrfViewMiddleware
from django.urls import is_valid_path
from django.utils.cache import (
    cc_delim_re,
    get_conditional_response,
    patch_vary_headers,
    set_response_etag,
)
from django.utils.http import escape_leading_slashes, http_date, parse_http_date_safe
from django.utils.text import acompress_sequence, compress_sequence, compress_string

if TYPE_CHECKING:
    from collections.abc import Callable

    from django.http import HttpRequest, HttpResponseBase

_re_accepts_gzip = re.compile(r"\bgzip\b")
_SHORT_BODY = 200  # GZip skips bodies shorter than this (Django's threshold)
_NOT_FOUND = 404
_SERVER_ERROR = 500  # SessionMiddleware skips the session save for 5xx responses


class _FastMiddleware:
    """Base for native-async fast middleware.

    ``__call__`` mirrors ``MiddlewareMixin.__acall__`` (process_request -> get_response ->
    process_response) but invokes the sync ``process_*`` hooks directly in the loop, with no
    ``sync_to_async`` thread hop. Subclasses cache settings in ``__init__`` and define the
    ``process_request``/``process_response`` they need.
    """

    async_capable = True
    sync_capable = False

    def __init__(self, get_response: Callable) -> None:
        self.get_response = get_response
        if iscoroutinefunction(get_response):
            markcoroutinefunction(self)

    async def __call__(self, request: HttpRequest) -> HttpResponseBase:
        response = None
        process_request = getattr(self, "process_request", None)
        if process_request is not None:
            response = process_request(request)
        if response is None:
            response = await self.get_response(request)
        process_response = getattr(self, "process_response", None)
        if process_response is not None:
            response = process_response(request, response)
        return response


class XFrameOptionsMiddleware(_FastMiddleware):
    """Native-async drop-in for django.middleware.clickjacking.XFrameOptionsMiddleware."""

    def __init__(self, get_response: Callable) -> None:
        super().__init__(get_response)
        self.x_frame_options = getattr(settings, "X_FRAME_OPTIONS", "DENY").upper()

    def process_response(self, request: HttpRequest, response: HttpResponseBase) -> HttpResponseBase:  # noqa: ARG002 - Django middleware signature
        if response.get("X-Frame-Options") is not None:
            return response
        if getattr(response, "xframe_options_exempt", False):
            return response
        response.headers["X-Frame-Options"] = self.x_frame_options
        return response


class SecurityMiddleware(_FastMiddleware):
    """Native-async drop-in for django.middleware.security.SecurityMiddleware."""

    def __init__(self, get_response: Callable) -> None:
        super().__init__(get_response)
        self.sts_seconds = settings.SECURE_HSTS_SECONDS
        self.sts_include_subdomains = settings.SECURE_HSTS_INCLUDE_SUBDOMAINS
        self.sts_preload = settings.SECURE_HSTS_PRELOAD
        self.content_type_nosniff = settings.SECURE_CONTENT_TYPE_NOSNIFF
        self.redirect = settings.SECURE_SSL_REDIRECT
        self.redirect_host = settings.SECURE_SSL_HOST
        self.redirect_exempt = [re.compile(r) for r in settings.SECURE_REDIRECT_EXEMPT]
        self.referrer_policy = settings.SECURE_REFERRER_POLICY
        self.cross_origin_opener_policy = settings.SECURE_CROSS_ORIGIN_OPENER_POLICY

    def process_request(self, request: HttpRequest) -> HttpResponseBase | None:
        path = request.path.lstrip("/")
        if (
            self.redirect
            and not request.is_secure()
            and not any(pattern.search(path) for pattern in self.redirect_exempt)
        ):
            host = self.redirect_host or request.get_host()
            return HttpResponsePermanentRedirect(f"https://{host}{request.get_full_path()}")
        return None

    def process_response(self, request: HttpRequest, response: HttpResponseBase) -> HttpResponseBase:
        if self.sts_seconds and request.is_secure() and "Strict-Transport-Security" not in response:
            sts_header = f"max-age={self.sts_seconds}"
            if self.sts_include_subdomains:
                sts_header += "; includeSubDomains"
            if self.sts_preload:
                sts_header += "; preload"
            response.headers["Strict-Transport-Security"] = sts_header
        if self.content_type_nosniff:
            response.headers.setdefault("X-Content-Type-Options", "nosniff")
        if self.referrer_policy:
            response.headers.setdefault(
                "Referrer-Policy",
                ",".join(
                    [v.strip() for v in self.referrer_policy.split(",")]
                    if isinstance(self.referrer_policy, str)
                    else self.referrer_policy,
                ),
            )
        if self.cross_origin_opener_policy:
            response.setdefault("Cross-Origin-Opener-Policy", self.cross_origin_opener_policy)
        return response


class ConditionalGetMiddleware(_FastMiddleware):
    """Native-async drop-in for django.middleware.http.ConditionalGetMiddleware (reuses Django's cache helpers)."""

    def process_response(self, request: HttpRequest, response: HttpResponseBase) -> HttpResponseBase:
        if request.method != "GET":
            return response
        if self._needs_etag(response) and not response.has_header("ETag"):
            set_response_etag(response)
        etag = response.get("ETag")
        last_modified_header = response.get("Last-Modified")
        last_modified = parse_http_date_safe(last_modified_header) if last_modified_header else None
        if etag or last_modified:
            return get_conditional_response(
                request,
                etag=etag,
                last_modified=last_modified,
                response=response,
            )
        return response

    def _needs_etag(self, response: HttpResponseBase) -> bool:
        cache_control_headers = cc_delim_re.split(response.get("Cache-Control", ""))
        return all(header.lower() != "no-store" for header in cache_control_headers)


class CommonMiddleware(_FastMiddleware):
    """Native-async drop-in for django.middleware.common.CommonMiddleware.

    The hot path (DISALLOWED_USER_AGENTS, PREPEND_WWW, Content-Length) is re-implemented; the
    APPEND_SLASH branch delegates to Django's ``is_valid_path`` verbatim (URL resolution).
    """

    response_redirect_class = HttpResponsePermanentRedirect

    def __init__(self, get_response: Callable) -> None:
        super().__init__(get_response)
        self.disallowed_user_agents = settings.DISALLOWED_USER_AGENTS
        self.prepend_www = settings.PREPEND_WWW
        self.append_slash = settings.APPEND_SLASH

    def process_request(self, request: HttpRequest) -> HttpResponseBase | None:
        user_agent = request.META.get("HTTP_USER_AGENT")
        if user_agent is not None:
            for user_agent_regex in self.disallowed_user_agents:
                if user_agent_regex.search(user_agent):
                    raise PermissionDenied("Forbidden user agent")
        host = request.get_host()
        if self.prepend_www and host and not host.startswith("www."):
            if self._should_redirect_with_slash(request):
                path = self._get_full_path_with_slash(request)
            else:
                path = request.get_full_path()
            return self.response_redirect_class(f"{request.scheme}://www.{host}{path}")
        return None

    def process_response(self, request: HttpRequest, response: HttpResponseBase) -> HttpResponseBase:
        if response.status_code == _NOT_FOUND and self._should_redirect_with_slash(request):
            response = self.response_redirect_class(self._get_full_path_with_slash(request))
        if not response.streaming and not response.has_header("Content-Length"):
            response.headers["Content-Length"] = str(len(response.content))
        return response

    def _should_redirect_with_slash(self, request: HttpRequest) -> bool:
        if self.append_slash and not request.path_info.endswith("/"):
            urlconf = getattr(request, "urlconf", None)
            if not is_valid_path(request.path_info, urlconf):
                match = is_valid_path(f"{request.path_info}/", urlconf)
                if match:
                    view = match.func
                    return getattr(view, "should_append_slash", True)
        return False

    def _get_full_path_with_slash(self, request: HttpRequest) -> str:
        new_path = request.get_full_path(force_append_slash=True)
        new_path = escape_leading_slashes(new_path)
        if settings.DEBUG and request.method in ("DELETE", "POST", "PUT", "PATCH"):
            raise RuntimeError(
                f"You called this URL via {request.method}, but the URL doesn't end "
                "in a slash and you have APPEND_SLASH set. Django can't "
                f"redirect to the slash URL while maintaining {request.method} data. "
                f"Change your form to point to {request.get_host() + new_path} (note the trailing "
                "slash), or set APPEND_SLASH=False in your Django settings.",
            )
        return new_path


class GZipMiddleware(_FastMiddleware):
    """Native-async drop-in for django.middleware.gzip.GZipMiddleware.

    Verbatim process_response (including the BREACH-mitigation random padding via
    ``max_random_bytes``), so the compressed output is non-deterministic exactly as the real
    middleware's is; the differential decompresses before comparing.
    """

    max_random_bytes = 100

    def process_response(self, request: HttpRequest, response: HttpResponseBase) -> HttpResponseBase:
        if not response.streaming and len(response.content) < _SHORT_BODY:
            return response
        if response.has_header("Content-Encoding"):
            return response
        patch_vary_headers(response, ("Accept-Encoding",))
        ae = request.META.get("HTTP_ACCEPT_ENCODING", "")
        if not _re_accepts_gzip.search(ae):
            return response
        if response.streaming:
            if response.is_async:
                response.streaming_content = acompress_sequence(
                    response.streaming_content,
                    max_random_bytes=self.max_random_bytes,
                )
            else:
                response.streaming_content = compress_sequence(
                    response.streaming_content,
                    max_random_bytes=self.max_random_bytes,
                )
            del response.headers["Content-Length"]
        else:
            compressed_content = compress_string(response.content, max_random_bytes=self.max_random_bytes)
            if len(compressed_content) >= len(response.content):
                return response
            response.content = compressed_content
            response.headers["Content-Length"] = str(len(response.content))
        etag = response.get("ETag")
        if etag and etag.startswith('"'):
            response.headers["ETag"] = "W/" + etag
        response.headers["Content-Encoding"] = "gzip"
        return response


# ---------------------------------------------------------------- stateful built-ins
# These subclass the real Django middleware (inheriting every security-sensitive hook verbatim)
# and only replace the thread-hopping __acall__ with a native-async one.


class SessionMiddleware(_DjangoSessionMiddleware):
    """Native-async drop-in for django.contrib.sessions.middleware.SessionMiddleware.

    ``process_request`` only attaches a lazy ``SessionStore`` (no I/O) and runs inline.
    ``process_response`` is the one hook that does backend I/O -- the session save when the
    session was modified -- so it runs as an async mirror (``_aprocess_response``) that awaits the
    backend's async API (``asave``/``aget_expiry_age``/``aget_expire_at_browser_close``) instead of
    paying ``MiddlewareMixin``'s thread hop. ``SessionBase`` defines those async methods for every
    backend; ``db``/``cached_db``/``cache``/``signed_cookies`` are genuinely non-blocking, while
    the ``file`` backend's ``asave`` is a sync passthrough (``return self.save()``) that still
    blocks the loop on save -- a rare-in-async-deployments trade-off, matching django-asyncio.
    Mirrors django-asyncio's native-async SessionMiddleware.
    """

    async_capable = True
    sync_capable = False

    def __init__(self, get_response: Callable) -> None:
        self.get_response = get_response
        if iscoroutinefunction(get_response):
            markcoroutinefunction(self)
        engine = import_module(settings.SESSION_ENGINE)
        self.SessionStore = engine.SessionStore

    async def __call__(self, request: HttpRequest) -> HttpResponseBase:
        self.process_request(request)  # inherited; attaches a lazy store, no I/O
        # django-stubs types the inherited get_response as a sync/async union; the chain only ever
        # builds us with an async get_response, so the await is valid (hence the ignore[misc]).
        response = await self.get_response(request)  # type: ignore[misc]
        return await self._aprocess_response(request, response)

    async def _aprocess_response(self, request: HttpRequest, response: HttpResponseBase) -> HttpResponseBase:
        # Async mirror of the inherited process_response: identical branches, but the expiry reads
        # and the session save go through the backend's async API so the loop is never blocked.
        try:
            accessed = request.session.accessed
            modified = request.session.modified
            empty = request.session.is_empty()
        except AttributeError:
            return response
        if settings.SESSION_COOKIE_NAME in request.COOKIES and empty:
            response.delete_cookie(
                settings.SESSION_COOKIE_NAME,
                path=settings.SESSION_COOKIE_PATH,
                domain=settings.SESSION_COOKIE_DOMAIN,
                samesite=settings.SESSION_COOKIE_SAMESITE,
            )
            need_vary_cookie = True
        else:
            need_vary_cookie = accessed
            if (modified or settings.SESSION_SAVE_EVERY_REQUEST) and not empty:
                if await request.session.aget_expire_at_browser_close():
                    max_age = None
                    expires = None
                else:
                    max_age = await request.session.aget_expiry_age()
                    expires = http_date(time.time() + max_age)
                if response.status_code < _SERVER_ERROR:
                    try:
                        await request.session.asave()
                    except UpdateError:
                        raise SessionInterrupted(
                            "The request's session was deleted before the request completed. "
                            "The user may have logged out in a concurrent request, for example.",
                        ) from None
                    response.set_cookie(
                        settings.SESSION_COOKIE_NAME,
                        request.session.session_key,
                        max_age=max_age,
                        expires=expires,
                        domain=settings.SESSION_COOKIE_DOMAIN,
                        path=settings.SESSION_COOKIE_PATH,
                        secure=settings.SESSION_COOKIE_SECURE or None,
                        httponly=settings.SESSION_COOKIE_HTTPONLY or None,
                        samesite=settings.SESSION_COOKIE_SAMESITE,
                    )
                    need_vary_cookie = True
        if need_vary_cookie:
            patch_vary_headers(response, ("Cookie",))
        return response


class AuthenticationMiddleware(_FastMiddleware, _DjangoAuthenticationMiddleware):
    """Native-async drop-in for django.contrib.auth.middleware.AuthenticationMiddleware.

    ``process_request`` only attaches a lazy ``request.user``/``request.auser`` (no I/O), so the
    generic ``_FastMiddleware.__call__`` runs the inherited hook inline; there is no
    ``process_response``. The lazy user resolves (and hits the DB) only when a view touches it,
    exactly as in stock.
    """


class MessageMiddleware(_DjangoMessageMiddleware):
    """Native-async drop-in for django.contrib.messages.middleware.MessageMiddleware.

    ``process_request`` attaches lazy storage (no I/O) and runs inline. ``process_response`` saves
    the messages via ``storage.update()``: for ``CookieStorage`` that is pure CPU (a signed cookie)
    and runs inline -- the thread hop is gone. But ``SessionStorage``/``FallbackStorage`` (the
    default) and custom backends can touch ``request.session`` or do backend I/O inside
    ``update()``, so for those it runs the inherited ``update()`` through ``sync_to_async`` exactly
    as stock ``MiddlewareMixin`` does -- off the event loop -- keeping the output byte-identical
    without blocking the loop. (A storage that grows a native ``aupdate()`` is awaited directly.)
    """

    async_capable = True
    sync_capable = False

    def __init__(self, get_response: Callable) -> None:
        self.get_response = get_response
        if iscoroutinefunction(get_response):
            markcoroutinefunction(self)

    async def __call__(self, request: HttpRequest) -> HttpResponseBase:
        self.process_request(request)  # inherited; attaches lazy storage, no I/O
        # django-stubs types the inherited get_response as a sync/async union (see SessionMiddleware).
        response = await self.get_response(request)  # type: ignore[misc]
        return await self._aprocess_response(request, response)

    async def _aprocess_response(self, request: HttpRequest, response: HttpResponseBase) -> HttpResponseBase:
        # Mirror of the inherited process_response, but the storage save never blocks the loop:
        # CookieStorage.update() is pure CPU so it runs inline; any other storage may touch the
        # session or do I/O, so it runs through sync_to_async exactly as stock does. Byte-identical.
        storage = getattr(request, "_messages", None)
        if storage is None:
            return response
        aupdate = getattr(storage, "aupdate", None)
        if aupdate is not None:
            unstored_messages = await aupdate(response)
        elif type(storage) is _CookieStorage:
            unstored_messages = storage.update(response)
        else:
            unstored_messages = await sync_to_async(storage.update, thread_sensitive=True)(response)
        if unstored_messages and settings.DEBUG:
            msg = "Not all temporary messages could be stored."
            raise ValueError(msg)
        return response


class CsrfViewMiddleware(_FastMiddleware, _DjangoCsrfViewMiddleware):
    """Native-async drop-in for django.middleware.csrf.CsrfViewMiddleware.

    Token setup (``process_request``) and the outgoing-cookie write (``process_response``) are
    pure-CPU crypto, run inline by the generic ``__call__``. Enforcement (``process_view``) is
    exposed as a native ``aprocess_view`` so the chain invokes it directly instead of through
    ``adapt_method_mode``'s ``sync_to_async`` wrap. Every CSRF accept/reject decision is the
    inherited stock code, byte-for-byte.
    """

    async def aprocess_view(
        self,
        request: HttpRequest,
        callback: Callable,
        callback_args: tuple,
        callback_kwargs: dict,
    ) -> HttpResponseBase | None:
        return self.process_view(request, callback, callback_args, callback_kwargs)


# Django dotted path -> fast re-implementation. The chain substitutes these in its build loop;
# every other middleware (including all third-party) runs as the real Django class.
REGISTRY = {
    "django.middleware.clickjacking.XFrameOptionsMiddleware": XFrameOptionsMiddleware,
    "django.middleware.security.SecurityMiddleware": SecurityMiddleware,
    "django.middleware.http.ConditionalGetMiddleware": ConditionalGetMiddleware,
    "django.middleware.common.CommonMiddleware": CommonMiddleware,
    "django.middleware.gzip.GZipMiddleware": GZipMiddleware,
    "django.contrib.sessions.middleware.SessionMiddleware": SessionMiddleware,
    "django.contrib.auth.middleware.AuthenticationMiddleware": AuthenticationMiddleware,
    "django.contrib.messages.middleware.MessageMiddleware": MessageMiddleware,
    "django.middleware.csrf.CsrfViewMiddleware": CsrfViewMiddleware,
}
