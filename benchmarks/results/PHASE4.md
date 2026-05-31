# Phase 4 benchmark: multi-process (SO_REUSEPORT) + sync dispatch

**Date:** 2026-05-31
**What:** With Phase 4, the server runs N worker processes via `SO_REUSEPORT` and
dispatches sync views on a thread-pool. Two measurements: (a) 2-worker N-vs-N on the
core, and (b) sync vs async dispatch cost. Plus a lifecycle check.

bombardier `-c 50 -n 10000`, same host (loopback), Python 3.14. massless and
django-bolt run `--processes 2`; plain Django runs `uvicorn --workers 2`.

## (a) Two workers each, core endpoints

| Endpoint | django req/s | bolt req/s | massless req/s | vs bolt |
|----------|-------------:|-----------:|---------------:|--------:|
| `/` | 4,387 | 75,924 | 83,307 | 1.10x |
| `/10k-json` | 3,580 | 52,697 | 49,906 | 0.95x |
| `/items/12345` | 4,042 | 65,695 | 75,963 | 1.16x |
| `/items/12345?q=hello` | 4,005 | 65,485 | 71,083 | 1.09x |

**Read this with the caveat below, not as "the single-process 2x advantage
disappeared."** At 2 workers massless and django-bolt are comparable here, but the
numbers are almost certainly **harness-ceiling-bound, not server-bound**:

- massless single-process was ~76K req/s (PHASE1-3); at 2 workers it is ~83K, i.e.
  it barely scaled.
- django-bolt single-process was ~40K; at 2 workers it is ~76K, i.e. it ~doubled.

A framework that was already at ~76K single-process cannot show 2x from a second
worker if the **loopback + single bombardier client saturates around ~80K req/s** on
this machine. django-bolt, starting below that ceiling, had room to double; massless,
already near it, did not. So this measures the load harness, not massless's true
multi-process throughput. A real multi-process scaling number needs a heavier load
setup (multiple client machines, or higher `-c`, off-loopback). The honest single-
process per-request-overhead comparison (massless ~2x bolt, ~30x plain Django) is in
PHASE1-3; this phase's contribution is that multi-process *works* (see lifecycle).

## (b) Sync dispatch cost (massless, 2 workers)

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
