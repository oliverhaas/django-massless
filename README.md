# django-massless

[![CI](https://github.com/oliverhaas/django-massless/actions/workflows/ci.yml/badge.svg)](https://github.com/oliverhaas/django-massless/actions/workflows/ci.yml)

A **drop-in, high-performance server and request pipeline for an unmodified Django
project** (including django-ninja apps). You keep your `urls.py`, your views, your
`settings`, and your `MIDDLEWARE`; you run the project under massless instead of
uvicorn/gunicorn and it serves the *normal Django stack* faster.

The request pipeline runs in **Cython/C** (httptools + uvloop): it parses in C, builds
a lazy `MasslessRequest` that defers materializing the parts of the request a handler
never reads, runs on multiple processes via `SO_REUSEPORT`, and lets you put hot routes
on leaner middleware stacks. Django stays the source of truth: massless feeds the lazy
request through Django's own URL resolver, your `MIDDLEWARE`, and your view, so behavior
is identical to running under uvicorn.

> [!WARNING]
> **Alpha, in active development.** The project recently pivoted from a django-bolt-style
> API framework to this drop-in accelerator (see
> [the re-architecture design](docs/superpowers/specs/2026-06-01-django-massless-dropin-design.md)).
> Phase 1 (serve a normal Django project) is implemented; `MIDDLEWARE_STACKS` and
> streaming are in progress. APIs are unstable; not yet released to PyPI.

## Quick start

No app code changes. Point massless at your existing Django project:

```console
# inside a Django project (settings, urls.py, views, MIDDLEWARE unchanged):
python manage.py runmassless --host 0.0.0.0 --port 8000 --processes 4

# or standalone:
DJANGO_SETTINGS_MODULE=myproject.settings python -m massless --host 0.0.0.0 --port 8000 --processes 4
```

Your normal Django (or django-ninja) views serve through the C pipeline; sync views run
on Django's thread-sensitive executor exactly as under uvicorn.

## How it works

```
TCP (SO_REUSEPORT) -> uvloop -> Cython protocol -> httptools parse
  -> lazy MasslessRequest (META/GET/POST/body/COOKIES built on first touch)
  -> Django URL resolver (ROOT_URLCONF) -> your MIDDLEWARE -> your view
  -> HttpResponse -> C-serialize (status/headers/Set-Cookie/body) -> socket
```

`MasslessRequest` is a `WSGIRequest` subclass built from C buffers; an
attribute-by-attribute parity suite keeps it behaviorally identical to a stock Django
request. Multi-process, graceful shutdown, and lifecycle hooks come from the engine
built earlier.

## Status and roadmap

| Phase | Goal | Status |
|-------|------|--------|
| 1 | Serve an unmodified Django project: `MasslessHandler` over Django's resolver + `MIDDLEWARE`, lazy request, multi-process, byte-identical responses. | done |
| 2 | `MIDDLEWARE_STACKS`: named middleware stacks in settings, assignable per route, so hot routes run lean and stay on the fast path. | next |
| 3 | django-ninja example + the benchmark pivot (massless vs uvicorn+Django / uvicorn+ninja on the same app). | planned |
| 4 | Streaming responses (`StreamingHttpResponse`/SSE), optional WSGI mode. | later |

## Honesty about performance

A full-fidelity drop-in runs Django's resolver, your whole `MIDDLEWARE`, and your view
(all Python), so the default-path speedup is **bounded** by that cost. With the full
stock middleware the lazy request is promoted before the view anyway, so Phase 1's gain
over uvicorn+Django is mostly the C parse + transport. The real lever is per-route lean
stacks (`MIDDLEWARE_STACKS`, Phase 2). The benchmark harness in
[`benchmarks/`](benchmarks/) compares against uvicorn+Django honestly; results land with
Phase 3. (The earlier `PHASE1-4.md` numbers measured the now-retired bolt-style engine,
not the drop-in.)

## License

MIT
