"""Copy the 50 selected testcases into testcases_filtered/ (source untouched)."""
import os
import shutil
import time

DST = 'testcases_filtered'
os.makedirs(DST, exist_ok=True)

with open('.filtered_50.txt', encoding='utf-8') as f:
    cases = [ln.strip() for ln in f if ln.strip()]

print(f"copying {len(cases)} cases -> {DST}/")
ok, failed = 0, []
for c in cases:
    src = os.path.join('testcases', c)
    dst = os.path.join(DST, c)
    if os.path.exists(dst):
        shutil.rmtree(dst)
    # retry against transient Defender file locks
    for attempt in range(5):
        try:
            shutil.copytree(src, dst)
            ok += 1
            break
        except Exception as e:
            last = e
            time.sleep(1.0)
    else:
        failed.append((c, str(last)))

print(f"copied ok: {ok}  failed: {len(failed)}")
for c, e in failed:
    print("  FAIL", c, e[:160])
