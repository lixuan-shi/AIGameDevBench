#!/usr/bin/env bash
# compare-and-maybe-release.sh — after a benchmark batch finishes, compare its
# mean score against the agentic-game-development plugin's stored baseline (the
# score the CURRENT release was cut at). If the new run is NOT LOWER than baseline
# (delta >= MIN_DELTA, default 0), bump the plugin version, refresh the baseline,
# and push to main — which triggers release-on-bump.yml to publish a new release.
# Per operator requirement: "benchmark 结果不低于上一版本即打出新版本."
#
# Baseline is stored in TWO places (in-repo authoritative + release asset):
#   * $PLUGIN_REPO/workflow/benchmark-baseline.json   <- source of truth, versioned
#   * uploaded as an asset by release-on-bump.yml on each publish (for provenance)
# This script reads and writes the in-repo file only; the release asset is a copy.
# The baseline records the plugin_commit it was cut at; a run whose plugin HEAD
# matches that commit is NOT re-released (identical content), even if not lower.
#
# Decision (per operator choice): not-lower + plugin changed => push to main =
# FULLY AUTOMATIC release (no PR gate). Guard rails: only writes with
# --auto-release; otherwise it just reports the comparison and what it WOULD do.
#
# Usage:
#   scripts/compare-and-maybe-release.sh \
#     --report results/<delivery>/report.json \
#     --plugin-repo ../agentic-game-development \
#     [--auto-release] [--min-delta 0] [--bump patch|minor|major] [--dry-run]
#
# Options (env in parens):
#   --report FILE     aggregate report.json from run_k8s_matrix.sh   (REPORT, required)
#   --plugin-repo DIR agentic-game-development checkout    (PLUGIN_REPO, default ../agentic-game-development)
#   --baseline FILE   baseline json path (rel to plugin repo)
#                                     (BASELINE_FILE, default workflow/benchmark-baseline.json)
#   --min-delta N     release gate threshold; release when delta >= this value
#                     (MIN_DELTA, default 0 => "not lower than baseline")
#   --bump T          patch|minor|major version bump on release      (BUMP, default patch)
#   --auto-release    actually bump+commit+push main (else report only, no writes)
#   --delivery ID     delivery id, recorded in baseline provenance   (DELIVERY, optional)
#   --dry-run         do everything except git commit/push           (DRY_RUN)
#   -h                help
#
# Exit: 0 always on a clean comparison (released or not). Non-zero only on error
# (missing report, malformed json, git failure).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

REPORT="${REPORT:-}"
PLUGIN_REPO="${PLUGIN_REPO:-$REPO_ROOT/../agentic-game-development}"
BASELINE_FILE="${BASELINE_FILE:-workflow/benchmark-baseline.json}"
MIN_DELTA="${MIN_DELTA:-0}"
BUMP="${BUMP:-patch}"
AUTO_RELEASE=0
DELIVERY="${DELIVERY:-}"
DRY_RUN="${DRY_RUN:-0}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --report) REPORT="$2"; shift 2;;
    --plugin-repo) PLUGIN_REPO="$2"; shift 2;;
    --baseline) BASELINE_FILE="$2"; shift 2;;
    --min-delta) MIN_DELTA="$2"; shift 2;;
    --bump) BUMP="$2"; shift 2;;
    --auto-release) AUTO_RELEASE=1; shift;;
    --delivery) DELIVERY="$2"; shift 2;;
    --dry-run) DRY_RUN=1; shift;;
    -h|--help) sed -n '2,40p' "$0"; exit 0;;
    *) echo "unknown option: $1" >&2; exit 2;;
  esac
done

log() { echo "[compare-release] $*" >&2; }
die() { echo "[compare-release] ERROR: $*" >&2; exit 1; }

[[ -n "$REPORT" && -f "$REPORT" ]] || die "--report FILE not found: ${REPORT:-<unset>}"
[[ -d "$PLUGIN_REPO/.git" ]] || die "--plugin-repo is not a git checkout: $PLUGIN_REPO"
case "$BUMP" in patch|minor|major) ;; *) die "--bump must be patch|minor|major";; esac

CODEX_MANIFEST="plugins/agentic-game-development-superpowers/.codex-plugin/plugin.json"
CLAUDE_MANIFEST="plugins/agentic-game-development-superpowers/.claude-plugin/plugin.json"
BASELINE_ABS="$PLUGIN_REPO/$BASELINE_FILE"

# --- New run's mean score + metadata ------------------------------------------
NEW_SCORE="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1])).get("mean_score") or 0.0)' "$REPORT")"
NEW_COUNT="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1])).get("count") or 0)' "$REPORT")"
NEW_IMAGE="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1])).get("image") or "")' "$REPORT")"
CUR_VERSION="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["version"])' "$PLUGIN_REPO/$CODEX_MANIFEST")"
log "new run: mean_score=$NEW_SCORE over $NEW_COUNT testcase(s); current plugin v$CUR_VERSION"

# --- Baseline (may not exist yet on first ever run) ---------------------------
if [[ -f "$BASELINE_ABS" ]]; then
  BASE_SCORE="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1])).get("mean_score") or 0.0)' "$BASELINE_ABS")"
  BASE_VERSION="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1])).get("version") or "?")' "$BASELINE_ABS")"
  BASE_PLUGIN_COMMIT="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1])).get("plugin_commit") or "")' "$BASELINE_ABS")"
  HAVE_BASELINE=1
  log "baseline: mean_score=$BASE_SCORE (from plugin v$BASE_VERSION, commit ${BASE_PLUGIN_COMMIT:0:12})"
else
  BASE_SCORE=0.0; BASE_VERSION="(none)"; BASE_PLUGIN_COMMIT=""; HAVE_BASELINE=0
  log "no baseline file yet at $BASELINE_FILE — will establish it (no release on first run)"
fi

# Commit of the plugin content THAT WAS BENCHMARKED. Prefer the report's
# embedded plugin_change.commit (captured by the orchestrator BEFORE the matrix,
# from the pulled plugin HEAD) — this is the authoritative "what produced these
# scores". Fall back to the plugin repo's current HEAD only if the report lacks
# it. NOTE: we must NOT just use `git rev-parse HEAD` here, because establishing
# or bumping the baseline commits to the repo and advances HEAD, which would
# defeat the "did the plugin actually change?" guard below.
PLUGIN_COMMIT="$(python3 -c 'import json,sys
try:
    print((json.load(open(sys.argv[1])).get("plugin_change") or {}).get("commit") or "")
except Exception:
    print("")' "$REPORT")"
if [[ -z "$PLUGIN_COMMIT" ]]; then
  PLUGIN_COMMIT="$(git -C "$PLUGIN_REPO" rev-parse HEAD 2>/dev/null || echo '')"
fi

DELTA="$(python3 -c "print(round(float('$NEW_SCORE') - float('$BASE_SCORE'), 6))")"
# Gate: release when the run is NOT LOWER than baseline, i.e. delta >= min-delta
# (default min-delta 0 => "score did not drop"). Per operator requirement:
# "benchmark 结果不低于上一版本即打出新版本".
RELEASE_WORTHY="$(python3 -c "print('1' if (float('$NEW_SCORE') - float('$BASE_SCORE')) >= float('$MIN_DELTA') else '0')")"
log "delta = $NEW_SCORE - $BASE_SCORE = $DELTA  (min-delta $MIN_DELTA; release_worthy=$RELEASE_WORTHY, gate is >=)"

# --- Compute the next version (semver bump) -----------------------------------
NEXT_VERSION="$(python3 - "$CUR_VERSION" "$BUMP" <<'PY'
import sys
cur, bump = sys.argv[1], sys.argv[2]
parts = (cur.split(".") + ["0", "0", "0"])[:3]
try:
    maj, minr, pat = (int(x) for x in parts)
except ValueError:
    maj, minr, pat = 0, 1, 0
if bump == "major":   maj, minr, pat = maj + 1, 0, 0
elif bump == "minor": minr, pat = minr + 1, 0
else:                 pat += 1
print(f"{maj}.{minr}.{pat}")
PY
)"

# --- Helper: write the baseline json (in-repo source of truth) ----------------
write_baseline() {
  local version="$1" score="$2"
  python3 - "$BASELINE_ABS" "$version" "$score" "$NEW_COUNT" "$NEW_IMAGE" "$DELIVERY" "$REPORT" "$PLUGIN_COMMIT" <<'PY'
import json, sys, os
path, version, score, count, image, delivery, report, plugin_commit = sys.argv[1:9]
# Pull the per-testcase score map from the report for provenance/diffing.
rep = json.load(open(report))
cases = {t.get("testcase_id"): t.get("score")
         for t in rep.get("testcases", []) if t.get("testcase_id")}
doc = {
    "version": version,
    "mean_score": float(score),
    "count": int(count),
    "image": image,
    "delivery": delivery or None,
    "plugin_commit": plugin_commit or None,
    "driver": rep.get("driver"),
    "testcases": cases,
    "note": "Benchmark baseline for the CURRENT release. Updated by "
            "AIGameDevBench/scripts/compare-and-maybe-release.sh whenever a run scores "
            "not lower than this baseline (gate: delta >= min-delta). "
            "Timestamps intentionally omitted for deterministic diffs.",
}
os.makedirs(os.path.dirname(path), exist_ok=True)
with open(path, "w", encoding="utf-8") as f:
    json.dump(doc, f, indent=2)
    f.write("\n")
print(path)
PY
}

# --- Helper: bump both manifests (and marketplace if it pins a version) -------
bump_manifests() {
  local version="$1"
  for m in "$CODEX_MANIFEST" "$CLAUDE_MANIFEST"; do
    python3 - "$PLUGIN_REPO/$m" "$version" <<'PY'
import json, sys
path, version = sys.argv[1], sys.argv[2]
d = json.load(open(path))
d["version"] = version
with open(path, "w", encoding="utf-8") as f:
    json.dump(d, f, indent=2)
    f.write("\n")
PY
  done
  # marketplace.json: only rewrite if it PINS a version for our plugin.
  python3 - "$PLUGIN_REPO/.claude-plugin/marketplace.json" "$version" <<'PY'
import json, sys
path, version = sys.argv[1], sys.argv[2]
try:
    d = json.load(open(path))
except Exception:
    sys.exit(0)
changed = False
for p in d.get("plugins", []):
    if p.get("name") == "agentic-game-development-superpowers" and p.get("version") is not None:
        p["version"] = version; changed = True
if changed:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2); f.write("\n")
PY
}

# =============================================================================
# Decision
# =============================================================================
if [[ "$HAVE_BASELINE" == "0" ]]; then
  # First run ever: establish the baseline at the CURRENT version, no release.
  log "establishing initial baseline at v$CUR_VERSION (mean_score=$NEW_SCORE); no release."
  if [[ "$DRY_RUN" == "1" || "$AUTO_RELEASE" == "0" ]]; then
    log "(dry-run / no --auto-release) would write $BASELINE_FILE and commit it."
    exit 0
  fi
  write_baseline "$CUR_VERSION" "$NEW_SCORE" >/dev/null
  ( cd "$PLUGIN_REPO"
    git add "$BASELINE_FILE"
    git commit -m "chore(bench): establish benchmark baseline at v$CUR_VERSION (mean_score=$NEW_SCORE)" >/dev/null
    git push origin HEAD >/dev/null 2>&1 || log "WARN: push failed (commit is local)"
  )
  log "baseline established and pushed."
  exit 0
fi

if [[ "$RELEASE_WORTHY" != "1" ]]; then
  log "score LOWER than baseline (delta $DELTA < min-delta $MIN_DELTA). No release. Baseline unchanged."
  exit 0
fi

# Guard: don't cut a new release for plugin content identical to the baseline's.
# The gate is "not lower", so an unchanged plugin re-running would otherwise
# release forever. Only release when the plugin HEAD differs from the baseline's.
if [[ -n "$PLUGIN_COMMIT" && -n "$BASE_PLUGIN_COMMIT" && "$PLUGIN_COMMIT" == "$BASE_PLUGIN_COMMIT" ]]; then
  log "score not lower (delta $DELTA) but plugin commit unchanged (${PLUGIN_COMMIT:0:12}); nothing new to release."
  exit 0
fi

log "RELEASE-WORTHY: score not lower than baseline (delta $DELTA >= $MIN_DELTA) and plugin changed."
log "Target release: v$CUR_VERSION -> v$NEXT_VERSION (bump=$BUMP); plugin ${BASE_PLUGIN_COMMIT:0:12} -> ${PLUGIN_COMMIT:0:12}."
if [[ "$AUTO_RELEASE" == "0" ]]; then
  log "(no --auto-release) would: bump manifests to v$NEXT_VERSION, refresh baseline, push main."
  exit 0
fi
if [[ "$DRY_RUN" == "1" ]]; then
  log "(--dry-run) computing changes but NOT committing/pushing."
fi

# --- Apply: bump + refresh baseline + commit + push main (auto-release) -------
bump_manifests "$NEXT_VERSION"
write_baseline "$NEXT_VERSION" "$NEW_SCORE" >/dev/null
log "wrote v$NEXT_VERSION into manifests + baseline (mean_score=$NEW_SCORE)."

if [[ "$DRY_RUN" == "1" ]]; then
  log "(--dry-run) skipping git commit/push. Review changes under $PLUGIN_REPO."
  ( cd "$PLUGIN_REPO" && git --no-pager diff --stat ) || true
  exit 0
fi

( cd "$PLUGIN_REPO"
  cur_branch="$(git rev-parse --abbrev-ref HEAD)"
  if [[ "$cur_branch" != "main" ]]; then
    log "checking out main (was on $cur_branch) to auto-release..."
    git checkout main >/dev/null 2>&1 || die "cannot checkout main"
    git pull --ff-only origin main >/dev/null 2>&1 || log "WARN: pull main failed; committing on local main"
    bump_manifests "$NEXT_VERSION"
    write_baseline "$NEXT_VERSION" "$NEW_SCORE" >/dev/null
  fi
  git add "$CODEX_MANIFEST" "$CLAUDE_MANIFEST" ".claude-plugin/marketplace.json" "$BASELINE_FILE"
  git commit -m "chore(plugin): bump to v$NEXT_VERSION (benchmark $NEW_SCORE, delta $DELTA vs v$BASE_VERSION; not lower)" >/dev/null
  git push origin main >/dev/null 2>&1 || die "push to main failed"
)
log "pushed v$NEXT_VERSION to main — release-on-bump.yml will publish the release."
log "DONE: released v$NEXT_VERSION (mean_score $BASE_SCORE -> $NEW_SCORE, delta $DELTA)."
