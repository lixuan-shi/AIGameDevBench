from __future__ import annotations

import shutil

import pytest

from aigamedevbench.testcase import Testcase
from aigamedevbench.verifiers.godot_runtime import (
    GodotSceneTreeVerifier, parse_assertion_json, check_class_cache,
)


def _write(p, text):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_class_cache_ok_when_all_registered(tmp_path):
    _write(tmp_path / "components" / "state.gd", "class_name State\nextends RefCounted\n")
    _write(tmp_path / ".godot" / "global_script_class_cache.cfg",
           'list=[{\n"class": &"State",\n"path": "res://components/state.gd"\n}]')
    assert check_class_cache(tmp_path) is None


def test_class_cache_none_when_no_global_classes(tmp_path):
    _write(tmp_path / "a.gd", "extends Node\nfunc f():\n\tpass\n")
    assert check_class_cache(tmp_path) is None


def test_class_cache_missing_file_is_reported(tmp_path):
    _write(tmp_path / "components" / "state.gd", "class_name State\nextends RefCounted\n")
    msg = check_class_cache(tmp_path)
    assert msg is not None and "import cache incomplete" in msg and "State" in msg


def test_class_cache_unregistered_symbol_is_reported(tmp_path):
    _write(tmp_path / "components" / "state.gd", "class_name State\nextends RefCounted\n")
    _write(tmp_path / "components" / "fsm.gd", "class_name FiniteStateMachine\nextends RefCounted\n")
    _write(tmp_path / ".godot" / "global_script_class_cache.cfg",
           'list=[{\n"class": &"State",\n"path": "res://components/state.gd"\n}]')
    msg = check_class_cache(tmp_path)
    assert msg is not None and "FiniteStateMachine" in msg


def test_class_cache_ignores_injected_verifier(tmp_path):
    # The injected verifier file declaring class_name must not be counted as a
    # project class (it is removed after the run and never import-scanned).
    _write(tmp_path / ".aigdbench_verify_abc.gd", "class_name Injected\nextends Node\n")
    assert check_class_cache(tmp_path) is None


def test_parse_assertion_json():
    out = 'noise\n{"assertions": [{"name": "moved", "pass": true}, {"name": "ranged", "pass": false}]}\ntail'
    checks = parse_assertion_json(out)
    assert len(checks) == 2
    assert checks[0].name == "moved" and checks[0].passed is True
    assert checks[1].passed is False


def test_parse_assertion_json_carries_expected_actual():
    # A verifier reports expected vs actual per checkpoint so the report explains
    # WHAT was wrong, not just that a check failed. The parser must surface them.
    out = ('{"assertions": [{"name": "state", "pass": false, '
           '"detail": "wrong state", "expected": "CardBaseState", '
           '"actual": "CardClickedState"}]}')
    checks = parse_assertion_json(out)
    assert len(checks) == 1
    assert checks[0].expected == "CardBaseState"
    assert checks[0].actual == "CardClickedState"


def test_parse_assertion_json_expected_actual_default_none():
    # Assertions that omit expected/actual leave them None (back-compat).
    out = '{"assertions": [{"name": "x", "pass": true}]}'
    checks = parse_assertion_json(out)
    assert checks[0].expected is None
    assert checks[0].actual is None


def test_missing_binary_is_error(tmp_path, monkeypatch):
    monkeypatch.setattr("aigamedevbench.verifiers.godot_runtime.resolve_godot_binary",
                        lambda _: None)
    tc_dir = tmp_path / "tc"; tc_dir.mkdir()
    (tc_dir / "verifier.gd").write_text("extends SceneTree\n", encoding="utf-8")
    ws = tmp_path / "ws"; ws.mkdir()
    tc = Testcase("t", "behavior_logic", "ref", "task", "godot_scenetree",
                  "verifier.gd", "checkpoints", tc_dir)
    result = GodotSceneTreeVerifier().verify(tc, ws)
    assert result.status == "error"


@pytest.mark.skipif(shutil.which("godot") is None, reason="godot not installed")
def test_real_godot_runs(tmp_path):
    tc_dir = tmp_path / "tc"; tc_dir.mkdir()
    (tc_dir / "verifier.gd").write_text(
        'extends SceneTree\n'
        'func _initialize():\n'
        '    print(JSON.stringify({"assertions": [{"name": "ok", "pass": true}]}))\n'
        '    quit()\n',
        encoding="utf-8")
    ws = tmp_path / "ws"; ws.mkdir()
    (ws / "project.godot").write_text("config_version=5\n", encoding="utf-8")
    tc = Testcase("t", "behavior_logic", "ref", "task", "godot_scenetree",
                  "verifier.gd", "checkpoints", tc_dir)
    result = GodotSceneTreeVerifier().verify(tc, ws)
    assert result.status == "pass"


def test_verifier_passes_quit_after(tmp_path, monkeypatch):
    # Every verifier godot subprocess must carry --quit-after so a crashed
    # verifier (e.g. load() == null) is bounded to a few frames instead of
    # hanging the booted main scene until the wall-clock timeout.
    import aigamedevbench.verifiers.godot_runtime as gr

    monkeypatch.setattr(gr, "resolve_godot_binary", lambda _: "/usr/bin/godot")
    captured = {}

    class _Proc:
        returncode = 0
        stdout = '{"assertions": [{"name": "ok", "pass": true}]}'
        stderr = ""

    def _fake_run(argv, *a, **k):
        captured["argv"] = argv
        return _Proc()

    monkeypatch.setattr(gr.subprocess, "run", _fake_run)
    tc_dir = tmp_path / "tc"; tc_dir.mkdir()
    (tc_dir / "verifier.gd").write_text("extends SceneTree\n", encoding="utf-8")
    ws = tmp_path / "ws"; ws.mkdir()
    tc = Testcase("t", "behavior_logic", "ref", "task", "godot_scenetree",
                  "verifier.gd", "checkpoints", tc_dir)
    result = GodotSceneTreeVerifier().verify(tc, ws)
    assert result.status == "pass"
    argv = captured["argv"]
    assert "--quit-after" in argv
    assert argv[argv.index("--quit-after") + 1] == str(gr._QUIT_AFTER_FRAMES)


def test_verifier_resolves_msys_path(tmp_path, monkeypatch):
    # An MSYS /d/... binary that which() can't resolve directly must still run
    # the verifier via its native d:/... form, not error as "not found".
    import aigamedevbench.verifiers.godot_runtime as gr
    from aigamedevbench import godot_bin

    def fake_which(b):
        return r"D:\Godot\godot.exe" if b == "d:/Godot/godot/bin/godot" else None

    monkeypatch.setattr(godot_bin.shutil, "which", fake_which)
    captured = {}

    class _Proc:
        returncode = 0
        stdout = '{"assertions": [{"name": "ok", "pass": true}]}'
        stderr = ""

    def _fake_run(argv, *a, **k):
        captured["argv"] = argv
        return _Proc()

    monkeypatch.setattr(gr.subprocess, "run", _fake_run)
    tc_dir = tmp_path / "tc"; tc_dir.mkdir()
    (tc_dir / "verifier.gd").write_text("extends SceneTree\n", encoding="utf-8")
    ws = tmp_path / "ws"; ws.mkdir()
    tc = Testcase("t", "behavior_logic", "ref", "task", "godot_scenetree",
                  "verifier.gd", "checkpoints", tc_dir)
    result = GodotSceneTreeVerifier().verify(tc, ws, godot_binary="/d/Godot/godot/bin/godot")
    assert result.status == "pass"
    assert captured["argv"][0] == r"D:\Godot\godot.exe"


def test_interaction_routing_registered():
    from aigamedevbench.verifiers.base import get_verifier
    from aigamedevbench.verifiers import godot_runtime  # noqa: F401
    v = get_verifier("interaction_routing")
    assert v is not None
