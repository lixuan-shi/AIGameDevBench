from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from aigamedevbench.testcase import CATEGORIES


DEFAULT_VERIFIER = "godot_scene_assert"
DEFAULT_SCORING = "checkpoints"


@dataclass(frozen=True)
class ScaffoldResult:
    testcase_dir: Path
    created_files: list[Path]


def _validate_id(testcase_id: str) -> None:
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", testcase_id):
        raise ValueError(
            "testcase id must use lowercase letters, digits, '-' or '_' and "
            "start with a letter or digit"
        )


def _manifest(testcase_id: str, category: str, task: str,
              verifier_type: str, verifier_entry: str,
              scoring_mode: str, source_repo: str | None) -> str:
    source_repo_line = f'source_repo = "{source_repo}"\n' if source_repo else ""
    return f'''[testcase]
id = "{testcase_id}"
category = "{category}"
source_kind = "folder"
{source_repo_line}task = """
{task}
"""

[verifier]
type = "{verifier_type}"
entry = "{verifier_entry}"

[scoring]
mode = "{scoring_mode}"

[provenance]
author = "TODO"
created = "TODO: YYYY-MM-DD"
notes = "TODO: why this case is representative and what failure it discriminates"
'''


def _verifier_scene() -> str:
    return '''[gd_scene load_steps=3 format=3]

[ext_resource type="Script" path="res://__VERIFIER_GD__" id="1_verifier"]
[ext_resource type="PackedScene" path="res://scenes/main.tscn" id="2_main"]

[node name="TestRunner" type="Node"]
script = ExtResource("1_verifier")

[node name="Main" parent="." instance=ExtResource("2_main")]
'''


def _verifier_gd(testcase_id: str) -> str:
    return f'''extends Node

var checks := []


func _ready() -> void:
\tcall_deferred("run_validation")


func _record(name: String, condition: bool, detail: String, expected = null, actual = null) -> void:
\tchecks.append({{"name": name, "pass": condition, "detail": detail, "expected": expected, "actual": actual}})


func _emit() -> void:
\tprint(JSON.stringify({{"assertions": checks}}))
\tget_tree().quit()


func run_validation() -> void:
\t# TODO({testcase_id}): replace this with task-specific assertions.
\t# Keep setup checks out of scoring unless they prove the requested behavior.
\tvar main_node := get_node_or_null("Main")
\t_record("main_scene_loads", main_node != null, "Main scene should load", "Main", "null" if main_node == null else main_node.name)
\t_emit()
'''


def scaffold_folder_testcase(testcases_dir: Path, testcase_id: str,
                             category: str = "behavior_logic",
                             task: str = "TODO: describe the requested game-dev change",
                             source_project: Path | None = None,
                             source_repo: str | None = None,
                             force: bool = False) -> ScaffoldResult:
    _validate_id(testcase_id)
    if category not in CATEGORIES:
        raise ValueError(f"invalid category '{category}' (allowed: {sorted(CATEGORIES)})")

    tc_dir = testcases_dir / testcase_id
    if tc_dir.exists():
        if not force:
            raise FileExistsError(f"testcase already exists: {tc_dir}")
        if not tc_dir.is_dir():
            raise FileExistsError(f"path exists and is not a directory: {tc_dir}")
    tc_dir.mkdir(parents=True, exist_ok=True)

    baseline = tc_dir / "baseline"
    created: list[Path] = []
    if source_project is not None:
        if not source_project.is_dir():
            raise FileNotFoundError(f"source project not found: {source_project}")
        ignore = shutil.ignore_patterns(
            ".git", ".godot", ".import", "export_presets.cfg", "*.tmp", "*.log")
        if baseline.exists():
            if not force:
                raise FileExistsError(f"baseline already exists: {baseline}")
            shutil.rmtree(baseline)
        shutil.copytree(source_project, baseline, ignore=ignore)
        created.append(baseline)
    else:
        baseline.mkdir(exist_ok=True)
        placeholder = baseline / ".gitkeep"
        if force or not placeholder.exists():
            placeholder.write_text("", encoding="utf-8")
            created.append(placeholder)

    files = {
        "testcase.toml": _manifest(
            testcase_id, category, task, DEFAULT_VERIFIER, "verifier_scene.tscn",
            DEFAULT_SCORING, source_repo),
        "verifier_scene.tscn": _verifier_scene(),
        "verifier.gd": _verifier_gd(testcase_id),
    }
    for rel, text in files.items():
        path = tc_dir / rel
        if path.exists() and not force:
            raise FileExistsError(f"file already exists: {path}")
        path.write_text(text, encoding="utf-8")
        created.append(path)

    return ScaffoldResult(tc_dir, created)
