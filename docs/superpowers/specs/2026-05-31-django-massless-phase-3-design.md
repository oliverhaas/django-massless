# django-massless Phase 3: Tiered middleware

**Status:** Approved for implementation planning
**Date:** 2026-05-31
**Parent design:** [2026-05-31-django-massless-design.md](2026-05-31-django-massless-design.md) (§5, §10 Phase 3)

---

## 1. Goal and exit criterion

A two-tier middleware chain:

- **Fast tier:** ordered, C-level middleware (CORS, rate-limit, JWT/API-key auth) that
  operate on the `RequestCore` header API only and **never promote**. They may
  short-circuit with a C-built response (preflight `204`, `429`, `401`) and may add
  response headers on the way out.
- **Bridge tier:** for routes that need real Django middleware (CSRF, sessions,
  messages, third-party). Entering it **promotes** the request, then runs the view
  through Django's real middleware chain.

**Exit criterion:**
1. A JWT-authenticated endpoint that only reads validated claims serves without
   promoting (`_is_django` never set), asserted by a no-promotion test, and is
   competitive with django-bolt's `/auth/context`.
2. A CORS preflight (`OPTIONS`) is answered `204` with the right headers entirely on
   the fast path; actual responses carry the CORS headers.
3. A rate-limited route returns `429` after its limit, built on the fast path.
4. A route flagged for the bridge tier runs through a real Django middleware
   (e.g. a header-adding middleware) and the middleware observes/modifies the request
   and response.

## 2. Decisions

1. **Fast middleware interface.** A `cdef class Middleware` with two hooks:
   `before(req) -> response | None` (None continues; a response short-circuits) and
   `after(req, resp) -> None` (mutate the response, e.g. add headers). Implemented in
   `_middleware.pyx`. The chain is an ordered Python list compiled per route at startup
   (a C array is a later optimization; correctness first).
2. **Concrete fast middleware (Phase 3 set):**
   - **CORS:** answer `OPTIONS` preflight with `204` + `Access-Control-Allow-*` from
     config; add `Access-Control-Allow-Origin` to actual responses. Reads `Origin`,
     `Access-Control-Request-*` from the C header API.
   - **Rate limit:** fixed-window or token-bucket per client key (IP or a header), in
     a process-local `dict`/`libcpp` map; `429` short-circuit when exceeded. Per-process
     (matches the single-process model; cross-process is a later concern).
   - **JWT auth:** verify an `Authorization: Bearer <jwt>` HS256 signature against a
     configured secret using stdlib `hmac`/`hashlib` (C-backed) on the raw header bytes,
     decode the claims (msgspec), and attach them to the request as `request.auth`
     (a plain attribute set on the fast path, no promotion). Invalid/expired -> `401`
     short-circuit. (RS256/API-key are later additions; the interface accommodates them.)
3. **`request.auth` vs `request.user`.** Fast-tier auth attaches the validated claims as
   `request.auth` (set as a plain attribute, no promotion). `request.user` (a DB-backed
   user) is a lazy property that promotes and queries the user model on access; an
   endpoint that only reads `request.auth` stays on the fast path, one that reads
   `request.user` pays the promotion + DB cost (mirrors django-bolt's
   `/auth/context` vs `/auth/me`).
4. **Bridge tier.** For routes flagged `bridge=True`, dispatch promotes the request and
   runs the view through Django's real middleware chain. Implementation: build, once at
   startup, a Django middleware chain via `BaseHandler.load_middleware()` semantics
   (from `settings.MIDDLEWARE`), wrapping a synthetic `get_response` that calls the
   massless view with the promoted request. The bridge runs in the thread/async context
   the view needs. Django is the source of truth from entry through response.
5. **Registration.** `@api.get(path, middleware=[...], bridge=False)`. Each route
   compiles to an ordered fast-tier list plus a bridge flag. Global default middleware
   may be set on the `MasslessAPI`. Compiled at startup.
6. **Response model.** The fast tier needs a lightweight response the C builder can emit
   (status, headers, body) for short-circuits, plus `after()` mutation. Introduce a
   minimal `Response` (status, headers dict, body) used by middleware short-circuits and
   by `after()` header addition; the view's dict/bytes/str returns still serialize as in
   Phase 1, wrapped into this response shape before `after()` runs.

## 3. Module changes

```
src/massless/
  _middleware.pyx + .pxd   # Middleware base, the fast chain runner, CORS/RateLimit/JWTAuth
  _response.pyx            # add a Response value (status/headers/body) for short-circuits + after()
  _protocol.pyx            # run fast-tier before() -> view -> after(); bridge promotes
  app.py                   # @api.get(middleware=..., bridge=...); compile per-route chain
  bridge.py                # Django middleware-chain shim (load_middleware around the view)
  _request.pyx             # request.auth plain attr; request.user lazy (promote + ORM)
```

## 4. Data flow (Phase 3)

```
... C router match ...
  -> fast-tier before() in order (C header API, nogil-friendly)
       any returns a Response? -> after() hooks -> C serialize -> write   [no promotion]
  -> route.bridge?  yes -> PROMOTE -> Django middleware chain -> view -> Django response
                    no  -> view(MasslessRequest, **kwargs)   [fast path]
  -> wrap view return into a Response
  -> fast-tier after() in reverse order (e.g. add CORS headers)
  -> C serialize -> write
```

## 5. Testing strategy

- **Fast-tier unit tests:** CORS preflight 204 + headers; CORS actual-response header;
  rate-limit allows N then 429; JWT valid -> claims attached + 200, invalid/expired ->
  401, missing -> 401 (or anonymous, per config).
- **No-promotion:** a JWT endpoint reading only `request.auth` never promotes (probe
  `_is_django`).
- **request.user promotes:** an endpoint reading `request.user` promotes and returns the
  DB user (pytest-django + ORM).
- **Bridge tier:** a route with a custom Django middleware in `settings.MIDDLEWARE` sees
  the request and can add a response header; assert the header appears and the request
  promoted.
- **Integration:** all of the above through the real server.
- **Regression:** Phase 1/2 fast-path endpoints unchanged; their no-promotion holds.

## 6. Benchmark (after the phase)

Add bench endpoints mirroring django-bolt's auth cases: `/auth/context` (JWT validated,
no DB, no promotion), `/auth/me` (promotes + ORM user load), plus a CORS preflight and a
rate-limited route. Compare `/auth/context` head-to-head with django-bolt's
`/auth/context`. Confirm no regression on the Phase 1/2 core endpoints.

## 7. Out of scope for Phase 3

RS256/asymmetric JWT and API-key backends beyond the HS256 example; distributed
(cross-process) rate limiting; the full Django auth/session/messages feature set beyond
proving the bridge runs real middleware; `nogil` C-crypto via libsodium (stdlib hmac is
the Phase 3 implementation). CSRF correctness parity is proven by the bridge running
Django's CSRF middleware, not reimplemented.

## 8. Risks

- **Bridge correctness:** wrapping Django's middleware chain around a non-handler view is
  intricate (async vs sync middleware, `get_response` signature, `MiddlewareNotUsed`).
  Mitigated by reusing `BaseHandler.load_middleware` rather than hand-rolling, and a
  bridge integration test with a real middleware.
- **Fast-path auth correctness:** HS256 verification on raw bytes must constant-time
  compare (`hmac.compare_digest`) and handle base64url/exp correctly. Covered by tests
  including tampered/expired tokens.
- **Rate-limit state:** per-process and time-based; tests must control the clock (inject
  a time source) to be deterministic, not sleep.
