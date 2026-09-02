"""EU monitor, phase 1: Commission initiatives open for public feedback.

    python3 tools/eu_monitor.py           # pull + classify + print the monitor
    python3 tools/eu_monitor.py --pull    # pull only, no rendering

The European analogue of the devolved consultations collector, built on the
Commission's Better Regulation portal ("Have your say"). Everything the EU
is PROMOTING passes through it: legislative proposals, delegated and
implementing acts, evaluations and fitness checks all take public feedback
there in defined windows -- which makes it the one EU source where the
action-window rule (docs/parl-monitor-devolved-fix.md) transfers unchanged:
open window, stated closing date, open to anyone.

Live-probed 2026-09-01 (data/raw/eu-probe-2026-09-01/): 4,101 initiatives
on the portal, 41 with feedback OPEN via the server-side filter
`feedbackStatus=OPEN` -- one page weekly. The listing carries the current
window's dates; ONE detail fetch per new initiative adds the EN dossier
summary for classification. Classification is the same taxonomy pass the
devolved monitors run, over title + summary.

Separation guarantee, as for every devolved source: this tool writes
eu_consultations ONLY -- never items or mp_events, so nothing here can
reach the published Westminster digest until Christopher wires it in
deliberately.

ONE WRITER AT A TIME on data/parl-monitor.db.
"""

from __future__ import annotations

import datetime
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, filter as filt
from src.http import FetchError, HttpClient

SEARCH = ("https://ec.europa.eu/info/law/better-regulation/brpapi/"
          "searchInitiatives?feedbackStatus=OPEN&language=EN&size=200")
DETAIL = ("https://ec.europa.eu/info/law/better-regulation/brpapi/"
          "groupInitiatives/{0}")
PAGE = "https://ec.europa.eu/info/law/better-regulation/have-your-say/initiatives/{0}"


def iso(hys_date):
    """'2026/08/31 08:24:00' -> '2026-08-31'; None stays None."""
    if not hys_date:
        return None
    return str(hys_date)[:10].replace("/", "-")


def parse_listing(payload):
    """The OPEN-feedback initiatives, one dict each, dates ISO."""
    page = payload.get("initiativeResultDtoPage") or {}
    out = []
    for item in page.get("content") or []:
        cur = next((s for s in item.get("currentStatuses") or []
                    if s.get("isCurrent")), None) or {}
        if cur.get("receivingFeedbackStatus") != "OPEN":
            continue    # the filter is server-side, but never trust it alone
        key = str(int(item["id"]))
        out.append({
            "key": key,
            "reference": item.get("reference"),
            "title": item.get("shortTitle"),
            "url": PAGE.format(key),
            "act_type": item.get("foreseenActType"),
            "topics": [t.get("label") for t in item.get("topics") or []],
            "stage": cur.get("frontEndStage"),
            "opened": iso(cur.get("feedbackStartDate")),
            "closes": iso(cur.get("feedbackEndDate")),
        })
    return out, page.get("totalElements")


def pull(conn, client, today, log=print):
    tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
    wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))
    try:
        listing = client.get_json(SEARCH, "eu-consultations", "open",
                                  archive=False)
    except FetchError as exc:
        conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) "
                     "VALUES (?,?,?)",
                     (today, "eu-consultations", str(exc.cause)))
        conn.commit()
        log("  [gap] eu-consultations: {0}".format(exc.cause))
        return 0, 0, 0
    found, total = parse_listing(listing)
    if total and total > len(found):
        log("  [gap] {0} open initiatives but one page holds {1} -- raise "
            "size or page".format(total, len(found)))
    known = {r[0]: r[1] for r in conn.execute(
        "SELECT key, summary FROM eu_consultations")}
    new = ours = 0
    for c in found:
        summary = known.get(c["key"]) or ""
        if c["key"] not in known or not summary:
            # One detail fetch per new initiative: the EN dossier summary,
            # without which classification would run on the title alone.
            try:
                det = client.get_json(DETAIL.format(c["key"]),
                                      "eu-consultations", "detail",
                                      archive=False)
                summary = (det.get("dossierSummary") or "").strip()
            except FetchError as exc:
                log("  [gap] detail {0}: {1}".format(c["key"], exc.cause))
        res = filt.filter_item(tax, wl, "{0} {1}".format(c["title"], summary))
        areas = res.issue_areas or []
        if areas:
            ours += 1
        if c["key"] not in known:
            new += 1
        conn.execute(
            "INSERT INTO eu_consultations (key, reference, title, url, "
            "summary, act_type, topics, stage, opened, closes, areas, "
            "matched_terms, tier, first_seen, last_seen) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET title=excluded.title, "
            "summary=CASE WHEN excluded.summary != '' THEN excluded.summary "
            "ELSE summary END, act_type=excluded.act_type, "
            "topics=excluded.topics, stage=excluded.stage, "
            "opened=COALESCE(excluded.opened, opened), "
            "closes=COALESCE(excluded.closes, closes), "
            "areas=excluded.areas, matched_terms=excluded.matched_terms, "
            "tier=excluded.tier, last_seen=excluded.last_seen",
            (c["key"], c["reference"], c["title"], c["url"], summary,
             c["act_type"], json.dumps(c["topics"]), c["stage"], c["opened"],
             c["closes"], json.dumps(areas),
             json.dumps(res.matched_terms or []), res.tier, today, today))
    conn.commit()
    return len(found), new, ours


def render(conn, today, out=print):
    """The watching brief: our ground first, then the rest, deadline order.

    Prints EVERY open initiative -- the suppression lesson (never a hidden
    filter): what did not match the taxonomy is listed under its own
    heading, not silently dropped.
    """
    rows = conn.execute(
        "SELECT * FROM eu_consultations WHERE closes >= ? "
        "ORDER BY closes", (today,)).fetchall()
    ours = [r for r in rows if json.loads(r["areas"] or "[]")]
    rest = [r for r in rows if not json.loads(r["areas"] or "[]")]
    out("\nEU MONITOR - initiatives open for public feedback ({0})".format(today))
    out("=" * 68)
    out("\nON OUR GROUND ({0}):".format(len(ours)) if ours
        else "\nON OUR GROUND: none this week.")
    for r in ours:
        days = (datetime.date.fromisoformat(r["closes"])
                - datetime.date.fromisoformat(today)).days
        out("  [{0}] {1}".format(", ".join(
            str(a) for a in json.loads(r["areas"])), r["title"]))
        out("      closes {0} ({1} days) - {2} - {3}".format(
            r["closes"], days, r["act_type"] or "?", r["url"]))
    out("\nWATCHING - no taxonomy match ({0}):".format(len(rest)))
    for r in rest:
        out("  - {0} (closes {1})".format((r["title"] or "?")[:84],
                                          r["closes"]))


def _why(r):
    """The triage judge's line, when the row has been scored."""
    try:
        w = r["why_it_matters"]
        s = r["triage_score"]
    except (IndexError, KeyError):
        return ""
    if not w:
        return ""
    return " **Why it matters:** {0}{1}".format(
        w, " (score {0})".format(s) if s is not None else "")


def render_edition(conn, today):
    """The weekly EU edition, its own document (Christopher, 2026-09-01:
    'a separate one for the EU edition'). Same grammar as the Westminster
    edition -- our ground first with urgency-banded deadlines, then the
    complete watching list, then gaps -- but its own file, because the EU
    is a different parliament on a different rhythm, not a section of
    Westminster's week."""
    from src import intel
    names = intel.area_names(os.path.join(ROOT, "config", "taxonomy.yaml"))
    rows = conn.execute("SELECT * FROM eu_consultations WHERE closes >= ? "
                        "ORDER BY closes", (today,)).fetchall()
    ours = [r for r in rows if json.loads(r["areas"] or "[]")]
    rest = [r for r in rows if not json.loads(r["areas"] or "[]")]
    t = datetime.date.fromisoformat(today)

    def band(closes):
        days = (datetime.date.fromisoformat(closes) - t).days
        flag = "RED" if days <= 8 else "AMBER" if days <= 21 else "open"
        return days, flag

    lines = ["# EU Monitor - week commencing {0}".format(today), ""]
    lines.append("> Commission initiatives open for public feedback on the "
                 "Better Regulation portal, classified with taxonomy v1.5. "
                 "Generated by tools/eu_monitor.py; feedback windows are "
                 "open to anyone, so every item here is actionable by "
                 "definition. An on-our-ground consultation generates a "
                 "Campaigns Brief draft through the normal generator, gated "
                 "by its Asana approval task; good ones are passed to team "
                 "members by hand. No Top lines, no Slack (Christopher, "
                 "2026-09-01).")
    lines.append("")
    lines.append("## On our ground ({0})".format(len(ours)))
    lines.append("")
    if not ours:
        lines.append("Nothing this week matched the taxonomy. The full "
                     "watching list below is the proof it was looked at, "
                     "not a filter's silence.")
        lines.append("")
    for r in ours:
        days, flag = band(r["closes"])
        areas = ", ".join(names.get(a, str(a))
                          for a in json.loads(r["areas"]))
        lines.append("### {0}".format(r["title"]))
        lines.append("")
        lines.append("- **Areas:** {0} | **Closes:** {1} ({2} days, {3}) | "
                     "**Type:** {4}".format(areas, r["closes"], days, flag,
                                            r["act_type"] or "?"))
        if r["summary"]:
            lines.append("- {0}".format(r["summary"][:600]))
        if _why(r):
            lines.append("-{0}".format(_why(r)))
        lines.append("- Respond: {0}".format(r["url"]))
        lines.append("")
    # Coming up in plenary (phase 2b): the foreseen agenda inside 60 days,
    # written by tools/eu_agenda.py. Matched items in full; the rest
    # counted per sitting day -- 65 rows of vineyard votes would bury the
    # one debate that matters, but a count is not suppression.
    ag = conn.execute("SELECT * FROM eu_agenda WHERE date >= ? "
                      "ORDER BY date, activity_id", (today,)).fetchall()
    if ag:
        ag_matched = [r for r in ag if json.loads(r["areas"] or "[]")]
        per_day = {}
        for r in ag:
            per_day[r["date"]] = per_day.get(r["date"], 0) + 1
        lines.append("## Coming up in plenary ({0} days ahead)".format(90))
        lines.append("")
        for r in ag_matched:
            areas = ", ".join(names.get(a, str(a))
                              for a in json.loads(r["areas"]))
            lines.append("- **{0}** - {1} ({2}) - {3}{4}".format(
                r["date"], r["label"],
                (r["activity_type"] or "").replace("PLENARY_", "").lower(),
                areas, " -" + _why(r) if _why(r) else ""))
        if not ag_matched:
            lines.append("Nothing on our ground in the published agendas.")
        lines.append("")
        lines.append("Published agendas checked: " + ", ".join(
            "{0} ({1} items)".format(d, n)
            for d, n in sorted(per_day.items())) + ". Agendas publish "
            "closer to the sitting; later sittings appear as they do.")
        lines.append("")
    # Divisions on our ground (phase 2d, collection only): the roll calls
    # exist in the store for the eventual EU 5CA; the edition names the
    # votes and their tallies. NO verdicts: meanings are signed off per
    # division, never derived from a title (the Lords inversion lesson).
    dv = conn.execute("SELECT * FROM eu_divisions ORDER BY date DESC"
                      ).fetchall()
    if dv:
        lines.append("## Plenary divisions on our ground (last 60 days)")
        lines.append("")
        for r in dv:
            areas = ", ".join(names.get(a, str(a))
                              for a in json.loads(r["areas"] or "[]"))
            n = conn.execute("SELECT COUNT(*) FROM eu_votes WHERE "
                             "vote_id = ?", (r["vote_id"],)).fetchone()[0]
            lines.append("- **{0}** - {1} - {2}-{3}-{4}{5} - {6}{7}".format(
                r["date"], r["label"], r["favor"], r["against"],
                r["abstention"],
                " ({0} recorded positions)".format(n) if n else
                " (totals only, no roll call)", areas,
                " -" + _why(r) if _why(r) else ""))
        lines.append("")
        lines.append("Tallies are favor-against-abstention. These votes "
                     "carry no verdict yet: meanings are signed off per "
                     "division before any MEP is judged on them.")
        lines.append("")
    # Adopted by the Parliament (phase 2c): the last 60 days' resolutions
    # on our ground; the full count keeps the window honest.
    tx = conn.execute("SELECT * FROM eu_texts ORDER BY date DESC").fetchall()
    if tx:
        tx_matched = [r for r in tx if json.loads(r["areas"] or "[]")]
        lines.append("## Adopted by the Parliament (last 60 days)")
        lines.append("")
        for r in tx_matched:
            areas = ", ".join(names.get(a, str(a))
                              for a in json.loads(r["areas"]))
            lines.append("- **{0}** - {1} ({2}) - {3}{4}".format(
                r["date"], r["title"], r["identifier"], areas,
                " -" + _why(r) if _why(r) else ""))
        lines.append("")
        lines.append("{0} of {1} adopted texts in the window matched the "
                     "taxonomy.".format(len(tx_matched), len(tx)))
        lines.append("")
    # Citizens' initiatives (2026-09-02): ECIs on our ground with their
    # signature counts -- a hostile ECI crossing one million validated
    # signatures forces a Commission response, and the weekly delta says
    # which way the ground is moving.
    try:
        ecis = conn.execute("SELECT * FROM eu_ecis WHERE areas != '[]' "
                            "ORDER BY supporters DESC").fetchall()
    except Exception:
        ecis = []
    if ecis:
        lines.append("## Citizens' initiatives on our ground")
        lines.append("")
        for r in ecis:
            delta = ""
            if r["prev_supporters"] is not None and r["supporters"] is not None                     and r["supporters"] != r["prev_supporters"]:
                d = r["supporters"] - r["prev_supporters"]
                delta = " ({0}{1:,} this week)".format("+" if d > 0 else "", d)
            lines.append("- **{0}** - {1} - {2:,} supporters{3} - {4}".format(
                r["status"], (r["title"] or "").replace("|", "/"),
                r["supporters"] or 0, delta, r["support_link"] or ""))
        lines.append("")
    # In committee (2026-09-02): upcoming watched-committee meetings and
    # the taxonomy-matched pipeline documents -- draft reports and opinions
    # live in committee for months before plenary, the deepest forward
    # look there is.
    try:
        mts = conn.execute("SELECT committee, date, COUNT(*) AS n FROM "
                           "eu_cmte_meetings WHERE date >= ? GROUP BY 1, 2 "
                           "ORDER BY date LIMIT 20", (today,)).fetchall()
        cutoff = (datetime.date.fromisoformat(today)
                  - datetime.timedelta(days=548)).isoformat()
        docs = conn.execute("SELECT * FROM eu_cmte_docs WHERE areas != '[]' "
                            "AND date >= ? ORDER BY date DESC LIMIT 12",
                            (cutoff,)).fetchall()
    except Exception:
        mts, docs = [], []
    if mts or docs:
        lines.append("## In committee")
        lines.append("")
        if mts:
            lines.append("Meetings ahead: " + " · ".join(
                "{0} {1}".format(r["committee"], r["date"]) for r in mts))
            lines.append("")
            lines.append("Pipeline documents (drafts and opinions inside 18 "
                         "months) on our ground:")
            lines.append("")
        for r in docs:
            areas_lbl = ", ".join(names.get(a, str(a))
                                  for a in json.loads(r["areas"]))
            lines.append("- **{0}** {1} ({2}) - {3} - {4}".format(
                r["committee"], r["date"], r["work_type"] or "?",
                (r["title"] or "").replace("|", "/"), areas_lbl))
        lines.append("")
    # The dossier board (phase 2a): watched EP procedures with movement,
    # tracked by tools/eu_dossiers.py from config/eu_watchlist.yaml.
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "eu_dossiers", os.path.join(ROOT, "tools", "eu_dossiers.py"))
        eud = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(eud)
        board = eud.board_rows(conn, today)
    except Exception:
        board = []
    if board:
        lines.append("## Dossier board ({0} watched)".format(len(board)))
        lines.append("")
        lines.append("| Dossier | Why we track it | Stage | Movement |")
        lines.append("|---|---|---|---|")
        for b in board:
            lines.append("| [{0}]({1}) {2} | {3} | {4} | {5} |".format(
                b["label"], b["url"],
                (b["title"] or "").replace("|", "/"),
                (b["why"] or "").replace("|", "/").replace("\n", " "),
                b["stage"], b["movement"]))
        lines.append("")
    lines.append("## Watching - no taxonomy match ({0})".format(len(rest)))
    lines.append("")
    lines.append("| Initiative | Type | Closes |")
    lines.append("|---|---|---|")
    for r in rest:
        lines.append("| [{0}]({1}) | {2} | {3} |".format(
            (r["title"] or "?").replace("|", "/"), r["url"],
            r["act_type"] or "?", r["closes"]))
    lines.append("")
    gaps = conn.execute("SELECT detail FROM gaps WHERE feed = "
                        "'eu-consultations' AND edition = ?",
                        (today,)).fetchall()
    lines.append("Gaps: none." if not gaps else
                 "Gaps: " + "; ".join(g["detail"] for g in gaps))
    lines.append("")
    path = os.path.join(ROOT, "editions", "eu-monitor-{0}.md".format(today))
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    return path


def dm_summary(conn, today):
    """The EU week in one Slack message, sent as a DM.

    Christopher, 2026-09-01: hold the channel, DM the proof of concept.
    Triage-scored items lead (the judge's why lines are the substance);
    counts keep it honest; the edition file carries the rest.
    """
    scored = []
    for table, datecol in (("eu_consultations", "closes"),
                           ("eu_agenda", "date"), ("eu_divisions", "date"),
                           ("eu_texts", "date")):
        try:
            for r in conn.execute(
                    "SELECT * FROM {0} WHERE areas != '[]' AND "
                    "triage_score IS NOT NULL".format(table)).fetchall():
                title = (r["title"] if "title" in r.keys() else None) or \
                        (r["label"] if "label" in r.keys() else "?")
                scored.append((r["triage_score"], r[datecol], title,
                               r["why_it_matters"] or ""))
        except Exception:
            continue
    scored.sort(key=lambda x: (-(x[0] or 0), x[1] or ""))
    # One story, one line: a division and its adopted text share a subject;
    # the higher-scored row (first after the sort) represents it.
    seen_titles = set()
    deduped = []
    for item in scored:
        key = (item[2] or "").lower()[:55]
        if key in seen_titles:
            continue
        seen_titles.add(key)
        deduped.append(item)
    scored = deduped
    nc = conn.execute("SELECT COUNT(*), SUM(areas != '[]') FROM "
                      "eu_consultations WHERE closes >= ?",
                      (today,)).fetchone()
    lines = [":eu: *EU Monitor - week commencing {0}*".format(today), ""]
    lines.append("{0} Commission feedback windows open, {1} on our ground. "
                 "Full edition: editions/eu-monitor-{2}.md in the repo."
                 .format(nc[0] or 0, int(nc[1] or 0), today))
    if scored:
        lines.append("")
        lines.append("*Scored by triage (same rubric as Westminster):*")
        for score, date, title, why in scored[:6]:
            lines.append("• *[{0}]* {1} ({2})".format(score, title[:90],
                                                      date or "?"))
            if why:
                lines.append("   _{0}_".format(why))
    board = []
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "eu_dossiers", os.path.join(ROOT, "tools", "eu_dossiers.py"))
        eud = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(eud)
        board = eud.board_rows(conn, today)
    except Exception:
        pass
    if board:
        lines.append("")
        lines.append("*Dossier board:* " + " · ".join(
            "{0} at {1} ({2})".format(b["label"], b["stage"], b["movement"])
            for b in board))
    return "\n".join(lines)


def main():
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    conn = db.init_db(db.connect(os.path.join(ROOT, "data",
                                              "parl-monitor.db")))
    today = datetime.date.today().isoformat()
    n, new, ours = pull(conn, client, today)
    print("eu-consultations: {0} open, {1} new, {2} on our ground.".format(
        n, new, ours))
    if "--edition" in sys.argv:
        print("edition: {0}".format(render_edition(conn, today)))
    elif "--pull" not in sys.argv:
        render(conn, today)
    if "--dm" in sys.argv:
        # The channel is deliberately NOT posted (Christopher, 2026-09-01:
        # hold on publishing the Slack for now); the weekly summary goes to
        # him alone as a DM until he says otherwise.
        from src import publish
        result = publish.slack_dm(publish.load_secrets(),
                                  dm_summary(conn, today))
        print("dm: {0}".format(result))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
