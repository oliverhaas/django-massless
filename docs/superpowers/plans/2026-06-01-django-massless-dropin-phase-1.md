# django-massless drop-in rebuild, Phase 1: core handler + drop-in server

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development or superpowers:executing-plans. Checkbox (`- [ ]`) steps.

**Goal:** Serve an unmodified Django project through massless: C parse -> lazy `MasslessRequest` -> Django's URL resolver + global `MIDDLEWARE` + view (via a `BaseHandler`-derived `MasslessHandler`) -> `HttpResponse` -> C serialize. Retire the bolt-style API surface (custom router, `@api.get`, fast-tier middleware).

**Architecture:** A `MasslessHandler(BaseHandler)` loads Django's async middleware chain and uses Django's normal resolution; the protocol builds a `MasslessRequest` from the C buffers and calls the handler, then serializes the Django response. The custom router and `MasslessAPI` are deleted; routing is Django's `ROOT_URLCONF`. The engine (transport, lazy request, multi-process, response serialization) is reused.

**Tech Stack:** Cython 3.2, uvloop, httptools, Django (`BaseHandler`, resolver, middleware), pytest, pytest-django.

**Spec:** [docs/superpowers/specs/2026-06-01-django-massless-dropin-design.md](../specs/2026-06-01-django-massless-dropin-design.md) (Phase 1 of §9)

---

## Conventions
Rebuild `.pyx` with `uv sync --reinstall-package django-massless` after edits. Gates: `uv run pytest -n auto`, `uv run ruff check`, `uv run mypy src/massless/`. Tests run under pytest-django (`DJANGO_SETTINGS_MODULE=settings.base`). Commit per task; hooks may reformat (re-stage).

## File Structure
| File | Change |
|------|--------|
| `src/massless/handler.py` | new `MasslessHandler(BaseHandler)`: Django middleware chain + resolver + view |
| `src/massless/_request.pyx` | `MasslessRequest.__init__` also sets plain `path_info` (resolver needs it without promoting) |
| `src/massless/_protocol.pyx` | `dispatch`/`MasslessProtocol` use the handler (build request -> `handler.handle` -> serialize); drop router/api/route logic |
| `src/massless/server.py`, `__main__.py`, `management/commands/runmassless.py` | build `MasslessHandler` from settings; serve the current Django project (no `module:api`) |
| `src/massless/__init__.py` | stop exporting `MasslessAPI` |
| **delete** `src/massless/_router.pyx`, `_router.pxd`, `app.py`, `_middleware.pyx`, `_middleware.pxd`, `bridge.py` | retired bolt-style surface (bridge folds into handler) |
| `tests/settings/urls.py` + `tests/settings/base.py` | a real drop-in test project: function + CBV views, an ORM view, ROOT_URLCONF + MIDDLEWARE |
| **delete** `tests/test_router.py`, `test_app.py`, `test_binding.py`, `test_middleware.py`, `test_auth.py`, `test_bridge.py`, `test_dispatch.py` | tests for retired modules |
| `tests/test_handler.py`, `tests/test_dropin.py` | new: handler unit + real-server drop-in integration |
| `tests/test_protocol.py`, `test_integration.py`, `test_lifecycle.py`, `test_promotion_orm.py` | rewire fixtures to the handler-based server |
| `pyproject.toml` | mypy `ignore_missing_imports` list drops the deleted `_router`/`_middleware`; add `massless.handler` if needed |
| `benchmarks/app.py` | replaced later (Phase 3); for now a minimal Django project to serve |

`tests/test_parity.py`, `test_request.py`, `test_response.py` are kept unchanged (the lazy request + parity + serialization are the reused core).

---

## Task 1: MasslessRequest exposes plain `path_info`

Django's URL resolver reads `request.path_info` first thing; it must be available without promoting (it is cheap, just the path).

**Files:** `src/massless/_request.pyx`; `tests/test_request.py`

- [ ] **Step 1: Failing test**

```python
# add to tests/test_request.py
def test_path_info_is_plain_and_does_not_promote():
    core = RequestCore.py_create(b"GET", b"/items/5", b"", [(b"host", b"ex.com")], b"")
    req = MasslessRequest(core, {})
    assert req.path_info == "/items/5"
    assert req._is_django is False   # reading path_info must not promote
```

- [ ] **Step 2: Run, expect fail** (`path_info` missing -> `__getattr__` promotes or AttributeError).

- [ ] **Step 3: Implement.** In `MasslessRequest.__init__`, after `self.path = core.path`, add `self.path_info = core.path`. (Plain attr; the resolver and basic middleware read it without triggering promotion.)

- [ ] **Step 4: Rebuild + test.** `uv sync --reinstall-package django-massless && uv run pytest tests/test_request.py -v` green.

- [ ] **Step 5: Commit** `feat(request): plain path_info for the Django resolver`.

## Task 2: MasslessHandler (the core)

A `BaseHandler` subclass that runs Django's async middleware chain (global `MIDDLEWARE`) and Django's normal resolution. Unlike the retired `BridgeHandler`, it does NOT override `_get_response_async` (it lets Django resolve the URL and call the view).

**Files:** `src/massless/handler.py`; `tests/test_handler.py`; `tests/settings/urls.py`, `tests/settings/base.py`

- [ ] **Step 1: Add test views + ROOT_URLCONF.** In `tests/settings/urls.py`:

```python
from django.http import HttpResponse, JsonResponse
from django.urls import path


async def hello(request):
    return JsonResponse({"message": "Hello World", "path": request.path})


async def echo_q(request, item_id: int):
    return JsonResponse({"item_id": item_id, "q": request.GET.get("q")})


def sync_hello(request):
    return HttpResponse(b"sync-ok")


urlpatterns = [
    path("", hello),
    path("items/<int:item_id>", echo_q),
    path("sync", sync_hello),
]
```

In `tests/settings/base.py` add `ROOT_URLCONF = "settings.urls"` and a minimal `MIDDLEWARE` (`["django.middleware.common.CommonMiddleware"]`). `ALLOWED_HOSTS = ["*"]` is already present.

- [ ] **Step 2: Failing test**

```python
# tests/test_handler.py
import asyncio

from massless._request import MasslessRequest, RequestCore
from massless.handler import MasslessHandler


def _req(method=b"GET", path=b"/items/7", query=b"q=hi", headers=None):
    headers = headers or [(b"host", b"ex.com")]
    return MasslessRequest(RequestCore.py_create(method, path, query, headers, b""), {})


def test_handler_routes_through_django_resolver_and_middleware():
    handler = MasslessHandler()
    resp = asyncio.run(handler.handle(_req()))
    assert resp.status_code == 200
    assert b'"item_id": 7' in resp.content
    assert b'"q": "hi"' in resp.content


def test_handler_404_for_unknown_path():
    handler = MasslessHandler()
    resp = asyncio.run(handler.handle(_req(path=b"/nope", query=b"")))
    assert resp.status_code == 404
```

- [ ] **Step 3: Run, expect fail** (`massless.handler` missing).

- [ ] **Step 4: Implement** `src/massless/handler.py`:

```python
"""The core drop-in handler: run a request through Django's real middleware chain
and URL resolver, exactly as Django's own ASGI/WSGI handlers do, but fed a lazy
MasslessRequest built from the C buffers instead of an ASGI scope.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.core.handlers.base import BaseHandler

if TYPE_CHECKING:
    from django.http import HttpRequest, HttpResponseBase


class MasslessHandler(BaseHandler):
    """Loads Django's async middleware chain once; `handle` runs a request through
    it (the chain resolves the URL against ROOT_URLCONF and calls the view)."""

    def __init__(self) -> None:
        super().__init__()
        self.load_middleware(is_async=True)

    async def handle(self, request: HttpRequest) -> HttpResponseBase:
        return await self.get_response_async(request)
```

- [ ] **Step 5: Rebuild not needed (pure Python). Run + commit.**

Run: `uv run pytest tests/test_handler.py -v` -> 2 passed.
Commit: `feat(handler): MasslessHandler over Django resolver + middleware`.

## Task 3: Protocol dispatch uses the handler (retire routing)

Replace the router/`@api.get` dispatch with: build a `MasslessRequest`, run it through a `MasslessHandler`, serialize the Django response. `MasslessProtocol` takes a handler instead of `(api, router)`.

**Files:** `src/massless/_protocol.pyx`; `tests/test_protocol.py`

- [ ] **Step 1: Failing test**

```python
# rewrite the dispatch test in tests/test_protocol.py
import asyncio

from massless._protocol import dispatch, parse_request
from massless.handler import MasslessHandler


def test_dispatch_runs_request_through_handler():
    core = parse_request(b"GET /items/7?q=hi HTTP/1.1\r\nHost: x\r\n\r\n")
    handler = MasslessHandler()
    raw = asyncio.run(dispatch(handler, core))
    assert raw.startswith(b"HTTP/1.1 200 OK\r\n")
    assert b'"item_id": 7' in raw
```

- [ ] **Step 2: Run, expect fail** (old `dispatch(api, core, route_id, param)` signature).

- [ ] **Step 3: Implement.** In `_protocol.pyx`:
  - Change `dispatch` to `async def dispatch(handler, core):` -> build `request = MasslessRequest(core, {})`; `dj_resp = await handler.handle(request)`; `return _django_response_to_massless(dj_resp).to_bytes(True)`. Reuse `_django_response_to_massless` (already serializes status/headers/Set-Cookie/body).
  - Remove the route/middleware/bridge branches and the `run_before`/`run_after`/`_wrap_result`/`_get_bridge` machinery and the `from massless._middleware cimport ...` / `from massless._request import MasslessRequest` stays.
  - `MasslessProtocol.__init__(self, handler)`: store `self._handler = handler`; drop `self._router`. In `data_received`/`_process_loop`, drop the router match; for each parsed request build the `RequestCore` and enqueue `(core,)`; in `_respond`/`_process_loop` call `await dispatch(self._handler, core)` (no route_id). Keep the per-connection ordered worker + drain + `_inflight` registry intact.
  - Keep `parse_request`, `_Collector`, `_django_response_to_massless`, the sync-executor handling for sync views (now handled by Django's middleware chain adapting sync views via `sync_to_async`, so the executor may be dropped here -- verify during build).

- [ ] **Step 4: Rebuild + test.** `uv sync --reinstall-package django-massless && uv run pytest tests/test_protocol.py -v` green.

- [ ] **Step 5: Commit** `refactor(protocol): dispatch via MasslessHandler; drop the custom router`.

## Task 4: Server + runner serve the current Django project

`serve`/`serve_async`/`MasslessProtocol` build a `MasslessHandler` from the configured settings; `runmassless` and `python -m massless` serve the current project (no `module:api` argument).

**Files:** `src/massless/server.py`, `src/massless/__main__.py`, `src/massless/management/commands/runmassless.py`; `tests/test_runner.py`, `tests/test_management.py`

- [ ] **Step 1: Failing test**

```python
# tests/test_runner.py (replace app-loading assertions)
from unittest.mock import patch

from massless.__main__ import main


def test_main_single_process_serves_with_handler():
    with patch("massless.server.serve") as serve:
        main(["--host", "127.0.0.1", "--port", "0", "--processes", "1"])
    assert serve.called
```

- [ ] **Step 2: Run, expect fail** (main still requires a `target` arg).

- [ ] **Step 3: Implement.**
  - `server.py`: `serve_async`/`serve` take no `api`; build `handler = MasslessHandler()` (after Django is set up) and `MasslessProtocol(handler)`; `create_server(lambda: MasslessProtocol(handler), sock=sock)`. Drop `api.build_router()`.
  - `__main__.py`: drop the `target` positional and `load_app`; `main` parses `--host/--port/--processes/--workers/--settings`, bootstraps Django (`_bootstrap_django` requires `DJANGO_SETTINGS_MODULE`/`--settings`), then `serve(...)` (N=1) or `run_supervised(_serve_target, host, port, workers, processes=...)` where `_serve_target(host, port, workers)` re-bootstraps Django in the worker and serves. `_serve_target` stays in `server.py` (spawn-picklable).
  - `runmassless.py`: drop the `target` arg; `handle()` bootstraps (manage.py already did `django.setup()`) and calls `serve`/`run_supervised`.

- [ ] **Step 4: Test.** `uv run pytest tests/test_runner.py tests/test_management.py -v` green.

- [ ] **Step 5: Commit** `feat(server): serve the current Django project (drop module:api)`.

## Task 5: Retire the bolt-style surface

**Files:** delete `_router.pyx`, `_router.pxd`, `app.py`, `_middleware.pyx`, `_middleware.pxd`, `bridge.py`; delete `tests/test_router.py`, `test_app.py`, `test_binding.py`, `test_middleware.py`, `test_auth.py`, `test_bridge.py`, `test_dispatch.py`; edit `__init__.py`, `pyproject.toml`.

- [ ] **Step 1:** `git rm` the listed source and test files.
- [ ] **Step 2:** `src/massless/__init__.py`: remove `from massless.app import MasslessAPI` and `__all__`; keep the module docstring only.
- [ ] **Step 3:** `pyproject.toml`: in the mypy `ignore_missing_imports` override module list, remove `massless._router` and `massless._middleware` (deleted) and ensure `massless._request`, `massless._response`, `massless._protocol` remain.
- [ ] **Step 4:** Rebuild + run the whole suite; fix any lingering imports of the deleted modules (e.g. `_response`/`_protocol` may have imported `_middleware`/`Response`-for-middleware -- the protocol now only needs `_django_response_to_massless` + `to_bytes`). `uv sync --reinstall-package django-massless && uv run pytest -n auto`.
- [ ] **Step 5: Commit** `refactor: retire bolt-style API surface (router, MasslessAPI, fast-tier middleware)`.

## Task 6: Drop-in integration test through the real server

A normal Django project (the `tests/settings/urls.py` views + `MIDDLEWARE`) served by the real uvloop server returns responses matching Django.

**Files:** `tests/test_dropin.py`; reuse/adapt the server fixture from `tests/test_integration.py`

- [ ] **Step 1: Failing test**

```python
# tests/test_dropin.py
import socket
import threading
import time
import urllib.request

import pytest


@pytest.fixture
def server():
    import asyncio

    import uvloop

    from massless._protocol import MasslessProtocol
    from massless.handler import MasslessHandler

    sock = socket.socket(); sock.bind(("127.0.0.1", 0)); port = sock.getsockname()[1]; sock.close()
    ready = threading.Event(); hold = {}

    def run():
        loop = uvloop.new_event_loop(); asyncio.set_event_loop(loop); hold["loop"] = loop
        handler = MasslessHandler()
        srv = loop.run_until_complete(loop.create_server(lambda: MasslessProtocol(handler), "127.0.0.1", port))
        ready.set()
        try:
            loop.run_forever()
        finally:
            srv.close(); loop.run_until_complete(srv.wait_closed())

    t = threading.Thread(target=run, daemon=True); t.start(); ready.wait(5); time.sleep(0.1)
    yield f"http://127.0.0.1:{port}"
    hold["loop"].call_soon_threadsafe(hold["loop"].stop); t.join(5)


def _get(url):
    with urllib.request.urlopen(url, timeout=5) as r:
        return r.status, r.read()


def test_normal_django_view_served(server):
    status, body = _get(server + "/items/7?q=hi")
    assert status == 200
    assert b'"item_id": 7' in body and b'"q": "hi"' in body


def test_sync_view_served(server):
    status, body = _get(server + "/sync")
    assert status == 200 and body == b"sync-ok"


def test_unknown_path_404(server):
    import urllib.error
    with pytest.raises(urllib.error.HTTPError) as e:
        _get(server + "/missing")
    assert e.value.code == 404
```

- [ ] **Step 2: Run.** `uv run pytest tests/test_dropin.py -v` -> green (a real Django sync and async view, plus 404, served through massless).

- [ ] **Step 3: Confirm the full suite + gates.** `uv run pytest -n auto && uv run ruff check && uv run mypy src/massless/` all green. Confirm `test_parity.py`, `test_request.py`, `test_response.py`, `test_promotion_orm.py`, `test_lifecycle.py`, `test_supervisor.py` still pass (rewire their fixtures to the handler-based server where they used `MasslessAPI`).

- [ ] **Step 4: Commit** `test(dropin): normal Django project served through massless end-to-end`.

## Self-Review
Spec coverage: core handler (§3) -> Task 2; lazy request/path_info (§4) -> Task 1; protocol/dispatch rewire (§3) -> Task 3; serve the project (§6 reuse) -> Task 4; retire surface (§6) -> Task 5; drop-in correctness (§8) -> Task 6. Name consistency: `MasslessHandler.handle`, `dispatch(handler, core)`, `MasslessProtocol(handler)`, `MasslessRequest.path_info`. Highest risk: the protocol/server rewiring after deleting `_router`/`app`/`_middleware`, and whether Django's middleware chain correctly adapts sync views (it should, via `sync_to_async`); the verify step hardens both. Streaming/`MIDDLEWARE_STACKS` are out of scope (later phases).
