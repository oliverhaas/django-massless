"""The massless-owned middleware chain.

`MasslessChain` builds the request/response onion from ``settings.MIDDLEWARE`` and runs
it, replacing Django's ``BaseHandler.get_response_async`` / ``_get_response_async`` for the
massless dispatch path. Owning the loop is what lets later phases substitute a fast
re-implementation for a known middleware (the registry) instead of running the Python class.

Phase 1 is pure delegation: every ``settings.MIDDLEWARE`` entry becomes the real Django
middleware instance, wrapped exactly as ``load_middleware`` wraps it (``convert_exception_to_response``
+ ``adapt_method_mode``), so ``run()`` is observationally identical to ``get_response_async``.
The build loop, the three hook lists, and ``_run_view`` mirror ``django/core/handlers/base.py``
line for line; the only seams are that resolution goes through the handler's (router-backed)
``resolve_request`` and the helpers (``adapt_method_mode``/``make_view_atomic``/``check_response``)
are reused from the handler rather than reimplemented.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from asgiref.sync import iscoroutinefunction, sync_to_async
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, MiddlewareNotUsed
from django.core.handlers.exception import convert_exception_to_response
from django.urls import set_urlconf
from django.utils.log import log_response
from django.utils.module_loading import import_string

from massless._middleware import REGISTRY as _REGISTRY

if TYPE_CHECKING:
    from django.http import HttpRequest, HttpResponseBase

    from massless.handler import MasslessHandler

logger = logging.getLogger("django.request")


class MasslessChain:
    """An async middleware chain built from ``settings.MIDDLEWARE``, owned by massless.

    Construct once per handler (it reads ``settings.MIDDLEWARE`` and instantiates each
    middleware). ``run(request)`` executes the chain and returns the response, faithful to
    ``BaseHandler.get_response_async``.
    """

    def __init__(self, handler: MasslessHandler) -> None:
        self.handler = handler
        # Fast re-implementation substitution is on by default; MASSLESS_FAST_MIDDLEWARE=0
        # makes the chain run every middleware as its real Django class (escape hatch /
        # A-B benchmark knob), still through the owned chain.
        self._fast_mw = bool(getattr(settings, "MASSLESS_FAST_MIDDLEWARE", True))
        self._view_middleware: list = []
        self._template_response_middleware: list = []
        self._exception_middleware: list = []
        self._middleware_chain: Any = None
        # The middleware instances in build order (innermost-first), for introspection/tests.
        # A registry-substituted entry is the FastLayer instance, not the real Django class.
        self.layers: list = []
        self._build()

    # ------------------------------------------------------------------ build

    def _build(self) -> None:  # noqa: C901 - mirrors Django's load_middleware structure
        """Mirror of ``BaseHandler.load_middleware(is_async=True)``.

        The innermost handler is ``_run_view`` (this chain's equivalent of
        ``_get_response_async``); each middleware wraps the next, outermost last.
        """
        handler = self.handler
        self._view_middleware = []
        self._template_response_middleware = []
        self._exception_middleware = []

        composed = convert_exception_to_response(self._run_view)
        handler_is_async = True
        self.layers = []
        for middleware_path in reversed(settings.MIDDLEWARE):
            # Substitute a fast re-implementation for an exact stock-path match; any other
            # (custom subclass, third-party) runs as the real Django class via import_string.
            fast = _REGISTRY.get(middleware_path) if self._fast_mw else None
            middleware = fast if fast is not None else import_string(middleware_path)
            middleware_can_sync = getattr(middleware, "sync_capable", True)
            middleware_can_async = getattr(middleware, "async_capable", False)
            if not middleware_can_sync and not middleware_can_async:
                raise RuntimeError(
                    f"Middleware {middleware_path} must have at least one of sync_capable/async_capable set to True.",
                )
            middleware_is_async = False if not handler_is_async and middleware_can_sync else middleware_can_async

            adapted_handler = handler.adapt_method_mode(
                middleware_is_async,
                composed,
                handler_is_async,
                debug=settings.DEBUG,
                name=f"middleware {middleware_path}",
            )
            try:
                mw_instance = middleware(adapted_handler)
            except MiddlewareNotUsed as exc:
                if settings.DEBUG:
                    if str(exc):
                        logger.debug("MiddlewareNotUsed(%r): %s", middleware_path, exc)
                    else:
                        logger.debug("MiddlewareNotUsed: %r", middleware_path)
                continue

            if mw_instance is None:
                raise ImproperlyConfigured(
                    f"Middleware factory {middleware_path} returned None.",
                )

            # Always-async build: prefer the native a-prefixed hooks, else adapt the sync ones.
            if hasattr(mw_instance, "aprocess_view"):
                self._view_middleware.insert(0, mw_instance.aprocess_view)
            elif hasattr(mw_instance, "process_view"):
                self._view_middleware.insert(
                    0,
                    handler.adapt_method_mode(True, mw_instance.process_view),
                )
            if hasattr(mw_instance, "aprocess_template_response"):
                self._template_response_middleware.append(mw_instance.aprocess_template_response)
            elif hasattr(mw_instance, "process_template_response"):
                self._template_response_middleware.append(
                    handler.adapt_method_mode(True, mw_instance.process_template_response),
                )
            if hasattr(mw_instance, "process_exception"):
                # The exception stack is still always synchronous, matching Django.
                self._exception_middleware.append(
                    handler.adapt_method_mode(False, mw_instance.process_exception),
                )

            self.layers.append(mw_instance)
            composed = convert_exception_to_response(mw_instance)
            handler_is_async = middleware_is_async

        self._middleware_chain = handler.adapt_method_mode(True, composed, handler_is_async)

    # ------------------------------------------------------------------ run

    async def run(self, request: HttpRequest) -> HttpResponseBase:
        """Mirror of ``BaseHandler.get_response_async``."""
        set_urlconf(settings.ROOT_URLCONF)
        response = await self._middleware_chain(request)
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

    async def _run_view(self, request: HttpRequest) -> HttpResponseBase:  # noqa: C901, PLR0912 - mirrors Django's _get_response_async
        """Mirror of ``BaseHandler._get_response_async``: resolve, run view/exception/
        template-response middleware around the view. Resolution uses the handler's
        (router-backed) ``resolve_request``."""
        handler = self.handler
        response: HttpResponseBase | None = None
        callback, callback_args, callback_kwargs = handler.resolve_request(request)

        for middleware_method in self._view_middleware:
            response = await middleware_method(request, callback, callback_args, callback_kwargs)
            if response:
                break

        if response is None:
            wrapped_callback: Any = handler.make_view_atomic(callback)
            if not iscoroutinefunction(wrapped_callback):
                wrapped_callback = sync_to_async(wrapped_callback, thread_sensitive=True)
            try:
                response = await wrapped_callback(request, *callback_args, **callback_kwargs)
            except Exception as e:
                response = await sync_to_async(
                    self._process_exception_by_middleware,
                    thread_sensitive=True,
                )(e, request)
                if response is None:
                    raise

        handler.check_response(response, callback)

        if hasattr(response, "render") and callable(response.render):
            for middleware_method in self._template_response_middleware:
                response = await middleware_method(request, response)
                handler.check_response(
                    response,
                    middleware_method,
                    name=f"{middleware_method.__self__.__class__.__name__}.process_template_response",
                )
            try:
                if iscoroutinefunction(response.render):
                    response = await response.render()
                else:
                    response = await sync_to_async(response.render, thread_sensitive=True)()
            except Exception as e:
                response = await sync_to_async(
                    self._process_exception_by_middleware,
                    thread_sensitive=True,
                )(e, request)
                if response is None:
                    raise

        if asyncio.iscoroutine(response):
            msg = "Response is still a coroutine."
            raise RuntimeError(msg)
        return response

    def _process_exception_by_middleware(self, exception: Exception, request: HttpRequest) -> HttpResponseBase | None:
        """Mirror of ``BaseHandler.process_exception_by_middleware`` over this chain's list."""
        for middleware_method in self._exception_middleware:
            response = middleware_method(request, exception)
            if response:
                return response
        return None
