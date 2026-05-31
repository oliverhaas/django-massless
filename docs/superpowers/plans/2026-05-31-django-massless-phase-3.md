# django-massless Phase 3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development or superpowers:executing-plans. Checkbox (`- [ ]`) steps.

**Goal:** A two-tier middleware chain: a C-level fast tier (CORS, rate-limit, JWT auth) that never promotes and can short-circuit, plus a bridge tier that promotes and runs the view through Django's real middleware chain.

**Architecture:** Per route, an ordered fast-tier `Middleware` list (`before`/`after`) compiled at startup, plus a `bridge` flag. The protocol runs `before()` hooks (short-circuit on a returned `Response`), dispatches the view (promoting first if `bridge`), then runs `after()` hooks. JWT auth attaches `request.auth` (plain attr, no promotion); `request.user` is a lazy promote+ORM property.

**Tech Stack:** Cython 3.2, Django (`BaseHandler` middleware loading), msgspec, stdlib `hmac`/`hashlib`/`base64`, pytest.

**Spec:** [docs/superpowers/specs/2026-05-31-django-massless-phase-3-design.md](../specs/2026-05-31-django-massless-phase-3-design.md)

---

## Conventions
Same as prior phases. Rebuild `.pyx` with `uv sync --reinstall-package django-massless`. Gates: `uv run pytest -n auto`, `uv run ruff check`, `uv run mypy src/massless/`. Tests run under pytest-django. Commit per task; hooks may reformat (re-stage).

## File Structure
| File | Change |
|------|--------|
| `src/massless/_response.pyx` (+pxd if needed) | a `Response` value (status, headers, body) for short-circuits + `after()` mutation |
| `src/massless/_middleware.pyx` + `.pxd` | `Middleware` base; `run_before`/`run_after`; `CORS`, `RateLimit`, `JWTAuth` |
| `src/massless/_request.pyx` | `request.auth` plain attr; `request.user` lazy (promote + ORM) |
| `src/massless/app.py` | `@api.get(..., middleware=[...], bridge=False)`; per-route compile |
| `src/massless/bridge.py` | Django middleware-chain shim around the view |
| `src/massless/_protocol.pyx` | run fast-tier before/after; promote + bridge when flagged |
| `benchmarks/app.py` | `/auth/context`, `/auth/me`, CORS + rate-limited endpoints |
| `tests/test_middleware.py`, `tests/test_auth.py`, `tests/test_bridge.py` | unit + integration |

---

## Task 1: Response value object

**Files:** `src/massless/_response.pyx`; `tests/test_response.py`

- [ ] Failing test: `Response(200, {"X-A": "1"}, b"hi")` exposes `.status`, `.headers`, `.body`; a helper `response_to_bytes(resp, keep_alive)` produces the same wire bytes as `build_http_response`. Also `from_view_result(obj)` builds a `Response` (200, inferred content-type, serialized body) from a dict/bytes/str.
- [ ] Implement a small `Response` (a `cdef class` or plain class) with `status:int`, `headers:dict[str,str]`, `body:bytes`, plus `from_view_result` and `to_bytes(keep_alive)` reusing `serialize_body`/`build_http_response`. Headers from the dict are appended to the response.
- [ ] Rebuild + test. Commit `feat(response): Response value for middleware short-circuits`.

## Task 2: Middleware base + chain runner

**Files:** `src/massless/_middleware.pyx` + `_middleware.pxd`; `tests/test_middleware.py`

- [ ] Failing test: a `Middleware` subclass whose `before` returns a `Response` short-circuits `run_before(chain, req)` (returns that response, later middleware not called); one returning `None` continues; `run_after(chain, req, resp)` calls each `after` in reverse order.
- [ ] Implement `Middleware` with `before(self, req)` (return `Response|None`) and `after(self, req, resp)`; module functions `run_before(list, req)->Response|None` and `run_after(list, req, resp)`.
- [ ] Rebuild + test. Commit `feat(middleware): Middleware base + chain runner`.

## Task 3: CORS middleware

**Files:** `src/massless/_middleware.pyx`; `tests/test_middleware.py`

- [ ] Failing test: `CORS(allow_origins=["https://ex.com"])`. `before` on an `OPTIONS` with `Origin` + `Access-Control-Request-Method` returns a `204` `Response` with `Access-Control-Allow-Origin/Methods/Headers`. On a non-preflight request `before` returns None; `after` adds `Access-Control-Allow-Origin` to the response when `Origin` matches.
- [ ] Implement `CORS(Middleware)` reading `Origin`/`Access-Control-Request-*` via `req.get_header(...)` (fast path). Config: allowed origins/methods/headers.
- [ ] Rebuild + test. Commit `feat(middleware): CORS (preflight 204 + response headers)`.

## Task 4: Rate-limit middleware

**Files:** `src/massless/_middleware.pyx`; `tests/test_middleware.py`

- [ ] Failing test: `RateLimit(limit=2, window_s=60, now=fake_clock)` keyed by a client id (a header or a fixed key in the test). First 2 `before` calls return None, 3rd returns a `429` `Response`; after the window advances (fake clock), allowed again. Deterministic via injected clock, no sleeping.
- [ ] Implement a fixed-window `RateLimit(Middleware)` with a process-local dict `{key: (window_start, count)}` and an injectable `now` callable (defaults to a real monotonic clock). Key derived from a configurable header (default a fixed/global key for the test).
- [ ] Rebuild + test. Commit `feat(middleware): fixed-window rate limit (429)`.

## Task 5: JWT auth middleware

**Files:** `src/massless/_middleware.pyx`; `tests/test_auth.py`

- [ ] Failing test: `JWTAuth(secret="s")`. With a valid `Authorization: Bearer <HS256 jwt>` (built in the test via base64url + hmac-sha256), `before` returns None and sets `req.auth` to the decoded claims; tampered signature -> `401`; expired (`exp` in the past) -> `401`; missing header -> `401` (configurable allow-anonymous later). Use `hmac.compare_digest`.
- [ ] Implement `JWTAuth(Middleware)`: split the token, base64url-decode header/payload, recompute HMAC-SHA256 over `header.payload` with the secret, constant-time compare, check `exp`, msgspec-decode claims, set `req.auth = claims` (plain attr; no promotion). Build the test's tokens with stdlib only (no PyJWT dependency).
- [ ] Rebuild + test. Commit `feat(auth): HS256 JWT fast-tier auth -> request.auth`.

## Task 6: request.auth + lazy request.user

**Files:** `src/massless/_request.pyx`; `tests/test_request.py`

- [ ] Failing test: `req.auth` defaults to None and is a plain settable attr (no promotion when read/written). `req.user`: accessing it promotes and returns a user resolved from `req.auth` claims via the ORM (test with pytest-django: a claim `{"sub": <id>}` -> `get_user_model().objects.aget`/sync resolve). Reading only `req.auth` keeps `_is_django` False.
- [ ] Implement: `auth = None` default (set as plain attr in `__init__`). `user` as a promote-first property that resolves the user from `self.auth` (e.g. `sub`) via the user model, caching on `self._user`. (Keep it minimal: if no auth or no sub, an `AnonymousUser`.)
- [ ] Rebuild + test. Commit `feat(request): request.auth (fast) + lazy request.user (promote+ORM)`.

## Task 7: Registration + per-route compile

**Files:** `src/massless/app.py`; `tests/test_app.py`

- [ ] Failing test: `@api.get("/x", middleware=[m1, m2], bridge=True)` records the ordered middleware and the bridge flag on the `Route`; a global `api.middleware` default is prepended. `build_router` unchanged; routes carry `middleware` + `bridge`.
- [ ] Implement: extend `Route` with `middleware: list` and `bridge: bool`; `get(path, middleware=None, bridge=False)`; `MasslessAPI(middleware=[...])` global default.
- [ ] Test (no rebuild). Commit `feat(app): per-route middleware + bridge registration`.

## Task 8: Protocol wiring (fast tier + bridge)

**Files:** `src/massless/_protocol.pyx`; `tests/test_integration.py`

- [ ] Failing integration test: an endpoint with a CORS + JWT middleware: preflight OPTIONS -> 204; valid token -> 200 with CORS header; bad token -> 401; the response carries CORS headers via `after`.
- [ ] Implement in `dispatch`: build the `MasslessRequest`; `r = run_before(route.middleware, request)`; if `r` is a `Response`, run `run_after` and return its bytes; else if `route.bridge`: `request._promote()` then run via the bridge shim (Task 9); else call the view; wrap the result in a `Response`; `run_after(route.middleware, request, resp)`; return `resp.to_bytes()`.
- [ ] Rebuild + test. Commit `feat(protocol): fast-tier before/after + bridge dispatch`.

## Task 9: Django bridge shim

**Files:** `src/massless/bridge.py`; `tests/test_bridge.py`

- [ ] Failing test: with `settings.MIDDLEWARE = ["tests.bridge_mw.AddHeaderMiddleware"]` (a tiny middleware that sets `response["X-Bridge"] = "1"` and reads `request.path`), a bridged route's response carries `X-Bridge: 1` and the request promoted. (Define the test middleware in a tests module.)
- [ ] Implement `bridge.py`: a `BridgeHandler` that, once at startup, loads the Django middleware chain (reuse `django.core.handlers.base.BaseHandler.load_middleware` semantics) wrapping a `get_response(request)` that calls the massless view and returns a Django `HttpResponse` (convert the view's dict/bytes/str result into an `HttpResponse`/`JsonResponse`). `run(request, view, kwargs)` invokes the chain and returns the Django response; the protocol serializes it from `.status_code`/`.content`/`.headers`. Handle async vs sync middleware via Django's own adaptation.
- [ ] Rebuild + test. Commit `feat(bridge): run views through Django's real middleware chain`.

## Task 10: Benchmark endpoints

**Files:** `benchmarks/app.py`; `tests/test_integration.py`

- [ ] Add `/auth/context` (JWTAuth middleware; view returns `request.auth` claims; no promotion), `/auth/me` (returns `request.user` id; promotes + ORM), a CORS-wrapped route, and a rate-limited route. Add a smoke test that each serves.
- [ ] Commit `feat(bench): auth/CORS/rate-limit Phase 3 endpoints`.

## Self-Review
Spec coverage: fast tier (§2.2) -> Tasks 2-5; request.auth/user (§2.3) -> Task 6; bridge (§2.4) -> Task 9; registration (§2.5) -> Task 7; Response (§2.6) -> Task 1; protocol flow (§4) -> Task 8; benchmark (§6) -> Task 10; no-promotion + tests (§5) -> Tasks 5,6,8. Check name consistency: `run_before`/`run_after`, `Response.to_bytes`/`from_view_result`, `Route.middleware`/`Route.bridge`, `request.auth`. The bridge is the highest-risk task; the verify step will harden it against real Django.
