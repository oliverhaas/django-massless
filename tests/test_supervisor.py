"""Task 5: Supervisor spawn/monitor/restart/shutdown logic, tested deterministically
with a module-level fake worker target that signals readiness via a Queue (proving
the spawned worker actually re-imported and ran the target). Bounded waits + a
finally-shutdown so no test leaks orphan processes or hangs."""

import multiprocessing as mp

import pytest
from supervisor_targets import ready_then_sleep

from massless.supervisor import Supervisor


@pytest.fixture
def spawn_ctx():
    return mp.get_context("spawn")


def _drain_ready(queue, count, timeout=20.0):
    """Collect ``count`` worker pids from the ready queue (workers signal once
    they are actually running their target)."""
    import queue as _q

    pids = []
    import time

    deadline = time.monotonic() + timeout
    while len(pids) < count and time.monotonic() < deadline:
        try:
            pids.append(queue.get(timeout=max(0.0, deadline - time.monotonic())))
        except _q.Empty:
            break
    return pids


def test_start_spawns_and_runs_n_workers(spawn_ctx):
    q = spawn_ctx.Queue()
    sup = Supervisor(ready_then_sleep, args=(q,), n=2, ctx=spawn_ctx, join_timeout=5.0)
    try:
        sup.start()
        pids = _drain_ready(q, 2)
        # Both spawned workers re-imported the target and signalled readiness.
        assert len(pids) == 2, f"only {len(pids)} workers signalled ready"
        assert all(p.is_alive() for p in sup._workers)
    finally:
        sup.shutdown()
    assert sup._workers == []


def test_reap_and_restart_replaces_dead_worker(spawn_ctx):
    q = spawn_ctx.Queue()
    sup = Supervisor(ready_then_sleep, args=(q,), n=2, ctx=spawn_ctx, join_timeout=5.0)
    try:
        sup.start()
        assert len(_drain_ready(q, 2)) == 2
        victim = sup._workers[0]
        victim_pid = victim.pid

        victim.terminate()
        victim.join(timeout=5)
        assert not victim.is_alive()

        # A single monitor step must re-spawn to keep n=2 alive.
        sup._reap_and_restart()
        assert len(sup._workers) == 2
        # The replacement worker re-imported the target and signalled ready.
        new_pids = _drain_ready(q, 1)
        assert len(new_pids) == 1
        assert victim_pid not in [p.pid for p in sup._workers]
        assert all(p.is_alive() for p in sup._workers)
    finally:
        sup.shutdown()
    assert sup._workers == []


def test_shutdown_terminates_all_workers(spawn_ctx):
    q = spawn_ctx.Queue()
    sup = Supervisor(ready_then_sleep, args=(q,), n=3, ctx=spawn_ctx, join_timeout=5.0)
    sup.start()
    assert len(_drain_ready(q, 3)) == 3
    procs = list(sup._workers)
    sup.shutdown()
    assert all(not p.is_alive() for p in procs)
    assert all(p.exitcode is not None for p in procs)
    assert sup._workers == []


def test_reap_does_not_restart_during_shutdown(spawn_ctx):
    q = spawn_ctx.Queue()
    sup = Supervisor(ready_then_sleep, args=(q,), n=2, ctx=spawn_ctx, join_timeout=5.0)
    sup.start()
    assert len(_drain_ready(q, 2)) == 2
    sup.shutdown()
    # After shutdown, a monitor step must NOT spawn new workers.
    sup._reap_and_restart()
    assert sup._workers == []
