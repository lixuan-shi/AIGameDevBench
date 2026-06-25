from __future__ import annotations

import json
from pathlib import Path

from aigamedevbench.webreport import load_reports, build_summary, report_detail


def _write_report(path: Path, harness: str, testcases: list[dict]) -> None:
    count = len(testcases)
    mean = sum(t["score"] for t in testcases) / count if count else 0.0
    path.write_text(
        json.dumps({
            "harness": harness,
            "count": count,
            "mean_score": mean,
            "testcases": testcases,
        }),
        encoding="utf-8",
    )


def _tc(tcid: str, score: float, category: str = "behavior_logic",
        checks: list[dict] | None = None, **extra) -> dict:
    vr = {
        "score": score,
        "status": "pass" if score >= 1.0 else ("fail" if score <= 0 else "partial"),
        "category": category,
        "error": "",
        "checks": checks or [],
    }
    rec = {
        "testcase_id": tcid,
        "harness": "h",
        "category": category,
        "l0_l1_pass": True,
        "score": score,
        "verifier_result": vr,
        "diff": "",
        "artifacts_path": None,
    }
    rec.update(extra)
    return rec


def test_load_reports_reads_each_json_and_injects_run_metadata(tmp_path):
    _write_report(tmp_path / "report_a.json", "alpha", [_tc("t1", 1.0)])
    _write_report(tmp_path / "report_b.json", "beta", [_tc("t1", 0.0)])

    reports = load_reports(tmp_path)

    assert len(reports) == 2
    by_file = {r["_file"]: r for r in reports}
    assert by_file["report_a.json"]["harness"] == "alpha"
    assert by_file["report_b.json"]["harness"] == "beta"
    for r in reports:
        assert isinstance(r["_mtime"], float)
        assert r["_run_id"]  # non-empty unique id


def test_load_reports_run_ids_are_unique_even_with_same_harness(tmp_path):
    _write_report(tmp_path / "r1.json", "claude", [_tc("t1", 1.0)])
    _write_report(tmp_path / "r2.json", "claude", [_tc("t1", 0.5)])

    run_ids = {r["_run_id"] for r in load_reports(tmp_path)}

    assert len(run_ids) == 2


def test_load_reports_skips_bad_and_non_report_json(tmp_path):
    _write_report(tmp_path / "good.json", "ok", [_tc("t1", 1.0)])
    (tmp_path / "broken.json").write_text("{not valid json", encoding="utf-8")
    (tmp_path / "other.json").write_text(json.dumps({"foo": "bar"}), encoding="utf-8")

    reports = load_reports(tmp_path)

    assert [r["_file"] for r in reports] == ["good.json"]


def test_build_summary_score_matrix_fills_none_for_missing_testcase(tmp_path):
    _write_report(tmp_path / "a.json", "alpha", [_tc("t1", 1.0), _tc("t2", 0.5)])
    _write_report(tmp_path / "b.json", "beta", [_tc("t1", 0.0)])

    summary = build_summary(load_reports(tmp_path))

    assert summary["testcases"] == ["t1", "t2"]
    a = next(r["_run_id"] for r in load_reports(tmp_path) if r["_file"] == "a.json")
    b = next(r["_run_id"] for r in load_reports(tmp_path) if r["_file"] == "b.json")
    matrix = summary["matrix"]
    assert matrix["t1"][a] == 1.0
    assert matrix["t1"][b] == 0.0
    assert matrix["t2"][a] == 0.5
    assert matrix["t2"][b] is None


def test_build_summary_run_meta_carries_mean_and_count(tmp_path):
    _write_report(tmp_path / "a.json", "alpha", [_tc("t1", 1.0), _tc("t2", 0.0)])

    summary = build_summary(load_reports(tmp_path))

    run = summary["runs"][0]
    assert run["harness"] == "alpha"
    assert run["count"] == 2
    assert run["mean_score"] == 0.5
    assert isinstance(run["mtime"], float)


def test_build_summary_category_aggregate(tmp_path):
    _write_report(tmp_path / "a.json", "alpha", [
        _tc("t1", 1.0, category="behavior_logic"),
        _tc("t2", 0.0, category="behavior_logic"),
        _tc("t3", 1.0, category="visual"),
    ])

    summary = build_summary(load_reports(tmp_path))
    run_id = summary["runs"][0]["run_id"]
    cats = summary["categories"][run_id]

    assert cats["behavior_logic"]["mean"] == 0.5
    assert cats["behavior_logic"]["pass_rate"] == 0.5
    assert cats["visual"]["mean"] == 1.0
    assert cats["visual"]["pass_rate"] == 1.0


def test_build_summary_timing_aggregate(tmp_path):
    _write_report(tmp_path / "a.json", "alpha", [
        _tc("t1", 1.0, wall_time=2.0, timed_out=False),
        _tc("t2", 0.0, wall_time=4.0, timed_out=True),
    ])

    summary = build_summary(load_reports(tmp_path))
    run_id = summary["runs"][0]["run_id"]
    timing = summary["timing"][run_id]

    assert timing["total_wall_time"] == 6.0
    assert timing["mean_wall_time"] == 3.0
    assert timing["timed_out"] == 1
    assert timing["stalled"] == 0
    assert timing["blocked_on_approval"] == 0


def test_report_detail_returns_checks_with_expected_actual(tmp_path):
    checks = [
        {"name": "c1", "passed": True, "detail": "ok", "expected": 1, "actual": 1},
        {"name": "c2", "passed": False, "detail": "bad", "expected": 2, "actual": 3},
    ]
    _write_report(tmp_path / "a.json", "alpha",
                  [_tc("t1", 0.5, checks=checks, log_path="harness-logs/x.log")])

    reports = load_reports(tmp_path)
    detail = report_detail(reports[0], "t1")

    assert detail["testcase_id"] == "t1"
    assert detail["checks"][1]["expected"] == 2
    assert detail["checks"][1]["actual"] == 3
    assert detail["log_path"] == "harness-logs/x.log"


def test_report_detail_missing_testcase_returns_none(tmp_path):
    _write_report(tmp_path / "a.json", "alpha", [_tc("t1", 1.0)])
    reports = load_reports(tmp_path)

    assert report_detail(reports[0], "nope") is None
