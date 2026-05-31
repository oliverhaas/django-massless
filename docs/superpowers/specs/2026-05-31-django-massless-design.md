# django-massless: Design

**Status:** Draft for review
**Date:** 2026-05-31
**Package:** `django-massless` · **Import:** `massless` · **Framework name:** Massless

---

## 1. Summary

`django-massless` is a high-performance, Django-coupled API framework whose entire
request pipeline runs in **Cython/C over C-typed structures**. It defers
materialization of Python/Django objects until code actually reaches for them.

It is the same *architecture* as django-bolt (a C-native pipeline that only crosses
into Python at the user's handler), but with **Cython as the systems language instead
of Rust**.

### The thesis

The Rust/PyO3 approach pays an FFI boundary cost on every crossing into Python.
Cython has no such seam. It compiles to CPython C-API calls in the same binary, so:

1. Calling the user's view from the pipeline is a bare `PyObject_Call`, no marshaling.
2. The request object can be **backed by C storage while still being a real
   `django.http.HttpRequest` subclass**, lazily filling its Django state only when
   touched.

The goal is to keep a simple request cycle entirely in C/Cython (`nogil` where
possible), and pay the "lift into Python/Django" cost exactly when, and if, a
request needs it.

### What this does NOT change

The Django ORM stays sync-driver-on-a-thread (`sync_to_async` / thread-pool), exactly
as in django-bolt and stock ASGI Django. Massless makes the *framework overhead*
near-free. DB-bound endpoints converge to normal Django ORM throughput. This is a
known, accepted ceiling.

---

## 2. Goals & non-goals

### Goals
- A real Django-coupled framework: real `HttpRequest` at the view, real Django ORM,
  settings, app autodiscovery, and the ability to run real Django middleware where needed.
- A request pipeline (parse, route, fast middleware, auth) that touches **no Python
  object** for endpoints that don't need Django state.
- Lazy, one-shot promotion to a full Django request on first access to Django state.
- Match or beat django-bolt RPS on framework-bound (non-DB) endpoints.

### Non-goals (v1, YAGNI)
- WebSockets, SSE, streaming responses.
- Response compression (gzip/brotli/zstd).
- Trivially-async micro-optimization (bolt's `coro.send(None)` bytecode trick).
- Free-threading (no-GIL) support. A later lever, not v1.

---

## 3. Architecture: component map

Legend: **[reuse]** existing library · **[build]** we write it.

| # | Component | Status | Notes |
|---|-----------|--------|-------|
| 1 | Event loop | **[reuse]** | uvloop (Cython over libuv). |
| 2 | HTTP parser | **[reuse]** | httptools (Cython bindings to `llhttp`). Handles HTTP/1.1 state, keep-alive, chunked. |
| 3 | Connection/protocol layer | **[build]** | Cython `asyncio.Protocol` feeding bytes to httptools. Backpressure, pipelining. |
| 4 | Multi-process acceptor | **[build]** | `SO_REUSEPORT` across processes (bolt-shaped). |
| 5 | `MasslessRequest` | **[build]** | Regular `HttpRequest` subclass wrapping a `cdef RequestCore` (a cdef class cannot subclass a pure-Python class). C storage plus lazy promotion. **Keystone.** |
| 6 | Router | **[build]** | Radix/trie on path bytes, static-vs-dynamic split, `nogil`. |
| 7 | Middleware chain (tiered) | **[build]** | Fast cdef tier plus bridge to real Django middleware. |
| 8 | Auth | **[build]** | JWT/HMAC/API-key on raw bytes via bound C crypto (OpenSSL/libsodium), `nogil`. |
| 9 | Request body parsing | **[build]**/**[reuse]** | JSON (msgspec/orjson or C lib) plus multipart/form parser. |
| 10 | Response serialization | **[reuse]** | msgspec/orjson for view objects. C fast-paths for bytes/str. |
| 11 | Response object + builder | **[build]** | C-buildable fast path, or materialized from a Django `HttpResponse`. |
| 12 | View dispatch / concurrency | **[build]** | async on uvloop. sync goes to a thread-pool executor. |
| 13 | App API + registration | **[build]** | `@api.get` decorators, startup route table, compiled C router. |
| 14 | Django glue | **[build thin]** | settings bootstrap, middleware bridge, user-model loading, WSGI/ASGI fall-through mount. |
| 15 | Error handling | **[build]** | exception to response on both fast and Django paths. |
| 16 | Lifecycle | **[build]** | startup/shutdown/lifespan/signals/worker management. |

---

## 4. Keystone: `MasslessRequest` and the promotion latch

### Mechanism (Approach A: subclass plus `__getattr__` interception)

`MasslessRequest` is a **regular Python class** that subclasses **`WSGIRequest`**,
backed by a held `cdef class RequestCore` that owns the C storage. It cannot itself be
a `cdef class`: a Cython extension type cannot inherit from a pure-Python class
(verified: `First base of 'MasslessRequest' is not an extension type`). The base is
`WSGIRequest`, not `HttpRequest`, because `GET`/`POST`/`COOKIES`/`FILES` are
descriptors defined on `WSGIRequest` (not `HttpRequest`); `isinstance(req, HttpRequest)`
still holds since `WSGIRequest` subclasses it. Composition keeps every property
Approach A needs (`isinstance`, lazy `__getattr__` promotion, C-speed storage) while
compiling cleanly. (As built in Phase 2; see the Phase 2 design doc.)

```python
cdef class RequestCore:           # C storage, nogil-fillable during parse/route
    cdef bytes _method, _path, _query, _body
    cdef object _headers          # header list
    # fast-path surface exposed as Cython properties / cpdef:
    #   method, path, get_header(b'...'), query_param(...)  -- served from C, never promotes

class MasslessRequest(WSGIRequest):   # regular Python subclass; isinstance(HttpRequest) holds
    # Built at view dispatch, wrapping a RequestCore. Does NOT call __init__, so
    # Django-machinery attrs are absent until promotion.
    def __init__(self, core, path_params):
        self._core = core; self.path_params = path_params
        self.method = core.method; self.path = core.path   # plain attrs (fast path)
        self._is_django = False                            # the one-way latch

    def _promote(self):
        self._is_django = True                             # latch first (re-entrancy safe)
        WSGIRequest.__init__(self, self._build_wsgi_environ())  # Django reconstructs META/GET/POST/body/...

    def __getattr__(self, name):   # only on a normal-lookup MISS (plain attrs: META, user, ...)
        if name.startswith("_") or self.__dict__.get("_is_django"):
            raise AttributeError(name)
        self._promote()
        return object.__getattribute__(self, name)

    # Django attrs that are properties/methods on the class bypass __getattr__, so a
    # bounded set is overridden to promote-first then delegate: body, headers, encoding,
    # scheme, get_host, get_port, is_secure, build_absolute_uri, read/readline/__iter__,
    # and GET/POST/COOKIES/FILES (GET/COOKIES also get deleters for the encoding-set path).
```

### Why it works
- We **do not call `HttpRequest.__init__`** at construction, so Django's machinery
  attributes (`GET`, `POST`, `FILES`, `body`, `META`, `COOKIES`, `user`, `session`,
  `encoding`) are *absent*. `__getattr__` fires only on the first miss, then promotes.
- `isinstance(request, HttpRequest)` passes (the wrapper subclasses it), so Django views
  and middleware accept the object unmodified.
- **Fast-path attrs never promote.** `method`, `path`, path params, and `get_header()`
  are served from the `RequestCore` C fields. Ported Cython middleware use only this C API,
  so they stay `nogil` and never trip the latch. Only Django-land code touching `.META`/`.GET`/`.user`
  promotes.
- Promotion is **lazy, one-shot, all-at-once.** After `_promote()`, the real attributes
  exist, so `__getattr__` no longer fires for them.
- Entering the bridge-tier (real Django) middleware **promotes explicitly**, because
  those middlewares will touch the request anyway.
- After promotion, **Django is the source of truth** through to response serialization.

### Promotion triggers
1. First access to a Django-machinery attribute via `__getattr__` (typically in a view).
2. Explicit promote on entry to the bridge middleware tier.

### Primary risk (acknowledged)
A deliberately half-initialized `HttpRequest` subclass is delicate. `_promote()` must
reconstruct the invariants Django consumers expect (`META` populated WSGI-style,
`GET`/`POST` as `QueryDict`s, `content_type`/`encoding`, `_read_started`, and so on).
That is effectively a hand-rolled `HttpRequest.__init__` fed from C buffers.
Completeness and correctness here, plus drift across Django versions, is the single
biggest correctness task in the project.

### Rejected alternative (Approach B)
Two objects, decide at view entry: build a plain fast request, materialize a real
`HttpRequest` *before* the view if the route is flagged Django-needing. Simpler, but
lazy-at-*entry* not lazy-at-*access*. A view that only conditionally touches Django state
always pays. Rejected for losing the core optimization.

---

## 5. Tiered middleware chain

```python
cdef class Middleware:
    cdef object before(self, MasslessRequest req)   # None, or a Response to short-circuit
    cdef object after(self, MasslessRequest req, resp)
```

- **Fast tier:** CORS, rate-limit, JWT/API-key auth. Ordered C array, operating on the C
  header API only, no promotion. Pure-C work runs `nogil`. Short-circuits (preflight `204`,
  `429`, `401`) are built in C and returned without entering Python-land. `after()` hooks add
  response headers (e.g. CORS) on the way out.
- **Bridge tier:** CSRF, sessions, messages, third-party. Runs only when a route is
  configured for it. Entering it promotes the request, then wraps Django's real
  `get_response` chain via a `django_adapter`-style shim. Django response is source of truth
  from here.
- **Registration:** per route, an ordered fast-tier array plus a flag/handle for whether the
  bridge tier runs. Compiled at startup.

---

## 6. Dispatch & concurrency

- One **uvloop per process**. Multi-process via **`SO_REUSEPORT`**.
- View dispatch decided at registration via `inspect.iscoroutinefunction`:
  - **async view:** awaited on uvloop. Async ORM is `sync_to_async`-on-a-thread (unchanged).
  - **sync view:** run in a **thread-pool executor** (blocking ORM safe there).
- **Response serialization:**
  - view returns `dict`/`list`: msgspec/orjson (C, GIL-held, fast).
  - view returns `bytes`/`str`: C fast-path.
  - view returns Django `HttpResponse` (post-promotion): serialize from
    `.content` / `.status_code` / `.headers`.

---

## 7. Data flow

```
TCP (SO_REUSEPORT)
  -> uvloop accept
  -> Cython Protocol  -- feeds bytes --> httptools (llhttp) parse
  -> MasslessRequest built on C buffers          [no Python objects]
  -> C router match (static O(1) / radix)         [nogil]
  -> fast-tier middleware (CORS / rate-limit / auth) on C header API   [nogil, may short-circuit]
  -> [route uses bridge tier?] -- yes --> PROMOTE --> real Django middleware --> view
                              \- no --> view(MasslessRequest)
        view touches Django state? -- yes --> PROMOTE (one-shot, __getattr__)
  -> view returns dict/bytes/str  -> C / msgspec fast serialize
     view returns HttpResponse    -> serialize from Django response
  -> C response builder (status, headers, cookies)
  -> write to socket
```

---

## 8. Error handling

- Fast path: exceptions in the C pipeline map to HTTP responses built in C
  (`400`/`401`/`404`/`429`/`500`) without promotion where possible.
- Django path: post-promotion exceptions flow through Django's normal handling within the
  bridge shim.
- Every error path produces a response or logs and re-raises. No error is dropped.

---

## 9. Testing strategy

- **TDD throughout** (red-green-refactor).
- **Correctness parity:** a `MasslessRequest` after `_promote()` must be behaviorally
  indistinguishable from a stock `HttpRequest` for the supported surface. Property-based
  tests compare attribute-by-attribute against a real request built from the same raw bytes.
- **No-promotion assertions:** tests that assert the fast path never promotes (e.g. a probe
  that fails the test if `_is_django` flips) for endpoints that shouldn't need Django.
- **Benchmark gate:** RPS comparison vs django-bolt on framework-bound endpoints. Regressions
  are failures. The harness lives in [`benchmarks/`](../../../benchmarks/): `run.sh` drives a
  running server through the case matrix in [`benchmarks/cases.md`](../../../benchmarks/cases.md)
  (ported from django-bolt), and `compare.py` enforces the gate. The matrix tags each case with
  whether it is expected to promote, so the no-promotion assertions and the benchmark share one
  source of truth. Benchmarking starts in Phase 1; until the slice exists, the same harness
  captures a django-bolt baseline.
- Integration tests through the real server (httptools plus uvloop), not mocks.

---

## 10. Phased build

This framework is too large for one implementation plan. Each phase gets its own plan.

- **Phase 1: Thin end-to-end slice (proves the thesis).**
  httptools Protocol, C router, `MasslessRequest` (fast path only, *no promotion*),
  native view returning JSON, C response builder. No middleware, no Django promotion.
  Benchmark vs django-bolt via the `benchmarks/` harness, implementing the framework-bound
  endpoint contract in `benchmarks/cases.md`. *Exit criterion: a request cycle that touches no
  Python object except the view, at competitive RPS.*
- **Phase 2: Promotion plus Django glue.** `_promote()`, the `HttpRequest` subclass invariants,
  settings bootstrap, ORM access, user-model loading. Correctness-parity test suite.
- **Phase 3: Middleware tiers.** Fast cdef tier (CORS/rate-limit/auth) plus bridge shim for real
  Django middleware.
- **Phase 4: Dispatch hardening plus lifecycle.** sync/async dispatch refinement, thread-pool
  tuning, error handling, lifespan/signals, multi-process management, management command.

---

## 11. Risks & open questions

- **Half-initialized `HttpRequest` subclass correctness** (Phase 2): highest risk. Mitigated
  by the parity test suite and pinning supported Django versions.
- **Django version drift:** `_promote()` mirrors `HttpRequest` internals. Needs a version
  compatibility matrix and CI against each supported Django.
- **`nogil` discipline:** no Python containers/exceptions in `nogil` sections. Lean on
  `libcpp` (`std::string`, `unordered_map`). Easy to violate by accident.
- **Memory safety:** C/C++ undefined-behavior territory (no borrow checker). Buffer lifetimes
  (request body outliving the parse callback) need care.
- **httptools coverage:** confirm it handles the HTTP/1.1 edge cases we need. Fall back to
  picohttpparser only if a benchmark proves it matters.
- **ORM ceiling:** unchanged from django-bolt. Documented, not solved.

### Future (post-v1)
Free-threading (no-GIL CPython) as the path to multi-core without separate processes.
WebSockets. Streaming/SSE. Compression.
