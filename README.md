# django-massless

[![CI](https://github.com/oliverhaas/django-massless/actions/workflows/ci.yml/badge.svg)](https://github.com/oliverhaas/django-massless/actions/workflows/ci.yml)

High-performance, Django-coupled API framework whose request pipeline runs in
**Cython/C over C-typed structures**, deferring materialization of Python/Django
objects until code actually reaches for them.

It is the same *architecture* as django-bolt: a C-native pipeline that only
crosses into Python at the user's handler, but with **Cython as the systems
language instead of Rust**. Cython compiles to CPython C-API calls
in the same binary, so there is no FFI seam. Calling the user's view is a bare
`PyObject_Call`, and the request object can be backed by C storage while still
being a real `django.http.HttpRequest` subclass that lazily fills its Django state
only when touched.

> [!WARNING]
> **Alpha, in active development.** All four phases of the
> [build plan](docs/superpowers/specs/2026-05-31-django-massless-design.md) are
> implemented (request pipeline, lazy promotion, tiered middleware, multi-process
> lifecycle), but APIs are unstable and it is not yet released to PyPI.

## Quick example

```python
# app.py
from massless import MasslessAPI
from massless._middleware import JWTAuth

api = MasslessAPI()

@api.get("/items/{item_id}")
async def read_item(item_id: int, q: str | None = None):
    return {"item_id": item_id, "q": q}

@api.get("/me", middleware=[JWTAuth(secret="...")])
async def me(request):
    return {"sub": request.auth["sub"]}   # JWT validated on the C fast path, no promotion
```

```console
python -m massless app:api --host 0.0.0.0 --port 8000 --processes 4
# or, inside a Django project:
python manage.py runmassless app:api --processes 4
```

## Phased build (all implemented)

| Phase | Goal | Status |
|-------|------|--------|
| 1 | Thin end-to-end slice (httptools protocol, C router, `MasslessRequest` fast path, native JSON view, C response builder). | done |
| 2 | Lazy promotion + Django glue (`_promote()` to a real `WSGIRequest`, parity suite, ORM, settings, request injection). | done |
| 3 | Tiered middleware (fast cdef tier: CORS/rate-limit/JWT auth + bridge to real Django middleware). | done |
| 4 | Dispatch hardening + lifecycle (sync thread-pool dispatch, `SO_REUSEPORT` multi-process + supervisor, `runmassless`, graceful shutdown). | done |

## Benchmarks

Performance is a day-one concern. The [`benchmarks/`](benchmarks/) harness compares
massless head-to-head with django-bolt and plain Django (case matrix ported from
django-bolt). On framework-bound endpoints, single-process massless runs **~2x
django-bolt** and **~30x plain Django**; JWT-validated requests stay on the C fast
path (`/auth/context` ~2.35x bolt, no promotion). Per-phase results are committed in
[`benchmarks/results/`](benchmarks/results/) (`PHASE1.md`-`PHASE4.md`); see
[`benchmarks/README.md`](benchmarks/README.md). Numbers are first-pass, single-run.

## License

MIT
