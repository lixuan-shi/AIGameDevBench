#!/usr/bin/env python3
"""Standalone webhook receiver for the AIGameDevBench dashboard.

Listens for the k8s github-webhook receiver's forwarded deliveries
(POST /trigger) and appends each one to a JSONL log that the dashboard's
Webhooks tab reads. This is the "record only" half of bench-orchestrator.sh's
http mode -- it does NOT launch any benchmark; it just captures what arrived so
the dashboard shows it.

Why this exists: the k8s receiver forwards to BENCH_TRIGGER_URL
(e.g. http://<this-host>:8899/trigger). If nothing listens there, the receiver
logs "benchmark trigger forward failed: fetch failed" and the delivery is lost.
Running this keeps the port alive and captures every delivery.

Usage:
    python3 scripts/webhook_receiver.py --port 8899 \
        --log .orchestrator/webhooks.jsonl [--token <shared-secret>]

Pure stdlib. The record format matches bench-orchestrator.sh exactly, so the
dashboard renders receiver-captured and orchestrator-captured deliveries the
same way.
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def make_handler(log_path: Path, token: str, autorun_url: str = "",
                 autorun_jobs: int = 16, autorun_timeout: int = 1200):
    def record(rec: dict) -> None:
        rec.setdefault("time", time.time())
        rec.setdefault("source", "receiver")
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except OSError as e:
            sys.stderr.write(f"[receiver] could not write log: {e}\n")

    def kick_benchmark(delivery: str, pr_number: str, head_sha: str,
                       repo: str) -> None:
        """Fire-and-forget POST to the dashboard's /api/runs/start so an opened
        PR launches the real docker/k8s matrix over all filtered testcases. The
        dashboard runs one at a time, so a 409 (busy) is expected and ignored."""
        if not autorun_url:
            return
        sha8 = (head_sha or "")[:8]
        name = f"pr-{pr_number or '?'}-{sha8 or delivery[:8]}"
        payload = json.dumps({
            "name": name,
            "testcases": "",          # blank = all filtered testcases
            "jobs": autorun_jobs,
            "timeout": autorun_timeout,
        }).encode()

        def _post():
            try:
                req = urllib.request.Request(
                    autorun_url, data=payload, method="POST",
                    headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=15) as r:
                    body = r.read().decode("utf-8", "replace")
                    sys.stderr.write(
                        f"[receiver] auto-run kicked ({name}): {r.status} {body}\n")
            except urllib.error.HTTPError as e:
                # 409 = a run is already in progress; that's fine.
                msg = e.read().decode("utf-8", "replace") if e.fp else ""
                sys.stderr.write(
                    f"[receiver] auto-run {name}: HTTP {e.code} {msg}\n")
            except Exception as e:  # noqa: BLE001 - never let this kill the handler
                sys.stderr.write(f"[receiver] auto-run {name} failed: {e}\n")

        threading.Thread(target=_post, daemon=True).start()

    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, obj: dict) -> None:
            body = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):  # keep console quiet
            pass

        def do_GET(self):  # noqa: N802
            if self.path == "/healthz":
                self._send(200, {"ok": True})
            else:
                self._send(404, {"error": "not found"})

        def do_POST(self):  # noqa: N802
            if self.path != "/trigger":
                self._send(404, {"error": "not found"})
                return
            if token and self.headers.get("x-bench-token", "") != token:
                self._send(401, {"error": "bad token"})
                return
            n = int(self.headers.get("Content-Length", "0") or "0")
            raw = self.rfile.read(n) if n > 0 else b"{}"
            client = self.client_address[0]
            try:
                o = json.loads(raw or b"{}")
            except Exception:
                record({"decision": "error", "error": "bad json", "client": client,
                        "event": "?", "body": (raw or b"").decode("utf-8", "replace")})
                self._send(400, {"error": "bad json"})
                return
            if not isinstance(o, dict):
                record({"decision": "error", "error": "body not an object",
                        "client": client, "event": "?", "body": o})
                self._send(400, {"error": "body not an object"})
                return

            delivery = str(o.get("delivery") or "").strip()
            if not delivery:
                record({"decision": "error", "error": "missing delivery",
                        "client": client, "event": str(o.get("event") or "?"),
                        "body": o})
                self._send(400, {"error": "missing delivery"})
                return

            # Mirror bench-orchestrator.sh's event classification exactly.
            event = str(o.get("event") or "").strip().lower()
            pr = o.get("pull_request") or {}
            pr_number = str(o.get("pr_number") or o.get("pr")
                            or pr.get("number") or "").strip()
            head_sha = str(o.get("head_sha")
                           or (pr.get("head") or {}).get("sha") or "").strip()
            base_ref = str(o.get("base_ref")
                           or (pr.get("base") or {}).get("ref") or "main").strip()
            action = str(o.get("action") or "").strip().lower()
            is_pr = event in ("pull_request", "pr") or bool(pr_number and head_sha)
            base = {"delivery": delivery, "client": client,
                    "event": event or ("pull_request" if is_pr else "?"),
                    "action": action, "repo": str(o.get("repo")
                                                   or o.get("repository") or ""),
                    "pr_number": pr_number, "head_sha": head_sha,
                    "base_ref": base_ref, "body": o}

            if is_pr:
                if action and action != "opened":
                    record({**base, "decision": "skipped", "skipped_reason": action})
                    self._send(202, {"accepted": False, "skipped": action})
                    return
                if not (pr_number and head_sha):
                    record({**base, "decision": "error",
                            "error": "missing pr_number/head_sha"})
                    self._send(400,
                               {"error": "pull_request missing pr_number/head_sha"})
                    return
                record({**base, "decision": "accepted"})
                note = "recorded (no auto-run)"
                if autorun_url:
                    kick_benchmark(delivery, pr_number, head_sha, base["repo"])
                    note = "recorded; benchmark auto-run kicked"
                self._send(202, {"accepted": True, "event": "pull_request",
                                 "pr": pr_number, "note": note})
                return

            record({**base, "decision": "skipped",
                    "skipped_reason": event or "non-pull_request"})
            self._send(202, {"accepted": False,
                             "skipped": event or "non-pull_request"})

    return Handler


def main() -> None:
    ap = argparse.ArgumentParser(description="AIGameDevBench webhook receiver")
    ap.add_argument("--port", type=int, default=8899)
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--log", required=True,
                    help="JSONL log to append received deliveries to "
                         "(the dashboard reads this via --webhook-log)")
    ap.add_argument("--token", default="",
                    help="Shared x-bench-token to require (empty = no auth)")
    ap.add_argument("--autorun-url", default="",
                    help="If set, POST here (the dashboard's /api/runs/start) to "
                         "auto-launch a benchmark on each accepted opened PR. "
                         "Empty = record only.")
    ap.add_argument("--autorun-jobs", type=int, default=16,
                    help="jobs (max concurrent k8s Jobs) for auto-run")
    ap.add_argument("--autorun-timeout", type=int, default=1200,
                    help="per-testcase timeout (s) for auto-run")
    args = ap.parse_args()

    log_path = Path(args.log)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.touch(exist_ok=True)

    server = ThreadingHTTPServer(
        (args.host, args.port),
        make_handler(log_path, args.token, autorun_url=args.autorun_url,
                     autorun_jobs=args.autorun_jobs,
                     autorun_timeout=args.autorun_timeout))
    print(f"[receiver] listening on http://{args.host}:{args.port}/trigger "
          f"-> {log_path}"
          + ("  (token required)" if args.token else "  (no auth)")
          + (f"  (auto-run -> {args.autorun_url})" if args.autorun_url
             else "  (record only)"), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
