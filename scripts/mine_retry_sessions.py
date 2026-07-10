#!/usr/bin/env python
"""Mine local Claude conversation history for game-dev sessions with repeated
error/retry loops — the highest-signal source of real testcases.

Scans ~/.claude/projects/<project>/*.jsonl, excluding the benchmark's own
throwaway workspaces (aigdbench-ws-*), and scores each session by four retry
signals:

  1. tool_error          tool_result blocks with is_error=true (cmd exit!=0,
                         compile errors, missing files, ...)
  2. file_thrash         the same file Edited/Written >= 3 times (churned)
  3. user_correction     user turns containing correction language
                         (不对 / 还是错 / 报错 / 重新 / wrong / still ... / no, )
  4. godot_crash         Godot-specific failure text (Parse Error / SCRIPT ERROR
                         / Could not find type / Failed to load)

A session's retry_score is a weighted sum. The script prints a ranked table and
writes a JSON scenario list (per session: project, first user task, signal
counts, the thrashed files, and short excerpts of the first few errors) for
manual review and re-creation as folder-type testcases.

Usage:
  python scripts/mine_retry_sessions.py [--projects-dir DIR] [--min-score N]
      [--json out.json] [--top N]
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

# Benchmark workspaces are synthetic (Claude solving bench tasks), not real
# game-dev sessions — exclude them.
EXCLUDE_SUBSTR = "aigdbench-ws-"

CORRECTION_RE = re.compile(
    r"(不对|还是错|还是不|报错了?|又错|重新|改回|不行|没生效|没有生效|崩了|闪退|"
    r"\bwrong\b|\bstill (?:not|fail|error|broken)|\bdoesn'?t work|\bnot working|"
    r"\btry again\b|^no[,，]|\bthat'?s not)",
    re.IGNORECASE)

GODOT_CRASH_RE = re.compile(
    r"(Parse Error|SCRIPT ERROR|Could not find type|Failed to load|"
    r"Invalid (?:call|get|set|access)|Cannot infer|nonexistent function|"
    r"Identifier \".*?\" not declared)")

WEIGHTS = {"tool_error": 3, "file_thrash": 2, "user_correction": 2, "godot_crash": 4}


def _text_of(content) -> str:
    """Flatten a message 'content' (str or list of blocks) to plain text."""
    if isinstance(content, str):
        return content
    out = []
    if isinstance(content, list):
        for b in content:
            if isinstance(b, dict):
                if b.get("type") == "text" and isinstance(b.get("text"), str):
                    out.append(b["text"])
                elif b.get("type") == "tool_result":
                    c = b.get("content")
                    out.append(c if isinstance(c, str) else json.dumps(c, ensure_ascii=False))
    return "\n".join(out)


def analyze_session(path: Path) -> dict | None:
    tool_errors: list[str] = []
    edits = Counter()           # file path -> edit/write count
    corrections = 0
    godot_hits = 0
    first_user_task = ""
    n_lines = 0

    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        n_lines += 1
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            continue
        typ = o.get("type")
        msg = o.get("message") if isinstance(o.get("message"), dict) else {}
        content = msg.get("content")

        # tool errors + godot crash text live in tool_result blocks
        if isinstance(content, list):
            for b in content:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "tool_result" and b.get("is_error"):
                    txt = _text_of([b])
                    tool_errors.append(txt[:300])
                    if GODOT_CRASH_RE.search(txt):
                        godot_hits += 1
                if b.get("type") == "tool_use":
                    name = b.get("name", "")
                    if name in ("Edit", "Write", "NotebookEdit"):
                        fp = (b.get("input") or {}).get("file_path")
                        if fp:
                            edits[fp] += 1

        if typ == "user":
            txt = _text_of(content)
            # skip tool_result-only user turns (they're not human typing)
            if txt and not (isinstance(content, list) and all(
                    isinstance(b, dict) and b.get("type") == "tool_result" for b in content)):
                if not first_user_task:
                    first_user_task = txt.strip()[:500]
                if CORRECTION_RE.search(txt):
                    corrections += 1
        # godot crash text can also appear in assistant text / other places
        if typ == "assistant":
            if GODOT_CRASH_RE.search(_text_of(content)):
                godot_hits += 1

    thrashed = {f: c for f, c in edits.items() if c >= 3}
    signals = {
        "tool_error": len(tool_errors),
        "file_thrash": sum(thrashed.values()),
        "user_correction": corrections,
        "godot_crash": godot_hits,
    }
    score = sum(WEIGHTS[k] * v for k, v in signals.items())
    if score == 0:
        return None
    return {
        "session": path.stem,
        "project": path.parent.name,
        "lines": n_lines,
        "retry_score": score,
        "signals": signals,
        "thrashed_files": thrashed,
        "first_user_task": first_user_task,
        "error_excerpts": tool_errors[:5],
    }


# --- Codex rollout format (~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl) ---

_CODEX_CWD_RE = re.compile(r"<cwd>(.*?)</cwd>")
_CODEX_EXIT_RE = re.compile(r"^Exit code:\s*([0-9]+)")
_CODEX_APPLY_PATCH_RE = re.compile(r'\*\*\* (?:Update|Add) File:\s*(.+)')


def _codex_text(content) -> str:
    """Codex message content is a list of {type:input_text|output_text, text}."""
    if isinstance(content, str):
        return content
    out = []
    if isinstance(content, list):
        for b in content:
            if isinstance(b, dict) and isinstance(b.get("text"), str):
                out.append(b["text"])
    return "\n".join(out)


def analyze_codex_session(path: Path) -> dict | None:
    """Score a Codex rollout session with the same four retry signals.

    Codex schema: each line is a response item. Messages are
    {type:message, role, content:[{type:input_text|output_text, text}]}.
    Tool calls are {type:function_call, name, arguments} and their results are
    {type:function_call_output, output:"Exit code: N\\n..."}. File churn is
    counted from apply_patch payloads ('*** Update File: <path>')."""
    tool_errors: list[str] = []
    edits = Counter()
    corrections = 0
    godot_hits = 0
    first_user_task = ""
    cwd = ""
    n_lines = 0

    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        n_lines += 1
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            continue
        # rollout items may be wrapped: {type, payload} or flat
        item = o.get("payload") if isinstance(o.get("payload"), dict) else o
        typ = item.get("type")

        if typ == "message":
            role = item.get("role")
            txt = _codex_text(item.get("content"))
            if role == "user":
                m = _CODEX_CWD_RE.search(txt)
                if m and not cwd:
                    cwd = m.group(1).strip()
                # real human turns: not the injected environment/permissions context
                if txt and "<environment_context>" not in txt and "<permissions" not in txt:
                    if not first_user_task:
                        first_user_task = txt.strip()[:500]
                    if CORRECTION_RE.search(txt):
                        corrections += 1
            elif role == "assistant":
                if GODOT_CRASH_RE.search(txt):
                    godot_hits += 1

        elif typ == "function_call":
            args = item.get("arguments")
            if isinstance(args, str):
                for fp in _CODEX_APPLY_PATCH_RE.findall(args):
                    edits[fp.strip()] += 1

        elif typ == "function_call_output":
            out = item.get("output")
            out = out if isinstance(out, str) else json.dumps(out, ensure_ascii=False)
            m = _CODEX_EXIT_RE.match(out.strip())
            if m and m.group(1) != "0":
                tool_errors.append(out[:300])
                if GODOT_CRASH_RE.search(out):
                    godot_hits += 1

    thrashed = {f: c for f, c in edits.items() if c >= 3}
    signals = {
        "tool_error": len(tool_errors),
        "file_thrash": sum(thrashed.values()),
        "user_correction": corrections,
        "godot_crash": godot_hits,
    }
    score = sum(WEIGHTS[k] * v for k, v in signals.items())
    if score == 0:
        return None
    return {
        "session": path.stem,
        "project": cwd or path.parent.name,
        "lines": n_lines,
        "retry_score": score,
        "signals": signals,
        "thrashed_files": thrashed,
        "first_user_task": first_user_task,
        "error_excerpts": tool_errors[:5],
    }


def inspect_session(path: Path, out: Path | None) -> int:
    """Dump a single session's task + ordered error/edit/correction timeline for
    manual review (so a retry scenario can be re-created as a testcase)."""
    timeline = []
    first_task = ""
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            continue
        typ = o.get("type")
        msg = o.get("message") if isinstance(o.get("message"), dict) else {}
        content = msg.get("content")
        if isinstance(content, list):
            for b in content:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "tool_result" and b.get("is_error"):
                    timeline.append({"kind": "ERROR", "text": _text_of([b])[:400]})
                if b.get("type") == "tool_use" and b.get("name") in ("Edit", "Write"):
                    fp = (b.get("input") or {}).get("file_path", "")
                    timeline.append({"kind": "EDIT", "text": Path(fp).name if fp else "?"})
        if typ == "user":
            txt = _text_of(content)
            is_tool_only = isinstance(content, list) and all(
                isinstance(b, dict) and b.get("type") == "tool_result" for b in content)
            if txt and not is_tool_only:
                if not first_task:
                    first_task = txt.strip()
                if CORRECTION_RE.search(txt):
                    timeline.append({"kind": "USER_FIX", "text": txt.strip()[:300]})

    payload = {"session": path.stem, "project": path.parent.name,
               "first_task": first_task, "timeline": timeline}
    if out:
        out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"wrote {out} ({len(timeline)} timeline events)")
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    default_projects = Path.home() / ".claude" / "projects"
    ap.add_argument("--projects-dir", type=Path, default=default_projects)
    ap.add_argument("--min-score", type=int, default=6)
    ap.add_argument("--top", type=int, default=30)
    ap.add_argument("--json", type=Path, default=None)
    ap.add_argument("--inspect", type=Path, default=None,
                    help="dump one session's timeline (path to its .jsonl)")
    ap.add_argument("--codex", action="store_true",
                    help="mine Codex rollout sessions (~/.codex/sessions/**/*.jsonl) "
                         "instead of Claude projects")
    ap.add_argument("--codex-dir", type=Path,
                    default=Path.home() / ".codex" / "sessions",
                    help="Codex sessions root (used with --codex)")
    args = ap.parse_args()

    if args.inspect:
        return inspect_session(args.inspect, args.json)

    results = []
    if args.codex:
        for sess in sorted(args.codex_dir.rglob("rollout-*.jsonl")):
            row = analyze_codex_session(sess)
            if row and row["retry_score"] >= args.min_score:
                results.append(row)
    else:
        for proj in sorted(args.projects_dir.iterdir()):
            if not proj.is_dir() or EXCLUDE_SUBSTR in proj.name:
                continue
            for sess in proj.glob("*.jsonl"):
                row = analyze_session(sess)
                if row and row["retry_score"] >= args.min_score:
                    results.append(row)

    results.sort(key=lambda r: r["retry_score"], reverse=True)

    print(f"\n{'score':>5} {'lines':>6} {'te':>3} {'ft':>3} {'uc':>3} {'gc':>3}  project / session")
    print("-" * 90)
    for r in results[:args.top]:
        s = r["signals"]
        proj = r["project"]
        proj = proj[-34:] if len(proj) > 34 else proj
        print(f"{r['retry_score']:>5} {r['lines']:>6} {s['tool_error']:>3} "
              f"{s['file_thrash']:>3} {s['user_correction']:>3} {s['godot_crash']:>3}  "
              f"{proj}/{r['session'][:10]}")
    print("-" * 90)
    print(f"{len(results)} sessions with retry_score >= {args.min_score}")
    print("legend: te=tool_error ft=file_thrash uc=user_correction gc=godot_crash")

    if args.json:
        args.json.write_text(json.dumps({
            "schema": "aigdbench/retry-mine/1",
            "weights": WEIGHTS,
            "count": len(results),
            "sessions": results,
        }, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nwrote {args.json}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
