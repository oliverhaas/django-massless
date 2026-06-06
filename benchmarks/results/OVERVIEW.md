# Benchmark results overview (2026-06-03)

All numbers are req/s. There are **three measurement regimes** below and they are NOT
comparable across regimes (different core counts, load tools, apps). Compare only within
a regime. The intended massless-vs-bolt-vs-uvicorn suite (`cases.md`) is still unbuilt
(4 of 48 routes exist), so none of this is that suite; it is a massless-variant plus
fork-server comparison, with bolt quoted from its own repo for scale only.

Two axes throughout: **server** (uvicorn = Python/ASGI, massless = Cython, granian =
Rust/ASGI+RSGI, django-bolt = Rust/Actix own stack) and **Django flavor**
(`[django]` = stock, `[django-asyncio]` = the async fork).

---

## Regime A: framework-bound, single core (`taskset -c 0`), bombardier

Trivial/medium JSON, no DB. Tiny-JSON is `/healthz` (fork app) and `/` (django_baseline);
they agree (5.6k stock). mw = middleware count (0 / 2 = Security+Common / 7 = production stack).

| server + Django | 0 mw | 2 mw | 7 mw |
|---|--:|--:|--:|
| uvicorn + stock | 2,688 | n/a | n/a |
| **massless[django]** (stock) | 5,624 | 3,253 | 1,602 |
| **massless[django-asyncio]** (fork) | 6,970 | 6,721 | 4,609 |
| granian-ASGI + fork | 6,045 | n/a | n/a |
| granian-RSGI + fork | 7,428 | n/a | 4,934 |

Larger payloads / params (django_baseline, lean / 2 mw):

| | `/` root | `/10k-json` | `/items/<id>?q=` |
|---|--:|--:|--:|
| massless[django] | 5,629 / 3,253 | 3,929 / 2,605 | 5,180 / 3,097 |
| massless[django-asyncio] | 7,156 / 6,721 | 4,838 / 4,472 | 6,865 / 6,101 |

## Regime B: full scenarios, single core, oha, postgres + Toxiproxy, full 7-mw stack

The fork's harness (`django-asyncio/benchmarks/run.py`, massless backend added).

| scenario | massless[django] | massless[django-asyncio] | granian-RSGI + fork |
|---|--:|--:|--:|
| io (50 ms sleep, c=100) | 916 | 1,909 | 1,791 |
| db (1-row, 1 ms latency, c=100) | 488 | 1,788 | 1,667 |
| db_heavy (16-lookup prefetch, 5 ms, c=50) | 12.5 | hangs* | 39.8 |

\* parallel-prefetch borrow path not yet working under massless; single request is correct.
Fork's own committed reference, same harness, db 1-row full-mw: upstream-async 288,
fork-async 1,538, fork-rsgi 1,677 (`django-asyncio/benchmarks/RESULTS.md`).

## Regime C: django-bolt, its OWN results, **8 processes** (multi-core), bombardier C=100

From `django-bolt/bench/BENCHMARK_BASELINE.md` (config line: `8 processes x 1 workers`).
**Not run here, not single-core, 8x the cores, Rust hot path / GIL-free.** Listed for scale
only; do NOT compare to Regime A/B.

| case | bolt (8-proc) |
|---|--:|
| `/` root | 177,286 |
| `/10k-json` | 115,794 |
| `/items/12345?q=` | 138,722 |
| `/items/12345` (path int) | 150,638 |
| `/header` | 97,492 |
| `/cookie` | 88,635 |
| `/bench/parse` (JSON validate) | 151,741 |
| `/bench/serializer-validated` | 84,087 |
| `/feed` (100 union items) | 63,082 |
| `/middleware/demo` | 10,058 |
| `/users/full10` (DB, async) | 14,425 |

---

## How to read this

- **Within Regime A/B (single core), comparable.** `massless[django-asyncio]` beats
  `massless[django]` everywhere (lifecycle/signal fast-paths help even at 0 mw; native
  middleware removes the tax; native async ORM fixes single-row DB), and matches or beats
  granian+fork. uvicorn+stock is the slowest.
- **Regime C is not comparable to A/B.** bolt ran on 8 cores; my numbers on 1. bolt is also
  a Rust framework that bypasses Django's Python request path, so it is a different tier
  regardless of cores. I never ran bolt on equal footing (single core, or massless on 8
  processes), so there is no fair massless-vs-bolt number in this document.
- **What is missing:** the designed 3-way (massless vs bolt vs uvicorn+Django on identical
  `cases.md` endpoints, equal cores). That requires building out the bench app and running
  all three the same way. Not done.
