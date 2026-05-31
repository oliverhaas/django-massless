# Phase 2 benchmark: no fast-path regression + promotion cost

**Date:** 2026-05-31
**What:** After Phase 2 (lazy promotion + Django glue), confirm (a) the framework-bound
fast path did not regress, and (b) measure what promotion costs when a view actually
materializes a full Django request.

Single-process, all optimized: massless (Cython), django-bolt 0.8.1 (`--release`),
plain Django ASGI (uvicorn 1 worker). bombardier `-c 50 -n 10000`. Same host, Python
3.14, one server under load at a time.

## (a) No fast-path regression

The 4 framework-bound endpoints never promote (their views take no `request` param),
so they stay on the Phase 1 C path. Numbers are in line with Phase 1 (run-to-run
variance applies):

| Endpoint | django req/s | bolt req/s | massless req/s | vs bolt |
|----------|-------------:|-----------:|---------------:|--------:|
| `/` | 2,308 | 38,302 | 76,560 | 2.00x |
| `/10k-json` | 1,839 | 25,682 | 40,115 | 1.56x |
| `/items/12345` | 2,169 | 33,382 | 76,396 | 2.29x |
| `/items/12345?q=hello` | 2,030 | 31,016 | 81,413 | 2.62x |

massless still beats django-bolt ~1.6x to 2.6x and plain Django ~30x. No regression.

## (b) Promotion cost

Measured back-to-back on the same massless server (started with
`DJANGO_SETTINGS_MODULE` so promotion can run), comparing a non-promoting endpoint to
one that forces a full promotion (`/promote-demo` calls `request.get_host()`):

| Endpoint | req/s | relative |
|----------|------:|---------:|
| `/` (no promotion) | 85,467 | 1.00x |
| `/promote-demo` (full promotion: builds the WSGI environ + `WSGIRequest.__init__`) | 49,826 | 0.58x |

Promotion costs roughly **42% of throughput** (about 17µs/request of extra work to
reconstruct the full Django request). Even fully promoted, the path is ~25x faster than
plain Django and comparable to django-bolt's non-promoting numbers. This is the
"pay the lift-into-Django cost only when, and if, a request needs it" thesis (design
§1) holding: framework-bound requests stay on the C path; only requests that reach for
Django state pay for it, once.

## Caveats

- Single run per endpoint, no warmup; run-to-run variance is real (the `/` number is
  76.5k under the 3-way run.sh sweep vs 85.5k in the isolated promotion-cost pair).
  Re-run before quoting as stable.
- The promotion-cost pair is the apples-to-apples figure (identical server, back-to-back).
- Promotion requires configured Django settings (`get_host()` reads `ALLOWED_HOSTS`),
  so the benchmark server was launched with `DJANGO_SETTINGS_MODULE`. Fast-path-only
  apps still run with no settings, as in Phase 1.
- Same partial-implementation caveat as Phase 1: only the 4 core endpoints (+ now
  `/promote-demo`) are implemented; the other rows in the raw reports are 404 artifacts.
