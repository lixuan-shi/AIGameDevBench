"""Collect distribution stats for a testcases dir. Prints JSON. Read-only."""
import glob
import json
import re
import sys
import tomllib
from collections import Counter

root = sys.argv[1] if len(sys.argv) > 1 else 'testcases'

cats, verifiers, kinds, scoring, sources, years, repos, badtypes = (
    Counter(), Counter(), Counter(), Counter(), Counter(), Counter(), Counter(), Counter())
n = 0
file_counts = []  # number of touched files per case (where derivable)

for p in sorted(glob.glob(f'{root}/*/testcase.toml')):
    case = re.split(r'[\\/]', p)[-2]
    if case == '_templates':
        continue
    with open(p, 'rb') as f:
        try:
            data = tomllib.load(f)
        except Exception as e:
            print(f"PARSE FAIL {p}: {e}", file=sys.stderr)
            continue
    n += 1
    tc = data.get('testcase', {})
    prov = data.get('provenance', {})
    cats[tc.get('category', '?')] += 1
    verifiers[data.get('verifier', {}).get('type', '?')] += 1
    kinds[tc.get('source_kind', '?')] += 1
    scoring[data.get('scoring', {}).get('mode', '?')] += 1

    # source family from case id prefix
    if case.startswith('survey-fixcommit'):
        fam = 'survey-fixcommit'
    elif case.startswith('survey-history'):
        fam = 'survey-history'
    elif case.startswith('gdb-task'):
        fam = 'gdb-task'
    elif case.startswith('survey-'):
        fam = 'survey-other'
    else:
        fam = 'hand-authored'
    sources[fam] += 1

    if prov.get('bad_case_type'):
        badtypes[prov['bad_case_type']] += 1

    repo = tc.get('source_repo', '')
    if repo and ('scout' in repo or '/' in repo or '\\' in repo):
        rn = re.split(r'[\\/]', repo.rstrip('\\/'))[-1]
        if rn and rn != repo:
            repos[rn] += 1

    ym = re.search(r'_(\d{4})-\d{2}-', case)
    if ym:
        years[ym.group(1)] += 1

    task = tc.get('task', '')
    m = re.search(r'correctly:\s*(.*?)\.\s*$', task, re.DOTALL) or \
        re.search(r'relevant files:\s*(.*?)\.', task, re.DOTALL)
    if m:
        file_counts.append(len([x for x in m.group(1).split(',') if x.strip()]))

out = {
    'root': root,
    'total': n,
    'category': dict(cats.most_common()),
    'verifier_type': dict(verifiers.most_common()),
    'source_kind': dict(kinds.most_common()),
    'scoring_mode': dict(scoring.most_common()),
    'source_family': dict(sources.most_common()),
    'source_repo': dict(repos.most_common()),
    'year': dict(sorted(years.items())),
    'bad_case_type': dict(badtypes.most_common()),
    'touched_files': {
        'cases_with_filelist': len(file_counts),
        'min': min(file_counts) if file_counts else 0,
        'max': max(file_counts) if file_counts else 0,
        'avg': round(sum(file_counts) / len(file_counts), 2) if file_counts else 0,
    },
}
print(json.dumps(out, ensure_ascii=False, indent=2))
