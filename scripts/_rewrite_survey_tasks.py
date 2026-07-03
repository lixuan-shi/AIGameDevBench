"""Rewrite survey testcase.toml `task` fields to strip leakage.

Leaky template (three parts, all leaking):
  Complete the original Survey bad-case task touching the relevant files: <FILES>.
  Original failure notes: fix commit <hash>: <subject>
  \n\n Regression target: avoid the original Survey bad case (A1): fix commit <hash>: <subject>

We keep ONLY the file list and replace with a neutral instruction. Everything
else (verifier/scoring/provenance, incl. the original commit info) is untouched;
the commit metadata still lives in provenance + bad.diff/survey_bad_case.json.

Usage:
  python scripts/_rewrite_survey_tasks.py --dry-run   # preview, no writes
  python scripts/_rewrite_survey_tasks.py --apply      # write changes
"""
import glob
import re
import sys

# Matches:  ...touching the relevant files: <FILES>. Original failure notes...
# Capture the file list between "relevant files:" and the ". Original failure" boundary.
FILES_RE = re.compile(
    r'touching the relevant files:\s*(?P<files>.*?)\.\s*Original failure notes:',
    re.DOTALL,
)

# The whole task line in the toml (single-line string form: task = "...").
TASK_LINE_RE = re.compile(r'^(?P<prefix>task\s*=\s*")(?P<body>.*)(?P<suffix>")\s*$')

NEW_TEMPLATE = (
    'Investigate and fix the defect in the following file(s), '
    'making the affected feature behave correctly: {files}.'
)


def rewrite_task_body(body: str):
    """Return new task body, or None if this doesn't look like the leaky template."""
    m = FILES_RE.search(body)
    if not m:
        return None
    files = m.group('files').strip()
    if not files:
        return None
    return NEW_TEMPLATE.format(files=files)


def process(path, apply):
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    changed = False
    for i, line in enumerate(lines):
        m = TASK_LINE_RE.match(line.rstrip('\n'))
        if not m:
            continue
        new_body = rewrite_task_body(m.group('body'))
        if new_body is None:
            return ('skip', path, m.group('body'), None)
        new_line = f'{m.group("prefix")}{new_body}{m.group("suffix")}\n'
        if new_line != line:
            lines[i] = new_line
            changed = True
            old_body = m.group('body')
        break
    else:
        return ('no-task', path, None, None)

    if changed and apply:
        with open(path, 'w', encoding='utf-8', newline='') as f:
            f.writelines(lines)
    return ('changed' if changed else 'nochange', path, old_body if changed else None,
            new_body if changed else None)


def main():
    apply = '--apply' in sys.argv
    dry = '--dry-run' in sys.argv or not apply

    files = sorted(set(
        glob.glob('testcases/survey-fixcommit_*/testcase.toml')
        + glob.glob('testcases/survey-history_*/testcase.toml')
    ))

    stats = {'changed': 0, 'skip': 0, 'no-task': 0, 'nochange': 0}
    skips = []
    samples = []
    for p in files:
        status, path, old, new = process(p, apply)
        stats[status] += 1
        if status == 'skip':
            skips.append((path, old))
        if status == 'changed' and len(samples) < 3:
            samples.append((path, old, new))

    print(f"total: {len(files)}  |  " + "  ".join(f"{k}={v}" for k, v in stats.items()))
    print(f"mode: {'APPLY (wrote files)' if apply else 'DRY-RUN (no writes)'}\n")

    print("--- sample rewrites ---")
    for path, old, new in samples:
        print(f"\n# {path}")
        print(f"  BEFORE: {old[:220]}")
        print(f"  AFTER : {new[:220]}")

    if skips:
        print(f"\n--- {len(skips)} SKIPPED (task did not match leaky template — left untouched) ---")
        for path, body in skips[:15]:
            print(f"  {path}\n    task: {body[:160]}")


if __name__ == '__main__':
    main()
