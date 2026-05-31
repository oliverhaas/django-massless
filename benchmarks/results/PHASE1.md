# Phase 1 benchmark: massless vs django-bolt vs plain Django

**Date:** 2026-05-31
**What:** Phase 1 exit-criterion benchmark on the framework-bound endpoints, three
single-process servers:

- **massless** (this framework, Cython pipeline),
- **django-bolt** 0.8.1 (the Rust/PyO3 predecessor, `--release`),
- **plain Django** ASGI (the framework-overhead floor).

First benchmark, captured the day Phase 1 landed. Directional signal, not a rigorous
measurement (see Caveats).

## Result

massless beats single-process django-bolt by **~1.4x to 2.3x (median ~2.06x)** and
plain Django by **~23x to 34x (median ~33x)** on every core endpoint, at a fraction
of the p50 latency.

| Endpoint | django req/s | bolt req/s | massless req/s | vs bolt | vs django |
|----------|-------------:|-----------:|---------------:|--------:|----------:|
| `/` (root JSON) | 2,285 | 38,367 | 76,211 | 1.99x | 33.4x |
| `/10k-json` | 1,730 | 27,258 | 39,054 | 1.43x | 22.6x |
| `/items/12345` (path int) | 2,153 | 31,730 | 72,625 | 2.29x | 33.7x |
| `/items/12345?q=hello` (path + query) | 2,180 | 33,348 | 70,771 | 2.12x | 32.5x |

p50 latency (same run):

| Endpoint | django p50 | bolt p50 | massless p50 |
|----------|-----------:|---------:|-------------:|
| `/` | 21.98ms | 1.29ms | 0.56ms |
| `/10k-json` | 28.26ms | 1.81ms | 1.16ms |
| `/items/12345` | 23.32ms | 1.56ms | 0.66ms |
| `/items/12345?q=hello` | 23.21ms | 1.48ms | 0.66ms |

All runs returned `2xx` for all 10,000 requests on every server.

This supports the thesis (design §1): with no FFI seam, the Cython pipeline pays less
per-request framework overhead than bolt's Rust/PyO3 boundary on framework-bound work,
and both are far above the plain-Django floor.

## Methodology

- **Load tool:** bombardier, `-c 50 -n 10000` per endpoint.
- **All single-process / single-worker**, all optimized:
  - massless: the Cython extension built by setuptools, served via `python -m massless benchmarks.app:api`.
  - django-bolt 0.8.1, built `--release`, served via `manage.py runbolt --processes 1`.
  - plain Django: async views, empty middleware, no apps (the rawest ASGI path),
    served via `uvicorn benchmarks.django_baseline.asgi:application --workers 1` (uvloop).
- **Same host**, Python 3.14, one server under load at a time (others idle).
- **Payloads:** `/10k-json` is 10,921 bytes (massless), 10,864 bytes (bolt), and
  12,520 bytes (Django, which adds JSON whitespace). Close enough to compare; not
  byte-identical because Django does not emit compact JSON.

SO_REUSEPORT multi-process is a Phase 4 concern and out of scope here.

## Reproduce

```console
# massless on :8000
uv run python -m massless benchmarks.app:api --port 8000
# single-process django-bolt on :8001 (in the django-bolt repo, release-built)
DJANGO_BOLT_WORKERS=1 python manage.py runbolt --host 127.0.0.1 --port 8001 --processes 1
# plain Django on :8002
uv run uvicorn benchmarks.django_baseline.asgi:application --port 8002 --workers 1

# from this repo
PORT=8000 LABEL=massless OUT=benchmarks/results/massless.md ./benchmarks/run.sh
PORT=8001 LABEL=bolt     OUT=benchmarks/results/bolt.md     ./benchmarks/run.sh
PORT=8002 LABEL=django   OUT=benchmarks/results/django.md   ./benchmarks/run.sh
python benchmarks/compare.py benchmarks/results/bolt.md benchmarks/results/massless.md
```

## Caveats

- **Single run per endpoint.** No warmup, no repeated trials. Run-to-run variance is
  real (massless `/` was 76.5k one run, 76.2k another; bolt `/` 40.7k then 38.4k).
  Re-run before quoting these as stable.
- **Plain Django config is the floor, not a tuned deployment.** Empty middleware, no
  apps, async views on a single uvicorn worker. A real Django app (default middleware,
  more workers) differs. The point is the order-of-magnitude framework-overhead floor.
- **Only these 4 endpoints are implemented in Phase 1.** The raw `run.sh` reports and
  `compare.py` also list the rest of the django-bolt case matrix (`/100k-json`,
  `/feed`, `/header`, ...); massless and Django return a fast 404 there while bolt does
  the real work, so those rows are artifacts, not wins. Disregard them until later
  phases implement those endpoints. The `compare.py` gate scores only these 4 core keys.
- Raw per-run reports live alongside this file: `massless.md`, `bolt.md`, `django.md`.
