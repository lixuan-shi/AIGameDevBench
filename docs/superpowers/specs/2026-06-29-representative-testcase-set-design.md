# Design: A Representative, Trap-Driven Testcase Set

Date: 2026-06-29
Status: approved (design phase)

## Problem

The benchmark suite is badly skewed: of 16 discoverable testcases, **14 are
`behavior_logic`** and the other four capability categories have ≤1 each
(`visual_audio` = 0). It therefore measures almost only "does the runtime
behavior work" and barely tests intent translation, precise editing,
architecture constraints, or visual layout.

Worse, many existing cases are low-information: the stronger harness passes them
cleanly (gdb-task_0013/0051/0052 → 1.0), so they don't discriminate. The cases
that *do* discriminate are the trap-heavy ones (gdb-task_0025 → 0.00/0.06,
gdb-task_0281 → 0.21/0.47, gdb-task_0027 → 0.10/0.90): tasks where a plausible
AI attempt fails in a specific, repeatable way.

## Goal

Author **15 new self-contained testcases** spanning all five categories,
frequency-weighted, where **every case is built around a documented AI failure
mode**. Each must be a clean discriminator (the benchmark's hard invariants):

- **noop → 0.00** (doing nothing scores zero)
- **golden (`fix.diff`) → 1.00** (the correct change scores full)
- tight oracle; portable (folder-type, runs anywhere)

and must pass `aigdbench audit` clean before admission.

## Non-goals

- Not fixing the 6 existing leaky `gdb-task_*` baselines or the 3 over-broad
  `survey-history_*` oracles (separate effort).
- Not building a generator/automation; these are hand-authored.
- Not touching `git`-type survey cases or the runner/verifier engine.

## Design principle: trap-driven cases

A testcase has high information value only where a *plausible* AI attempt fails.
So the unit of design is not "a feature" but **a failure mode**:

1. Pick a high-frequency Godot system (combat stats, inventory, FSM, HUD…).
2. Identify the specific way a lazy/obvious implementation goes **subtly wrong**
   (the trap).
3. Build the minimal baseline + task so the obvious attempt hits the trap.
4. Make the verifier's **discriminating checkpoint** target exactly that trap —
   so the wrong attempt fails it and only the correct change passes.

This is a stronger notion of "hard" than multi-step: difficulty comes from the
trap, not from volume.

## Organizing structure: capability × difficulty, realistic scenarios

The set is a **capability × difficulty matrix** (deliberate coverage + a
discriminating difficulty spread), with each slot filled by a **real,
high-frequency gameplay system** (ecological validity). Frequency weighting:

| category | count | rationale |
|---|---|---|
| behavior_logic | 4 | highest-frequency capability |
| intent_translation | 4 | highest-frequency capability |
| precise_edit | 3 | common, distinct verifier |
| architecture | 2 | rarer but important |
| visual_audio | 2 | currently zero coverage |
| **total** | **15** | |

## The 15 cases

Each row: category / difficulty · system · **the trap (AI failure mode)** ·
discriminating check · verifier. `bad.diff` is added **only where it meaningfully
sharpens the trap** (proving monotonic scoring), not for all.

| # | cat / diff | system | trap (AI failure mode) | discriminating check | verifier | bad.diff |
|---|---|---|---|---|---|---|
| 1 | behavior_logic / easy | ability cooldown timer | resets/ignores delta accumulation → fires every frame | fires only after cooldown elapsed | godot_scene_assert | — |
| 2 | behavior_logic / med | damage → death | no HP clamp at 0; emits `died` on every hit | `died` emits exactly once; HP clamps ≥0 | godot_scene_assert | yes |
| 3 | behavior_logic / med | player FSM (idle/run/jump) | transitions without exit()/enter(); allows illegal jump→jump | guard rejects illegal transition; enter/exit called | godot_scene_assert | — |
| 4 | behavior_logic / hard | pickup → inventory → UI | signal wired but UI never updates; double-counts on re-entry | UI count correct after pickup; no double-add | godot_scene_assert | yes |
| 5 | intent_translation / easy | "elite +20%" stat | writes 50 (copies base) or 70 (adds 20, not 20%) | equals 60; must_differ_from_base | py_config | — |
| 6 | intent_translation / med | loot drop rates | rates don't sum to 1; edits display string not data | weighted rates correct in data file | py_config | — |
| 7 | intent_translation / med | movement tuning | tweaks one constant, misses the coupled one (gravity vs jump) | all related constants consistent | py_config | — |
| 8 | intent_translation / hard | difficulty preset (multi-file) | edits one file, leaves the other stale | every file's field correct; anti-copy | py_config | yes |
| 9 | precise_edit / easy | add collision-layer prop to a node | sets target but flips an unrelated default → side-effect | target prop set; siblings unchanged | py_tscn_diff | — |
| 10 | precise_edit / med | add node + wire one signal | adds node but forgets connection / wrong method | node added AND signal connected to right method | py_tscn_diff | yes |
| 11 | precise_edit / hard | reparent without breaking refs | reparent breaks a NodePath / `$` ref elsewhere | reparented AND all refs still resolve | py_tscn_diff | — |
| 12 | architecture / med | no hardcoded `res://` paths | works but hardcodes the path string | forbid_hardcoded_res_path passes | py_gdscript_ast | — |
| 13 | architecture / hard | component boundary | right extends but imports across forbidden boundary | require_extends AND forbid_import_glob | py_gdscript_ast | — |
| 14 | visual_audio / easy | HUD health-bar anchor | positions by absolute offset; breaks on resize (wrong anchor) | anchors set, not just offsets | visual_static | — |
| 15 | visual_audio / med | panel layout per template | children laid out but wrong order / overlap / visibility | each child positioned + visible per template | visual_static | yes |

`bad.diff` cases (2, 4, 8, 10, 15): the plausible-wrong attempt must score
**strictly between 0 and the golden**, demonstrating the verifier ranks quality.

## Per-case structure (all folder-type)

```
testcases/<id>/
  testcase.toml          # source_kind="folder", category, verifier type, scoring mode
  baseline/              # minimal self-contained Godot project (no .git/.godot)
    project.godot
    <minimal scenes/scripts for this system>
  fix.diff               # golden change: baseline → correct (audited → 1.00)
  bad.diff               # optional: plausible-wrong attempt (>0, <golden)
  # verifier artifacts, by type:
  verifier_scene.tscn + verifier.gd     # godot_scene_assert / visual_static
  expected.json                         # py_config
  expected_delta.json                   # py_tscn_diff (+ baseline scene)
  arch_rules.json                       # py_gdscript_ast
```

The baseline is **deliberately minimal**: it contains only the nodes/scripts the
system needs and is constructed so doing nothing scores 0 (no pre-satisfied
checkpoints — the leaky-baseline failure mode is designed out).

### Verifier discipline (avoid the known failure modes)

- **No setup checkpoints that score.** `scene_loads`, `has_physics_process` etc.
  may gate (fail → overall fail) but must not award points; only trap-targeting
  checkpoints score. (Prevents leaky baselines.)
- **Tight change-set oracles.** `py_tscn_diff` `expected_delta` and any
  `must_change_one_of` cover only the files/nodes the golden touches.
- **fail-fast checkpoint pattern** for `godot_scene_assert`/`visual_static`:
  emit unreached checkpoints as failed so the denominator is stable
  (per `testcases/gdb-task_0013/verifier.gd`).

## Build & acceptance per case

For each of the 15, using existing tooling:

1. `aigdbench scaffold --id <id> --category <c> --task "<t>"` → skeleton.
2. Hand-author `baseline/`, the verifier artifact, `fix.diff` (and `bad.diff`
   where listed).
3. `aigdbench smoke --testcase <id> --godot-binary <godot>` → assert noop=0,
   golden=1 for this one case.
4. For `bad.diff` cases: run `--driver patch --patch bad.diff`, assert
   `0 < score < golden`.

**Suite-level acceptance:** `aigdbench audit --testcases-dir ./testcases
--json docs/testcase_health.json` exits 0 with no flags on all new cases; pytest
stays green; `testcases/README.md` index updated with the 15 rows.

## Risks & mitigations

- **Runtime verifiers need Godot.** 9 of 15 use Godot (behavior_logic +
  visual_audio); 6 are pure-Python. Build/audit the 6 pure-Python cases first
  (no Godot dependency, fastest feedback), then the Godot ones.
- **visual_static is the least-exercised verifier** (0 existing cases). Validate
  its assertion format against `src/aigamedevbench/verifiers/godot_runtime.py`
  early with case 14 before authoring case 15.
- **Trap must be reachable.** If the "obvious wrong" attempt can't actually be
  expressed, the trap is theoretical — the `bad.diff` cases (2,4,8,10,15)
  concretely prove the trap is hittable.

## Ordering

1. Pure-Python, lower-risk: cases 5, 7, 9, 12 (one per their verifier, easy/med).
2. Remaining pure-Python: 6, 8, 10, 11, 13.
3. Godot behavior_logic: 1, 3, 2, 4.
4. Godot visual_audio: 14, then 15.
