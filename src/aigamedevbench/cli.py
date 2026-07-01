from __future__ import annotations

from pathlib import Path

import click

from aigamedevbench.git_ops import get_repo_root


def _config(godot_binary: str) -> dict:
    return {"global": {"godot": {"binary": godot_binary}}}


def _echo_harness_failure(testcase_id: str, outcome: dict, tail_lines: int = 30) -> None:
    """Print a harness failure (timeout, stall, approval-block, or non-zero exit)
    and its log tail to the screen so problems are visible immediately instead of
    buried in a log file."""
    timed_out = outcome.get("timed_out")
    stalled = outcome.get("stalled")
    blocked = outcome.get("blocked_on_approval")
    exit_code = outcome.get("exit_code", 0)
    if not (timed_out or stalled or blocked) and exit_code == 0:
        return
    if blocked:
        reason = "BLOCKED ON APPROVAL"
    elif stalled:
        reason = "STALLED (no output)"
    elif timed_out:
        reason = "TIMEOUT"
    else:
        reason = f"exit_code={exit_code}"
    click.echo(f"  !! harness {reason} for {testcase_id}", err=True)
    log_path = outcome.get("log_path")
    if not log_path:
        click.echo("     (no log captured - run with --log-dir to capture output)", err=True)
        return
    try:
        text = Path(log_path).read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        click.echo(f"     (could not read log {log_path}: {e})", err=True)
        return
    lines = text.splitlines()
    click.echo(f"     log: {log_path}", err=True)
    for line in lines[-tail_lines:]:
        click.echo(f"     | {line}", err=True)


def _echo_verifier_result(verifier_result, tail_detail: int = 200) -> None:
    """Print the verifier's per-check breakdown (and any error) to the screen so
    the user can see *why* a testcase scored what it did, not just the score."""
    if verifier_result.error:
        click.echo(f"     verifier error: {verifier_result.error}", err=True)
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
        click.echo(line, err=True)


def _echo_diff(result, max_lines: int = 40) -> None:
    """Log what the harness changed: a per-file summary plus a capped preview of
    the diff, so the modification is visible on screen and in the log without
    dumping a huge patch. The full diff lives in the report and --artifacts-dir."""
    diff = result.diff or ""
    if not diff.strip():
        click.echo("     changes: (none)", err=True)
        return
    files = [ln[len("+++ b/"):] for ln in diff.splitlines()
             if ln.startswith("+++ b/") and not ln.endswith("/dev/null")]
    if files:
        click.echo(f"     changed {len(files)} file(s): {', '.join(files)}", err=True)
    lines = diff.splitlines()
    click.echo("     --- diff ---", err=True)
    for ln in lines[:max_lines]:
        click.echo(f"     | {ln}", err=True)
    if len(lines) > max_lines:
        click.echo(f"     | ... ({len(lines) - max_lines} more lines)", err=True)
    if result.artifacts_path:
        click.echo(f"     saved: {result.artifacts_path}", err=True)


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
              help="Stream harness output live to the screen (default: on).")
@click.option("--godot-binary", default="godot", help="Godot executable for L0/runtime verifiers")
def run_cmd(testcases_dir: str, testcase_id: str | None, harness_id: str,
            driver: str, patch_file: str | None, harness_cmd: str | None,
            timeout: float, stall_timeout: float, log_dir: str, report_file: str | None,
            workspace_root: str | None, artifacts_dir: str | None,
            stream: bool, godot_binary: str):
    """Run testcases against a harness driver (executed inside the target game repo)."""
    from aigamedevbench.testcase import discover_testcases
    from aigamedevbench.runner import run_testcase
    from aigamedevbench.driver import NoOpDriver, PatchDriver, CommandHarnessDriver

    config = _config(godot_binary)

    if driver == "patch":
        if not patch_file:
            click.echo("--patch FILE required with --driver patch")
            return
        drv = PatchDriver(Path(patch_file).read_text(encoding="utf-8"))
    elif driver == "command":
        if not harness_cmd:
            click.echo("--harness-cmd TEMPLATE required with --driver command")
            return
        # Stream each harness line live (prefixed) so a stuck prompt is visible
        # the instant it appears, not after the timeout fires.
        on_line = None
        if stream:
            def on_line(line: str) -> None:
                click.echo(f"  [{drv.label}] {line}", err=True)
        drv = CommandHarnessDriver(harness_cmd, timeout=timeout,
                                   log_dir=Path(log_dir), stall_timeout=stall_timeout,
                                   on_line=on_line)
    else:
        drv = NoOpDriver()

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

    total = 0.0
    records = []
    for tc in testcases:
        if isinstance(drv, CommandHarnessDriver):
            drv.label = tc.id
        try:
            result = run_testcase(repo_root, tc, drv, harness_id, config,
                                  workspace_root=workspace_root,
                                  artifacts_dir=artifacts_dir)
        except Exception as e:
            # One un-runnable testcase (e.g. a git-type case with no repo root,
            # or a bad baseline_ref) must not kill the rest of the batch.
            click.echo(f"{tc.id}\t{tc.category}\terror\t0.00\t{e}")
            records.append({"testcase_id": tc.id, "category": tc.category,
                            "score": 0.0, "status": "error", "error": str(e)})
            continue
        total += result.score
        click.echo(f"{tc.id}\t{tc.category}\t{result.verifier_result.status}\t{result.score:.2f}")
        _echo_verifier_result(result.verifier_result)
        _echo_diff(result)
        # Surface harness failures on screen immediately (don't make the user dig
        # through log files): if the command harness timed out or exited non-zero,
        # echo the tail of its log right after the result row.
        if isinstance(drv, CommandHarnessDriver) and drv.last_outcome is not None:
            _echo_harness_failure(tc.id, drv.last_outcome)
        record = result.to_dict()
        if isinstance(drv, CommandHarnessDriver) and drv.last_outcome is not None:
            record.update(drv.last_outcome)
        records.append(record)

    mean = total / len(testcases) if testcases else 0.0
    if testcases:
        click.echo(f"--- mean score: {mean:.3f} over {len(testcases)} testcase(s)")

    if report_file:
        import json
        report = {"harness": harness_id, "count": len(testcases),
                  "mean_score": mean, "testcases": records}
        Path(report_file).write_text(json.dumps(report, indent=2), encoding="utf-8")
        click.echo(f"--- report written to {report_file}")


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
