"""Classify each survey testcase by ORACLE STRENGTH (read-only, prints JSON).

Weak oracle signals (bad for a robust benchmark):
  - bad.diff missing/empty  -> "does_not_reproduce_bad_diff" auto-passes
  - baseline_ref == bad_ref  -> no independent bad state was captured
  - original_l0_pass/l1_pass both null -> no runtime regression assertion
Strong oracle signals:
  - non-empty bad.diff AND baseline_ref != bad_ref
  - original_l0_pass == False or original_l1_pass == False (runtime oracle)
"""
import glob
import json
import re
import sys
import tomllib
from collections import Counter

root = sys.argv[1] if len(sys.argv) > 1 else 'testcases'

rows = []
for toml_path in sorted(glob.glob(f'{root}/*/testcase.toml')):
    case_dir = re.split(r'[\\/]', toml_path)[:-1]
    case = case_dir[-1]
    d = '/'.join(case_dir)
    with open(toml_path, 'rb') as f:
        tc = tomllib.load(f)
    vtype = tc.get('verifier', {}).get('type', '?')
    if vtype != 'survey_bad_case':
        continue

    spec_path = f'{d}/survey_bad_case.json'
    bad_diff_path = f'{d}/bad.diff'

    # bad.diff non-empty?
    bad_diff_bytes = 0
    try:
        with open(bad_diff_path, encoding='utf-8', errors='replace') as f:
            bad_diff_bytes = len(f.read().strip())
    except FileNotFoundError:
        bad_diff_bytes = -1  # missing

    baseline_ref = bad_ref = good_ref = None
    l0 = l1 = None
    root_cause = ''
    good_changed = []
    try:
        with open(spec_path, encoding='utf-8') as f:
            spec = json.load(f)
        baseline_ref = spec.get('baseline_ref')
        bad_ref = spec.get('bad_ref')
        good_ref = spec.get('good_ref')
        exp = spec.get('expected', {})
        l0 = exp.get('original_l0_pass')
        l1 = exp.get('original_l1_pass')
        good_changed = spec.get('hidden_oracle', {}).get('good_changed_files', [])
        sess = spec.get('bench_record', {}).get('survey_session', {})
        root_cause = sess.get('tag', {}).get('root_cause', '')
    except FileNotFoundError:
        pass

    has_bad_diff = bad_diff_bytes > 0
    baseline_eq_bad = (baseline_ref is not None and baseline_ref == bad_ref)
    has_runtime_oracle = (l0 is False) or (l1 is False)
    good_differs = (good_ref is not None and good_ref != baseline_ref)

    # strength score
    if has_runtime_oracle and has_bad_diff:
        strength = 'strong'
    elif has_bad_diff and not baseline_eq_bad:
        strength = 'medium'
    else:
        strength = 'weak'

    rows.append({
        'case': case,
        'bad_diff_bytes': bad_diff_bytes,
        'has_bad_diff': has_bad_diff,
        'baseline_eq_bad': baseline_eq_bad,
        'has_runtime_oracle': has_runtime_oracle,
        'good_differs_from_baseline': good_differs,
        'good_changed_files': good_changed,
        'root_cause': root_cause,
        'strength': strength,
    })

summary = Counter(r['strength'] for r in rows)
print(json.dumps({
    'root': root,
    'survey_total': len(rows),
    'strength_summary': dict(summary),
    'weak_reasons': {
        'missing_bad_diff': sum(1 for r in rows if r['bad_diff_bytes'] == -1),
        'empty_bad_diff': sum(1 for r in rows if r['bad_diff_bytes'] == 0),
        'baseline_eq_bad_ref': sum(1 for r in rows if r['baseline_eq_bad']),
        'no_runtime_oracle': sum(1 for r in rows if not r['has_runtime_oracle']),
    },
    'rows': rows,
}, ensure_ascii=False, indent=2))
