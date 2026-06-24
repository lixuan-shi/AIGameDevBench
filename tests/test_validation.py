from __future__ import annotations

from pathlib import Path

from aigamedevbench import validation
from aigamedevbench.validation import check_gd_syntax, run_validation


def test_paren_in_string_not_counted(tmp_path):
    # Regression: a '(' inside a string literal must not be read as an unclosed
    # paren. GameDevBench's vendored QuestManager.gd has `split("(")[0]`.
    (tmp_path / "a.gd").write_text(
        'extends Node\n'
        'func f():\n'
        '\tvar callable = function.split("(")[0]\n',
        encoding="utf-8")
    issues = check_gd_syntax(tmp_path, ["a.gd"])
    assert issues == []


def test_paren_in_comment_not_counted(tmp_path):
    (tmp_path / "a.gd").write_text(
        'extends Node\n'
        '# get only function name without ()\n'
        'func f():\n'
        '\tpass\n',
        encoding="utf-8")
    assert check_gd_syntax(tmp_path, ["a.gd"]) == []


def test_real_unclosed_paren_still_flagged(tmp_path):
    (tmp_path / "a.gd").write_text(
        'extends Node\n'
        'func f():\n'
        '\tvar x = foo(1, 2\n',
        encoding="utf-8")
    issues = check_gd_syntax(tmp_path, ["a.gd"])
    assert any("unclosed" in i for i in issues)


def test_real_unmatched_close_paren_still_flagged(tmp_path):
    (tmp_path / "a.gd").write_text(
        'extends Node\n'
        'func f():\n'
        '\tvar x = 1)\n',
        encoding="utf-8")
    issues = check_gd_syntax(tmp_path, ["a.gd"])
    assert any("unmatched" in i for i in issues)


def test_escaped_quote_in_string(tmp_path):
    # A backslash-escaped quote must not end the string early, which would
    # otherwise expose a '(' that is really inside the string.
    (tmp_path / "a.gd").write_text(
        'extends Node\n'
        'func f():\n'
        '\tvar s = "a \\" ( b"\n',
        encoding="utf-8")
    assert check_gd_syntax(tmp_path, ["a.gd"]) == []


def test_run_validation_calls_godot_import_before_l0(tmp_path, monkeypatch):
    # The import pass must run before L0 boots changed scenes so imported
    # resources resolve. Assert godot_import is invoked, ahead of run_l0.
    calls = []
    monkeypatch.setattr(validation, "godot_import",
                        lambda root, binary="godot": calls.append("import"))
    monkeypatch.setattr(validation, "run_l0",
                        lambda root, scenes, binary="godot": (calls.append("l0"), (True, []))[1])
    monkeypatch.setattr(validation, "run_l1",
                        lambda root, changed: (True, []))
    result = run_validation(tmp_path, ["scenes/x.tscn"], {})
    assert calls == ["import", "l0"]
    assert result.l0_pass and result.l1_pass


def test_godot_import_noop_without_binary(tmp_path, monkeypatch):
    # No godot on PATH -> import is a silent no-op, never raises, returns None.
    monkeypatch.setattr(validation.shutil, "which", lambda _: None)
    assert validation.godot_import(tmp_path) is None


def test_godot_import_skips_non_godot_project(tmp_path, monkeypatch):
    # A directory with no project.godot (e.g. a py_config data repo) is not a
    # Godot project: import must be skipped, never run, and report no error.
    monkeypatch.setattr(validation.shutil, "which", lambda _: "/usr/bin/godot")
    ran = []
    monkeypatch.setattr(validation.subprocess, "run",
                        lambda *a, **k: ran.append(a) or None)
    assert validation.godot_import(tmp_path) is None
    assert ran == []


def test_godot_import_reports_nonzero_exit(tmp_path, monkeypatch):
    # A non-zero --import exit must be reported (not swallowed) so an incomplete
    # cache becomes a visible diagnostic instead of a later verifier hang.
    (tmp_path / "project.godot").write_text("config_version=5\n", encoding="utf-8")
    monkeypatch.setattr(validation.shutil, "which", lambda _: "/usr/bin/godot")

    class _Proc:
        returncode = 1
        stderr = "boom: could not import\n"

    monkeypatch.setattr(validation.subprocess, "run", lambda *a, **k: _Proc())
    msg = validation.godot_import(tmp_path)
    assert msg is not None and "exited 1" in msg


def test_godot_import_reports_timeout(tmp_path, monkeypatch):
    (tmp_path / "project.godot").write_text("config_version=5\n", encoding="utf-8")
    monkeypatch.setattr(validation.shutil, "which", lambda _: "/usr/bin/godot")

    def _raise(*a, **k):
        raise validation.subprocess.TimeoutExpired(cmd="godot", timeout=120)

    monkeypatch.setattr(validation.subprocess, "run", _raise)
    msg = validation.godot_import(tmp_path)
    assert msg is not None and "timed out" in msg


def test_run_validation_fails_gate_on_import_error(tmp_path, monkeypatch):
    # When import fails, the L0 gate must fail and carry the import diagnostic.
    monkeypatch.setattr(validation, "godot_import",
                        lambda root, binary="godot": "godot --import exited 1: boom")
    monkeypatch.setattr(validation, "run_l0",
                        lambda root, scenes, binary="godot": (True, []))
    monkeypatch.setattr(validation, "run_l1", lambda root, changed: (True, []))
    result = run_validation(tmp_path, ["scenes/x.tscn"], {})
    assert result.l0_pass is False
    assert any("import:" in d for d in result.l0_details)
