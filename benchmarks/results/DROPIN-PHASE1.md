# Drop-in Phase 1 benchmark: massless vs uvicorn+Django (same app)

**Date:** 2026-06-01
**What:** After the pivot to a drop-in accelerator, the honest comparison is the **same
unmodified Django app** served by massless vs by uvicorn. Both run 4 workers on a 32-core
box; load is the saturating multi-client driver (`aggregate.sh`, 8 parallel bombardier
clients), so the numbers are server-bound, not client-bound.

App: `benchmarks/django_baseline` (normal Django async views: `/` returns a small
`JsonResponse`; `/items/<int>?q=` reads `request.GET`). Two middleware configs.

## (a) Lean middleware (empty `MIDDLEWARE`)

The view touches little, so massless's lazy request never materializes `META`/`COOKIES`
(and `/` never even builds `GET`). This is the case `MIDDLEWARE_STACKS` (Phase 2) will let
you opt hot routes into.

| Endpoint | uvicorn+Django req/s | massless req/s | speedup |
|----------|---------------------:|---------------:|--------:|
| `/` | 7,686 | 42,804 | **5.57x** |
| `/items/7?q=hi` | 7,101 | 37,649 | **5.30x** |

## (b) Full default stack (`SecurityMiddleware` + `CommonMiddleware`)

Stock middleware reads `get_host()`/`is_secure()`, which promotes the lazy request before
the view, so the lazy-construction win is mostly gone here. The remaining win is the C
parse, the efficient request build from C buffers, and C response serialization vs Django's
ASGI scope -> `ASGIRequest` -> ASGI-send path.

| Endpoint | uvicorn+Django req/s | massless req/s | speedup |
|----------|---------------------:|---------------:|--------:|
| `/` | 4,691 | 15,320 | **3.27x** |
| `/items/7?q=hi` | 4,491 | 13,943 | **3.10x** |

## Reading this

- A **zero-change drop-in** (same `urls.py`, views, `settings`, `MIDDLEWARE`) serves a
  normal Django app **~3.3x faster** than uvicorn+Django on the full default stack, and
  **~5.5x** on lean middleware. The earlier design doc predicted a "bounded, near-parity"
  default-path gain; the measurement shows that was too pessimistic. The C pipeline + the
  request built directly from C buffers (no ASGI scope round-trip) is a real ~3.3x even
  when the request promotes; the lazy request adds the rest on lean routes.
- The lean-vs-full gap (5.5x vs 3.3x) is exactly the lazy-request lever, which validates
  the Phase 2 `MIDDLEWARE_STACKS` direction: put hot routes on a lean stack and they
  stay lazy.
- Responses are byte-identical to Django (the drop-in runs Django's real resolver +
  middleware + view); see `tests/test_dropin.py::test_responses_match_django_test_client`.

## Caveats

- Single run per endpoint, no warmup, loopback, one machine; the absolute ceiling is the
  loopback stack across cores. The *ratio* (massless vs uvicorn on the identical app and
  load) is the trustworthy figure. Re-run before quoting as stable.
- uvicorn was run with its default (uvloop) `--workers 4`; massless with `--processes 4`.
- This benchmarks the small-`JsonResponse` framework-overhead case. DB-bound endpoints
  converge to the Django ORM ceiling regardless of server (an accepted, documented limit).
- The retired bolt-style engine's numbers live in `PHASE1-4.md`; they are not comparable
  to the drop-in.
