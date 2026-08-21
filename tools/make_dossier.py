"""Cross-chamber dossier: one issue area across Westminster, Holyrood and NI.

    python3 tools/make_dossier.py --area 2

The stores hold each chamber separately; a campaigner planning one issue needs
them together. This assembles what is already known -- READ-ONLY over the db,
no fetching, no model calls -- into dossiers/<area>-<date>.md.

INTERNAL ONLY, never posted: no Slack, no publish import, and it may quote
watching-brief material (NI, Holyrood) that must not reach the digest. The
dossier POINTS AT the 5CA sheets rather than reproducing them.
"""

from __future__ import annotations

import datetime
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import db, intel, stance


def has_area(raw, area):
    """Tolerant across the stores' three formats: JSON list ('[2, 5]'),
    bare CSV ('2' or '2,5' -- bills_board), and None. json.loads('2') is the
    INT 2, and `area in 2` raises -- which the first version swallowed as
    False, silently emptying the Westminster bills section."""
    if not raw:
        return False
    try:
        v = json.loads(raw)
        if isinstance(v, list):
            return area in v
        if isinstance(v, int):
            return area == v
    except Exception:
        pass
    return str(area) in re.findall(r"\d+", str(raw))


def glance(conn, area, out):
    out.append("## At a glance\n")
    live = [r["title"] for r in conn.execute(
        "SELECT title, areas, status FROM bills_board WHERE status='live'")
        if has_area(r["areas"], area)]
    out.append("* **Westminster**: {0}".format(
        "; ".join("{0} (live)".format(t) for t in live) or "no live bill"))
    sp3 = conn.execute("SELECT vote_for, vote_against, dated FROM sp_divisions "
                       "WHERE reference='S6M-21005'").fetchone()
    if area == 2 and sp3:
        out.append("* **Holyrood**: the Bill was DEFEATED at Stage 3, {0} -- "
                   "{1} for / {2} against; every MSP's position held. A new "
                   "bill needs a new member's slot in session 7.".format(
                       sp3["dated"], sp3["vote_for"], sp3["vote_against"]))
    else:
        n = sum(1 for r in conn.execute(
            "SELECT areas FROM sp_divisions WHERE source='votesmotion'")
            if has_area(r[0], area))
        out.append("* **Holyrood**: {0} classified division(s); see below.".format(n))
    nq = sum(1 for r in conn.execute(
        "SELECT areas FROM ni_items WHERE kind='question'")
        if has_area(r[0], area))
    out.append("* **NI**: watching brief only -- {0} question(s), no bill, "
               "no division on this ground.".format(nq))
    out.append("")


def westminster(conn, area, out):
    out.append("## Westminster\n")
    rows_all = conn.execute(
        "SELECT * FROM bills_board ORDER BY status DESC, title").fetchall()
    matched_titles = {r["title"] for r in rows_all if has_area(r["areas"], area)}
    for r in rows_all:
        # Closed rows carry areas=None; a fallen predecessor of a matched live
        # bill (same title, e.g. the Lords TIA bill lost at prorogation) is
        # part of this issue's story and is pulled in by title.
        if not (has_area(r["areas"], area) or
                (r["status"] == "closed" and r["title"] in matched_titles)):
            continue
        note = " -- {0}".format(r["closed_note"]) if r["closed_note"] else ""
        out.append("* **{0}** ({1}) -- {2}, {3}{4}".format(
            r["title"], r["house"], r["stage"], r["status"], note))
    # full_roster=True is what makes `house` filter: with False the function
    # returns every ledger-active member of EITHER House (documented in its
    # docstring, missed on first use -- the gradient summed to 1,135).
    rows = stance.suggest_rows(conn, area, full_roster=True, house="Commons")
    tally = {c: 0 for c in stance.COLUMNS}
    for r in rows:
        tally[r["column"]] += 1
    out.append("\nCommons 5CA gradient (Claude-scored ledger, human overrides): "
               + "  ".join("{0} x{1}".format(c, tally[c]) for c in stance.COLUMNS))
    half = (datetime.date.today() - datetime.timedelta(days=180)).isoformat()
    deb = sum(1 for r in conn.execute(
        "SELECT areas FROM mp_events WHERE kind='debate' AND date >= ?", (half,))
        if has_area(r[0], area))
    pq = sum(1 for r in conn.execute(
        "SELECT areas FROM mp_events WHERE kind='pq' AND date >= ?", (half,))
        if has_area(r[0], area))
    out.append("\nLast six months: {0} debate contributions, {1} written "
               "questions on this ground.".format(deb, pq))
    acts = [r for r in conn.execute(
        "SELECT title, deadline, priority_tag FROM items "
        "WHERE priority_tag IS NOT NULL") if has_area(r["title"], -1) is False
        and False]  # deadlines handled generically below
    for r in conn.execute("SELECT title, deadline, priority_tag, issue_areas "
                          "FROM items WHERE deadline IS NOT NULL"):
        if has_area(r["issue_areas"], area):
            out.append("* [{0}] {1} -- deadline {2}".format(
                r["priority_tag"] or "-", r["title"][:80], r["deadline"]))
    out.append("\nFull sheet: `python3 tools/make_5ca.py {0}`\n".format(area))


def holyrood(conn, area, out):
    import sp_5ca
    out.append("## Holyrood (watching brief -- never published)\n")
    for r in conn.execute("SELECT * FROM sp_bills ORDER BY latest_stage_date DESC"):
        if not has_area(r["areas"], area):
            continue
        out.append("* **{0}** -- latest stage: {1} on {2}".format(
            r["name"], r["latest_stage"], r["latest_stage_date"]))
    out.append("\n**Divisions with confirmed meaning lines** "
               "(every MSP's position held):\n")
    entries = sp_5ca.load_stance(section="divisions")
    for r in conn.execute(
            "SELECT reference, title, dated, vote_for, vote_against, result "
            "FROM sp_divisions WHERE source='votesmotion' AND tier=1 "
            "ORDER BY dated"):
        d = conn.execute("SELECT areas FROM sp_divisions WHERE reference=?",
                         (r["reference"],)).fetchone()
        if not has_area(d[0], area):
            continue
        e = entries.get(r["reference"])
        if e and not e.get("draft") and (e.get("aye") is not None
                                         or e.get("no") is not None):
            mark = "places voters"
        elif e:
            mark = "NOT PLACEABLE (reasoning in config/sp_stance.yaml)"
        else:
            mark = "evidence only"
        out.append("* {0}  {1} -- {2} aye / {3} no, {4}  [{5}]".format(
            r["dated"], (r["title"] or "")[:58], r["vote_for"],
            r["vote_against"], r["result"], mark))
    ors = conn.execute(
        "SELECT COUNT(*) FROM sp_divisions WHERE source='official-report' "
        "AND areas IS NOT NULL AND areas != '[]' AND areas LIKE ?",
        ("%{0}%".format(area),)).fetchone()[0]
    if ors:
        out.append("\nPlus {0} bill-amendment division(s) from the Official "
                   "Report on this ground -- AGGREGATE ONLY (no roll-call is "
                   "published anywhere; question closed 2026-08-21).".format(ors))
    rows = sp_5ca.build_rows(conn, area,
                             sp_5ca.load_stance(section="divisions"),
                             sp_5ca.load_stance(section="motions"))
    tally = {c: 0 for c in stance.COLUMNS}
    targets = []
    for r in rows:
        tally[r["column"]] += 1
        if r.get("target_shaped"):
            targets.append(r["decision_maker"])
    out.append("\nSP 5CA gradient (129 current MSPs, human-confirmed lines "
               "only): " + "  ".join("{0} x{1}".format(c, tally[c])
                                     for c in stance.COLUMNS))
    if targets:
        out.append("TARGET-SHAPED (chosen acts diverge from whipped votes): "
                   + "; ".join(t[:60] for t in targets))
    q = sum(1 for r in conn.execute(
        "SELECT areas FROM sp_items WHERE kind='question'")
        if has_area(r[0], area))
    sp = sum(1 for r in conn.execute("SELECT areas FROM sp_events")
             if has_area(r[0], area))
    out.append("\n{0} written questions (answers inline) and {1} classified "
               "speech excerpts on this ground.".format(q, sp))
    out.append("Full sheet: `python3 tools/sp_5ca.py --area {0}`\n".format(area))


def ni(conn, area, out):
    out.append("## Northern Ireland Assembly (watching brief -- never "
               "published)\n")
    qs = [r for r in conn.execute(
        "SELECT reference, dated, title, tabler, minister, answer FROM ni_items "
        "WHERE kind='question' AND areas IS NOT NULL ORDER BY dated DESC")
        if has_area(conn.execute("SELECT areas FROM ni_items WHERE reference=?",
                                 (r["reference"],)).fetchone()[0]
                    if r["reference"] else None, area)]
    divs = [r for r in conn.execute(
        "SELECT dated, item_name, amendment_no, areas FROM ni_divisions "
        "WHERE areas IS NOT NULL AND areas != '[]'")
        if has_area(r["areas"], area)]
    out.append("{0} question(s) and {1} classified division(s) on this "
               "ground.".format(len(qs), len(divs)))
    for r in qs[:5]:
        out.append("* {0}  {1} ({2}): \"{3}...\"".format(
            r["dated"], r["reference"], (r["tabler"] or "?"),
            " ".join((r["title"] or "").split())[:90]))
    for r in divs:
        out.append("* DIVISION {0}: {1} (amendment {2})".format(
            r["dated"], (r["item_name"] or "?")[:60], r["amendment_no"]))
    out.append("Monitor: `python3 tools/ni_monitor.py`; sheet: "
               "`python3 tools/ni_5ca.py --area {0}`\n".format(area))


def main():
    if "--area" not in sys.argv:
        print("usage: python3 tools/make_dossier.py --area N")
        return 1
    area = int(sys.argv[sys.argv.index("--area") + 1])
    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    names = intel.area_names(os.path.join(ROOT, "config", "taxonomy.yaml"))
    label = names.get(area, "area-{0}".format(area))
    today = datetime.date.today().isoformat()

    out = ["# Cross-chamber dossier: {0}".format(label),
           "",
           "> Generated {0} by tools/make_dossier.py, read-only over the "
           "store. INTERNAL ONLY --".format(today),
           "> it quotes watching-brief material that must never reach Slack "
           "or the partner site.",
           ""]
    glance(conn, area, out)
    westminster(conn, area, out)
    holyrood(conn, area, out)
    ni(conn, area, out)

    slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
    path = os.path.join(ROOT, "dossiers", "{0}-{1}.md".format(slug, today))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out) + "\n")
    print("dossier -> {0}".format(os.path.relpath(path, ROOT)))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
