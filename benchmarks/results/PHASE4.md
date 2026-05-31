# Phase 4 benchmark: multi-process (SO_REUSEPORT) + sync dispatch

**Date:** 2026-05-31
**What:** With Phase 4, the server runs N worker processes via `SO_REUSEPORT` and
dispatches sync views on a thread-pool. Two measurements: (a) 4-worker N-vs-N on the
core, and (b) sync vs async dispatch cost. Plus a lifecycle check.

Machine: 32 cores, Python 3.14, loopback. massless and django-bolt run `--processes 4`;
plain Django runs `uvicorn --workers 4`.

## (a) Four workers each, core endpoints (saturating load)

A first attempt drove each server with a single `bombardier -c 50` and produced a flat
~80K ceiling that made the frameworks look "converged." That was a **measurement bug,
not a result**: one bombardier process is itself CPU-bound (~one core, mostly loopback
syscalls), so it cannot saturate four workers. Re-measured with
[`aggregate.sh`](../aggregate.sh) (8 parallel bombardier clients), the server workers
hit **~400% CPU (4 cores, fully saturated)** while the 32-core box stayed ~93% idle, so
these are genuinely **server-bound** numbers. Aggregate req/s across the 8 clients:

| Endpoint | django req/s | bolt req/s | massless req/s | vs bolt | vs django |
|----------|-------------:|-----------:|---------------:|--------:|----------:|
| `/` | 7,679 | 131,825 | 170,896 | **1.30x** | 22x |
| `/items/12345?q=hello` | 7,095 | 111,911 | 147,080 | **1.31x** | 21x |
| `/10k-json` | 6,338 | 91,399 | 97,854 | 1.07x | 15x |

At 4 workers massless stays **~1.3x django-bolt** on the routing/dispatch-bound
endpoints and ~15-22x plain Django. The margin over bolt is smaller than the ~2x of the
single-process comparison (PHASE1-3): under 4 concurrent workers both frameworks lose
per-worker efficiency to shared memory bandwidth and the loopback network stack, and
the gap narrows most on `/10k-json` (1.07x) where serialization, not framework overhead,
dominates. To verify saturation yourself, watch worker CPU with `pidstat` while
`aggregate.sh` runs (see its header).

## (b) Sync dispatch cost (massless)

These two were measured with a single client (the *ratio* is the point, so compare the
rows; the absolute numbers are single-client and not directly comparable to the
saturating aggregates in (a)).

| Endpoint | req/s | relative |
|----------|------:|---------:|
| `/` (async, on the loop) | 84,233 | 1.00x |
| `/sync-hello` (sync `def`, thread-pool executor) | 32,423 | 0.38x |

A sync view runs in the `ThreadPoolExecutor` (so blocking ORM is safe), which costs
~62% versus an async view: the thread hop plus the GIL serializing Python-level work
in the pool. This is the expected sync-on-a-thread tax (the same reason async views
are preferred for non-DB work); it is the price of supporting blocking Django code
safely, and DB-bound sync views converge to the ORM ceiling regardless.

## Lifecycle (verified, not a benchmark)

- `--processes 2` load-balances across both workers (kernel `SO_REUSEPORT`); verified
  earlier with a pid-returning app (requests split across 2 distinct worker PIDs).
- `fuser -k` of the workers (an unexpected death) triggers the **supervisor to restart
  them** (port back to 200), as designed.
- `SIGTERM` to the **master** shuts down gracefully: workers drain in-flight requests,
  run shutdown hooks, and exit; the port goes down with **no orphan processes**.

## Caveats

- Single run, no warmup; loopback + one bombardier client; the ~80K ceiling dominates
  the multi-process core numbers (see (a)). Treat (a) as "comparable at saturation,"
  not a scaling measurement.
- Same partial-implementation note as prior phases: only the implemented endpoints are
  meaningful; other rows in the raw reports are 404 artifacts.
