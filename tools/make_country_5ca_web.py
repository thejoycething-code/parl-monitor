#!/usr/bin/env python3
"""The 5CA tracker and partner sheet for the new country editions: one page,
a country switcher.

    python3 tools/make_country_5ca_web.py                  # the weekly step
    python3 tools/make_country_5ca_web.py --cc pl --cc it  # some countries only
    python3 tools/make_country_5ca_web.py --db /path/store.db
    python3 tools/make_country_5ca_web.py --db-map stores.txt   # "cc path" per line

Writes docs/5ca-countries.html (internal, every country) and, ONLY when at
least one country has a confirmed reading that places someone,
partner_site/5ca-countries.html (those countries only). With no such country
the partner page is not written, and a stale one is removed: nothing reaches
the partner site before a named person has signed a reading.

The new-country counterpart of tools/make_5ca_tracker.py (docs/5ca-tracker.html,
partner_site/5ca.html): the same look, the same per-area block (the gradient
bar, the change since last week, the names behind each decisive column), with
a country switcher because twenty-one countries do not fit one scroll. What
it shows comes from src/country5ca.publishable_sheets, the SAME gate the CSV
sheets (data/5ca/<cc>-5ca-*.csv) pass through, so a page and a sheet cannot
disagree:

  * a chamber and area appears only with a CONFIRMED reading that places
    someone (status: confirmed, confirmed_by, confirmed_on);
  * every other country shows a placeholder, "Awaiting sign-off: N readings",
    with the breakdown (proposed, procedural, need reading), and no
    placement, guessed or drafted, anywhere;
  * party-group countries (AT, PT, NL: X5) carry the DERIVED label on every
    member placed from the group's vote, and say so above their sheets.

The internal page adds who may sign for each country and the sign-off guide.
The partner page drops both, as the UK partner pages drop our working notes.
English throughout, as the UK 5CA pages; the members' and parties' names are
as each parliament publishes them.

Change since last week is kept in data/5ca/country-web-state.json, per
country, chamber and area, by week commencing.

Runs in jobs/editions-session-judge.sh (Sundays 16:45 London, Mini only),
after tools/country_5ca.py; the Monday deploy ships the partner page.
Read-only on the store; fetches nothing, posts nothing.
"""

from __future__ import annotations

import argparse
import datetime
import html
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import country5ca as c5  # noqa: E402
from src import readings5ca as r5  # noqa: E402
from src.latam import AREA_LABELS  # noqa: E402

INTERNAL_PATH = os.path.join(ROOT, "docs", "5ca-countries.html")
PARTNER_PATH = os.path.join(ROOT, "partner_site", "5ca-countries.html")
STATE_PATH = os.path.join(ROOT, "data", "5ca", "country-web-state.json")

COLUMN_LABEL = {"++": "Strong ally", "+": "Leans our way", "0": "No placement",
                "-": "Leans against", "--": "Strong opponent"}
SEG_CLASS = {"++": "pp", "+": "p", "0": "z", "-": "m", "--": "mm"}

BANNER_INTERNAL = (
    "<strong>Internal.</strong> CitizenGO's 5CA placements in the new country editions. "
    "A member is placed only by a recorded vote whose reading a named person has "
    "confirmed in <code>config/&lt;cc&gt;_stance.yaml</code>; until then a country shows "
    "how many readings await sign-off, and no placement.")
BANNER_PARTNER = (
    "<strong>Coalition partner edition.</strong> Prepared by CitizenGO from each "
    "parliament's published votes. A member is placed only by a recorded vote whose "
    "meaning CitizenGO has reviewed and signed off. The gradient is CitizenGO's campaign "
    "assessment, not the member's stated position, and is a working draft. Please do not "
    "circulate beyond your organisation.")
DERIVED_NOTE = (
    "This parliament records how each party group voted, not each member. Members marked "
    "<span class=\"tag d\">DERIVED</span> carry their group's vote, not a vote of their "
    "own (X5), and weigh less than a member's own recorded vote.")

PAGE = """<!doctype html>
<html lang="en-GB"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>__TITLE__</title>
<link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700;900&display=swap" rel="stylesheet">
<style>
body { font: 15px/1.55 Roboto, sans-serif; color:#52575C; background:#FFF; max-width:70rem;
       margin:0 auto; padding:1rem 1.5rem 3rem; }
h1 { color:#52575C; font-size:1.4rem; border-bottom:4px solid #4285f4; padding-bottom:.4rem; }
h2 { color:#52575C; font-size:1.2rem; margin:1.4rem 0 .3rem; }
.banner { background:#FFEBAD; border-left:4px solid #DB544F; padding:.6rem 1rem;
          font-size:.88em; border-radius:0 4px 4px 0; }
.switch { display:flex; gap:.6rem; align-items:center; flex-wrap:wrap; margin:1.1rem 0 .4rem;
          font-size:.9em; }
.switch select { font:inherit; padding:.32rem .5rem; border:1px solid #C8D0DC; border-radius:4px;
                 background:#FFF; color:#52575C; max-width:100%; }
.status { font-size:.9em; margin:.2rem 0 .8rem; }
.await { border:2px dashed #C3C8CF; border-radius:8px; padding:1.1rem 1.3rem; margin:1rem 0; }
.await b.big { display:block; font-size:1.25rem; color:#52575C; margin-bottom:.3rem; }
.await p { margin:.3rem 0; font-size:.9em; }
.side { font-size:.82em; opacity:.8; }
.area { border:1px solid #EEEEEE; border-radius:8px; padding:1rem 1.2rem; margin:1rem 0; }
.area h3 { color:#4285f4; font-size:1.05rem; margin:0 0 .1rem; }
.evidence { font-size:.82em; opacity:.8; margin:0 0 .7rem; }
.bar { display:flex; height:1.5rem; border-radius:4px; overflow:hidden; margin:.5rem 0 .3rem; }
.seg { font-size:.7em; color:#FFF; display:flex; align-items:center;
       justify-content:center; font-weight:700; }
.seg.pp { background:#55B159; } .seg.p { background:#9ccf9e; color:#2f4030; }
.seg.z { background:#EEEEEE; color:#52575C; }
.seg.m { background:#e9a09d; color:#4a2523; } .seg.mm { background:#DB544F; }
.legend { font-size:.76em; display:flex; gap:.9rem; flex-wrap:wrap; margin:.2rem 0 .6rem; }
.legend i { width:.7em; height:.7em; border-radius:2px; display:inline-block; margin-right:.25em; }
.delta { font-size:.8em; margin:.4rem 0; }
.delta b { color:#4285f4; }
.up { color:#55B159; font-weight:700; } .down { color:#DB544F; font-weight:700; }
details { border-left:3px solid #EEEEEE; padding-left:.8rem; margin:.5rem 0; }
summary { cursor:pointer; font-size:.86em; font-weight:700; color:#4285f4; }
ul { padding-left:1.1rem; margin:.35rem 0; font-size:.84em; }
li { margin:.16rem 0; }
.tag { display:inline-block; font-size:10px; font-weight:700; line-height:1; padding:2px 4px;
       border-radius:3px; margin-left:4px; vertical-align:middle; }
.tag.d { background:#e5e7eb; color:#374151; }
.tag.f { background:#fde68a; color:#7c5a00; }
.note { font-size:.84em; background:#F7F9FC; border-left:3px solid #4285f4; padding:.5rem .8rem;
        margin:.6rem 0; }
.aside { font-size:.8em; opacity:.8; margin:.35rem 0; }
.foot { font-size:.8em; opacity:.7; border-top:1px solid #EEEEEE;
        margin-top:2rem; padding-top:.8rem; }
code { font-size:.92em; }
.js .country { display:none; } .js .country.on { display:block; }
@media print { .switch { display:none; } .js .country { display:block; } }
</style></head><body>
<h1>__H1__ <span style="font-weight:400;font-size:.68em">week commencing __WEEK__</span></h1>
<p class="banner">__BANNER__</p>

<div class="switch"><label for="cc">Country</label>
<select id="cc">__OPTIONS__</select>
<span class="side">__SUMMARY__</span></div>

<p class="legend">
<span><i style="background:#55B159"></i>++ strong ally</span>
<span><i style="background:#9ccf9e"></i>+ leans our way</span>
<span><i style="background:#EEEEEE"></i>0 no placement</span>
<span><i style="background:#e9a09d"></i>- leans against</span>
<span><i style="background:#DB544F"></i>-- strong opponent</span>
</p>

__COUNTRIES__

<p class="foot">Generated __STAMP__ from the parliamentary monitor's country stores. A member is
placed by a recorded vote only once CitizenGO's reading of that vote (which side is ours) is
confirmed by a named person; the strongest such vote decides, and a member with votes on both
sides is flagged. Totals count sitting members only.__FOOT_EXTRA__</p>
<script>
(function () {
  document.documentElement.className = "js";
  var sel = document.getElementById("cc");
  function show(cc) {
    var all = document.querySelectorAll(".country"), hit = false;
    for (var i = 0; i < all.length; i++) {
      var on = all[i].id === "cc-" + cc;
      all[i].className = "country" + (on ? " on" : "");
      hit = hit || on;
    }
    if (!hit && all.length) { all[0].className = "country on"; cc = all[0].id.slice(3); }
    sel.value = cc;
  }
  sel.addEventListener("change", function () {
    show(sel.value);
    if (history.replaceState) history.replaceState(null, "", "#" + sel.value);
  });
  show((location.hash || "").replace("#", "") || sel.value);
})();
</script>
</body></html>
"""


def week_commencing(today):
    d = datetime.date.fromisoformat(today)
    return (d - datetime.timedelta(days=d.weekday())).isoformat()


def area_name(area):
    name = AREA_LABELS.get(area, "area {0}".format(area))
    return name[:1].upper() + name[1:]


def chamber_name(spec, chamber):
    return spec.chambers.get(chamber) or chamber or "Parliament"


def pending(c):
    return c["proposed"] + c["procedural"] + c["needs_reading"]


# --- the data ------------------------------------------------------------------------

def tally(rows):
    out = {c: 0 for c in r5.COLUMNS}
    for r in rows:
        if r["sitting"]:
            out[r["column"]] += 1
    return out


def country_state(cc, conn=None, config_dir=None, today=None, store_error=None):
    """What one country shows: its counts and the sheets that pass the gate.

    `conn` is needed only when the country has a confirmed reading; without
    one, no store is read and the country is awaiting sign-off. A store that
    cannot be read for a country WITH confirmed readings is a gap: the
    country is shown as such internally and kept off the partner page."""
    spec = c5.SPECS[cc]
    entries = c5.load(cc, config_dir)[0]
    counts = c5.counts(cc, config_dir)
    state = {"cc": cc, "name": spec.name, "counts": counts, "awaiting": pending(counts),
             "party_group": cc in c5.PARTY_GROUP, "sheets": [], "gap": None,
             "signers": [s for s in c5.signers(cc) if s not in c5.ALWAYS_SIGNS]}
    if not any(c5._is_confirmed(e) for e in entries.values()):
        return state
    if conn is None:
        state["gap"] = store_error or "no store to read"
        return state
    try:
        for sh in c5.publishable_sheets(conn, cc, config_dir, today, entries=entries):
            if sh["rows"] is None:
                continue
            state["sheets"].append({
                "chamber": sh["chamber"], "chamber_name": chamber_name(spec, sh["chamber"]),
                "area": sh["area"], "area_name": area_name(sh["area"]),
                "signed": sh["signed"], "unsigned": sh["unsigned"],
                "rows": sh["rows"], "tally": tally(sh["rows"])})
    except Exception as exc:          # fail closed: an unreadable country publishes nothing
        state["sheets"] = []
        state["gap"] = "{0}: {1}".format(type(exc).__name__, exc)
    return state


def published(state):
    return bool(state["sheets"]) and not state["gap"]


# --- change since last week ----------------------------------------------------------

def load_history(path):
    try:
        with open(path, encoding="utf-8") as h:
            return json.load(h)
    except (OSError, ValueError):
        return {}


def sheet_key(cc, sheet):
    return "{0}|{1}|{2}".format(cc, sheet["chamber"], sheet["area"])


def prior_counts(history, key, week):
    weeks = sorted(w for w in (history.get(key) or {}) if w < week)
    return history[key][weeks[-1]] if weeks else None


def record(history, states, week):
    for st in states:
        for sh in st["sheets"]:
            history.setdefault(sheet_key(st["cc"], sh), {})[week] = sh["tally"]
    return history


# --- the page ------------------------------------------------------------------------

def bar(counts):
    total = sum(counts.values()) or 1
    segs = []
    for key in r5.COLUMNS:
        n = counts.get(key, 0)
        if not n:
            continue
        pct = 100.0 * n / total
        segs.append('<div class="seg {0}" style="width:{1:.2f}%" title="{2}: {3}">{4}</div>'
                    .format(SEG_CLASS[key], pct, COLUMN_LABEL[key], n, n if pct >= 6 else ""))
    return '<div class="bar">' + "".join(segs) + "</div>"


def delta_line(counts, prior):
    if not prior:
        return '<p class="delta">First week on the tracker: this week is the baseline.</p>'
    bits = []
    for key in r5.COLUMNS:
        change = counts.get(key, 0) - prior.get(key, 0)
        if change:
            cls = "up" if (change > 0) == (key in ("++", "+")) else "down"
            bits.append('{0} <span class="{1}">{2:+d}</span>'.format(key, cls, change))
    if not bits:
        return '<p class="delta">No change since last week.</p>'
    return '<p class="delta"><b>Since last week:</b> ' + " &middot; ".join(bits) + "</p>"


def member_item(r, internal):
    name = r["decision_maker"].replace(" [DERIVED]", "")
    tags = ""
    if "[DERIVED]" in r["decision_maker"]:
        tags += '<span class="tag d">DERIVED</span>'
    if r.get("conflict"):
        tags += '<span class="tag f">MIXED RECORD</span>'
    title = ""
    if internal:
        title = ' title="{0}"'.format(html.escape("{0}; {1}".format(r["based_on"], r["confidence"])))
    return "<li{0}>{1}{2}</li>".format(title, html.escape(name), tags)


def member_list(rows, internal, limit=80):
    shown = rows[:limit]
    items = "".join(member_item(r, internal) for r in shown)
    if len(rows) > limit:
        items += "<li><em>and {0} more (the full sheet is in data/5ca/)</em></li>".format(
            len(rows) - limit)
    return "<ul>" + (items or "<li><em>none</em></li>") + "</ul>"


def awaiting_block(st, internal):
    c = st["counts"]
    n = st["awaiting"]
    if not n and not c["confirmed"]:
        lead = "No votes on our ground to read yet"
        body = ("The store holds no watched or tier-1 vote for this country yet, so there is "
                "nothing to sign off and no one to place.")
    else:
        lead = "Awaiting sign-off: {0:,} reading{1}".format(n, "" if n == 1 else "s")
        body = ("No member is placed until a named person confirms CitizenGO's reading of a "
                "vote. Waiting: {0:,} proposed, {1:,} procedural, {2:,} needing a person to "
                "read the text first.".format(c["proposed"], c["procedural"], c["needs_reading"]))
        if c["confirmed"]:
            body += (" {0:,} confirmed so far, none of which yet places anyone.".format(
                c["confirmed"]))
    out = ['<div class="await"><b class="big">{0}</b><p>{1}</p>'.format(lead, body)]
    if internal:
        out.append('<p class="side">Sign-off guide: <code>docs/5ca-{0}-readings.md</code>; '
                   'confirm with <code>python3 tools/country_5ca.py --cc {0} --sign-from-doc '
                   '--by NAME</code>. Who signs: {1}.</p>'.format(
                       st["cc"], html.escape(", ".join(st["signers"]))
                       if st["signers"] else "Chris (no country signer named yet in "
                       "<code>config/stance_signers.yaml</code>)"))
    out.append("</div>")
    return "\n".join(out)


def sheet_block(st, sh, prior, internal):
    by_col = {}
    for r in sh["rows"]:
        if r["sitting"]:
            by_col.setdefault(r["column"], []).append(r)
    sitting = sum(sh["tally"].values())
    former = sum(1 for r in sh["rows"] if not r["sitting"])
    placed = sitting - sh["tally"]["0"]
    out = ['<div class="area"><h3>{0} <span style="font-weight:400">&middot; {1}</span></h3>'
           .format(html.escape(sh["area_name"]), html.escape(sh["chamber_name"])),
           '<p class="evidence">{0} of {1} sitting members placed, from {2} confirmed '
           'reading{3}{4}{5}</p>'.format(
               placed, sitting, sh["signed"], "" if sh["signed"] == 1 else "s",
               "; {0} more vote{1} awaiting sign-off, not counted".format(
                   sh["unsigned"], "" if sh["unsigned"] == 1 else "s") if sh["unsigned"] else "",
               "; {0} former member{1} listed in the sheet, not counted".format(
                   former, "" if former == 1 else "s") if (internal and former) else ""),
           bar(sh["tally"]), delta_line(sh["tally"], prior)]
    for key in ("++", "+", "-", "--"):
        group = by_col.get(key, [])
        if group:
            out.append("<details><summary>{0} {1} ({2})</summary>{3}</details>".format(
                key, COLUMN_LABEL[key], len(group), member_list(group, internal)))
    zero = sh["tally"]["0"]
    out.append('<p class="aside">0 no placement: {0} sitting member{1} with no confirmed vote '
               'on this area.</p>'.format(zero, "" if zero == 1 else "s"))
    out.append("</div>")
    return "\n".join(out)


def country_block(st, history, week, internal):
    out = ['<section class="country" id="cc-{0}"><h2>{1}</h2>'.format(st["cc"],
                                                                     html.escape(st["name"]))]
    if st["gap"] and internal:
        out.append('<div class="await"><b class="big">Not shown this week</b><p>This country '
                   'has confirmed readings, but its store could not be read ({0}). Nothing is '
                   'published for it until it can.</p></div>'.format(html.escape(st["gap"])))
    elif st["sheets"]:
        n = st["awaiting"]
        out.append('<p class="status">{0} area sheet{1} from confirmed readings.{2}</p>'.format(
            len(st["sheets"]), "" if len(st["sheets"]) == 1 else "s",
            " A further {0:,} reading{1} await sign-off and place no one.".format(
                n, "" if n == 1 else "s") if n else ""))
        if st["party_group"]:
            out.append('<p class="note">{0}</p>'.format(DERIVED_NOTE))
        for sh in st["sheets"]:
            out.append(sheet_block(st, sh, prior_counts(history, sheet_key(st["cc"], sh), week),
                                   internal))
        if internal and n:
            out.append(awaiting_block(st, internal))
    else:
        out.append(awaiting_block(st, internal))
    out.append("</section>")
    return "\n".join(out)


def option_label(st):
    if published(st):
        return "{0} ({1} sheet{2})".format(st["name"], len(st["sheets"]),
                                          "" if len(st["sheets"]) == 1 else "s")
    if st["gap"]:
        return "{0} (not shown this week)".format(st["name"])
    return "{0} (awaiting sign-off: {1:,})".format(st["name"], st["awaiting"])


def render(states, history, week, today, internal):
    options = "".join('<option value="{0}">{1}</option>'.format(st["cc"],
                                                               html.escape(option_label(st)))
                      for st in states)
    live = sum(1 for st in states if published(st))
    waiting = sum(st["awaiting"] for st in states)
    if internal:
        summary = "{0} of {1} countries with confirmed placements; {2:,} readings await " \
                  "sign-off.".format(live, len(states), waiting)
        foot = (" Readings and the sign-off: <code>config/&lt;cc&gt;_stance.yaml</code>, "
                "<code>docs/5ca-&lt;cc&gt;-readings.md</code>; full sheets: "
                "<code>data/5ca/&lt;cc&gt;-5ca-*.csv</code>.")
    else:
        summary = "{0} countr{1} with confirmed placements.".format(live, "y" if live == 1 else "ies")
        foot = ""
    page = PAGE
    for k, v in (("__TITLE__", "5CA: the new countries" + (" (internal)" if internal else "")),
                 ("__H1__", "Five Column Analysis: the new countries"),
                 ("__WEEK__", week), ("__BANNER__", BANNER_INTERNAL if internal else BANNER_PARTNER),
                 ("__OPTIONS__", options), ("__SUMMARY__", html.escape(summary)),
                 ("__STAMP__", today), ("__FOOT_EXTRA__", foot),
                 ("__COUNTRIES__", "\n\n".join(country_block(st, history, week, internal)
                                               for st in states))):
        page = page.replace(k, v)
    return page


# --- the run -------------------------------------------------------------------------

def build(ccs, stores, default_db, config_dir=None, today=None, internal_path=INTERNAL_PATH,
          partner_path=PARTNER_PATH, state_path=STATE_PATH, log=print):
    """Write the internal page, and the partner page only when a country passes
    the gate. Returns (states, partner page written?)."""
    today = today or datetime.date.today().isoformat()
    week = week_commencing(today)
    states = []
    for cc in ccs:
        if not os.path.exists(c5.stance_path(cc, config_dir)):
            continue
        entries = c5.load(cc, config_dir)[0]
        conn, err = None, None
        if any(c5._is_confirmed(e) for e in entries.values()):
            path = stores.get(cc, default_db)
            if os.path.exists(path):
                try:
                    conn = c5.connect_ro(path)
                except Exception as exc:
                    err = "{0}: {1}".format(type(exc).__name__, exc)
            else:
                err = "no store at {0}".format(path)
        try:
            st = country_state(cc, conn, config_dir, today, store_error=err)
        finally:
            if conn is not None:
                conn.close()
        if st["gap"]:
            log("  [gap] {0}: {1}".format(cc, st["gap"]))
        states.append(st)

    history = load_history(state_path)
    internal = render(states, history, week, today, internal=True)
    live = [st for st in states if published(st)]
    partner = render(live, history, week, today, internal=False) if live else None

    os.makedirs(os.path.dirname(internal_path), exist_ok=True)
    with open(internal_path, "w", encoding="utf-8") as h:
        h.write(internal)
    if partner is not None:
        os.makedirs(os.path.dirname(partner_path), exist_ok=True)
        with open(partner_path, "w", encoding="utf-8") as h:
            h.write(partner)
    elif os.path.exists(partner_path):
        os.remove(partner_path)
        log("  no country has a confirmed placement now; removed {0}".format(partner_path))
    if live:
        os.makedirs(os.path.dirname(state_path), exist_ok=True)
        with open(state_path, "w", encoding="utf-8") as h:
            json.dump(record(history, live, week), h, indent=1, sort_keys=True)
            h.write("\n")
    log("5CA countries: {0} countries, {1} with confirmed placements, {2:,} readings awaiting "
        "sign-off -> {3}{4}".format(
            len(states), len(live), sum(st["awaiting"] for st in states), internal_path,
            ", " + partner_path if partner is not None else " (partner page gated: none yet)"))
    return states, partner is not None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cc", action="append", default=[], help="country code (repeatable)")
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--db-map", help="file of 'cc path' lines: a store per country")
    ap.add_argument("--today", help="ISO date (default today)")
    args = ap.parse_args(argv)
    ccs = []
    for c in args.cc:
        ccs += [x.strip() for x in c.split(",") if x.strip()]
    bad = [cc for cc in ccs if cc not in c5.SPECS]
    if bad:
        ap.error("unknown country: {0}".format(", ".join(bad)))
    stores = {}
    if args.db_map:
        with open(args.db_map, encoding="utf-8") as h:
            for line in h:
                bits = line.split()
                if len(bits) == 2 and not line.startswith("#"):
                    stores[bits[0]] = bits[1]
    build(ccs or list(c5.COUNTRIES), stores, args.db, today=args.today)
    return 0


if __name__ == "__main__":
    sys.exit(main())
