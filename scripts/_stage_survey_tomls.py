"""One-off helper: stage all survey testcase.toml files as a git rollback baseline.

Windows Defender can transiently lock freshly-written .git/objects entries, so
`git add` on hundreds of files at once may fail with EPERM. We batch + retry.
"""
import glob
import subprocess
import sys
import time

files = sorted(set(
    glob.glob('testcases/survey-fixcommit_*/testcase.toml')
    + glob.glob('testcases/survey-history_*/testcase.toml')
))
print(f"total survey tomls: {len(files)}")

BATCH = 25
failed = []
for i in range(0, len(files), BATCH):
    batch = files[i:i + BATCH]
    for attempt in range(5):
        r = subprocess.run(['git', 'add', '--'] + batch,
                           capture_output=True, text=True)
        if r.returncode == 0:
            break
        time.sleep(1.0)
    else:
        failed += batch
        print(f"batch {i // BATCH} failed: {r.stderr.strip()[:200]}")

print(f"done. permanently failed: {len(failed)}")
for f in failed[:20]:
    print("  FAIL", f)
sys.exit(1 if failed else 0)
