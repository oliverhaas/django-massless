#!/usr/bin/env bash
# Benchmark a *running* server (massless or django-bolt) and write a markdown
# report that benchmarks/compare.py can diff. Framework-agnostic: it only hits
# HTTP endpoints, so point it at whichever server is live.
#
# Typical head-to-head (massless on :8000, django-bolt on :8001):
#
#   PORT=8000 LABEL=massless OUT=results/massless.md ./run.sh
#   PORT=8001 LABEL=bolt     OUT=results/bolt.md     ./run.sh
#   python compare.py results/bolt.md results/massless.md
#
# The cases mirror benchmarks/cases.md (ported from django-bolt). The server under
# test must expose those paths; see cases.md for the endpoint contract.
#
# Knobs (env vars):
#   HOST=127.0.0.1 PORT=8000   target server
#   C=50 N=10000               bombardier connections / total requests
#   LABEL=massless             label printed in the report header
#   OUT=results/massless.md    write report here (default: stdout)
#   AUTH_TOKEN=<jwt>           if set, run the JWT auth cases
#   WITH_DB=1                  also run DB-bound cases (seeds rows first)
set -uo pipefail

HOST=${HOST:-127.0.0.1}
PORT=${PORT:-8000}
C=${C:-50}
N=${N:-10000}
LABEL=${LABEL:-massless}
WITH_DB=${WITH_DB:-0}
AUTH_TOKEN=${AUTH_TOKEN:-}
OUT=${OUT:-}
BASE="http://$HOST:$PORT"

# bombardier is the same load tool django-bolt uses, so numbers are comparable.
BOMBARDIER_BIN=""
for cand in bombardier "$HOME/go/bin/bombardier" "$HOME/.local/bin/bombardier"; do
  if command -v "$cand" >/dev/null 2>&1; then BOMBARDIER_BIN="$cand"; break; fi
  [ -x "$cand" ] && BOMBARDIER_BIN="$cand" && break
done
if [ -z "$BOMBARDIER_BIN" ]; then
  echo "ERROR: bombardier not found. Install: go install github.com/codesenberg/bombardier@latest" >&2
  exit 1
fi

log() { echo "$@" >&2; }

# Wait for the server to answer 200 on / (up to MAX_WAIT seconds).
wait_for_server() {
  local max_wait=${MAX_WAIT:-15} elapsed=0 code
  while [ "$elapsed" -lt "$max_wait" ]; do
    code=$(curl -s -o /dev/null -w '%{http_code}' "$BASE/") || code=000
    [ "$code" = "200" ] && return 0
    sleep 1; elapsed=$((elapsed + 1))
  done
  log "Server at $BASE not ready after ${max_wait}s (last status: ${code:-?}); aborting."
  exit 1
}

wait_for_server
if [ -n "$OUT" ]; then mkdir -p "$(dirname "$OUT")"; exec >"$OUT"; fi

# bench TITLE PATH [extra bombardier args...]
# Emits a "### TITLE (PATH)" header plus bombardier's RPS / latency / status mix.
bench() {
  local title="$1" path="$2"; shift 2
  local report
  report=$("$BOMBARDIER_BIN" -c "$C" -n "$N" -l "$@" "$BASE$path" 2>&1 | tr '\r' '\n')
  echo "### $title ($path)"
  if echo "$report" | grep -q 'Reqs/sec'; then
    echo "$report" | grep -E "(Reqs/sec|Latency|[0-9]xx -|50%|75%|90%|99%)"
  else
    echo "Skipped or errored: $(echo "$report" | tail -1)"
  fi
  echo ""
}

JSON='Content-Type: application/json'
PARSE_BODY='{"title":"bench","count":100,"items":[{"name":"a","price":1.0,"is_offer":true}]}'
SER_RAW='{"id":1,"name":"John Doe","email":"john@example.com","bio":"dev"}'
SER_VAL='{"id":1,"name":"  John Doe  ","email":"JOHN@EXAMPLE.COM","bio":"dev"}'
FORM='Content-Type: application/x-www-form-urlencoded'

echo "# Benchmark report: $LABEL"
echo "Config: C=$C N=$N target=$BASE"
echo ""

echo "## Framework-bound, no DB"
bench "Root JSON Async" "/"
bench "Root JSON Sync" "/sync"
bench "10kb JSON Async" "/10k-json"
bench "10kb JSON Sync" "/sync-10k-json"
bench "1kb JSON" "/1k-json"
bench "100kb JSON" "/100k-json"
bench "500kb JSON" "/500k-json"
bench "1mb JSON" "/1m-json"
bench "Path Param int" "/items/12345"
bench "Path + Query" "/items/12345?q=hello"
bench "Typed Params" "/bench/params/typed/12345?count=3&price=1.5&active=true"
bench "Multi Query" "/bench/params/multi-query?page=2&limit=20&sort=id&order=asc&filter_active=true&min_price=1.0&max_price=9.0"
bench "Header Param" "/header" -H "x-test: val"
bench "Cookie Param" "/cookie" -H "Cookie: session=abc"
bench "Exception 404" "/exc"
bench "HTML Response" "/html"
bench "Redirect 302" "/redirect"
bench "JSON Parse/Validate" "/bench/parse" -m POST -H "$JSON" -b "$PARSE_BODY"
bench "Form urlencoded" "/form" -m POST -H "$FORM" -b "name=TestUser&age=25&email=test%40example.com"
bench "Serializer Raw" "/bench/serializer-raw" -m POST -H "$JSON" -b "$SER_RAW"
bench "Serializer Validated" "/bench/serializer-validated" -m POST -H "$JSON" -b "$SER_VAL"
bench "Union Single Concrete" "/bench/single"
bench "Union Single" "/bench/union-single"
bench "Union List Concrete" "/bench/list"
bench "Union List" "/bench/union-list"
bench "Feed Post Branch" "/feed/0"
bench "Feed Comment Branch" "/feed/1"
bench "Feed Like Branch" "/feed/2"
bench "Feed Mixed 100" "/feed"
bench "Multi-Response Tuple" "/bench/multi/tuple"
bench "Multi-Response Dict" "/bench/multi/dict"

if [ -n "$AUTH_TOKEN" ]; then
  echo "## Auth (JWT)"
  AUTH="Authorization: Bearer $AUTH_TOKEN"
  bench "Auth Context" "/auth/context" -H "$AUTH"
  bench "Auth No User Access" "/auth/no-user-access" -H "$AUTH"
  bench "Auth Me" "/auth/me" -H "$AUTH"
  bench "Auth Me Dependency" "/auth/me-dependency" -H "$AUTH"
else
  log "Skipping auth cases: set AUTH_TOKEN=<jwt> to enable them."
fi

if [ "$WITH_DB" = "1" ]; then
  echo "## DB-bound (ORM ceiling)"
  log "Seeding rows for DB cases..."
  curl -s -o /dev/null "$BASE/users/seed?count=1000" || log "Warning: seed call failed."
  bench "Users Full10 Async" "/users/full10"
  bench "Users Full10 Sync" "/users/sync-full10"
  bench "Users Mini10 Async" "/users/mini10"
  bench "Users Mini10 Sync" "/users/sync-mini10"
  bench "CRUD List" "/bench/items"
  bench "CRUD Retrieve" "/bench/items/1"
  curl -s -o /dev/null -X POST "$BASE/users/delete" || true
else
  log "Skipping DB cases: set WITH_DB=1 to enable them."
fi

log "Done. Report -> ${OUT:-stdout}"
