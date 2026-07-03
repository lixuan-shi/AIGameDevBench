from __future__ import annotations

import json
from pathlib import Path

from aigamedevbench.git_ops import git_run
from aigamedevbench.testcase import Testcase
from aigamedevbench.verifiers.survey_bad_case import SurveyBadCaseVerifier


def test_survey_bad_case_verifier_passes_relevant_fix(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "scripts").mkdir()
    (workspace / "scripts" / "enemy.gd").write_text("extends Node\n", encoding="utf-8")
    git_run(["init"], cwd=workspace)
    git_run(["config", "user.email", "bench@test.local"], cwd=workspace)
    git_run(["config", "user.name", "Bench"], cwd=workspace)
    git_run(["add", "-A"], cwd=workspace)
    git_run(["commit", "-m", "baseline"], cwd=workspace)
    (workspace / "scripts" / "enemy.gd").write_text("extends Node\n\nfunc fixed():\n\tpass\n", encoding="utf-8")

    tc_dir = tmp_path / "tc"
    tc_dir.mkdir()
    (tc_dir / "survey_bad_case.json").write_text(json.dumps({
        "expected": {
            "bad_case_type": "C1",
            "original_human_intervention_ratio": 1.0,
            "must_change_one_of": ["scripts/enemy.gd"],
            "minimum_changed_files": 1,
        },
        "bench_record": {
            "ai_agent_context": {
                "turns": [{"turn": 1, "agent_input": "fix enemy", "agent_output": "fixed"}],
            },
            "survey_session": {
                "bad_case_type": "C1",
                "notes": "human_intervention_ratio=1.00",
            },
        },
    }), encoding="utf-8")
    testcase = Testcase(
        id="survey-bad",
        category="precise_edit",
        baseline_ref="HEAD",
        task="fix",
        verifier_type="survey_bad_case",
        verifier_entry="survey_bad_case.json",
        scoring_mode="checkpoints",
        dir=tc_dir,
    )

    result = SurveyBadCaseVerifier().verify(testcase, workspace)

    assert result.status == "pass"
    assert {c.name for c in result.checks} >= {
        "changed_relevant_file",
        "original_human_intervention_context_available",
        "l0_l1_gate_passes",
    }


def test_survey_bad_case_verifier_fails_without_context_for_human_case(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "file.txt").write_text("base\n", encoding="utf-8")
    git_run(["init"], cwd=workspace)
    git_run(["config", "user.email", "bench@test.local"], cwd=workspace)
    git_run(["config", "user.name", "Bench"], cwd=workspace)
    git_run(["add", "-A"], cwd=workspace)
    git_run(["commit", "-m", "baseline"], cwd=workspace)
    (workspace / "file.txt").write_text("changed\n", encoding="utf-8")

    tc_dir = tmp_path / "tc"
    tc_dir.mkdir()
    (tc_dir / "survey_bad_case.json").write_text(json.dumps({
        "expected": {
            "bad_case_type": "C1",
            "original_human_intervention_ratio": 1.0,
            "must_change_one_of": ["file.txt"],
        },
        "bench_record": {
            "ai_agent_context": {"turns": []},
            "survey_session": {"bad_case_type": "C1"},
        },
    }), encoding="utf-8")
    testcase = Testcase(
        id="survey-bad",
        category="precise_edit",
        baseline_ref="HEAD",
        task="fix",
        verifier_type="survey_bad_case",
        verifier_entry="survey_bad_case.json",
        scoring_mode="checkpoints",
        dir=tc_dir,
    )

    result = SurveyBadCaseVerifier().verify(testcase, workspace)

    assert result.status == "fail"
    context_check = next(c for c in result.checks if c.name == "original_human_intervention_context_available")
    assert not context_check.passed


def test_survey_bad_case_verifier_fails_when_bad_diff_is_reproduced(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "file.txt").write_text("base\n", encoding="utf-8")
    git_run(["init"], cwd=workspace)
    git_run(["config", "user.email", "bench@test.local"], cwd=workspace)
    git_run(["config", "user.name", "Bench"], cwd=workspace)
    git_run(["add", "-A"], cwd=workspace)
    git_run(["commit", "-m", "baseline"], cwd=workspace)
    (workspace / "file.txt").write_text("bad\n", encoding="utf-8")
    bad_diff = git_run(["diff", "--binary"], cwd=workspace)

    tc_dir = tmp_path / "tc"
    tc_dir.mkdir()
    (tc_dir / "bad.diff").write_text(bad_diff, encoding="utf-8")
    (tc_dir / "survey_bad_case.json").write_text(json.dumps({
        "expected": {
            "bad_case_type": "B1",
            "must_change_one_of": ["file.txt"],
        },
        "bench_record": {
            "ai_agent_context": {
                "turns": [{"turn": 1, "agent_input": "fix", "agent_output": "bad"}],
            },
            "survey_session": {"bad_case_type": "B1"},
        },
    }), encoding="utf-8")
    testcase = Testcase(
        id="survey-bad",
        category="intent_translation",
        baseline_ref="HEAD",
        task="fix",
        verifier_type="survey_bad_case",
        verifier_entry="survey_bad_case.json",
        scoring_mode="checkpoints",
        dir=tc_dir,
    )

    result = SurveyBadCaseVerifier().verify(testcase, workspace)

    diff_check = next(c for c in result.checks if c.name == "does_not_reproduce_original_bad_diff")
    assert not diff_check.passed
    assert result.status == "fail"


def test_survey_bad_case_verifier_flags_weak_oracle_as_non_scoreable(tmp_path: Path):
    """A case with empty bad.diff, no runtime regression flags, and no process
    context has a non-discriminating oracle and must be reported as fail."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "scripts").mkdir()
    (workspace / "scripts" / "board.gd").write_text("extends Node\n", encoding="utf-8")
    git_run(["init"], cwd=workspace)
    git_run(["config", "user.email", "bench@test.local"], cwd=workspace)
    git_run(["config", "user.name", "Bench"], cwd=workspace)
    git_run(["add", "-A"], cwd=workspace)
    git_run(["commit", "-m", "baseline"], cwd=workspace)
    # A plausible-but-superficial edit to the relevant file.
    (workspace / "scripts" / "board.gd").write_text("extends Node\n\n# tweak\n", encoding="utf-8")

    tc_dir = tmp_path / "tc"
    tc_dir.mkdir()
    # No bad.diff written; l0/l1 pass flags null; no process signal.
    (tc_dir / "survey_bad_case.json").write_text(json.dumps({
        "expected": {
            "bad_case_type": "A1",
            "original_l0_pass": None,
            "original_l1_pass": None,
            "original_human_intervention_ratio": 0.0,
            "original_rounds_to_resolution": 2,
            "must_change_one_of": ["scripts/board.gd"],
            "minimum_changed_files": 1,
        },
        "bench_record": {
            "ai_agent_context": {"turns": []},
            "survey_session": {"bad_case_type": "A1", "notes": "weak"},
        },
    }), encoding="utf-8")
    testcase = Testcase(
        id="survey-weak",
        category="behavior_logic",
        baseline_ref="HEAD",
        task="fix",
        verifier_type="survey_bad_case",
        verifier_entry="survey_bad_case.json",
        scoring_mode="checkpoints",
        dir=tc_dir,
    )

    result = SurveyBadCaseVerifier().verify(testcase, workspace)

    oracle_check = next(c for c in result.checks if c.name == "oracle_is_discriminating")
    assert not oracle_check.passed
    assert result.status == "fail"
