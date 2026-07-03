from __future__ import annotations

import json
from pathlib import Path, PureWindowsPath
from typing import Iterable

from aigamedevbench.driver import NoOpDriver, PatchDriver
from aigamedevbench.runner import run_testcase
from aigamedevbench.testcase import Testcase, discover_testcases

LEAK_TOL = 1e-9
PATCH_TARGET = 1.0
OVERBROAD_ORACLE = 20


def config_for(godot_binary: str) -> dict:
    return {"global": {"godot": {"binary": godot_binary}}}


def _safe_run(repo_root: Path | None, tc: Testcase, driver, harness: str,
              cfg: dict) -> tuple[float | None, str, str | None]:
    try:
        res = run_testcase(repo_root, tc, driver, harness, cfg)
        err = res.verifier_result.error if res.verifier_result else None
        status = res.verifier_result.status if res.verifier_result else "?"
        return res.score, status, err
    except Exception as e:
        return None, "exception", f"{type(e).__name__}: {e}"


def _oracle_breadth(tc: Testcase) -> int | None:
    if tc.verifier_type != "survey_bad_case":
        return None
    spec = tc.dir / tc.verifier_entry
    if not spec.exists():
        return None
    try:
        data = json.loads(spec.read_text(encoding="utf-8"))
        return len(data.get("expected", {}).get("must_change_one_of", []))
    except Exception:
        return None


def _is_abs_or_drive_path(path_text: str) -> bool:
    if not path_text:
        return False
    return Path(path_text).is_absolute() or bool(PureWindowsPath(path_text).drive)


def audit_one(tc: Testcase, repo_root: Path | None, godot_binary: str,
              patch_path: Path | None = None) -> dict:
    cfg = config_for(godot_binary)
    row: dict = {
        "id": tc.id,
        "category": tc.category,
        "verifier": tc.verifier_type,
        "source_kind": tc.source_kind,
        "source_repo": tc.source_repo,
        "flags": [],
    }

    if tc.source_kind == "git":
        repo = Path(tc.source_repo) if tc.source_repo else repo_root
        present = bool(repo and Path(repo).exists())
        row["repo_present"] = present
        if not present:
            row["flags"].append("repo_missing")
        if tc.source_repo and _is_abs_or_drive_path(str(tc.source_repo)):
            row["flags"].append("nonportable_abs_path")

    noop_score, noop_status, noop_err = _safe_run(
        repo_root, tc, NoOpDriver(), "audit-noop", cfg)
    row["noop_score"] = noop_score
    row["noop_status"] = noop_status
    if noop_err:
        row["noop_error"] = noop_err

    is_survey = tc.verifier_type == "survey_bad_case"
    if is_survey:
        breadth = _oracle_breadth(tc)
        row["oracle_breadth"] = breadth
        if breadth is not None and breadth > OVERBROAD_ORACLE:
            row["flags"].append(f"overbroad_oracle({breadth})")
        if noop_score is not None and noop_score > LEAK_TOL:
            row["flags"].append(f"noop_not_zero({noop_score:.2f})")
        row["patch_score"] = None
    else:
        if noop_score is None:
            row["flags"].append("noop_run_failed")
        elif noop_score > LEAK_TOL:
            row["flags"].append(f"leaky_baseline(noop={noop_score:.2f})")

        fix = patch_path or (tc.dir / "fix.diff")
        row["patch_path"] = str(fix)
        if not fix.exists():
            row["flags"].append("no_fix_diff")
            row["patch_score"] = None
        else:
            patch_score, patch_status, patch_err = _safe_run(
                repo_root, tc,
                PatchDriver(fix.read_text(encoding="utf-8", errors="replace")),
                "audit-patch", cfg)
            row["patch_score"] = patch_score
            row["patch_status"] = patch_status
            if patch_err:
                row["patch_error"] = patch_err
            if patch_score is None or abs(patch_score - PATCH_TARGET) > 1e-6:
                row["flags"].append(f"patch_not_one(patch={patch_score})")

    row["healthy"] = len(row["flags"]) == 0
    return row


def select_testcases(testcases_dir: Path, only: Iterable[str] | None = None) -> list[Testcase]:
    cases = discover_testcases(testcases_dir)
    if only:
        wanted = set(only)
        cases = [c for c in cases if c.id in wanted]
    return cases


def audit_testcases(testcases: Iterable[Testcase], repo_root: Path | None,
                    godot_binary: str) -> list[dict]:
    return [audit_one(tc, repo_root, godot_binary) for tc in testcases]


def health_payload(rows: list[dict]) -> dict:
    healthy = sum(1 for row in rows if row["healthy"])
    return {
        "schema": "aigdbench/health/1",
        "total": len(rows),
        "healthy": healthy,
        "testcases": rows,
    }


def format_audit_table(rows: list[dict]) -> str:
    lines = [
        f"{'testcase':<48} {'noop':>6} {'patch':>6}  flags",
        "-" * 100,
    ]
    for row in rows:
        noop = "-" if row.get("noop_score") is None else f"{row['noop_score']:.2f}"
        patch = "-" if row.get("patch_score") is None else f"{row['patch_score']:.2f}"
        flags = ", ".join(row["flags"]) if row["flags"] else "OK"
        lines.append(f"{row['id']:<48} {noop:>6} {patch:>6}  {flags}")
    healthy = sum(1 for row in rows if row["healthy"])
    lines.extend(["-" * 100, f"{healthy}/{len(rows)} healthy"])
    return "\n".join(lines)


def write_health_json(path: Path, rows: list[dict]) -> None:
    path.write_text(json.dumps(health_payload(rows), indent=2, ensure_ascii=False),
                    encoding="utf-8")
