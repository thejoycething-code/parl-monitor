#!/usr/bin/env python3
"""The German edition: its own document, and a DM.

    python3 tools/de_monitor.py --edition
    python3 tools/de_monitor.py --edition --dm
    python3 tools/de_monitor.py --dm-full      # the whole edition, as a canvas

Christopher, 2026-09-21: "We will do a section of the monitor separate for
the German team." Not a Westminster section and not the partner site -- its
own file under editions/, in the EU edition's grammar, because Germany is a
different parliament on a different rhythm.

WHAT THIS RENDERS, AND WHAT IT REFUSES TO
-----------------------------------------
Documents and Vorgänge from DIP lead, because that is where the volume is:
five relevant recorded votes across 230 in two legislatures, against 507
Vorgänge on our ground. A monitor led by roll calls would look empty and be
wrong about why.

Recorded votes carry their tallies and their per-Fraktion splits and NO
VERDICT. Not "the House defended life", not "a defeat" -- the direction of a
German division is a signed human judgement, exactly as it is at Westminster
and in the EU, and the Lords inversion is the reason: a division's question
comes from the motion, never from its title. Nothing here derives one.

THE HONESTY NOTE IS NOT DECORATION. The whole German stack is English
machinery reading German text, judged by a model given an English frame,
through config/taxonomy-de.yaml -- an AI first draft that no German speaker
has verified. Each layer is defensible; stacked, they can be confidently
wrong. The note stays on the face of the edition until the German team signs
the taxonomy off, and the edition must not be presented internally as
finished before then.

THE LÄNDER SECTION DISCLOSES ITS OWN THINNESS. Sixteen Land parliaments
publish recorded votes in single digits and have no document layer at all, so
a thin Land section means a thin SOURCE, not a strict filter. Said plainly,
because a reader who assumes the filter is at fault will loosen it.

ONE WRITER AT A TIME on data/parl-monitor.db.
"""

from __future__ import annotations

import datetime
import json
import os
import re
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, degate  # noqa: E402

TAXONOMY = os.path.join(ROOT, "config", "taxonomy-de.yaml")

# Kept in one place so the edition, the DM and any later surface cannot
# drift: the version the note names must be the version the file carries.
TAXONOMY_VERSION = "v0.4"

HONESTY = (
    "> **Read this first.** Every area on this page comes from "
    "`config/taxonomy-de.yaml` {0}, an AI first draft that **no German "
    "speaker has verified**. The text is German and untranslated; the judge "
    "scoring it was given a German frame but reasons in English; the matcher "
    "is the same English-built one Westminster uses. Each layer is "
    "defensible and the stack can still be confidently wrong. Treat a German "
    "area as a weaker claim than an English one, and do not present this "
    "edition as finished until the German team has been through the "
    "taxonomy."
).format(TAXONOMY_VERSION)

LAENDER_NOTE = (
    "The sixteen Land parliaments publish recorded votes in single digits a "
    "year and have **no document layer** -- DIP covers the Bundestag only. A "
    "thin section here is a thin *source*, not a strict filter, so do not "
    "loosen the taxonomy on the strength of it."
)

NO_VERDICT = (
    "**No verdicts.** Tallies and Fraktion splits only. Which way a German "
    "division ran for us is a signed human judgement, never derived from a "
    "title -- the rule the Lords inversion taught."
)


# Migration: collated, never campaigned, shown nowhere. Christopher's
# standing instruction, and a repo-wide rule -- src/partner.py holds the
# original and src/stance.py, src/debateradar.py, src/issuepages.py and
# src/spoke.py each carry the same tuple. Germany is no exception, and the
# German taxonomy shares the English area numbers (a test asserts it), so
# area 11 is Migration in both.
#
# MEASURED, 22 September 2026: this is not hypothetical here. The first
# German triage pass scored 199 items and the top of the list was six
# deportation Vorgänge in a row. Without this rule the German team's first
# edition would have opened on exactly the campaign the org does not run.
HIDDEN_AREAS = (11,)


def area_names():
    from src import intel
    return intel.area_names(TAXONOMY)


def _nums(row):
    try:
        return json.loads(row["areas"] or "[]")
    except (TypeError, ValueError):
        return []


def visible_areas(row):
    """The areas a reader is shown: everything but the collated-only ones."""
    return [a for a in _nums(row) if a not in HIDDEN_AREAS]


def hidden_only(row):
    """Matched, but on collated ground alone -- so it is not rendered.

    A row with migration AND another area still shows, under the other area:
    the rule suppresses the campaign, not the item.
    """
    return bool(_nums(row)) and not visible_areas(row)


def split_hidden(rows):
    """(shown, suppressed) -- never just the shown ones.

    Returned as a pair so every caller has the suppressed count in hand and
    the edition can PRINT it. A filter that drops rows and reports only what
    survived is how real news dies quietly; this repo has paid for that
    lesson more than once and the fix each time was to show the discard.
    """
    shown = [r for r in rows if not hidden_only(r)]
    return shown, len(rows) - len(shown)


def oneline(text):
    """A title on one line. DIP puts a document number on a second line
    ("... Bürgerinitiative ...\nK(2026)3333 endg."), which breaks a markdown
    heading in half and leaves the number floating as body text."""
    return " ".join((text or "").split())


def _clip(text, n):
    """Truncate with an ellipsis. A German title cut mid-word at exactly n
    characters reads as corrupted data rather than as an abbreviation."""
    text = text or ""
    return text if len(text) <= n else text[:n - 1].rstrip() + "\u2026"


def _areas(row, names):
    return ", ".join(names.get(a, str(a)) for a in visible_areas(row))


def _why(row):
    """The judge's why-line, or nothing. Never a fabricated one."""
    try:
        why = row["why_it_matters"]
    except (IndexError, KeyError):
        return ""
    return (" " + why.strip()) if why else ""


def _score(row):
    try:
        return row["triage_score"]
    except (IndexError, KeyError):
        return None


def _band(score):
    if score is None:
        return "unscored"
    return {3: "campaign trigger", 2: "digest", 1: "background"}.get(score, "noise")


def ours(conn, table, datecol, limit=None):
    """Rows on our ground that clear the digest bar, best first.

    An UNSCORED row is shown (degate.FLOOR's contract): a row the judge has
    not reached is not a row the judge rejected, and hiding it would make a
    stalled triage look like a quiet week.

    THE DATE COLUMN IS PASSED IN, not guessed. The first draft of this
    ordered by COALESCE(datum, date, '') so one query could serve both
    shapes -- but de_vorgaenge has no `date` and de_divisions has no
    `datum`, so EVERY call raised, the broad `except` below swallowed it,
    and the edition rendered "0 Vorgänge on our ground" over a store holding
    507. A green run reporting an empty week is the exact failure this file
    exists to refuse, and it got in through the rescue clause rather than
    the logic. Tests/test_de_monitor.py caught it; nothing else would have.
    """
    sql = ("SELECT * FROM {0} WHERE areas IS NOT NULL AND areas != '[]' "
           "AND {1} ORDER BY COALESCE(triage_score, 99) DESC, "
           "{2} DESC".format(table, degate.SHOWN_SQL, datecol))
    try:
        rows = conn.execute(sql).fetchall()
    except sqlite3.OperationalError as exc:
        # ONLY a table this store predates. Any other operational error is a
        # bug in the query above and must be loud: swallowing it is how the
        # empty edition happened.
        if "no such table" not in str(exc):
            raise
        return []
    return rows[:limit] if limit else rows


def fraktion_split(conn, vote_id):
    """Per-Fraktion yes/no/abstain/absent for one division.

    Fraktion discipline is the whole story of a German vote: a bill carried
    with the governing parties whipped against a free-vote minority reads
    nothing like the same tally split down the middle. The tallies alone
    cannot show it.
    """
    rows = conn.execute(
        "SELECT COALESCE(m.party, '(unknown)') AS party, v.position, "
        "COUNT(*) AS n FROM de_votes v LEFT JOIN de_members m "
        "ON m.person_id = v.person_id WHERE v.vote_id = ? "
        "GROUP BY 1, 2", (vote_id,)).fetchall()
    out = {}
    for r in rows:
        out.setdefault(r["party"], {})[r["position"]] = r["n"]
    return out


def _split_line(split):
    parts = []
    for party in sorted(split, key=lambda p: -sum(split[p].values())):
        c = split[party]
        parts.append("{0} {1}/{2}/{3}".format(
            party, c.get("yes", 0), c.get("no", 0),
            c.get("abstain", 0) + c.get("no_show", 0)))
    return " · ".join(parts)


BUNDESTAG = "5"     # abgeordnetenwatch's own parliament id


def divisions(conn, bundestag=True):
    """Recorded votes on our ground, the Bundestag's or the Länder's.

    Split on the parliament id rather than taking a list of Land ids: a Land
    whose collector is added later then appears here the day its votes land,
    instead of being silently absent because nobody updated a list.
    """
    test = "=" if bundestag else "!="
    try:
        return conn.execute(
            "SELECT * FROM de_divisions WHERE parliament {0} ? AND areas "
            "IS NOT NULL AND areas != '[]' AND {1} ORDER BY date DESC".format(
                test, degate.SHOWN_SQL), (BUNDESTAG,)).fetchall()
    except sqlite3.OperationalError as exc:
        if "no such table" not in str(exc):
            raise           # see ours(): a swallowed query bug reads as calm
        return []


# WHERE A VORGANG HAS GOT TO, and therefore whether it is still worth a
# reader's attention. Christopher, 22 September 2026: "The focus should be on
# upcoming items and debates with the weekly canvas, not what's in the past."
#
# MEASURED before it was written. Of 294 non-migration items in the store, 215
# are "Beantwortet" -- answered written questions, finished business -- and
# they were filling the Top lines. 24 are genuinely live. A briefing led by
# the 215 is a briefing about last month.
#
# Ordered MOST IMMINENT FIRST: a Beschlussempfehlung is a recommendation
# tabled for decision, so that item is about to be voted; a fresh referral to
# committee may sit for months.
STAGE_LIVE = (
    "beschlussempfehlung",          # recommendation tabled -- a vote is next
    "in der beratung",              # under active consideration
    "überwiesen",                   # referred to committee
    "noch nicht beraten",           # tabled, not yet debated
    "durchgang im bundesrat",       # through one chamber, on to the other
    "noch nicht beantwortet",       # question asked, answer outstanding
)
STAGE_CONCLUDED = ("beantwortet", "angenommen", "abgelehnt", "verkündet",
                   "für erledigt erklärt", "zurückgezogen")
STAGE_LAPSED = ("ablauf der wahlperiode",)


def stage_of(stand):
    """('live', rank) | ('concluded', 0) | ('lapsed', 0) | ('unknown', 0).

    UNKNOWN IS ITS OWN ANSWER and it is shown with the live items, never
    quietly filed under concluded. DIP's Stand is free text and this list was
    built from one store on one day; the stage this code has never seen is
    exactly the one that would vanish, and a vanished item looks identical to
    an item that was never collected.
    """
    s = (stand or "").strip().lower()
    if not s:
        return ("unknown", 0)
    for i, frag in enumerate(STAGE_LIVE):
        if frag in s:
            return ("live", i)
    for frag in STAGE_LAPSED:
        if frag in s:
            return ("lapsed", 0)
    for frag in STAGE_CONCLUDED:
        if frag in s:
            return ("concluded", 0)
    return ("unknown", 0)


def by_stage(rows):
    """Split rows into (live, concluded, lapsed) with live ordered by how
    close each is to a decision, then by score, then most recent."""
    live, concluded, lapsed = [], [], []
    for r in rows:
        kind, rank = stage_of(r["stand"] if "stand" in r.keys() else None)
        if kind == "concluded":
            concluded.append(r)
        elif kind == "lapsed":
            lapsed.append(r)
        else:
            live.append((rank if kind == "live" else len(STAGE_LIVE), r))
    live.sort(key=lambda x: (x[0], -(_score(x[1]) or 0),
                             -(len(x[1]["datum"] or ""))))
    return [r for _, r in live], concluded, lapsed


def edition_number(today):
    """Which edition this is, counted from the editions actually written.

    Deterministic on a re-render: today's date is included in the sort, so
    rendering the same week twice gives the same number rather than walking
    it up one each time.
    """
    import glob
    dates = {os.path.basename(f)[len("de-monitor-"):-len(".md")]
             for f in glob.glob(os.path.join(ROOT, "editions",
                                             "de-monitor-*.md"))}
    dates.add(today)
    return sorted(dates).index(today) + 1


def _dip(vorgang_id, titel=None):
    """A DIP permalink that actually opens (Christopher, 23 September 2026:
    "I get page not found when clicking links in the weekly digest").

    DIP's route is /vorgang/<slug>/<id>, and /vorgang/<id> with no slug
    segment silently bounces to the DIP home page -- it answers 200 and
    renders an SPA shell, so curl saw success and a reader saw nothing. That
    is why three canvases shipped with dead links: nothing a script could
    check was wrong.

    VERIFIED IN A BROWSER, on two ids: the slug is IGNORED. /vorgang/x/336554
    renders the right Vorgang. The id resolves it; the segment merely has to
    exist. A slug is generated anyway so a pasted link reads as something,
    and because a route that tolerates junk today may not tomorrow.
    """
    slug = re.sub(r"[^a-z0-9]+", "-",
                  (titel or "").lower().replace("ä", "ae").replace("ö", "oe")
                  .replace("ü", "ue").replace("ß", "ss")).strip("-")[:60]
    return "https://dip.bundestag.de/vorgang/{0}/{1}".format(
        slug.rstrip("-") or "vorgang", vorgang_id)


def top_lines(vgs, bt, ld, names, cap=6):
    """LIVE items only. Passed the live list by the caller -- a Top lines
    block led by answered written questions is a briefing about last month.

    The handful that matter, Westminster's grammar: a linked item, its
    why-line, and the thing a reader needs to act -- the stage it has
    reached. Capped, because a Top lines block that lists everything is the
    section it was invented to replace.
    """
    out = []
    for r in vgs:
        if (_score(r) or 0) < 3:
            continue
        why = _why(r).strip()
        out.append("- [{0}]({1}){2}{3}".format(
            oneline(r["titel"]) or "?", _dip(r["vorgang_id"], r["titel"]),
            " - " + why if why else "",
            " (Stage: {0})".format(r["stand"]) if r["stand"] else ""))
    for r in list(bt) + list(ld):
        if (_score(r) or 0) < 3:
            continue
        why = _why(r).strip()
        out.append("- **{0}** {1} - {2} ({3} yes / {4} no){5}".format(
            r["parliament_label"] or r["parliament"], r["date"] or "?",
            oneline(r["label"]) or "?", r["yes"] or 0, r["no"] or 0,
            " - " + why if why else ""))
    return out[:cap]


DECISIONS = os.path.join(ROOT, "config", "decisions-de.yaml")

# Vorgangstyp groupings. Taken from the store's own values rather than a
# guess: "Verordnung" returns nothing from DIP, the German for a statutory
# instrument is Rechtsverordnung, and the questions come in four flavours.
BILL_TYPES = ("Gesetzgebung",)
SI_TYPES = ("Rechtsverordnung",)
QUESTION_TYPES = ("Schriftliche Frage", "Kleine Anfrage", "Mündliche Frage",
                  "Große Anfrage")

MOVEMENT_NOTE = (
    "*Movement is measured between COLLECTIONS, not from the Bundestag's own "
    "record: a Vorgang reads \"not seen to move\" until this monitor has "
    "observed it at two different stages. On a young collector that is most "
    "of them, and it means we have not watched it yet -- not that it has "
    "stood still.*")


def of_type(rows, types):
    return [r for r in rows if (r["vorgangstyp"] or "") in types]


def movement(row):
    """What changed since we last looked, in the Westminster board's words."""
    if row["prev_stand"] and row["prev_stand"] != row["stand"]:
        return "**moved** {0} -> {1}{2}".format(
            row["prev_stand"], row["stand"],
            " on " + row["moved_date"] if row["moved_date"] else "")
    return "not seen to move"


def decisions_block(today, mentions):
    """The decisions the German monitor is waiting on.

    Same machinery as Westminster (src/decisions.py) against its own log, so
    a why-line that calls something an open decision cannot recur unlogged
    week after week.
    """
    try:
        from src import decisions as dec
    except ImportError:
        return None
    try:
        rows = dec.collect(dec.load(DECISIONS), mentions, today)
    except (ValueError, OSError) as exc:                    # noqa: BLE001
        # A malformed log must SAY so. Returning None would render an edition
        # with no decisions block, which is what a healthy week looks like.
        return ("## Decisions needed\n\n*The decisions log could not be "
                "read: {0}. Fix `config/decisions-de.yaml`.*\n".format(
                    str(exc)[:120]))
    return dec.render(rows)


# Christopher decided on 2026-09-07 that WESTMINSTER petitions are collated
# and never rendered in the weekly report. This is a different edition and the
# entire point of the section is that Germany had nothing with a deadline on
# it, so German petitions DO render -- but that is his call to confirm, and
# this is the one line that reverses it.
SHOW_PETITIONS = True


def band(closes, today):
    """Westminster's urgency bands, so a German deadline reads the same way."""
    try:
        days = (datetime.date.fromisoformat(closes)
                - datetime.date.fromisoformat(today)).days
    except (TypeError, ValueError):
        return None, "no date"
    return days, "RED" if days <= 8 else "AMBER" if days <= 21 else "open"


def petitions(conn, today):
    """Open for co-signature, on our ground, closing soonest first."""
    if not SHOW_PETITIONS:
        return []
    try:
        rows = conn.execute(
            "SELECT * FROM de_petitions WHERE closes >= ? AND areas IS NOT "
            "NULL AND areas != '[]' AND {0} ORDER BY closes".format(
                degate.SHOWN_SQL), (today,)).fetchall()
    except sqlite3.OperationalError as exc:
        if "no such table" not in str(exc):
            raise
        return []
    return [r for r in rows if not hidden_only(r)]


def judgments(conn):
    try:
        rows = conn.execute(
            "SELECT * FROM de_judgments WHERE areas IS NOT NULL AND areas != "
            "'[]' AND {0} ORDER BY case_no".format(degate.SHOWN_SQL)).fetchall()
    except sqlite3.OperationalError as exc:
        if "no such table" not in str(exc):
            raise
        return []
    return [r for r in rows if not hidden_only(r)]


def amendments(conn):
    try:
        rows = conn.execute(
            "SELECT * FROM de_amendments WHERE areas IS NOT NULL AND areas != "
            "'[]' AND {0} ORDER BY datum DESC".format(
                degate.SHOWN_SQL)).fetchall()
    except sqlite3.OperationalError as exc:
        if "no such table" not in str(exc):
            raise
        return []
    return [r for r in rows if not hidden_only(r)]


def placements(conn):
    """Where members sit, PER AREA -- never one number for a whole member.

    The first version averaged every score a member had into a single
    figure, and it produced "+2.0 Katrin Göring-Eckardt (Greens)". The score
    was right: she condemned violence against journalists, which genuinely
    aligns with defending free speech. The AVERAGE was the lie -- it read as
    "ally" when it meant "aligned on press freedom", and it is exactly how
    this reader misread it before checking the underlying speech.

    A member can be with us on speech and against us on family, and a
    monitor that collapses those into one number will brief someone into a
    meeting with the wrong idea of who they are talking to. Westminster's
    5CA places members per area for the same reason.
    """
    try:
        rows = conn.execute(
            "SELECT s.speaker, s.party, s.areas, st.stance "
            "FROM de_speeches s JOIN stance st "
            "ON st.ref = 'de-speech:' || s.speech_id "
            "WHERE s.person_id IS NOT NULL").fetchall()
    except sqlite3.OperationalError:
        return []
    acc = {}
    for r in rows:
        for area in visible_areas(r):
            key = (r["speaker"], r["party"], area)
            got = acc.setdefault(key, [])
            got.append(r["stance"])
    out = []
    for (speaker, party, area), scores in acc.items():
        out.append({"speaker": speaker, "party": party, "area": area,
                    "avg": sum(scores) / len(scores), "n": len(scores)})
    out.sort(key=lambda x: (-abs(x["avg"]), -x["n"]))
    return out


def week_ahead(conn, today):
    """Sittings still to come, and how far the feed could actually see.

    Two numbers, not one. The matched sittings are the briefing; the HORIZON
    is the honesty. The Tagesordnungen feed is a rolling window of about
    fifteen items covering the days immediately ahead, so "nothing on our
    ground next month" and "the feed only reaches Friday" produce an
    identical empty section -- and a reader who cannot tell them apart will
    believe the first.
    """
    try:
        rows = conn.execute(
            "SELECT * FROM de_agenda WHERE date >= ? ORDER BY date, time",
            (today,)).fetchall()
        horizon = conn.execute(
            "SELECT MAX(date) FROM de_agenda").fetchone()[0]
    except sqlite3.OperationalError as exc:
        if "no such table" not in str(exc):
            raise
        return [], [], None
    matched = [r for r in rows if not hidden_only(r) and visible_areas(r)]
    return matched, rows, horizon


def speeches(conn, today, days=45):
    """Speeches on our ground, newest first, and the protocols they came from.

    Both are returned. Without the protocol count, "no speeches on our
    ground" and "no sitting day has been read" render as the same empty
    section, and only one of those is news.
    """
    since = (datetime.date.fromisoformat(today)
             - datetime.timedelta(days=days)).isoformat()
    try:
        rows = conn.execute(
            "SELECT * FROM de_speeches WHERE date >= ? AND {0} "
            "ORDER BY date DESC, speech_id".format(degate.SHOWN_SQL),
            (since,)).fetchall()
        read = conn.execute(
            "SELECT COUNT(*), MIN(date), MAX(date) FROM de_protocols "
            "WHERE date >= ?", (since,)).fetchone()
    except sqlite3.OperationalError as exc:
        if "no such table" not in str(exc):
            raise
        return [], (0, None, None)
    return [r for r in rows if not hidden_only(r)], read


def render_edition(conn, today):
    """The German edition in the WESTMINSTER frame (Christopher, 22 September
    2026: "Can it be framed like the Westminster one?").

    The first draft used the EU's grammar -- a heading per item with bulleted
    detail underneath -- which reads as a list of documents rather than a
    briefing. Westminster's shape is a dated header, Top lines capped at six,
    and then TABLES, so a reader scans a column of why-lines instead of
    twenty-five stacked headings. Germany takes the same shape.

    What Germany keeps that Westminster has no need of: the standing note
    that the taxonomy is unverified, the Länder thinness disclosure, and the
    migration suppression count. Those are not decoration and they do not
    move into a footnote.
    """
    names = area_names()
    docs, docs_hidden = split_hidden(ours(conn, "de_documents", "datum"))
    vgs, vgs_hidden = split_hidden(ours(conn, "de_vorgaenge", "datum"))
    bt, bt_hidden = split_hidden(divisions(conn, bundestag=True))
    ld, ld_hidden = split_hidden(divisions(conn, bundestag=False))
    collated = docs_hidden + vgs_hidden + bt_hidden + ld_hidden

    lines = ["# German Monitor",
             "### Week commencing Monday {0} | Edition {1} | TAXONOMY {2} "
             "UNVERIFIED".format(today, edition_number(today),
                                 TAXONOMY_VERSION),
             ""]
    lines.append(HONESTY)
    lines.append("")

    # --- Top lines ---
    live, concluded, lapsed = by_stage(vgs)
    tops = top_lines(live, bt, ld, names)
    lines.append("## Top lines")
    lines.append("")
    if tops:
        lines += tops
    else:
        lines.append("*Nothing scored a campaign trigger this week.*")
    lines.append("")

    # --- Decisions needed, directly under Top lines (Westminster's order) ---
    mentions = [(oneline(r["titel"] or ""), _why(r)) for r in live + concluded]
    block = decisions_block(today, mentions)
    if block:
        lines.append(block)
        lines.append("")

    # --- Week ahead: the only section that names a DATE ---
    ahead, all_ahead, horizon = week_ahead(conn, today)
    lines.append("## Week ahead")
    lines.append("")
    if ahead:
        lines.append("| When | Committee | Open? | Areas | On the agenda |")
        lines.append("|---|---|---|---|---|")
        for r in ahead:
            lines.append("| {0}{1} | [{2}]({3}) | {4} | {5} | {6} |".format(
                r["date"] or "?",
                " " + r["time"] if r["time"] else "",
                (r["committee"] or "?").replace("|", "/"), r["url"],
                r["openness"] or "?", _areas(r, names) or "?",
                " ".join((r["excerpt"] or "-").split())[:160].replace("|", "/")))
        lines.append("")
    else:
        lines.append("*No sitting on our ground in the published agendas.*")
        lines.append("")
    if all_ahead or horizon:
        per_day = {}
        for r in all_ahead:
            per_day[r["date"]] = per_day.get(r["date"], 0) + 1
        lines.append("Sittings published ahead: " + (" · ".join(
            "{0} ({1})".format(d, n) for d, n in sorted(per_day.items()))
            or "none") + ". **The feed reaches {0}** -- it is a rolling "
            "window of the days immediately ahead, not a term calendar, so a "
            "quiet section here may mean the Bundestag has published no "
            "further agendas yet rather than that nothing is coming."
            .format(horizon or "no dated sitting"))
        lines.append("")

    # --- THE DEADLINE SECTION. Germany's only one. ---
    pets = petitions(conn, today)
    if pets or SHOW_PETITIONS:
        lines.append("## Open for co-signature ({0})".format(len(pets)))
        lines.append("")
        lines.append("*The only German section with a DATE TO ACT ON. A "
                     "Bundestag e-petition open for co-signature closes on a "
                     "published day; everything else in this edition reports "
                     "what is happening rather than what can still be done "
                     "about it.*")
        lines.append("")
        if pets:
            lines.append("| Petition | Areas | Closes | Signatures | "
                         "Why it matters |")
            lines.append("|---|---|---|---|---|")
            for r in pets:
                days, flag = band(r["closes"], today)
                lines.append("| [{0}]({1}) | {2} | {3} ({4} days, {5}) | {6} "
                             "| {7} |".format(
                                 oneline(r["title"] or "?").replace("|", "/"),
                                 r["url"] or "", _areas(r, names) or "?",
                                 r["closes"] or "?",
                                 "?" if days is None else days, flag,
                                 r["signatures"] if r["signatures"] is not None
                                 else "?",
                                 _why(r).strip().replace("|", "/") or "-"))
            lines.append("")
        else:
            lines.append("*Nothing on our ground is open for co-signature.*")
            lines.append("")

    # --- Coming up: the live items, most imminent first ---
    lines.append("## Coming up ({0} live)".format(len(live)))
    lines.append("")
    lines.append("*Ordered by how close each is to a decision. A "
                 "Beschlussempfehlung is tabled FOR a vote; a fresh referral "
                 "may sit for months. Concluded and lapsed business is "
                 "counted below, not listed.*")
    lines.append("")
    if not live:
        lines.append("Nothing cleared the bar this week. The watching counts "
                     "below are the proof it was looked at, not a filter's "
                     "silence." if not (docs_hidden + vgs_hidden) else
                     "Nothing to show: the {0} item(s) that matched are on "
                     "migration alone, which is collated and never "
                     "campaigned.".format(docs_hidden + vgs_hidden))
        lines.append("")
    else:
        lines.append("| Vorgang | Areas | Type | Stage | Why it matters |")
        lines.append("|---|---|---|---|---|")
        for r in live[:25]:
            score = _score(r)
            lines.append("| {0}[{1}]({2}) | {3} | {4} | {5} | {6} |".format(
                "**[{0}]** ".format(score) if score is not None else "**[-]** ",
                oneline(r["titel"] or "?").replace("|", "/"),
                _dip(r["vorgang_id"], r["titel"]), _areas(r, names) or "?",
                (r["vorgangstyp"] or "?").replace("|", "/"),
                (r["stand"] or "?").replace("|", "/"),
                _why(r).strip().replace("|", "/") or "-"))
        lines.append("")
        if len(live) > 25:
            lines.append("_...and {0} more live on our ground; the store "
                         "holds them all._".format(len(live) - 25))
            lines.append("")
    if docs:
        lines.append("**Papers behind them** (Drucksachen whose *body* "
                     "matched, not just a title):")
        lines.append("")
        lines.append("| Drucksache | Areas | Why it matters |")
        lines.append("|---|---|---|")
        for r in docs[:15]:
            lines.append("| **[{0}]** {1} | {2} | {3} |".format(
                "-" if _score(r) is None else _score(r),
                oneline(r["titel"] or "?").replace("|", "/"),
                _areas(r, names) or "?",
                _why(r).strip().replace("|", "/") or "-"))
        lines.append("")

    # --- Written questions: 216 on our ground and never shown until now ---
    qs = of_type(live + concluded, QUESTION_TYPES)
    if qs:
        top_qs = [r for r in qs if (_score(r) or 0) >= 3]
        lines.append("## Written and oral questions ({0})".format(len(qs)))
        lines.append("")
        lines.append("*A question is a position stated on the record, and an "
                     "ANSWER is the government stating one back. Scored 3 "
                     "below; the rest are counted by type.*")
        lines.append("")
        if top_qs:
            lines.append("| Question | Type | Areas | Stage | Why it matters |")
            lines.append("|---|---|---|---|---|")
            for r in top_qs[:12]:
                lines.append("| [{0}]({1}) | {2} | {3} | {4} | {5} |".format(
                    oneline(r["titel"] or "?").replace("|", "/"),
                    _dip(r["vorgang_id"], r["titel"]),
                    (r["vorgangstyp"] or "?").replace("|", "/"),
                    _areas(r, names) or "?",
                    (r["stand"] or "?").replace("|", "/"),
                    _why(r).strip().replace("|", "/") or "-"))
            lines.append("")
            if len(top_qs) > 12:
                lines.append("_...and {0} more scored 3._".format(
                    len(top_qs) - 12))
                lines.append("")
        by_type = {}
        for r in qs:
            by_type[r["vorgangstyp"] or "?"] = by_type.get(
                r["vorgangstyp"] or "?", 0) + 1
        lines.append("By type: " + " · ".join(
            "{0} ({1})".format(k, v)
            for k, v in sorted(by_type.items(), key=lambda x: -x[1])) + ".")
        lines.append("")

    # --- Active bills board ---
    bills = of_type(live + concluded, BILL_TYPES)
    if bills:
        lines.append("## Active bills board ({0})".format(len(bills)))
        lines.append("")
        lines.append("| Bill | Brought by | Areas | Stage | Movement | "
                     "Why it matters |")
        lines.append("|---|---|---|---|---|---|")
        for r in bills:
            lines.append("| [{0}]({1}) | {2} | {3} | {4} | {5} | {6} |".format(
                oneline(r["titel"] or "?").replace("|", "/"),
                _dip(r["vorgang_id"], r["titel"]),
                (r["initiative"] or "?").replace("|", "/"),
                _areas(r, names) or "?",
                (r["stand"] or "?").replace("|", "/"),
                movement(r),
                _why(r).strip().replace("|", "/") or "-"))
        lines.append("")
        lines.append(MOVEMENT_NOTE)
        lines.append("")

    # --- Amendments to those bills ---
    amds = amendments(conn)
    if amds:
        lines.append("## Amendments ({0})".format(len(amds)))
        lines.append("")
        lines.append("| Moved | By | To which bill | Areas | Amendment |")
        lines.append("|---|---|---|---|---|")
        for r in amds[:15]:
            bill = oneline(r["vorgang_titel"] or "?").replace("|", "/")
            if r["inherited"]:
                # DISCLOSED: an Änderungsantrag's own title is procedure, so
                # nearly all of these are on our ground because of the BILL
                # they amend, not because of anything they say.
                bill += " _(areas from the bill, not the amendment)_"
            lines.append("| {0} | {1} | {2} | {3} | [{4}]({5}) |".format(
                r["datum"] or "?",
                oneline(r["urheber"] or "?").replace("|", "/"), bill,
                _areas(r, names) or "?",
                r["doc_id"].replace("drucksache:", "Drs. "),
                r["url"] or ""))
        lines.append("")

    # --- Secondary legislation ---
    sis = of_type(live + concluded, SI_TYPES)
    if sis:
        lines.append("## Secondary legislation ({0})".format(len(sis)))
        lines.append("")
        lines.append("| Instrument | Areas | Stage | Why it matters |")
        lines.append("|---|---|---|---|")
        for r in sis:
            lines.append("| [{0}]({1}) | {2} | {3} | {4} |".format(
                oneline(r["titel"] or "?").replace("|", "/"),
                _dip(r["vorgang_id"], r["titel"]),
                _areas(r, names) or "?",
                (r["stand"] or "?").replace("|", "/"),
                _why(r).strip().replace("|", "/") or "-"))
        lines.append("")

    # --- Concluded and lapsed: counted, and the notable ones named ---
    # NOT dropped. A bill that PASSED is finished business and still the most
    # important thing that happened, so anything the judge scored 3 is named
    # even though it is over; the rest are a count. Silence here would mean a
    # law could be adopted and never appear in any edition.
    if concluded or lapsed:
        lines.append("## Concluded and lapsed ({0} concluded, {1} lapsed)"
                     .format(len(concluded), len(lapsed)))
        lines.append("")
        notable = [r for r in concluded + lapsed if (_score(r) or 0) >= 3]
        if notable:
            lines.append("*Closed business, so it is below Coming up. An "
                         "answered written question is here because the "
                         "ANSWER is new -- it is the government stating a "
                         "position on the record, which is worth reading "
                         "even though the question itself is finished.*")
            lines.append("")
            lines.append("| Outcome | Vorgang | Areas | Why it mattered |")
            lines.append("|---|---|---|---|")
            for r in notable[:6]:
                lines.append("| {0} | [{1}]({2}) | {3} | {4} |".format(
                    (r["stand"] or "?").replace("|", "/"),
                    oneline(r["titel"] or "?").replace("|", "/"),
                    _dip(r["vorgang_id"], r["titel"]), _areas(r, names) or "?",
                    _why(r).strip().replace("|", "/") or "-"))
            if len(notable) > 6:
                lines.append("")
                lines.append("_...and {0} more scored 3 and closed; the "
                             "outcomes below count everything._".format(
                                 len(notable) - 6))
            lines.append("")
        outcomes = {}
        for r in concluded + lapsed:
            outcomes[(r["stand"] or "?")] = outcomes.get(r["stand"] or "?", 0) + 1
        lines.append("Outcomes: " + " · ".join(
            "{0} ({1})".format(k, v) for k, v in
            sorted(outcomes.items(), key=lambda x: -x[1])) + ".")
        lines.append("")

    # --- Recorded votes, as a table. NO VERDICTS. ---
    lines.append("## Bundestag recorded votes ({0})".format(len(bt)))
    lines.append("")
    lines.append(NO_VERDICT)
    lines.append("")
    if not bt:
        lines.append("No recorded vote on our ground. The Bundestag takes "
                     "them in bursts -- 68 in sixteen months -- so a quiet "
                     "week here is normal and is not evidence of anything."
                     if not bt_hidden else
                     "Nothing shown here: all {0} matched Bundestag vote(s) "
                     "are on migration alone, which is collated and never "
                     "campaigned. That is the standing rule removing them, "
                     "NOT the House being quiet.".format(bt_hidden))
        lines.append("")
    else:
        lines.append("| Date | Vote | Areas | House's result | Tally | "
                     "By Fraktion (yes/no/other) |")
        lines.append("|---|---|---|---|---|---|")
        for r in bt:
            split = fraktion_split(conn, r["vote_id"])
            label = oneline(r["label"] or "?").replace("|", "/")
            if r["inherited_from"]:
                # DISCLOSED in the row itself: a terse vote label that matched
                # nothing took its ground from the paper it voted on, and a
                # reader is entitled to know the classification is second-hand.
                label += " _(areas inherited from {0})_".format(
                    r["inherited_from"])
            lines.append("| {0} | {1} | {2} | {3} | {4}/{5}/{6}/{7} | {8} |"
                         .format(r["date"] or "?", label,
                                 _areas(r, names) or "?",
                                 "accepted" if r["accepted"] else "not accepted",
                                 r["yes"] or 0, r["no"] or 0,
                                 r["abstain"] or 0, r["absent"] or 0,
                                 _split_line(split).replace("|", "/") or "-"))
        lines.append("")
        lines.append("*Tally is yes/no/abstain/absent. The result is the "
                     "House's own, never derived from the tallies.*")
        lines.append("")

    # --- Karlsruhe ---
    jud = judgments(conn)
    if jud:
        lines.append("## Before the Constitutional Court ({0})".format(
            len(jud)))
        lines.append("")
        lines.append("*Cases the Bundesverfassungsgericht has listed to "
                     "decide. The court publishes a STAGE, never a judgment "
                     "date, so this says what is coming and cannot say when.*")
        lines.append("")
        lines.append("| Case | Senate | Areas | Stage | What it is about |")
        lines.append("|---|---|---|---|---|")
        for r in jud[:12]:
            lines.append("| {0} | {1} | {2} | {3} | {4} |".format(
                r["case_no"], (r["senat"] or "?").replace("|", "/"),
                _areas(r, names) or "?",
                oneline(r["stage"] or "?").replace("|", "/"),
                oneline(r["subject"] or "?")[:170].replace("|", "/")))
        lines.append("")

    # --- Who spoke, on our issues ---
    sp, (protos, first_read, last_read) = speeches(conn, today)
    lines.append("## Parliamentarians on our issues ({0})".format(len(sp)))
    lines.append("")
    if sp:
        lines.append("| Date | Member | Fraktion | Areas | What they said |")
        lines.append("|---|---|---|---|---|")
        for r in sp[:20]:
            who = oneline(r["speaker"] or "?")
            if r["person_id"] is None:
                # DISCLOSED. An unattributed speaker is usually a minister
                # without a Bundestag mandate or a member who has not voted
                # in a division we hold -- but the reader is entitled to know
                # the name was not matched to anyone, rather than assume it
                # was.
                who += " _(not matched to a member)_"
            lines.append("| {0} | {1} | {2} | {3} | {4} |".format(
                r["date"] or "?", who.replace("|", "/"),
                (r["party"] or "-").replace("|", "/"),
                _areas(r, names) or "?",
                " ".join((r["excerpt"] or "-").split())[:190].replace("|", "/")))
        lines.append("")
        if len(sp) > 20:
            lines.append("_...and {0} more in the window._".format(len(sp) - 20))
            lines.append("")
    else:
        lines.append("*No speech on our ground in the protocols read.*")
        lines.append("")
    place = placements(conn)
    if place:
        lines.append("**Where members sit, from their own words** (+2 ally "
                     ".. -2 opponent), PER AREA:")
        lines.append("")
        lines.append("| Member | Fraktion | Area | Stance | Speeches |")
        lines.append("|---|---|---|---|---|")
        for r in place[:12]:
            lines.append("| {0} | {1} | {2} | {3:+.1f} | {4} |".format(
                oneline(r["speaker"] or "?").replace("|", "/"),
                (r["party"] or "-").replace("|", "/"),
                names.get(r["area"], str(r["area"])), r["avg"], r["n"]))
        lines.append("")
        lines.append("*Per area, never one number for a member. A member can "
                     "be with us on free speech and against us on family, and "
                     "a single average would brief you into the room with the "
                     "wrong idea of who you are meeting. A placement resting "
                     "on ONE speech is an anecdote, not a position; the count "
                     "is there so you can tell.*")
        lines.append("")
    lines.append("Sitting days read: **{0}**{1}. A speech is stored only when "
                 "it matches the taxonomy -- the rest are counted, never "
                 "kept, because a hundred speeches a sitting day would be a "
                 "copy of the Bundestag rather than a monitor.".format(
                     protos,
                     " ({0} to {1})".format(first_read, last_read)
                     if first_read else ""))
    lines.append("")

    # --- The Länder ---
    seen = conn.execute("SELECT COUNT(DISTINCT parliament) FROM de_divisions "
                        "WHERE parliament != ?", (BUNDESTAG,)).fetchone()[0]
    lines.append("## The Länder ({0} on our ground, {1} parliaments "
                 "collected)".format(len(ld), seen))
    lines.append("")
    lines.append(LAENDER_NOTE)
    lines.append("")
    if ld:
        lines.append("| Land | Date | Vote | Tally | Why it matters |")
        lines.append("|---|---|---|---|---|")
        for r in ld:
            lines.append("| {0} | {1} | {2} | {3} yes / {4} no | {5} |".format(
                r["parliament_label"] or r["parliament"], r["date"] or "?",
                oneline(r["label"] or "?").replace("|", "/"),
                r["yes"] or 0, r["no"] or 0,
                _why(r).strip().replace("|", "/") or "-"))
    else:
        lines.append("Nothing on our ground in the Land votes collected.")
    lines.append("")

    # --- Watching, and what the bar hid ---
    def counted(table):
        try:
            total = conn.execute("SELECT COUNT(*) FROM {0}".format(table)).fetchone()[0]
            matched = conn.execute(
                "SELECT COUNT(*) FROM {0} WHERE areas IS NOT NULL AND "
                "areas != '[]'".format(table)).fetchone()[0]
            below = conn.execute(
                "SELECT COUNT(*) FROM {0} WHERE areas IS NOT NULL AND areas "
                "!= '[]' AND triage_score IS NOT NULL AND triage_score < "
                "{1}".format(table, degate.FLOOR)).fetchone()[0]
            unscored = conn.execute(
                "SELECT COUNT(*) FROM {0} WHERE areas IS NOT NULL AND areas "
                "!= '[]' AND triage_score IS NULL".format(table)).fetchone()[0]
            return total, matched, below, unscored
        except sqlite3.OperationalError:
            return 0, 0, 0, 0

    lines.append("## Watching")
    lines.append("")
    lines.append("| Source | Collected | On our ground | Judged below the bar "
                 "| Not yet judged |")
    lines.append("|---|---|---|---|---|")
    pending = 0
    for table, label in (("de_vorgaenge", "Vorgänge (DIP)"),
                         ("de_documents", "Drucksachen (DIP)"),
                         ("de_divisions", "Recorded votes")):
        total, matched, below, unscored = counted(table)
        pending += unscored
        lines.append("| {0} | {1} | {2} | {3} | {4} |".format(
            label, total, matched, below, unscored))
    lines.append("")
    lines.append("*Drucksachen* read 0 because the weekly runs "
                 "`de_documents.py --mode terms`, which drives DIP from the "
                 "tier-1 German terms and writes Vorgänge only. The body-text "
                 "layer is `--mode window`, which is not scheduled. That zero "
                 "is a configuration choice, not a collector that failed.")
    lines.append("")
    lines.append("*Judged below the bar* is the deliberate discard: the judge "
                 "read it and scored it 0 or 1. *Not yet judged* is not a "
                 "discard at all -- those rows are SHOWN above, unscored, "
                 "because a row the judge has not reached is not a row the "
                 "judge rejected.")
    if collated:
        lines.append("")
        lines.append("**{0} item(s) matched on migration alone** and are "
                     "collated, never campaigned (Christopher's standing "
                     "instruction), so they are not shown above. They are in "
                     "the store. An item carrying migration AND another area "
                     "does appear, under the other area.".format(collated))
    if pending:
        lines.append("")
        lines.append("**{0} matched row(s) await the judge.** Run "
                     "`python3 tools/de_triage.py`.".format(pending))
    lines.append("")

    gaps = conn.execute("SELECT feed, detail FROM gaps WHERE feed LIKE 'de-%' "
                        "AND edition = ?", (today,)).fetchall()
    lines.append("Gaps: none." if not gaps else "Gaps: " + "; ".join(
        "{0}: {1}".format(g["feed"], g["detail"]) for g in gaps))
    lines.append("")

    path = os.path.join(ROOT, "editions", "de-monitor-{0}.md".format(today))
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    return path


def dm_summary(conn, today):
    """The German week in one Slack message, sent as a DM.

    The channel is deliberately not posted. Scored items lead, the counts keep
    it honest, the edition file carries the rest -- and the honesty note comes
    with it, because a DM is the surface most likely to be forwarded without
    the edition attached.
    """
    names = area_names()
    scored = []
    for table, datecol, titlecol in (("de_vorgaenge", "datum", "titel"),
                                     ("de_documents", "datum", "titel"),
                                     ("de_divisions", "date", "label")):
        try:
            rows = conn.execute(
                "SELECT * FROM {0} WHERE areas IS NOT NULL AND areas != '[]' "
                "AND triage_score IS NOT NULL".format(table)).fetchall()
        except Exception:                                   # noqa: BLE001
            continue
        for r in rows:
            if hidden_only(r):
                continue        # migration alone: collated, never campaigned
            scored.append((r["triage_score"], r[datecol] or "",
                           r[titlecol] or "?", r["why_it_matters"] or "",
                           _areas(r, names)))
    # Highest score first, then the MOST RECENT. The first draft sorted
    # (-score, date) ascending, which put the oldest item at the top: a
    # weekly DM led with six Vorgänge from 2024.
    scored.sort(key=lambda x: (x[0] or 0, x[1] or ""), reverse=True)

    # One story, one line: a division and the paper it voted on share a
    # subject, and two lines for one story reads as two findings.
    seen, deduped = set(), []
    for item in scored:
        key = (item[2] or "").lower()[:55]
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    scored = deduped

    lines = [":de: *German Monitor - week commencing {0}*".format(today), ""]
    lines.append("_Areas come from an AI-drafted German taxonomy ({0}) that "
                 "no German speaker has verified. Treat a German area as a "
                 "weaker claim than an English one._".format(TAXONOMY_VERSION))
    lines.append("")

    top = [s for s in scored if (s[0] or 0) >= degate.FLOOR]
    if top:
        lines.append("*On our ground:*")
        for score, date, title, why, areas in top[:6]:
            lines.append("• *[{0}]* {1} ({2})".format(
                score, _clip(oneline(title), 90), date or "?"))
            if why:
                lines.append("   _{0}_".format(why))
    else:
        lines.append("_Nothing cleared the digest bar this week._")

    try:
        bt = conn.execute(
            "SELECT COUNT(*) FROM de_divisions WHERE parliament = ?",
            (BUNDESTAG,)).fetchone()[0]
        vg = conn.execute(
            "SELECT COUNT(*), SUM(areas IS NOT NULL AND areas != '[]') "
            "FROM de_vorgaenge").fetchone()
        lines.append("")
        lines.append("{0} Vorgänge held, {1} on our ground; {2} Bundestag "
                     "recorded votes collected. Full edition: "
                     "`editions/de-monitor-{3}.md`.".format(
                         vg[0] or 0, int(vg[1] or 0), bt, today))
    except Exception as exc:                                # noqa: BLE001
        # SAY SO. A DM that cannot count is worth knowing about; the EU
        # monitor swallowed exactly this and read as "nothing to report".
        lines.append("")
        lines.append(":grey_question: counts unavailable: {0}".format(
            str(exc)[:120]))

    try:
        pending = 0
        for table in ("de_vorgaenge", "de_documents", "de_divisions"):
            pending += conn.execute(
                "SELECT COUNT(*) FROM {0} WHERE areas IS NOT NULL AND areas "
                "!= '[]' AND triage_score IS NULL".format(table)).fetchone()[0]
        if pending:
            lines.append("")
            lines.append(":warning: *{0} matched row(s) await the judge* - "
                         "they render unscored rather than hidden, but "
                         "nothing has said whether they matter.".format(
                             pending))
    except Exception as exc:                                # noqa: BLE001
        lines.append("")
        lines.append(":grey_question: triage backlog uncountable: {0}".format(
            str(exc)[:120]))

    return "\n".join(lines)


def main():
    conn = db.init_db(db.connect(os.path.join(ROOT, "data",
                                              "parl-monitor.db")))
    today = datetime.date.today().isoformat()
    if "--edition" in sys.argv:
        print("edition: {0}".format(render_edition(conn, today)))
    if "--dm-full" in sys.argv:
        # The WHOLE edition, as a Slack canvas shared with the DM recipient
        # alone (Christopher, 22 September 2026: "Dm the full edition"). A
        # canvas rather than a message because the edition is 14k characters
        # of markdown with headings and a table: pasted into chat it is
        # truncated and its structure is lost, and the repo's rule is that
        # files go to Drive, not Slack. Same mechanism the EU full edition
        # uses. The channel is NOT given access.
        from src import publish
        path = os.path.join(ROOT, "editions",
                            "de-monitor-{0}.md".format(today))
        if not os.path.exists(path):
            path = render_edition(conn, today)
        with open(path, encoding="utf-8") as fh:
            markdown = fh.read()
        lead = (":de: *German Monitor - week commencing {0}* - the full "
                "edition, shared with you alone.\n\n_Areas come from an "
                "AI-drafted German taxonomy ({1}) that no German speaker has "
                "verified._".format(today, TAXONOMY_VERSION))
        print("dm-full: {0}".format(publish.slack_preview_canvas(
            publish.load_secrets(),
            "German Monitor - week commencing {0}".format(today),
            markdown, lead)))

    if "--dm" in sys.argv:
        # The channel is deliberately NOT posted: this goes to Christopher
        # alone until he says otherwise, the same hold the EU edition is
        # under.
        from src import publish
        print("dm: {0}".format(publish.slack_dm(publish.load_secrets(),
                                                dm_summary(conn, today))))
    if not {"--edition", "--dm", "--dm-full"} & set(sys.argv):
        print(dm_summary(conn, today))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
