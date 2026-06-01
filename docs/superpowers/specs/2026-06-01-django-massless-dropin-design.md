# django-massless: Drop-in Django accelerator (re-architecture)

**Status:** Approved for implementation planning
**Date:** 2026-06-01
**Supersedes:** the django-bolt-style framing of
[2026-05-31-django-massless-design.md](2026-05-31-django-massless-design.md). The C
engine built across Phases 1-4 is kept; the bolt-style API surface is retired.

---

## 1. Summary and pivot

`django-massless` is a **drop-in, high-performance server and request pipeline for an
unmodified Django project** (including django-ninja apps). You
keep your `urls.py`, your views (`request -> HttpResponse`), your `settings`, and your
`MIDDLEWARE`; you run the project under massless instead of uvicorn/gunicorn and it
serves the *normal Django stack* faster.

This is a deliberate pivot. The earlier design was a django-bolt-style API framework
(`MasslessAPI`, `@api.get`, a custom radix router, dict-returning views, with real
Django as an opt-in "bridge"). That bypassed Django for its fast path. The new identity
is the opposite: **Django is always the source of truth; massless accelerates it** by
parsing in C, deferring construction of the parts of the request a handler never reads,
running on uvloop across processes, and letting you put hot routes on leaner middleware
stacks.

### The honest value proposition
A full-fidelity drop-in runs Django's URL resolver, your whole `MIDDLEWARE`, and your
view, all in Python, so the speedup is **bounded** by that Python cost; it is not the
2x-30x of the bypass framework. The real wins are:
1. A lazy `MasslessRequest` that skips building `META`/`GET`/`POST`/`body`/`COOKIES`
   for handlers that do not touch them.
2. A C HTTP parse + uvloop transport + `SO_REUSEPORT` multi-process.
3. **Per-route middleware stacks** (`MIDDLEWARE_STACKS`): a hot API route can run a lean
   stack (no session/CSRF) and stay close to the fast path, while `/admin` keeps the
   full stack. This is the largest, opt-in lever, and it is something stock Django (one
   global `MIDDLEWARE`) cannot do.

## 2. Approved decisions

1. **Zero-change drop-in.** No app code changes for the default path. Adoption is
   swapping the run command.
2. **Full-fidelity default + opt-in fast lane.** Default: run the complete Django stack,
   behavior byte-identical to uvicorn+Django. Opt-in: assign leaner named middleware
   stacks per route via `MIDDLEWARE_STACKS`.
3. **Approach A** (of three): massless owns the transport, the lazy request, and C
   response serialization, and **reuses Django's URL resolver + middleware** via a
   `BaseHandler`-derived core handler. (Rejected: B, a thin C ASGI server in front of
   `get_asgi_application()`, gives no lazy-request gain since Django rebuilds its own
   request from the ASGI scope; C, reimplementing routing/middleware in C, is too
   invasive and a fidelity risk.)
4. **Pivot, reusing the engine.** Keep the C engine; retire the bolt-style surface.
5. **django-ninja works unchanged** (it is Django views plugged into `urls.py`).
6. **ASGI-flavored, sync views via the thread-pool.** No separate WSGI mode. Streaming
   responses (`StreamingHttpResponse`/SSE) are a later phase.
7. **Benchmarks pivot** to massless vs uvicorn+Django and massless vs uvicorn+ninja on
   the same app (plus the existing bolt/plain-Django context).

## 3. Request flow (default, full-fidelity)

```
TCP (SO_REUSEPORT) -> uvloop -> Cython protocol -> httptools parse
  -> MasslessRequest                                  [lazy: META/GET/POST/body/COOKIES on first touch]
  -> Django URL resolver (ROOT_URLCONF) on request.path_info  -> view + args/kwargs + the route's stack
  -> run the selected MIDDLEWARE stack (BaseHandler onion) around the view, with the lazy request
       async view -> awaited on the loop
       sync view  -> run in the thread-pool executor (blocking ORM safe)
  -> view returns HttpResponse  -> C-serialize (status line, headers, Set-Cookie, body) -> socket
```

Django is the source of truth from the resolver through response. The result is
behaviorally identical to running the same project under uvicorn, with a faster request
construction and transport.

## 4. The lazy request, recast

In the drop-in, the request is **always** a real Django request used by middleware and
the view, so the Phase 2 mechanism changes meaning: "promotion" becomes "build each
sub-part on first access." `MasslessRequest` subclasses `WSGIRequest` (verified
necessity) and is constructed for every request from the `RequestCore` C buffers;
`META`, `GET`, `POST`, `body`, `COOKIES`, `headers`, and `encoding` materialize lazily.
A handler that never reads `POST`/`body`/`FILES`/`COOKIES` does not pay to build them.

The **attribute-by-attribute parity suite** (promoted `MasslessRequest` == stock
`WSGIRequest` from the same bytes) becomes the central correctness guarantee, now
exercised on the path every request takes. Drift here is the project's primary
correctness risk, mitigated by the parity suite run on each supported Django version.

## 5. `MIDDLEWARE_STACKS` (the opt-in fast lane)

- **Definition (settings):**
  ```python
  MIDDLEWARE_STACKS = {
      "default": MIDDLEWARE,                 # falls back to the global MIDDLEWARE if unset
      "api": [                               # lean: no session/CSRF/messages
          "django.middleware.security.SecurityMiddleware",
          "django.middleware.common.CommonMiddleware",
      ],
  }
  ```
- **Assignment (per route).** A route declares its stack, resolved from the
  `resolver_match`:
  - per include: `path("api/", massless.stack("api", include("myapi.urls")))`
  - per view: `@massless.stack("api")` on the view callable.
  A route with no declared stack uses `"default"`. A django-ninja app is mounted on the
  lean `"api"` stack with one `massless.stack(...)` wrapper.
- **Execution.** massless resolves the URL once to find the view and its stack, then runs
  that stack's pre-built middleware chain (a `BaseHandler` per named stack) around the
  view. **Implementation must preserve Django's middleware ordering semantics**
  (`process_request` before resolution, `process_view` after, `process_response` on the
  way out) within each stack; whether a route's stack is chosen before or after
  resolution, and how that interacts with `process_request`, is the key implementation
  detail to pin during the build (and is covered by parity tests against Django's own
  ordering). Under massless+uvicorn the global `MIDDLEWARE` still works as the single
  default stack, so `MIDDLEWARE_STACKS` is purely additive.

## 6. Reuse vs retire

**Reuse (the engine, mostly as-is):**
- `_protocol.pyx`: httptools/uvloop connection layer, keep-alive, pipelining, per-
  connection ordered dispatch, graceful drain.
- `_request.pyx`: `RequestCore` C storage + lazy `MasslessRequest` (`WSGIRequest`
  subclass) + the parity surface.
- `bridge.py` -> becomes the core **`MasslessHandler`** (a `BaseHandler` subclass) that
  runs a middleware stack around Django's resolver + view. Phase 3 overrode the innermost
  handler to call a massless view directly; the drop-in instead uses Django's normal
  resolution (`ROOT_URLCONF`).
- `server.py`, `supervisor.py`, `runmassless`, `__main__.py`: `SO_REUSEPORT` multi-
  process, supervisor, lifecycle/hooks, graceful shutdown. `runmassless` now serves the
  current Django project (no `module:api` argument needed).
- `_response.pyx`: serialize a Django `HttpResponse` to wire bytes (status, headers,
  `Set-Cookie`, body); the sync/async executor dispatch.

**Retire:**
- `_router.pyx` (custom radix router) -> Django's URL resolver.
- `app.py` (`MasslessAPI`, `@api.get`, the signature binder, `Route`, request injection).
- The bolt-style fast-tier middleware framework (`_middleware.pyx`: `CORS`, `RateLimit`,
  `JWTAuth`, `run_before`/`run_after`, `Response`). In the drop-in you use Django's (or
  ninja's) own auth/CORS/throttling middleware in a stack. The C middlewares may return
  later as optional, Django-compatible stack entries, but they are not core.

## 7. django-ninja

A django-ninja API plugs into `urls.py` (`path("api/", api.urls)`); its operations
compile to async/sync Django view callables and read `request.body`/query, which the
lazy request materializes on demand. So a ninja app runs unchanged under massless. The
headline demo + benchmark: an existing ninja API, mounted on a lean
`MIDDLEWARE_STACKS["api"]`, served by massless vs the same app under uvicorn.

## 8. Error handling and testing

- **Error handling:** Django's normal handling via the middleware chain
  (`convert_exception_to_response`); 404 from the resolver; unhandled 500 logged via the
  `massless` logger, traceback in the body only when `settings.DEBUG`.
- **Testing:**
  - The **parity suite** (now central): promoted `MasslessRequest` matches stock
    `WSGIRequest` attribute-by-attribute, across Django versions.
  - **Drop-in integration:** a small but representative Django project (a normal
    `urls.py` with function and class-based views, a couple of stock middleware, a model
    + ORM view) served through massless, asserting responses match Django's behavior
    (compare against the Django test client / uvicorn for the same requests).
  - **django-ninja integration:** a ninja API served through massless returns correct
    schema-validated responses.
  - **`MIDDLEWARE_STACKS`:** a route on a lean stack skips the omitted middleware (e.g.
    no `Set-Cookie` session) while a default-stack route runs the full chain; ordering
    matches Django.
  - **Lifecycle/multi-process** (reused) and the **benchmark gate** vs uvicorn+Django.

## 9. Phased rebuild

1. **Core handler + drop-in server.** Replace the `@api.get` surface with `MasslessHandler`
   (Django resolver + global `MIDDLEWARE` + view, fed the lazy `MasslessRequest`); make
   `runmassless`/`__main__` serve the current Django project; retire `_router.pyx` and
   `app.py`. Drop-in integration tests (a normal Django project, byte-identical
   responses). This is the bulk of the pivot.
2. **`MIDDLEWARE_STACKS`.** Named stacks in settings + per-include/per-view assignment +
   per-stack `BaseHandler`s, preserving Django ordering.
3. **django-ninja example + benchmark pivot.** A ninja app on a lean stack; benchmarks
   become massless vs uvicorn+Django and massless vs uvicorn+ninja on the same app.
4. **(Later)** Streaming responses (`StreamingHttpResponse`/SSE, chunked transfer);
   optional WSGI mode; the retired C middlewares as optional Django-compatible stack
   entries.

## 10. Non-goals and risks

- **Non-goals (now):** streaming/SSE, WSGI mode, a custom API surface, C-accelerated URL
  resolution (Django's resolver stays Python), reviving the bolt-style fast tier.
- **Risks:**
  - **Bounded speedup:** running the full Django stack caps the default-path gain; the
    headline numbers depend on lean stacks + skipped request construction. The benchmark
    must report honestly vs uvicorn+Django (not vs the old bypass numbers).
  - **HttpRequest parity drift:** now on every request; the parity suite is the guard.
  - **Middleware-ordering fidelity with `MIDDLEWARE_STACKS`:** the resolve-then-select
    ordering must not change `process_request`/`process_view` semantics; pinned by tests
    against Django's own order.
  - **Streaming gap:** ninja/Django apps that stream will not work until the later phase;
    must be documented clearly so the drop-in is not advertised as universal yet.
