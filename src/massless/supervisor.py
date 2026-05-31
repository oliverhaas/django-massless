"""Master process: spawn, monitor, restart, and gracefully shut down N workers.

Workers share one ``(host, port)`` via SO_REUSEPORT (each builds its own socket),
so the master only manages process lifecycle. Uses the ``spawn`` start method;
spawned workers do NOT inherit the parent's imported app, so the worker target is
a module-level callable that re-imports/rebuilds what it needs (see __main__).
"""

from __future__ import annotations

import contextlib
import logging
import multiprocessing as mp
import os
import signal
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

_logger = logging.getLogger("massless")

# Exit code a worker uses for a clean, intentional shutdown; anything else is
# treated as an unexpected death and triggers a restart.
_GRACEFUL_EXITCODE = 0


class Supervisor:
    def __init__(
        self,
        target: Callable,
        args: tuple = (),
        n: int = 1,
        *,
        ctx: mp.context.BaseContext | None = None,
        join_timeout: float = 5.0,
    ) -> None:
        self._target = target
        self._args = args
        self._n = n
        self._ctx = ctx or mp.get_context("spawn")
        self._join_timeout = join_timeout
        self._workers: list[mp.process.BaseProcess] = []
        self._shutting_down = False

    def _spawn_one(self) -> mp.process.BaseProcess:
        proc = self._ctx.Process(target=self._target, args=self._args, daemon=False)  # type: ignore[attr-defined]
        proc.start()
        self._workers.append(proc)
        return proc

    def start(self) -> None:
        """Spawn ``n`` workers."""
        for _ in range(self._n):
            self._spawn_one()

    def _reap_and_restart(self) -> None:
        """One monitor step: replace any worker that has exited, unless we are
        shutting down. Keeps exactly ``n`` workers alive."""
        if self._shutting_down:
            return
        alive: list[mp.process.BaseProcess] = []
        for proc in self._workers:
            if proc.is_alive():
                alive.append(proc)
            else:
                proc.join(timeout=0)
                _logger.warning("worker %s exited (code=%s); restarting", proc.pid, proc.exitcode)
        self._workers = alive
        while len(self._workers) < self._n:
            self._spawn_one()

    def monitor(self, *, poll_interval: float = 0.5) -> None:
        """Block, restarting dead workers, until ``shutdown`` is called."""
        while not self._shutting_down:
            self._reap_and_restart()
            time.sleep(poll_interval)

    def shutdown(self) -> None:
        """Signal all workers to stop, join with a timeout, escalate to terminate."""
        self._shutting_down = True
        for proc in self._workers:
            if proc.is_alive():
                self._signal(proc, signal.SIGTERM)
        deadline = time.monotonic() + self._join_timeout
        for proc in self._workers:
            remaining = max(0.0, deadline - time.monotonic())
            proc.join(timeout=remaining)
        for proc in self._workers:
            if proc.is_alive():
                _logger.warning("worker %s did not exit; terminating", proc.pid)
                proc.terminate()
                proc.join(timeout=self._join_timeout)
        self._workers = []

    @staticmethod
    def _signal(proc: mp.process.BaseProcess, sig: int) -> None:
        if proc.pid is not None:
            with contextlib.suppress(ProcessLookupError):
                os.kill(proc.pid, sig)


def run_supervised(target: Callable, *args: object, processes: int = 1) -> None:
    """Spawn and supervise ``processes`` workers running ``target(*args)``.

    Installs SIGTERM/SIGINT handlers in the master that trigger a graceful
    shutdown of all workers, then blocks in the monitor loop.
    """
    supervisor = Supervisor(target, args=args, n=processes)

    def _handle(signum, frame) -> None:  # noqa: ANN001, ARG001
        supervisor.shutdown()

    signal.signal(signal.SIGTERM, _handle)
    signal.signal(signal.SIGINT, _handle)

    supervisor.start()
    try:
        supervisor.monitor()
    finally:
        supervisor.shutdown()
