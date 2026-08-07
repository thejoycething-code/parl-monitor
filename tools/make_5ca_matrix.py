"""Cross-issue matrix: where every member stands across all our issues at once.

    python3 tools/make_5ca_matrix.py

Writes partner_site/5ca-matrix.html and docs/5ca-matrix.html.

One row per member, one column per campaign area, plus a total across all
issues (Christopher, 2026-08-07). This answers the question a single-area
sheet cannot: Naz Shah is a strong ally on assisted dying and against us on
abortion and free speech, and no per-issue sheet shows both halves.

One honesty point drives the whole design. In a single-area sheet a member
with no evidence sits at "0", which reads as neutral. Across ten areas that
would print 3,874 zeros against 232 genuinely neutral placements -- so a
member with nothing recorded shows a dash here, never a zero, and contributes
nothing to their total. Absence of evidence is not evidence of neutrality.
"""

from __future__ import annotations

import datetime
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, intel, stance

OUTPUTS = (os.path.join(ROOT, "partner_site", "5ca-matrix.html"),
           os.path.join(ROOT, "docs", "5ca-matrix.html"))

RANK = {"++": 2, "+": 1, "0": 0, "-": -1, "--": -2}

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
<title>Cross-issue matrix</title>
<link href="https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700;900&display=swap" rel="stylesheet">
<style>
* { box-sizing:border-box; }
body { font:15px/1.5 Roboto, sans-serif; color:#52575C; background:#FFF;
       max-width:84rem; margin:0 auto; padding:1rem 1.1rem 3rem; }
h1 { color:#52575C; font-size:1.32rem; border-bottom:4px solid #4285f4;
     padding-bottom:.4rem; margin-bottom:.5rem; }
a { color:#4285f4; text-decoration:none; } a:hover { text-decoration:underline; }
.banner { background:#FFEBAD; border-left:4px solid #DB544F; padding:.6rem 1rem;
          font-size:.86em; border-radius:0 4px 4px 0; margin-bottom:.9rem; }
.bar { display:flex; gap:.55rem; align-items:center; flex-wrap:wrap;
       font-size:.85em; margin-bottom:.6rem; position:relative; }
select, input[type=search], .btn { font:inherit; font-size:.9em; padding:.3rem .45rem;
       border:1px solid #C8D0DC; border-radius:4px; background:#FFF; color:#52575C; }
input[type=search] { width:15rem; }
.btn { cursor:pointer; } .btn:hover { background:#f2f6fe; }
.btn.primary { background:#4285f4; color:#FFF; border-color:#4285f4; }
.btn.on { border-color:#4285f4; color:#4285f4; font-weight:700; }
#partypanel { position:absolute; top:2.2rem; left:0; z-index:6; background:#FFF;
   border:1px solid #C8D0DC; border-radius:6px; padding:.55rem .8rem;
   box-shadow:0 4px 14px rgba(0,0,0,.12); max-height:19rem; overflow:auto;
   column-width:12rem; column-gap:1.3rem; display:none; }
#partypanel.open { display:block; }
#partypanel label { display:block; white-space:nowrap; font-size:.92em; break-inside:avoid; }
#partypanel .count { opacity:.55; }
#partypanel .acts { column-span:all; border-top:1px solid #EEEEEE; margin-top:.35rem;
   padding-top:.35rem; }
.pcnote { font-size:.82em; opacity:.7; }
.wrap { overflow-x:auto; }
table { border-collapse:separate; border-spacing:0; font-size:.82em; }
th, td { border-right:1px solid #EEEEEE; border-bottom:1px solid #EEEEEE;
         padding:.3rem .4rem; text-align:center; white-space:nowrap; }
thead th { background:#4285f4; color:#FFF; font-weight:500; position:sticky; top:0; z-index:3;
           cursor:pointer; vertical-align:bottom; }
thead th:hover { background:#2f6fd8; }
th.name, td.name { text-align:left; position:sticky; left:0; background:#FFF; z-index:2;
                   border-left:1px solid #EEEEEE; min-width:14rem; }
thead th.name { background:#4285f4; z-index:4; }
td.name { font-weight:700; }
td.name span { display:block; font-weight:400; font-size:.86em; opacity:.7; }
th.area { writing-mode:vertical-rl; transform:rotate(180deg); height:8.5rem;
          font-size:.95em; padding:.4rem .2rem; }
td.cell { font-weight:700; width:2.4rem; }
td.pp { background:#dff0e0; color:#2f6b33; } td.p { background:#eff7f0; color:#4b7a4e; }
td.z  { background:#F4F4F4; color:#7a7a7a; } td.m { background:#fbeceb; color:#a85450; }
td.mm { background:#f6d9d8; color:#a3302c; }
td.none { color:#C4C4C4; }
td.total { font-weight:700; border-left:2px solid #4285f4; }
td.total .split { display:block; font-weight:400; font-size:.85em; opacity:.65; }
.pos { color:#3d8040; } .neg { color:#DB544F; }
tfoot td { background:#F7F9FC; font-weight:700; border-top:2px solid #4285f4; }
tfoot td.lab { text-align:left; font-weight:500; }
.legend { font-size:.8em; opacity:.85; margin:.5rem 0 0; }
.legend b { display:inline-block; width:1.3rem; text-align:center; border-radius:3px; }
.note { font-size:.82em; opacity:.78; margin-top:.9rem; }
@media print { .bar { display:none; } thead th, th.name, td.name { position:static; } }
</style></head><body>
<h1>Cross-issue matrix <span style="font-weight:400;font-size:.7em">all campaign areas at once</span></h1>
<p class="banner">__BANNER__</p>

<div class="bar">
  <input type="search" id="q" placeholder="Name, constituency, party or postcode" autocomplete="off">
  <button class="btn" id="partybtn" aria-expanded="false">All parties</button>
  <div id="partypanel"></div>
  <span class="pcnote" id="pcnote"></span>
  <select id="sort">
    <option value="net">Sort: strongest allies first</option>
    <option value="netasc">Sort: strongest opponents first</option>
    <option value="evidence">Sort: most evidence</option>
    <option value="name">Sort: name</option>
    <option value="party">Sort: party</option>
  </select>
  <span style="flex:1"></span>
  <span><b id="n">0</b> shown</span>
  <button class="btn" id="clear">Clear</button>
  <button class="btn primary" id="export">Export CSV</button>
</div>

<div class="wrap" id="out"></div>

<p class="legend"><b class="pp" style="background:#dff0e0">++</b> strong ally
 <b class="p" style="background:#eff7f0">+</b> leans our way
 <b class="z" style="background:#F4F4F4">0</b> evidence, no direction
 <b class="m" style="background:#fbeceb">&minus;</b> leans against
 <b class="mm" style="background:#f6d9d8">&minus;&minus;</b> strong opponent
 &nbsp;&middot;&nbsp; <b>&middot;</b> nothing recorded on that issue</p>

<p class="note">A dash means we hold no evidence for that member on that issue, which is not
the same as neutral: it contributes nothing to the total. The total adds the placements where
evidence exists (++ counts 2, + counts 1, &minus; counts &minus;1, &minus;&minus; counts
&minus;2), so a high total means broadly with us across the issues we could measure, and it is
a summary rather than a verdict &mdash; ten areas are not equally important, and this treats
them as if they were. Click any column heading to sort by it. Names link to that member's
voting record. Generated __STAMP__.</p>

<script>
const DATA = __DATASET__;
const COLS = ["++","+","0","-","--"];
const CLS = {"++":"pp","+":"p","0":"z","-":"m","--":"mm"};
const q = document.getElementById("q"), out = document.getElementById("out"),
      nEl = document.getElementById("n"), pcnote = document.getElementById("pcnote"),
      sortSel = document.getElementById("sort"),
      partyBtn = document.getElementById("partybtn"), panel = document.getElementById("partypanel");
let party = new Set(), pcConstituency = null, sortArea = null, sortDir = -1;

function norm(s){ return (s||"").toLowerCase().replace(/[^a-z0-9 ]/g," ").replace(/\\s+/g," ").trim(); }

function buildPartyPanel(){
  const counts = {};
  DATA.members.forEach(m => counts[m.p] = (counts[m.p]||0)+1);
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
  partyBtn.textContent = n === 0 ? "All parties" : (n === 1 ? [...party][0] : n + " parties");
  partyBtn.classList.toggle("on", n > 0);
}

function filtered(){
  const term = norm(q.value);
  let rows = DATA.members.filter(m => {
    if (party.size && !party.has(m.p)) return false;
    if (pcConstituency) return norm(m.s) === pcConstituency;
    if (term) return norm(m.n).includes(term) || norm(m.s).includes(term)
                  || norm(m.p).includes(term);
    return true;
  });
  const mode = sortSel.value;
  if (sortArea !== null) {
    rows.sort((a,b) => {
      const av = a.c[sortArea], bv = b.c[sortArea];
      const ar = av === null ? -99 : 2 - av, br = bv === null ? -99 : 2 - bv;
      return (br - ar) * sortDir || a.n.localeCompare(b.n);
    });
  } else if (mode === "name") rows.sort((a,b) => a.n.localeCompare(b.n));
  else if (mode === "party") rows.sort((a,b) => a.p.localeCompare(b.p) || a.n.localeCompare(b.n));
  else if (mode === "evidence") rows.sort((a,b) => b.e - a.e || a.n.localeCompare(b.n));
  else if (mode === "netasc") rows.sort((a,b) => a.t - b.t || a.n.localeCompare(b.n));
  else rows.sort((a,b) => b.t - a.t || a.n.localeCompare(b.n));
  return rows;
}

function render(){
  const rows = filtered();
  nEl.textContent = rows.length;
  if (!rows.length) { out.innerHTML = '<p class="note">No members match.</p>'; return; }
  let html = '<table><thead><tr><th class="name" data-sort="name">Decision-Maker</th>' +
    DATA.areas.map((a,i) => '<th class="area" data-area="' + i + '" title="' + a +
                            '">' + a + '</th>').join("") +
    '<th data-sort="net">Total</th></tr></thead><tbody>' +
    rows.map(m => '<tr><td class="name"><a href="mp-votes.html#mp-' + m.i + '">' + m.n +
      '</a><span>' + m.p + ', ' + m.s + '</span></td>' +
      m.c.map(v => v === null
        ? '<td class="cell none" title="Nothing recorded">&middot;</td>'
        : '<td class="cell ' + CLS[COLS[v]] + '">' + COLS[v] + '</td>').join("") +
      '<td class="total"><span class="' + (m.t > 0 ? "pos" : (m.t < 0 ? "neg" : "")) + '">' +
      (m.t > 0 ? "+" : "") + m.t + '</span><span class="split">' + m.w + ' with &middot; ' +
      m.a + ' against</span></td></tr>').join("") + '</tbody>';
  // Footer: how each issue stands across the members on screen.
  const withUs = DATA.areas.map((_, i) => rows.filter(m => m.c[i] !== null && m.c[i] < 2).length);
  const against = DATA.areas.map((_, i) => rows.filter(m => m.c[i] !== null && m.c[i] > 2).length);
  html += '<tfoot><tr><td class="lab">With us, by issue</td>' +
    withUs.map(n => '<td>' + n + '</td>').join("") + '<td></td></tr>' +
    '<tr><td class="lab">Against us, by issue</td>' +
    against.map(n => '<td>' + n + '</td>').join("") + '<td></td></tr></tfoot></table>';
  out.innerHTML = html;
  out.querySelectorAll("th[data-area]").forEach(th => th.onclick = () => {
    const i = +th.dataset.area;
    if (sortArea === i) sortDir = -sortDir; else { sortArea = i; sortDir = -1; }
    render();
  });
  out.querySelectorAll("th[data-sort]").forEach(th => th.onclick = () => {
    sortArea = null; sortSel.value = th.dataset.sort === "net" ? "net" : "name"; render();
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
sortSel.addEventListener("change", () => { sortArea = null; render(); });
partyBtn.addEventListener("click", e => {
  e.stopPropagation();
  const open = panel.classList.toggle("open");
  partyBtn.setAttribute("aria-expanded", open ? "true" : "false");
});
document.addEventListener("click", e => {
  if (!panel.contains(e.target) && e.target !== partyBtn) panel.classList.remove("open");
});
document.getElementById("clear").addEventListener("click", () => {
  party.clear(); q.value = ""; pcConstituency = null; pcnote.textContent = "";
  sortArea = null; sortSel.value = "net";
  buildPartyPanel(); syncPartyBtn(); render();
});
document.getElementById("export").addEventListener("click", () => {
  const rows = filtered();
  const head = ["Decision-Maker"].concat(DATA.areas).concat(["Total","With us","Against us"]);
  const body = rows.map(m => ['"' + m.n + " (" + m.p + ", " + m.s + ')"']
    .concat(m.c.map(v => v === null ? "" : COLS[v]))
    .concat([m.t, m.w, m.a]).join(","));
  const csv = [head.join(",")].concat(body).join("\\n");
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([csv], {type:"text/csv"}));
  a.download = "5ca-matrix.csv";
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

    areas = [a for a in sorted(names) if a not in excluded]
    members = {}
    for index, area in enumerate(areas):
        for r in stance.suggest_rows(conn, area, full_roster=True, overrides_cfg=cfg):
            mid = r["member_id"]
            if mid not in members:
                name, party, seat = r["decision_maker"], "", ""
                if " (" in name and name.endswith(")"):
                    name, detail = name[:name.rindex(" (")], name[name.rindex(" (") + 2:-1]
                    party, _, seat = detail.partition(", ")
                members[mid] = {"i": mid, "n": name, "p": party or "Unknown",
                                "s": seat or "-", "c": [None] * len(areas), "e": 0}
            # A member with no evidence on an area gets a dash, never a zero:
            # absence of evidence is not evidence of neutrality.
            if r["n_events"]:
                members[mid]["c"][index] = cols.index(r["column"])
                members[mid]["e"] += r["n_events"]
    conn.close()

    for m in members.values():
        placed = [cols[v] for v in m["c"] if v is not None]
        m["t"] = sum(RANK[p] for p in placed)
        m["w"] = sum(1 for p in placed if RANK[p] > 0)
        m["a"] = sum(1 for p in placed if RANK[p] < 0)

    dataset = json.dumps({"areas": [names[a] for a in areas],
                          "members": sorted(members.values(), key=lambda m: -m["t"])},
                         separators=(",", ":"))
    for path, banner in ((OUTPUTS[0], BANNER_PARTNER), (OUTPUTS[1], BANNER_INTERNAL)):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        page = (PAGE.replace("__BANNER__", banner)
                    .replace("__STAMP__", datetime.date.today().isoformat())
                    .replace("__DATASET__", dataset))
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(page)
    print("{0} areas x {1} members -> {2}".format(
        len(areas), len(members), ", ".join(OUTPUTS)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
