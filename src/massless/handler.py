"""The core drop-in handler: run a request through Django's real middleware chain
and URL resolver, exactly as Django's own ASGI/WSGI handlers do, but fed a lazy
MasslessRequest built from the C buffers instead of an ASGI scope.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.core.handlers.base import BaseHandler

if TYPE_CHECKING:
    import asyncio
    from collections.abc import Callable

    from django.http import HttpRequest, HttpResponseBase


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

    async def handle(self, request: HttpRequest) -> HttpResponseBase:
        return await self.get_response_async(request)
