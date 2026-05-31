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
> **Pre-alpha, not yet released.** This repository currently holds the design
> and the project scaffold. The architecture and phased build plan live in
> [`docs/superpowers/specs/2026-05-31-django-massless-design.md`](docs/superpowers/specs/2026-05-31-django-massless-design.md).

## Phased build

| Phase | Goal |
|-------|------|
| 1 | Thin end-to-end slice (httptools protocol, C router, `MasslessRequest` fast path, native JSON view, C response builder). Proves the thesis vs django-bolt. |
| 2 | Lazy promotion + Django glue (`_promote()`, `HttpRequest` subclass invariants, ORM, settings). |
| 3 | Tiered middleware (fast cdef tier + bridge to real Django middleware). |
| 4 | Dispatch hardening + lifecycle (sync/async, thread-pool, errors, signals, multi-process). |

## Benchmarks

Performance is a day-one concern. The [`benchmarks/`](benchmarks/) harness
mirrors django-bolt's benchmark case matrix so the two frameworks can be compared
head-to-head from the first runnable slice. See
[`benchmarks/README.md`](benchmarks/README.md).

## License

MIT
