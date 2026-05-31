# django-massless Phase 4: Dispatch hardening and lifecycle

**Status:** Approved for implementation planning
**Date:** 2026-05-31
**Parent design:** [2026-05-31-django-massless-design.md](2026-05-31-django-massless-design.md) (§6, §10 Phase 4)

---

## 1. Goal and exit criterion

Make the server production-shaped: sync views run safely, multiple processes serve
one port, a Django management command launches it, and the process shuts down
gracefully.

**Exit criterion:**
1. A **sync** view (`def`, not `async def`) is dispatched on a thread-pool executor and
   serves correctly (including blocking Django ORM), while async views still run on the
   loop. The dispatch path is chosen once at registration.
2. The server runs **N worker processes** sharing one port via `SO_REUSEPORT`; a master
   supervises them (spawn, restart on unexpected exit, graceful shutdown on
   `SIGTERM`/`SIGINT`).
3. `python manage.py runmassless <module:api> --processes N --workers T` launches the
   server inside a Django project (settings auto-loaded), and the standalone
   `python -m massless` runner also gains `--processes`.
4. `@api.on_startup` / `@api.on_shutdown` hooks run once per worker; in-flight requests
   drain on shutdown.
5. Unhandled view exceptions are logged (with traceback) and return a `500`; the error
   path never leaks a Python traceback to the client unless `DEBUG` is set.

## 2. Decisions

1. **Sync dispatch via a thread-pool executor.** At registration, `inspect.iscoroutinefunction`
   splits views into async (awaited on the loop) and sync (run via
   `loop.run_in_executor(pool, ...)` on a dedicated `ThreadPoolExecutor`, configurable
   `--workers`/`max_workers`). The binder + middleware fast tier stay on the loop thread;
   only the view body runs in the thread, where the blocking ORM is safe. A sync view's
   `MasslessRequest` works the same (promotion is thread-safe enough for one request,
   which is confined to its thread).
2. **Multi-process via `SO_REUSEPORT`.** Each worker process creates its own listening
   socket with `SO_REUSEPORT` bound to the same `(host, port)`; the kernel load-balances
   connections across workers. Workers are independent (no shared state beyond the OS);
   this matches the rate-limit "process-local" note from Phase 3. A master process spawns
   workers (via `multiprocessing` with a spawn/fork start method), monitors them, restarts
   a worker that exits unexpectedly, and forwards `SIGTERM`/`SIGINT` for graceful shutdown.
   `--processes 1` runs in-process (no master) for dev/tests.
3. **Django management command.** `runmassless` (a `BaseCommand` under
   `massless/management/commands/`) parses `module:api`, host, port, processes, workers,
   and runs the server. Because `manage.py` already calls `django.setup()`, settings and
   apps are loaded, so promotion/ORM/bridge work. The standalone `python -m massless`
   path remains for non-Django use and gains `--processes`.
4. **Lifecycle hooks + graceful shutdown.** `MasslessAPI` gains `on_startup`/`on_shutdown`
   registries (lists of zero-arg sync-or-async callables). Each worker runs startup hooks
   before serving and shutdown hooks after the server stops accepting. On `SIGTERM`/`SIGINT`,
   a worker stops accepting new connections, lets in-flight request tasks finish (bounded
   grace period), runs shutdown hooks, and exits.
5. **Error handling.** The protocol's view/dispatch `except` logs via the `massless` logger
   (`logger.exception`) and returns a `500`. With `settings.DEBUG` true (and settings
   configured), the body may include the traceback; otherwise a plain `Internal Server
   Error`. 404 stays as today.

## 3. Module changes

```
src/massless/
  _dispatch.pyx (or extend _protocol.pyx)  # async-vs-sync view invocation via the executor
  server.py                                 # serve(): socket(SO_REUSEPORT) + uvloop; signal handling; hooks
  supervisor.py                             # master: spawn/monitor/restart/shutdown N workers
  app.py                                    # is_async flag per route; on_startup/on_shutdown registries
  __main__.py                               # --processes / --workers; delegate to supervisor or serve
  management/__init__.py
  management/commands/__init__.py
  management/commands/runmassless.py        # Django BaseCommand wrapping the runner
```

## 4. Dispatch (Phase 4)

```
... fast-tier before() ...
  route.is_async? -- yes --> await view(**kwargs)                  (loop thread)
                    no  --> await loop.run_in_executor(pool, partial(view, **kwargs))  (worker thread; blocking ORM safe)
  -> wrap -> after() -> serialize
```

Process model:

```
master (runmassless --processes N)
  ├─ worker 0: socket(SO_REUSEPORT) -> uvloop -> startup hooks -> serve_forever
  ├─ worker 1: ...
  └─ worker N-1: ...
  (SIGTERM/SIGINT -> signal each worker -> drain -> shutdown hooks -> exit; restart on unexpected death)
```

## 5. Testing strategy

- **Sync dispatch:** a sync view returning a dict serves correctly; a sync view doing a
  blocking ORM read works (pytest-django); assert it ran off the loop thread (e.g. record
  `threading.get_ident()` differs from the loop thread) and that async views still work.
- **Executor selection:** `iscoroutinefunction` routing picks the right path; a sync and an
  async route in the same app both serve.
- **SO_REUSEPORT:** two in-process servers bound to the same port with `SO_REUSEPORT` both
  accept (smoke); a `--processes 2` run serves requests across workers (integration, best
  effort in CI).
- **Lifecycle:** `on_startup`/`on_shutdown` hooks fire (sync and async); graceful shutdown
  closes the server and runs shutdown hooks; in-flight request completes before exit.
- **Error handling:** a view that raises returns `500` and logs; with `DEBUG=False` the body
  is generic; `DEBUG=True` includes the traceback.
- **Supervisor:** a worker that exits unexpectedly is restarted (unit-test the supervisor
  loop with a fake worker target); `SIGTERM` stops all workers.
- **Regression:** all Phase 1-3 tests pass; the fast path and no-promotion hold.

## 6. Benchmark (after the phase): multi-process N-vs-N

This is the capstone benchmark. With `SO_REUSEPORT`, run massless, django-bolt, and plain
Django each with **N=2 (and N=4) worker processes** and compare RPS on the core
framework-bound endpoints (matching real deployment), alongside the single-process numbers
from Phase 1. Also benchmark a **sync** view (thread-pool dispatch) vs an async view to
show the executor overhead. Confirm no single-process regression.

## 7. Out of scope for Phase 4

Cross-process shared rate-limit/state (still process-local); auto-reload/hot-restart on
code change; HTTP/2; graceful zero-downtime worker rollover; Windows process model
(POSIX `SO_REUSEPORT` + fork/spawn is the target). Method-aware routing / `405` stays as a
later enhancement (the router matches on path; method dispatch is not added here).

## 8. Risks

- **Thread-pool + per-request `MasslessRequest`:** a sync view runs in a worker thread; the
  request object is confined to that request, so no cross-thread sharing, but promotion
  inside a thread must not assume the loop thread. Covered by the sync-ORM test.
- **`SO_REUSEPORT` portability:** Linux/macOS support it; the socket must set the option
  before `bind`. uvloop's `create_server` can take a pre-made socket. Tested on Linux CI.
- **Signal handling under uvloop + multiprocessing:** the master must install handlers and
  forward to workers; workers must install loop signal handlers (`loop.add_signal_handler`).
  Graceful drain needs a bounded timeout to avoid hangs. Covered by the lifecycle tests.
- **Management command import:** `runmassless` must not import the compiled server at module
  import in a way that breaks `manage.py` for non-serving commands; import lazily inside
  `handle()`.
