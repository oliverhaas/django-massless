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

## Install

massless is backed by Django but does not pin which one. Install exactly one extra
(both provide the `django` package, so they are mutually exclusive):

```console
pip install django-massless[django]          # stock Django
pip install django-massless[django-asyncio]  # the async-optimized Django fork
```

`[django-asyncio]` pulls the [django-asyncio fork](https://github.com/oliverhaas/django-asyncio),
whose native-async middleware/ORM removes the per-middleware `sync_to_async` tax massless
cannot fix on its own. On a full middleware stack that is ~2.9x faster than stock Django
under massless ([benchmarks/results/DROPIN-DJANGO-VARIANTS.md](benchmarks/results/DROPIN-DJANGO-VARIANTS.md)).
It is experimental (the fork tracks a dev branch).

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
| 1b | HTTP fidelity hardening: `REMOTE_ADDR` + trusted `X-Forwarded-Proto`/`-For`, header folding + underscore drop, percent-decoded paths, exact reason phrase, HEAD/204/304 framing, `Date`, keep-alive + `Connection: close`, `Expect: 100-continue`, `request_started`/`finished`. | done |
| 2 | `MIDDLEWARE_STACKS`: named middleware stacks in settings, assignable per route, so hot routes run lean and stay on the fast path. | next |
| 3 | django-ninja example + the benchmark pivot (massless vs uvicorn+Django / uvicorn+ninja on the same app). | planned |
| 4 | Streaming responses (`StreamingHttpResponse`/SSE), optional WSGI mode. | later |

### HTTP fidelity

massless aims to behave like the same project under uvicorn+Django. The request (`META`,
client address, scheme behind a trusted proxy, headers, cookies, percent-decoded path) and
the response (status line + reason phrase, `Content-Type`/`Content-Length`, `Set-Cookie`,
`Date`, HEAD/204/304 framing, keep-alive) are matched, and `request_started`/`request_finished`
fire on the executor thread so DB-connection bookkeeping works. Known gaps: streaming
responses answer a clear `501` (Phase 4); request bodies are buffered in memory (no
spool-to-disk for very large uploads); responses use `Content-Length` framing rather than
chunked.

## Performance

Serving the **same unmodified Django app** (4 workers, saturating load), massless is
**~3.3x faster than uvicorn+Django on the full default middleware stack** and **~5.5x on
lean middleware**, while returning byte-identical responses
([`benchmarks/results/DROPIN-PHASE1.md`](benchmarks/results/DROPIN-PHASE1.md)):

| Endpoint | uvicorn+Django | massless | speedup |
|----------|---------------:|---------:|--------:|
| `/` (full default stack) | 4,691 | 15,320 | 3.27x |
| `/` (lean middleware) | 7,686 | 42,804 | 5.57x |

A full-fidelity drop-in still runs Django's resolver, your `MIDDLEWARE`, and your view in
Python, so the gain is bounded by that. The ~3.3x comes from the C parse, building the
request directly from C buffers (no ASGI scope round-trip), and C response serialization;
the lazy request adds the rest on lean routes, which per-route stacks
(`MIDDLEWARE_STACKS`, Phase 2) will let you opt into. Numbers are first-pass, single-run,
on loopback. (The earlier `PHASE1-4.md` numbers measured the now-retired bolt-style
engine, not the drop-in.)

## License

MIT
