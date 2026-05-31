# django-massless Phase 1: Thin end-to-end slice

**Status:** Approved for implementation planning
**Date:** 2026-05-31
**Parent design:** [2026-05-31-django-massless-design.md](2026-05-31-django-massless-design.md) (§10 Phase 1)

---

## 1. Goal and exit criterion

Build the smallest server that proves the core thesis: a request cycle that runs
in Cython/C and crosses into Python only at the user's view.

A request flows TCP → uvloop → Cython protocol → httptools parse → C router →
`MasslessRequest` (fast path, no promotion) → async view → C/msgspec response →
socket, touching no Python object except the view.

**Exit criterion:** the slice serves the framework-bound benchmark endpoints at
RPS competitive with single-process django-bolt, and a test asserts the request
never promotes (`_is_django` never flips) on those endpoints.

## 2. Decisions

These were settled during brainstorming and scope this phase:

1. **Single process.** No `SO_REUSEPORT` multi-process acceptor in Phase 1 (that
   is Phase 4). The benchmark compares single-process massless against
   single-process django-bolt, which isolates per-request framework overhead, the
   thing the thesis is about.
2. **msgspec** for serialization. Matches django-bolt (its bench app uses
   `msgspec.Struct`) and covers later phases (request models, response models,
   union dispatch) without a second dependency.
3. **Minimal, radix-ready router.** Static routes in a C hash map (O(1)) plus a
   simple dynamic-segment matcher for one int path param. At this route count a
   hash map is faster than a radix trie. Full radix is a later-phase enhancement
   for large route tables.
4. **Async-only views.** Async views are awaited on uvloop. Sync thread-pool
   dispatch arrives with the Phase 4 dispatch hardening.
5. **Standalone app and runner.** A `MasslessAPI` object with decorators, launched
   via `python -m massless module:api`. No Django settings bootstrap or management
   command yet (Phase 2).
6. **Minimal signature-based param binding** (approved micro-decision). At
   registration the view signature is inspected to build a per-route binder: path
   params coerced by annotation (`int` to int), query params as `str` or
   `str | None`. This makes the bench endpoints work as written and seeds the
   eventual binding API.
7. **Trim `compare.py` core keys to the Phase 1 subset** (approved micro-decision).
   The gate uses the 4 framework-bound, no-body, async core endpoints reachable in
   Phase 1; the remaining core keys are restored as later phases add sync, body,
   and header support. This is documented in `compare.py`.

It was verified that `MasslessRequest` can subclass `django.http.HttpRequest` and
serve fast-path attributes without `settings.configure()`, that `isinstance`
passes, and that touching a Django-machinery attribute (`.GET`) raises
`AttributeError` before promotion. Phase 1 relies on all three.

## 3. Module layout

```
src/massless/
  __init__.py        # public API re-exports (MasslessAPI)
  app.py             # MasslessAPI: @api.get, route-table compile at startup
  __main__.py        # python -m massless module:api --host --port
  _protocol.pyx      # asyncio.Protocol on uvloop, feeds bytes to httptools
  _router.pyx        # static C hash map + dynamic int-param matcher (nogil)
  _request.pyx       # cdef RequestCore (C storage) + MasslessRequest(HttpRequest) wrapper
  _response.pyx      # C response builder; msgspec/bytes/str body paths
  _router.pxd        # cimport surface for the router (MatchResult, match_c)
  _request.pxd       # cimport surface for RequestCore (used by the protocol)
```

In Phase 1 the protocol calls the response builder through a plain Python import of its
`cpdef` functions (still compiled, one call per request). A `_response.pxd` cimport
surface for a zero-overhead C-level call is a later-phase optimization, so it is not
created here.

Each `.pyx` is a small, well-bounded unit with one purpose, testable on its own.
`app.py` and `__main__.py` are pure Python; they run only on the cold path
(registration and startup).

## 4. Data flow (Phase 1)

```
TCP accept (uvloop)
  -> _protocol.pyx feeds bytes to httptools (llhttp)
  -> httptools callbacks fill a RequestCore's C fields           [no Python objects]
     (method, path, query bytes, header map)
  -> _router.pyx matches path bytes, captures int param          [GIL-held in P1; nogil later]
  -> at dispatch: wrap RequestCore in a MasslessRequest          [the one Python object]
  -> per-route binder builds view kwargs (path int + query str)
  -> await async view(**kwargs)                                  [the one Python crossing]
  -> view returns dict/list  -> msgspec.json.encode
                  bytes/str   -> direct
  -> _response.pyx writes status line + headers + body, keep-alive
  -> write to socket
```

## 5. Components

### 5.1 `_protocol.pyx`
A Cython `asyncio.Protocol` running on uvloop. Owns an httptools `HttpRequestParser`
per connection, feeds received bytes to it, and drives the request lifecycle on the
parser callbacks (`on_url`, `on_header`, `on_body`, `on_message_complete`). Handles
HTTP/1.1 keep-alive. Backpressure and pipelining are handled minimally (correct, not
yet tuned). On message complete it schedules the matched view and, when the result
is ready, hands it to `_response.pyx` and writes to the transport.

### 5.2 `_router.pyx`
Compiles the registered routes at startup into:
- a static table: exact path bytes to route handle, backed by a `libcpp`
  `unordered_map` for O(1) lookup,
- a small dynamic table: routes with one int segment (e.g. `/items/{item_id}`),
  matched by splitting on the captured segment and coercing to int.

Lookup returns a route handle plus the captured int param (if any). A miss returns a
sentinel that the protocol turns into a 404. In Phase 1 the match holds the GIL (the
`bytes`-to-`std::string` conversion and the dynamic scan are GIL-bound); that is
acceptable because dispatch holds the GIL anyway and the map lookup is already
C-speed at this route count. A true `nogil` match over a C buffer is the eventual
target (parent design §3) and a later-phase optimization.

### 5.3 `_request.pyx`
Two coupled units. A `cdef class` cannot inherit from `HttpRequest` (a pure-Python
class), so the C storage and the `HttpRequest` subclass are separated:

- **`cdef class RequestCore`**: owns the C fields (method, path, raw query bytes, body
  bytes, header map). Filled by the protocol during parse, potentially `nogil` for the
  pure-byte work. Exposes the fast-path surface as Cython properties / `cpdef` methods:
  `method`, `path`, query access (parsed from raw query bytes on demand), and
  `get_header(name)`. Private `cdef` fields are invisible to Python, so the surface must
  go through these accessors.
- **`class MasslessRequest(HttpRequest)`**: a regular Python class, materialized only at
  view dispatch, wrapping a `RequestCore` plus the router-captured `path_params`. Its
  fast-path attributes delegate to the core. It does NOT call `HttpRequest.__init__`, so
  Django-machinery attributes are absent.

No `__getattr__` or promotion in Phase 1. Touching a Django-machinery attribute raises
`AttributeError`, which is the behavior the no-promotion test asserts. (The separation
and these three behaviors were verified against Cython 3.2.5 and Django 6.0.)

### 5.4 View and param binding
At registration the view signature is inspected once to build a per-route binder.
The binder maps:
- path params to positional/keyword args, coercing by annotation (`int` to int; a
  segment that fails int coercion is treated as no match and returns 404),
- query params to `str` or `str | None` (missing optional becomes `None`; no
  coercion failure is possible for these shapes).

The binder calls the async view with the bound kwargs. Phase 1 supports only the
parameter shapes the bench endpoints use (int path param, optional str query).

### 5.5 `_response.pyx`
A C response builder. Inputs: status code, headers, body. Three body paths:
- `dict`/`list` to JSON via `msgspec.json.encode`,
- `bytes` passed through,
- `str` encoded as UTF-8.

It sets `Content-Length` and infers `Content-Type` from the body path: `dict`/`list`
to `application/json`, `str` to `text/plain; charset=utf-8`, `bytes` to
`application/octet-stream`. It emits a keep-alive HTTP/1.1 response. (View-set
content types arrive with response objects in a later phase.)

### 5.6 `app.py` and `__main__.py`
`MasslessAPI` exposes an `@api.get(path)` decorator that records routes and view
signatures (POST arrives with body parsing in a later phase). At startup the route table is compiled into the C
router. `__main__.py` parses `module:api --host --port`, imports the app, starts a
uvloop loop, and serves until interrupted.

## 6. Benchmark bench-app and gate

`benchmarks/app.py` implements the framework-bound, no-DB, async, no-body subset of
[`benchmarks/cases.md`](../../../benchmarks/cases.md):

| Case | Path |
|------|------|
| Root JSON Async | `/` |
| 10kb JSON Async | `/10k-json` |
| Path Param int | `/items/12345` |
| Path + Query | `/items/12345?q=hello` |

These are 4 of `compare.py`'s 7 core keys; the other 3 (header, cookie, JSON
parse) need header access or body parsing that Phase 1 does not have.
`compare.py`'s `CORE_KEYS` is trimmed to these 4 for now, with a comment listing
the keys to restore as later phases land sync, header, and body support.

Workflow: start massless via `python -m massless benchmarks.app:api`, start
single-process django-bolt, run `benchmarks/run.sh` against each, then
`benchmarks/compare.py bolt.md massless.md`.

## 7. Testing strategy

TDD, red-green per unit:
- **Router:** static hit, dynamic hit with int coercion, miss, and a bad int
  segment.
- **MasslessRequest:** each fast-path attribute returns the C-backed value;
  touching a Django attribute raises `AttributeError`.
- **Response:** correct bytes for `dict`, `bytes`, and `str`, including
  `Content-Length` and `Content-Type`.
- **Binder:** path/query binding and coercion for the supported shapes.
- **Integration:** drive the real httptools + uvloop server over real sockets (not
  mocks) for each bench endpoint, asserting status, headers, and body.
- **No-promotion assertion:** a probe that fails if `_is_django` flips while
  serving any bench endpoint.

Correctness parity against a real `HttpRequest` is a Phase 2 concern (it depends on
promotion), so it is out of scope here.

## 8. Dependencies

Add runtime dependencies: `uvloop`, `httptools`, `msgspec`. No new dev
dependencies beyond `cython`, which is already present.

## 9. Out of scope for Phase 1

Promotion and `__getattr__`; Django settings, ORM, and middleware; sync views;
multipart and body parsing; auth; multi-process; response models and unions; error
handling beyond a basic 404 and 500.

## 10. Risks and notes

- **httptools edge cases.** Confirm httptools handles the HTTP/1.1 keep-alive and
  request shapes the bench needs. Fall back only if a benchmark proves it matters.
- **nogil discipline.** No Python containers or exceptions inside `nogil` sections;
  lean on `libcpp` for the static map. Easy to violate by accident.
- **Buffer lifetimes.** The request body and header bytes must outlive the parse
  callbacks; ownership lives in `MasslessRequest`'s C fields.
- **Editable rebuilds.** setuptools editable installs do not auto-rebuild on `.pyx`
  changes; `uv sync` (or `uv pip install -e .`) is required after editing Cython
  sources before tests or benchmarks run.
