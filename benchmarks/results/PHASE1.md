# Phase 1 benchmark: massless vs django-bolt

**Date:** 2026-05-31
**What:** Phase 1 exit-criterion benchmark. Single-process django-massless against
single-process [django-bolt](https://github.com/) (the Rust/PyO3 predecessor) on
the framework-bound endpoints both implement.

This is the first benchmark, captured the day Phase 1 landed. Treat the numbers as
a directional signal, not a rigorous measurement (see Caveats).

## Result

massless beats single-process django-bolt on every core endpoint, by **1.48x to
2.37x (median ~2.07x)**, at roughly half the p50 latency.

| Endpoint | bolt req/s | massless req/s | speedup | bolt p50 | massless p50 | bolt p99 | massless p99 |
|----------|-----------:|---------------:|--------:|---------:|-------------:|---------:|-------------:|
| `/` (root JSON) | 40,709 | 76,546 | 1.88x | 1.21ms | 0.53ms | 1.35ms | 1.18ms |
| `/10k-json` | 26,110 | 38,585 | 1.48x | 1.90ms | 1.22ms | 2.17ms | 2.59ms |
| `/items/12345` (path int) | 34,061 | 77,257 | 2.27x | 1.44ms | 0.62ms | 1.75ms | 1.24ms |
| `/items/12345?q=hello` (path + query) | 31,480 | 74,747 | 2.37x | 1.58ms | 0.64ms | 1.72ms | 1.30ms |

All runs returned `2xx` for all 10,000 requests on both servers.

This supports the thesis (design §1): with no FFI seam, the Cython pipeline pays less
per-request framework overhead than bolt's Rust/PyO3 boundary on framework-bound
(non-DB) work.

## Methodology

- **Load tool:** bombardier, `-c 50 -n 10000` per endpoint (the config django-bolt
  uses, so numbers are comparable).
- **Both single-process**, both optimized: massless is the Cython extension built by
  setuptools; django-bolt 0.8.1 was built `--release`. SO_REUSEPORT multi-process is
  a Phase 4 concern and out of scope here.
- **Same host**, Python 3.14, one server under load at a time (the other idle).
- **Comparable payloads:** `/10k-json` is 10,921 bytes (massless) vs 10,864 bytes
  (bolt).
- massless served via `python -m massless benchmarks.app:api`; bolt via
  `manage.py runbolt --processes 1`.

## Reproduce

```console
# massless on :8000
uv run python -m massless benchmarks.app:api --port 8000

# single-process django-bolt on :8001 (in the django-bolt repo, release-built)
DJANGO_BOLT_WORKERS=1 python manage.py runbolt --host 127.0.0.1 --port 8001 --processes 1

# from this repo
PORT=8000 LABEL=massless OUT=benchmarks/results/massless.md ./benchmarks/run.sh
PORT=8001 LABEL=bolt     OUT=benchmarks/results/bolt.md     ./benchmarks/run.sh
python benchmarks/compare.py benchmarks/results/bolt.md benchmarks/results/massless.md
```

## Caveats

- **Single run per endpoint.** No warmup, no repeated trials. Run-to-run variance is
  real: massless showed high req/s standard deviation on `/` (mean 76.5k, stdev 24k),
  while bolt's distributions were tight. Re-run before quoting these as stable.
- **Only these 4 endpoints are implemented in Phase 1.** `compare.py` and the raw
  `run.sh` reports also list the rest of the django-bolt case matrix (`/100k-json`,
  `/feed`, `/header`, and so on); on those, massless returns a fast 404 while bolt
  does the real work, so those rows are artifacts, not wins. Disregard them until
  later phases implement those endpoints. The `compare.py` gate correctly scores only
  these 4 core keys.
- The full raw `run.sh` outputs (`benchmarks/results/massless.md`,
  `benchmarks/results/bolt.md`) are gitignored; only this curated summary is tracked.
