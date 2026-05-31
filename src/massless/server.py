"""Single-worker serving core: SO_REUSEPORT socket, uvloop, lifecycle hooks,
signal handling, and graceful drain.

``serve_async`` is the awaitable core (testable with plain asyncio); ``serve``
wraps it under uvloop with signal handlers for production/CLI use.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import signal
import socket
from typing import TYPE_CHECKING

import uvloop

from massless._protocol import MasslessProtocol

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from massless.app import MasslessAPI

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
    api: MasslessAPI,
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

    await _run_hooks(api.on_startup_hooks)

    owns_sock = sock is None
    if sock is None:
        sock = _make_socket(host, port)

    loop = asyncio.get_running_loop()
    server = await loop.create_server(lambda: MasslessProtocol(api, api.build_router()), sock=sock)
    try:
        if ready is not None:
            ready.set()
        await stop.wait()
    finally:
        # Stop accepting new connections.
        server.close()
        await server.wait_closed()
        if owns_sock:
            sock.close()
        # Bounded drain for in-flight request tasks.
        await _drain(loop, timeout=drain_timeout)
        await _run_hooks(api.on_shutdown_hooks)
        executor = getattr(api, "executor", None)
        if executor is not None:
            executor.shutdown(wait=False)


async def _drain(loop: asyncio.AbstractEventLoop, *, timeout: float) -> None:  # noqa: ASYNC109
    """Wait (bounded) for outstanding request tasks to finish.

    The protocol's per-connection worker tasks are the in-flight work; give them a
    bounded grace period rather than hanging forever.
    """
    current = asyncio.current_task()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        pending = [t for t in asyncio.all_tasks(loop) if t is not current and not t.done()]
        if not pending:
            return
        await asyncio.sleep(0.01)


def _serve_target(target: str, host: str, port: int, workers: int | None, settings: str | None) -> None:
    """Worker entry point (runs in a spawned process): re-bootstrap Django,
    re-import the app, and serve.

    This lives in ``massless.server`` (NOT ``massless.__main__``) on purpose:
    ``multiprocessing`` with the spawn start method pickles the target by its
    ``module:qualname``, and a function defined in ``__main__`` (which is what
    ``python -m massless`` makes ``massless.__main__`` become) cannot be unpickled
    in the spawned child. A real submodule like this one always re-imports cleanly.
    """
    from massless.__main__ import _bootstrap_django, load_app  # noqa: PLC0415

    _bootstrap_django(settings)
    api = load_app(target)
    serve(api, host, port, workers)


def serve(api: MasslessAPI, host: str, port: int, workers: int | None = None) -> None:
    """Run a single worker under uvloop with SIGTERM/SIGINT graceful shutdown.

    ``workers`` sets the sync-view executor's ``max_workers`` (thread count).
    """
    if workers is not None:
        api._max_workers = workers  # noqa: SLF001

    async def _main() -> None:
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                loop.add_signal_handler(sig, stop.set)
            except (NotImplementedError, ValueError):
                # Signal handlers are unavailable off the main thread; ignore.
                _logger.debug("could not install handler for %s", sig)
        await serve_async(api, host, port, stop=stop)

    uvloop.run(_main())
