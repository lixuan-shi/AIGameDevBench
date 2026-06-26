from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aigamedevbench.result import CheckResult, VerifierResult
from aigamedevbench.testcase import Testcase
from aigamedevbench.validation import run_validation
from aigamedevbench.verifiers.base import register


@register("survey_bad_case")
class SurveyBadCaseVerifier:
    """Verifier for testcases exported from AIGameDevCollecter Survey.

    These cases are regression harnesses for real bad sessions. They score a new
    harness output by requiring it to avoid the original Survey failure signals
    and to make a relevant edit.
    """

    def verify(self, testcase: Testcase, workspace: Path,
               godot_binary: str = "godot") -> VerifierResult:
        spec_path = testcase.dir / testcase.verifier_entry
        if not spec_path.exists():
            return VerifierResult.error_result(testcase.category, f"missing {testcase.verifier_entry}")
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        expected = spec.get("expected", {})
        bench_record = spec.get("bench_record", {})
        session = bench_record.get("survey_session", {})
        changed_files = _changed_files(workspace)
        current_diff = _current_diff(workspace)

        checks: list[CheckResult] = []
        checks.append(_made_relevant_change(expected, current_diff))
        checks.append(_does_not_reproduce_bad_diff(testcase, current_diff))

        validation = run_validation(workspace, changed_files, {"global": {"godot": {"binary": godot_binary}}})
        if expected.get("original_l0_pass") is False:
            checks.append(CheckResult(
                "regression_l0_passes",
                validation.l0_pass,
                detail="; ".join(validation.l0_details),
                expected="pass",
                actual="pass" if validation.l0_pass else "fail",
            ))
        if expected.get("original_l1_pass") is False:
            checks.append(CheckResult(
                "regression_l1_passes",
                validation.l1_pass,
                detail="; ".join(validation.l1_details),
                expected="pass",
                actual="pass" if validation.l1_pass else "fail",
            ))

        # Human-intervention and round-count bad cases are not directly
        # reproducible inside a one-shot Bench run. The exported transcript still
        # makes the original context visible, so the runnable part asserts that
        # the harness makes a relevant change and passes L0/L1 gates.
        human_ratio = expected.get("original_human_intervention_ratio")
        if isinstance(human_ratio, (int, float)) and human_ratio > 0.4:
            checks.append(CheckResult(
                "original_human_intervention_context_available",
                _has_agent_context(bench_record),
                detail="Survey bad case was triggered by human follow-up volume; "
                       "the transcript context must be present for review.",
                expected="ai_agent_context.turns",
                actual=len(bench_record.get("ai_agent_context", {}).get("turns", [])),
            ))

        rounds = expected.get("original_rounds_to_resolution")
        if isinstance(rounds, int) and rounds > 4:
            checks.append(CheckResult(
                "original_multi_round_context_available",
                _has_agent_context(bench_record),
                detail="Survey bad case was triggered by many resolution rounds; "
                       "the transcript context must be present for review.",
                expected="ai_agent_context.turns",
                actual=len(bench_record.get("ai_agent_context", {}).get("turns", [])),
            ))

        if not any(c.name.startswith("regression_l") for c in checks):
            checks.append(CheckResult(
                "l0_l1_gate_passes",
                validation.l0_pass and validation.l1_pass,
                detail="; ".join([*validation.l0_details, *validation.l1_details]),
                expected="pass",
                actual="pass" if validation.l0_pass and validation.l1_pass else "fail",
            ))

        notes = session.get("notes") or expected.get("notes") or ""
        if notes:
            checks.append(CheckResult(
                "survey_bad_case_documented",
                True,
                detail=str(notes),
                expected=session.get("bad_case_type") or expected.get("bad_case_type"),
                actual=session.get("bad_case_type") or expected.get("bad_case_type"),
            ))

        hard_failures = {
            "changed_relevant_file",
            "changed_file",
            "does_not_reproduce_original_bad_diff",
            "original_human_intervention_context_available",
            "original_multi_round_context_available",
        }
        if any(c.name in hard_failures and not c.passed for c in checks):
            return VerifierResult(score=0.0, status="fail", checks=checks, category=testcase.category)
        return VerifierResult.from_checks(checks, testcase.category, testcase.scoring_mode)


def _changed_files(workspace: Path) -> list[str]:
    from aigamedevbench.git_ops import git_run

    try:
        out = git_run(["status", "--porcelain"], cwd=workspace)
    except Exception:
        return []
    files = []
    for line in out.splitlines():
        if len(line) > 3:
            files.append(line[3:].strip().replace("\\", "/"))
    return files


def _made_relevant_change(expected: dict[str, Any], current_diff: str) -> CheckResult:
    minimum = int(expected.get("minimum_changed_files") or 1)
    relevant = {str(f).replace("\\", "/") for f in expected.get("must_change_one_of", []) if f}
    changed = set(_diff_changed_files(current_diff))
    if relevant:
        overlap = sorted(relevant & changed)
        return CheckResult(
            "changed_relevant_file",
            len(overlap) >= minimum,
            detail=", ".join(overlap) if overlap else "no originally relevant file changed",
            expected=sorted(relevant),
            actual=sorted(changed),
        )
    return CheckResult(
        "changed_file",
        len(changed) >= minimum,
        expected=f">= {minimum}",
        actual=len(changed),
    )


def _diff_changed_files(diff: str) -> list[str]:
    files: list[str] = []
    for line in diff.splitlines():
        if line.startswith("diff --git "):
            parts = line.split()
            if len(parts) >= 4:
                path = parts[3]
                if path.startswith("b/"):
                    path = path[2:]
                if path != "/dev/null":
                    files.append(path.replace("\\", "/"))
    return sorted(set(files))


def _does_not_reproduce_bad_diff(testcase: Testcase, current_diff: str) -> CheckResult:
    bad_diff_path = testcase.dir / "bad.diff"
    if not bad_diff_path.exists() or not bad_diff_path.read_text(encoding="utf-8", errors="replace").strip():
        return CheckResult(
            "does_not_reproduce_original_bad_diff",
            True,
            detail="no original bad diff was exported",
            expected="different from original bad diff",
            actual="no bad.diff",
        )
    current = _normalized_diff(current_diff)
    bad = _normalized_diff(bad_diff_path.read_text(encoding="utf-8", errors="replace"))
    same = bool(current and current == bad)
    return CheckResult(
        "does_not_reproduce_original_bad_diff",
        not same,
        detail="current diff matches the original Survey bad-case diff" if same else "",
        expected="different from original bad diff",
        actual="same as bad.diff" if same else "different",
    )


def _current_diff(workspace: Path) -> str:
    from aigamedevbench.git_ops import git_run

    try:
        git_run(["add", "-A", "-N"], cwd=workspace)
    except Exception:
        pass
    try:
        return git_run(["diff", "--binary"], cwd=workspace)
    except Exception:
        return ""


def _normalized_diff(text: str) -> str:
    lines = []
    for line in text.replace("\r\n", "\n").splitlines():
        if line.startswith("index "):
            continue
        lines.append(line.rstrip())
    return "\n".join(lines).strip()


def _has_agent_context(bench_record: dict[str, Any]) -> bool:
    turns = bench_record.get("ai_agent_context", {}).get("turns", [])
    return bool(turns)
