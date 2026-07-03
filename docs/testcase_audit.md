# Testcase Audit — 2026-06-29

Health audit of all 17 testcases in `testcases/`. The benchmark's two hard
invariants are: **noop → 0.00** (doing nothing scores zero) and **patch(fix.diff)
→ 1.00** (the golden fix scores full). A testcase that violates either is not a
clean discriminator.

## Method

- Folder-type (`gdb-task_*`, `bench-0001`): ran `--driver noop` and
  `--driver patch --patch fix.diff` from the repo root with `--godot-binary`.
- Git-type (`survey-*`): ran `--driver noop` from inside each case's
  `source_repo`. The survey verifier scores by "made a relevant change AND did
  not reproduce bad.diff AND passes L0/L1", so `noop` is expected to fail; there
  is no `fix.diff` to replay (they carry `good.diff`/`bad.diff` instead).

## Results — folder / py_config testcases

| testcase | noop | patch | verdict |
|---|---|---|---|
| bench-0001-attack-buff | 0.00* | 0.00* | **BROKEN** — template, not a real testcase |
| gdb-task_0002 | 0.00 ✓ | 1.00 ✓ | healthy |
| gdb-task_0007 | **0.09** ✗ | 1.00 ✓ | leaky baseline |
| gdb-task_0012 | 0.00 ✓ | 1.00 ✓ | healthy (noop blocked at L0 gate) |
| gdb-task_0013 | 0.00 ✓ | 1.00 ✓ | healthy |
| gdb-task_0025 | 0.00 ✓ | 1.00 ✓ | healthy |
| gdb-task_0027 | **0.10** ✗ | 1.00 ✓ | leaky baseline |
| gdb-task_0051 | **0.20** ✗ | 1.00 ✓ | leaky baseline |
| gdb-task_0052 | **0.23** ✗ | 1.00 ✓ | leaky baseline |
| gdb-task_0103 | **0.21** ✗ | 1.00 ✓ | leaky baseline |
| gdb-task_0281 | **0.21** ✗ | 1.00 ✓ | leaky baseline |

`*` bench-0001 is git-type with `baseline_ref = "REPLACE_WITH_BASELINE_COMMIT_SHA"`,
so the runner can't check out a starting commit and the verifier errors on both
noop and patch. It is a demo/template scaffold, never a runnable case.

### The "leaky baseline" pattern (6 of 10 gdb tasks)

All patches score 1.00 (the golden fix is correct). The problem is on the noop
side: the baseline project already satisfies some checkpoints, so doing nothing
scores partial. Example — `gdb-task_0052` (noop = 0.23):

```
[PASS] player_scene_loads      <- baseline already has Player.tscn
[PASS] player_instances        <- baseline already instances it
[PASS] has_physics_process     <- baseline already has _physics_process
[FAIL] friction_accel_exported <- the ACTUAL task starts here
[FAIL] friction_default ... (10 more task-specific checks)
```

3 of 13 checkpoints are **setup/scaffolding assertions** that any starting state
passes. They are not task-discriminating, but in `checkpoints` scoring mode they
still contribute to the score. This is exactly the failure mode warned about in
`testcases/README.md` (the "noop 非 0" note).

**Fix options (per leaky case):**
1. **Gate** — make setup checkpoints contribute 0 unless ≥1 discriminating
   checkpoint passes (cleanest; preserves the verifier's structure).
2. **Reweight** — move to `weighted` scoring, weight setup checks at 0.
3. **Trim** — delete the pure-setup assertions from `verifier.gd` so only
   task-relevant checkpoints score (simplest, what gdb-task_0002 already did).

Whichever is chosen, the acceptance test is unchanged: re-run noop and confirm
0.00.

## Results — git / survey_bad_case testcases

| testcase | source_repo | repo present | noop | oracle breadth | verdict |
|---|---|---|---|---|---|
| survey-two-step-signal-oracle | C:\tmp\godot_demo_survey_badcase | yes | fail ✓ | 3 files | **good** (hand-authored) |
| survey-codex_…624e21 | C:\…\Codes\godot_demo | yes | fail ✓ | 10 files | ok |
| survey-unknown_2026-06-25_000 | C:\…\Codes\godot_demo | yes | fail ✓ | 3 files | ok |
| survey-history_2026-06-10_2f271c6_000 | C:\…\Documents\test | yes | fail ✓ | **94 files** | **weak oracle** |
| survey-history_2026-06-12_445a385_005 | C:\…\Documents\test | yes | fail ✓ | **94 files** | **weak oracle** |
| survey-history_2026-06-15_1781fe0_010 | C:\…\Documents\test | yes | fail ✓ | **94 files** | **weak oracle** |

All survey cases correctly fail noop. Two structural problems:

1. **Portability** — every survey case hard-codes an absolute Windows
   `source_repo` path and must be run from inside that repo. None are
   self-contained. On any other machine, all six are unrunnable. The three
   `survey-history_*` additionally share one repo (`Documents\test`) that has
   since been reused for unrelated work — fragile.
2. **Over-broad auto-mined oracle** — the `survey-history_*` cases were exported
   automatically and their `must_change_one_of` lists ~94 files (every path in
   the commit range, including `.codex/skills/*`, `README.md`, and mojibake'd
   filenames). "Change any 1 of 94 files" is a weak discriminator: almost any
   edit passes the `changed_relevant_file` check. Contrast the hand-authored
   `survey-two-step-signal-oracle` (3 tightly-scoped files).

## Summary of issues

| # | severity | issue | affected |
|---|---|---|---|
| 1 | high | template scaffold counted as a testcase, errors on run | bench-0001 |
| 2 | high | leaky baseline: noop scores partial | gdb-task_0007/0027/0051/0052/0103/0281 |
| 3 | high | non-portable: hard-coded abs path, must run in-repo | all survey-* |
| 4 | med | over-broad auto-mined oracle (~94 files) | survey-history_* (3) |
| 5 | low | category skew: 10/17 are behavior_logic | suite-wide |
| 6 | low | no machine-readable suite index / health snapshot | suite-wide |

## Next actions

- Issue 1 → move bench-0001 to a `templates/` dir or mark non-discoverable.
- Issue 2 → apply the gate/trim fix to the 6 leaky verifiers; re-assert noop=0.
- Issue 3 → document required repos + commits; longer term, snapshot each survey
  baseline into a self-contained `baseline/` folder (convert git→folder).
- Issue 4 → tighten survey-history oracles to the handful of files the golden
  resolution actually touched (derivable from `good_ref`).
- Issue 5/6 → README index table + a `scripts/audit_testcases.py` that emits this
  table automatically (the collection-methodology prototype below).
