"""The 5CA sheets as a filterable page: one per campaign area, all in one file.

    python3 tools/make_5ca_web.py

Writes partner_site/5ca-sheets.html and docs/5ca-sheets.html.

The table is the Campaigns Brief 5CA format plus two things: the member's name
links to their record in the vote tracker, and a Total column says how much
evidence sits behind the placement. Evidence itself is NOT shown here
(Christopher, 2026-08-06) -- it stays in the CSV's Comments column, which is
the record that goes into a Brief.

Filters are deliberately few: find a member by name, constituency or postcode,
and narrow by party and placement. Evidence, flags and nation filters were
considered and dropped as clutter.
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

PAGE = """<!doctype html>
<html lang="en-GB"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>Five Column Analysis sheets</title>
<link href="https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700;900&display=swap" rel="stylesheet">
<style>
* {{ box-sizing:border-box; }}
body {{ font:15px/1.55 Roboto, sans-serif; color:#52575C; background:#FFF;
       max-width:74rem; margin:0 auto; padding:1rem 1.25rem 3rem; }}
h1 {{ color:#52575C; font-size:1.35rem; border-bottom:4px solid #4285f4;
     padding-bottom:.4rem; margin-bottom:.5rem; }}
a {{ color:#4285f4; text-decoration:none; }} a:hover {{ text-decoration:underline; }}
.banner {{ background:#FFEBAD; border-left:4px solid #DB544F; padding:.6rem 1rem;
          font-size:.87em; border-radius:0 4px 4px 0; margin-bottom:1rem; }}
.controls {{ border:1px solid #EEEEEE; border-radius:6px; padding:.8rem .9rem;
            margin-bottom:.8rem; display:flex; gap:1.1rem; flex-wrap:wrap; }}
.group {{ font-size:.83em; }}
.group b {{ display:block; margin-bottom:.25rem; font-size:.92em; }}
.group label {{ display:block; white-space:nowrap; }}
.group .count {{ opacity:.55; }}
select, input[type=search] {{ font:inherit; font-size:.9em; padding:.35rem .45rem;
        border:1px solid #C8D0DC; border-radius:4px; max-width:100%; }}
input[type=search] {{ width:17rem; }}
.toolbar {{ display:flex; gap:.6rem; align-items:center; flex-wrap:wrap;
           font-size:.85em; margin-bottom:.6rem; }}
.btn {{ border:1px solid #4285f4; color:#4285f4; background:#FFF; border-radius:4px;
       padding:.3rem .7rem; font:inherit; font-size:.9em; cursor:pointer; }}
.btn:hover {{ background:#f2f6fe; }}
.btn.primary {{ background:#4285f4; color:#FFF; }}
.matchcount {{ font-weight:700; }}
table {{ border-collapse:collapse; width:100%; font-size:.84em; }}
th, td {{ border:1px solid #EEEEEE; padding:.38rem .5rem; text-align:left; }}
th {{ background:#4285f4; color:#FFF; font-weight:500; white-space:nowrap;
     position:sticky; top:0; z-index:1; }}
th.c, td.c {{ text-align:center; width:2.1rem; }}
td.c {{ font-weight:700; }}
td.n {{ text-align:right; width:4rem; }}
.dm {{ font-weight:700; white-space:nowrap; }}
.dm span {{ display:block; font-weight:400; font-size:.86em; opacity:.72; }}
tr.pp td.c.on {{ color:#3d8040; }} tr.p td.c.on {{ color:#6aa46c; }}
tr.z td.c.on {{ color:#B0B0B0; }} tr.m td.c.on {{ color:#c2726f; }}
tr.mm td.c.on {{ color:#DB544F; }}
.empty {{ padding:1.4rem; text-align:center; opacity:.7; font-size:.9em; }}
.note {{ font-size:.82em; opacity:.78; margin-top:.9rem; }}
@media print {{ .controls, .toolbar {{ display:none; }} th {{ position:static; }} }}
</style></head><body>
<h1>Five Column Analysis <span style="font-weight:400;font-size:.7em">working sheets</span></h1>
<p class="banner">{banner}</p>

<div class="controls">
  <div class="group"><b>Issue</b><select id="area">{area_options}</select></div>
  <div class="group"><b>Find a member</b>
    <input type="search" id="q" placeholder="Name, constituency or postcode" autocomplete="off">
    <div id="pcnote" class="count"></div></div>
  <div class="group"><b>Party</b><div id="parties"></div></div>
  <div class="group"><b>Placement</b><div id="placements"></div></div>
</div>

<div class="toolbar">
  <span><span class="matchcount" id="n">0</span> of {total} decision-makers</span>
  <span style="flex:1"></span>
  <button class="btn" id="clear">Clear filters</button>
  <button class="btn primary" id="export">Export these as CSV</button>
</div>

<div id="out"></div>

<p class="note">Placements are suggestions from the evidence ledger, strongest evidence first:
a recorded vote outranks a speech, a speech a motion, a motion a question, and a free vote
outranks a whipped one. Target is left blank deliberately: that call belongs to the
campaigner. The dated evidence behind each placement is in the CSV sheets in
<code>data/5ca/</code>. Generated {stamp}.</p>

<script>
const DATA = __DATASET__;
const COLS = ["++","+","0","-","--"];
const CLS = {{"++":"pp","+":"p","0":"z","-":"m","--":"mm"}};
const areaSel = document.getElementById("area"), q = document.getElementById("q"),
      out = document.getElementById("out"), nEl = document.getElementById("n"),
      pcnote = document.getElementById("pcnote");
const byId = {{}}; DATA.members.forEach(m => byId[m.i] = m);
let party = new Set(), placement = new Set(), pcConstituency = null;

function currentRows() {{
  const p = DATA.placements[areaSel.value] || {{}};
  return Object.keys(p).map(id => ({{m: byId[id], c: COLS[p[id][0]], n: p[id][1]}}))
                       .filter(r => r.m);
}}
function norm(s) {{ return (s||"").toLowerCase().replace(/[^a-z0-9 ]/g," ").replace(/\\s+/g," ").trim(); }}

function facets() {{
  const rows = currentRows(), counts = {{}}, pcounts = {{}};
  rows.forEach(r => {{ counts[r.m.p] = (counts[r.m.p]||0)+1;
                      pcounts[r.c] = (pcounts[r.c]||0)+1; }});
  document.getElementById("parties").innerHTML = Object.keys(counts).sort(
    (a,b) => counts[b]-counts[a]).map(p =>
    `<label><input type="checkbox" data-p="${{p.replace(/"/g,'&quot;')}}"${{party.has(p)?" checked":""}}> ${{p}} <span class="count">(${{counts[p]}})</span></label>`).join("");
  document.getElementById("placements").innerHTML = COLS.filter(c => pcounts[c]).map(c =>
    `<label><input type="checkbox" data-c="${{c}}"${{placement.has(c)?" checked":""}}> ${{c}} <span class="count">(${{pcounts[c]}})</span></label>`).join("");
  document.querySelectorAll('[data-p]').forEach(el => el.onchange = e => {{
    e.target.checked ? party.add(e.target.dataset.p) : party.delete(e.target.dataset.p); render(); }});
  document.querySelectorAll('[data-c]').forEach(el => el.onchange = e => {{
    e.target.checked ? placement.add(e.target.dataset.c) : placement.delete(e.target.dataset.c); render(); }});
}}

function filtered() {{
  const term = norm(q.value);
  return currentRows().filter(r => {{
    if (party.size && !party.has(r.m.p)) return false;
    if (placement.size && !placement.has(r.c)) return false;
    if (pcConstituency) return norm(r.m.s) === pcConstituency;
    if (term) return norm(r.m.n).includes(term) || norm(r.m.s).includes(term);
    return true;
  }}).sort((a,b) => COLS.indexOf(a.c) - COLS.indexOf(b.c) || b.n - a.n
                    || (a.m.l||a.m.n).localeCompare(b.m.l||b.m.n));
}}

function render() {{
  const rows = filtered();
  nEl.textContent = rows.length;
  if (!rows.length) {{ out.innerHTML = '<p class="empty">No decision-makers match.</p>'; return; }}
  out.innerHTML = '<table><thead><tr><th>Decision-Maker</th>' +
    COLS.map(c => `<th class="c">${{c}}</th>`).join("") +
    '<th class="c">Target</th><th class="n">Total</th></tr></thead><tbody>' +
    rows.map(r => `<tr class="${{CLS[r.c]}}"><td class="dm"><a href="mp-votes.html#mp-${{r.m.i}}">${{r.m.n}}</a><span>${{r.m.p}}, ${{r.m.s}}</span></td>` +
      COLS.map(c => `<td class="c${{c===r.c?" on":""}}">${{c===r.c?"1":""}}</td>`).join("") +
      `<td class="c"></td><td class="n">${{r.n}}</td></tr>`).join("") +
    '</tbody></table>';
}}

async function postcode(v) {{
  const pc = v.replace(/\\s+/g,"").toUpperCase();
  if (!/^[A-Z]{{1,2}}\\d[A-Z\\d]?\\d[A-Z]{{2}}$/.test(pc)) {{ pcConstituency = null; pcnote.textContent=""; return false; }}
  try {{
    const r = await fetch("https://api.postcodes.io/postcodes/" + encodeURIComponent(pc));
    const j = await r.json();
    const c = j && j.result && j.result.parliamentary_constituency;
    if (!c) throw 0;
    pcConstituency = norm(c); pcnote.textContent = c; return true;
  }} catch (e) {{ pcConstituency = null; pcnote.textContent = "Postcode not found"; return false; }}
}}

q.addEventListener("input", async () => {{
  pcConstituency = null; pcnote.textContent = "";
  if (/\\d/.test(q.value)) await postcode(q.value);
  render();
}});
areaSel.addEventListener("change", () => {{ facets(); render(); }});
document.getElementById("clear").addEventListener("click", () => {{
  party.clear(); placement.clear(); q.value=""; pcConstituency=null; pcnote.textContent="";
  facets(); render(); }});
document.getElementById("export").addEventListener("click", () => {{
  const rows = filtered();
  const head = ["Decision-Maker"].concat(COLS).concat(["Target (Y/N)","Total"]);
  const body = rows.map(r => [`"${{r.m.n}} (${{r.m.p}}, ${{r.m.s}})"`]
    .concat(COLS.map(c => c===r.c?"1":"")).concat(["", r.n]).join(","));
  const blob = new Blob([[head.join(",")].concat(body).join("\\n")], {{type:"text/csv"}});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "5ca-" + areaSel.value + "-filtered.csv";
  a.click();
}});

facets(); render();
</script>
</body></html>
"""

BANNER_PARTNER = (
    "<strong>Coalition partner edition.</strong> Every placement is derived from a member's "
    "own votes, speeches, motions and questions in the public record. The gradient is "
    "CitizenGO's campaign assessment, not the member's stated position, and is a working "
    "draft. Please do not circulate beyond your organisation.")
BANNER_INTERNAL = (
    "<strong>Internal.</strong> CitizenGO's own placements for named parliamentarians, "
    "derived from the evidence ledger. Suggestions for a campaigner to confirm.")


def main():
    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    cfg = stance.load_overrides(os.path.join(ROOT, "config", "stance_overrides.yaml"))
    names = intel.area_names(os.path.join(ROOT, "config", "taxonomy.yaml"))
    excluded = set(cfg.get("excluded_from_5ca") or [])
    cols = list(stance.COLUMNS)

    members, placements, areas = {}, {}, []
    for area in sorted(names):
        if area in excluded:
            continue
        rows = stance.suggest_rows(conn, area, full_roster=True, overrides_cfg=cfg)
        if not rows:
            continue
        key = str(area)
        areas.append({"id": key, "name": names[area]})
        placements[key] = {}
        for r in rows:
            mid = str(r["member_id"])
            if mid not in members:
                name = r["decision_maker"]
                party, seat = "", ""
                if " (" in name and name.endswith(")"):
                    name, detail = name[:name.rindex(" (")], name[name.rindex(" (") + 2:-1]
                    party, _, seat = detail.partition(", ")
                members[mid] = {"i": r["member_id"], "n": name, "p": party or "-",
                                "s": seat or "-", "l": None}
            placements[key][mid] = [cols.index(r["column"]), r["n_events"]]
    conn.close()

    if not areas:
        print("no areas to render")
        return 1
    dataset = {"members": list(members.values()), "placements": placements}
    options = "".join('<option value="{0}">{1}</option>'.format(a["id"], a["name"])
                      for a in areas)
    for path, banner in ((OUTPUTS[0], BANNER_PARTNER), (OUTPUTS[1], BANNER_INTERNAL)):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        page = PAGE.format(banner=banner, area_options=options,
                           total=len(members), stamp=datetime.date.today().isoformat())
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(page.replace("__DATASET__",
                                      json.dumps(dataset, separators=(",", ":"))))
    print("{0} areas, {1} decision-makers -> {2}".format(
        len(areas), len(members), ", ".join(OUTPUTS)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
