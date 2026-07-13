#!/usr/bin/env bash
# One-shot launcher for the AIGameDevBench web dashboard.
#
# The dashboard (Reports + Testcases + Contents + Run + Webhooks tabs) is one
# server on :8000, run in a detached tmux session so it survives your shell
# closing. Webhook messages are shown IN the dashboard's Webhooks tab (reading
# .orchestrator/webhooks.jsonl). The Run tab launches the REAL production
# benchmark: docker image (reused) + one Kubernetes Job per testcase, harness
# from the cluster Secret -- NOT a local run. Results become a normal report.
#
# Port :8000 is opened PERMANENTLY at the OS level (iptables INPUT ACCEPT,
# persisted in /etc/iptables/rules.v4), so by default this script does NOT touch
# iptables. Pass --firewall to have the script open/close the port itself.
#
# Usage (from anywhere):
#   scripts/start_dashboard.sh                 # start (port already open)
#   scripts/start_dashboard.sh --stop          # stop (leaves port open)
#   scripts/start_dashboard.sh --foreground    # run in the foreground
#   scripts/start_dashboard.sh --firewall      # ALSO open/close the port in iptables
#
# Env overrides:
#   PORT(8000) HOST(0.0.0.0) REPORTS_DIR TESTCASES_DIR SESSION(aigdbench-web)
#   ALLOW_RUN(1) WEBHOOK_LOG(.orchestrator/webhooks.jsonl)
#   RUNNER_IMAGE K8S_NAMESPACE(default) HARNESS_SECRET(aigdbench-harness)
#   IMAGE_TESTCASES_DIR(/app/testcases_filtered) JOBS(16)
#   ALLOW_CIDR(0.0.0.0/0 => open to everyone; set e.g. 10.0.21.0/24 to restrict)
set -uo pipefail
cd "$(dirname "$0")/.."
REPO_ROOT="$(pwd)"

PORT="${PORT:-8000}"
HOST="${HOST:-0.0.0.0}"
REPORTS_DIR="${REPORTS_DIR:-$REPO_ROOT/dashboard_reports}"
TESTCASES_DIR="${TESTCASES_DIR:-$REPO_ROOT/testcases_filtered}"
SESSION="${SESSION:-aigdbench-web}"
ALLOW_RUN="${ALLOW_RUN:-1}"
WEBHOOK_LOG="${WEBHOOK_LOG:-$REPO_ROOT/.orchestrator/webhooks.jsonl}"
ALLOW_CIDR="${ALLOW_CIDR:-0.0.0.0/0}"
# Run tab = real docker + k8s matrix (one Job per testcase on this image).
RUNNER_IMAGE="${RUNNER_IMAGE:-harbor.omgwow.ai/beaver_hub-public/aigdbench-runner:latest}"
K8S_NAMESPACE="${K8S_NAMESPACE:-default}"
HARNESS_SECRET="${HARNESS_SECRET:-aigdbench-harness}"
IMAGE_TESTCASES_DIR="${IMAGE_TESTCASES_DIR:-/app/testcases_filtered}"
JOBS="${JOBS:-16}"

# By default the script does NOT touch iptables: :8000 is opened permanently at
# the OS level (persisted in /etc/iptables/rules.v4), so the script must not
# close it on --stop. Pass --firewall to have the script open/close the port
# itself (e.g. when using a non-default port).
FOREGROUND=0; STOP=0; DO_FIREWALL=0
for arg in "$@"; do
  case "$arg" in
    --foreground|-f) FOREGROUND=1 ;;
    --stop)          STOP=1 ;;
    --firewall)      DO_FIREWALL=1 ;;
    --no-firewall)   DO_FIREWALL=0 ;;
    -h|--help)       sed -n '2,24p' "$0"; exit 0 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

# --- iptables helpers -------------------------------------------------------
# INPUT ends in REJECT, so each served port needs an explicit ACCEPT inserted
# ABOVE that reject. -I INPUT 1 puts it at the top. Idempotent via -C check.
fw_open() {
  local port="$1"
  [[ "$DO_FIREWALL" == "1" ]] || return 0
  command -v iptables >/dev/null 2>&1 || { echo "  (no iptables; skip open :$port)"; return 0; }
  if sudo -n iptables -C INPUT -s "$ALLOW_CIDR" -p tcp --dport "$port" -j ACCEPT 2>/dev/null; then
    echo "  firewall: :$port already open for $ALLOW_CIDR"
  elif sudo -n iptables -I INPUT 1 -s "$ALLOW_CIDR" -p tcp --dport "$port" -j ACCEPT 2>/dev/null; then
    echo "  firewall: opened :$port for $ALLOW_CIDR"
  else
    echo "  WARNING: could not open :$port in iptables (need sudo). External access will fail." >&2
  fi
}
fw_close() {
  local port="$1"
  [[ "$DO_FIREWALL" == "1" ]] || return 0
  command -v iptables >/dev/null 2>&1 || return 0
  # Delete every matching rule (there should be at most one).
  while sudo -n iptables -C INPUT -s "$ALLOW_CIDR" -p tcp --dport "$port" -j ACCEPT 2>/dev/null; do
    sudo -n iptables -D INPUT -s "$ALLOW_CIDR" -p tcp --dport "$port" -j ACCEPT 2>/dev/null || break
    echo "  firewall: closed :$port for $ALLOW_CIDR"
  done
}

# --- stop mode --------------------------------------------------------------
if [[ "$STOP" == "1" ]]; then
  if command -v tmux >/dev/null 2>&1 && tmux has-session -t "$SESSION" 2>/dev/null; then
    tmux kill-session -t "$SESSION" && echo "stopped tmux session '$SESSION'"
  else
    pid="$(ss -ltnp 2>/dev/null | grep ":$PORT " | grep -oP 'pid=\K[0-9]+' | head -1 || true)"
    [[ -n "$pid" ]] && kill "$pid" && echo "killed pid $pid on :$PORT"
  fi
  fw_close "$PORT"
  exit 0
fi

# --- pick a python interpreter that has the package + its deps --------------
pick_python() {
  for cand in \
      "$REPO_ROOT/.venv/bin/python3" \
      "/tmp/AIGameDevBench/.venv/bin/python3" \
      "python3" "python"; do
    command -v "$cand" >/dev/null 2>&1 || [[ -x "$cand" ]] || continue
    PYBIN="$cand"; return 0
  done
  echo "ERROR: no python3 found" >&2; exit 1
}
pick_python
export PYTHONPATH="$REPO_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
if ! "$PYBIN" -c "import aigamedevbench, godot_parser" >/dev/null 2>&1; then
  echo "ERROR: '$PYBIN' cannot import aigamedevbench + godot_parser." >&2
  echo "       Install deps first, e.g.:  $PYBIN -m pip install -e '.[dev]'" >&2
  exit 1
fi

# --- assemble the dashboard command -----------------------------------------
ARGS=(-m aigamedevbench.cli serve
      --host "$HOST" --port "$PORT"
      --reports-dir "$REPORTS_DIR" --testcases-dir "$TESTCASES_DIR"
      --webhook-log "$WEBHOOK_LOG"
      --runner-image "$RUNNER_IMAGE" --k8s-namespace "$K8S_NAMESPACE"
      --harness-secret "$HARNESS_SECRET" --image-testcases-dir "$IMAGE_TESTCASES_DIR"
      --jobs "$JOBS"
      --no-open-browser)
[[ "$ALLOW_RUN" == "1" ]] && ARGS+=(--allow-run) || ARGS+=(--no-allow-run)
mkdir -p "$REPORTS_DIR" "$(dirname "$WEBHOOK_LOG")"
touch "$WEBHOOK_LOG"

if ss -ltn 2>/dev/null | grep -q ":$PORT "; then
  echo "ERROR: port $PORT is already in use. Stop it first: $0 --stop" >&2
  exit 1
fi

lan_ip="$(hostname -I 2>/dev/null | awk '{print $1}')"
url_host="${lan_ip:-<this-node-ip>}"
banner() {
  echo "--- AIGameDevBench dashboard"
  echo "    local:    http://127.0.0.1:$PORT/"
  [[ "$HOST" == "0.0.0.0" || "$HOST" == "::" ]] && \
    echo "    network:  http://$url_host:$PORT/"
  echo "    tabs:     Reports · Testcases · Contents · Run · Webhooks"
  echo "    webhooks: $WEBHOOK_LOG"
  echo "    reports:  $REPORTS_DIR"
  if [[ "$ALLOW_RUN" == "1" ]]; then
    echo "    run tab:  docker+k8s matrix (image=$RUNNER_IMAGE ns=$K8S_NAMESPACE secret=$HARNESS_SECRET)"
  else
    echo "    run tab:  disabled"
  fi
  if [[ "$DO_FIREWALL" == "1" ]]; then
    echo "    firewall: script-managed, opened for $ALLOW_CIDR (closed on --stop)"
  else
    echo "    firewall: not managed by script; :$PORT is permanently open (rules.v4)"
  fi
}

# --- foreground -------------------------------------------------------------
if [[ "$FOREGROUND" == "1" ]]; then
  fw_open "$PORT"
  banner
  echo "    (foreground; Ctrl-C to stop. Port stays open; run '$0 --stop' to close it.)"
  exec "$PYBIN" "${ARGS[@]}"
fi

# --- background via tmux (preferred) ----------------------------------------
if command -v tmux >/dev/null 2>&1; then
  tmux has-session -t "$SESSION" 2>/dev/null && {
    echo "ERROR: tmux session '$SESSION' already exists. Stop it: $0 --stop" >&2
    exit 1; }
  dash_cmd="cd $(printf %q "$REPO_ROOT") && PYTHONPATH=$(printf %q "$PYTHONPATH") $(printf %q "$PYBIN")"
  for a in "${ARGS[@]}"; do dash_cmd+=" $(printf %q "$a")"; done
  tmux new-session -d -s "$SESSION" -n dashboard "$dash_cmd"
  fw_open "$PORT"
  sleep 1
  banner
  echo "    tmux:     attach with 'tmux attach -t $SESSION' ; stop with '$0 --stop'"
  exit 0
fi

# --- background without tmux (nohup fallback) -------------------------------
LOG="$REPO_ROOT/dashboard.log"
nohup setsid "$PYBIN" "${ARGS[@]}" >"$LOG" 2>&1 < /dev/null &
fw_open "$PORT"
sleep 1
banner
echo "    log:      $LOG (no tmux; stop with '$0 --stop')"
