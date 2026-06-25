from __future__ import annotations

from pathlib import Path

from aigamedevbench import validation
from aigamedevbench.validation import (
    check_gd_syntax, check_signal_targets, run_validation,
)


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


def test_signal_target_defined_on_directly_scripted_node(tmp_path):
    (tmp_path / "h.gd").write_text(
        "extends Node\nfunc on_hit():\n\tpass\n", encoding="utf-8")
    (tmp_path / "s.tscn").write_text(
        '[gd_scene load_steps=2 format=3]\n'
        '[ext_resource type="Script" path="res://h.gd" id="1"]\n'
        '[node name="Root" type="Node"]\n'
        'script = ExtResource("1")\n'
        '[connection signal="sig" from="." to="." method="on_hit"]\n',
        encoding="utf-8")
    assert check_signal_targets(tmp_path, ["s.tscn"]) == []


def test_signal_target_method_on_instanced_scene_is_resolved(tmp_path):
    # Regression (gdb-task_0027): a connection whose target method lives on the
    # root script of an INSTANCED PackedScene must resolve. The method is not in
    # the parent .tscn's own script ext_resources, so the check must follow the
    # instance=ExtResource("...") PackedScene to its root script.
    (tmp_path / "player.gd").write_text(
        "extends Node3D\nfunc apply_weapon_impulse(d, p):\n\tpass\n",
        encoding="utf-8")
    (tmp_path / "player.tscn").write_text(
        '[gd_scene load_steps=2 format=3]\n'
        '[ext_resource type="Script" path="res://player.gd" id="1_p"]\n'
        '[node name="PlayerBody" type="Node3D"]\n'
        'script = ExtResource("1_p")\n',
        encoding="utf-8")
    (tmp_path / "main.tscn").write_text(
        '[gd_scene load_steps=2 format=3]\n'
        '[ext_resource type="PackedScene" path="res://player.tscn" id="1_pb"]\n'
        '[node name="Main" type="Node3D"]\n'
        '[node name="PlayerBody" parent="." instance=ExtResource("1_pb")]\n'
        '[connection signal="on_shot" from="WeaponEffects" to="PlayerBody" '
        'method="apply_weapon_impulse"]\n',
        encoding="utf-8")
    assert check_signal_targets(tmp_path, ["main.tscn"]) == []


def test_signal_target_truly_missing_still_flagged_with_instances(tmp_path):
    # Following instanced scenes must not mask a genuinely undefined method.
    (tmp_path / "player.gd").write_text(
        "extends Node3D\nfunc some_other():\n\tpass\n", encoding="utf-8")
    (tmp_path / "player.tscn").write_text(
        '[gd_scene load_steps=2 format=3]\n'
        '[ext_resource type="Script" path="res://player.gd" id="1_p"]\n'
        '[node name="PlayerBody" type="Node3D"]\n'
        'script = ExtResource("1_p")\n',
        encoding="utf-8")
    (tmp_path / "main.tscn").write_text(
        '[gd_scene load_steps=2 format=3]\n'
        '[ext_resource type="PackedScene" path="res://player.tscn" id="1_pb"]\n'
        '[node name="Main" type="Node3D"]\n'
        '[node name="PlayerBody" parent="." instance=ExtResource("1_pb")]\n'
        '[connection signal="on_shot" from="W" to="PlayerBody" method="nope"]\n',
        encoding="utf-8")
    issues = check_signal_targets(tmp_path, ["main.tscn"])
    assert any("nope" in i for i in issues)


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


def test_godot_import_resolves_msys_path_and_runs(tmp_path, monkeypatch):
    # An MSYS /d/... binary that which() can't resolve directly must still run
    # the import via its native d:/... form, not be silently skipped.
    (tmp_path / "project.godot").write_text("config_version=5\n", encoding="utf-8")

    def fake_which(b):
        return r"D:\Godot\godot.exe" if b == "d:/Godot/godot/bin/godot" else None

    monkeypatch.setattr(validation.shutil, "which", fake_which)
    ran = {}

    class _Proc:
        returncode = 0
        stderr = ""

    def _fake_run(argv, *a, **k):
        ran["argv"] = argv
        return _Proc()

    monkeypatch.setattr(validation.subprocess, "run", _fake_run)
    msg = validation.godot_import(tmp_path, "/d/Godot/godot/bin/godot")
    assert msg is None
    assert ran["argv"][0] == r"D:\Godot\godot.exe"


def test_godot_import_errors_on_explicit_unresolvable_binary(tmp_path, monkeypatch):
    # An explicit path-like binary that resolves to nothing is a misconfiguration,
    # not "godot absent": report it instead of silently skipping import.
    (tmp_path / "project.godot").write_text("config_version=5\n", encoding="utf-8")
    monkeypatch.setattr(validation.shutil, "which", lambda _: None)
    msg = validation.godot_import(tmp_path, "/d/nope/godot")
    assert msg is not None and "not found" in msg and "/d/nope/godot" in msg


def test_godot_import_silent_skip_on_bare_name_absent(tmp_path, monkeypatch):
    # A bare 'godot' (the default) not on PATH means godot isn't installed:
    # skip silently, return None (downstream godot steps skip too).
    (tmp_path / "project.godot").write_text("config_version=5\n", encoding="utf-8")
    monkeypatch.setattr(validation.shutil, "which", lambda _: None)
    assert validation.godot_import(tmp_path, "godot") is None


def test_run_l0_errors_on_explicit_unresolvable_binary(tmp_path, monkeypatch):
    (tmp_path / "scenes").mkdir()
    monkeypatch.setattr(validation.shutil, "which", lambda _: None)
    ok, issues = validation.run_l0(tmp_path, ["scenes/x.tscn"], "/d/nope/godot")
    assert ok is False
    assert any("not found" in i for i in issues)


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
