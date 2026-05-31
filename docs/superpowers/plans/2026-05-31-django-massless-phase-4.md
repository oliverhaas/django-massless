# django-massless Phase 4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development or superpowers:executing-plans. Checkbox (`- [ ]`) steps.

**Goal:** Production-shaped server: sync views on a thread-pool, N worker processes via SO_REUSEPORT with a supervising master, a `runmassless` Django management command, lifecycle hooks, graceful shutdown, and logged 500s.

**Architecture:** `iscoroutinefunction` splits views at registration; sync views run via `loop.run_in_executor(ThreadPoolExecutor, ...)`. A `server.py` `serve()` builds a `SO_REUSEPORT` socket, runs uvloop, installs signal handlers, runs startup/shutdown hooks, and drains in-flight requests on shutdown. A `supervisor.py` master spawns/monitors/restarts N workers and forwards signals. `runmassless` (Django BaseCommand) and `python -m massless` both drive it.

**Tech Stack:** Cython 3.2, uvloop, Django (management command), `multiprocessing`, `socket(SO_REUSEPORT)`, `concurrent.futures.ThreadPoolExecutor`, pytest.

**Spec:** [docs/superpowers/specs/2026-05-31-django-massless-phase-4-design.md](../specs/2026-05-31-django-massless-phase-4-design.md)

---

## Conventions
Same as prior phases. Rebuild `.pyx` with `uv sync --reinstall-package django-massless`. Gates: `uv run pytest -n auto`, `uv run ruff check`, `uv run mypy src/massless/`. Tests run under pytest-django. Commit per task; hooks may reformat (re-stage).

## File Structure
| File | Change |
|------|--------|
| `src/massless/app.py` | `Route.is_async` (iscoroutinefunction); `on_startup`/`on_shutdown` registries + decorators |
| `src/massless/_protocol.pyx` | sync views via `loop.run_in_executor(pool, partial(view, **kwargs))`; the api carries the pool; logged 500 + DEBUG traceback |
| `src/massless/server.py` | `serve(api, host, port, workers)`: SO_REUSEPORT socket, uvloop, signal handlers, startup/shutdown hooks, graceful drain |
| `src/massless/supervisor.py` | `run_supervised(api_target, host, port, processes, workers)`: spawn/monitor/restart/shutdown |
| `src/massless/__main__.py` | `--processes` / `--workers`; delegate to supervisor (N>1) or serve (N=1) |
| `src/massless/management/commands/runmassless.py` | Django `BaseCommand` |
| `tests/test_dispatch.py`, `tests/test_lifecycle.py`, `tests/test_supervisor.py` | unit + integration |
| `benchmarks/app.py` | a sync view endpoint (`/sync-hello`) for the executor benchmark |

---

## Task 1: Route.is_async + lifecycle registries

**Files:** `src/massless/app.py`; `tests/test_app.py`

- [ ] Failing test: registering an `async def` view sets `route.is_async is True`; a `def` view sets `False`. `@api.on_startup`/`@api.on_shutdown` append callables to `api.on_startup_hooks`/`api.on_shutdown_hooks`.
- [ ] Implement: in `_register`, `route.is_async = inspect.iscoroutinefunction(view)` (add `is_async: bool` to `Route`). Add `on_startup_hooks: list`, `on_shutdown_hooks: list` to `MasslessAPI` with `on_startup`/`on_shutdown` decorators that append and return the callable.
- [ ] Test. Commit `feat(app): is_async per route + startup/shutdown hook registries`.

## Task 2: Sync view dispatch via thread-pool executor

**Files:** `src/massless/_protocol.pyx`; `tests/test_dispatch.py`

- [ ] Failing test: an app with a sync view `def v(): return {"tid": threading.get_ident()}` dispatched through `dispatch` returns a tid different from the loop thread's; an async view returns the loop thread's tid. (Build an api with both; call `dispatch`; the api must carry a `ThreadPoolExecutor`.)
- [ ] Implement: the api gets an `executor` attribute (a `ThreadPoolExecutor`; `_get_executor(api)` lazily creates one, default `max_workers` from `api._max_workers` or a default). In `dispatch`, after binding kwargs and the non-bridge branch: `if route.is_async: result = await route.view(**kwargs)` else `result = await asyncio.get_running_loop().run_in_executor(_get_executor(api), functools.partial(route.view, **kwargs))`. (Bridge path stays async-only for now; a sync bridged view is out of scope.)
- [ ] Rebuild + test. Commit `feat(dispatch): sync views on a thread-pool executor`.

## Task 3: Logged 500 + DEBUG traceback

**Files:** `src/massless/_protocol.pyx`; `tests/test_dispatch.py`

- [ ] Failing test: a view that raises returns a 500 Response; the `massless` logger records the exception (use `caplog`); with `settings.DEBUG = True` the body contains the exception text, with `DEBUG = False` it is a generic message.
- [ ] Implement: wrap the view call in `dispatch` (both async and executor paths) in `try/except Exception`. On exception: `logging.getLogger("massless").exception("view error")`; build a 500 Response whose body is the traceback if `settings.configured and settings.DEBUG` else `b"Internal Server Error"`. (Guard `settings.configured` so fast-path-only apps without settings still work.)
- [ ] Rebuild + test. Commit `feat(dispatch): log unhandled view errors; DEBUG traceback in 500`.

## Task 4: server.py: SO_REUSEPORT socket, uvloop, hooks, graceful shutdown

**Files:** `src/massless/server.py`; `tests/test_lifecycle.py`

- [ ] Failing test (lifecycle): `serve_async(api, host, port, ready_event, stop_event)` (the awaitable core that `serve` wraps) runs `on_startup` hooks (sync + async) before signaling ready, serves, and on `stop_event` runs `on_shutdown` hooks. Drive it with `asyncio` in the test: start the coro as a task, wait for ready, hit it with a client, set stop_event, await, assert both hook lists fired and the server closed. Also a SO_REUSEPORT smoke: `_make_socket(host, 0)` returns a socket with `SO_REUSEPORT` set and two such sockets can bind the same port.
- [ ] Implement `server.py`:
  - `_make_socket(host, port)`: `socket.socket(AF_INET, SOCK_STREAM)`, set `SO_REUSEADDR` + `SO_REUSEPORT`, `bind`, `set_inheritable(True)`, return it (unlistened; `create_server` listens).
  - `async def serve_async(api, host, port, *, ready=None, stop=None)`: run startup hooks (await async, call sync); build `MasslessProtocol` server on `_make_socket`; `ready.set()`; `await stop.wait()` (or `serve_forever`); on stop: close server, drain (`await asyncio.sleep`-bounded wait for in-flight), run shutdown hooks.
  - `def serve(api, host, port, workers=None)`: set the executor max_workers; `uvloop.run(...)` of `serve_async` with a `stop` event wired to `loop.add_signal_handler(SIGTERM/SIGINT, stop.set)`.
- [ ] Rebuild not needed (pure Python). Test. Commit `feat(server): SO_REUSEPORT serve with hooks + graceful shutdown`.

## Task 5: supervisor.py: master process management

**Files:** `src/massless/supervisor.py`; `tests/test_supervisor.py`

- [ ] Failing test: `Supervisor(target, n=2)` where `target` is a fake (a function that sleeps until terminated). `start()` spawns 2 processes (assert 2 alive); killing one triggers a restart (the supervisor's `_monitor` step re-spawns to keep n alive); `shutdown()` terminates all and they exit. Test the supervisor loop logic deterministically (e.g. a single `_reap_and_restart()` step against a fake that exited), not a long-running loop.
- [ ] Implement `supervisor.py`: `run_supervised(target, *args, processes, **kw)` using `multiprocessing` (spawn context). A `Supervisor` class: `start()` spawns `processes` workers running `target(*args)`; a monitor loop that restarts a worker whose `exitcode` is not the graceful one; `shutdown()` sends `SIGTERM` to each and joins with a timeout, escalating to `terminate()`. Install `SIGTERM`/`SIGINT` handlers in the master that call `shutdown()`.
- [ ] Test. Commit `feat(supervisor): spawn/monitor/restart/shutdown N workers`.

## Task 6: __main__ --processes/--workers

**Files:** `src/massless/__main__.py`; `tests/test_app.py` (or a small CLI test)

- [ ] Failing test: `build_parser().parse_args([...])` accepts `--processes`/`--workers`; `--processes 1` path calls `serve(...)` (patch and assert), `--processes 2` calls `run_supervised(...)` (patch and assert).
- [ ] Implement: add `--processes` (default 1) and `--workers` (executor threads). In `main`: bootstrap Django (existing); if `processes <= 1`: `serve(api, host, port, workers)`; else `run_supervised(_serve_target, target_str, host, port, workers, processes=processes)` where `_serve_target(target_str, host, port, workers)` re-imports the app in the worker and calls `serve`. (Workers must re-import the app, since spawned processes do not inherit it.)
- [ ] Test. Commit `feat(runner): --processes (SO_REUSEPORT) and --workers`.

## Task 7: runmassless management command

**Files:** `src/massless/management/__init__.py`, `src/massless/management/commands/__init__.py`, `src/massless/management/commands/runmassless.py`; `tests/test_management.py`

- [ ] Failing test: `call_command("runmassless", "benchmarks.app:api", "--processes", "1", ...)` with `serve` patched invokes `serve` with the loaded app, host, port, workers. (Use `pytest-django`; patch `massless.management.commands.runmassless.serve`.)
- [ ] Implement the `BaseCommand`: `add_arguments` (target positional, `--host`, `--port`, `--processes`, `--workers`); `handle()` imports lazily (`from massless.server import serve` / `from massless.supervisor import run_supervised` and `from massless.__main__ import load_app`), loads the app, and runs serve/supervisor. `manage.py` already did `django.setup()`.
- [ ] Test. Commit `feat(management): runmassless Django command`.

## Task 8: Benchmark sync endpoint + multi-process bench note

**Files:** `benchmarks/app.py`; `tests/test_integration.py`

- [ ] Add a sync view `@api.get("/sync-hello")` `def sync_hello(): return {"message": "Hello World"}` to exercise the executor path. Add a smoke test that it serves 200 (it dispatches through the executor over the real server).
- [ ] Commit `feat(bench): sync endpoint for executor benchmark`.

## Self-Review
Spec coverage: sync dispatch (§2.1) -> Tasks 1-2; multi-process (§2.2) -> Tasks 4-6; mgmt command (§2.3) -> Task 7; lifecycle (§2.4) -> Tasks 1,4; error handling (§2.5) -> Task 3; benchmark (§6) -> Task 8. Name consistency: `Route.is_async`, `on_startup_hooks`/`on_shutdown_hooks`, `serve`/`serve_async`/`_make_socket`, `run_supervised`/`Supervisor`, `load_app`. Multi-process supervision + signals are the highest-risk; the verify step hardens them (and CI runs `--processes 2` best-effort). Method-aware routing/405 is explicitly out of scope.
