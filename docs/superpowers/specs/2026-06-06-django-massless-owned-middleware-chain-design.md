# Design Doc: massless-owned middleware chain + `get_response_async`

Status: Approved direction (2026-06-06). Supersedes the 2026-06-01 "reuse Django's chain" decision.
Author: lead architect, django-massless.

### Implementation status (2026-06-06)

Built and shipped (205 tests + the chain differential green on stock Django 6.0.5, and the
chain/response differential green against the django-asyncio fork via PYTHONPATH):

- **Phase 1 — owned chain.** `src/massless/_chain.py` (`MasslessChain`): faithful re-housing
  of `load_middleware` + `get_response_async` + `_get_response_async`, all-delegation. Wired
  into `handler.handle()`. Pure Python (not `.pyx`; see §2.1). Differential vs `get_response_async`
  in `tests/test_chain.py`.
- **§2.4 — lazy responses.** `responses.py` rewritten: `JsonResponse`/`HttpResponse` are real
  `HttpResponse` subclasses with a lazy msgspec body; they flow through any middleware. The
  protocol's fast-serialize branch reads `.headers`/`.cookies`. Tests in `tests/test_fast_responses.py`.
- **Fast re-implementations.** `src/massless/_middleware.py`: `XFrameFast`, `SecurityFast`,
  `ConditionalGetFast`, `CommonFast`, `GZipFast` + `REGISTRY`, substituted in the chain's build
  loop. Each byte-identical to the real middleware (the `REAL_STACK` differential validates all
  five at once; GZip via decompress-compare). Measured **5.6x on the middleware path on stock
  Django** (15.2k vs 2.7k req/s in-process; removes `MiddlewareMixin`'s `sync_to_async` thread
  hops), **~parity (1.04x) on the fork** (its builtins are already native-async).
- **Cleanup.** Removed the now-dead `_pool_teardown` / `_next_item` from `_protocol.pyx`.

Deferred:

- **Phase 2 inline fast-tier for all-fast stacks.** The empty-stack hot path (42.7k) is untouched
  and still served by the inlined `dispatch` fast path. An inline tier that also runs FastLayers
  would only shave the chain's per-layer coroutine frames; marginal (the fork shows the chain is
  not the bottleneck) and it touches the hot path, so it waits on a full bombardier-with-middleware
  benchmark to justify the risk.
**Benchmarked (single-core, root, realistic 7-middleware stack `BENCH_FULL_MIDDLEWARE=1`):**
uvicorn+django (stock) 942 rps; massless (stock) FastLayers off 1657 / on 2182 (+32%, 2.3x
uvicorn+django); massless (fork) off 5758 / on 5885 (~neutral, 6.2x uvicorn+django). Honest
read: the in-process 5.6x was the three substitutable middleware in isolation; on the full
stack the four *delegated* middleware (Session/CSRF/Auth/Messages) dominate, so FastLayers add
only +32% on stock, and the full-stack lever is the fork (native-async Session/Auth/CSRF/Messages).
bolt (41k root) runs no Django middleware, so it is not comparable to a full-Django-stack run;
massless still beats bolt on the unchanged no-middleware fast tier (42.7k). A `MASSLESS_FAST_MIDDLEWARE=0`
escape hatch was added (default on).

---

## 1. Summary + override of the 2026-06-01 decision

massless is a drop-in C server + handler for **unmodified** Django. Today it inherits Django's `BaseHandler` and reuses `BaseHandler.get_response_async` / `load_middleware` (`handler.py:64`, `:218`), with a `_fast_dispatch` bypass that fires only when `not settings.MIDDLEWARE` (`handler.py:95-99`). We already beat django-bolt on that no-middleware fast tier (MEMORY: "BEATS bolt", fast-tier root 42.7k > bolt 41.1k single-core). This doc proposes that massless **own its middleware chain and its own `get_response_async` equivalent**, accepting normal Django middleware classes, shipping fast re-implementations of the cheap header/redirect ones, and reading the same Django settings — true drop-in.

**Honest override.** The 2026-06-01 doc explicitly rejected owning the chain ("Approach C, too invasive") and chose to reuse Django's. That was the right call *then*: the win was removing async overhead on the empty-stack path, and the fast path covered the benchmark. It is wrong *now* for one measured reason: the middleware tax is the production bottleneck (MEMORY: "massless's middleware tax is its weakness"), and the static gate `not settings.MIDDLEWARE` means the fast path **almost never fires against a real app** — every production Django project ships `SecurityMiddleware`, `CommonMiddleware`, `SessionMiddleware`, `CsrfViewMiddleware`, `AuthenticationMiddleware`, etc. So today, real apps fall entirely to stock `get_response_async` and lose the lead. Owning the chain exists *precisely to lift the `not settings.MIDDLEWARE` constraint* (Report 4 §3): run a fast chain even *with* middleware by re-implementing the cheap known ones on the un-promoted request and wrapping the rest faithfully. The invasiveness the prior doc feared is contained by Phase 1 below: a chain that delegates **everything** to real Django middleware and is proven byte-identical before any substitution.

---

## 2. Architecture: the massless-owned chain

### 2.1 Where it lives

**Implemented as pure-Python `src/massless/_chain.py`** (Phase 1, done). The design first proposed `_chain.pyx`, but the measured lesson "cythonizing the pipeline regresses it" applies here too: what matters is *flatness* (few awaits), not the file extension, and the middleware path carries middleware cost regardless. The Cython stays where it pays (parse/serialize in `_protocol`). `run()` is a flat coroutine that mirrors `get_response_async`; the chain leans on the handler for `adapt_method_mode`/`make_view_atomic`/`check_response`/`resolve_request` (the last is already router-backed) and reimplements only the build loop, `run`, `_run_view`, and `_process_exception_by_middleware`. It honors both the fork's native `aprocess_*` hooks and stock's `process_*` (adapted), so it is drop-in for either Django; the differential suite runs on the installed stock Django 6.0.5, and a fork-venv differential (exercising the `aprocess_*` branches) is a pending gate.

### 2.2 Object model

- **`MasslessChain`** — built once in `MasslessHandler.__init__`, replacing the `load_middleware(is_async=True)` call (`handler.py:64`). It reads `settings.MIDDLEWARE` *exactly* as Django does: iterate `reversed(settings.MIDDLEWARE)` and `import_string` each entry (mirrors `base.py:40`, `:42`). For each dotted path it consults the substitution registry (§3):
  - **hit** → instantiate a `FastLayer` that operates on the un-promoted `MasslessRequest` (reads via `get_header`/`query_param` off the core, `_request.pyx:116-120`; sets `request.user`/`request.auth` per `_request.pyx:159-182`) without triggering promotion.
  - **miss** → build the *real* Django middleware instance and wrap it in a **`BridgeLayer`** using the exact same wrapping Django's `load_middleware` applies: `convert_exception_to_response` + `adapt_method_mode` (`base.py:96`, `:105`). The bridge accepts that the real middleware will promote the request the moment it reads `request.headers`/`COOKIES`/`user`.
- **`is_fast`** — the new meaning of `_fast_ok`. `True` iff every layer is a `FastLayer` **and** no DB alias has `ATOMIC_REQUESTS`. It is purely a property of the *request* path. It does **not** depend on the response object: `_Fast` responses are lazy `HttpResponse` subclasses (§2.4), so they flow safely through any layer (Fast or Bridge) regardless. This replaces the `handler.py:95-99` gate; `_fast_ok` is no longer "no middleware" but "the chain is fully fast-representable," asked of the chain object (`self._chain.is_fast`).
- **`run(request, handler)`** — the massless `get_response_async`. It performs the request-phase of each layer outer→inner, resolves the URL via the existing `Router.match` (`_router.pyx:131`), calls the extracted inner `_run_view`, then unwinds each layer's response-phase inner→outer, appends `request.close` to `response._resource_closers`, and logs 4xx/5xx (faithful to `base.py:164-172`). For any `BridgeLayer`, `run` delegates to the composed Django callable so behavior is identical to stock Django.

### 2.3 Request → response flow (replacing `get_response_async`)

```
                        per-connection loop  (_protocol.pyx:397-450, UNCHANGED)
                                   │
                                   ▼
                        dispatch() (_protocol.pyx:196-311)
            request_started (or skip per _pool_lifecycle, :234/:259-260)
                                   │
                                   ▼
                 ┌─────────────  MasslessChain.run(request, handler)  ──────────────┐
                 │                                                                   │
 request phase   │  Layer 0  (outermost = settings.MIDDLEWARE[0])                    │  response phase
   outer→inner   │     ├─ FastLayer.process_request / __call__ pre-code             │   inner→outer
                 │     ▼                                                             │   (reverse)
                 │  Layer 1 ...                                                      │
                 │     ▼                                                             │
                 │  [PROMOTION BOUNDARY: first BridgeLayer promotes MasslessRequest] │
                 │     ▼                                                             │
                 │  Layer N (innermost = settings.MIDDLEWARE[-1])                    │
                 │     ▼                                                             │
                 │  ┌──────────────  _run_view(request, match)  ─────────────────┐  │
                 │  │  Router.match (_router.pyx:131) → (cb,args,kwargs,route,    │  │
                 │  │       is_async)                                             │  │
                 │  │  request.resolver_match = _LazyResolverMatch(...)           │  │
                 │  │  _view_middleware loop (process_view, MIDDLEWARE order)     │  │
                 │  │  make_view_atomic (only if any ATOMIC_REQUESTS)             │  │
                 │  │  call view (await if is_async else sync_to_async TS)        │  │
                 │  │  check_response                                             │  │
                 │  │  deferred-render: _template_response_middleware + .render() │  │
                 │  │  exception → response_for_exception (convert_exc_to_resp)   │  │
                 │  └────────────────────────────────────────────────────────────┘  │
                 │                                                                   │
                 │  response._resource_closers.append(request.close)                 │
                 │  log_response if status >= 400                                     │
                 └───────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
            _Fast response branch (_protocol.pyx:266-273) + C serialize_body
                                   │
            teardown / request_finished (_protocol.pyx:293-310, gated by _pool_lifecycle)
```

The inner box (`_run_view`) is the shared "call view, check_response, render, exception-funnel, close, log" routine that today exists twice — `MasslessHandler._fast_dispatch` (`handler.py:174-200`) and its inlined twin (`_protocol.pyx:235-254`). It is extracted once and becomes the chain's innermost layer — the structural equivalent of Django's `_get_response_async` (`base.py:229`).

### 2.4 Fast responses are lazy `HttpResponse` subclasses

The opt-in fast responses (`massless.JsonResponse`, `massless.HttpResponse`) are rewritten so they are **real `HttpResponse` subclasses with a lazy, msgspec-backed body**. This is the response-side mirror of the lazy `MasslessRequest`: keep the full Django API, defer the *work*, never skip the *interface*.

The current `responses.py` `_Fast` is **not** an `HttpResponse` subclass (`responses.py:6-7`): it carries only a status, a private `_headers` dict, and a `_serialize`. Anything in the chain that reads or mutates the response through the standard API (`.content`, `.setdefault`, `patch_vary_headers`, `.streaming`) would break on it. Verified against the source: the response API middleware actually uses lives on `HttpResponseBase` (`django/http/response.py`: `__setitem__:204`, `__getitem__:210`, `has_header:213`, `set_cookie:225`, `setdefault:289`, `headers`/`cookies`/`_resource_closers` in `__init__:122`), while the eager `content` encoding lives on the concrete `HttpResponse` as a property (`:397`, `:416-420`). So the heavy part is exactly the part we can keep lazy.

Design:

```python
class JsonResponse(HttpResponse):
    def __init__(self, data, status=200):
        super().__init__(content=b"", content_type="application/json", status=status)
        self.data = data
        self._materialized = False

    @property                       # runs only if middleware/anything reads the body
    def content(self):
        if not self._materialized:
            self._container = [serialize_body(self.data)[0]]   # msgspec, once
            self._materialized = True
        return b"".join(self._container)

    def _serialize(self):           # the C fast path; never touches .content
        if not self._materialized:
            return serialize_body(self.data)      # msgspec direct at the C layer
        return b"".join(self._container), self._content_type_bytes
```

Two regimes, both correct:
- **Body untouched** (FastLayers only, or middleware that only sets headers): the C serializer calls `_serialize`, msgspec runs once at the C layer, `.content` never materializes. This is the current fast-tier speed, preserved (the JSON win was msgspec vs `json.dumps`, which lives here, not in avoiding the class).
- **Body read or rewritten** (`GZipMiddleware` reads `.content`, compresses, sets it back; `ConditionalGetMiddleware` hashes `.content` for the ETag): first access materializes via the same `serialize_body` bytes, then the object behaves exactly like a normal `HttpResponse`. The encode that middleware would have forced anyway just happens on first touch.

The cost is one `HttpResponseBase.__init__` per fast response (the `headers`/`cookies` setup the old `_Fast` skipped); the body encode stays deferred. This is the trade we accept to be genuinely drop-in: a `JsonResponse` is now safe through the full real middleware stack, which removes the response-side `is_fast` gate (§2.2) and the former Phase 8 gating (§7).

---

## 3. The substitution registry

The registry is a dict keyed by Django dotted path → `FastLayer` subclass. Crucially, copying bolt's model (Report 1 §2, §5): **bolt has NO substitution registry; it runs the real Django classes**. massless deliberately diverges here — we *do* substitute, but only the five middlewares Report 3 proved are "pure header/redirect logic reading scalar settings, no pluggable backend." Everything else delegates to the real class via `BridgeLayer`, exactly like bolt.

### 3.1 Fast re-implementations (Report 3 "worth a fast re-implementation")

| Django dotted path | Fast? | Why (Report 3) |
|---|---|---|
| `django.middleware.security.SecurityMiddleware` | **FAST** | trivial; redirect + 4 conditional headers; 9 settings cached at init |
| `django.middleware.clickjacking.XFrameOptionsMiddleware` | **FAST** | trivial; one header, one setting (`X_FRAME_OPTIONS`, default `"DENY"`, `.upper()` cached) |
| `django.middleware.gzip.GZipMiddleware` | **FAST** | trivial guards + CPU compression; no settings; natural C-speedup target for the gzip itself |
| `django.middleware.common.CommonMiddleware` | **FAST (hot path only)** | re-impl per-request `Content-Length` + `DISALLOWED_USER_AGENTS`/`PREPEND_WWW`; **delegate** the `is_valid_path` `APPEND_SLASH`/404-slash branch to Django's `django.urls.is_valid_path` |
| `django.middleware.http.ConditionalGetMiddleware` | **FAST** | small settings-free control flow; **reuse/port** Django's `set_response_etag`, `get_conditional_response`, `parse_http_date_safe`; ETag hashing is the speedup |

### 3.2 Always delegate to the real Django middleware (`BridgeLayer`)

| Django dotted path | Why delegate (Report 3) |
|---|---|
| `django.contrib.sessions.middleware.SessionMiddleware` | pluggable `SESSION_ENGINE` backend; cost is DB/cache I/O, not the middleware — re-impl buys nothing |
| `django.contrib.auth.middleware.AuthenticationMiddleware` (+ `LoginRequiredMiddleware`, `RemoteUserMiddleware`, `PersistentRemoteUserMiddleware`) | pluggable `AUTHENTICATION_BACKENDS` + `AUTH_USER_MODEL`; security-critical; lazy attach already nearly free |
| `django.contrib.messages.middleware.MessageMiddleware` | pluggable `MESSAGE_STORAGE`; backend-bound, no-op when unused |
| `django.middleware.csrf.CsrfViewMiddleware` | security-critical token crypto + trusted-origin/session edge cases; re-impl risks CSRF bypass |
| `django.middleware.locale.LocaleMiddleware` | deeply coupled to `django.utils.translation` negotiation/catalogs; if i18n off, omit it |
| **any third-party / unknown path** | run unchanged inside the chain (§4) |

> Note: `CommonMiddleware`'s companion `BrokenLinkEmailsMiddleware` is left to Django (Report 3: mail/404-only, not hot). It is not a registry key.

### 3.3 The `FastMiddleware` interface

A `FastLayer` is **not** a Django middleware factory — it operates directly on the massless request/response without `convert_exception_to_response` wrapping (it must not raise for known conditions; it returns or short-circuits). The interface mirrors the three Django phases the chain understands (request, view, response) so a layer can fill in only what it needs:

```python
# conceptual — implemented as a cdef class in _chain.pyx
class FastLayer:
    # Built once. Reads + caches the SAME settings the Django class reads in __init__.
    def __init__(self, settings): ...

    # Request phase. Return a response to short-circuit (skips view + inner layers),
    # or None to continue. Mirrors Django process_request / __call__ pre-code.
    async def process_request(self, request) -> "response | None": ...

    # View phase. Runs after Router.match, in MIDDLEWARE order, before the view.
    # Truthy return short-circuits the view (mirrors process_view, base.py:240-244).
    async def process_view(self, request, view_func, view_args, view_kwargs) -> "response | None": ...

    # Response phase. Mutates/returns the response. Runs inner→outer (reverse MIDDLEWARE order).
    async def process_response(self, request, response) -> response: ...
```

A layer that needs none of a phase leaves it unset; the chain skips it (no empty-loop tax — contrast Report 2 §4, where Django's empty `_view_middleware`/`_template_response_middleware` loops are pure overhead).

### 3.4 Byte-identical via the SAME settings

Each `FastLayer.__init__` reads and caches **exactly the settings keys the Django class reads in its own `__init__`**, so config is identical with zero new settings:

- **`SecurityFast`** caches: `SECURE_HSTS_SECONDS`, `SECURE_HSTS_INCLUDE_SUBDOMAINS`, `SECURE_HSTS_PRELOAD`, `SECURE_CONTENT_TYPE_NOSNIFF`, `SECURE_SSL_REDIRECT`, `SECURE_SSL_HOST`, `SECURE_REDIRECT_EXEMPT` (compiled to regex list at init, as Django does), `SECURE_REFERRER_POLICY`, `SECURE_CROSS_ORIGIN_OPENER_POLICY`. Emits `Strict-Transport-Security` (only if secs truthy AND `request.is_secure()` AND header absent), `X-Content-Type-Options` (`setdefault`), `Referrer-Policy` (`setdefault`), `Cross-Origin-Opener-Policy` (`setdefault`); request-side SSL redirect short-circuits with `HttpResponsePermanentRedirect`.
- **`XFrameFast`** caches `getattr(settings, "X_FRAME_OPTIONS", "DENY").upper()`. Sets `X-Frame-Options` only if not already set AND not `response.xframe_options_exempt`.
- **`GZipFast`** reads no settings (class attr `max_random_bytes = 100`). Guards: skip non-streaming `< 200` bytes, skip if `Content-Encoding` set, `patch_vary_headers(response, ("Accept-Encoding",))`, require `\bgzip\b` in `HTTP_ACCEPT_ENCODING`, weaken strong ETag to `W/"..."`, set `Content-Encoding: gzip`. To stay byte-identical, keep `compress_string` semantics (random-byte padding via `max_random_bytes`); the gzip itself drops to C/`zlib`.
- **`CommonFast`** caches `DISALLOWED_USER_AGENTS` (compiled), `PREPEND_WWW`, `APPEND_SLASH`, `DEBUG`. Hot path: `PermissionDenied` on disallowed UA, `PREPEND_WWW` redirect, response-side `Content-Length` set on non-streaming responses missing it. The `should_redirect_with_slash` branch (which calls `django.urls.is_valid_path` — URL resolution) is **delegated to Django's helper verbatim**, not re-implemented.
- **`ConditionalGetFast`** reads no settings. Bails on non-GET; `set_response_etag` if `needs_etag` and no ETag; reads `ETag`/`Last-Modified`; returns 304 via `get_conditional_response`. Reuses Django's `set_response_etag`, `get_conditional_response`, `parse_http_date_safe`, `cc_delim_re` rather than re-deriving RFC 9110 matching.

---

## 4. Fidelity contract (the #1 risk)

The chain must be **observationally identical to `_get_response_async`** for any middleware stack (Report 2). This is the highest risk, guaranteed by differential testing (§8) against the fork's real `get_response_async`. The exact semantics to preserve, from Report 2:

### 4.1 Build order
- Iterate `reversed(settings.MIDDLEWARE)` (`base.py:40`). The **last** entry is instantiated **first** and is **innermost** (closest to the view); the **first** entry is instantiated **last** and is **outermost** (closest to the client) — the canonical onion. For `[A, B, C]`: nesting is `A(B(C(_run_view)))`.

### 4.2 Hook ordering (the three lists, Report 2 §1.6)
- **`process_view` order = MIDDLEWARE order** (A, B, C). Django achieves this via `insert(0, ...)` over reversed iteration (`base.py:84`). Runs **inside `_run_view`**, after URL resolution, before the view. First truthy response breaks (`base.py:240-244`).
- **`process_template_response` order = reverse MIDDLEWARE order** (C, B, A). Django uses `append` (`base.py:86`). Runs only when `hasattr(response, "render") and callable(response.render)`. Each result passes `check_response` (the error name uses `middleware_method.__self__.__class__.__name__`, so hooks must stay bound methods).
- **`process_exception` order = reverse MIDDLEWARE order**, **always synchronous** (`adapt_method_mode(False, ...)`, `base.py:104`). Invoked only for exceptions from the **view call** or **template render**, via `sync_to_async(self.process_exception_by_middleware, thread_sensitive=True)`. First truthy wins; all-`None` re-raises to the per-layer `convert_exception_to_response`.

### 4.3 sync/async capability + adaptation (Report 2 §1.2-1.3, §1.8)
- Honor `sync_capable` (default `True`) / `async_capable` (default `False`); `RuntimeError` if both false.
- `middleware_is_async` depends on the **mode of the handler it wraps** (`handler_is_async`), not the global `is_async`.
- The `get_response` passed into a middleware's `__init__` is coerced to the **middleware's** mode (`adapt_method_mode`): sync mw wrapping async handler gets `async_to_sync`; async mw wrapping sync handler gets `sync_to_async(..., thread_sensitive=True)`.
- **Fork-specific** (must preserve): prefer native `aprocess_view` / `aprocess_template_response` over the sync hook when `is_async` (`base.py:83`, `:90`) to avoid a per-request `sync_to_async` wrap.

### 4.4 Construction edge cases
- `MiddlewareNotUsed` → skip the instance entirely; **handler unchanged** (the adapted handler is discarded), DEBUG-log (`base.py:64-72`).
- Factory returning `None` → `ImproperlyConfigured` (`base.py:74-77`).

### 4.5 Inner `_run_view` load-bearing pieces (must NOT be skipped — Report 2 §4)
- `resolve_request` semantics: set `request.resolver_match`, honor `request.urlconf` override, `set_urlconf`. (massless: `Router.match` + `_LazyResolverMatch`.)
- `make_view_atomic` — required for `ATOMIC_REQUESTS` correctness and the async-view-with-atomic `RuntimeError` guard. Conditionally skippable only when no alias has `ATOMIC_REQUESTS` (the existing gate exploits this).
- sync-view detection: `if not iscoroutinefunction(wrapped_callback): sync_to_async(..., thread_sensitive=True)`. massless uses the router's precomputed `is_async` (`_router.pyx:148`) to pick the branch with no per-request `iscoroutinefunction`.
- `check_response` (view returned `None` / unawaited coroutine).
- deferred-render detection + `response.render()` (sync vs async dispatch).
- `convert_exception_to_response` wrapping the inner handler: `Http404`→404, `PermissionDenied`→403, `SuspiciousOperation`/`BadRequest`/`MultiPartParserError`→400, else 500 + `got_request_exception`; unrendered `TemplateResponse` from a handler is force-rendered.
- final `asyncio.iscoroutine(response)` guard.
- `get_response_async` wrapper: `response._resource_closers.append(request.close)` and ≥400 `log_response` (via `sync_to_async(log_response, thread_sensitive=False)`).

### 4.6 How unknown/third-party middleware runs unchanged
A registry **miss** yields a `BridgeLayer` that wraps the *real* Django instance with **the identical `convert_exception_to_response` + `adapt_method_mode` wrapping Django's `load_middleware` uses** (`base.py:96`, `:105`). The bridge is a normal Django middleware factory consumer: it passes the next inner layer as `get_response` (coerced to the middleware's mode), runs the real hooks, registers the instance's `process_view`/`process_template_response`/`process_exception` into the chain's three lists with the exact ordering of §4.2. This is bolt's exact model (Report 1 §2: "do not re-implement Django middleware classes; run the real ones"). The only difference from bolt is that bolt collapses N classes into one `DjangoMiddlewareStack` with a single Bolt↔Django conversion; massless does not need that conversion because the Django middleware operates on a `MasslessRequest`/`HttpResponse` directly (it just triggers promotion, `_request.pyx:258-271`).

**Guarantee mechanism — differential gate.** Every phase ships with a harness (§8) that runs the same request through `MasslessChain.run` and through the fork's real `get_response_async`, asserting identical status, headers, body, `resolver_match`, and side effects (cookies, Vary, signals). A chain that cannot be proven identical for a given stack sets `is_fast = False` and **degrades to the retained stock `get_response_async`** with zero behavior change (Report 4 §5: "Keep Django's `self._middleware_chain` available as the whole-chain fallback"). Correctness never depends on the substitution being right — only performance does.

---

## 5. How existing pieces fold in

| Piece | Location | Fate |
|---|---|---|
| Cython `_router` / `Router.match` | `_router.pyx:130-149` → `(callback, args, kwargs, route_str, is_async)` | **Stays unchanged.** Feeds the chain's inner `_run_view`. Precomputed `is_async` (`:148`) drives the await-vs-`sync_to_async` branch with no per-request `iscoroutinefunction`. |
| `_LazyResolverMatch` | `handler.py:23-48` | **Stays.** Set as `request.resolver_match` before the view. Real Django middleware reading `resolver_match` triggers `_materialize` (`handler.py:34`) — correct and already handled. |
| massless responses (`_Fast`/`JsonResponse`) + C `serialize_body` | `responses.py` (rewritten, §2.4), consumed `_protocol.pyx:266-273` | **Stays, rewritten as lazy `HttpResponse` subclasses (§2.4).** `_Fast` now subclasses Django's `HttpResponse`, so it carries the full response API (`headers`, `setdefault`, `set_cookie`, `content`, `streaming = False`) and passes `isinstance(resp, HttpResponse)`. The body stays lazy: a clean response serializes via msgspec at the C layer (`_serialize`, never touching `.content`); a real Django middleware that reads or rewrites `.content` (GZip, ETag) materializes it via msgspec on first touch, then behaves like any `HttpResponse`. Result: a `JsonResponse` flows correctly through the full real middleware stack, so there is no response-side gate. |
| `_fast_dispatch` | `handler.py:157-200` (+ inlined twin `_protocol.pyx:235-254`) | **Subsumed.** Both copies merge into the chain's inner `_run_view` — the single "call view, check_response, render, exception-funnel, close, log" routine. `handler.py:_fast_dispatch` is already effectively dead on the hot path (Report 4 §1: the protocol inlines it and only calls `handle` for the slow tier). After this work there is one `_run_view`, called by the chain. |
| `MasslessRequest` lazy promotion | `_request.pyx:93-386` | **Stays.** The chain's *value* is keeping more middleware on the un-promoted path: `FastLayer`s read off the core (`get_header`/`query_param`, `_request.pyx:116-120`); the first `BridgeLayer` is the promotion boundary. |
| Per-connection loop | `_protocol.pyx:397-450`; `dispatch` `:196-311` | **Stays unchanged.** Loop contract `raw, keep_alive = await dispatch(...)` (`:424`) is untouched; the chain lives *inside* `dispatch`. The two dispatch seams change in lockstep: the inlined fast block (`:226-254`) becomes either the empty/trivial-chain specialization or a call to `self._chain`; the slow `handler.handle(request)` (`:261`) becomes `handler._chain.run(...)`. |
| `request_started` / teardown / `request_finished` | `_protocol.pyx:234, 259-260, 293-310` | **Stays as the chain's outer lifecycle bookends**, governed by `_pool_lifecycle` (`handler.py:88`). Honor the fork's two `request_finished` receivers (`reset_urlconf` `run_async=False`, `areset_urlconf` `run_sync=False`, base.py:390-391). |

**Construction seam** (`handler.py:62-99`): replace `self.load_middleware(is_async=True)` (`:64`) with `self._chain = MasslessChain(settings.MIDDLEWARE, inner=self._run_view)`; redefine `_fast_ok` (`:95-99`) as `self._chain.is_fast`. Router/urlconf bookkeeping (`:71-79`) and `_pool_lifecycle` (`:88`) are unchanged. Keep calling `load_middleware` too (or build the equivalent lists internally) so the stock `_middleware_chain` remains available as the whole-chain fallback when `is_fast == False`.

---

## 6. Settings read (drop-in config parity)

Every key consulted by a fast re-impl is a settings key the corresponding Django class already reads — **no new settings**, full drop-in parity. (massless's own knobs `MASSLESS_POOL_LIFECYCLE` and `ROOT_URLCONF`/`MIDDLEWARE`/`DATABASES[*].ATOMIC_REQUESTS`/`DEBUG` are unchanged.)

| Fast layer | Settings keys read (cached at init) |
|---|---|
| `SecurityFast` | `SECURE_HSTS_SECONDS`, `SECURE_HSTS_INCLUDE_SUBDOMAINS`, `SECURE_HSTS_PRELOAD`, `SECURE_CONTENT_TYPE_NOSNIFF`, `SECURE_SSL_REDIRECT`, `SECURE_SSL_HOST`, `SECURE_REDIRECT_EXEMPT`, `SECURE_REFERRER_POLICY`, `SECURE_CROSS_ORIGIN_OPENER_POLICY` |
| `XFrameFast` | `X_FRAME_OPTIONS` (`getattr`, default `"DENY"`) |
| `GZipFast` | none (class attr `max_random_bytes`) |
| `CommonFast` | `DISALLOWED_USER_AGENTS`, `PREPEND_WWW`, `APPEND_SLASH`, `DEBUG` |
| `ConditionalGetFast` | none |
| Chain build | `MIDDLEWARE` (read like Django, `reversed` + `import_string`), `ROOT_URLCONF`, `DATABASES[*].ATOMIC_REQUESTS`, `DEBUG`, `MASSLESS_POOL_LIFECYCLE` |
| Delegated layers (`BridgeLayer`) | read their own settings inside the real class — `SESSION_*`, `CSRF_*`, `AUTHENTICATION_BACKENDS`, `AUTH_USER_MODEL`, `MESSAGE_STORAGE`, `LANGUAGE_CODE`/`LANGUAGES`/`USE_I18N`, etc. — untouched by massless |

Per Report 3, the delegated layers carry pluggable backends (`SESSION_ENGINE`, `AUTHENTICATION_BACKENDS`, `MESSAGE_STORAGE`); reading their settings is left to the real class so backend pluggability is preserved verbatim. We deliberately do **not** mimic bolt's separate `CORS_*`/`BOLT_COMPRESSION` Rust layer (Report 1 §5) — massless is a *substitution* model keyed off `settings.MIDDLEWARE` dotted paths, not a parallel decorator/settings system.

---

## 7. Phased plan (TDD, differential gate each phase)

Each phase is red-green-refactor with the differential harness (§8) as the acceptance gate. No phase ships unless `MasslessChain.run` is byte-identical to the fork's `get_response_async` for that phase's stack, AND single-core root benchmark (pinned cpu0, per MEMORY) does not regress.

**Phase 0 — extract `_run_view`.** Factor the shared "call view, check_response, render, exception-funnel, close, log" routine out of `_fast_dispatch` (`handler.py:174-200`) and the protocol inline (`_protocol.pyx:235-254`) into one `_run_view(request, match)`. No behavior change. Gate: existing suite + benchmark flat.

**Phase 1 — chain skeleton, ALL delegation (the proof).** Implement `MasslessChain` + `BridgeLayer` only — *no fast substitutions*. Every entry in `settings.MIDDLEWARE` becomes a `BridgeLayer` wrapping the real Django class with `convert_exception_to_response` + `adapt_method_mode`. Route `handler.py:218` and the slow protocol seam (`_protocol.pyx:261`) through `self._chain.run`. This proves the owned chain is byte-identical to Django's `get_response_async` *before any substitution*. Gate: differential harness passes for the common production stack (Security, Common, Session, Csrf, Auth, Messages, XFrame) + a synthetic stack with `process_view`/`process_template_response`/`process_exception`/`MiddlewareNotUsed`/sync-only/async-only middleware. This is where the 2026-06-01 "too invasive" fear is retired with evidence.

**Phase 2 — `is_fast` gate + trivial passthrough fast tier.** Make the chain recognize an empty/all-passthrough stack and route it through the existing inlined fast path, so we keep the current 42.7k lead unchanged when no fast substitution applies yet. Gate: no-middleware root benchmark identical to today.

**Phase 3 — `XFrameFast`** (smallest: one header, one setting). First real substitution. Differential vs real `XFrameOptionsMiddleware` across exempt/non-exempt, header-already-set, `X_FRAME_OPTIONS` variants. Gate: parity + root benchmark with XFrame in the stack improves.

**Phase 4 — `SecurityFast`.** Differential across all 9 settings, `is_secure` true/false, `SECURE_REDIRECT_EXEMPT` matches, HSTS preconditions, `setdefault` semantics.

**Phase 5 — `GZipFast`.** Differential across short-body bail, no-`gzip`-accept bail, streaming vs non-streaming, ETag weakening, byte-identical compressed output (keep `max_random_bytes` padding). C/`zlib` speedup for the compression.

**Phase 6 — `ConditionalGetFast`.** Reuse Django's `set_response_etag`/`get_conditional_response`/`parse_http_date_safe`. Differential across 304 hits, ETag generation, `If-None-Match`/`If-Modified-Since`.

**Phase 7 — `CommonFast` (hot path only).** Re-impl `Content-Length` + `DISALLOWED_USER_AGENTS` + `PREPEND_WWW`; **delegate** the `is_valid_path` `APPEND_SLASH`/404-slash branch to Django's helper. Differential including the slash-redirect and `RuntimeError`-on-non-GET-with-DEBUG edge cases.

**Phase 8 — partial-fast chains.** Allow a fast prefix of `FastLayer`s above a `BridgeLayer` boundary (the promotion boundary). No response-side gating is needed: `_Fast` responses are lazy `HttpResponse` subclasses (§2.4) and flow safely through Bridge layers. Differential-test a `JsonResponse` view under the full real stack (GZip rewriting `.content`, ConditionalGet hashing it) to prove the lazy materialization is byte-identical. Benchmark the realistic production stack with Security+XFrame+Gzip+Common fast and Session+Csrf+Auth delegated. The headline goal: keep the bolt-beating lead *with* the common stack active.

---

## 8. Test strategy

**Differential harness (the core gate).** A pytest fixture that, given a `settings.MIDDLEWARE` list and a request, runs it through both:
1. `MasslessChain.run(request, handler)`, and
2. the fork's real `BaseHandler.get_response_async` (the retained fallback at `handler.py:218`),

and asserts identical: status code, full header set (order-insensitive where Django is, order-sensitive for `Vary`/`Set-Cookie`), body bytes, `request.resolver_match` (materialized), and side effects — cookies set, `patch_vary_headers` results, `got_request_exception` signal firing, `_resource_closers` containing `request.close`. This is the same discipline that made `_fast_dispatch` trustworthy (MEMORY: "audited+differential-tested faithful to Django").

**Per-middleware parity tests.** For each fast re-impl, a dedicated suite runs the request through `FastLayer` and the real Django class side-by-side, sweeping the settings matrix in §3.4/§6. Byte-identical output required (GZip and ETag explicitly assert identical bytes, including `max_random_bytes` padding).

**Ordering tests** (port Report 2 §2, mirror bolt's `test_mixed_hook_and_call_only_stack_preserves_declared_order`): a stack `[A, B, C]` of instrumented middleware recording `process_request`/`__call__`-pre, `process_view`, view, `process_template_response`, `__call__`-post, `process_response`. Assert:
- `__call__` pre-code: outer→inner (A, B, C).
- `process_view`: MIDDLEWARE order (A, B, C), first truthy short-circuits.
- `process_template_response`: reverse (C, B, A), only for deferred-render responses.
- `process_exception`: reverse, synchronous, only for view/render exceptions; all-`None` re-raises.
- `__call__` post-code: inner→outer (C, B, A).

**Edge-case suite:** `MiddlewareNotUsed` skip (handler unchanged), `None` factory → `ImproperlyConfigured`, both-capable-false → `RuntimeError`, sync-only middleware in async chain (`async_to_sync` coercion), native `aprocess_view`/`aprocess_template_response` preference, per-request `request.urlconf` override forcing fallback, `ATOMIC_REQUESTS` forcing `make_view_atomic`, view returning `None`/unawaited coroutine, deferred-render `TemplateResponse`, `Http404`/`PermissionDenied`/`SuspiciousOperation` → 404/403/400.

**Benchmark gate** (single-core, pinned cpu0 per MEMORY "benchmark-single-core"): root no-DB throughput must (a) hold the no-middleware fast-tier lead over bolt (≥42.7k), and (b) the realistic stack (Security+XFrame+Gzip+Common fast; Session+Csrf+Auth delegated) must beat stock `get_response_async` on the same stack — the project's stated win condition.

---

## 9. Risks + non-goals

**Risks**
- **Fidelity drift (highest).** A fast re-impl diverging from the real class in a header, ordering, or edge case. *Mitigation:* the differential harness gates every phase; any unprovable stack degrades to the retained stock `get_response_async` (correctness never depends on substitution being right). Phase 1 proves the chain itself before any substitution exists.
- **`_Fast` lazy-body fidelity** (§2.4). `_Fast` now subclasses `HttpResponse` with a lazy, msgspec-backed `content`, so a Bridge layer reading `.content`/`setdefault` works. The residual risk is the lazy body diverging from an eager one. *Mitigation:* materialization goes through the same `serialize_body` bytes the C path emits; Phase 8 differential-tests a `JsonResponse` under GZip/ConditionalGet (the body-reading middlewares) for byte-identical output.
- **`CommonFast` `should_redirect_with_slash`** pulls in the resolver (`is_valid_path`). *Mitigation:* delegate that branch verbatim; re-impl only the hot path (Report 3 §2).
- **Fork-specific divergences** (`aprocess_view`/`aprocess_template_response` preference; dual `request_finished` receivers). *Mitigation:* explicit edge-case tests (§8); this repo's `get_response_async`, not stock Django's, is the differential oracle.
- **Cythonization regressing the hot path** (MEMORY: "cythonizing the pipeline regresses it"). *Mitigation:* `run()` is a flat coroutine that *removes* async overhead; benchmark gate per phase; if a `.pyx` layer regresses, keep it pure-Python.
- **Promotion creep.** A `FastLayer` accidentally touching a promoting attribute defeats the no-promote win. *Mitigation:* `FastLayer`s read only via the core accessors (`_request.pyx:116-120`); assert no promotion in fast-tier tests.

**Non-goals**
- Re-implementing `SessionMiddleware`, `AuthenticationMiddleware`, `MessageMiddleware`, `CsrfViewMiddleware`, `LocaleMiddleware`, or any pluggable-backend / security-crypto middleware — always delegate (Report 3).
- Re-implementing third-party middleware — runs unchanged via `BridgeLayer` (Report 1 §3: unknown middleware is never skipped or errored).
- A bolt-style parallel CORS/rate-limit/compression layer keyed off decorators/settings instead of `settings.MIDDLEWARE` (Report 1 §5) — massless stays a pure dotted-path substitution model.
- `BrokenLinkEmailsMiddleware` substitution (mail/404-only, not hot).
- Multi-core or cross-core-count benchmark headlines (MEMORY: "benchmark-single-core").
- Publishing / docs site (MEMORY: deferred).

---

### Files (all absolute)
- New: `/home/ohaas/e1+/django-massless/src/massless/_chain.pyx`, `/home/ohaas/e1+/django-massless/src/massless/_chain.pxd`
- Changed: `/home/ohaas/e1+/django-massless/src/massless/handler.py` (`:64` build seam, `:95-99` `_fast_ok`→`is_fast`, `:157-200` `_fast_dispatch`→`_run_view`, `:218` dispatch seam), `/home/ohaas/e1+/django-massless/src/massless/_protocol.pyx` (`:226-254` inline, `:261` slow seam)
- Unchanged, fold in: `/home/ohaas/e1+/django-massless/src/massless/_router.pyx` (`:130-149`), `/home/ohaas/e1+/django-massless/src/massless/_request.pyx` (`:93-386`), `/home/ohaas/e1+/django-massless/src/massless/responses.py` (`:6-7`, `:20-101`)
- Differential oracle: `/home/ohaas/e1+/django-asyncio/django/core/handlers/base.py` (`load_middleware:26-114`, `get_response_async:153-184`, `_get_response_async:240-310`), `/home/ohaas/e1+/django-asyncio/django/core/handlers/exception.py` (`convert_exception_to_response:38-50`, `response_for_exception:64-160`)
- Middleware sources to mirror: `/home/ohaas/e1+/django-asyncio/django/middleware/{security,common,gzip,clickjacking,http}.py`
