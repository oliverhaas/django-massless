#!/usr/bin/env bash
# Single-core ceiling probe: how fast is httptools+uvloop with NO Django?
# Server pinned to cpu0, bombardier to cpu4-12 (same methodology as run_all.sh).
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
MSL_REPO="$(cd "$HERE/../.." && pwd)"
MSLPY="$MSL_REPO/.venv/bin/python"
BOMB="${BOMBARDIER:-$HOME/.local/bin/bombardier}"
C="${C:-50}"; DUR="${DUR:-6s}"
SRV_CPU="${SRV_CPU:-0}"; CLI_CPU="${CLI_CPU:-4-12}"; PORT="${PORT:-8600}"

rps() { taskset -c "$CLI_CPU" "$BOMB" -c "$C" -d "$DUR" -l "$1" 2>&1 | tr '\r' '\n' | grep -E 'Reqs/sec' | head -1 | awk '{print $2}'; }
wait_up() { for _ in $(seq 1 50); do [ "$(curl -s -o /dev/null -w '%{http_code}' "$1" 2>/dev/null)" = "200" ] && return 0; sleep 0.2; done; return 1; }

probe() {  # $1 mode
  local mode="$1"
  ( cd "$HERE" && exec taskset -c "$SRV_CPU" env MODE="$mode" PORT="$PORT" PYTHONPATH="$MSL_REPO/src" "$MSLPY" server.py ) >"/tmp/ceiling-$mode.log" 2>&1 &
  local pid=$!
  if ! wait_up "http://127.0.0.1:$PORT/"; then
    echo "  [$mode] FAILED:"; tail -5 "/tmp/ceiling-$mode.log" | sed 's/^/    /'
    kill "$pid" 2>/dev/null; return 1
  fi
  printf '  %-8s %s rps\n' "$mode" "$(rps "http://127.0.0.1:$PORT/")"
  kill "$pid" 2>/dev/null; wait "$pid" 2>/dev/null; sleep 0.5
}

echo "ceiling probe | server cpu$SRV_CPU | client cpu$CLI_CPU | C=$C dur=$DUR | port=$PORT"
probe raw
probe cython
