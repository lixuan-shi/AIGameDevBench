#!/usr/bin/env bash
# Full bench run over the 50 filtered testcases, using `claude -p {task}` as the
# harness. Results, agent-produced code, and per-case logs are all persisted
# under bench_runs/filtered50/.
#
# Usage (from repo root):
#   tmux new -s bench50
#   bash scripts/run_bench50.sh
# Detach with Ctrl-b d ; reattach with `tmux attach -t bench50`.
set -uo pipefail
cd "$(dirname "$0")/.."

OUT=bench_runs/filtered50
mkdir -p "$OUT"

aigdbench run \
  --testcases-dir ./testcases_filtered \
  --driver command \
  --harness-cmd 'claude -p {task} --dangerously-skip-permissions' \
  --harness claude \
  --godot-binary 'D:/Godot/godot/bin/godot.exe' \
  --timeout 900 \
  --report "$OUT/report.json" \
  --artifacts-dir "$OUT/artifacts" \
  --log-dir "$OUT/logs" 2>&1 | tee "$OUT/run.log"

echo "BENCH_EXIT=${PIPESTATUS[0]}" | tee -a "$OUT/run.log"
