# massless[django] vs massless[django-asyncio]

massless does not pin which Django backs it. Two mutually-exclusive extras select it
(both provide the `django` package, so install exactly one):

```console
pip install django-massless[django]          # stock Django
pip install django-massless[django-asyncio]  # the async-optimized Django fork
```

massless accelerates the **server + transport + thread** layer (Cython parse, no ASGI,
one shared thread-sensitive executor). It runs Django's middleware/ORM as-is, so it
cannot remove the per-middleware `sync_to_async` tax that stock Django's `MiddlewareMixin`
imposes on the async path (~65 us/middleware). The
[django-asyncio fork](https://github.com/oliverhaas/django-asyncio) rewrites the built-in
middleware and ORM as native-async (~10 us/middleware, no thread hop). The two are
complementary; combining them removes massless's one structural weakness.

## Benchmark

Same app (the fork's bench app), same server (massless), same Python (3.14), same load
(bombardier `-c 50 -d 8s`). Server pinned to one core (`taskset -c 0`), client on
cpu 4-12. Trivial async JSON view (`/healthz`), no DB. Only the installed Django differs.

| variant | empty middleware | full 7-middleware stack |
|---|--:|--:|
| `massless[django]` (stock 6.0.5) | 5,624 rps | **1,602 rps** |
| `massless[django-asyncio]` (fork 6.2) | **6,970 rps** | **4,609 rps** |
| delta | +24% | **+188% (2.9x)** |

Reference, same single-core setup:

| config | empty mw | full 7 mw |
|---|--:|--:|
| granian-RSGI + fork | 7,428 | 4,934 |
| granian-ASGI + fork | 6,045 | n/a |
| uvicorn + stock Django | 2,688 | n/a |

## Reading it

- On the **full middleware stack**, stock Django drags massless down to 1,602 rps: the
  7 `MiddlewareMixin` middlewares each cost ~65 us via `sync_to_async(thread_sensitive)`,
  ~407 us/req of pure tax. The fork's native-async middleware erases it, and massless
  jumps to 4,609 rps (217 us/req) without changing a line of massless.
- `massless[django-asyncio]` lands next to granian+fork (4,609 vs 4,934 full; 6,970 vs
  7,428 empty). Granian's slight edge is its Rust HTTP core + RSGI vs massless's Cython +
  the two thread-hops massless adds for fidelity (`request_started` + `close`). massless
  carries the py3.14 vs py3.12 advantage, so the gap is mostly server-core.
- The floor under all of these (the Django Python request lifecycle + the async event
  loop) is why none reach django-bolt's tier (Rust hot path, GIL-free, ~100k+ rps).

Caveats: single bombardier client, 8 s runs, single-core pinned; one run each (numbers
reproduce within a few percent). The fork is built from a dev branch; treat
`massless[django-asyncio]` as experimental.

## Full suite (under load, via the fork's harness)

The trivial view above only exercises framework + middleware. Running the fork's full
benchmark harness (`django-asyncio/benchmarks/run.py`, with a massless backend added)
against postgres + Toxiproxy, single-core, full 7-middleware stack, tells the rest:

| scenario | massless[django] | massless[django-asyncio] | granian-RSGI + fork |
|---|--:|--:|--:|
| io (50 ms sleep, c=100) | 916 | **1,795** | 1,791 |
| db (1-row, 1 ms latency, c=100) | 488 | **broken** | 1,667 |
| db_heavy (16-lookup prefetch, 5 ms, c=50) | 12.5 | **broken** | 39.8 |

Two findings, and the second corrects the headline above:

1. **Middleware/framework: the combination works.** On `io` (async view + full middleware
   under load) `massless[django-asyncio]` hits 1,795 rps, matching granian+fork (1,791) and
   nearly 2x `massless[django]` (916). The fork's native-async middleware removes the
   single-thread executor bottleneck that the stock `MiddlewareMixin` `sync_to_async` tax
   creates, and massless benefits fully.

2. **Async ORM: not yet compatible under concurrency.** On the DB scenarios
   `massless[django-asyncio]` *hangs* (8 / 4 rps; a single request is correct). The fork's
   native-async ORM opens connections on the event loop, but massless closes the response
   (and thus connections) via `sync_to_async(close)` on the executor thread, so async
   connections are not released, the pool exhausts, and concurrent requests stall.
   `massless[django]` is bottlenecked differently: the stock ORM's `sync_to_async` serializes
   all 100 concurrent queries onto the one shared executor thread (488 rps at 46% CPU, not
   CPU-bound), and db_heavy runs the 16 prefetch lookups sequentially there (12.5 rps).
   granian+fork captures the native-async-ORM win (1,667 / 39.8) because its handler manages
   the async connection lifecycle on the loop.

So `massless[django-asyncio]` is a clear win for framework/middleware-bound apps and a
regression for concurrent async-DB apps until massless learns to close async connections on
the event loop. For DB-heavy workloads today, `massless[django]` (slow but correct) is the
safe choice. Closing that gap (async-aware connection teardown in massless's dispatch) is
the prerequisite for the full "combine both" win.
