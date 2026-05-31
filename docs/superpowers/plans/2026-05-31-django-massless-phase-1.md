# django-massless Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a single-process Cython/C request pipeline that serves JSON from native async views, touching no Python object except the view, at RPS competitive with single-process django-bolt.

**Architecture:** A uvloop-driven `asyncio.Protocol` feeds bytes to httptools, which fills a `cdef RequestCore` (C storage). A libcpp-backed router matches the path. At dispatch the core is wrapped in a `MasslessRequest` (a regular `HttpRequest` subclass), a per-route binder builds view kwargs, the async view is awaited, and the result is serialized by a C response builder and written to the socket. No promotion, no Django settings, no middleware.

**Tech Stack:** Cython 3.2 (C++), uvloop, httptools, msgspec, Django (subclassing only), pytest.

**Spec:** [docs/superpowers/specs/2026-05-31-django-massless-phase-1-design.md](../specs/2026-05-31-django-massless-phase-1-design.md)

---

## Conventions for every task

- **Cython rebuild:** after editing any `.pyx`/`.pxd`, run `uv sync --reinstall-package django-massless` before importing or testing it. setuptools editable installs do not auto-rebuild on `.pyx` changes. This is verified to rebuild and pick up edits.
- **Test run:** `uv run pytest tests/<file>::<test> -v` for one test; `uv run pytest -n auto` for the suite.
- **Hot-path modules are `.pyx`** (compiled): `_response.pyx`, `_router.pyx`, `_request.pyx`, `_protocol.pyx`. **Cold-path modules are plain `.py`** (interpreted, not cythonized): `app.py`, `__main__.py`, `__init__.py`. `setup.py` only cythonizes `src/massless/**/*.pyx`, so `.py` files are never compiled.
- **C++ modules** carry `# distutils: language = c++` as their first line.
- **Commits:** conventional, one per task minimum.
- **Formatting:** the pre-commit `ruff-format` hook normalizes files on commit, so the code blocks here need not be hand-formatted. If a commit aborts because a hook reformatted files, re-stage and commit again. CI runs `ruff format --check`, which passes once the hook has formatted the committed code.

## File Structure

| File | Responsibility |
|------|----------------|
| `pyproject.toml` | add uvloop/httptools/msgspec runtime deps |
| `src/massless/_response.pyx` | serialize view return to body bytes; assemble HTTP/1.1 response bytes |
| `src/massless/_router.pyx` + `_router.pxd` | compile routes; match path bytes to (route_id, int param) via libcpp map + dynamic list |
| `src/massless/_request.pyx` + `_request.pxd` | `cdef RequestCore` (C storage + fast-path accessors) and `MasslessRequest(HttpRequest)` wrapper |
| `src/massless/_protocol.pyx` | httptools parse to RequestCore; async dispatch; `MasslessProtocol` glue; write response |
| `src/massless/app.py` | `MasslessAPI`: `@api.get`, signature binder, route-table compile |
| `src/massless/__main__.py` | `python -m massless module:api --host --port` runner on uvloop |
| `src/massless/__init__.py` | re-export `MasslessAPI` |
| `benchmarks/app.py` | Phase 1 bench-app implementing the 4 framework-bound endpoints |
| `benchmarks/compare.py` | trim `CORE_KEYS` to the Phase 1 subset |
| `tests/test_response.py` | response serialization + assembly |
| `tests/test_router.py` | static + dynamic match |
| `tests/test_request.py` | RequestCore accessors; MasslessRequest delegation + no-promotion |
| `tests/test_binding.py` | signature binder |
| `tests/test_app.py` | MasslessAPI registration + router compile |
| `tests/test_protocol.py` | httptools->RequestCore; async dispatch->bytes |
| `tests/test_integration.py` | real uvloop server over real sockets; no-promotion assertion |

---

## Task 1: Add Phase 1 dependencies and tooling config

The compiled modules ship no type stubs, so mypy needs per-module overrides; the
benchmark app and tests trip `select = ["ALL"]` rules that must be ignored. Doing
this config up front keeps every later task green against the CI gates (ruff check,
ruff format --check, mypy).

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add runtime dependencies**

In `pyproject.toml`, replace the `dependencies` array:

```toml
dependencies = [
  "Django>=5.2,<7",
  "httptools>=0.6.4",
  "msgspec>=0.18",
  "uvloop>=0.21",
]
```

- [ ] **Step 2: Tell mypy the compiled extensions have no stubs**

Add to `pyproject.toml` (after the `[tool.django-stubs]` block):

```toml
[[tool.mypy.overrides]]
module = ["massless._router", "massless._request", "massless._response", "massless._protocol"]
ignore_missing_imports = true
```

- [ ] **Step 3: Extend ruff per-file-ignores**

In `pyproject.toml`, update `[tool.ruff.lint.per-file-ignores]` so the `tests/**`
list also includes `PLC0415`, `PLR2004`, `S310` (in-function imports, literal
asserts, and `urlopen` are fine in tests), and change the benchmarks entry to ignore
annotations too:

```toml
[tool.ruff.lint.per-file-ignores]
"tests/**" = [
  "ANN", "ARG", "F841", "FBT", "PLC0415", "PLR2004", "PT006", "PT011",
  "PT013", "PT018", "S101", "S105", "S310",
]
# Benchmark CLI scripts and apps: print is their output; views need no annotations.
"benchmarks/**" = ["ANN", "T201"]
```

- [ ] **Step 4: Sync (no rebuild needed; no compiled sources exist yet)**

Run: `uv sync --group dev`
Expected: resolves and installs uvloop, httptools, msgspec.

- [ ] **Step 5: Verify imports and config**

Run: `uv run python -c "import uvloop, httptools, msgspec; print('ok')" && uv run ruff check && uv run mypy src/massless/`
Expected: `ok`, then ruff and mypy both clean.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "feat: add Phase 1 runtime deps and tooling config"
```

---

## Task 2: Response body serialization

**Files:**
- Create: `src/massless/_response.pyx`
- Test: `tests/test_response.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_response.py
from massless import _response


def test_serialize_dict_is_json():
    body, ctype = _response.serialize_body({"message": "Hello World"})
    assert body == b'{"message":"Hello World"}'
    assert ctype == b"application/json"


def test_serialize_list_is_json():
    body, ctype = _response.serialize_body([1, 2, 3])
    assert body == b"[1,2,3]"
    assert ctype == b"application/json"


def test_serialize_str_is_text():
    body, ctype = _response.serialize_body("hi")
    assert body == b"hi"
    assert ctype == b"text/plain; charset=utf-8"


def test_serialize_bytes_passthrough():
    body, ctype = _response.serialize_body(b"\x00\x01")
    assert body == b"\x00\x01"
    assert ctype == b"application/octet-stream"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_response.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'massless._response'`

- [ ] **Step 3: Write minimal implementation**

```cython
# src/massless/_response.pyx
import msgspec


cpdef tuple serialize_body(object obj):
    """Return (body_bytes, content_type_bytes) for a view return value."""
    if isinstance(obj, bytes):
        return obj, b"application/octet-stream"
    if isinstance(obj, str):
        return (<str>obj).encode("utf-8"), b"text/plain; charset=utf-8"
    return msgspec.json.encode(obj), b"application/json"
```

- [ ] **Step 4: Rebuild and run**

Run: `uv sync --reinstall-package django-massless && uv run pytest tests/test_response.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/massless/_response.pyx tests/test_response.py
git commit -m "feat: response body serialization (msgspec/str/bytes)"
```

---

## Task 3: HTTP response assembly

**Files:**
- Modify: `src/massless/_response.pyx`
- Test: `tests/test_response.py`

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_response.py
def test_build_http_response_200_keepalive():
    raw = _response.build_http_response(200, b"application/json", b'{"a":1}', True)
    assert raw == (
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Type: application/json\r\n"
        b"Content-Length: 7\r\n"
        b"Connection: keep-alive\r\n"
        b"\r\n"
        b'{"a":1}'
    )


def test_build_http_response_404_close():
    raw = _response.build_http_response(404, b"text/plain; charset=utf-8", b"nope", False)
    assert raw.startswith(b"HTTP/1.1 404 Not Found\r\n")
    assert b"Connection: close\r\n" in raw
    assert raw.endswith(b"\r\n\r\nnope")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_response.py::test_build_http_response_200_keepalive -v`
Expected: FAIL with `AttributeError: module 'massless._response' has no attribute 'build_http_response'`

- [ ] **Step 3: Write minimal implementation**

Add to `src/massless/_response.pyx`:

```cython
cdef dict _REASON = {200: b"OK", 404: b"Not Found", 422: b"Unprocessable Entity", 500: b"Internal Server Error"}


cpdef bytes build_http_response(int status, bytes content_type, bytes body, bint keep_alive):
    cdef bytes reason = _REASON.get(status, b"OK")
    cdef bytes conn = b"keep-alive" if keep_alive else b"close"
    return (
        b"HTTP/1.1 " + str(status).encode("ascii") + b" " + reason + b"\r\n" +
        b"Content-Type: " + content_type + b"\r\n" +
        b"Content-Length: " + str(len(body)).encode("ascii") + b"\r\n" +
        b"Connection: " + conn + b"\r\n\r\n" +
        body
    )
```

- [ ] **Step 4: Rebuild and run**

Run: `uv sync --reinstall-package django-massless && uv run pytest tests/test_response.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/massless/_response.pyx tests/test_response.py
git commit -m "feat: HTTP/1.1 response assembly"
```

---

## Task 4: Router static match

**Files:**
- Create: `src/massless/_router.pxd`, `src/massless/_router.pyx`
- Test: `tests/test_router.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_router.py
from massless._router import Router


def test_static_hit_returns_route_id_and_no_param():
    r = Router()
    r.add_static(b"/", 0)
    r.add_static(b"/10k-json", 1)
    assert r.match(b"/") == (0, -1)
    assert r.match(b"/10k-json") == (1, -1)


def test_static_miss_returns_minus_one():
    r = Router()
    r.add_static(b"/", 0)
    assert r.match(b"/nope") == (-1, -1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_router.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'massless._router'`

- [ ] **Step 3: Write the declarations**

```cython
# src/massless/_router.pxd
# distutils: language = c++
from libcpp.string cimport string
from libcpp.unordered_map cimport unordered_map


cdef struct MatchResult:
    int route_id
    long param


cdef class Router:
    cdef unordered_map[string, int] _static
    cdef list _dynamic
    cdef MatchResult match_c(self, bytes path) except *
```

- [ ] **Step 4: Write the implementation**

```cython
# src/massless/_router.pyx
# distutils: language = c++
from cython.operator cimport dereference as deref
from libcpp.string cimport string


cdef class Router:
    def __cinit__(self):
        self._dynamic = []

    def add_static(self, bytes path, int route_id):
        self._static[<string>path] = route_id

    def add_dynamic(self, bytes prefix, int route_id):
        # Matches `<prefix><int>`, e.g. prefix b"/items/" matches b"/items/123".
        self._dynamic.append((prefix, route_id))

    cdef MatchResult match_c(self, bytes path) except *:
        cdef MatchResult result
        result.route_id = -1
        result.param = -1
        cdef string key = <string>path
        cdef unordered_map[string, int].iterator it = self._static.find(key)
        if it != self._static.end():
            result.route_id = deref(it).second
            return result
        cdef bytes prefix
        cdef int rid
        cdef bytes tail
        for prefix, rid in self._dynamic:
            if path.startswith(prefix):
                tail = path[len(prefix):]
                if tail.isdigit():
                    result.route_id = rid
                    result.param = int(tail)
                    return result
        return result

    def match(self, bytes path):
        cdef MatchResult r = self.match_c(path)
        return (r.route_id, r.param)
```

> **Note:** in Phase 1 `match_c` holds the GIL (the `bytes`→`std::string` conversion, the
> Python-list dynamic scan, `isdigit()`, and `int()` are all GIL-bound). That is fine here
> (dispatch holds the GIL anyway, and at this route count the map lookup is already C-speed).
> A true `nogil` match over a C buffer is a later optimization once route tables are large.

- [ ] **Step 5: Rebuild and run**

Run: `uv sync --reinstall-package django-massless && uv run pytest tests/test_router.py -v`
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add src/massless/_router.pyx src/massless/_router.pxd tests/test_router.py
git commit -m "feat: router static match (libcpp unordered_map)"
```

---

## Task 5: Router dynamic int-param match

**Files:**
- Test: `tests/test_router.py` (implementation already present from Task 4; this task proves and locks the dynamic path)

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_router.py
def test_dynamic_hit_captures_int():
    r = Router()
    r.add_dynamic(b"/items/", 2)
    assert r.match(b"/items/12345") == (2, 12345)


def test_dynamic_non_int_segment_is_miss():
    r = Router()
    r.add_dynamic(b"/items/", 2)
    assert r.match(b"/items/abc") == (-1, -1)


def test_static_wins_over_dynamic():
    r = Router()
    r.add_static(b"/items/active", 9)
    r.add_dynamic(b"/items/", 2)
    assert r.match(b"/items/active") == (9, -1)
```

- [ ] **Step 2: Run tests**

Run: `uv run pytest tests/test_router.py -v`
Expected: 5 passed (static is tried before dynamic, so `test_static_wins_over_dynamic` passes with the Task 4 implementation).

- [ ] **Step 3: Commit**

```bash
git add tests/test_router.py
git commit -m "test: router dynamic int-param match and static precedence"
```

---

## Task 6: RequestCore

**Files:**
- Create: `src/massless/_request.pxd`, `src/massless/_request.pyx`
- Test: `tests/test_request.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_request.py
from massless._request import RequestCore


def test_core_method_and_path():
    core = RequestCore.py_create(b"GET", b"/items/12345", b"q=hello", [(b"x-test", b"val")])
    assert core.method == "GET"
    assert core.path == "/items/12345"


def test_core_get_header_case_insensitive():
    core = RequestCore.py_create(b"GET", b"/", b"", [(b"X-Test", b"val")])
    assert core.get_header("x-test") == "val"
    assert core.get_header("missing") is None


def test_core_query_param():
    core = RequestCore.py_create(b"GET", b"/", b"q=hello&n=3", [])
    assert core.query_param("q") == "hello"
    assert core.query_param("n") == "3"
    assert core.query_param("absent") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_request.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'massless._request'`

- [ ] **Step 3: Write the declarations**

```cython
# src/massless/_request.pxd
cdef class RequestCore:
    cdef bytes _method
    cdef bytes _path
    cdef bytes _query
    cdef list _headers          # list[tuple[bytes, bytes]], lower-cased names
    cdef dict _query_cache       # parsed lazily

    @staticmethod
    cdef RequestCore create(bytes method, bytes path, bytes query, list headers)
```

- [ ] **Step 4: Write the implementation**

```cython
# src/massless/_request.pyx
from urllib.parse import parse_qs


cdef class RequestCore:
    @staticmethod
    cdef RequestCore create(bytes method, bytes path, bytes query, list headers):
        cdef RequestCore c = RequestCore.__new__(RequestCore)
        c._method = method
        c._path = path
        c._query = query
        c._headers = [(name.lower(), value) for name, value in headers]
        c._query_cache = None
        return c

    @staticmethod
    def py_create(bytes method, bytes path, bytes query, list headers):
        # Python-callable wrapper for tests.
        return RequestCore.create(method, path, query, headers)

    @property
    def method(self):
        return self._method.decode("ascii")

    @property
    def path(self):
        return self._path.decode("latin1")

    def get_header(self, str name):
        cdef bytes target = name.lower().encode("latin1")
        cdef bytes hname
        cdef bytes hvalue
        for hname, hvalue in self._headers:
            if hname == target:
                return hvalue.decode("latin1")
        return None

    def query_param(self, str name):
        if self._query_cache is None:
            self._query_cache = parse_qs(self._query.decode("latin1"))
        values = self._query_cache.get(name)
        return values[0] if values else None
```

- [ ] **Step 5: Rebuild and run**

Run: `uv sync --reinstall-package django-massless && uv run pytest tests/test_request.py -v`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add src/massless/_request.pyx src/massless/_request.pxd tests/test_request.py
git commit -m "feat: RequestCore C storage with fast-path accessors"
```

---

## Task 7: MasslessRequest wrapper

**Files:**
- Modify: `src/massless/_request.pyx`
- Test: `tests/test_request.py`

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_request.py
from django.http import HttpRequest
from massless._request import RequestCore, MasslessRequest


def test_wrapper_delegates_and_is_httprequest():
    core = RequestCore.py_create(b"GET", b"/items/12345", b"q=hi", [(b"x-test", b"v")])
    req = MasslessRequest(core, {"item_id": 12345})
    assert isinstance(req, HttpRequest)
    assert req.method == "GET"
    assert req.path == "/items/12345"
    assert req.path_params == {"item_id": 12345}
    assert req.get_header("x-test") == "v"


def test_wrapper_does_not_promote_on_fast_path():
    core = RequestCore.py_create(b"GET", b"/", b"", [])
    req = MasslessRequest(core, {})
    # Touching a Django-machinery attribute must raise (no promotion in Phase 1).
    import pytest
    with pytest.raises(AttributeError):
        _ = req.GET
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_request.py::test_wrapper_delegates_and_is_httprequest -v`
Expected: FAIL with `ImportError: cannot import name 'MasslessRequest'`

- [ ] **Step 3: Write the implementation**

Add to `src/massless/_request.pyx` (a regular Python class; it cannot be a `cdef class` because `HttpRequest` is a pure-Python class):

```cython
from django.http import HttpRequest


class MasslessRequest(HttpRequest):
    """Regular HttpRequest subclass backed by a RequestCore. No HttpRequest.__init__
    call, so Django-machinery attrs are absent until promotion (Phase 2)."""

    def __init__(self, core, path_params):
        self._core = core
        self.path_params = path_params

    method = property(lambda self: self._core.method)
    path = property(lambda self: self._core.path)

    def get_header(self, name):
        return self._core.get_header(name)

    def query_param(self, name):
        return self._core.query_param(name)
```

- [ ] **Step 4: Rebuild and run**

Run: `uv sync --reinstall-package django-massless && uv run pytest tests/test_request.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/massless/_request.pyx tests/test_request.py
git commit -m "feat: MasslessRequest HttpRequest-subclass wrapper over RequestCore"
```

---

## Task 8: Signature binder

**Files:**
- Create: `src/massless/app.py`
- Test: `tests/test_binding.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_binding.py
from massless.app import build_binder


def test_binder_coerces_path_int_and_query_str():
    async def view(item_id: int, q: str | None = None):
        return {"item_id": item_id, "q": q}

    binder = build_binder(view)
    kwargs = binder({"item_id": 12345}, lambda name: "hello" if name == "q" else None)
    assert kwargs == {"item_id": 12345, "q": "hello"}


def test_binder_optional_query_defaults_none():
    async def view(item_id: int, q: str | None = None):
        return {}

    binder = build_binder(view)
    kwargs = binder({"item_id": 1}, lambda name: None)
    assert kwargs == {"item_id": 1, "q": None}


def test_binder_no_params():
    async def view():
        return {}

    binder = build_binder(view)
    assert binder({}, lambda name: None) == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_binding.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'massless.app'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/massless/app.py
"""Cold-path app API: registration, signature binding, route-table compile."""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


def build_binder(view: Callable) -> Callable[[dict, Callable], dict]:
    """Inspect a view signature and return binder(path_params, query_getter) -> kwargs.

    Path params present in path_params are coerced by annotation (int -> int).
    Remaining params are read from query_getter(name); missing optionals become None.
    """
    sig = inspect.signature(view)
    params = list(sig.parameters.values())

    def binder(path_params: dict, query_getter: Callable) -> dict:
        kwargs: dict = {}
        for p in params:
            if p.name in path_params:
                raw = path_params[p.name]
                kwargs[p.name] = int(raw) if p.annotation is int else raw
            else:
                value = query_getter(p.name)
                if value is None and p.default is not inspect.Parameter.empty:
                    value = p.default
                kwargs[p.name] = value
        return kwargs

    return binder
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_binding.py -v`
Expected: 3 passed. (No rebuild needed: `app.py` is interpreted Python.)

- [ ] **Step 5: Commit**

```bash
git add src/massless/app.py tests/test_binding.py
git commit -m "feat: signature-based param binder"
```

---

## Task 9: MasslessAPI registration and router compile

**Files:**
- Modify: `src/massless/app.py`, `src/massless/__init__.py`
- Test: `tests/test_app.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_app.py
from massless.app import MasslessAPI


def test_register_and_compile_static_and_dynamic():
    api = MasslessAPI()

    @api.get("/")
    async def root():
        return {"message": "Hello World"}

    @api.get("/items/{item_id}")
    async def item(item_id: int, q: str | None = None):
        return {"item_id": item_id, "q": q}

    router = api.build_router()
    assert router.match(b"/")[0] != -1
    rid, param = router.match(b"/items/12345")
    assert rid != -1 and param == 12345
    # The compiled route exposes its view and binder by id.
    route = api.routes[rid]
    assert route.view is item
    assert route.binder({"item_id": 12345}, lambda n: "x")["item_id"] == 12345
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_app.py -v`
Expected: FAIL with `ImportError: cannot import name 'MasslessAPI'`

- [ ] **Step 3: Write the implementation**

Add to `src/massless/app.py`:

```python
import re
from dataclasses import dataclass

from massless._router import Router

_PARAM_RE = re.compile(r"^(?P<prefix>/[^{}]*/)\{(?P<name>[a-zA-Z_][a-zA-Z0-9_]*)\}$")


@dataclass
class Route:
    path: str
    view: Callable
    binder: Callable
    is_dynamic: bool
    prefix: bytes
    param_name: str | None


class MasslessAPI:
    def __init__(self) -> None:
        self.routes: list[Route] = []

    def get(self, path: str) -> Callable:
        def decorator(view: Callable) -> Callable:
            self._register(path, view)
            return view

        return decorator

    def _register(self, path: str, view: Callable) -> None:
        binder = build_binder(view)
        match = _PARAM_RE.match(path)
        if match:
            route = Route(
                path=path, view=view, binder=binder, is_dynamic=True,
                prefix=match["prefix"].encode("latin1"), param_name=match["name"],
            )
        else:
            route = Route(
                path=path, view=view, binder=binder, is_dynamic=False,
                prefix=path.encode("latin1"), param_name=None,
            )
        self.routes.append(route)

    def build_router(self) -> Router:
        router = Router()
        for route_id, route in enumerate(self.routes):
            if route.is_dynamic:
                router.add_dynamic(route.prefix, route_id)
            else:
                router.add_static(route.prefix, route_id)
        return router
```

Replace `src/massless/__init__.py` body with:

```python
"""High-performance Django API framework with a Cython request pipeline that
defers Django object materialization until touched.
"""

from massless.app import MasslessAPI

__all__ = ["MasslessAPI"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_app.py -v`
Expected: 1 passed. (No rebuild needed for `app.py`/`__init__.py`; `_router` is already built.)

- [ ] **Step 5: Commit**

```bash
git add src/massless/app.py src/massless/__init__.py tests/test_app.py
git commit -m "feat: MasslessAPI registration and router compile"
```

---

## Task 10: Protocol (parse to RequestCore and async dispatch)

**Files:**
- Create: `src/massless/_protocol.pyx`
- Test: `tests/test_protocol.py`

This task has three units: an httptools parser that produces a `RequestCore`, an async `dispatch` that produces response bytes, and the `MasslessProtocol` glue. The first two are unit-tested here; the glue is exercised by the Task 11 integration test.

- [ ] **Step 1: Write the failing test (parse)**

```python
# tests/test_protocol.py
from massless._protocol import parse_request


def test_parse_get_request_to_core():
    raw = (
        b"GET /items/12345?q=hello HTTP/1.1\r\n"
        b"Host: x\r\n"
        b"X-Test: val\r\n"
        b"\r\n"
    )
    core = parse_request(raw)
    assert core.method == "GET"
    assert core.path == "/items/12345"
    assert core.query_param("q") == "hello"
    assert core.get_header("x-test") == "val"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_protocol.py::test_parse_get_request_to_core -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'massless._protocol'`

- [ ] **Step 3: Write the parser and dispatch**

```cython
# src/massless/_protocol.pyx
import httptools

from massless._request cimport RequestCore
from massless._request import MasslessRequest
from massless._response import build_http_response, serialize_body


cdef class _Collector:
    """httptools callback target that accumulates one request into a RequestCore.

    The attributes are `cdef public` so the plain-Python MasslessProtocol can read
    them; bare `cdef` fields are invisible to Python and would raise AttributeError.
    """
    cdef public bytes url
    cdef public list headers
    cdef public bint complete

    def __cinit__(self):
        self.headers = []
        self.url = b""
        self.complete = False

    def on_url(self, bytes url):
        self.url += url   # httptools may deliver the URL in multiple chunks

    def on_header(self, bytes name, bytes value):
        self.headers.append((name, value))

    def on_message_complete(self):
        self.complete = True


def parse_request(bytes raw):
    """Parse a full HTTP/1.1 request into a RequestCore (test + glue helper)."""
    collector = _Collector()
    parser = httptools.HttpRequestParser(collector)
    parser.feed_data(raw)
    method = parser.get_method()  # bytes
    parsed = httptools.parse_url(collector.url)
    cdef bytes path = parsed.path
    cdef bytes query = parsed.query if parsed.query is not None else b""
    return RequestCore.create(method, path, query, collector.headers)


async def dispatch(api, core, int route_id, long param):
    """Run the matched view and return full HTTP response bytes."""
    route = api.routes[route_id]
    path_params = {route.param_name: param} if route.param_name is not None else {}
    request = MasslessRequest(core, path_params)
    kwargs = route.binder(path_params, request.query_param)
    result = await route.view(**kwargs)
    body, ctype = serialize_body(result)
    return build_http_response(200, ctype, body, True)
```

Note: `RequestCore.create` is a `@staticmethod cdef`, callable here because `_protocol.pyx` `cimport`s `RequestCore` from `_request.pxd`.

- [ ] **Step 4: Rebuild and run the parse test**

Run: `uv sync --reinstall-package django-massless && uv run pytest tests/test_protocol.py::test_parse_get_request_to_core -v`
Expected: 1 passed.

- [ ] **Step 5: Write the failing test (dispatch)**

```python
# add to tests/test_protocol.py
import asyncio

from massless._protocol import dispatch, parse_request
from massless.app import MasslessAPI


def _api():
    api = MasslessAPI()

    @api.get("/items/{item_id}")
    async def item(item_id: int, q: str | None = None):
        return {"item_id": item_id, "q": q}

    return api


def test_dispatch_runs_view_and_builds_response():
    api = _api()
    router = api.build_router()
    core = parse_request(b"GET /items/7?q=hi HTTP/1.1\r\nHost: x\r\n\r\n")
    route_id, param = router.match(b"/items/7")
    raw = asyncio.run(dispatch(api, core, route_id, param))
    assert raw.startswith(b"HTTP/1.1 200 OK\r\n")
    assert raw.endswith(b'{"item_id":7,"q":"hi"}')
```

- [ ] **Step 6: Run test to verify it passes**

Run: `uv run pytest tests/test_protocol.py -v`
Expected: 2 passed.

- [ ] **Step 7: Write the MasslessProtocol glue**

Add to `src/massless/_protocol.pyx`:

```cython
import asyncio


class MasslessProtocol(asyncio.Protocol):
    """One instance per connection. Parses requests and writes responses."""

    def __init__(self, api, router):
        self._api = api
        self._router = router
        self._transport = None
        self._reset()

    def _reset(self):
        self._collector = _Collector()
        self._parser = httptools.HttpRequestParser(self._collector)

    def connection_made(self, transport):
        self._transport = transport

    def data_received(self, bytes data):
        self._parser.feed_data(data)
        if self._collector.complete:
            method = self._parser.get_method()
            parsed = httptools.parse_url(self._collector.url)
            query = parsed.query if parsed.query is not None else b""
            core = RequestCore.create(method, parsed.path, query, self._collector.headers)
            route_id, param = self._router.match(parsed.path)
            self._reset()
            asyncio.get_event_loop().create_task(self._respond(core, route_id, param))

    async def _respond(self, core, route_id, param):
        if route_id == -1:
            self._transport.write(build_http_response(404, b"text/plain; charset=utf-8", b"Not Found", True))
            return
        try:
            raw = await dispatch(self._api, core, route_id, param)
        except Exception:
            raw = build_http_response(500, b"text/plain; charset=utf-8", b"Internal Server Error", True)
        self._transport.write(raw)
```

- [ ] **Step 8: Rebuild**

Run: `uv sync --reinstall-package django-massless && uv run pytest tests/test_protocol.py -v`
Expected: 2 passed (glue is covered by Task 11).

- [ ] **Step 9: Commit**

```bash
git add src/massless/_protocol.pyx tests/test_protocol.py
git commit -m "feat: httptools parse, async dispatch, MasslessProtocol"
```

---

## Task 11: Runner and real-server integration

**Files:**
- Create: `src/massless/__main__.py`
- Test: `tests/test_integration.py`

- [ ] **Step 1: Write the runner**

```python
# src/massless/__main__.py
"""Run a MasslessAPI app: python -m massless module:attr --host H --port P."""

from __future__ import annotations

import argparse
import asyncio
import importlib
from typing import TYPE_CHECKING

import uvloop

from massless._protocol import MasslessProtocol

if TYPE_CHECKING:
    from massless.app import MasslessAPI


def load_app(target: str) -> MasslessAPI:
    module_name, _, attr = target.partition(":")
    module = importlib.import_module(module_name)
    return getattr(module, attr or "api")


async def serve(api: MasslessAPI, host: str, port: int) -> None:
    router = api.build_router()
    loop = asyncio.get_running_loop()
    server = await loop.create_server(lambda: MasslessProtocol(api, router), host, port)
    async with server:
        await server.serve_forever()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="massless")
    parser.add_argument("target", help="module:attr of the MasslessAPI app")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    api = load_app(args.target)
    uvloop.run(serve(api, args.host, args.port))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Write the failing integration test**

```python
# tests/test_integration.py
import socket
import threading
import time
import urllib.request

import pytest

from massless.app import MasslessAPI


@pytest.fixture
def server():
    api = MasslessAPI()

    @api.get("/")
    async def root():
        return {"message": "Hello World"}

    @api.get("/items/{item_id}")
    async def item(item_id: int, q: str | None = None):
        return {"item_id": item_id, "q": q}

    # bind an ephemeral port
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()

    import asyncio

    import uvloop

    from massless._protocol import MasslessProtocol

    ready = threading.Event()
    loop_holder = {}

    def run():
        loop = uvloop.new_event_loop()
        asyncio.set_event_loop(loop)
        loop_holder["loop"] = loop
        router = api.build_router()
        srv = loop.run_until_complete(
            loop.create_server(lambda: MasslessProtocol(api, router), "127.0.0.1", port),
        )
        ready.set()
        try:
            loop.run_forever()
        finally:
            srv.close()
            loop.run_until_complete(srv.wait_closed())

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    ready.wait(timeout=5)
    time.sleep(0.1)
    yield f"http://127.0.0.1:{port}"
    loop_holder["loop"].call_soon_threadsafe(loop_holder["loop"].stop)
    thread.join(timeout=5)


def _get(url):
    with urllib.request.urlopen(url, timeout=5) as resp:
        return resp.status, resp.read()


def test_root(server):
    status, body = _get(server + "/")
    assert status == 200
    assert body == b'{"message":"Hello World"}'


def test_path_param(server):
    status, body = _get(server + "/items/12345")
    assert status == 200
    assert body == b'{"item_id":12345,"q":null}'


def test_path_and_query(server):
    status, body = _get(server + "/items/12345?q=hello")
    assert status == 200
    assert body == b'{"item_id":12345,"q":"hello"}'
```

- [ ] **Step 3: Run tests**

Run: `uv run pytest tests/test_integration.py -v`
Expected: 3 passed (no rebuild: `__main__.py` is interpreted; `_protocol` is already built).

- [ ] **Step 4: Manual smoke (optional)**

Run: `uv run python -m massless benchmarks.app:api --port 8000` (after Task 12), then `curl localhost:8000/items/1?q=hi`.

- [ ] **Step 5: Commit**

```bash
git add src/massless/__main__.py tests/test_integration.py
git commit -m "feat: uvloop runner and real-server integration tests"
```

---

## Task 12: No-promotion assertion

**Files:**
- Modify: `tests/test_integration.py`

- [ ] **Step 1: Write the failing test**

The protocol must never promote a request while serving these endpoints. We assert it by spying on `MasslessRequest`: a promotion would set `_is_django = True`. In Phase 1 there is no promotion path, so we assert the attribute never becomes truthy after a request, and that the served bodies are correct (proving the fast path served them).

```python
# add to tests/test_integration.py
def test_no_promotion_on_fast_path(server):
    from massless._request import MasslessRequest

    created = []
    orig_init = MasslessRequest.__init__

    def spy_init(self, core, path_params):
        created.append(self)
        orig_init(self, core, path_params)

    MasslessRequest.__init__ = spy_init
    try:
        _get(server + "/")
        _get(server + "/items/12345?q=hello")
        import time

        time.sleep(0.2)  # let the response tasks finish
    finally:
        MasslessRequest.__init__ = orig_init

    assert created, "expected requests to be served via MasslessRequest"
    for req in created:
        # No promotion: the latch attribute was never set, and Django state was never
        # materialized (touching .GET still raises, as on a pristine fast-path request).
        assert not hasattr(req, "_is_django")
        with pytest.raises(AttributeError):
            _ = req.GET
```

- [ ] **Step 2: Run test**

Run: `uv run pytest tests/test_integration.py::test_no_promotion_on_fast_path -v`
Expected: PASS (no promotion occurs).

- [ ] **Step 3: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: assert fast path never promotes the request"
```

---

## Task 13: Benchmark bench-app and compare.py trim

**Files:**
- Create: `benchmarks/app.py`
- Modify: `benchmarks/compare.py`
- Test: `tests/test_integration.py` (reuse), plus a bench-app import test

- [ ] **Step 1: Write the bench-app**

```python
# benchmarks/app.py
"""Phase 1 benchmark app: the framework-bound, no-DB, async, no-body endpoints
from benchmarks/cases.md. Run: python -m massless benchmarks.app:api
"""

from massless import MasslessAPI

api = MasslessAPI()

# JSON payload built once at import. range(100) encodes to ~5KB with msgspec, so use
# range(200) (~10.6KB) to match the "10kb" label. Confirm the byte size is close to
# django-bolt's /10k-json payload so the head-to-head comparison stays apples-to-apples.
_TEN_K = [{"id": i, "name": f"item-{i}", "value": i * 7, "active": i % 2 == 0} for i in range(200)]


@api.get("/")
async def root():
    return {"message": "Hello World"}


@api.get("/10k-json")
async def ten_k_json():
    return _TEN_K


@api.get("/items/{item_id}")
async def read_item(item_id: int, q: str | None = None):
    return {"item_id": item_id, "q": q}
```

- [ ] **Step 2: Trim compare.py CORE_KEYS**

In `benchmarks/compare.py`, replace the `CORE_KEYS` tuple with the Phase 1 subset and document the deferred keys:

```python
# Phase 1 ships only framework-bound, no-body, async endpoints. The keys to restore
# as later phases add header access and request-body parsing are:
#   Header Param (/header), Cookie Param (/cookie), JSON Parse/Validate (/bench/parse)
CORE_KEYS = (
    "Root JSON Async (/)",
    "10kb JSON Async (/10k-json)",
    "Path Param int (/items/12345)",
    "Path + Query (/items/12345?q=hello)",
)
```

- [ ] **Step 3: Add a bench-app server test**

```python
# add to tests/test_integration.py
def test_bench_app_importable_and_serves(tmp_path):
    import importlib

    bench = importlib.import_module("benchmarks.app")
    router = bench.api.build_router()
    assert router.match(b"/")[0] != -1
    assert router.match(b"/10k-json")[0] != -1
    assert router.match(b"/items/5")[0] != -1
```

For this import to work, `benchmarks/` must be importable. Add an empty `benchmarks/__init__.py`.

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_integration.py -v && uv run ruff check && uv run mypy src/massless/`
Expected: all green.

- [ ] **Step 5: Capture a baseline and run the gate (manual, needs bombardier + bolt)**

```bash
# massless on :8000
uv run python -m massless benchmarks.app:api --port 8000 &
PORT=8000 LABEL=massless OUT=benchmarks/results/massless.md ./benchmarks/run.sh
# single-process django-bolt on :8001 (in the django-bolt repo)
PORT=8001 LABEL=bolt OUT=benchmarks/results/bolt.md ./benchmarks/run.sh
uv run python benchmarks/compare.py benchmarks/results/bolt.md benchmarks/results/massless.md
```

Exit criterion: `compare.py` reports PASS (massless within 2% of, or beating, bolt on the 4 core endpoints).

- [ ] **Step 6: Commit**

```bash
git add benchmarks/app.py benchmarks/__init__.py benchmarks/compare.py tests/test_integration.py
git commit -m "feat: Phase 1 benchmark app and compare.py core-key trim"
```

---

## Self-Review

(Completed by the author before handoff; see the session notes. Spec sections 1-9 each map to a task: response (§5.5) -> Tasks 2-3; router (§5.2) -> Tasks 4-5; request (§5.3) -> Tasks 6-7; binding (§5.4) -> Task 8; app/runner (§5.6) -> Tasks 9, 11; protocol (§5.1) -> Task 10; bench + gate (§6) -> Task 13; testing (§7) -> Tasks 10-12; deps (§8) -> Task 1.)
