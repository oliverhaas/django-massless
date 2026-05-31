# Phase 3 benchmark: fast-tier auth/CORS + no regression

**Date:** 2026-05-31
**What:** After Phase 3 (tiered middleware), measure (a) the fast-tier JWT auth path
head-to-head with django-bolt's `/auth/context`, (b) CORS overhead, and (c) no
regression on the framework-bound core.

Single-process, all optimized: massless (Cython), django-bolt 0.8.1 (`--release`),
plain Django ASGI (uvicorn 1 worker). bombardier `-c 50 -n 10000`. Same host, Python
3.14, one server under load at a time.

## (a) Fast-tier JWT auth (no promotion), head-to-head with django-bolt

`/auth/context` validates an HS256 `Authorization: Bearer` JWT and reads only the
claims (`request.auth`); it never promotes. Both frameworks expose this case.

| Endpoint | bolt req/s | massless req/s | speedup |
|----------|-----------:|---------------:|--------:|
| `/auth/context` (JWT validated, no DB) | 24,887 | 58,419 | **2.35x** |

massless verifies the JWT in the C fast tier (stdlib `hmac`/`hashlib`, constant-time
compare, no promotion) and is ~2.35x faster than django-bolt's equivalent.

## (b) Middleware overhead on the fast path (same massless server, back-to-back)

| Endpoint | req/s | relative to `/` |
|----------|------:|----------------:|
| `/` (no middleware) | 86,094 | 1.00x |
| `/cors/ping` (CORS middleware) | 78,661 | 0.91x |
| `/auth/context` (JWT middleware) | 58,419 | 0.68x |

CORS costs ~9%; HS256 JWT verification costs ~32%. Both stay entirely on the C fast
path (no promotion), so an authenticated, framework-bound request is still far faster
than promoting into Django. CORS preflight (`OPTIONS`) is answered `204` on the fast
path.

## (c) No regression on the framework-bound core (3-way)

| Endpoint | django | bolt | massless | vs bolt |
|----------|-------:|-----:|---------:|--------:|
| `/` | 2,318 | 40,044 | 63,554 | 1.59x |
| `/10k-json` | 1,834 | 26,444 | 38,300 | 1.45x |
| `/items/12345` | 2,018 | 32,203 | 73,362 | 2.28x |
| `/items/12345?q=hello` | 2,140 | 31,822 | 80,700 | 2.54x |

In line with Phases 1-2; the middleware tiers add no cost to routes that use no
middleware.

## Caveats

- Single run per endpoint, no warmup; run-to-run variance is real (`/` is 63.5k under
  the 3-way run.sh sweep vs 86.1k in the isolated middleware-overhead pair). The (a)/(b)
  pairs are the apples-to-apples figures (same server, back-to-back).
- `/auth/me` (promotes + ORM user load) is not benchmarked here: it needs a configured
  user DB on the standalone server. The promotion cost itself is measured in PHASE2.md.
- The massless server was launched with `DJANGO_SETTINGS_MODULE` so the bridge/promotion
  paths work; the fast tier (auth/CORS/rate-limit) needs no settings.
- Same partial-implementation caveat as before: the non-core rows in the raw reports are
  404 artifacts; only the listed endpoints are implemented.
