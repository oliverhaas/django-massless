# django-massless Phase 2: Lazy promotion and Django glue

**Status:** Approved for implementation planning
**Date:** 2026-05-31
**Parent design:** [2026-05-31-django-massless-design.md](2026-05-31-django-massless-design.md) (§4, §10 Phase 2)

---

## 1. Goal and exit criterion

A `MasslessRequest` lazily and one-shot **promotes** into a fully-functional Django
`HttpRequest` on first access to Django-machinery state, reconstructed from the
`RequestCore` C buffers. After promotion the object is behaviorally
indistinguishable from a stock request for the supported surface, so real Django
views (and the Django ORM) work against it.

**Exit criterion:**
1. A property-based parity test suite builds, from the same raw request bytes, both a
   stock Django `WSGIRequest` and a promoted `MasslessRequest`, and asserts they match
   attribute-by-attribute across the supported surface (method, path, GET, POST, body,
   COOKIES, META, content_type, encoding, headers, get_host, scheme).
2. The Phase 1 no-promotion guarantee still holds: the 4 framework-bound bench
   endpoints never promote (`_is_django` never set), asserted by the existing test.
3. A view that performs a Django ORM query works end-to-end through the real server.

## 2. Decisions

1. **Reuse Django's request construction.** `_promote()` builds a WSGI environ from the
   `RequestCore` and calls `WSGIRequest.__init__(self, environ)` to populate `self`.
   This borrows Django's own, version-correct logic for META/GET/POST/body/headers
   rather than hand-rolling it, which maximizes parity and shrinks the drift surface.
   (WSGI, not ASGI, because the environ + `wsgi.input` stream model is synchronous and
   simplest to build from bytes we already hold; the resulting `HttpRequest` surface is
   identical either way.)
2. **`method`/`path` become plain instance attributes** (set in `MasslessRequest.__init__`
   from the core), not read-only properties. Read-only properties would break
   `WSGIRequest.__init__`'s assignments to `self.path`/`self.method`. Plain attributes
   are also marginally faster on the fast path and satisfy the Phase 1 tests unchanged.
3. **Two promotion triggers** (the parent spec's Approach A, made complete):
   - **`__getattr__`** fires on a missing *plain* attribute (`META`, `GET`, `POST`,
     `COOKIES`, `FILES`, `session`, `user`, ...) and promotes (recursion-guarded).
   - **Bounded explicit overrides** for the Django attributes that are *properties or
     methods on the `HttpRequest` class* and therefore never trigger `__getattr__`:
     `body`, `headers`, `encoding`, `scheme`, `is_secure`, `get_host`, `get_port`,
     `build_absolute_uri`, `read`, `readline`, `__iter__`. Each ensures promotion, then
     delegates to the `HttpRequest` implementation. This closes the property-trap the
     parent spec flagged as the core risk.
4. **Fast path is unchanged.** `method`, `path`, `path_params`, `get_header`,
   `query_param` are served from the core (or plain attrs) and never promote. Phase 1's
   endpoints stay on the C path.
5. **Settings bootstrap.** Promotion and the ORM require configured Django settings
   (`QueryDict`, `get_host`, etc. read `settings`). `__main__`/`serve` calls
   `django.setup()` when `DJANGO_SETTINGS_MODULE` is set; promotion raises a clear
   `ImproperlyConfigured`-style error if settings are unconfigured. Fast-path-only apps
   still run without settings (Phase 1 behavior preserved).
6. **Scope deferrals.** `request.user`/`session`/auth belong to Phase 3 (middleware), so
   they are not populated by promotion here (accessing them after promotion raises, as
   on a stock request with no auth middleware). Multipart `FILES` parity is a documented
   limitation for Phase 2 (urlencoded and JSON bodies are covered); full multipart
   parity is hardened later.
7. **Pinned Django versions.** Parity is validated against Django 5.2 and 6.0 (the
   supported matrix). `_promote()` mirrors `WSGIRequest` internals, so CI runs the
   parity suite on each supported Django.

## 3. Module changes

```
src/massless/
  _request.pyx   # MasslessRequest: plain method/path attrs, _promote(), __getattr__,
                 #   bounded property/method overrides; RequestCore gains a body field
  app.py         # unchanged surface; views may now touch Django state / ORM
  __main__.py    # optional django.setup() when DJANGO_SETTINGS_MODULE is set
```

`RequestCore` already holds method/path/query/headers; Phase 2 ensures it also carries
the **body bytes** (the protocol passes the parsed body through), since `_promote()`
needs them to build `wsgi.input`.

## 4. The promotion mechanism

```python
class MasslessRequest(HttpRequest):
    def __init__(self, core, path_params):
        self._core = core
        self.path_params = path_params
        self.method = core.method        # plain attrs (fast path, no promotion)
        self.path = core.path
        self._is_django = False

    def get_header(self, name):  return self._core.get_header(name)
    def query_param(self, name): return self._core.query_param(name)

    # --- promotion ---
    def _ensure_promoted(self):
        if not self._is_django:
            self._promote()
            self._is_django = True

    def _promote(self):
        environ = self._build_wsgi_environ()   # from self._core buffers
        WSGIRequest.__init__(self, environ)     # Django populates META/GET/body/...

    def __getattr__(self, name):
        # Only called on a miss. Guard against recursion and post-promotion misses.
        if name.startswith("_") or self.__dict__.get("_is_django"):
            raise AttributeError(name)
        self._promote()
        self._is_django = True
        return object.__getattribute__(self, name)

    # --- bounded overrides for property/method attrs that bypass __getattr__ ---
    @property
    def body(self):
        self._ensure_promoted()
        return HttpRequest.body.fget(self)

    def get_host(self):
        self._ensure_promoted()
        return HttpRequest.get_host(self)
    # ... same pattern for headers, encoding, scheme, is_secure, get_port,
    #     build_absolute_uri, read, readline, __iter__
```

`_build_wsgi_environ()` maps the core to a WSGI environ:

| environ key | source |
|-------------|--------|
| `REQUEST_METHOD` | `core.method` |
| `PATH_INFO` | `core.path` |
| `QUERY_STRING` | raw query bytes |
| `CONTENT_TYPE` | `Content-Type` header |
| `CONTENT_LENGTH` | `len(body)` |
| `HTTP_*` | each request header, upper-cased, `-`→`_`, prefixed `HTTP_` (except Content-Type/Length) |
| `wsgi.input` | `io.BytesIO(body)` |
| `SERVER_NAME` / `SERVER_PORT` | from `Host` header (or defaults) |
| `SERVER_PROTOCOL` | `HTTP/1.1` |
| `wsgi.url_scheme` | `http` (Phase 2 has no TLS termination info) |
| `REMOTE_ADDR` | placeholder until the protocol threads the peer address (later phase) |

## 5. Django glue

- **Settings bootstrap:** `__main__.main()` calls `django.setup()` if
  `DJANGO_SETTINGS_MODULE` is set; otherwise it serves fast-path-only (no promotion).
- **ORM:** with settings configured and `django.setup()` done, async views may use the
  Django ORM (`async for`, `aget`, etc.) exactly as in stock async Django. No special
  glue beyond settings; the ORM remains sync-driver-on-a-thread (design §1).
- **User model loading:** `get_user_model()` resolves once apps are loaded; this is what
  "user-model loading" in the parent Phase 2 description means. `request.user` (the
  per-request authenticated user) is Phase 3.

## 6. Testing strategy

- **Parity suite (the keystone test).** A table of raw HTTP requests (GET with query;
  POST urlencoded; POST JSON; with cookies; with assorted headers). For each: build a
  stock `WSGIRequest` from the same environ and a promoted `MasslessRequest` from the
  same bytes, then assert equality of `method`, `path`, `GET`, `POST`, `body`,
  `COOKIES`, `content_type`, `content_params`, `encoding`, `headers`, `get_host()`,
  `scheme`, and the `META` subset we construct. Property-based where practical.
- **Trigger coverage.** A test per override (`body`, `headers`, `get_host`, ...) asserting
  it promotes on first access (probe `_is_django` flips) and returns the correct value.
- **No-promotion regression.** The Phase 1 test still passes: the 4 bench endpoints never
  promote.
- **ORM end-to-end.** A view that runs an async ORM query (against the test sqlite DB)
  returns correct data through the real server (uses `pytest-django` + the test settings).
- **Idempotent promotion.** Promoting twice is a no-op; accessing many Django attrs
  promotes exactly once.

## 7. Out of scope for Phase 2

`request.user`/`session`/auth (Phase 3); real Django middleware chain (Phase 3);
multipart `FILES` parsing parity; sync views / thread-pool dispatch (Phase 4); the peer
address in `REMOTE_ADDR`; HTTPS/`wsgi.url_scheme=https`.

## 8. Risks

- **HttpRequest parity drift** (the project's biggest correctness task). Mitigated by
  reusing `WSGIRequest.__init__` (Django does the work) and the attribute-by-attribute
  parity suite run on each supported Django version.
- **Property-trap completeness.** If a view uses a Django property/method not in the
  override list, it runs against unset state and fails rather than promoting. Mitigated
  by covering the common surface and documenting the list; new entries are cheap to add.
- **`__getattr__` recursion.** Guarded by the `_`-prefix / `_is_django` check and
  `object.__getattribute__` for the post-promotion fetch.
