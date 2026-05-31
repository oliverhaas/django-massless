"""Module-level fake worker targets for supervisor tests.

These MUST be importable by name so the ``spawn`` start method can pickle them.
Each takes a shared ``ready`` Event/Queue so tests can deterministically wait
until the spawned worker has actually re-imported this module and started running
its target (proving spawn re-loads the worker code), instead of racing on
``Process.is_alive()`` (which is True the instant the OS process spawns).
"""

import os
import signal
import time


def ready_then_sleep(ready_queue):
    """Signal the parent (with this worker's pid) once running, then sleep until
    SIGTERM, exiting 0. ``ready_queue`` is a multiprocessing Queue."""

    def _stop(signum, frame):
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, _stop)
    ready_queue.put(os.getpid())
    while True:
        time.sleep(0.05)


def ignore_sigterm_then_sleep(ready_queue):
    """A hung worker that IGNORES SIGTERM (the graceful-stop signal), so the
    supervisor's escalation must use SIGKILL to actually stop it. Signals the
    parent once running, then sleeps forever. ``ready_queue`` is a mp Queue."""
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    ready_queue.put(os.getpid())
    while True:
        time.sleep(0.05)
