"""One page per campaign area: everything the German monitor holds on it.

Christopher, 24 September 2026: "Build the issue pages." Westminster has had
them since 7 September; Germany had no way to answer "what have we seen on
surrogacy in the Bundestag since May?" without a query.

Each page is that answer, built from the store and read only:

  * the bills on our ground and what stage they have reached;
  * what the judge scored 2 or 3 in the window, dated, with its line;
  * members who have SPOKEN on the area, their stance placement, their seat
    and whether they hold it directly or from a list;
  * committee reports and laid papers on the area;
  * cases the Constitutional Court has listed;
  * e-petitions still open, with their closing dates;
  * recorded votes with tallies and no verdicts.

MIGRATION HAS NO PAGE, as at Westminster: collated, never campaigned.

THESE ARE NOT PUBLISHED, AND THAT IS DELIBERATE
-----------------------------------------------
Westminster's pages are written into partner_site/, which the Monday publish
deploys to Vercel production -- anything placed there goes live. The German
pages were held back while the taxonomy was an unverified draft. Christopher
signed it off on 29 September 2026 and said "publish the Germany issue pages"
on 2 October, so PUBLISH_TO_SITE is True: the pages go into partner_site/ as
HTML (de-issue-<area>.html and de-issues.html, through the same
src/partner.to_html shell as Westminster's issue pages) and deploy with the
partner site, which sits behind its passphrase. Set it False to stop; the
Markdown copies in docs/de-issues/ are what the unpublished build writes.
The note on who signed the taxonomy off stays on every page either way.

NO STANCE PLACEMENT OF AN INDIVIDUAL IS PRESENTED AS A VERDICT. What a member
said is quoted with its score, as the 5CA would; what a division meant is
never inferred.
"""

from __future__ import annotations

import datetime
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

HIDDEN = (11,)              # migration: collated, never campaigned
WINDOW_DAYS = 183           # six months, as Westminster's pages use
TAXONOMY_VERSION = "v0.6"

# FALSE UNTIL THE GERMAN TEAM HAS SIGNED THE TAXONOMY OFF. True writes the
# pages into partner_site/, which the Monday publish deploys to production.
PUBLISH_TO_SITE = True

OUT_DIR = os.path.join(ROOT, "docs", "de-issues")
SITE_DIR = os.path.join(ROOT, "partner_site")

DIRECTION = {2: "with us, strongly", 1: "with us", 0: "neutral or unclear",
             -1: "against us", -2: "against us, strongly"}

UNVERIFIED = (
    "> **The areas on this page come from `config/taxonomy-de.yaml` {0}, "
    "signed off by Christopher on 29 September 2026; the German team may "
    "still refine it.** The text is German and untranslated; the judge that "
    "scored it reasons in English; the matcher was built for English. If an "
    "area looks wrong, say so.").format(TAXONOMY_VERSION)


def _seat(constituency, mandate_won):
    """The seat a member HOLDS, never the one they stood in.

    abgeordnetenwatch's `constituency` is where they were a candidate, and
    mandate_won says whether they won it. Three members share "103 -
    München-Giesing": one won it and two entered from the list. Printing the
    constituency for all of them told a reader that Fabian Jacobi represents
    Köln I -- he stood there and came in on the Landesliste, and a campaign
    mobilising Köln I constituents to write to "their MP" would have been
    writing to the wrong person.
    """
    if mandate_won == "constituency" and constituency:
        return constituency
    if mandate_won == "list":
        return "list ({0})".format(constituency.split(" (")[0]) \
            if constituency else "list"
    return "-"


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")


def _has(row, area):
    try:
        return area in json.loads(row["areas"] or "[]")
    except (TypeError, ValueError, IndexError, KeyError):
        return False


def _rows(conn, sql, params=()):
    try:
        return conn.execute(sql, params).fetchall()
    except Exception:                                       # noqa: BLE001
        return []                      # a table this store predates


def collect(conn, area, today=None, window_days=WINDOW_DAYS):
    """Everything on one area. Read only; nothing here writes."""
    today = today or datetime.date.today()
    since = (today - datetime.timedelta(days=window_days)).isoformat()
    got = {"since": since, "area": area}

    got["bills"] = [r for r in _rows(
        conn, "SELECT * FROM de_vorgaenge WHERE vorgangstyp = 'Gesetzgebung' "
        "AND areas IS NOT NULL AND areas != '[]' ORDER BY datum DESC")
        if _has(r, area)]

    got["scored"] = [r for r in _rows(
        conn, "SELECT * FROM de_vorgaenge WHERE triage_score >= 2 AND datum "
        ">= ? AND areas IS NOT NULL ORDER BY datum DESC", (since,))
        if _has(r, area)]

    # Members who have spoken, with their placement and their seat. The seat
    # is what makes a placement actionable: a directly elected member answers
    # to a constituency, a list member does not.
    got["voices"] = [r for r in _rows(
        conn,
        "SELECT s.speaker, s.party, s.date, s.excerpt, s.areas, st.stance, "
        "m.constituency, m.mandate_won, m.profile_url "
        "FROM de_speeches s "
        "LEFT JOIN stance st ON st.ref = 'de-speech:' || s.speech_id "
        "LEFT JOIN de_members m ON m.person_id = s.person_id "
        "WHERE s.date >= ? AND s.areas IS NOT NULL ORDER BY s.date DESC",
        (since,)) if _has(r, area)]

    got["reports"] = [r for r in _rows(
        conn, "SELECT * FROM de_committee_reports WHERE datum >= ? AND areas "
        "IS NOT NULL ORDER BY datum DESC", (since,)) if _has(r, area)]

    got["court"] = [r for r in _rows(
        conn, "SELECT * FROM de_judgments WHERE areas IS NOT NULL "
        "ORDER BY case_no") if _has(r, area)]

    got["petitions"] = [r for r in _rows(
        conn, "SELECT * FROM de_petitions WHERE closes >= ? AND areas IS NOT "
        "NULL ORDER BY closes", (today.isoformat(),)) if _has(r, area)]

    got["divisions"] = [r for r in _rows(
        conn, "SELECT * FROM de_divisions WHERE areas IS NOT NULL "
        "ORDER BY date DESC") if _has(r, area)]
    return got


def render(data, name, today=None):
    today = today or datetime.date.today()
    x = lambda s: " ".join((s or "").split()).replace("|", "/")   # noqa: E731
    out = ["# {0} - Germany".format(name), "",
           UNVERIFIED, "",
           "Everything the German monitor holds on this area: the bills, what "
           "the judge scored since {0}, who has spoken and how they were "
           "read, the committee papers, Karlsruhe, open petitions and the "
           "recorded votes. Public record and the monitor's own scoring. "
           "Generated {1}.".format(data["since"], today.isoformat()), ""]

    if data["bills"]:
        out += ["## Bills", "", "| Bill | Brought by | Stage |",
                "|---|---|---|"]
        for b in data["bills"]:
            out.append("| {0} | {1} | {2} |".format(
                x(b["titel"]), x(b["initiative"]) or "-", x(b["stand"]) or "?"))
        out.append("")

    if data["scored"]:
        out += ["## In the editions ({0})".format(len(data["scored"])), "",
                "| Date | Score | Item | Why it matters |", "|---|---|---|---|"]
        for it in data["scored"]:
            out.append("| {0} | {1} | {2} | {3} |".format(
                it["datum"] or "?", it["triage_score"], x(it["titel"]),
                x(it["why_it_matters"]) or "-"))
        out.append("")

    if data["voices"]:
        out += ["## Who has spoken ({0})".format(len(data["voices"])), "",
                "*A member's own words, with how the stance pass read them "
                "and the seat they hold. A directly elected member answers to "
                "a constituency; a list member does not, which changes who "
                "can usefully write to them.*", "",
                "| Date | Member | Fraktion | Seat | Read as | Said |",
                "|---|---|---|---|---|---|"]
        for v in data["voices"]:
            seat = _seat(v["constituency"], v["mandate_won"])
            out.append("| {0} | {1} | {2} | {3} | {4} | {5} |".format(
                v["date"] or "?", x(v["speaker"]), x(v["party"]) or "-", seat,
                DIRECTION.get(v["stance"], "not yet scored"),
                x(v["excerpt"])[:150]))
        out.append("")

    if data["reports"]:
        out += ["## Committee reports and laid papers ({0})".format(
            len(data["reports"])), "",
            "| Date | Committee | Paper |", "|---|---|---|"]
        for r in data["reports"]:
            out.append("| {0} | {1} | {2} |".format(
                r["datum"] or "?",
                x(r["committee"]) or "not yet published by DIP",
                x(r["titel"])[:130]))
        out.append("")

    if data["court"]:
        out += ["## Before the Constitutional Court ({0})".format(
            len(data["court"])), "",
            "*The court publishes a stage, never a judgment date.*", "",
            "| Case | Senate | Stage | About |", "|---|---|---|---|"]
        for c in data["court"]:
            out.append("| {0} | {1} | {2} | {3} |".format(
                c["case_no"], x(c["senat"]) or "?", x(c["stage"]) or "?",
                x(c["subject"])[:150]))
        out.append("")

    if data["petitions"]:
        out += ["## Open for co-signature ({0})".format(
            len(data["petitions"])), "",
            "| Closes | Signatures | Petition |", "|---|---|---|"]
        for p in data["petitions"]:
            out.append("| {0} | {1} | {2} |".format(
                p["closes"] or "?",
                p["signatures"] if p["signatures"] is not None else "?",
                x(p["title"])))
        out.append("")

    if data["divisions"]:
        out += ["## Recorded votes ({0})".format(len(data["divisions"])), "",
                "**No verdicts.** Tallies only: which way a German division "
                "ran for us is a signed human judgement.", "",
                "| Date | Parliament | Vote | Tally |", "|---|---|---|---|"]
        for d in data["divisions"]:
            out.append("| {0} | {1} | {2} | {3} yes / {4} no |".format(
                d["date"] or "?", x(d["parliament_label"]) or "?",
                x(d["label"]), d["yes"] or 0, d["no"] or 0))
        out.append("")

    if not any(data[k] for k in ("bills", "scored", "voices", "reports",
                                 "court", "petitions", "divisions")):
        out += ["*Nothing on this area in the store yet. That is what has "
                "been COLLECTED, not what exists: the German collectors are "
                "days old and the Bundestag's record goes back decades.*", ""]
    return "\n".join(out)


def build(conn, area_names, today=None, out_dir=None):
    """A page per area plus an index. Returns the paths written."""
    today = today or datetime.date.today()
    out_dir = out_dir or (SITE_DIR if PUBLISH_TO_SITE else OUT_DIR)
    # The partner site serves HTML; a raw .md there is a text dump.
    as_html = os.path.abspath(out_dir) == os.path.abspath(SITE_DIR)
    ext = ".html" if as_html else ".md"

    def emit(path, markdown, title):
        if as_html:
            from src import partner
            markdown = partner.to_html(markdown, title)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(markdown)

    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    written, index = [], []
    for area in sorted(a for a in area_names if a not in HIDDEN):
        name = area_names.get(area) or str(area)
        data = collect(conn, area, today)
        body = render(data, name, today)
        path = os.path.join(out_dir, "de-issue-{0}{1}".format(slug(name), ext))
        emit(path, body, "{0} - Germany issue page".format(name))
        written.append(path)
        index.append((name, os.path.basename(path), sum(
            len(data[k]) for k in ("bills", "scored", "voices", "reports",
                                   "court", "petitions", "divisions"))))
    lines = ["# German monitor: issues", "", UNVERIFIED, "",
             "One page per campaign area, built from the store on {0}. "
             "Migration has no page: collated, never campaigned.".format(
                 today.isoformat()), "",
             "| Area | Page | Items held |", "|---|---|---|"]
    for name, base, n in index:
        lines.append("| {0} | [{1}]({2}) | {3} |".format(
            name, base, ("/" + base) if as_html else base, n))
    lines.append("")
    if not PUBLISH_TO_SITE:
        lines.append("*Not published. These pages are built into docs/ "
                     "rather than partner_site/, which deploys to production, "
                     "until Christopher decides to publish them. "
                     "`de_issuepages.PUBLISH_TO_SITE` is the one line that "
                     "changes that.*")
        lines.append("")
    path = os.path.join(out_dir, "de-issues" + ext)
    emit(path, "\n".join(lines), "Germany issue pages")
    written.append(path)
    return written
