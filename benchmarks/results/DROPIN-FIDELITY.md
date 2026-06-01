# Drop-in HTTP fidelity hardening (2026-06-01)

After the Phase 1 drop-in landed, a parity audit against uvicorn+Django's `ASGIHandler`
found request/response gaps. These were fixed and adversarially reviewed; the table below
is what now matches uvicorn+Django, plus the known limitations.

## Matched

| Area | Behavior |
|------|----------|
| Client address | `REMOTE_ADDR`/`REMOTE_HOST`/`REMOTE_PORT` from the TCP peer; a single `X-Forwarded-For` from a trusted peer (uvicorn's default `proxy_headers`, trust `127.0.0.1`, `MASSLESS_FORWARDED_ALLOW_IPS` to change) |
| Scheme | `request.scheme`/`is_secure()` honor a single `X-Forwarded-Proto` from a trusted peer (fixes a `SECURE_SSL_REDIRECT` loop behind a TLS proxy) |
| Server address | `SERVER_NAME`/`SERVER_PORT` from the local bind address, not the Host header |
| Headers | duplicate request headers comma-joined; `_`-bearing names dropped (spoof guard); multiple `Cookie` folded with `; ` |
| Path | percent-decoded before resolution (`/caf%C3%A9/` resolves like ASGI) |
| Status line | exact reason phrase from Django (no more `302 OK`) |
| Framing | HEAD = headers only; 204/304 = no body, `Content-Length: 0` (as Django's `CommonMiddleware` + uvicorn emit), 304 drops `Content-Type` |
| Headers out | `Date` header (cached once/sec); present-but-empty `Content-Type` preserved |
| Connection | keep-alive from HTTP version + `Connection: close`; socket closed when not keep-alive; implicit keep-alive (no `Connection` header), as uvicorn |
| Continue | `Expect: 100-continue` answered |
| Errors | malformed request -> `400` then close (e.g. TLS to the plaintext port); an internal `500` closes the connection |
| Signals | `request_started` + `request_finished` fire on the thread-sensitive executor, so `close_old_connections`/`reset_queries` manage the sync views' DB connections |

## Known limitations

- Streaming responses (`StreamingHttpResponse`/SSE) answer a clear `501` (Phase 4).
- Request bodies are buffered in memory (no spool-to-disk for very large uploads).
- Responses use `Content-Length` framing, never chunked (uvicorn chunks a body without a
  `Content-Length`); both deliver identical bytes.
- Reason phrase honors a view's custom `reason_phrase` (uvicorn discards it for the IANA one).

## Benchmark (same app, single process, saturating)

The fidelity work added per-request cost that uvicorn+Django also pay (`request_started`,
and `response.close()` on the executor thread). The competitive ratio holds:

| Stack | uvicorn+Django req/s | massless req/s | speedup |
|-------|---------------------:|---------------:|--------:|
| full default (`SecurityMiddleware`+`CommonMiddleware`) | ~1,330 | ~3,470 | ~2.6x |
| lean (empty `MIDDLEWARE`) | ~2,260 | ~7,050 | ~3.1x |

(Single bombardier client + single worker, so absolute numbers are lower than the 4-worker
saturating run in `DROPIN-PHASE1.md`; the ratio is the point.) Moving `response.close()`
onto the executor thread for correct connection management cost massless ~7% throughput.
