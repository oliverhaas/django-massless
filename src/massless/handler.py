"""The core drop-in handler: run a request through Django's real middleware chain
and URL resolver, exactly as Django's own ASGI/WSGI handlers do, but fed a lazy
MasslessRequest built from the C buffers instead of an ASGI scope.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from asgiref.sync import iscoroutinefunction, sync_to_async
from django.core.handlers.base import BaseHandler
from django.core.handlers.exception import response_for_exception
from django.urls import ResolverMatch
from django.utils.log import log_response

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from django.http import HttpRequest, HttpResponseBase


class _LazyResolverMatch:
    """A request.resolver_match that defers building the real ResolverMatch (which does
    _func_path string formatting and namespace list-comprehensions) until a view actually
    reads it. Unpacks to (func, args, kwargs) like ResolverMatch and proxies attributes."""

    __slots__ = ("_parts", "_rm")

    def __init__(self, callback: Callable, args: tuple, kwargs: dict, route: str | None) -> None:
        self._parts = (callback, args, kwargs, route)
        self._rm: ResolverMatch | None = None

    def _materialize(self) -> ResolverMatch:
        rm = self._rm
        if rm is None:
            callback, args, kwargs, route = self._parts
            rm = self._rm = ResolverMatch(callback, args, kwargs, route=route)
        return rm

    def __getattr__(self, name: str) -> object:
        return getattr(self._materialize(), name)

    def __iter__(self) -> Iterator:
        return iter(self._materialize())

    def __getitem__(self, index: int) -> object:
        return self._materialize()[index]


class MasslessHandler(BaseHandler):
    """Loads Django's async middleware chain once; `handle` runs a request through
    it (the chain resolves the URL against ROOT_URLCONF and calls the view).

    It also owns the per-worker lifecycle state the connection protocol and the
    server's graceful drain coordinate through: startup/shutdown hooks, the
    in-flight request registry, the drain latch + event, and the sync-view
    thread-pool executor knobs. (These used to live on the retired MasslessAPI;
    the handler is now the single per-worker object the server builds.)
    """

    def __init__(self) -> None:
        super().__init__()
        self.load_middleware(is_async=True)
        # Fast URL resolution: a typed Cython router built from the app's own
        # urlpatterns. It short-circuits Django's regex resolver for the common
        # path() routes and defers to it (via resolve_request below) for anything
        # it cannot match exactly. Built once for the current ROOT_URLCONF; a
        # different active urlconf (override_settings, a per-request urlconf) makes
        # resolve_request fall back. Any build error leaves the router off.
        self._router: Any = None
        self._router_urlconf: object = None
        try:
            from massless._router import build_router  # noqa: PLC0415

            self._router = build_router()
            from django.conf import settings  # noqa: PLC0415

            self._router_urlconf = settings.ROOT_URLCONF
        except Exception:  # noqa: BLE001 - never let routing setup break startup
            self._router = None
        # Pool lifecycle (django-bolt style): skip the per-request request_started/
        # request_finished signal dispatch and return DB connections directly. Requires
        # a connection pool with CONN_MAX_AGE=0 to own connection lifetime. Off by
        # default (full signal compatibility); see _protocol.dispatch teardown.
        from django.conf import settings  # noqa: PLC0415

        self._pool_lifecycle: bool = bool(getattr(settings, "MASSLESS_POOL_LIFECYCLE", False))
        # Fast dispatch (django-bolt style): when there is no user middleware and no
        # ATOMIC_REQUESTS, a router hit calls the view directly (see _fast_dispatch),
        # skipping get_response_async's middleware chain, exception wrapper, and atomic
        # wrapper. Both preconditions are static, so they are decided once here.
        from django.db import connections  # noqa: PLC0415

        self._fast_ok: bool = (
            self._router is not None
            and not settings.MIDDLEWARE
            and not any(s.get("ATOMIC_REQUESTS") for s in connections.settings.values())
        )
        # The massless-owned middleware chain: builds the request/response onion from
        # settings.MIDDLEWARE and runs it in place of Django's get_response_async (see
        # massless._chain). Phase 1 delegates every middleware to its real Django class,
        # so chain.run is byte-identical to get_response_async (proven by tests/test_chain.py);
        # Django's own self._middleware_chain (from load_middleware above) stays as the
        # whole-chain fallback / differential oracle.
        from massless._chain import MasslessChain  # noqa: PLC0415

        self._chain = MasslessChain(self)
        # Lifecycle hooks: zero-arg sync-or-async callables run once per worker.
        self.on_startup_hooks: list[Callable] = []
        self.on_shutdown_hooks: list[Callable] = []
        # Sync-view dispatch carries a ThreadPoolExecutor, built lazily in the
        # protocol. ``_max_workers`` is set by the runner from ``--workers``.
        self.executor: object | None = None
        self._max_workers: int | None = None
        # Graceful-shutdown coordination, shared across all connections of this
        # worker. ``_inflight`` holds one future per request currently being
        # handled; the server's drain awaits it. ``_draining`` tells
        # ``connection_lost`` not to cancel a worker that is mid-response.
        # ``_drain_event`` (created by the server within its loop) wakes idle
        # per-connection worker loops so they stop blocking the drain.
        self._inflight: set[asyncio.Future] = set()
        self._draining: bool = False
        self._drain_event: asyncio.Event | None = None

    def begin_drain(self) -> None:
        """Mark this worker as draining and wake idle connection loops. Idempotent."""
        self._draining = True
        event = self._drain_event
        if event is not None:
            event.set()

    def on_startup(self, func: Callable) -> Callable:
        """Register a zero-arg (sync or async) callable to run before serving."""
        self.on_startup_hooks.append(func)
        return func

    def on_shutdown(self, func: Callable) -> Callable:
        """Register a zero-arg (sync or async) callable to run after the server stops."""
        self.on_shutdown_hooks.append(func)
        return func

    def resolve_request(self, request: HttpRequest) -> ResolverMatch:
        """Resolve the view via the Cython router, falling back to Django's resolver.

        Called by Django's _get_response_async. A router hit returns the same
        (view, args, kwargs) Django would, wrapped in a real ResolverMatch so the rest
        of the request path (middleware, view call, request.resolver_match readers) is
        unchanged. Misses, opaque routes, a per-request ``urlconf`` override, or a
        ROOT_URLCONF the router was not built for all defer to Django.
        """
        router = self._router
        if router is not None and not getattr(request, "urlconf", None):
            from django.conf import settings  # noqa: PLC0415
            from django.urls import get_urlconf  # noqa: PLC0415

            if get_urlconf(settings.ROOT_URLCONF) == self._router_urlconf:
                match = router.match(request.path_info.encode("utf-8"))
                if match is not None:
                    callback, args, kwargs, route = match[0], match[1], match[2], match[3]
                    resolver_match = ResolverMatch(callback, args, kwargs, route=route)
                    request.resolver_match = resolver_match
                    return resolver_match
        return super().resolve_request(request)

    async def _fast_dispatch(self, request: HttpRequest, match: tuple) -> HttpResponseBase:
        """Call the view directly, bypassing get_response_async.

        Faithful to _get_response_async for the no-middleware / no-ATOMIC_REQUESTS case:
        sync views run on the thread-sensitive executor; view exceptions go through
        Django's response_for_exception (Http404 -> 404, PermissionDenied -> 403, ... ,
        else 500 + got_request_exception); deferred-render responses are rendered;
        request.close is registered as a resource closer; 4xx/5xx are logged. The empty
        view/exception/template middleware lists are skipped, and make_view_atomic is a
        no-op here (gated on no ATOMIC_REQUESTS), so neither is invoked.
        """
        callback, args, kwargs, route, is_async = match
        request.resolver_match = _LazyResolverMatch(callback, args, kwargs, route)  # type: ignore[assignment]
        # Django wraps the whole of _get_response_async in convert_exception_to_response,
        # so a view error AND a check_response/render/coroutine error all become a
        # response via response_for_exception. With no exception middleware that
        # collapses to a single try -> response_for_exception around the lot.
        try:
            if is_async:
                response = await callback(request, *args, **kwargs)
            else:
                response = await sync_to_async(callback, thread_sensitive=True)(request, *args, **kwargs)
            self.check_response(response, callback)
            if hasattr(response, "render") and callable(response.render):
                if iscoroutinefunction(response.render):
                    response = await response.render()
                else:
                    response = await sync_to_async(response.render, thread_sensitive=True)()
            if asyncio.iscoroutine(response):
                msg = "Response is still a coroutine."
                raise RuntimeError(msg)  # noqa: TRY301 - mirror Django's coroutine guard
        except Exception as exc:  # noqa: BLE001 - mirror Django: any error becomes a response
            # thread_sensitive=False matches Django's convert_exception_to_response (exception.py).
            response = await sync_to_async(response_for_exception, thread_sensitive=False)(request, exc)
        response._resource_closers.append(request.close)  # noqa: SLF001 - Django's own resource-closer protocol
        if response.status_code >= 400:  # noqa: PLR2004 - 400 is the HTTP client-error boundary
            await sync_to_async(log_response, thread_sensitive=False)(
                "%s: %s",
                response.reason_phrase,
                request.path,
                response=response,
                request=request,
            )
        return response

    async def handle(self, request: HttpRequest) -> HttpResponseBase:
        if self._fast_ok:
            from django.conf import settings  # noqa: PLC0415
            from django.urls import get_urlconf, set_urlconf  # noqa: PLC0415

            # Only fast-route when the active urlconf is the one the router was built
            # for, and the request carries no per-request urlconf override (a guard
            # mirroring resolve_request; unreachable under no middleware, kept as
            # insurance). Then set the thread-local urlconf as get_response_async would
            # (base.py:162) so reverse()/get_urlconf() and error-handler resolution see
            # ROOT_URLCONF even on a worker that has only ever taken the fast path.
            if not getattr(request, "urlconf", None) and get_urlconf(settings.ROOT_URLCONF) == self._router_urlconf:
                set_urlconf(settings.ROOT_URLCONF)
                match = self._router.match(request.path_info.encode("utf-8"))
                if match is not None:
                    return await self._fast_dispatch(request, match)
        return await self._chain.run(request)
