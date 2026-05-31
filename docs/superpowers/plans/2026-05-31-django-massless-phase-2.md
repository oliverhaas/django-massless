# django-massless Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Lazily, one-shot promote a `MasslessRequest` into a fully-functional Django `HttpRequest` (reconstructed from the `RequestCore` C buffers) so real Django views and the ORM work, while the Phase 1 fast path still never promotes.

**Architecture:** `_promote()` builds a WSGI environ from the core and calls `WSGIRequest.__init__(self, environ)` (reuse Django's own construction for parity). Promotion is triggered by `__getattr__` (missing plain attrs) plus a bounded set of property/method overrides (`body`, `headers`, `get_host`, ...) that otherwise bypass `__getattr__`.

**Tech Stack:** Cython 3.2, Django (`WSGIRequest`), msgspec, pytest, pytest-django.

**Spec:** [docs/superpowers/specs/2026-05-31-django-massless-phase-2-design.md](../specs/2026-05-31-django-massless-phase-2-design.md)

---

## Conventions

Same as Phase 1: after editing any `.pyx`/`.pxd` run `uv sync --reinstall-package django-massless` before testing. Gates: `uv run pytest -n auto`, `uv run ruff check`, `uv run mypy src/massless/`. Commit per task; pre-commit hooks may reformat (re-stage, commit again). Tests run under pytest-django with `DJANGO_SETTINGS_MODULE=settings.base`, so Django settings are configured in the test process.

## File Structure

| File | Change |
|------|--------|
| `src/massless/_request.pyx` + `_request.pxd` | RequestCore gains `body`; MasslessRequest gets plain method/path attrs, `_promote`, `__getattr__`, overrides |
| `src/massless/_protocol.pyx` | pass the parsed body into `RequestCore.create` |
| `src/massless/__main__.py` | optional `django.setup()` when `DJANGO_SETTINGS_MODULE` set |
| `tests/test_request.py` | promotion + override + idempotency tests |
| `tests/test_parity.py` | the attribute-by-attribute parity suite |
| `tests/test_promotion_orm.py` | ORM-through-promoted-request test |
| `benchmarks/app.py` | add a `/promote-demo` endpoint that touches `request.META` (for a promotion-cost benchmark) |

---

## Task 1: RequestCore carries the body

**Files:** `src/massless/_request.pxd`, `_request.pyx`, `_protocol.pyx`; `tests/test_request.py`

- [ ] **Step 1: Failing test**

```python
# add to tests/test_request.py
def test_core_exposes_body():
    core = RequestCore.py_create(b"POST", b"/x", b"", [(b"content-type", b"application/json")], b'{"a":1}')
    assert core.body == b'{"a":1}'
```

- [ ] **Step 2: Run, expect fail** (`py_create` takes no body yet / `body` missing).

- [ ] **Step 3: Implement.** In `_request.pxd` add `cdef bytes _body` to `RequestCore` and update the `create` signature to accept `bytes body`. In `_request.pyx`: `create` and `py_create` take `body`, store `self._body = body`, and add a `body` property returning `self._body`. In `_protocol.pyx`, the collector already has access to the body via httptools `on_body`; capture it (add `on_body` appending to a per-message buffer, snapshot into the request tuple) and pass it to `RequestCore.create(method, path, query, headers, body)`. Default body to `b""` when absent. Update `parse_request` and `dispatch` call sites accordingly.

- [ ] **Step 4: Rebuild + test.** `uv sync --reinstall-package django-massless && uv run pytest tests/test_request.py tests/test_protocol.py -v` → green.

- [ ] **Step 5: Commit** `feat(request): RequestCore carries request body`.

---

## Task 2: MasslessRequest plain method/path attributes

**Files:** `src/massless/_request.pyx`; `tests/test_request.py`

- [ ] **Step 1: Failing test**

```python
# add to tests/test_request.py
def test_method_path_are_plain_attributes_and_settable():
    core = RequestCore.py_create(b"GET", b"/items/5", b"", [], b"")
    req = MasslessRequest(core, {})
    assert req.method == "GET"
    assert req.path == "/items/5"
    req.path = "/changed"   # plain attr: assignable (read-only property would raise)
    assert req.path == "/changed"
```

- [ ] **Step 2: Run, expect fail** (`path` is a read-only property in Phase 1 → assignment raises).

- [ ] **Step 3: Implement.** In `MasslessRequest.__init__` set `self.method = core.method`, `self.path = core.path` as plain attrs; remove the `method`/`path` `property(...)` definitions. Initialize `self._is_django = False`. Keep `get_header`/`query_param` delegating to `_core`.

- [ ] **Step 4: Rebuild + test.** Existing Phase 1 request tests + the new one pass.

- [ ] **Step 5: Commit** `refactor(request): method/path as plain attrs (promotable)`.

---

## Task 3: Build a WSGI environ from the core

**Files:** `src/massless/_request.pyx`; `tests/test_request.py`

- [ ] **Step 1: Failing test**

```python
# add to tests/test_request.py
def test_build_wsgi_environ_maps_core():
    core = RequestCore.py_create(
        b"POST", b"/items/5", b"q=hi",
        [(b"host", b"example.com:9000"), (b"content-type", b"application/json"), (b"x-test", b"v")],
        b'{"a":1}',
    )
    req = MasslessRequest(core, {})
    env = req._build_wsgi_environ()
    assert env["REQUEST_METHOD"] == "POST"
    assert env["PATH_INFO"] == "/items/5"
    assert env["QUERY_STRING"] == "q=hi"
    assert env["CONTENT_TYPE"] == "application/json"
    assert env["CONTENT_LENGTH"] == "7"
    assert env["HTTP_X_TEST"] == "v"
    assert env["SERVER_NAME"] == "example.com" and env["SERVER_PORT"] == "9000"
    assert env["wsgi.input"].read() == b'{"a":1}'
```

- [ ] **Step 2: Run, expect fail.**

- [ ] **Step 3: Implement** `_build_wsgi_environ` on `MasslessRequest`:

```python
import io

def _build_wsgi_environ(self):
    core = self._core
    body = core.body
    headers = core.headers_list()  # list[tuple[bytes,bytes]] lower-cased (add this accessor on RequestCore)
    host = b""
    environ = {
        "REQUEST_METHOD": core.method.decode("ascii") if isinstance(core.method, bytes) else self.method,
        "PATH_INFO": self.path,
        "QUERY_STRING": core.query_string(),       # add: raw query bytes decoded latin1
        "SERVER_PROTOCOL": "HTTP/1.1",
        "wsgi.input": io.BytesIO(body),
        "wsgi.url_scheme": "http",
        "CONTENT_LENGTH": str(len(body)),
    }
    for name, value in headers:
        n = name.decode("latin1")
        v = value.decode("latin1")
        if n == "content-type":
            environ["CONTENT_TYPE"] = v
        elif n == "content-length":
            environ["CONTENT_LENGTH"] = v
        else:
            environ["HTTP_" + n.upper().replace("-", "_")] = v
        if n == "host":
            host = value
    server_name, _, server_port = host.decode("latin1").partition(":")
    environ["SERVER_NAME"] = server_name or "localhost"
    environ["SERVER_PORT"] = server_port or "80"
    return environ
```

Add the small accessors this needs to `RequestCore` (`headers_list()` returning the lower-cased list, `query_string()` returning the decoded raw query) in `_request.pyx`. (The verify step will confirm exact method names; keep them consistent across tasks.)

- [ ] **Step 4: Rebuild + test.**

- [ ] **Step 5: Commit** `feat(request): build WSGI environ from the core`.

---

## Task 4: Promotion via WSGIRequest.__init__ + __getattr__

**Files:** `src/massless/_request.pyx`; `tests/test_request.py`

- [ ] **Step 1: Failing test**

```python
# add to tests/test_request.py
def test_promote_populates_django_state():
    core = RequestCore.py_create(b"GET", b"/items/5", b"q=hi", [(b"host", b"ex.com")], b"")
    req = MasslessRequest(core, {})
    assert req._is_django is False
    assert req.GET["q"] == "hi"            # __getattr__ miss -> promote
    assert req._is_django is True
    assert req.META["REQUEST_METHOD"] == "GET"

def test_promotion_is_idempotent():
    core = RequestCore.py_create(b"GET", b"/", b"", [(b"host", b"ex.com")], b"")
    req = MasslessRequest(core, {})
    _ = req.GET
    meta1 = req.META
    _ = req.COOKIES
    assert req.META is meta1               # not rebuilt
```

- [ ] **Step 2: Run, expect fail.**

- [ ] **Step 3: Implement.** Add to `MasslessRequest`:

```python
from django.core.handlers.wsgi import WSGIRequest

def _ensure_promoted(self):
    if not self._is_django:
        self._promote()

def _promote(self):
    WSGIRequest.__init__(self, self._build_wsgi_environ())
    self._is_django = True

def __getattr__(self, name):
    # Called only on a normal-lookup miss.
    if name.startswith("_") or self.__dict__.get("_is_django"):
        raise AttributeError(name)
    self._promote()
    return object.__getattribute__(self, name)
```

Note: `WSGIRequest.__init__` sets `self.environ`, `self.path`, `self.META`, `self.GET` (lazy), `self.COOKIES`, `self._read_started`, `self.resolver_match`, etc. It reassigns `self.path`/`self.method` (now plain attrs, so assignment works).

- [ ] **Step 4: Rebuild + test.** New tests + the Phase 1 no-promotion test pass.

- [ ] **Step 5: Commit** `feat(request): lazy one-shot promotion to a real HttpRequest`.

---

## Task 5: Bounded property/method overrides (close the property-trap)

**Files:** `src/massless/_request.pyx`; `tests/test_request.py`

- [ ] **Step 1: Failing test**

```python
# add to tests/test_request.py
import pytest

@pytest.mark.parametrize("access", [
    lambda r: r.body,
    lambda r: r.headers["X-Test"],
    lambda r: r.get_host(),
    lambda r: r.scheme,
])
def test_property_access_promotes(access):
    core = RequestCore.py_create(b"GET", b"/", b"", [(b"host", b"ex.com"), (b"x-test", b"v")], b"")
    req = MasslessRequest(core, {})
    access(req)
    assert req._is_django is True

def test_body_returns_bytes_after_promote():
    core = RequestCore.py_create(b"POST", b"/", b"", [(b"host", b"ex.com"), (b"content-type", b"text/plain")], b"hello")
    req = MasslessRequest(core, {})
    assert req.body == b"hello"
```

- [ ] **Step 2: Run, expect fail** (`body`/`headers`/`get_host`/`scheme` run against unset state, or don't promote).

- [ ] **Step 3: Implement** the bounded overrides on `MasslessRequest`. Properties delegate via the descriptor; methods via the unbound call:

```python
@property
def body(self):
    self._ensure_promoted(); return HttpRequest.body.fget(self)

@property
def encoding(self):
    self._ensure_promoted(); return HttpRequest.encoding.fget(self)

@encoding.setter
def encoding(self, value):
    self._ensure_promoted(); HttpRequest.encoding.fset(self, value)

@property
def headers(self):
    self._ensure_promoted(); return HttpRequest.headers.fget(self)

@property
def scheme(self):
    self._ensure_promoted(); return HttpRequest.scheme.fget(self)

def get_host(self):       self._ensure_promoted(); return HttpRequest.get_host(self)
def get_port(self):       self._ensure_promoted(); return HttpRequest.get_port(self)
def is_secure(self):      self._ensure_promoted(); return HttpRequest.is_secure(self)
def build_absolute_uri(self, location=None):
    self._ensure_promoted(); return HttpRequest.build_absolute_uri(self, location)
def read(self, *a, **k):  self._ensure_promoted(); return HttpRequest.read(self, *a, **k)
def readline(self, *a, **k): self._ensure_promoted(); return HttpRequest.readline(self, *a, **k)
def __iter__(self):       self._ensure_promoted(); return HttpRequest.__iter__(self)
```

Note: `headers` is a `cached_property` on `HttpRequest`; access via `HttpRequest.headers.func(self)` if `.fget` is unavailable. The verify step pins the exact descriptor accessor per Django version.

- [ ] **Step 4: Rebuild + test.**

- [ ] **Step 5: Commit** `feat(request): promote on property/method access (close the trap)`.

---

## Task 6: Parity test suite (the keystone)

**Files:** `tests/test_parity.py`

- [ ] **Step 1: Write the parity suite.** For each raw request, build a stock `WSGIRequest` from an equivalent environ and a promoted `MasslessRequest` from the core, and assert equality across the supported surface.

```python
# tests/test_parity.py
import io

import pytest
from django.core.handlers.wsgi import WSGIRequest

from massless._request import MasslessRequest, RequestCore

CASES = [
    (b"GET", b"/items/5", b"q=hi&n=3", [(b"host", b"ex.com")], b""),
    (b"POST", b"/submit", b"", [(b"host", b"ex.com"), (b"content-type", b"application/x-www-form-urlencoded")], b"a=1&b=2"),
    (b"POST", b"/api", b"", [(b"host", b"ex.com"), (b"content-type", b"application/json")], b'{"a":1}'),
    (b"GET", b"/", b"", [(b"host", b"ex.com:8080"), (b"cookie", b"sid=abc; theme=dark")], b""),
]


def _stock(method, path, query, headers, body):
    env = {
        "REQUEST_METHOD": method.decode(), "PATH_INFO": path.decode(),
        "QUERY_STRING": query.decode(), "wsgi.input": io.BytesIO(body),
        "CONTENT_LENGTH": str(len(body)), "SERVER_PROTOCOL": "HTTP/1.1",
        "wsgi.url_scheme": "http", "SERVER_NAME": "localhost", "SERVER_PORT": "80",
    }
    for n, v in headers:
        n = n.decode(); v = v.decode()
        if n == "content-type": env["CONTENT_TYPE"] = v
        elif n == "host":
            sn, _, sp = v.partition(":"); env["SERVER_NAME"] = sn; env["SERVER_PORT"] = sp or "80"
        else: env["HTTP_" + n.upper().replace("-", "_")] = v
    return WSGIRequest(env)


@pytest.mark.parametrize("case", CASES)
def test_promoted_matches_stock(case):
    stock = _stock(*case)
    req = MasslessRequest(RequestCore.py_create(*case), {})
    req._promote()
    assert req.method == stock.method
    assert req.path == stock.path
    assert dict(req.GET) == dict(stock.GET)
    assert dict(req.POST) == dict(stock.POST)
    assert req.body == stock.body
    assert req.COOKIES == stock.COOKIES
    assert req.content_type == stock.content_type
    assert req.content_params == stock.content_params
    assert req.get_host() == stock.get_host()
    assert dict(req.headers) == dict(stock.headers)
    assert req.encoding == stock.encoding
```

- [ ] **Step 2: Run.** Expect failures revealing any environ/promotion gaps; fix `_build_wsgi_environ`/`_promote` until every case matches stock.

- [ ] **Step 3: Commit** `test(parity): promoted MasslessRequest matches stock WSGIRequest`.

---

## Task 7: Settings bootstrap in the runner

**Files:** `src/massless/__main__.py`

- [ ] **Step 1: Implement.** In `main()`, before serving, if `os.environ.get("DJANGO_SETTINGS_MODULE")` is set, call `django.setup()` so promotion + ORM work. If unset, serve fast-path-only (no change). Add a `--settings` flag that sets `DJANGO_SETTINGS_MODULE` then calls `django.setup()`.

```python
def _bootstrap_django(settings_module: str | None) -> None:
    import os
    if settings_module:
        os.environ["DJANGO_SETTINGS_MODULE"] = settings_module
    if os.environ.get("DJANGO_SETTINGS_MODULE"):
        import django
        django.setup()
```

Call `_bootstrap_django(args.settings)` in `main()` after parsing args.

- [ ] **Step 2: Test.** `uv run python -m massless --help` shows `--settings`; ruff/mypy green. (Runner serving is covered by integration tests.)

- [ ] **Step 3: Commit** `feat(runner): optional django.setup() bootstrap`.

---

## Task 8: ORM-through-promotion end-to-end + promotion-cost bench endpoint

**Files:** `tests/test_promotion_orm.py`, `benchmarks/app.py`

- [ ] **Step 1: Failing test.** A view that runs an async ORM query against the test DB, served through the real server.

```python
# tests/test_promotion_orm.py
import pytest
from django.contrib.auth import get_user_model


@pytest.mark.django_db
def test_view_can_use_orm_through_promoted_request(... reuse the integration server fixture ...):
    # register a view that does: count = await get_user_model().objects.acount(); return {"users": count}
    # hit it over the real server; assert 200 and the count is correct.
    ...
```

(Reuse/extend the `server` fixture from `tests/test_integration.py`; mark `django_db`; create a user with the ORM, then assert the endpoint returns the count.)

- [ ] **Step 2: Implement** by adding the ORM view to the fixture's API (no library code change needed; the ORM already works once settings are configured). Confirm green.

- [ ] **Step 3: Bench endpoint.** Add to `benchmarks/app.py` a `/promote-demo` endpoint that forces promotion by touching `request.META` (e.g. returns `{"host": request.get_host()}`), so the Phase 2 benchmark can measure promotion overhead vs the non-promoting path. (No DB; just promotion cost.)

- [ ] **Step 4: Commit** `test(orm): ORM works through a promoted request; add promote-demo bench endpoint`.

---

## Self-Review

(Run before handoff.) Spec coverage: promotion mechanism (§4) → Tasks 3-5; parity (§6) → Task 6; settings/ORM glue (§5) → Tasks 7-8; body in core → Task 1; fast-path preserved (method/path plain attrs, no-promotion test) → Tasks 2, 6. Confirm `_ensure_promoted`/`_promote`/`_build_wsgi_environ`/`headers_list`/`query_string` names are consistent across tasks. The bounded override list is the property-trap surface; note it in the spec if extended.
