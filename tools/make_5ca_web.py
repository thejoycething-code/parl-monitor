"""The 5CA sheets as a filterable page: one per campaign area, all in one file.

    python3 tools/make_5ca_web.py

Writes partner_site/5ca-sheets.html and docs/5ca-sheets.html.

The table is the Campaigns Brief 5CA format plus a linked name. Evidence is NOT
shown here (Christopher, 2026-08-06): it stays in the CSV's Comments column,
which is the record that goes into a Brief.

Filter design (Christopher, 2026-08-07):
  * the TOTALS ROW doubles as the placement filter -- click a gradient column
    to filter to it. The numbers a campaigner reads anyway become the control,
    which deletes a whole filter group rather than shrinking it.
  * parties are multi-select and ALL of them are listed, behind one button so
    the bar stays a single line until opened.
  * totals show as two rows when filtered (selected, and all decision-makers)
    and collapse to one when nothing is filtered.

The template uses __PLACEHOLDER__ substitution rather than str.format: the
JavaScript is full of braces and escaping them was becoming a bug source.
"""

from __future__ import annotations

import datetime
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, intel, stance

OUTPUTS = (os.path.join(ROOT, "partner_site", "5ca-sheets.html"),
           os.path.join(ROOT, "docs", "5ca-sheets.html"))

BANNER_PARTNER = (
    "<strong>Coalition partner edition.</strong> Every placement is derived from a member's "
    "own votes, speeches, motions and questions in the public record. The gradient is "
    "CitizenGO's campaign assessment, not the member's stated position, and is a working "
    "draft. Please do not circulate beyond your organisation.")
BANNER_INTERNAL = (
    "<strong>Internal.</strong> CitizenGO's own placements for named parliamentarians, "
    "derived from the evidence ledger. Suggestions for a campaigner to confirm.")

PAGE = """<!doctype html>
<html lang="en-GB"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>Five Column Analysis sheets</title>
<link href="https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700;900&display=swap" rel="stylesheet">
<style>
* { box-sizing:border-box; }
body { font:15px/1.55 Roboto, sans-serif; color:#52575C; background:#FFF;
       max-width:74rem; margin:0 auto; padding:1rem 1.25rem 3rem; }
h1 { color:#52575C; font-size:1.35rem; border-bottom:4px solid #4285f4;
     padding-bottom:.4rem; margin-bottom:.5rem; }
a { color:#4285f4; text-decoration:none; } a:hover { text-decoration:underline; }
.banner { background:#FFEBAD; border-left:4px solid #DB544F; padding:.6rem 1rem;
          font-size:.87em; border-radius:0 4px 4px 0; margin-bottom:1rem; }
.bar { display:flex; gap:.55rem; align-items:center; flex-wrap:wrap;
       font-size:.86em; margin-bottom:.6rem; position:relative; }
select, input[type=search], .btn { font:inherit; font-size:.9em; padding:.32rem .5rem;
       border:1px solid #C8D0DC; border-radius:4px; background:#FFF; color:#52575C; }
input[type=search] { width:16rem; }
.btn { cursor:pointer; } .btn:hover { background:#f2f6fe; }
.btn.primary { background:#4285f4; color:#FFF; border-color:#4285f4; }
.btn.on { border-color:#4285f4; color:#4285f4; font-weight:700; }
#partypanel { position:absolute; top:2.3rem; left:0; z-index:5; background:#FFF;
   border:1px solid #C8D0DC; border-radius:6px; padding:.6rem .8rem;
   box-shadow:0 4px 14px rgba(0,0,0,.12); max-height:19rem; overflow:auto;
   column-width:12rem; column-gap:1.4rem; display:none; }
#partypanel.open { display:block; }
#partypanel label { display:block; white-space:nowrap; font-size:.92em; padding:.06rem 0;
   break-inside:avoid; }
#partypanel .count { opacity:.55; }
#partypanel .acts { column-span:all; border-top:1px solid #EEEEEE; margin-top:.4rem;
   padding-top:.4rem; }
.pcnote { font-size:.82em; opacity:.7; }
table { border-collapse:collapse; width:100%; font-size:.84em; }
th, td { border:1px solid #EEEEEE; padding:.38rem .5rem; text-align:left; }
th { background:#4285f4; color:#FFF; font-weight:500; white-space:nowrap;
     position:sticky; top:0; z-index:1; }
th.c, td.c { text-align:center; width:2.3rem; }
th.c { cursor:pointer; user-select:none; }
th.c:hover { background:#2f6fd8; }
th.c.on { background:#FFF; color:#4285f4; }
th.c.on::after { content:" x"; font-size:.85em; }
td.c { font-weight:700; }
td.n { text-align:right; }
.dm { font-weight:700; white-space:nowrap; }
.dm span { display:block; font-weight:400; font-size:.86em; opacity:.72; }
tr.pp td.c.on { color:#3d8040; } tr.p td.c.on { color:#6aa46c; }
tr.z td.c.on { color:#B0B0B0; } tr.m td.c.on { color:#c2726f; }
tr.mm td.c.on { color:#DB544F; }
tfoot td { background:#F7F9FC; font-weight:700; }
tfoot tr.sel td { border-top:2px solid #4285f4; }
tfoot tr.all td { opacity:.75; }
tfoot td.lab { font-weight:500; font-size:.94em; }
td.mv .up { color:#55B159; font-weight:700; }
td.mv .down { color:#DB544F; font-weight:700; }
td.mv .ours { background:#EEEEEE; border-radius:3px; padding:.05em .35em; font-size:.92em; }
td.mv .new { background:#4285f4; color:#FFF; border-radius:3px; padding:.05em .35em;
             font-size:.9em; font-weight:700; }
td.mv .flat { opacity:.5; }
.empty { padding:1.4rem; text-align:center; opacity:.7; font-size:.9em; }
.note { font-size:.82em; opacity:.78; margin-top:.9rem; }
@media print { .bar { display:none; } th { position:static; } }
</style></head><body>
<h1>Five Column Analysis <span style="font-weight:400;font-size:.7em">working sheets</span></h1>
<p class="banner">__BANNER__</p>

<div class="bar">
  <select id="area">__AREA_OPTIONS__</select>
  <input type="search" id="q" placeholder="Name, constituency, party or postcode" autocomplete="off">
  <button class="btn" id="partybtn" aria-expanded="false">All parties</button>
  <div id="partypanel"></div>
  <span class="pcnote" id="pcnote"></span>
  <span style="flex:1"></span>
  <button class="btn" id="clear">Clear</button>
  <button class="btn primary" id="export">Export CSV</button>
</div>

<div id="out"></div>

<p class="note">Click a gradient column heading to filter to it. Placements are suggestions
from the evidence ledger, strongest evidence first: a recorded vote outranks a speech, a
speech a motion, a motion a question, and a free vote outranks a whipped one. Target is left
blank deliberately, because that call belongs to the campaigner. The dated evidence behind
each placement is in the CSV sheets in <code>data/5ca/</code>. Generated __STAMP__.</p>

<script>
const DATA = __DATASET__;
const COLS = ["++","+","0","-","--"];
const CLS = {"++":"pp","+":"p","0":"z","-":"m","--":"mm"};
const areaSel = document.getElementById("area"), q = document.getElementById("q"),
      out = document.getElementById("out"), pcnote = document.getElementById("pcnote"),
      partyBtn = document.getElementById("partybtn"), panel = document.getElementById("partypanel");
const byId = {}; DATA.members.forEach(m => byId[m.i] = m);
let party = new Set(), placement = new Set(), pcConstituency = null;

function norm(s){ return (s||"").toLowerCase().replace(/[^a-z0-9 ]/g," ").replace(/\\s+/g," ").trim(); }

function allRows(){
  const p = DATA.placements[areaSel.value] || {};
  return Object.keys(p).map(id => ({m: byId[id], c: COLS[p[id][0]], n: p[id][1]}))
                       .filter(r => r.m);
}

/* Every party listed, alphabetical, with its count in this issue. */
function buildPartyPanel(){
  const counts = {};
  allRows().forEach(r => counts[r.m.p] = (counts[r.m.p]||0)+1);
  const names = Object.keys(counts).sort((a,b) => a.localeCompare(b));
  panel.innerHTML = names.map(p =>
    '<label><input type="checkbox" data-p="' + p.replace(/"/g,"&quot;") + '"' +
    (party.has(p) ? " checked" : "") + '> ' + p +
    ' <span class="count">(' + counts[p] + ')</span></label>').join("") +
    '<div class="acts"><button class="btn" id="pall">Select all</button> ' +
    '<button class="btn" id="pnone">Clear</button></div>';
  panel.querySelectorAll("[data-p]").forEach(el => el.onchange = e => {
    e.target.checked ? party.add(e.target.dataset.p) : party.delete(e.target.dataset.p);
    syncPartyBtn(); render();
  });
  document.getElementById("pall").onclick = () => { names.forEach(n => party.add(n));
    buildPartyPanel(); panel.classList.add("open"); syncPartyBtn(); render(); };
  document.getElementById("pnone").onclick = () => { party.clear();
    buildPartyPanel(); panel.classList.add("open"); syncPartyBtn(); render(); };
}
function syncPartyBtn(){
  const n = party.size;
  partyBtn.textContent = n === 0 ? "All parties"
    : (n === 1 ? [...party][0] : n + " parties");
  partyBtn.classList.toggle("on", n > 0);
}

function filtered(){
  const term = norm(q.value);
  return allRows().filter(r => {
    if (party.size && !party.has(r.m.p)) return false;
    if (placement.size && !placement.has(r.c)) return false;
    if (pcConstituency) return norm(r.m.s) === pcConstituency;
    if (term) return norm(r.m.n).includes(term) || norm(r.m.s).includes(term)
                  || norm(r.m.p).includes(term);
    return true;
  }).sort((a,b) => COLS.indexOf(a.c) - COLS.indexOf(b.c) || b.n - a.n
                   || a.m.n.localeCompare(b.m.n));
}

function tally(rows){
  const t = {}; COLS.forEach(c => t[c] = 0);
  rows.forEach(r => t[r.c]++);
  return t;
}

function render(){
  const every = allRows(), rows = filtered();
  const isFiltered = rows.length !== every.length;
  const tSel = tally(rows), tAll = tally(every);
  const head = '<thead><tr><th>Decision-Maker</th>' + COLS.map(c =>
      '<th class="c' + (placement.has(c) ? " on" : "") + '" data-col="' + c +
      '" title="Click to filter to this column">' + c + '</th>').join("") +
    '<th class="c">Target</th></tr></thead>';
  const body = rows.length ? '<tbody>' + rows.map(r =>
      '<tr class="' + CLS[r.c] + '"><td class="dm"><a href="mp-votes.html#mp-' + r.m.i +
      '">' + r.m.n + '</a><span>' + r.m.p + ', ' + r.m.s + '</span></td>' +
      COLS.map(c => '<td class="c' + (c === r.c ? " on" : "") + '">' +
                    (c === r.c ? "1" : "") + '</td>').join("") +
      '<td class="c"></td></tr>').join("") + '</tbody>' : "";
  // Two totals rows when filtered; one when everything is shown.
  let foot = '<tfoot>';
  if (isFiltered) {
    foot += '<tr class="sel"><td class="lab">Selected &mdash; ' + rows.length +
      ' decision-maker' + (rows.length === 1 ? "" : "s") + '</td>' +
      COLS.map(c => '<td class="c">' + tSel[c] + '</td>').join("") +
      '<td class="c">0</td></tr>';
  }
  foot += '<tr class="all' + (isFiltered ? "" : " sel") + '"><td class="lab">All decision-makers &mdash; ' +
    every.length + '</td>' + COLS.map(c => '<td class="c">' + tAll[c] + '</td>').join("") +
    '<td class="c">0</td></tr></tfoot>';
  out.innerHTML = '<table>' + head + body + foot + '</table>' +
    (rows.length ? "" : '<p class="empty">No decision-makers match.</p>');
  out.querySelectorAll("th[data-col]").forEach(th => th.onclick = () => {
    const c = th.dataset.col;
    placement.has(c) ? placement.delete(c) : placement.add(c);
    render();
  });
}

async function postcode(v){
  const pc = v.replace(/\\s+/g,"").toUpperCase();
  if (!/^[A-Z]{1,2}\\d[A-Z\\d]?\\d[A-Z]{2}$/.test(pc)) { pcConstituency = null; pcnote.textContent = ""; return; }
  try {
    const r = await fetch("https://api.postcodes.io/postcodes/" + encodeURIComponent(pc));
    const j = await r.json();
    const c = j && j.result && j.result.parliamentary_constituency;
    if (!c) throw 0;
    pcConstituency = norm(c); pcnote.textContent = c;
  } catch (e) { pcConstituency = null; pcnote.textContent = "Postcode not found"; }
}

q.addEventListener("input", async () => {
  pcConstituency = null; pcnote.textContent = "";
  if (/\\d/.test(q.value)) await postcode(q.value);
  render();
});
areaSel.addEventListener("change", () => { buildPartyPanel(); syncPartyBtn(); render(); });
partyBtn.addEventListener("click", e => {
  e.stopPropagation();
  const open = panel.classList.toggle("open");
  partyBtn.setAttribute("aria-expanded", open ? "true" : "false");
});
document.addEventListener("click", e => {
  if (!panel.contains(e.target) && e.target !== partyBtn) panel.classList.remove("open");
});
document.getElementById("clear").addEventListener("click", () => {
  party.clear(); placement.clear(); q.value = ""; pcConstituency = null; pcnote.textContent = "";
  buildPartyPanel(); syncPartyBtn(); render();
});
document.getElementById("export").addEventListener("click", () => {
  const rows = filtered(), t = tally(rows);
  const head = ["Decision-Maker"].concat(COLS).concat(["Target (Y/N)","Moved","Based on"]);
  const body = rows.map(r => ['"' + r.m.n + " (" + r.m.p + ", " + r.m.s + ')"']
    .concat(COLS.map(c => c === r.c ? "1" : ""))
    .concat(["", '"' + (r.mv ? (r.mv[0] + (r.mv[1] ? " " + r.mv[1] : "")) : "") + '"',
             '"' + r.b + '"']).join(","));
  const totals = ['"Totals - ' + rows.length + ' decision-makers"']
    .concat(COLS.map(c => t[c])).concat(["","",""]).join(",");
  const csv = [head.join(",")].concat(body).concat([totals]).join("\\n");
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([csv], {type:"text/csv"}));
  a.download = "5ca-" + areaSel.value + "-filtered.csv";
  a.click();
});

buildPartyPanel(); syncPartyBtn(); render();
</script>
</body></html>
"""


def main():
    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    cfg = stance.load_overrides(os.path.join(ROOT, "config", "stance_overrides.yaml"))
    names = intel.area_names(os.path.join(ROOT, "config", "taxonomy.yaml"))
    excluded = set(cfg.get("excluded_from_5ca") or [])
    cols = list(stance.COLUMNS)

    today = datetime.date.today().isoformat()
    members, placements, areas = {}, {}, []
    for area in sorted(names):
        if area in excluded:
            continue
        rows = stance.suggest_rows(conn, area, full_roster=True, overrides_cfg=cfg)
        if not rows:
            continue
        # Movement is still RECORDED every week so the history accumulates,
        # but it is no longer shown. Because a recorded vote outranks every
        # other kind of evidence, the deciding evidence is usually an old
        # division: a member with 155 recent speeches read "a vote, 6 years
        # ago", which looked like stale tracking when the opposite was true
        # (Christopher, 2026-08-07).
        stance.update_member_state(conn, area, rows, today)
        key = str(area)
        areas.append({"id": key, "name": names[area]})
        placements[key] = {}
        for r in rows:
            mid = str(r["member_id"])
            if mid not in members:
                name, party, seat = r["decision_maker"], "", ""
                if " (" in name and name.endswith(")"):
                    name, detail = name[:name.rindex(" (")], name[name.rindex(" (") + 2:-1]
                    party, _, seat = detail.partition(", ")
                members[mid] = {"i": r["member_id"], "n": name,
                                "p": party or "Unknown", "s": seat or "-"}
            placements[key][mid] = [cols.index(r["column"]), r["n_events"]]
    conn.close()

    if not areas:
        print("no areas to render")
        return 1
    dataset = json.dumps({"members": list(members.values()),
                          "placements": placements}, separators=(",", ":"))
    options = "".join('<option value="{0}">{1}</option>'.format(a["id"], a["name"])
                      for a in areas)
    for path, banner in ((OUTPUTS[0], BANNER_PARTNER), (OUTPUTS[1], BANNER_INTERNAL)):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        page = (PAGE.replace("__BANNER__", banner)
                    .replace("__AREA_OPTIONS__", options)
                    .replace("__STAMP__", datetime.date.today().isoformat())
                    .replace("__DATASET__", dataset))
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(page)
    print("{0} areas, {1} decision-makers -> {2}".format(
        len(areas), len(members), ", ".join(OUTPUTS)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
