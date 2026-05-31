# Benchmarks

Performance is a day-one concern for massless, so the benchmark harness exists
before the framework does. The case matrix mirrors django-bolt's benchmark suite
(the cases, not the code) so the two frameworks can be compared head-to-head from
the first runnable slice (design Phase 1).

- [`cases.md`](cases.md): the full case matrix and the endpoint contract a server
  must expose. The **Promotes?** column ties each case to the design's
  no-promotion goal.
- [`run.sh`](run.sh): benchmarks a running server and writes a markdown report.
- [`compare.py`](compare.py): diffs two reports and gates the result against the
  design goal (match or beat django-bolt on framework-bound endpoints).

## Prerequisites

[bombardier](https://github.com/codesenberg/bombardier) is the load tool (the same
one django-bolt uses, so numbers are directly comparable):

```console
go install github.com/codesenberg/bombardier@latest
```

## Running

`run.sh` benchmarks a server that is *already running*; it does not start one.
That keeps it framework-agnostic. Start massless and django-bolt on different
ports, benchmark each, then compare:

```console
# massless on :8000, django-bolt on :8001 (start each in its own shell)

PORT=8000 LABEL=massless OUT=results/massless.md ./run.sh
PORT=8001 LABEL=bolt     OUT=results/bolt.md     ./run.sh

python compare.py results/bolt.md results/massless.md
```

`compare.py` exits non-zero if massless regresses by more than `--max-regression`
(default 2%) on any core framework-bound endpoint, so it doubles as a CI gate once
there is something to run.

### Multi-process / saturating runs

`run.sh` uses one bombardier process per endpoint, which is fine for single-process
servers but **cannot saturate a multi-worker server**: one bombardier is itself
~one-core-bound (mostly loopback syscalls), so a single-client run measures the client,
not the server. For an `--processes N` server, drive it with several parallel clients
and sum their throughput with [`aggregate.sh`](aggregate.sh):

```console
# server: python -m massless app:api --processes 4
./aggregate.sh 8000 / 8 48 6s        # 8 parallel clients, 48 conns each, 6s
```

Confirm the result is server-bound (not client-bound) by checking that the worker
processes are at ~100% CPU each while it runs (`pidstat -u -p "$(pgrep -d, -f 'massless benchmarks')" 4 1`);
if they are idle, raise the client/connection count. See `aggregate.sh`'s header and
`results/PHASE4.md` for the saturating multi-process methodology and numbers.

### Knobs

| Env var | Default | Meaning |
|---------|---------|---------|
| `HOST` / `PORT` | `127.0.0.1` / `8000` | target server |
| `C` / `N` | `50` / `10000` | bombardier connections / total requests |
| `LABEL` | `massless` | label in the report header |
| `OUT` | stdout | write the markdown report here |
| `AUTH_TOKEN` | unset | a JWT; if set, the auth cases run |
| `WITH_DB` | `0` | set to `1` to also run the DB-bound cases (seeds rows first) |

## Status

The runner and the gate are ready now. The benchmark app that implements the
endpoint contract in [`cases.md`](cases.md) lands with Phase 1 (the thin
end-to-end slice). Until then, point `run.sh` at django-bolt to capture a baseline.

Note: setuptools editable installs do not auto-rebuild on `.pyx` changes. After
editing Cython sources, run `uv sync` (or `uv pip install -e .`) before
benchmarking so the compiled extension is current.
