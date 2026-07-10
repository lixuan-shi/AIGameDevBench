# Collecting Better Testcases — Methodology

How AIGameDevBench gets new testcases today, what goes wrong, and a concrete
plan (with a runnable prototype) for collecting better ones.

A testcase is good only if it is a **clean discriminator**: doing nothing scores
0, the correct change scores 1, and the score moves monotonically with quality
in between. Everything below is in service of that property.

---

## 1. The two pipelines we have

### A. Import from GameDevBench (`scripts/import_gamedevbench.py`)
Takes a self-contained Godot tutorial project + its golden test, strips the
answer-leaking files, and rewrites `test.gd` into a checkpoint `verifier.gd`.
Produces the `gdb-task_*` folder-type cases.

- **Strengths:** self-contained (runs anywhere, no external repo), reproducible,
  Godot-verified, derived from real tutorial gameplay.
- **Weaknesses (confirmed by the audit):** the imported baseline often *already
  satisfies* setup checkpoints, so `noop` scores partial — 6 of 10 imported
  cases leak (0.09–0.23). The importer's default single-checkpoint fallback
  doesn't separate "scaffolding present" from "task done".

### B. Mine real sessions with Survey (`AIGameDevCollecter`)
Scans a real game repo's git history + AI transcripts for bad sessions (L0/L1
crashes, high human-intervention ratio, many resolution rounds) and exports them
as `survey_bad_case` git-type cases.

- **Strengths:** real failures from real harness usage; captures categories pure
  synthetic tasks miss (multi-turn, human rescue, regression).
- **Weaknesses (confirmed):** non-portable (hard-coded absolute `source_repo`,
  must run in-repo); the auto-mined oracle is over-broad — `survey-history_*`
  accept "change any 1 of **94** files", which barely discriminates. The
  hand-authored `survey-two-step-signal-oracle` (3-file oracle) shows the bar.

---

## 2. The four quality failures, and how to design them out

| failure | symptom in our suite | root cause | design fix |
|---|---|---|---|
| **Leaky baseline** | gdb noop = 0.09–0.23 | setup checkpoints score even on noop | separate *setup* gate-checks (pass/fail, 0 weight) from *task* checks (the only scored ones) |
| **Over-broad oracle** | survey-history 94-file `must_change_one_of` | exported every file in the commit range | derive the oracle from the **golden diff only** (`good_ref`), not the whole range |
| **Non-portable** | all survey cases pin abs paths | git-type carries no baseline | snapshot the baseline commit into a self-contained `baseline/` folder (git→folder) |
| **Answer leakage** | (importer already strips `*.md`+`task_config.json`) | tutorial ships the solution | keep stripping; add a check that the task text doesn't contain the literal answer |

The unifying principle: **the oracle must measure the delta the task asks for,
not the state the project happens to start in.** A leaky baseline measures start
state; an over-broad oracle measures "any change at all". Both dilute signal.

---

## 3. The collection contract (admission criteria)

Every candidate testcase — however sourced — must pass this gate before it joins
the suite. This is enforceable and is exactly what `scripts/audit_testcases.py`
checks:

1. **noop → 0.00.** If not, the baseline leaks; trim/gate the non-discriminating
   checkpoints (or remove the pre-satisfied state from the baseline).
2. **golden → 1.00.** `fix.diff` (folder) or `good.diff` (survey) reaches full
   score. If not, the verifier is mis-specified.
3. **Monotonic middle (recommended).** A partial/known-buggy diff (`bad.diff`)
   scores strictly between 0 and 1, and strictly below the golden. This proves
   the verifier ranks quality, not just pass/fail.
4. **Tight oracle.** For change-set oracles, `must_change_one_of` ⊆ the files the
   golden diff actually touches. Flag anything over ~20 files.
5. **Portable or documented.** Prefer folder-type (self-contained `baseline/`).
   If git-type, the required `source_repo` + `baseline_ref` must exist and be
   recorded; abs paths are a portability flag.
6. **Category balance.** Tag the real category; the suite is currently 10/17
   `behavior_logic` — actively seek `intent_translation`, `precise_edit`,
   `architecture`, `visual_audio`.

A candidate that fails 1–4 is not "a hard testcase" — it is a **broken
measurement** and must be fixed or rejected.

---

## 4. Sourcing strategy — where better cases come from

Ranked by signal-per-effort for this benchmark:

1. **Mine real harness failures (Survey), then *tighten*.** Highest ecological
   validity. The fix is mechanical: scope the oracle to `good_ref`'s diff and
   snapshot the baseline to a folder. Turn the 3 leaky `survey-history_*` into
   tight self-contained cases first — they're already real, just loosely
   specified.
2. **Mutation / regression seeding.** Take a *working* feature at a commit,
   programmatically revert the key change to create the baseline, and the
   original commit becomes the golden diff. Guarantees noop→0 and golden→1 by
   construction, and the oracle is exactly the reverted hunk. Cheap, clean,
   scalable.
3. **Import more GameDevBench tasks — but split checkpoints.** Keep importing,
   but require the importer to mark setup vs task checkpoints so noop stays 0.
4. **Differential cases from this suite's own runs.** Where harnesses disagree
   (one passes, one fails) are the most *informative* cases. The existing reports
   (`report*.json`) already locate them: gdb-task_0025 (claude 0.06), gdb-task_0281
   (0.47) are where the signal is — harvest near-misses into focused sub-tasks.

---

## 5. Concrete next steps

- **Now (mechanical, high value):**
  - Run `scripts/audit_testcases.py --json health.json` in CI; fail the build on
    any unhealthy case. This freezes the contract above.
  - Fix the 6 leaky gdb verifiers (gate/trim setup checkpoints) → re-audit.
  - Tighten the 3 `survey-history_*` oracles to their `good_ref` diff.
- **Next (tooling):**
  - Add a `--scope-oracle-from-good-ref` mode to Survey's exporter so newly mined
    cases ship tight oracles by default.
  - Add a `snapshot-baseline` step that converts a passing git-type survey case
    into a self-contained folder-type case (portability).
- **Later (scale):**
  - Build the mutation-seeding generator (strategy #2) to mass-produce clean
    regression cases from any healthy game repo's history.

---

## 6. The prototype — `scripts/audit_testcases.py`

A runnable auto-triage tool that enforces §3 (1, 2, 4, 5) across the whole suite
and emits a machine-readable health snapshot. It is the gate every candidate
must clear.

```bash
python scripts/audit_testcases.py \
  --testcases-dir ./testcases \
  --godot-binary /path/to/godot \
  --json health.json
# exit 0 = all healthy; exit 1 = at least one flag (CI-friendly)
```

Sample output on the current suite:

```
testcase                          noop  patch  flags
gdb-task_0013                     0.00   1.00  OK
gdb-task_0052                     0.23   1.00  leaky_baseline(noop=0.23)
survey-two-step-signal-oracle     0.00      -  nonportable_abs_path
```

It flags: `leaky_baseline`, `patch_not_one`, `no_fix_diff`, `overbroad_oracle(N)`,
`nonportable_abs_path`, `repo_missing`, `noop_not_zero`. Pass `--only <id>` to
audit a single case while iterating on a fix.
```
