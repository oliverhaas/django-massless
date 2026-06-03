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
