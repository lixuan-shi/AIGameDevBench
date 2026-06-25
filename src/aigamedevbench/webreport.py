from __future__ import annotations

import json
from pathlib import Path

# Single-file front-end: native JS + SVG/CSS, no CDN, no framework. Served at
# GET / and talks to /api/summary and /api/detail. Kept here so the package
# stays self-contained (no separate static-file dir to ship).
INDEX_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AIGameDevBench Reports</title>
<style>
  :root { --bg:#0f1117; --panel:#171a23; --line:#262a36; --fg:#e6e8ee;
          --muted:#8b91a1; --accent:#6ea8fe; }
  * { box-sizing: border-box; }
  body { margin:0; background:var(--bg); color:var(--fg);
         font:14px/1.5 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; }
  header { padding:14px 18px; border-bottom:1px solid var(--line);
           display:flex; align-items:center; gap:16px; flex-wrap:wrap; }
  h1 { font-size:16px; margin:0; font-weight:600; }
  h2 { font-size:13px; text-transform:uppercase; letter-spacing:.06em;
       color:var(--muted); margin:0 0 10px; }
  .wrap { padding:18px; display:grid; gap:18px; }
  .panel { background:var(--panel); border:1px solid var(--line);
           border-radius:8px; padding:16px; }
  button { background:#222634; color:var(--fg); border:1px solid var(--line);
           border-radius:6px; padding:5px 10px; cursor:pointer; font:inherit; }
  button:hover { border-color:var(--accent); }
  .runs { display:flex; gap:10px; flex-wrap:wrap; }
  .run-chip { display:flex; align-items:center; gap:7px; padding:6px 10px;
              border:1px solid var(--line); border-radius:6px; cursor:pointer;
              user-select:none; }
  .run-chip input { accent-color:var(--accent); }
  .run-chip small { color:var(--muted); }
  .bar-row { display:grid; grid-template-columns:160px 1fr 56px;
             align-items:center; gap:10px; margin:5px 0; }
  .bar-track { background:#0c0e14; border-radius:4px; height:18px;
               overflow:hidden; }
  .bar-fill { height:100%; }
  .num { text-align:right; color:var(--muted); }
  table { border-collapse:collapse; width:100%; }
  th, td { border:1px solid var(--line); padding:5px 7px; text-align:center; }
  th.tc, td.tc { text-align:left; white-space:nowrap; }
  td.cell { cursor:pointer; font-variant-numeric:tabular-nums; }
  td.cell:hover { outline:2px solid var(--accent); outline-offset:-2px; }
  .miss { color:#555; background:#12141b; }
  .cats { display:grid; gap:6px; }
  .cat-line { display:grid; grid-template-columns:130px 1fr; gap:8px;
              align-items:center; }
  .grp { display:grid; grid-template-columns:90px 1fr 44px;
         align-items:center; gap:8px; margin:2px 0; }
  .badge { display:inline-block; padding:1px 7px; border-radius:10px;
           font-size:12px; margin-left:6px; }
  .badge.warn { background:#3a2a12; color:#f0b86e; }
  .badge.ok { background:#16301f; color:#74d99f; }
  #overlay { position:fixed; inset:0; background:rgba(0,0,0,.55);
             display:none; align-items:flex-start; justify-content:center;
             padding:40px 16px; overflow:auto; }
  #overlay.show { display:flex; }
  .modal { background:var(--panel); border:1px solid var(--line);
           border-radius:10px; max-width:1100px; width:100%; padding:18px; }
  .modal-head { display:flex; justify-content:space-between; align-items:center;
                margin-bottom:12px; }
  .detail-cols { display:grid; gap:14px;
                 grid-template-columns:repeat(auto-fit,minmax(320px,1fr)); }
  .check { border:1px solid var(--line); border-radius:6px; padding:8px 10px;
           margin:6px 0; }
  .check.pass { border-left:3px solid #74d99f; }
  .check.fail { border-left:3px solid #f06e6e; }
  .check .nm { font-weight:600; }
  .check .ea { color:var(--muted); margin-top:3px; word-break:break-word; }
  .check .ea b { color:var(--fg); font-weight:600; }
  .empty { color:var(--muted); padding:20px; text-align:center; }
  .err { color:#f0a0a0; white-space:pre-wrap; }
  a { color:var(--accent); }
</style>
</head>
<body>
<header>
  <h1>AIGameDevBench Reports</h1>
  <button id="refresh">Refresh</button>
  <span id="status" style="color:var(--muted)"></span>
</header>
<div class="wrap">
  <div class="panel">
    <h2>Runs</h2>
    <div id="runs" class="runs"></div>
  </div>
  <div class="panel">
    <h2>Overall &amp; per-category</h2>
    <div id="overall"></div>
  </div>
  <div class="panel">
    <h2>Score matrix (click a cell to drill in)</h2>
    <div id="matrix" style="overflow:auto"></div>
  </div>
  <div class="panel">
    <h2>Timing &amp; stability</h2>
    <div id="timing"></div>
  </div>
</div>

<div id="overlay"><div class="modal">
  <div class="modal-head">
    <h2 id="modal-title" style="margin:0"></h2>
    <button id="close">Close</button>
  </div>
  <div id="modal-body"></div>
</div></div>

<script>
const $ = (s, el=document) => el.querySelector(s);
let SUMMARY = null;
let SELECTED = new Set();

function scoreColor(s) {
  if (s === null || s === undefined) return null;
  // red(0) -> yellow(0.5) -> green(1): hue 0..120
  const hue = Math.max(0, Math.min(1, s)) * 120;
  return `hsl(${hue},55%,32%)`;
}
function fmt(n, d=2) {
  return (n === null || n === undefined) ? "-" : Number(n).toFixed(d);
}
function esc(v) {
  if (v === null || v === undefined) return "null";
  return String(v).replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
}
function selectedRuns() {
  return SUMMARY.runs.filter(r => SELECTED.has(r.run_id));
}

async function load() {
  $("#status").textContent = "loading...";
  const res = await fetch("/api/summary");
  SUMMARY = await res.json();
  if (SELECTED.size === 0)
    SUMMARY.runs.forEach(r => SELECTED.add(r.run_id));
  else
    SELECTED = new Set([...SELECTED].filter(
      id => SUMMARY.runs.some(r => r.run_id === id)));
  $("#status").textContent =
    `${SUMMARY.runs.length} run(s), ${SUMMARY.testcases.length} testcase(s)`;
  renderRuns(); renderAll();
}

function renderRuns() {
  const box = $("#runs");
  if (!SUMMARY.runs.length) { box.innerHTML = '<span class="empty">No reports found.</span>'; return; }
  box.innerHTML = "";
  for (const r of SUMMARY.runs) {
    const d = new Date(r.mtime * 1000);
    const lab = document.createElement("label");
    lab.className = "run-chip";
    lab.innerHTML = `<input type="checkbox" ${SELECTED.has(r.run_id)?"checked":""}>
      <span>${esc(r.harness)} <small>${esc(r.file)}</small></span>
      <small>${fmt(r.mean_score)} · ${d.toLocaleString()}</small>`;
    lab.querySelector("input").addEventListener("change", e => {
      e.target.checked ? SELECTED.add(r.run_id) : SELECTED.delete(r.run_id);
      renderAll();
    });
    box.appendChild(lab);
  }
}

function renderAll() { renderOverall(); renderMatrix(); renderTiming(); }

function renderOverall() {
  const runs = selectedRuns();
  const el = $("#overall");
  if (!runs.length) { el.innerHTML = '<span class="empty">Select a run.</span>'; return; }
  let h = "<h2>Mean score</h2>";
  for (const r of runs) h += barRow(r.harness, r.mean_score);
  // per-category grouped
  const cats = [...new Set(runs.flatMap(r =>
    Object.keys(SUMMARY.categories[r.run_id] || {})))].sort();
  if (cats.length) {
    h += '<h2 style="margin-top:14px">Per-category mean</h2>';
    for (const c of cats) {
      h += `<div class="cat-line"><div>${esc(c)}</div><div>`;
      for (const r of runs) {
        const cd = (SUMMARY.categories[r.run_id]||{})[c];
        const m = cd ? cd.mean : null;
        h += `<div class="grp"><small>${esc(r.harness)}</small>
          <div class="bar-track"><div class="bar-fill"
            style="width:${(m||0)*100}%;background:${scoreColor(m)||'#333'}"></div></div>
          <span class="num">${fmt(m)}</span></div>`;
      }
      h += "</div></div>";
    }
  }
  el.innerHTML = h;
}
function barRow(label, score) {
  return `<div class="bar-row"><div>${esc(label)}</div>
    <div class="bar-track"><div class="bar-fill"
      style="width:${(score||0)*100}%;background:${scoreColor(score)||'#333'}"></div></div>
    <span class="num">${fmt(score)}</span></div>`;
}

function renderMatrix() {
  const runs = selectedRuns();
  const el = $("#matrix");
  if (!runs.length || !SUMMARY.testcases.length) {
    el.innerHTML = '<span class="empty">Nothing to show.</span>'; return; }
  let h = "<table><thead><tr><th class='tc'>testcase</th>";
  for (const r of runs) h += `<th>${esc(r.harness)}<br><small>${esc(r.file)}</small></th>`;
  h += "</tr></thead><tbody>";
  for (const tc of SUMMARY.testcases) {
    h += `<tr><td class='tc'>${esc(tc)}</td>`;
    for (const r of runs) {
      const s = SUMMARY.matrix[tc][r.run_id];
      if (s === null || s === undefined) {
        h += `<td class="cell miss">-</td>`;
      } else {
        h += `<td class="cell" style="background:${scoreColor(s)}"
          data-run="${esc(r.run_id)}" data-tc="${esc(tc)}">${fmt(s)}</td>`;
      }
    }
    h += "</tr>";
  }
  h += "</tbody></table>";
  el.innerHTML = h;
  el.querySelectorAll("td.cell[data-tc]").forEach(td =>
    td.addEventListener("click", () => openDetail(td.dataset.tc)));
}

function renderTiming() {
  const runs = selectedRuns();
  const el = $("#timing");
  if (!runs.length) { el.innerHTML = '<span class="empty">Select a run.</span>'; return; }
  const maxTotal = Math.max(...runs.map(r => (SUMMARY.timing[r.run_id]||{}).total_wall_time || 0), 1);
  let h = "";
  for (const r of runs) {
    const t = SUMMARY.timing[r.run_id] || {};
    let badges = "";
    if (t.timed_out) badges += `<span class="badge warn">timeout ${t.timed_out}</span>`;
    if (t.stalled) badges += `<span class="badge warn">stalled ${t.stalled}</span>`;
    if (t.blocked_on_approval) badges += `<span class="badge warn">blocked ${t.blocked_on_approval}</span>`;
    if (!badges) badges = `<span class="badge ok">clean</span>`;
    h += `<div class="bar-row"><div>${esc(r.harness)}</div>
      <div class="bar-track"><div class="bar-fill"
        style="width:${((t.total_wall_time||0)/maxTotal)*100}%;background:#3b6ea5"></div></div>
      <span class="num">${fmt(t.total_wall_time,1)}s</span></div>
      <div style="margin:-2px 0 8px 170px;color:var(--muted)">
        mean ${fmt(t.mean_wall_time,1)}s ${badges}</div>`;
  }
  el.innerHTML = h;
}

async function openDetail(tc) {
  const runs = selectedRuns();
  $("#modal-title").textContent = tc;
  $("#modal-body").innerHTML = "loading...";
  $("#overlay").classList.add("show");
  const details = await Promise.all(runs.map(r =>
    fetch(`/api/detail?run=${encodeURIComponent(r.run_id)}&testcase=${encodeURIComponent(tc)}`)
      .then(x => x.json()).then(d => ({run:r, detail:d})).catch(() => ({run:r, detail:null}))));
  let h = '<div class="detail-cols">';
  for (const {run, detail} of details) {
    h += `<div><h2>${esc(run.harness)} <small>${esc(run.file)}</small></h2>`;
    if (!detail) { h += '<div class="empty">not in this run</div></div>'; continue; }
    h += `<div style="margin-bottom:6px">score <b>${fmt(detail.score)}</b>
          · ${esc(detail.status)}`;
    if (detail.wall_time != null) h += ` · ${fmt(detail.wall_time,1)}s`;
    h += "</div>";
    if (detail.error) h += `<div class="err">${esc(detail.error)}</div>`;
    if (!detail.checks.length) h += '<div class="empty">no checks</div>';
    for (const c of detail.checks) {
      h += `<div class="check ${c.passed?'pass':'fail'}">
        <div class="nm">${c.passed?'✓':'✗'} ${esc(c.name)}</div>`;
      if (c.detail) h += `<div class="ea">${esc(c.detail)}</div>`;
      if (c.expected !== null || c.actual !== null)
        h += `<div class="ea">expected <b>${esc(c.expected)}</b> ·
              actual <b>${esc(c.actual)}</b></div>`;
      h += "</div>";
    }
    h += "</div>";
  }
  h += "</div>";
  $("#modal-body").innerHTML = h;
}

$("#refresh").addEventListener("click", load);
$("#close").addEventListener("click", () => $("#overlay").classList.remove("show"));
$("#overlay").addEventListener("click", e => {
  if (e.target.id === "overlay") $("#overlay").classList.remove("show"); });
document.addEventListener("keydown", e => {
  if (e.key === "Escape") $("#overlay").classList.remove("show"); });
load();
</script>
</body>
</html>
"""


def load_reports(reports_dir: Path) -> list[dict]:
    """Load every benchmark report JSON in `reports_dir`.

    Each loaded report gets three derived fields injected:
      _file:   the filename (used as the stable, unique run discriminator)
      _mtime:  file modification time (reports carry no timestamp of their own)
      _run_id: a unique id for the run, derived from harness + filename so two
               runs of the same harness still get distinct ids.
    Files that are not valid JSON, or are JSON without a `testcases` list, are
    skipped so one stray file cannot break the whole view.
    """
    reports_dir = Path(reports_dir)
    out: list[dict] = []
    for path in sorted(reports_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(data, dict) or not isinstance(data.get("testcases"), list):
            continue
        data["_file"] = path.name
        data["_mtime"] = path.stat().st_mtime
        harness = data.get("harness") or "run"
        data["_run_id"] = f"{harness}::{path.stem}"
        out.append(data)
    return out


def build_summary(reports: list[dict]) -> dict:
    """Aggregate loaded reports into the structure the web UI consumes."""
    runs = []
    categories: dict[str, dict] = {}
    timing: dict[str, dict] = {}
    testcase_ids: set[str] = set()
    matrix: dict[str, dict] = {}

    for r in reports:
        run_id = r["_run_id"]
        tcs = r.get("testcases", [])
        runs.append({
            "run_id": run_id,
            "file": r.get("_file", ""),
            "harness": r.get("harness", ""),
            "mtime": r.get("_mtime", 0.0),
            "count": r.get("count", len(tcs)),
            "mean_score": r.get("mean_score", 0.0),
        })
        categories[run_id] = _category_aggregate(tcs)
        timing[run_id] = _timing_aggregate(tcs)
        for tc in tcs:
            testcase_ids.add(tc["testcase_id"])

    ordered_ids = sorted(testcase_ids)
    run_ids = [run["run_id"] for run in runs]
    for tcid in ordered_ids:
        matrix[tcid] = {run_id: None for run_id in run_ids}
    for r in reports:
        run_id = r["_run_id"]
        for tc in r.get("testcases", []):
            matrix[tc["testcase_id"]][run_id] = tc.get("score")

    return {
        "runs": runs,
        "testcases": ordered_ids,
        "matrix": matrix,
        "categories": categories,
        "timing": timing,
    }


def _category_aggregate(testcases: list[dict]) -> dict:
    by_cat: dict[str, list[dict]] = {}
    for tc in testcases:
        by_cat.setdefault(tc.get("category", ""), []).append(tc)
    out = {}
    for cat, items in by_cat.items():
        n = len(items)
        mean = sum(t.get("score", 0.0) for t in items) / n if n else 0.0
        passed = sum(1 for t in items if t.get("score", 0.0) >= 1.0)
        out[cat] = {
            "mean": mean,
            "pass_rate": passed / n if n else 0.0,
            "count": n,
        }
    return out


def _timing_aggregate(testcases: list[dict]) -> dict:
    walls = [t["wall_time"] for t in testcases if isinstance(t.get("wall_time"), (int, float))]
    total = sum(walls)
    return {
        "total_wall_time": total,
        "mean_wall_time": total / len(walls) if walls else 0.0,
        "timed_out": sum(1 for t in testcases if t.get("timed_out")),
        "stalled": sum(1 for t in testcases if t.get("stalled")),
        "blocked_on_approval": sum(1 for t in testcases if t.get("blocked_on_approval")),
    }


def report_detail(report: dict, testcase_id: str) -> dict | None:
    """Per-testcase drill-down: checks (with expected/actual), error, diff, log."""
    for tc in report.get("testcases", []):
        if tc["testcase_id"] == testcase_id:
            vr = tc.get("verifier_result", {})
            return {
                "run_id": report.get("_run_id", ""),
                "testcase_id": testcase_id,
                "category": tc.get("category", ""),
                "score": tc.get("score"),
                "status": vr.get("status", ""),
                "error": vr.get("error", ""),
                "checks": vr.get("checks", []),
                "diff": tc.get("diff", ""),
                "log_path": tc.get("log_path"),
                "wall_time": tc.get("wall_time"),
            }
    return None
