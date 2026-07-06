from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import click

from aigamedevbench.git_ops import get_repo_root


def _config(godot_binary: str) -> dict:
    return {"global": {"godot": {"binary": godot_binary}}}


def _fmt_harness_failure(testcase_id: str, outcome: dict, tail_lines: int = 30) -> list[str]:
    """Lines describing a harness failure (timeout, stall, approval-block, or
    non-zero exit) plus its log tail, so problems are visible immediately instead
    of buried in a log file. Empty list if the harness did not fail."""
    timed_out = outcome.get("timed_out")
    stalled = outcome.get("stalled")
    blocked = outcome.get("blocked_on_approval")
    exit_code = outcome.get("exit_code", 0)
    if not (timed_out or stalled or blocked) and exit_code == 0:
        return []
    if blocked:
        reason = "BLOCKED ON APPROVAL"
    elif stalled:
        reason = "STALLED (no output)"
    elif timed_out:
        reason = "TIMEOUT"
    else:
        reason = f"exit_code={exit_code}"
    out = [f"  !! harness {reason} for {testcase_id}"]
    log_path = outcome.get("log_path")
    if not log_path:
        out.append("     (no log captured - run with --log-dir to capture output)")
        return out
    try:
        text = Path(log_path).read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        out.append(f"     (could not read log {log_path}: {e})")
        return out
    out.append(f"     log: {log_path}")
    for line in text.splitlines()[-tail_lines:]:
        out.append(f"     | {line}")
    return out


def _fmt_verifier_result(verifier_result, tail_detail: int = 200) -> list[str]:
    """Lines for the verifier's per-check breakdown (and any error) so the user
    can see *why* a testcase scored what it did, not just the score."""
    out: list[str] = []
    if verifier_result.error:
        out.append(f"     verifier error: {verifier_result.error}")
    for c in verifier_result.checks:
        mark = "PASS" if c.passed else "FAIL"
        line = f"     [{mark}] {c.name}"
        detail = (c.detail or "").strip()
        if detail:
            if len(detail) > tail_detail:
                detail = detail[:tail_detail] + "..."
            line += f" - {detail}"
        if c.expected is not None or c.actual is not None:
            line += f" (expected: {c.expected!r}, actual: {c.actual!r})"
        out.append(line)
    return out


def _echo_verifier_result(verifier_result, tail_detail: int = 200) -> None:
    """Thin wrapper: echo the verifier breakdown lines to stderr."""
    for line in _fmt_verifier_result(verifier_result, tail_detail):
        click.echo(line, err=True)


def _fmt_diff(result, max_lines: int = 40) -> list[str]:
    """Lines describing what the harness changed: a per-file summary plus a
    capped diff preview. The full diff lives in the report and --artifacts-dir."""
    diff = result.diff or ""
    if not diff.strip():
        return ["     changes: (none)"]
    files = [ln[len("+++ b/"):] for ln in diff.splitlines()
             if ln.startswith("+++ b/") and not ln.endswith("/dev/null")]
    out: list[str] = []
    if files:
        out.append(f"     changed {len(files)} file(s): {', '.join(files)}")
    lines = diff.splitlines()
    out.append("     --- diff ---")
    for ln in lines[:max_lines]:
        out.append(f"     | {ln}")
    if len(lines) > max_lines:
        out.append(f"     | ... ({len(lines) - max_lines} more lines)")
    if result.artifacts_path:
        out.append(f"     saved: {result.artifacts_path}")
    return out


def _format_result_block(tc, result, streamed_lines: list[str] | None,
                         label: str | None = None) -> list[str]:
    """Compose the full on-screen block for one finished testcase/attempt: any
    buffered harness output (parallel mode), the result row, the verifier
    breakdown, the diff, and a harness-failure tail. Returned as a list so the
    caller can flush it atomically (parallel runs must not interleave mid-line).
    `label` overrides the row id (e.g. "case#2" for the 2nd repeat attempt)."""
    row_id = label or tc.id
    block: list[str] = []
    if streamed_lines:
        block.extend(streamed_lines)
    stage = result.failure_stage
    stage_tag = "" if stage == "none" else f"\t[{stage}]"
    block.append(
        f"{row_id}\t{tc.category}\t{result.verifier_result.status}\t{result.score:.2f}{stage_tag}")
    block.extend(_fmt_verifier_result(result.verifier_result))
    block.extend(_fmt_diff(result))
    if result.harness_outcome:
        block.extend(_fmt_harness_failure(row_id, result.harness_outcome))
    return block


def _aggregate_testcase(attempt_recs: list[dict], repeat: int) -> dict:
    """Fold N attempt records of one testcase into a single report record.

    For repeat == 1 (or a single surviving attempt) the record is returned as-is
    (fully backward compatible — no `repeat` block). For repeat > 1 a
    representative attempt is chosen (the first full pass, else the first) to
    carry the diff/log/checks for drill-down, and a `repeat` block is attached
    with the per-attempt score distribution and stats. The record's top-level
    `score` becomes the mean, so existing consumers (matrix, mean_score) keep
    working and simply see the averaged score."""
    from aigamedevbench.stats import aggregate_scores, combine_repeat_stages
    if not attempt_recs:
        return {"score": 0.0, "status": "error", "failure_stage": "error",
                "error": "no attempts completed"}
    if len(attempt_recs) == 1:
        return attempt_recs[0]

    scores = [float(r.get("score", 0.0) or 0.0) for r in attempt_recs]
    stages = [r.get("failure_stage", "none") for r in attempt_recs]
    # Representative attempt: prefer a full pass so drill-down shows a successful
    # diff when one exists; otherwise the first attempt.
    rep = next((r for r, s in zip(attempt_recs, scores) if s >= 1.0), attempt_recs[0])
    agg = aggregate_scores(scores)
    record = dict(rep)  # copy so we don't mutate the representative attempt
    record["score"] = agg["mean"]
    record["repeat"] = {
        **agg,
        "scores": [round(s, 6) for s in scores],
        "failure_stages": combine_repeat_stages(stages),
    }
    return record


@click.group()
@click.version_option()
def main():
    """AIGameDevBench: controlled benchmark for AI Godot game development."""
    pass


@main.command("list")
@click.option("--testcases-dir", default="./testcases", type=click.Path(exists=True),
              help="Directory of testcases (default: ./testcases)")
def list_cmd(testcases_dir: str):
    """List discovered testcases."""
    from aigamedevbench.testcase import discover_testcases

    for tc in discover_testcases(Path(testcases_dir)):
        click.echo(f"{tc.id}\t{tc.category}\t{tc.verifier_type}\t{tc.source_kind}")


@main.command("audit")
@click.option("--testcases-dir", default="./testcases", type=click.Path(exists=True),
              help="Directory of testcases (default: ./testcases)")
@click.option("--only", "only", multiple=True,
              help="Audit only this testcase id (repeatable)")
@click.option("--json", "json_file", default=None, type=click.Path(),
              help="Write a machine-readable health snapshot")
@click.option("--repo-root", default=".", type=click.Path(),
              help="Fallback repo for git-type cases without source_repo")
@click.option("--godot-binary", default="godot",
              help="Godot executable for runtime verifiers")
def audit_cmd(testcases_dir: str, only: tuple[str, ...], json_file: str | None,
              repo_root: str, godot_binary: str):
    """Audit testcase health: noop must score 0 and golden patch must score 1."""
    from aigamedevbench.testcase_audit import (
        audit_testcases, format_audit_table, select_testcases, write_health_json,
    )

    rows = audit_testcases(
        select_testcases(Path(testcases_dir).resolve(), only or None),
        Path(repo_root).resolve(),
        godot_binary,
    )
    click.echo(format_audit_table(rows))
    if json_file:
        write_health_json(Path(json_file), rows)
        click.echo(f"--- health written to {json_file}")
    if any(not row["healthy"] for row in rows):
        raise click.exceptions.Exit(1)


@main.command("smoke")
@click.option("--testcases-dir", default="./testcases", type=click.Path(exists=True),
              help="Directory of testcases (default: ./testcases)")
@click.option("--testcase", "testcase_id", required=True,
              help="Testcase id to validate")
@click.option("--patch", "patch_file", default=None, type=click.Path(exists=True),
              help="Golden patch to replay (default: testcase/fix.diff)")
@click.option("--repo-root", default=".", type=click.Path(),
              help="Fallback repo for git-type cases without source_repo")
@click.option("--godot-binary", default="godot",
              help="Godot executable for runtime verifiers")
def smoke_cmd(testcases_dir: str, testcase_id: str, patch_file: str | None,
              repo_root: str, godot_binary: str):
    """Quickly validate one testcase's admission invariants."""
    from aigamedevbench.testcase import discover_testcases
    from aigamedevbench.testcase_audit import audit_one, format_audit_table

    matches = [tc for tc in discover_testcases(Path(testcases_dir).resolve())
               if tc.id == testcase_id]
    if not matches:
        click.echo(f"Testcase '{testcase_id}' not found.")
        raise click.exceptions.Exit(1)
    row = audit_one(matches[0], Path(repo_root).resolve(), godot_binary,
                    Path(patch_file) if patch_file else None)
    click.echo(format_audit_table([row]))
    if not row["healthy"]:
        raise click.exceptions.Exit(1)


@main.command("scaffold")
@click.option("--testcases-dir", default="./testcases", type=click.Path(),
              help="Directory where the testcase will be created (default: ./testcases)")
@click.option("--id", "testcase_id", required=True,
              help="New testcase id, e.g. pathfinding-npc-bridge-astar")
@click.option("--category", default="behavior_logic",
              type=click.Choice([
                  "behavior_logic", "intent_translation", "precise_edit",
                  "architecture", "visual_audio",
              ]))
@click.option("--task", default="TODO: describe the requested game-dev change",
              help="Task text to put in testcase.toml")
@click.option("--source-project", default=None, type=click.Path(exists=True),
              help="Copy this Godot project into baseline/ (strips .git/.godot)")
@click.option("--source-repo", default=None,
              help="Provenance label or repo path recorded in testcase.toml")
@click.option("--force", is_flag=True,
              help="Overwrite scaffold files if they already exist")
def scaffold_cmd(testcases_dir: str, testcase_id: str, category: str, task: str,
                 source_project: str | None, source_repo: str | None, force: bool):
    """Create a standard self-contained folder-type testcase skeleton."""
    from aigamedevbench.testcase_scaffold import scaffold_folder_testcase

    try:
        result = scaffold_folder_testcase(
            Path(testcases_dir), testcase_id, category=category, task=task,
            source_project=Path(source_project) if source_project else None,
            source_repo=source_repo, force=force,
        )
    except (OSError, ValueError) as e:
        click.echo(str(e))
        raise click.exceptions.Exit(1)
    click.echo(f"--- created {result.testcase_dir}")
    for path in result.created_files:
        click.echo(f"  {path}")


@main.command("run")
@click.option("--testcases-dir", default="./testcases", type=click.Path(exists=True),
              help="Directory of testcases (default: ./testcases)")
@click.option("--testcase", "testcase_id", default=None, help="Run only this testcase id")
@click.option("--harness", "harness_id", default="manual", help="Harness id label")
@click.option("--driver", type=click.Choice(["noop", "patch", "command"]), default="noop")
@click.option("--patch", "patch_file", default=None, type=click.Path(exists=True))
@click.option("--harness-cmd", "harness_cmd", default=None,
              help="Command template for --driver command, e.g. 'claude -p {task}'")
@click.option("--timeout", default=600.0, type=float, help="Per-testcase harness timeout (s)")
@click.option("--stall-timeout", "stall_timeout", default=0.0, type=float,
              help="Abort a harness that produces no output for this many seconds. "
                   "Default 0 (disabled): harnesses like 'claude -p' print nothing "
                   "until done, so a stall guard would kill long healthy tasks. "
                   "Only set this for harnesses that stream progress incrementally.")
@click.option("--log-dir", "log_dir", default="harness-logs", type=click.Path(),
              help="Where to write harness stdout/stderr logs")
@click.option("--report", "report_file", default=None, type=click.Path(),
              help="Write a JSON report to this path")
@click.option("--workspace-root", "workspace_root", default=None, type=click.Path(),
              help="Where to create per-testcase workspaces (default: OS temp dir). "
                   "Use a path your harness trusts if it gates edits under temp.")
@click.option("--artifacts-dir", "artifacts_dir", default=None, type=click.Path(),
              help="Persist each testcase's harness output here (a changes.diff and a "
                   "files/ copy of every changed file) for later re-verification. The "
                   "throwaway workspace is deleted after the run, so without this the "
                   "agent's code is lost.")
@click.option("--stream/--no-stream", "stream", default=True,
              help="Stream harness output live to the screen (default: on). "
                   "Ignored when --jobs > 1: parallel runs buffer each testcase's "
                   "output and print it as one block on completion, to avoid "
                   "interleaving. The full per-testcase log still goes to --log-dir.")
@click.option("--jobs", "-j", "jobs", default=1, type=int,
              help="Run this many testcases concurrently (default: 1 = serial). "
                   "Harness and Godot both run as subprocesses, so a thread pool "
                   "parallelises the I/O-bound wait. Each testcase gets its own "
                   "isolated workspace and driver, so results are identical to a "
                   "serial run. Mind machine load with runtime (Godot) verifiers.")
@click.option("--harness-format", "harness_format",
              type=click.Choice(["auto", "stream-json", "text"]), default="auto",
              help="How to parse the harness's stdout into structured per-turn "
                   "events (tool calls, tokens) for the report/dashboard. "
                   "'auto' tries stream-json per line then falls back to a text "
                   "heuristic; 'stream-json' is strict (pass e.g. Claude Code "
                   "--output-format stream-json --verbose); 'text' is heuristic only.")
@click.option("--repeat", "repeat", default=1, type=int,
              help="Run each testcase this many times (default: 1). An AI harness "
                   "is stochastic, so a single pass cannot separate a real skill "
                   "gap from luck. With --repeat > 1 each testcase's report record "
                   "carries a `repeat` block (per-attempt scores, mean, std, a 95%% "
                   "confidence interval, pass@1) and its `score` is the mean. "
                   "Combines with --jobs: (testcase x attempt) tasks are flattened "
                   "into the same thread pool.")
@click.option("--godot-binary", default="godot", help="Godot executable for L0/runtime verifiers")
def run_cmd(testcases_dir: str, testcase_id: str | None, harness_id: str,
            driver: str, patch_file: str | None, harness_cmd: str | None,
            timeout: float, stall_timeout: float, log_dir: str, report_file: str | None,
            workspace_root: str | None, artifacts_dir: str | None,
            stream: bool, jobs: int, harness_format: str, repeat: int,
            godot_binary: str):
    """Run testcases against a harness driver (executed inside the target game repo)."""
    from aigamedevbench.testcase import discover_testcases
    from aigamedevbench.runner import run_testcase
    from aigamedevbench.driver import NoOpDriver, PatchDriver, CommandHarnessDriver

    config = _config(godot_binary)
    jobs = max(1, jobs)
    repeat = max(1, repeat)
    patch_text = None
    if driver == "patch":
        if not patch_file:
            click.echo("--patch FILE required with --driver patch")
            return
        patch_text = Path(patch_file).read_text(encoding="utf-8")
    elif driver == "command" and not harness_cmd:
        click.echo("--harness-cmd TEMPLATE required with --driver command")
        return

    # Live streaming only makes sense serially and without repeats: with >1 job
    # or >1 attempt, lines from different runs interleave unreadably, so we buffer
    # and flush per block instead.
    live_stream = stream and jobs == 1 and repeat == 1

    def make_driver(label: str, sink: list[str] | None):
        """Build a FRESH driver per testcase so concurrent runs share no mutable
        state (label / last_outcome / event parser are all per-instance)."""
        if driver == "patch":
            return PatchDriver(patch_text or "")
        if driver == "command":
            def on_line(line: str) -> None:
                if live_stream:
                    click.echo(f"  [{label}] {line}", err=True)
                elif sink is not None:
                    sink.append(f"  [{label}] {line}")
            d = CommandHarnessDriver(harness_cmd, timeout=timeout,
                                     log_dir=Path(log_dir), stall_timeout=stall_timeout,
                                     on_line=on_line, harness_format=harness_format)
            d.label = label
            return d
        return NoOpDriver()

    testcases = discover_testcases(Path(testcases_dir))
    if testcase_id:
        testcases = [t for t in testcases if t.id == testcase_id]
        if not testcases:
            click.echo(f"Testcase '{testcase_id}' not found.")
            return

    # Folder-type testcases are self-contained and run anywhere; only git-type
    # ones need a repo root. Resolve it lazily and tolerantly: if cwd isn't a
    # git repo, git-type testcases fail individually (below) rather than aborting
    # the whole batch — a non-git cwd is normal when scoring folder-type cases.
    needs_repo = any(t.source_kind != "folder" for t in testcases)
    repo_root = None
    if needs_repo:
        try:
            repo_root = get_repo_root(Path.cwd())
        except (RuntimeError, FileNotFoundError):
            repo_root = None

    def run_attempt(tc, attempt: int):
        """Run one attempt of one testcase. Returns (record, output-block). The
        block is buffered (not printed) so the caller flushes it atomically."""
        label = tc.id if repeat == 1 else f"{tc.id}#{attempt + 1}"
        sink: list[str] = []
        drv = make_driver(label, sink)
        try:
            result = run_testcase(repo_root, tc, drv, harness_id, config,
                                  workspace_root=workspace_root,
                                  artifacts_dir=artifacts_dir)
        except Exception as e:
            # One un-runnable attempt (e.g. a git-type case with no repo root, or
            # a bad baseline_ref) must not kill the rest of the batch.
            rec = {"testcase_id": tc.id, "category": tc.category,
                   "score": 0.0, "status": "error", "failure_stage": "error",
                   "error": str(e)}
            return rec, [f"{label}\t{tc.category}\terror\t0.00\t{e}"]
        record = result.to_dict()
        block = _format_result_block(tc, result, sink if not live_stream else None,
                                     label=label)
        return record, block

    lock = threading.Lock()
    # One slot per (testcase, attempt), so results land in a deterministic place
    # regardless of completion order — the report stays stable and diffable.
    attempts = [(ti, a) for ti in range(len(testcases)) for a in range(repeat)]
    slots: list[dict | None] = [None] * len(attempts)

    def _flush(block):
        with lock:
            for line in block:
                click.echo(line, err=True)

    if jobs == 1:
        for idx, (ti, a) in enumerate(attempts):
            record, block = run_attempt(testcases[ti], a)
            slots[idx] = record
            _flush(block)
    else:
        with ThreadPoolExecutor(max_workers=jobs) as ex:
            futs = {ex.submit(run_attempt, testcases[ti], a): idx
                    for idx, (ti, a) in enumerate(attempts)}
            for fut in as_completed(futs):
                idx = futs[fut]
                record, block = fut.result()
                slots[idx] = record
                _flush(block)

    # Group attempts back by testcase (input order) and aggregate.
    records: list[dict] = []
    for ti, tc in enumerate(testcases):
        attempt_recs = [slots[idx] for idx, (t, _a) in enumerate(attempts)
                        if t == ti and slots[idx] is not None]
        records.append(_aggregate_testcase(attempt_recs, repeat))

    total = sum(float(r.get("score", 0.0) or 0.0) for r in records)
    mean = total / len(testcases) if testcases else 0.0
    if testcases:
        # Suite-level mean of per-testcase means, plus a CI derived from the
        # spread of per-testcase scores (how much the suite score itself moves).
        from aigamedevbench.stats import aggregate_scores
        suite = aggregate_scores([float(r.get("score", 0.0) or 0.0) for r in records])
        ci = suite["ci95"]
        repeat_note = f" (repeat={repeat})" if repeat > 1 else ""
        click.echo(
            f"--- mean score: {mean:.3f} ± {(ci[1]-ci[0])/2:.3f} "
            f"[95% CI {ci[0]:.3f}, {ci[1]:.3f}] over {len(testcases)} testcase(s){repeat_note}")
        # Failure funnel: aggregate across ALL attempts (not just representatives)
        # so a flaky harness's intermittent no_change/harness_error is visible.
        stage_counts: dict[str, int] = {}
        for rec in records:
            rpt = rec.get("repeat") or {}
            per = rpt.get("failure_stages")
            if per:
                for s, n in per.items():
                    stage_counts[s] = stage_counts.get(s, 0) + n
            else:
                s = rec.get("failure_stage", "none")
                stage_counts[s] = stage_counts.get(s, 0) + 1
        breakdown = ", ".join(f"{s}={n}" for s, n in sorted(stage_counts.items()))
        click.echo(f"--- failure stages: {breakdown}")

    if report_file:
        import json
        report = {"harness": harness_id, "count": len(testcases),
                  "repeat": repeat, "mean_score": mean,
                  "mean_score_ci95": suite["ci95"] if testcases else [0.0, 0.0],
                  "testcases": records}
        Path(report_file).write_text(json.dumps(report, indent=2), encoding="utf-8")
        click.echo(f"--- report written to {report_file}")


@main.command("compare")
@click.option("--report-a", "report_a", required=True, type=click.Path(exists=True),
              help="First run's report JSON (harness A)")
@click.option("--report-b", "report_b", required=True, type=click.Path(exists=True),
              help="Second run's report JSON (harness B)")
@click.option("--iters", default=10000, type=int,
              help="Bootstrap resamples (default 10000)")
@click.option("--seed", default=0, type=int, help="RNG seed for reproducibility")
@click.option("--top", default=5, type=int,
              help="Show this many testcases that contribute most to the difference")
def compare_cmd(report_a: str, report_b: str, iters: int, seed: int, top: int):
    """Statistically compare two harness runs on their shared testcases.

    Runs a paired bootstrap over the per-testcase score differences and reports
    the mean difference, a 95% confidence interval, and a two-sided p-value — so
    "harness A beats B" becomes a claim you can judge, not eyeball. Pairing on
    the same testcases removes per-testcase difficulty variance.
    """
    import json
    from aigamedevbench.stats import paired_bootstrap, paired_scores

    rep_a = json.loads(Path(report_a).read_text(encoding="utf-8"))
    rep_b = json.loads(Path(report_b).read_text(encoding="utf-8"))
    name_a = rep_a.get("harness") or Path(report_a).stem
    name_b = rep_b.get("harness") or Path(report_b).stem

    ids, sa, sb = paired_scores(rep_a, rep_b)
    if not ids:
        click.echo("No common testcases between the two reports — nothing to compare.")
        return
    res = paired_bootstrap(sa, sb, iters=iters, seed=seed)

    click.echo(f"--- compare: A={name_a}  vs  B={name_b}  ({res['n']} shared testcase(s))")
    click.echo(f"  A mean {res['mean_a']:.3f}   B mean {res['mean_b']:.3f}")
    ci = res["ci95"]
    click.echo(f"  mean diff (A-B): {res['mean_diff']:+.3f}  "
               f"[95% CI {ci[0]:+.3f}, {ci[1]:+.3f}]  p={res['p_value']:.4f}")
    # A CI that excludes 0 (equivalently p<0.05) is the "significant" signal.
    verdict = ("significant (CI excludes 0)" if ci[0] > 0 or ci[1] < 0
               else "not significant (CI spans 0)")
    better = name_a if res["mean_diff"] > 0 else name_b
    if abs(res["mean_diff"]) < 1e-9:
        click.echo("  verdict: identical mean")
    else:
        click.echo(f"  verdict: {verdict}; point estimate favors {better}")

    # Per-category mean difference, so a gap can be localised to a capability.
    by_cat_a = _scores_by_category(rep_a)
    by_cat_b = _scores_by_category(rep_b)
    cats = sorted(set(by_cat_a) & set(by_cat_b))
    if cats:
        click.echo("  per-category mean diff (A-B):")
        for c in cats:
            common = sorted(set(by_cat_a[c]) & set(by_cat_b[c]))
            if not common:
                continue
            d = sum(by_cat_a[c][t] - by_cat_b[c][t] for t in common) / len(common)
            click.echo(f"    {c:24s} {d:+.3f}  (n={len(common)})")

    # Which testcases drive the difference (largest |a-b|), so you know WHERE
    # the harnesses diverge, not just that they do.
    diffs = sorted(((a - b, t) for t, a, b in zip(ids, sa, sb)),
                   key=lambda x: abs(x[0]), reverse=True)
    shown = [(d, t) for d, t in diffs if abs(d) > 1e-9][:top]
    if shown:
        click.echo(f"  top {len(shown)} contributing testcase(s):")
        for d, t in shown:
            click.echo(f"    {t:40s} {d:+.3f}")


def _scores_by_category(report: dict) -> dict:
    """{category: {testcase_id: score}} for per-category paired diffs."""
    out: dict[str, dict] = {}
    for tc in report.get("testcases", []):
        cat = tc.get("category", "")
        tid = tc.get("testcase_id")
        if tid is None:
            continue
        out.setdefault(cat, {})[tid] = float(tc.get("score", 0.0) or 0.0)
    return out


@main.command("serve")
@click.option("--reports-dir", default=".", type=click.Path(exists=True),
              help="Directory to scan for *.json benchmark reports (default: cwd)")
@click.option("--testcases-dir", "testcases_dir", default=None, type=click.Path(),
              help="Directory of testcases to show in the Testcases tab "
                   "(default: ./testcases if it exists)")
@click.option("--port", default=8000, type=int)
@click.option("--host", default="127.0.0.1")
@click.option("--open-browser/--no-open-browser", default=True,
              help="Open the dashboard in a browser on startup (default: on)")
@click.option("--editable/--no-editable", default=False,
              help="Enable in-dashboard testcase create/edit/delete (writes to "
                   "--testcases-dir). Off by default: the dashboard is read-only "
                   "unless this flag is passed.")
def serve_cmd(reports_dir: str, testcases_dir: str | None, port: int, host: str,
              open_browser: bool, editable: bool):
    """Serve a local web dashboard to view and compare benchmark reports.

    Scans --reports-dir for report JSON files on every request, so re-running a
    benchmark and refreshing the page shows the new run immediately. Pure
    stdlib, fully offline; charts are drawn with native SVG/CSS.
    """
    import json
    import webbrowser
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from urllib.parse import urlparse, parse_qs

    from aigamedevbench.webreport import (
        INDEX_HTML, load_reports, build_summary, report_detail,
        load_testcase_catalog, load_testcase_detail,
        create_testcase, save_testcase_file, delete_testcase_file,
        editor_enums, EditError,
    )

    root = Path(reports_dir)
    if testcases_dir:
        tc_root = Path(testcases_dir)
    else:
        default_tc = root / "testcases"
        tc_root = default_tc if default_tc.is_dir() else None

    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, body: bytes, content_type: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj, code: int = 200) -> None:
            self._send(code, json.dumps(obj).encode("utf-8"),
                       "application/json; charset=utf-8")

        def do_GET(self) -> None:  # noqa: N802 (http.server API)
            parsed = urlparse(self.path)
            path = parsed.path
            if path == "/":
                self._send(200, INDEX_HTML.encode("utf-8"),
                           "text/html; charset=utf-8")
                return
            if path == "/api/config":
                self._json({"editable": editable and tc_root is not None,
                            "has_testcases": tc_root is not None,
                            "enums": editor_enums()})
                return
            if path == "/api/summary":
                self._json(build_summary(load_reports(root)))
                return
            if path == "/api/testcases":
                self._json(load_testcase_catalog(tc_root) if tc_root else [])
                return
            if path == "/api/testcase":
                q = parse_qs(parsed.query)
                tc = (q.get("id") or [""])[0]
                detail = load_testcase_detail(tc_root, tc) if tc_root else None
                self._json(detail if detail is not None else {"error": "not found"},
                           code=200 if detail is not None else 404)
                return
            if path == "/api/detail":
                q = parse_qs(parsed.query)
                run = (q.get("run") or [""])[0]
                tc = (q.get("testcase") or [""])[0]
                for r in load_reports(root):
                    if r["_run_id"] == run:
                        detail = report_detail(r, tc, reports_dir=root)
                        if detail is not None:
                            self._json(detail)
                            return
                        break
                self._json({"error": "not found"}, code=404)
                return
            self._json({"error": "not found"}, code=404)

        def _read_json_body(self) -> dict:
            length = int(self.headers.get("Content-Length") or 0)
            if length <= 0:
                return {}
            raw = self.rfile.read(length)
            try:
                obj = json.loads(raw.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                return {}
            return obj if isinstance(obj, dict) else {}

        def do_POST(self) -> None:  # noqa: N802 (http.server API)
            parsed = urlparse(self.path)
            path = parsed.path
            # Every write endpoint is gated on --editable AND a known testcases dir.
            if not (editable and tc_root is not None):
                self._json({"error": "editing is disabled (run serve with --editable)"},
                           code=403)
                return
            body = self._read_json_body()
            try:
                if path == "/api/testcase/create":
                    result = create_testcase(tc_root, str(body.get("id", "")),
                                             str(body.get("category", "behavior_logic")),
                                             str(body.get("task", "")))
                    self._json(result)
                    return
                if path == "/api/testcase/save-file":
                    result = save_testcase_file(tc_root, str(body.get("id", "")),
                                                str(body.get("path", "")),
                                                str(body.get("content", "")))
                    self._json(result)
                    return
                if path == "/api/testcase/delete-file":
                    result = delete_testcase_file(tc_root, str(body.get("id", "")),
                                                  str(body.get("path", "")))
                    self._json(result)
                    return
            except EditError as e:
                self._json({"error": str(e)}, code=e.status)
                return
            self._json({"error": "not found"}, code=404)

        def log_message(self, *args) -> None:
            pass  # keep the console quiet; failures still raise

    server = ThreadingHTTPServer((host, port), Handler)
    url = f"http://{host}:{port}/"
    click.echo(f"--- serving {root.resolve()} at {url} (Ctrl-C to stop)")
    if tc_root:
        mode = "editable" if editable else "read-only"
        click.echo(f"--- testcases from {tc_root.resolve()} ({mode})")
    elif editable:
        click.echo("--- --editable ignored: no --testcases-dir")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        click.echo("\n--- stopped")
    finally:
        server.server_close()
