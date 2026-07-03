"""Extract survey case metadata for diversity selection (read-only, prints TSV)."""
import glob
import re
import tomllib

rows = []
for p in sorted(glob.glob('testcases/survey-*/testcase.toml')):
    case = p.split('/')[1] if '/' in p else p.split('\\')[1]
    with open(p, 'rb') as f:
        data = tomllib.load(f)
    tc = data.get('testcase', {})
    prov = data.get('provenance', {})
    repo = tc.get('source_repo', '')
    repo_name = re.split(r'[\\/]', repo.rstrip('\\/'))[-1] if repo else ''
    task = tc.get('task', '')
    # extract file list from the neutral task
    m = re.search(r'behave correctly:\s*(.*?)\.\s*$', task, re.DOTALL)
    files = m.group(1).strip() if m else ''
    # year from case id
    ym = re.search(r'_(\d{4})-(\d{2})-', case)
    year = ym.group(1) if ym else ''
    bad_type = prov.get('bad_case_type', '')
    print('\t'.join([case, repo_name, year, bad_type, files]))
