"""The 5CA sheets as a two-tab page: a results board, and the sheets themselves.

    python3 tools/make_5ca_web.py

Writes partner_site/5ca-sheets.html and docs/5ca-sheets.html (Commons) and the
same pair for peers.

RESULTS tab (Christopher, 2026-09-17, chosen from docs/5ca-election-mockups.html):
  * the declaration board -- BBC results-screen idiom: three headline numbers
    (with us / against / no placement), the seat bar with the majority line,
    five result cards with change since last week, and how each party splits;
  * the chamber -- a hemicycle of every member coloured by placement, arranged
    by placement or by party, with W / T / +- highlights and a hover card.
  Change is counted ONLY where the member's deciding evidence changed
  (stance.MOVED_UP / MOVED_DOWN). A re-score of the same evidence is reported
  as "re-assessed" and never as a swing: on 14 Sept 2026 the sign-off wave
  re-placed hundreds of members without any of them doing anything.

SHEETS tab: the Campaigns Brief 5CA table plus a linked name. Evidence is NOT
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
The template is NOT a raw string, so a JavaScript backslash is written twice.
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
PEERS_OUTPUTS = (os.path.join(ROOT, "partner_site", "5ca-peers.html"),
                 os.path.join(ROOT, "docs", "5ca-peers.html"))

# A change counts if its changed_at is AFTER today minus this many days: the
# page is built on Mondays, so last Monday's changes fall just outside.
SINCE_DAYS = 7

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
<title>__TITLE__</title>
<link href="https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700;900&family=Roboto+Condensed:wght@700;900&display=swap" rel="stylesheet">
<style>
:root { --pp:#1B7F3B; --p:#7BC47F; --z:#C3C8CF; --m:#E58A86; --mm:#B80000;
        --ink:#141414; --ink2:#52575C; --mute:#8A8F96; --line:#E3E6EA; --panel:#F4F5F7; }
* { box-sizing:border-box; }
body { font:15px/1.55 Roboto, sans-serif; color:#52575C; background:#FFF;
       max-width:74rem; margin:0 auto; padding:1rem 1.25rem 3rem; }
h1 { color:#52575C; font-size:1.35rem; border-bottom:4px solid #4285f4;
     padding-bottom:.4rem; margin-bottom:.5rem; }
a { color:#4285f4; text-decoration:none; } a:hover { text-decoration:underline; }
.banner { background:#FFEBAD; border-left:4px solid #DB544F; padding:.6rem 1rem;
          font-size:.87em; border-radius:0 4px 4px 0; margin-bottom:1rem; }
.top { display:flex; align-items:flex-end; gap:1rem; border-bottom:1px solid var(--line);
       margin-bottom:1rem; flex-wrap:wrap; }
.top select { margin-bottom:.45rem; }
.tabs { display:flex; gap:.2rem; margin-left:auto; }
.tabs button { background:none; border:0; border-bottom:4px solid transparent; cursor:pointer;
       font:700 .84rem/1 Roboto, sans-serif; text-transform:uppercase; letter-spacing:.04em;
       padding:.7rem .8rem .55rem; color:var(--ink2); }
.tabs button.on { color:var(--ink); border-color:#B80000; }
.pane { display:none; } .pane.on { display:block; }
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
.empty { padding:1.4rem; text-align:center; opacity:.7; font-size:.9em; }
.note { font-size:.82em; opacity:.78; margin-top:.9rem; }
@media print { .bar, .tabs { display:none; } th { position:static; } }
.flag{display:inline-block;font-size:10px;font-weight:700;line-height:1;padding:2px 4px;border-radius:3px;margin-left:4px;vertical-align:middle}
.flag.w{background:#fde68a;color:#7c5a00}.flag.t{background:#bfdbfe;color:#1e3a8a}.flag.x{background:#e5e7eb;color:#374151}.flag.mv{background:var(--ink);color:#fff}
/* results board */
.board { border:1px solid var(--line); border-radius:6px; padding:1rem 1.2rem; margin-bottom:1.2rem; color:var(--ink); }
.kicker { font:700 .72rem/1 Roboto, sans-serif; text-transform:uppercase; letter-spacing:.08em; color:var(--mute); margin-bottom:.5rem; }
.heads { display:grid; grid-template-columns:repeat(3,1fr); gap:.75rem; margin-bottom:1rem; }
.head { border-top:6px solid var(--ink); padding:.5rem .1rem .2rem; }
.head.us { border-color:var(--pp); } .head.them { border-color:var(--mm); } .head.und { border-color:var(--z); }
.head .lab { font:700 .76rem/1 Roboto, sans-serif; text-transform:uppercase; letter-spacing:.06em; color:var(--ink2); }
.head .num { font:900 3rem/1 "Roboto Condensed", sans-serif; letter-spacing:-.02em; margin:.2rem 0 .1rem; }
.head .num small { font-size:1.05rem; font-weight:700; color:var(--mute); margin-left:.3rem; }
.chg { display:inline-block; font:700 .78rem/1 "Roboto Condensed", sans-serif; padding:.22rem .4rem; border-radius:3px; background:var(--panel); color:var(--ink2); }
.chg.up { background:#E4F3E6; color:#175F2C; } .chg.dn { background:#FBE5E5; color:#8E0000; }
.seatbar { position:relative; margin:1.5rem 0 .3rem; }
.seatbar .bar2 { display:flex; height:32px; gap:2px; }
.seatbar .seg { position:relative; border-radius:2px; }
.seatbar .seg span { position:absolute; inset:0; display:flex; align-items:center; justify-content:center; font:900 .92rem/1 "Roboto Condensed", sans-serif; color:#fff; }
.seatbar .seg.z span, .seatbar .seg.p span, .seatbar .seg.m span { color:var(--ink); }
.seatbar .maj { position:absolute; top:-9px; bottom:-9px; left:50%; border-left:2px dashed var(--ink); }
.seatbar .majlab { position:absolute; top:-1.55rem; left:50%; transform:translateX(-50%); font:700 .7rem/1 Roboto, sans-serif; text-transform:uppercase; letter-spacing:.05em; background:var(--ink); color:#fff; padding:.25rem .45rem; white-space:nowrap; }
.axis { display:flex; justify-content:space-between; font-size:.72rem; color:var(--mute); }
.cards { display:grid; grid-template-columns:repeat(5,1fr); gap:.6rem; margin-top:1rem; }
.card { border:1px solid var(--line); border-radius:5px; padding:.55rem .7rem .5rem; position:relative; overflow:hidden; }
.card::before { content:""; position:absolute; left:0; top:0; bottom:0; width:8px; background:var(--c); }
.card .g { font:900 1rem/1 "Roboto Condensed", sans-serif; color:var(--ink2); }
.card .n { font:900 2rem/1 "Roboto Condensed", sans-serif; margin:.25rem 0 .1rem; }
.card .s { font-size:.74rem; color:var(--mute); }
.card .lbl { font:700 .68rem/1.2 Roboto, sans-serif; text-transform:uppercase; letter-spacing:.05em; color:var(--ink2); margin-top:.3rem; }
.chgnote { font-size:.8rem; color:var(--ink2); margin-top:.8rem; }
.prow { display:grid; grid-template-columns:12rem 1fr 3.5rem; gap:.7rem; align-items:center; padding:.26rem 0; border-bottom:1px solid var(--line); font-size:.84rem; }
.prow .pn { display:flex; align-items:center; gap:.5rem; font-weight:700; }
.prow .sw { width:12px; height:12px; border-radius:2px; flex:none; }
.prow .pb { display:flex; height:16px; gap:2px; }
.prow .pb i { display:block; border-radius:2px; }
.prow .tot { text-align:right; color:var(--mute); font:700 .8rem/1 "Roboto Condensed", sans-serif; }
.legend { display:flex; gap:1rem; flex-wrap:wrap; font-size:.76rem; color:var(--ink2); margin:.6rem 0 0; }
.legend i { display:inline-block; width:12px; height:12px; border-radius:2px; vertical-align:-2px; margin-right:.3rem; }
.chamber-wrap { display:grid; grid-template-columns:1fr 17rem; gap:1.2rem; align-items:start; }
.chamber svg { width:100%; height:auto; display:block; }
.chamber .seat { cursor:pointer; stroke:#fff; stroke-width:1; }
.chamber .seat.dim { opacity:.16; }
.chamber .seat.hl { stroke:var(--ink) !important; stroke-width:3 !important; }
.side .box { border:1px solid var(--line); border-radius:5px; padding:.7rem .8rem; margin-bottom:.7rem; font-size:.84rem; }
.side .box b.k { display:block; font:700 .7rem/1 Roboto, sans-serif; text-transform:uppercase; letter-spacing:.06em; color:var(--mute); margin-bottom:.4rem; }
.chips { display:flex; gap:.35rem; flex-wrap:wrap; }
.chip { border:1px solid var(--line); border-radius:999px; padding:.22rem .6rem; font-size:.76rem; font-weight:700; background:#fff; cursor:pointer; color:var(--ink2); }
.chip.on { background:var(--ink); color:#fff; border-color:var(--ink); }
.seatcard { min-height:6rem; }
.seatcard .nm { font:900 1.1rem/1.1 "Roboto Condensed", sans-serif; color:var(--ink); }
.seatcard .mt { color:var(--ink2); font-size:.8rem; }
.pl { display:inline-block; font:900 .85rem/1 "Roboto Condensed", sans-serif; padding:.2rem .4rem; border-radius:3px; color:#fff; }
.pl.p, .pl.z, .pl.m { color:var(--ink); }
.conf { color:var(--mute); font-size:.75rem; }
.tip { position:fixed; pointer-events:none; z-index:50; background:var(--ink); color:#fff; padding:.5rem .65rem; border-radius:4px; font-size:.8rem; max-width:17rem; display:none; box-shadow:0 6px 18px rgba(0,0,0,.25); }
.tip b { display:block; font-size:.9rem; }
@media (max-width:860px) { .chamber-wrap { grid-template-columns:1fr; } .head .num { font-size:2.2rem; } }
@media (max-width:600px) { .cards { grid-template-columns:repeat(2,1fr); } .prow { grid-template-columns:7rem 1fr 3rem; } }
</style></head><body>
<h1>Five Column Analysis <span style="font-weight:400;font-size:.7em">__SUBTITLE__</span></h1>
<p class="banner">__BANNER__</p>

<div class="top">
  <select id="area">__AREA_OPTIONS__</select>
  <div class="tabs"><button class="on" data-tab="results">Results</button><button data-tab="sheets">Sheets</button></div>
</div>

<div class="pane on" id="pane-results">
  <div class="board">
    <div class="kicker">House of __HOUSE__ &middot; <span id="rName"></span> &middot; sheet of __STAMP__</div>
    <div class="heads" id="heads"></div>
    <div class="seatbar" id="seatbarwrap"><div class="majlab" id="majlab"></div><div class="bar2" id="seatbar"></div><div class="maj" id="maj"></div></div>
    <div class="axis"><span>0</span><span id="axisR"></span></div>
    <div class="cards" id="cards"></div>
    <p class="chgnote" id="chgnote"></p>
    <div class="kicker" style="margin-top:1.2rem">How the parties line up</div>
    <div id="parties"></div>
    <div class="legend"><span><i style="background:var(--pp)"></i>++ with us</span><span><i style="background:var(--p)"></i>+ leaning our way</span><span><i style="background:var(--z)"></i>0 no placement</span><span><i style="background:var(--m)"></i>- leaning against</span><span><i style="background:var(--mm)"></i>-- against</span></div>
  </div>
  <div class="board">
    <div class="chamber-wrap">
      <div class="chamber"><div class="kicker">The chamber &middot; <span id="cName"></span></div><svg id="hemi" viewBox="0 0 1000 560" role="img" aria-label="Every member as a seat, coloured by placement"></svg></div>
      <div class="side">
        <div class="box"><b class="k">Arrange</b><div class="chips"><span class="chip on" data-arr="stance">By placement</span><span class="chip" data-arr="party">By party</span></div></div>
        <div class="box" id="hlbox"><b class="k">Highlight</b><div class="chips" id="hlchips"><span class="chip" data-hl="1">Wavering</span><span class="chip" data-hl="2">Targeted</span><span class="chip" data-hl="4">Conflicting</span><span class="chip" data-hl="mv">Moved since <span id="hlSince"></span></span></div></div>
        <div class="box seatcard" id="seatcard"><b class="k">Seat</b><div class="mt">Hover a seat; click to pin.</div></div>
      </div>
    </div>
  </div>
</div>

<div class="pane" id="pane-sheets">
<div class="bar">
  <input type="search" id="q" placeholder="Name, constituency, party or postcode" autocomplete="off">
  <button class="btn" id="partybtn" aria-expanded="false">All parties</button>
  <button class="btn" id="waverbtn" title="Only members flagged as wavering supporters of the other side">Wavering</button>
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
</div>
<div class="tip" id="tip"></div>

<script>
const DATA = __DATASET__;
const HOUSE = "__HOUSE__";
const COLS = ["++","+","0","-","--"];
const CLS = {"++":"pp","+":"p","0":"z","-":"m","--":"mm"};
const CK = ["pp","p","z","m","mm"];
const CCOL = {pp:"#1B7F3B", p:"#7BC47F", z:"#C3C8CF", m:"#E58A86", mm:"#B80000"};
const PCOL = {"Labour":"#E4003B","Labour (Co-op)":"#E4003B","Conservative":"#0087DC","Liberal Democrat":"#FAA61A",
  "Reform UK":"#12B6CF","Green Party":"#02A95B","Scottish National Party":"#F1D400","Plaid Cymru":"#005B54",
  "Democratic Unionist Party":"#D46A4C","Sinn Féin":"#326760","Social Democratic & Labour Party":"#2AA82C",
  "Alliance":"#F6CB2F","Ulster Unionist Party":"#48A5EE","Traditional Unionist Voice":"#0C3A6A",
  "Crossbench":"#8A8F96","Non-affiliated":"#B0B5BC","Bishops":"#7C3AED","Lord Speaker":"#555","Speaker":"#555"};
const PORDER = ["Labour","Labour (Co-op)","Conservative","Liberal Democrat","Reform UK","Scottish National Party",
  "Crossbench","Independent","Non-affiliated","Green Party","Democratic Unionist Party","Sinn Féin","Plaid Cymru","Bishops"];
const areaSel = document.getElementById("area"), q = document.getElementById("q"),
      out = document.getElementById("out"), pcnote = document.getElementById("pcnote"),
      partyBtn = document.getElementById("partybtn"), panel = document.getElementById("partypanel");
const byId = {}; DATA.members.forEach(m => byId[m.i] = m);
let party = new Set(), placement = new Set(), pcConstituency = null, waverOnly = false;
function norm(s){ return (s||"").toLowerCase().replace(/[^a-z0-9 ]/g," ").replace(/\\s+/g," ").trim(); }
function esc(s){ return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/"/g,"&quot;"); }
function allRows(){
  const p = DATA.placements[areaSel.value] || {};
  return Object.keys(p).map(id => ({m: byId[id], c: COLS[p[id][0]], ci: p[id][0], n: p[id][1],
                                    f: p[id][2], fr: p[id][3], fl: p[id][4] || 0}))
                       .filter(r => r.m);
}
/* ---------- tabs ---------- */
document.querySelectorAll(".tabs button").forEach(b => b.onclick = () => {
  document.querySelectorAll(".tabs button").forEach(x => x.classList.toggle("on", x === b));
  document.querySelectorAll(".pane").forEach(p => p.classList.toggle("on", p.id === "pane-" + b.dataset.tab));
});

/* ---------- results: the declaration board ---------- */
const MOVES = DATA.moves || {}, SINCE = DATA.since || null;
function movesFor(){ return (MOVES[areaSel.value] || []).filter(x => byId[x[0]]); }
function movedSet(){ return new Set(movesFor().filter(x => x[2] === "M").map(x => String(x[0]))); }
function tally(rows){ const t = [0,0,0,0,0]; rows.forEach(r => t[r.ci]++); return t; }
/* Previous tally counts REAL moves only (kind M): a re-assessment is us, not the member. */
function prevTally(t, rows){
  const p = t.slice(), cur = {}; rows.forEach(r => cur[r.m.i] = r.ci);
  movesFor().forEach(([id, from, kind]) => { if (kind !== "M" || from < 0 || cur[id] == null) return; p[cur[id]]--; p[from]++; });
  return p;
}
/* good = +1 when a rise helps us, -1 when a rise hurts us, 0 neutral */
function chg(d, good){
  if (!SINCE) return "";
  if (!d) return '<span class="chg">no change</span>';
  const cls = good ? ((d * good > 0) ? "up" : "dn") : "";
  return '<span class="chg ' + cls + '">' + (d > 0 ? "&#9650; +" : "&#9660; ") + d + '</span>';
}
function pcol(p){ return PCOL[p] || "#8A8F96"; }
function areaName(){ return areaSel.options[areaSel.selectedIndex].text; }
function renderBoard(){
  const rows = allRows(), t = tally(rows), pt = prevTally(t, rows), N = rows.length;
  document.getElementById("rName").textContent = areaName();
  document.getElementById("axisR").textContent = N + (HOUSE === "Commons" ? " MPs" : " peers");
  const us = t[0] + t[1], them = t[3] + t[4], und = t[2];
  const pus = pt[0] + pt[1], pthem = pt[3] + pt[4], pund = pt[2];
  const pc = n => N ? Math.round(n / N * 100) : 0;
  document.getElementById("heads").innerHTML =
    '<div class="head us"><div class="lab">With us (++ and +)</div><div class="num">' + us + '<small>' + pc(us) + '%</small></div>' + chg(us - pus, 1) + '</div>' +
    '<div class="head them"><div class="lab">Against (- and --)</div><div class="num">' + them + '<small>' + pc(them) + '%</small></div>' + chg(them - pthem, -1) + '</div>' +
    '<div class="head und"><div class="lab">No placement</div><div class="num">' + und + '<small>' + pc(und) + '%</small></div>' + chg(und - pund, 0) + '</div>';
  document.getElementById("seatbar").innerHTML = t.map((n, i) => n ?
    '<div class="seg ' + CK[i] + '" style="flex:' + n + ';background:' + CCOL[CK[i]] + '" title="' + COLS[i] + ': ' + n + '">' +
    (n / N > 0.04 ? '<span>' + n + '</span>' : '') + '</div>' : '').join("");
  // The majority line means something in the Commons; the Lords has no fixed
  // quorum of members, so the peers page shows the bar without it.
  const commons = HOUSE === "Commons", maj = Math.floor(N / 2) + 1;
  document.getElementById("maj").style.display = commons ? "" : "none";
  document.getElementById("majlab").style.display = commons ? "" : "none";
  document.getElementById("majlab").textContent = maj + " for a majority";
  const LBL = ["Firmly with us","Leaning our way","No placement","Leaning against","Firmly against"], GOOD = [1,1,0,-1,-1];
  document.getElementById("cards").innerHTML = t.map((n, i) =>
    '<div class="card" style="--c:' + CCOL[CK[i]] + '"><div class="g">' + COLS[i] + '</div><div class="n">' + n + '</div>' +
    '<div class="s">' + (N ? (n / N * 100).toFixed(1) : 0) + '% of members</div><div class="lbl">' + LBL[i] + '</div>' +
    (SINCE ? '<div style="margin-top:.35rem">' + chg(n - pt[i], GOOD[i]) + '</div>' : '') + '</div>').join("");
  const mv = movesFor(), moved = mv.filter(x => x[2] === "M").length, re = mv.filter(x => x[2] === "R").length, nw = mv.filter(x => x[2] === "N").length;
  document.getElementById("chgnote").innerHTML = SINCE ?
    'Change since ' + SINCE + ': <b>' + moved + '</b> member' + (moved === 1 ? "" : "s") + ' moved on new evidence (counted above)' +
    (re ? '; <b>' + re + '</b> re-assessed by us on the same evidence (not counted)' : '') +
    (nw ? '; <b>' + nw + '</b> new to the sheet' : '') + '.' : '';
  const byP = {}; rows.forEach(r => { (byP[r.m.p] = byP[r.m.p] || [0,0,0,0,0])[r.ci]++; });
  const sum = a => a.reduce((x, y) => x + y, 0);
  const names = Object.keys(byP).sort((a, b) => (sum(byP[b]) - sum(byP[a])) || a.localeCompare(b));
  document.getElementById("parties").innerHTML = names.map(p => {
    const tp = byP[p];
    return '<div class="prow"><div class="pn"><i class="sw" style="background:' + pcol(p) + '"></i>' + esc(p) + '</div><div class="pb">' +
      tp.map((n, i) => n ? '<i style="flex:' + n + ';background:' + CCOL[CK[i]] + '" title="' + COLS[i] + ' ' + n + '"></i>' : '').join("") +
      '</div><div class="tot">' + sum(tp) + '</div></div>'; }).join("");
}

/* ---------- results: the chamber ---------- */
let arrange = "stance", hl = new Set(), pinned = null, seatCache = {};
function seats(total){
  if (seatCache[total]) return seatCache[total];
  const R = Math.max(6, Math.ceil(total / 59)), r0 = 150, r1 = 470, cx = 500, cy = 520, pts = [];
  const radii = []; for (let i = 0; i < R; i++) radii.push(r0 + (r1 - r0) * i / (R - 1));
  const sum = radii.reduce((a, b) => a + b, 0);
  const alloc = radii.map(r => Math.floor(total * r / sum));
  let rem = total - alloc.reduce((a, b) => a + b, 0);
  for (let i = R - 1; rem > 0; i = (i - 1 + R) % R) { alloc[i]++; rem--; }
  radii.forEach((r, i) => { const n = alloc[i]; for (let k = 0; k < n; k++) {
    const a = Math.PI - (n === 1 ? Math.PI / 2 : Math.PI * k / (n - 1));
    pts.push({x: cx + r * Math.cos(a), y: cy - r * Math.sin(a), a: a, row: i}); } });
  pts.sort((p, q) => q.a - p.a || p.row - q.row);
  pts.r = Math.min(11, ((r1 - r0) / (R - 1)) * 0.42);
  seatCache[total] = pts; return pts;
}
function ordered(rows){
  const po = p => { const i = PORDER.indexOf(p); return i < 0 ? 99 : i; };
  if (arrange === "party") return rows.slice().sort((a, b) => po(a.m.p) - po(b.m.p) || a.m.p.localeCompare(b.m.p) || a.ci - b.ci || a.m.n.localeCompare(b.m.n));
  return rows.slice().sort((a, b) => a.ci - b.ci || po(a.m.p) - po(b.m.p) || a.m.n.localeCompare(b.m.n));
}
function renderChamber(){
  const rows = ordered(allRows()), mv = movedSet(), S = seats(rows.length);
  document.getElementById("cName").textContent = areaName();
  const active = hl.size > 0;
  document.getElementById("hemi").innerHTML = rows.map((r, i) => { const s = S[i]; if (!s) return "";
    const on = !active || [...hl].some(h => h === "mv" ? mv.has(String(r.m.i)) : (r.fl & h));
    return '<circle class="seat' + (on ? '' : ' dim') + (pinned === r.m.i ? ' hl' : '') + '" data-id="' + r.m.i + '" cx="' + s.x.toFixed(1) + '" cy="' + s.y.toFixed(1) + '" r="' + S.r.toFixed(1) + '" fill="' + (arrange === "party" ? pcol(r.m.p) : CCOL[CK[r.ci]]) + '"' +
      (arrange === "party" ? ' style="stroke:' + CCOL[CK[r.ci]] + ';stroke-width:4.5"' : '') + '></circle>'; }).join("") +
    '<text x="500" y="535" text-anchor="middle" font-family="Roboto Condensed, Roboto, sans-serif" font-weight="900" font-size="30" fill="#141414">' + rows.length + (HOUSE === "Commons" ? " MPs" : " peers") + '</text>';
  if (pinned) showSeat(byId[pinned]);
}
const TIER = ["strong","moderate","thin"];
function flagHtml(fl, moved){
  return ((fl & 1) ? '<span class="flag w" title="Wavering: backed our side in votes, or thin majority with recent words not hostile">W</span>' : '') +
         ((fl & 2) ? '<span class="flag t" title="Targeted by one of our campaigns">T</span>' : '') +
         ((fl & 4) ? '<span class="flag x" title="Conflicting signals: evidence both ways">&plusmn;</span>' : '') +
         (moved ? '<span class="flag mv" title="Placement changed on new evidence since ' + SINCE + '">Moved</span>' : '');
}
function loyaltyLine(m){
  return m.al == null ? "" : m.al + '% with party' + (m.df ? ', defied whip &times;' + m.df : '') + (m.tu != null ? ', voted in ' + m.tu + '%' : '');
}
function showSeat(m){
  const p = DATA.placements[areaSel.value][m.i]; if (!p) return;
  const c = p[0], moved = movedSet().has(String(m.i)), loy = loyaltyLine(m);
  document.getElementById("seatcard").innerHTML = '<b class="k">Seat</b><div class="nm">' + esc(m.n) + '</div>' +
    '<div class="mt">' + esc(m.p) + ' &middot; ' + esc(m.s) + (loy ? '<br>' + loy : '') + '</div>' +
    '<div style="margin-top:.4rem"><span class="pl ' + CK[c] + '" style="background:' + CCOL[CK[c]] + '">' + COLS[c] + '</span> ' +
    '<span class="conf">' + (p[2] >= 0 ? TIER[p[2]] + ' &middot; ' + p[1] + ' evidence items' : p[1] + ' evidence items') + '</span></div>' +
    '<div style="margin-top:.35rem">' + flagHtml(p[4] || 0, moved) + '</div>';
}
const tip = document.getElementById("tip"), hemi = document.getElementById("hemi");
hemi.addEventListener("mousemove", e => {
  const c = e.target.closest("circle"); if (!c) { tip.style.display = "none"; return; }
  const m = byId[c.dataset.id], p = DATA.placements[areaSel.value][m.i], col = p[0];
  tip.innerHTML = '<b>' + esc(m.n) + '</b>' + esc(m.p) + ' &middot; ' + esc(m.s) + '<br><span class="pl ' + CK[col] + '" style="background:' + CCOL[CK[col]] + ';margin-top:.3rem">' + COLS[col] + '</span> <span style="opacity:.8">' + (p[2] >= 0 ? TIER[p[2]] : '') + '</span>';
  tip.style.display = "block"; tip.style.left = (e.clientX + 14) + "px"; tip.style.top = (e.clientY + 14) + "px";
  if (!pinned) showSeat(m);
});
hemi.addEventListener("mouseleave", () => tip.style.display = "none");
hemi.addEventListener("click", e => { const c = e.target.closest("circle"); if (!c) return;
  pinned = (pinned === +c.dataset.id) ? null : +c.dataset.id; renderChamber(); });
document.querySelectorAll("[data-arr]").forEach(ch => ch.onclick = () => { arrange = ch.dataset.arr;
  document.querySelectorAll("[data-arr]").forEach(x => x.classList.toggle("on", x === ch)); renderChamber(); });
document.querySelectorAll("#hlchips .chip").forEach(ch => ch.onclick = () => {
  const v = ch.dataset.hl === "mv" ? "mv" : +ch.dataset.hl;
  hl.has(v) ? hl.delete(v) : hl.add(v); ch.classList.toggle("on", hl.has(v)); renderChamber(); });
// The partner dataset carries no flags and no moves: hide the chips that would select nothing.
(function(){
  const anyFlag = Object.values(DATA.placements).some(p => Object.values(p).some(v => v[4]));
  document.querySelectorAll("#hlchips .chip").forEach(ch => {
    const isMv = ch.dataset.hl === "mv";
    ch.style.display = (isMv ? !!SINCE : anyFlag) ? "" : "none"; });
  document.getElementById("hlbox").style.display = (anyFlag || SINCE) ? "" : "none";
  document.getElementById("hlSince").textContent = SINCE || "";
})();
function renderResults(){ renderBoard(); pinned = null; renderChamber(); }

/* ---------- sheets ---------- */
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
    if (waverOnly && !(r.fl & 1)) return false;
    if (pcConstituency) return norm(r.m.s) === pcConstituency;
    if (term) return norm(r.m.n).includes(term) || norm(r.m.s).includes(term)
                  || norm(r.m.p).includes(term);
    return true;
  }).sort((a,b) => COLS.indexOf(a.c) - COLS.indexOf(b.c) || b.n - a.n
                   || a.m.n.localeCompare(b.m.n));
}
function tallyCols(rows){
  const t = {}; COLS.forEach(c => t[c] = 0);
  rows.forEach(r => t[r.c]++);
  return t;
}
function render(){
  const every = allRows(), rows = filtered();
  const isFiltered = rows.length !== every.length;
  const tSel = tallyCols(rows), tAll = tallyCols(every);
  const head = '<thead><tr><th>Decision-Maker</th>' + COLS.map(c =>
      '<th class="c' + (placement.has(c) ? " on" : "") + '" data-col="' + c +
      '" title="Click to filter to this column">' + c + '</th>').join("") +
    '<th class="c">Target</th></tr></thead>';
  const DOT = ["\\u25CF","\\u25D0","\\u25CB"];
  const conf = r => r.f < 0 ? "" :
      '<span class="cf cf' + r.f + '" title="' +
      (TIER[r.f] + ": " + (DATA.reasons[r.fr] || "")).replace(/"/g, "&quot;") +
      '">' + DOT[r.f] + '</span>';
  const PP = "__PROFILE_PREFIX__";  // empty when no profile page exists (peers)
  const nameCell = r => (PP
      ? '<a href="' + PP + r.m.i + '">' + r.m.n + '</a>'
      : r.m.n) +
      ((r.fl & 1) ? ' <span class="flag w" title="Wavering: backed our side in votes, or thin majority with recent words not hostile">W</span>' : '') +
      ((r.fl & 2) ? ' <span class="flag t" title="Targeted by one of our campaigns">T</span>' : '') +
      ((r.fl & 4) ? ' <span class="flag x" title="Conflicting signals: evidence both ways">±</span>' : '');
  const loyalty = m => m.al == null ? "" :
      ' \\u00b7 ' + m.al + '% with party' +
      (m.df ? ', defied whip \\u00d7' + m.df : '') +
      (m.tu != null ? ', voted in ' + m.tu + '%' : '');
  const body = rows.length ? '<tbody>' + rows.map(r =>
      '<tr class="' + CLS[r.c] + '"><td class="dm">' + nameCell(r) +
      conf(r) + '<span>' + r.m.p + ', ' + r.m.s + loyalty(r.m) + '</span></td>' +
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
document.getElementById("waverbtn").onclick = e => {
  waverOnly = !waverOnly; e.target.classList.toggle("on", waverOnly); render();
};
q.addEventListener("input", async () => {
  pcConstituency = null; pcnote.textContent = "";
  if (/\\d/.test(q.value)) await postcode(q.value);
  render();
});
areaSel.addEventListener("change", () => { buildPartyPanel(); syncPartyBtn(); render(); renderResults(); });
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
  const rows = filtered(), t = tallyCols(rows);
  const head = ["Decision-Maker"].concat(COLS).concat(["Target (Y/N)","Confidence","Evidence items"]);
  const body = rows.map(r => ['"' + r.m.n + " (" + r.m.p + ", " + r.m.s + ')"']
    .concat(COLS.map(c => c === r.c ? "1" : ""))
    .concat(["", '"' + (r.f >= 0 ? TIER[r.f] + " (" + (DATA.reasons[r.fr] || "") + ")" : "") + '"',
             r.n]).join(","));
  const totals = ['"Totals - ' + rows.length + ' decision-makers"']
    .concat(COLS.map(c => t[c])).concat(["","",""]).join(",");
  const csv = [head.join(",")].concat(body).concat([totals]).join("\\n");
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([csv], {type:"text/csv"}));
  a.download = "5ca-" + areaSel.value + "-filtered.csv";
  a.click();
});
buildPartyPanel(); syncPartyBtn(); render(); renderResults();
</script>
</body></html>
"""

MOVE_KIND = {stance.MOVED_UP: "M", stance.MOVED_DOWN: "M",
             stance.REASSESSED: "R", stance.NEW: "N"}


def split_decision_maker(text):
    """'Name (Party, Seat)' -> (name, party, seat), surviving a nested
    parenthesis in the party: 'Rachael Maskell (Labour (Co-op), York Central)'.
    """
    name, party, seat = text, "", ""
    if " (" in text and text.endswith(")"):
        cut = text.index(" (")
        name, detail = text[:cut], text[cut + 2:-1]
        # First comma: a party never contains one, a seat often does
        # ("Motherwell, Wishaw and Carluke").
        party, _, seat = detail.partition(", ")
    return name, party, seat


def move_entries(moves, cols, placed):
    """recent_moves rows -> [[member_id, previous column index or -1, kind]]
    for members on this sheet. Kind: M moved on new evidence, R re-assessed
    by us on the same evidence, N new to the sheet."""
    out = []
    for member_id, prev, _placement, movement, _changed in moves:
        kind = MOVE_KIND.get(movement)
        if not kind or str(member_id) not in placed:
            continue
        out.append([member_id, cols.index(prev) if prev in cols else -1, kind])
    return out


def build_datasets(members, placements, reasons, moves, since):
    """(internal_json, partner_json) for one house.

    Confidence is internal-only (Christopher, 2026-08-11): the tiers grade
    our own classifier's certainty, a working note. The partner build also
    drops the flags -- TARGETED names our own campaign targets and WAVERING
    is our read of who might move -- and the moves, which are our week-on-week
    working record. The JS reads a missing fifth element as 0 and a missing
    `since` as "show no change chips".
    """
    internal = json.dumps({"members": members, "placements": placements,
                           "reasons": reasons, "moves": moves, "since": since},
                          separators=(",", ":"))
    bare = {a: {m: [v[0], v[1], -1, -1] for m, v in p.items()}
            for a, p in placements.items()}
    partner = json.dumps({"members": members, "placements": bare,
                          "reasons": [], "moves": {}, "since": None},
                         separators=(",", ":"))
    return internal, partner


def main():
    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    cfg = stance.load_overrides(os.path.join(ROOT, "config", "stance_overrides.yaml"))
    names = intel.area_names(os.path.join(ROOT, "config", "taxonomy.yaml"))
    excluded = set(cfg.get("excluded_from_5ca") or [])
    cols = list(stance.COLUMNS)
    today = datetime.date.today()
    since = (today - datetime.timedelta(days=SINCE_DAYS)).isoformat()
    today = today.isoformat()
    made = []
    for house, outputs, subtitle in (("Commons", OUTPUTS, "working sheets"),
                                     ("Lords", PEERS_OUTPUTS, "peers")):
      members, placements, areas, moves = {}, {}, [], {}
      reasons, reason_ix = [], {}
      for area in sorted(names):
        if area in excluded:
            continue
        rows = stance.suggest_rows(conn, area, full_roster=True, overrides_cfg=cfg,
                                   house=house)
        if not rows:
            continue
        # Movement is recorded every week; the results board shows the last
        # week's REAL moves only (see recent_moves). The old per-row "Based on"
        # column stays hidden: a member with 155 recent speeches read "a vote,
        # 6 years ago", which looked like stale tracking when the opposite was
        # true (Christopher, 2026-08-07).
        stance.update_member_state(conn, area, rows, today)
        key = str(area)
        areas.append({"id": key, "name": names[area]})
        placements[key] = {}
        for r in rows:
            mid = str(r["member_id"])
            if mid not in members:
                name, party, seat = split_decision_maker(r["decision_maker"])
                members[mid] = {"i": r["member_id"], "n": name,
                                "p": party or "Unknown", "s": seat or "-"}
            tier = ["strong", "moderate", "thin"].index(r["confidence"]) \
                if r["confidence"] else -1
            why = r["confidence_why"] or ""
            if why and why not in reason_ix:
                reason_ix[why] = len(reasons)
                reasons.append(why)
            # fifth element: flags -- 1 wavering (see stance.wavering), 2 targeted by
            # one of our MP-named campaigns, 4 conflicting signals. Christopher, 12
            # Sept 2026: the sheet should say who to ring, not only where they sit.
            flags = (1 if r.get("wavering") else 0) | (2 if r.get("targeted") else 0) | (4 if r.get("conflict") else 0)
            placements[key][mid] = [cols.index(r["column"]), r["n_events"],
                                    tier, reason_ix.get(why, -1), flags]
        moves[key] = move_entries(stance.recent_moves(conn, area, since), cols,
                                  placements[key])
      if not areas:
          print("no areas to render for the {0}".format(house))
          continue
      # Whole-record loyalty, from mp_alignment (every Commons division of
      # this Parliament, via tools/pull_division_rolls.py). Christopher,
      # 2026-08-31: alignment and willingness to defy a whip belong in the
      # 5CA -- a target who has already defied their whip is a different
      # prospect from one who never has. Facts from the public record, so
      # both the internal and partner builds carry them; peers have no
      # Commons rolls and simply get no fields.
      align = {str(r["member_id"]): r for r in conn.execute(
          "SELECT member_id, eligible, voted, with_party, against_party, "
          "defied FROM mp_alignment")}
      for mid, m in members.items():
          a = align.get(mid)
          if not a or not (a["with_party"] + a["against_party"]):
              continue
          m["al"] = round(100 * a["with_party"]
                          / (a["with_party"] + a["against_party"]))
          m["df"] = a["defied"]
          if a["eligible"]:
              m["tu"] = round(100 * a["voted"] / a["eligible"])
      dataset_internal, dataset_partner = build_datasets(
          list(members.values()), placements, reasons, moves, since)
      options = "".join('<option value="{0}">{1}</option>'.format(a["id"], a["name"])
                        for a in areas)
      title = ("Five Column Analysis sheets" if house == "Commons"
               else "Five Column Analysis - Peers")
      for path, banner, dataset in ((outputs[0], BANNER_PARTNER, dataset_partner),
                                    (outputs[1], BANNER_INTERNAL, dataset_internal)):
          os.makedirs(os.path.dirname(path), exist_ok=True)
          page = (PAGE.replace("__BANNER__", banner)
                      .replace("__PROFILE_PREFIX__",
                               "mp-votes.html#mp-" if house == "Commons" else "")
                      .replace("__TITLE__", title)
                      .replace("__SUBTITLE__", subtitle)
                      .replace("__HOUSE__", house)
                      .replace("__AREA_OPTIONS__", options)
                      .replace("__STAMP__", today)
                      .replace("__DATASET__", dataset))
          with open(path, "w", encoding="utf-8") as handle:
              handle.write(page)
      n_moves = sum(len(v) for v in moves.values())
      made.append("{0}: {1} areas, {2} members, {3} moves since {4}".format(
          house, len(areas), len(members), n_moves, since))
    conn.close()
    print("; ".join(made) + " -> " + ", ".join(OUTPUTS + PEERS_OUTPUTS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
