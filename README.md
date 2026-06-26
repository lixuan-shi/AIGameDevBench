# AIGameDevBench

A SWE-bench-style **controlled benchmark** for evaluating how well AI coding
harnesses do **Godot game development**.

Each testcase = (source game repo @ a baseline commit) + (a task) + (a frozen
golden verifier). A harness's change is scored by an automated verifier. The
contract: **doing nothing must score 0; the correct change scores 1.**

## Install

```bash
git clone https://github.com/wz306097/AIGameDevBench.git
cd AIGameDevBench
python -m pip install -e ".[dev]"
```

Python ≥ 3.10. The pure-Python verifiers need no Godot. The runtime verifiers
(`godot_scenetree` / `visual_static` / `interaction_routing`) need a `godot`
binary on PATH (pass `--godot-binary` to point elsewhere).

## How a benchmark run works

```
runner:
  prepare isolated workspace            # see "starting state" below
  driver.run(task, workspace)           # noop | patch | (your AI harness)
  godot --import (folder-type)          # build the resource cache so scenes load
  L0/L1 gate                            # scene loads? no broken refs? else score 0
  inject golden verifier -> score       # deleted after scoring (anti-gaming)
```

Two starting-state shapes, set per testcase by `source_kind`:

| `source_kind` | starting state | where you run it |
|---|---|---|
| `folder` (the imported `gdb-task_*`) | the testcase's self-contained `baseline/` dir, copied to a temp dir + `git init` | **any directory** |
| `git` | a commit in the source game repo, checked out via `git worktree` | **inside that game repo** |

So folder-type testcases are self-contained and run anywhere; only git-type
testcases must be run from inside their target game repo.

## Quick start (a self-contained testcase)

`gdb-task_0002` is a folder-type testcase, so it runs from anywhere with no
setup. It needs `godot` on PATH (it boots a scene to score).

```bash
TCDIR=/path/to/AIGameDevBench/testcases

aigdbench list --testcases-dir "$TCDIR"

# baseline check: doing nothing must score 0
aigdbench run --testcases-dir "$TCDIR" --testcase gdb-task_0002 --driver noop

# replay the known-good fix: must score 1
aigdbench run --testcases-dir "$TCDIR" --testcase gdb-task_0002 \
  --driver patch --patch "$TCDIR/gdb-task_0002/fix.diff"
```

Expected:

| driver | status | score |
|---|---|---|
| noop | fail | 0.00 |
| patch (fix.diff) | pass | 1.00 |

## Evaluating a real AI harness

Use `--driver command` to run any CLI harness automatically. The driver writes
the testcase `task` to `workspace/TASK.md`, substitutes placeholders into your
command template, runs it inside the isolated workspace, and scores whatever it
changed. Placeholders: `{task}` (the task text as one argument), `{task_file}`
(path to `TASK.md`), `{workspace}` (the workspace dir).

```bash
aigdbench run --testcases-dir ./testcases \
  --driver command \
  --harness-cmd 'claude -p {task} --dangerously-skip-permissions' \
  --harness my-claude-code \
  --timeout 900 \
  --godot-binary /path/to/godot \
  --log-dir ./harness-logs \
  --workspace-root ./bench-workspaces \
  --report ./report.json
```

**The harness must run fully autonomously.** `--driver command` runs the harness
with no TTY and stdin closed, so any interactive prompt has no way to be
answered. A harness that pauses for edit approval will block until it is aborted.
Pass whatever flag puts your harness in unattended/auto-approve mode:

| harness | autonomous flag |
|---|---|
| Claude Code | `claude -p {task} --dangerously-skip-permissions` (or `--permission-mode bypassPermissions`) |
| Codex | `codex exec --full-auto {task}` (or `-a never`) |

The harness's output is **streamed live to the screen** (prefixed with the
testcase id) so a stuck prompt is visible the instant it appears — disable with
`--no-stream`. Hang protection: the overall `--timeout` (set it generously —
large multi-file tasks legitimately take several minutes) and an approval-prompt
detector that recognises "waiting on your permission approval" and similar and
aborts immediately with a hint. On any failure (timeout, approval-block, or
non-zero exit) the log tail is printed to the screen, the testcase scores 0, and
the batch continues.

> **`--stall-timeout` is off by default.** It aborts a harness that produces no
> output for N seconds — but `claude -p` (and most non-streaming harnesses) print
> nothing until they finish, so "no output" means "still working", and a stall
> guard would kill long-but-healthy tasks. Only enable it for harnesses that
> stream progress incrementally. Use `--timeout` as the real ceiling instead.

Full output also goes to `--log-dir`; `--report` writes a JSON summary
(per-testcase score, status, wall_time, exit_code, stalled/blocked flags, log
path, and overall mean).

**`--workspace-root`:** by default each testcase's workspace is created under the
OS temp dir. If your harness restricts which directories it will edit, point
`--workspace-root` at a directory it trusts (e.g. one inside your project). Note
this controls *where* the workspace is — it does not replace the autonomous-mode
flag above.

The manual loop still works if you prefer it: complete the task by hand, capture
`git diff > ai.diff`, and score with `aigdbench run --driver patch --patch ai.diff`.

## Viewing & comparing runs (`aigdbench serve`)

Every `--report FILE` is a standalone JSON file. To compare runs side by side
instead of reading raw JSON, start the local dashboard (pure stdlib, fully
offline, no extra deps):

```bash
aigdbench serve --reports-dir . --testcases-dir ./testcases
# → opens http://127.0.0.1:8000
```

It scans `--reports-dir` for `report*.json` on **every request**, so re-running a
benchmark and refreshing the page shows the new run immediately. What you get:

- **Reports** tab — one run per report file (labelled by `harness` + file mtime):
  mean-score bars, a per-testcase × per-run score matrix, category and
  timing/stability aggregates. **Click any matrix cell** to drill into that
  run's per-check `expected` vs `actual`, the harness log tail, and (for survey
  rows) the AI activity record.
- **Testcases** tab — the testcase library from `--testcases-dir`: task text,
  verifier type, scoring mode, and file listing for each `gdb-task_*`.

`--testcases-dir` defaults to `./testcases` if it exists; `--port` / `--host` /
`--no-open-browser` are available.

## Quick command cheat-sheet

```bash
# list testcases
aigdbench list --testcases-dir ./testcases

# baseline (must score 0) then golden fix (must score 1)
aigdbench run --testcases-dir ./testcases --testcase gdb-task_0002 --driver noop
aigdbench run --testcases-dir ./testcases --testcase gdb-task_0002 \
  --driver patch --patch ./testcases/gdb-task_0002/fix.diff

# evaluate a real harness over the whole suite, writing a report
aigdbench run --testcases-dir ./testcases --driver command \
  --harness-cmd 'claude -p {task} --dangerously-skip-permissions' \
  --harness my-claude-code --timeout 900 \
  --log-dir ./harness-logs --workspace-root ./bench-workspaces \
  --report ./report.json

# visualize & compare all report*.json
aigdbench serve --reports-dir . --testcases-dir ./testcases
```

## Survey bad cases (from the sibling `survey` tool)

`survey_bad_cases.json` is **not** produced by `aigdbench`. It comes from the
sibling [AIGameDevCollecter](../AIGameDevCollecter) `survey` CLI, which mines a
real game repo's git history for problematic AI sessions (L0/L1 failures, high
human-intervention ratio, many rounds to resolution) and exports them in
AIGameDevBench's report format. These rows are scored by survey's rule engine —
they have no `testcase.toml`/baseline/verifier and **cannot** be run by
`aigdbench run`; they only appear in the dashboard's Reports matrix.

Produce the file in the surveyed repo, then view it here:

```bash
# in the surveyed game repo (e.g. ../godot_demo, already `survey init`-ed)
cd ../godot_demo
survey collect --since 30d                 # mine sessions, auto-flag bad cases
survey report --format md                   # (optional) see what was flagged
survey tag <session_id> --type B1           # (optional) classify A1–C3
survey export-bench \
  -o ../AIGameDevBench/survey_bad_cases.json \
  --harness survey-godot-demo               # writes the report (auto-imports transcripts)

# back here: it shows up as the "survey-godot-demo" run in the matrix
cd ../AIGameDevBench
aigdbench serve --reports-dir . --testcases-dir ./testcases
```

In the dashboard, click a survey cell to see its checks (`bad_case_detected`,
`human_intervention_ratio`, `rounds_to_resolution` with expected vs actual) plus
the captured AI turns (agent input/output and tool calls).

## Testcase format

See [`testcases/README.md`](testcases/README.md) for the manifest schema, the
five capability categories, and all six verifier types.

## Verifier types

| type | needs Godot | reads | what it checks |
|---|---|---|---|
| `py_config` | no | `expected.json` | numeric/config fields by alias; anti-copy guard |
| `py_tscn_diff` | no | `expected_delta.json` + `baseline/` | scene node/prop delta, side-effect free |
| `py_gdscript_ast` | no | `arch_rules.json` | import/extends/path constraints, weighted |
| `godot_scenetree` | yes | `verifier.gd` | runtime assertions via headless SceneTree |
| `visual_static` | yes | `verifier.gd` | structured layout assertions |
| `interaction_routing` | yes | `verifier.gd` | click routing / focus order |

## Tests

```bash
pytest
```
