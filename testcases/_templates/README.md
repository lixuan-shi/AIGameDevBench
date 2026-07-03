# _templates

Scaffolds and examples that are **not** runnable testcases. Anything in here is
deliberately excluded from discovery (`discover_testcases` only picks up
top-level dirs that contain a `testcase.toml`, and this directory does not).

- `bench-0001-attack-buff/` — the original demo manifest showing the `py_config`
  shape. Its `baseline_ref` is the literal placeholder
  `REPLACE_WITH_BASELINE_COMMIT_SHA`, so the runner cannot check out a starting
  commit and it errors on both `noop` and `patch`. Kept as a copy-me template for
  authoring a new `py_config` case, not as a benchmark entry.

To turn a template into a real testcase, copy it up into `testcases/`, fill in a
real `baseline_ref` (or convert to `source_kind = "folder"` with a `baseline/`
dir), and confirm it passes `scripts/audit_testcases.py`.
