#!/usr/bin/env bash
# Single-core benchmark across every server on identical framework-bound endpoints.
# Server pinned to one core (cpu0), bombardier to others (cpu4-12). The Django servers
# (massless, uvicorn, granian) all serve benchmarks/bench/; django-bolt runs its own
# example app. Swaps the installed Django (stock <-> django-asyncio fork) between groups.
#
#   ./run_all.sh                  # lean middleware
#   BENCH_FULL_MIDDLEWARE=1 ./run_all.sh
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
MSL_REPO="$(cd "$HERE/.." && pwd)"
MSLPY="$MSL_REPO/.venv/bin/python"
FORK_SRC="${FORK_SRC:-/home/ohaas/e1+/django-asyncio}"
BOLT_REPO="${BOLT_REPO:-/home/ohaas/e1+/django-bolt}"
BOLTPY="$BOLT_REPO/.venv/bin/python"
BOMB="${BOMBARDIER:-$HOME/.local/bin/bombardier}"
C="${C:-50}"; DUR="${DUR:-5s}"; MW="${BENCH_FULL_MIDDLEWARE:-0}"
SRV_CPU="${SRV_CPU:-0}"; CLI_CPU="${CLI_CPU:-4-12}"; PORT="${PORT:-8500}"

ENDPOINTS=(
  "root|/"
  "sync-root|/sync"
  "1k-json|/1k-json"
  "10k-json|/10k-json"
  "100k-json|/100k-json"
  "items|/items/12345"
  "items+q|/items/12345?q=hello"
  "plaintext|/plaintext"
)
CONFIGS=("massless[django]" "uvicorn+django" "massless[django-asyncio]" "granian-rsgi+fork" "django-bolt")
declare -A RESULTS

rps() { taskset -c "$CLI_CPU" "$BOMB" -c "$C" -d "$DUR" -l "$1" 2>&1 | tr '\r' '\n' | grep -E 'Reqs/sec' | head -1 | awk '{print $2}'; }
wait_up() { for _ in $(seq 1 50); do [ "$(curl -s -o /dev/null -w '%{http_code}' "$1" 2>/dev/null)" = "200" ] && return 0; sleep 0.3; done; return 1; }

bench_server() {  # $1 name, $2 cwd, rest = command
  local name="$1" cwd="$2"; shift 2
  ( cd "$cwd" && exec "$@" ) >"/tmp/srv-${name//[^a-z]/_}.log" 2>&1 &
  if ! wait_up "http://127.0.0.1:$PORT/"; then
    echo "  [$name] FAILED to start:"; tail -4 "/tmp/srv-${name//[^a-z]/_}.log" | sed 's/^/    /'
    fuser -k "$PORT/tcp" 2>/dev/null; sleep 1; return 1
  fi
  for ep in "${ENDPOINTS[@]}"; do
    local label="${ep%%|*}" pathq="${ep#*|}"
    if [ "$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT$pathq")" = "200" ]; then
      RESULTS["$name,$label"]=$(rps "http://127.0.0.1:$PORT$pathq")
    else
      RESULTS["$name,$label"]="n/a"
    fi
  done
  fuser -k "$PORT/tcp" 2>/dev/null; sleep 1
  echo "  [$name] done"
}

set_django() {  # stock | fork
  if [ "$1" = fork ]; then
    uv pip install --python "$MSLPY" "$FORK_SRC" granian >/dev/null 2>&1
  else
    uv pip uninstall --python "$MSLPY" django >/dev/null 2>&1
    uv pip install --python "$MSLPY" 'Django>=5.2,<7' >/dev/null 2>&1
  fi
  echo "  [django: $("$MSLPY" -c 'import django;print(django.get_version())')]"
}

echo "single-core suite | server cpu$SRV_CPU | client cpu$CLI_CPU | C=$C dur=$DUR | full_mw=$MW"
DJ_ENV=(env "PYTHONPATH=$HERE" "DJANGO_SETTINGS_MODULE=bench.settings" "BENCH_FULL_MIDDLEWARE=$MW")

echo "== stock Django group =="; set_django stock
bench_server "massless[django]" "$HERE" taskset -c "$SRV_CPU" "${DJ_ENV[@]}" "$MSLPY" -m massless --settings bench.settings --port "$PORT" --processes 1
bench_server "uvicorn+django" "$HERE" taskset -c "$SRV_CPU" "${DJ_ENV[@]}" "$MSLPY" -m uvicorn bench.asgi:application --port "$PORT" --workers 1 --loop uvloop --no-access-log

echo "== fork Django group =="; set_django fork
bench_server "massless[django-asyncio]" "$HERE" taskset -c "$SRV_CPU" "${DJ_ENV[@]}" "$MSLPY" -m massless --settings bench.settings --port "$PORT" --processes 1
bench_server "granian-rsgi+fork" "$HERE" taskset -c "$SRV_CPU" "${DJ_ENV[@]}" "$MSLPY" -m granian --interface rsgi bench.rsgi:application --host 127.0.0.1 --port "$PORT" --workers 1 --loop uvloop
set_django stock  # restore repo default

echo "== django-bolt =="
bench_server "django-bolt" "$BOLT_REPO/python/example" taskset -c "$SRV_CPU" env DJANGO_BOLT_WORKERS=1 "$BOLTPY" manage.py runbolt --host 127.0.0.1 --port "$PORT" --processes 1

printf "\n| endpoint"; for c in "${CONFIGS[@]}"; do printf " | %s" "$c"; done; printf " |\n|---"; for _ in "${CONFIGS[@]}"; do printf "|---:"; done; printf "|\n"
for ep in "${ENDPOINTS[@]}"; do
  label="${ep%%|*}"; printf "| %s" "$label"
  for c in "${CONFIGS[@]}"; do printf " | %s" "${RESULTS[$c,$label]:-n/a}"; done
  printf " |\n"
done
