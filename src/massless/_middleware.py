"""Fast re-implementations of the common Django middleware, and the substitution registry.

Each ``*Fast`` class is a native-async drop-in for a stock Django middleware: it caches the
same settings at init and runs the *same* ``process_request``/``process_response`` logic, but
in the event loop instead of through ``sync_to_async`` (which stock ``MiddlewareMixin`` uses
for every hook, a thread hop per middleware per request). Behavior is byte-identical to the
real middleware (proven by the differential tests in tests/test_chain.py, which compare a
chain that substitutes these against Django's ``get_response_async`` running the real classes).

Only pure header/redirect middleware that read scalar settings are re-implemented. Session,
auth, CSRF, messages, locale (pluggable backends / security crypto / i18n catalogs) are never
substituted: they always run as the real Django class via the chain's BridgeLayer path.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from asgiref.sync import iscoroutinefunction, markcoroutinefunction
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.http import HttpResponsePermanentRedirect
from django.urls import is_valid_path
from django.utils.cache import (
    cc_delim_re,
    get_conditional_response,
    patch_vary_headers,
    set_response_etag,
)
from django.utils.http import escape_leading_slashes, parse_http_date_safe
from django.utils.text import acompress_sequence, compress_sequence, compress_string

if TYPE_CHECKING:
    from collections.abc import Callable

    from django.http import HttpRequest, HttpResponseBase

_re_accepts_gzip = re.compile(r"\bgzip\b")
_SHORT_BODY = 200  # GZip skips bodies shorter than this (Django's threshold)
_NOT_FOUND = 404


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


class XFrameFast(_FastMiddleware):
    """django.middleware.clickjacking.XFrameOptionsMiddleware."""

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


class SecurityFast(_FastMiddleware):
    """django.middleware.security.SecurityMiddleware."""

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


class ConditionalGetFast(_FastMiddleware):
    """django.middleware.http.ConditionalGetMiddleware (reuses Django's cache helpers)."""

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


class CommonFast(_FastMiddleware):
    """django.middleware.common.CommonMiddleware.

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


class GZipFast(_FastMiddleware):
    """django.middleware.gzip.GZipMiddleware.

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


# Django dotted path -> fast re-implementation. The chain substitutes these in its build loop;
# every other middleware (including all third-party) runs as the real Django class.
REGISTRY = {
    "django.middleware.clickjacking.XFrameOptionsMiddleware": XFrameFast,
    "django.middleware.security.SecurityMiddleware": SecurityFast,
    "django.middleware.http.ConditionalGetMiddleware": ConditionalGetFast,
    "django.middleware.common.CommonMiddleware": CommonFast,
    "django.middleware.gzip.GZipMiddleware": GZipFast,
}
