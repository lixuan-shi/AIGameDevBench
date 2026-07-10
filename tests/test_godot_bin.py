from __future__ import annotations

from aigamedevbench import godot_bin
from aigamedevbench.godot_bin import resolve_godot_binary, _msys_to_native


def test_msys_to_native_converts_drive_path():
    assert _msys_to_native("/d/Godot/godot/bin/godot") == "d:/Godot/godot/bin/godot"


def test_msys_to_native_returns_none_for_non_msys():
    assert _msys_to_native("godot") is None
    assert _msys_to_native("D:/Godot/godot.exe") is None
    # Only a single-letter first segment is an MSYS drive; /usr/... is not.
    assert _msys_to_native("/usr/bin/godot") is None


def test_resolve_returns_which_hit_directly(monkeypatch):
    monkeypatch.setattr(godot_bin.shutil, "which",
                        lambda b: "/resolved/godot" if b == "godot" else None)
    assert resolve_godot_binary("godot") == "/resolved/godot"


def test_resolve_falls_back_to_native_for_msys_path(monkeypatch):
    # which() can't resolve the MSYS form but can resolve the native form;
    # the resolver must retry with the converted path.
    def fake_which(b):
        return r"D:\Godot\godot\bin\godot.EXE" if b == "d:/Godot/godot/bin/godot" else None
    monkeypatch.setattr(godot_bin.shutil, "which", fake_which)
    assert resolve_godot_binary("/d/Godot/godot/bin/godot") == r"D:\Godot\godot\bin\godot.EXE"


def test_resolve_returns_none_when_unresolvable(monkeypatch):
    monkeypatch.setattr(godot_bin.shutil, "which", lambda _: None)
    assert resolve_godot_binary("/d/nope/godot") is None
