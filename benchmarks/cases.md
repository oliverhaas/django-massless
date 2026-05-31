# Benchmark case matrix

These cases are ported from django-bolt's benchmark suite (the *cases*, not the
code) so massless and django-bolt can be compared head-to-head. The server under
test must expose these paths; that is the endpoint contract the Phase 1 benchmark
app implements. `run.sh` drives them, `compare.py` gates the result.

The **Promotes?** column is massless-specific. It records whether serving the
case is expected to trip the `MasslessRequest` promotion latch (materialize full
Django state). Framework-bound cases must answer **No**: they are the win
condition (design §2, §9), and the no-promotion assertion in the test suite
guards it.

## Framework-bound, no DB (PRIMARY: match or beat django-bolt)

| Case | Method | Path | Exercises | Promotes? |
|------|--------|------|-----------|-----------|
| Root JSON Async | GET | `/` | minimal dict serialize, async dispatch | No |
| Root JSON Sync | GET | `/sync` | minimal dict serialize, thread-pool dispatch | No |
| 10kb JSON Async | GET | `/10k-json` | medium JSON serialize, async | No |
| 10kb JSON Sync | GET | `/sync-10k-json` | medium JSON serialize, thread-pool | No |
| 1kb JSON | GET | `/1k-json` | small payload serialize | No |
| 100kb JSON | GET | `/100k-json` | large payload serialize | No |
| 500kb JSON | GET | `/500k-json` | larger payload serialize | No |
| 1mb JSON | GET | `/1m-json` | streaming-size payload serialize | No |
| Path Param int | GET | `/items/12345` | path capture + int coercion via C router | No |
| Path + Query | GET | `/items/12345?q=hello` | path + query parse | No |
| Typed Params | GET | `/bench/params/typed/12345?count=3&price=1.5&active=true` | typed path + query coercion | No |
| Multi Query | GET | `/bench/params/multi-query?page=2&limit=20&sort=id&order=asc&filter_active=true&min_price=1.0&max_price=9.0` | many query params | No |
| Header Param | GET | `/header` (`x-test` header) | C header API read, PlainText response | No |
| Cookie Param | GET | `/cookie` (`session` cookie) | cookie read without full COOKIES build | No |
| Exception 404 | GET | `/exc` | error to response on the fast path | No |
| HTML Response | GET | `/html` | text/html response builder | No |
| Redirect 302 | GET | `/redirect` | 3xx response + Location header | No |
| JSON Parse/Validate | POST | `/bench/parse` | request body decode + validate (msgspec) | No |
| Form urlencoded | POST | `/form` | urlencoded form parse | No |
| Form Typed | POST | `/bench/form/typed` | typed form-field coercion | No |
| Form Large | POST | `/bench/form/large` | 10-field form parse | No |
| Form Repeated Keys | POST | `/form-list` | multi-value form binding (urlencoded + multipart) | No |
| File Upload | POST | `/upload` | multipart file parse | No |
| Mixed Form + File | POST | `/mixed-form` | multipart fields + file | No |
| Serializer Raw | POST | `/bench/serializer-raw` | raw msgspec decode baseline | No |
| Serializer Validated | POST | `/bench/serializer-validated` | decode + custom validators | No |
| Union Single Concrete | GET | `/bench/single` | concrete response model | No |
| Union Single | GET | `/bench/union-single` | tagged-union dispatch, single | No |
| Union List Concrete | GET | `/bench/list` | concrete list response model | No |
| Union List | GET | `/bench/union-list` | tagged-union dispatch, 100 items | No |
| Feed Post Branch | GET | `/feed/0` | union branch resolution | No |
| Feed Comment Branch | GET | `/feed/1` | union branch resolution | No |
| Feed Like Branch | GET | `/feed/2` | union branch resolution | No |
| Feed Mixed 100 | GET | `/feed` | 100 mixed union items | No |
| Multi-Response Tuple | GET | `/bench/multi/tuple` | (body, status, headers) tuple return | No |
| Multi-Response Dict | GET | `/bench/multi/dict` | bare dict return | No |

Paired cases (`single` vs `union-single`, `list` vs `union-list`) do identical
Python work and emit byte-identical JSON. Diffing their RPS isolates union
dispatch / response-validation cost.

## Auth (JWT)

| Case | Method | Path | Exercises | Promotes? |
|------|--------|------|-----------|-----------|
| Auth Context | GET | `/auth/context` | JWT validated in fast tier, no DB | No |
| Auth No User Access | GET | `/auth/no-user-access` | authenticated, lazy, no `request.user` touch | No |
| Auth Me | GET | `/auth/me` | touches `request.user`, triggers DB query | Yes |
| Auth Me Dependency | GET | `/auth/me-dependency` | user via dependency, DB query | Yes |

`/auth/context` and `/auth/no-user-access` are key massless cases: a valid JWT is
verified on raw bytes in the fast tier, and the request never promotes. `/auth/me`
is the deliberate contrast that promotes and pays the DB cost.

## Bridge tier / Django middleware (promotes)

| Case | Method | Path | Exercises | Promotes? |
|------|--------|------|-----------|-----------|
| Django Middleware Demo | GET | `/middleware/demo` | Session + Auth + Messages middleware, template render | Yes |

## DB-bound (ORM ceiling: convergence expected, not a win condition)

Run with `WITH_DB=1`. The runner seeds rows first. These converge to stock Django
ORM throughput by design (the accepted ceiling, design §1).

| Case | Method | Path | Exercises | Promotes? |
|------|--------|------|-----------|-----------|
| Users Full10 Async | GET | `/users/full10` | 10-row full serialize, async ORM | Yes |
| Users Full10 Sync | GET | `/users/sync-full10` | 10-row full serialize, sync ORM | Yes |
| Users Mini10 Async | GET | `/users/mini10` | 10-row minimal serialize, async ORM | Yes |
| Users Mini10 Sync | GET | `/users/sync-mini10` | 10-row minimal serialize, sync ORM | Yes |
| CRUD List | GET | `/bench/items` | viewset list | Yes |
| CRUD Retrieve | GET | `/bench/items/1` | viewset retrieve | Yes |

## Concurrency / slow-IO

| Case | Method | Path | Exercises | Promotes? |
|------|--------|------|-----------|-----------|
| Slow IO | GET | `/bench/slow?ms=100` | async sleep, event-loop concurrency under load | No |

## Out of scope for massless v1

django-bolt also benchmarks native static/media file serving (`/static/...`,
`/media/...`), served entirely by its Rust handler. Streaming and file responses
are a stated v1 non-goal for massless (design §2), so these are listed for parity
but not part of the massless gate.
