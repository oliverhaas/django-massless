#!/usr/bin/env bash
# Saturating multi-client load: drive a RUNNING server with several parallel
# bombardier processes and sum their Reqs/sec. A single bombardier process is
# itself CPU-bound (~one core, mostly loopback syscalls) and cannot saturate a
# multi-worker server, so a single-client run measures the CLIENT, not the server.
# This driver removes that ceiling by running CLIENTS independent load processes.
#
#   ./aggregate.sh PORT PATH [CLIENTS] [CONNS_PER_CLIENT] [DURATION]
#   ./aggregate.sh 8000 / 8 48 6s
#
# To trust a multi-process number, confirm the server is the bottleneck while this
# runs (in another shell):
#   pidstat -u -p "$(pgrep -d, -f 'massless benchmarks')" 4 1   # worker total ~= N*100%
#   mpstat 4 1                                                  # server cores busy, not idle
# If the workers are at ~100% each, the result is server-bound (trustworthy). If
# they are idle, raise CLIENTS / CONNS until they saturate.
set -uo pipefail

PORT=${1:?usage: aggregate.sh PORT PATH [CLIENTS] [CONNS] [DURATION]}
P=${2:?missing PATH}
CLIENTS=${3:-8}
CONNS=${4:-48}
DURATION=${5:-6s}
HOST=${HOST:-127.0.0.1}

BOMBARDIER_BIN=""
for cand in bombardier "$HOME/go/bin/bombardier" "$HOME/.local/bin/bombardier"; do
  command -v "$cand" >/dev/null 2>&1 && BOMBARDIER_BIN="$cand" && break
  [ -x "$cand" ] && BOMBARDIER_BIN="$cand" && break
done
[ -z "$BOMBARDIER_BIN" ] && { echo "ERROR: bombardier not found" >&2; exit 1; }

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
for i in $(seq 1 "$CLIENTS"); do
  ("$BOMBARDIER_BIN" -c "$CONNS" -d "$DURATION" "http://$HOST:$PORT$P" 2>&1 \
    | tr '\r' '\n' | grep 'Reqs/sec' | awk '{print $2}' > "$tmp/$i") &
done
wait 2>/dev/null

awk '{s+=$1; n++} END{printf "%-30s clients=%d conns=%d agg=%.0f req/s (per-client avg %.0f)\n", path, c, c*conns, s, (n?s/n:0)}' \
  path="$P" c="$CLIENTS" conns="$CONNS" "$tmp"/*
