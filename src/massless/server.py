"""Single-worker serving core: SO_REUSEPORT socket, uvloop, lifecycle hooks,
signal handling, and graceful drain.

``serve_async`` is the awaitable core (testable with plain asyncio); ``serve``
wraps it under uvloop with signal handlers for production/CLI use.
"""

from __future__ import annotations

import asyncio
import contextlib
import inspect
import logging
import signal
import socket
from typing import TYPE_CHECKING

import uvloop

from massless._protocol import MasslessProtocol

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from massless.handler import MasslessHandler

_logger = logging.getLogger("massless")

# Bounded grace period for in-flight requests to finish before forced shutdown.
_DRAIN_TIMEOUT = 5.0


def _make_socket(host: str, port: int) -> socket.socket:
    """Build a TCP listening socket with SO_REUSEADDR + SO_REUSEPORT set *before*
    bind, marked inheritable so spawned workers can share the port.

    Returned unlistened; asyncio's ``create_server(sock=...)`` calls ``listen``.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    sock.bind((host, port))
    sock.set_inheritable(True)
    return sock


async def _run_hooks(hooks: list[Callable[[], Awaitable | None]]) -> None:
    """Run lifecycle hooks in order: await async ones, call sync ones directly."""
    for hook in hooks:
        result = hook()
        if inspect.isawaitable(result):
            await result


async def serve_async(  # noqa: PLR0913
    handler: MasslessHandler,
    host: str,
    port: int,
    *,
    ready: asyncio.Event | None = None,
    stop: asyncio.Event | None = None,
    sock: socket.socket | None = None,
    drain_timeout: float = _DRAIN_TIMEOUT,
) -> None:
    """Serve one worker: run startup hooks, accept connections until ``stop`` is
    set, then close the listener, drain in-flight requests, and run shutdown hooks.

    ``ready`` is set once the server is accepting (after startup hooks). A caller
    may pass a pre-made ``sock`` (e.g. a shared SO_REUSEPORT socket); otherwise one
    is created here.
    """
    if stop is None:
        stop = asyncio.Event()

    # Reset per-serve drain state and bind the drain event to this loop.
    handler._draining = False  # noqa: SLF001
    handler._drain_event = asyncio.Event()  # noqa: SLF001

    await _run_hooks(handler.on_startup_hooks)

    owns_sock = sock is None
    if sock is None:
        sock = _make_socket(host, port)

    loop = asyncio.get_running_loop()
    server = await loop.create_server(lambda: MasslessProtocol(handler), sock=sock)
    try:
        if ready is not None:
            ready.set()
        await stop.wait()
    finally:
        # Stop accepting new connections.
        server.close()
        # Signal connections to wind down BEFORE waiting on the server: on 3.12+
        # ``wait_closed`` blocks until active connections finish, and idle
        # keep-alive loops only exit once the drain event is set.
        handler.begin_drain()
        # Wait (bounded) for in-flight request work to finish -- only real
        # requests, not idle keep-alive loops.
        await _drain(handler, timeout=drain_timeout)
        # Connections whose worker loops have exited will close; bound the wait so
        # a wedged peer cannot hang shutdown past the grace period.
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(server.wait_closed(), timeout=drain_timeout)
        if owns_sock:
            sock.close()
        await _run_hooks(handler.on_shutdown_hooks)
        # Shut the sync-view executor down last, waiting (bounded) for any
        # in-flight sync views (e.g. slow ORM calls) so threads do not leak.
        executor = getattr(handler, "executor", None)
        if executor is not None:
            await _shutdown_executor(loop, executor, timeout=drain_timeout)


async def _drain(handler: MasslessHandler, *, timeout: float) -> None:  # noqa: ASYNC109
    """Wait (bounded) for outstanding in-flight request work to finish.

    ``handler._inflight`` holds one future per request currently being handled;
    each resolves when its response is produced. We await the snapshot, then
    re-check for late arrivals (pipelined behind an in-flight request) until either
    the set is empty or the grace period elapses, then cancel any stragglers.
    """
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while handler._inflight:  # noqa: SLF001
        remaining = deadline - loop.time()
        if remaining <= 0:
            break
        pending = set(handler._inflight)  # noqa: SLF001
        await asyncio.wait(pending, timeout=remaining)
    # Past the grace period: cancel any request futures still outstanding.
    for fut in list(handler._inflight):  # noqa: SLF001
        if not fut.done():
            fut.cancel()


async def _shutdown_executor(
    loop: asyncio.AbstractEventLoop,
    executor: object,
    *,
    timeout: float,  # noqa: ASYNC109
) -> None:
    """Shut the thread-pool executor down, waiting (bounded) for in-flight sync
    views so worker threads do not leak. ``executor.shutdown(wait=True)`` blocks,
    so it runs off the loop and is itself bounded by the grace period."""
    try:
        await asyncio.wait_for(
            loop.run_in_executor(None, lambda: executor.shutdown(wait=True)),  # type: ignore[attr-defined]
            timeout=timeout,
        )
    except TimeoutError:
        # A sync view outlived the grace period; drop the wait so we still exit.
        executor.shutdown(wait=False)  # type: ignore[attr-defined]


def _serve_target(host: str, port: int, workers: int | None, settings: str | None) -> None:
    """Worker entry point (runs in a spawned process): re-bootstrap Django, build a
    fresh handler from the configured settings, and serve.

    This lives in ``massless.server`` (NOT ``massless.__main__``) on purpose:
    ``multiprocessing`` with the spawn start method pickles the target by its
    ``module:qualname``, and a function defined in ``__main__`` (which is what
    ``python -m massless`` makes ``massless.__main__`` become) cannot be unpickled
    in the spawned child. A real submodule like this one always re-imports cleanly.
    """
    from massless.__main__ import _bootstrap_django  # noqa: PLC0415
    from massless.handler import MasslessHandler  # noqa: PLC0415

    _bootstrap_django(settings)
    handler = MasslessHandler()
    serve(handler, host, port, workers)


def serve(handler: MasslessHandler, host: str, port: int, workers: int | None = None) -> None:
    """Run a single worker under uvloop with SIGTERM/SIGINT graceful shutdown.

    ``workers`` sets the sync-view executor's ``max_workers`` (thread count).
    """
    if workers is not None:
        handler._max_workers = workers  # noqa: SLF001

    async def _main() -> None:
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                loop.add_signal_handler(sig, stop.set)
            except (NotImplementedError, ValueError):
                # Signal handlers are unavailable off the main thread; ignore.
                _logger.debug("could not install handler for %s", sig)
        await serve_async(handler, host, port, stop=stop)

    uvloop.run(_main())
