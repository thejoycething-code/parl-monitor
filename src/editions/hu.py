"""Hungary: what became law, from the Magyar Közlöny (src/hu_store.py,
tools/hu_gazette.py). Phase 0 (HU6, 10 October 2026).

A "became law" edition. The Országgyűlés's bills and recorded votes are not
collected: parlament.hu answers us with a CAPTCHA (never solved or worked
around), and its W-API needs a personal token (HU1), so every edition
carries a standing line saying so. What the gazette gives is the end of the
process: each Act, amendment to the Fundamental Law, resolution of the
Országgyűlés, government resolution and decree, ministerial decree and
Constitutional Court (AB) decision, as its contents page lists them, a week
or more after the vote and without positions.

Items: Acts and amendments to the Fundamental Law under "Laws", everything
else under "Gazette notices", each with the Hungarian title verbatim and an
English takeaway built from the designation (what it is, its number, where
it was published) and the title's own legal formula ("... módosításáról":
it amends). No model reads anything (X16). Presidential (KE) and Prime
Minister's (ME) decisions, which are appointments, and the Kúria's
local-government rulings are stored but left out; a watched one is shown.

HU4: an amendment to the Fundamental Law is shown whatever its words, as a
watched item under the rule's own watchlist key, "HU4".

THE PARLIAMENT'S RECORD, FROM KARZAT (HU7, 10 October 2026). Until the W-API
token arrives (HU1), the term's papers, recorded votes and member positions
from 9 May to 28 August 2026 are loaded once from karzat's open data (CC BY
4.0; tools/hu_karzat_backfill.py). They are historical: a weekly edition
shows only the votes and papers DATED in its week, so after 28 August the
weekly editions carry the gazette alone. Where they appear:

  * "Recorded votes": each vote with its tally, the majority it needed, the
    record's own words for the motion and result, the split by group at the
    vote, and the members who voted against their group's majority. A
    bill's amendments and final vote are one group. HU5: a vote on accepting
    a minister's answer to an interpellation counts, on our ground when the
    interpellation is. HU4: every vote on an amendment to the Fundamental
    Law is shown.
  * "New on our ground" (bills, resolutions, reports) and "Questions"
    (interpellations, written and urgent questions), dated by submission.
  * Attribution, wherever such an item appears: a line on the item, the
    standing notice, and the licence and source under Coverage.

The one-off read of the whole backfill, "since 9 May", is
backfill_summary(), run as `python3 tools/hu_karzat_backfill.py --summary`.
"""

from __future__ import annotations

import json

from src import country_edition as ce
from src import hu_store

LAW_TYPES = ("act", "fundamental_law")
GAZETTE_TYPES = ("ogy_resolution", "gov_resolution", "gov_decree", "ministerial_decree",
                 "ab_decision")
HU4 = "HU4"
HU4_ENTRY = {"areas": [], "why": "HU4: every amendment to the Fundamental Law is triaged "
                                 "and read in full, whatever its words (Chris, 10 October 2026)."}
MONTHS = ce.MONTHS

# The title's closing legal formula, folded, and what it says in English.
# First match wins; the more specific formulas come first.
FORMULAS = (
    ("alaptorveny-ellenessegenek megallapitasarol es megsemmisiteserol",
     "It finds a provision or ruling contrary to the Fundamental Law and annuls it"),
    ("alaptorveny-ellenessegenek megallapitasarol",
     "It finds a provision or ruling contrary to the Fundamental Law"),
    ("alkotmanyjogi panasz elutasitasarol", "It rejects a constitutional complaint"),
    ("elutasitasarol", "It rejects a petition"),
    ("visszautasitasarol", "It turns a petition away"),
    ("hatalyon kivul helyezeserol", "It repeals earlier law"),
    ("kihirdeteserol", "It promulgates an international agreement"),
    ("modositasarol", "It amends existing law"),
    ("modositasaval osszefuggo", "It makes the changes that follow from another amendment"),
    ("letrehozasarol", "It establishes a body or scheme"),
    ("megszuneserol", "It ends a body or scheme"),
    ("tamogatasarol", "It provides funding or support"),
    ("vegrehajtasarol", "It implements an Act"),
)


STANDING = ("Bills and recorded votes await the Országgyűlés's API token (HU1): parlament.hu "
            "answers this project with a CAPTCHA, which is never solved or worked around. Until "
            "then this edition reports what became law, from the official gazette, a week or "
            "more after the vote and without positions.")
STANDING_KARZAT = (
    "Bills and recorded votes from the parliament's own feed await its API token (HU1): "
    "parlament.hu answers this project with a CAPTCHA, which is never solved or worked around. "
    "The term's papers and recorded votes from {0} to {1} are loaded once from karzat's open "
    "data ({2}, {3}, CC BY 4.0), derived from the Országgyűlés's record; a week after that "
    "has the official gazette alone: what became law, a week or more after the vote, without "
    "positions.")
KARZAT_ITEM = "From karzat's open data (github.com/abognar-git/karzat), CC BY 4.0."

# karzat's words for what was put, and ours. First match wins.
MOTIONS = (
    ("interpellációs választ", "The vote on accepting the minister's answer to interpellation "
                               "{paper} (HU5: such a vote counts)"),
    ("önálló indítvány minősített többséget igénylő része",
     "The final vote on {paper}, the part needing a qualified majority"),
    ("önálló indítvány egyszerű többséget igénylő része",
     "The final vote on {paper}, the part needing a simple majority"),
    ("önálló indítvány", "The final vote on {paper}"),
    ("összegző módosító javaslat", "The vote on the summary amendment to {paper} (motion {motion})"),
    ("zárószavazás előtti módosító", "A vote on an amendment to {paper} before the final vote"),
    ("zárószavazás elhalasztása", "A vote to postpone the final vote on {paper}"),
    ("bizottsági javaslat túlterjeszkedő",
     "A procedural vote on hearing an amendment to {paper} beyond its scope"),
    ("túlterjeszkedő módosító javaslat", "A vote on an amendment to {paper} beyond its scope "
                                         "(motion {motion})"),
    ("módosító javaslat fenntartása", "A vote on an amendment to {paper} its mover maintained "
                                      "(motion {motion})"),
    ("módosító javaslat", "A vote on amendments to {paper} (motion {motion})"),
    ("sürgősségi javaslat", "A procedural vote to take {paper} as urgent"),
    ("kivételességi javaslat", "A procedural vote to take {paper} in the exceptional procedure"),
    ("házszabályi rendelkezésektől való eltérés",
     "A procedural vote to depart from the standing orders for {paper}"),
)
FINAL = ("önálló indítvány", "interpellációs választ")
NO_GROUP = ("független",)
PAPER_KINDS = {"T": "bill", "H": "resolution", "B": "report", "S": "appointment",
               "Y": "information paper", "I": "interpellation", "K": "written question",
               "A": "urgent question"}
QUESTION_KINDS = ("I", "K", "A")


def karzat_source(conn):
    """The newest karzat load (a hu_sources row), or None."""
    got = ce.rows(conn, "SELECT * FROM hu_sources WHERE name = ? ORDER BY loaded_at DESC, "
                        "source DESC LIMIT 1", (hu_store.KARZAT,))
    return got[0] if got else None


def notice(conn, today, dm):
    """The standing line, in every edition and DM (quiet weeks included);
    with karzat's data loaded, it credits karzat (CC BY 4.0)."""
    src = karzat_source(conn)
    if dm:
        if src:
            return ("_Bills and votes from {0} to {1} from karzat's open data (CC BY 4.0); "
                    "after that, what became law, until the parliament's API token (HU1)._"
                    .format(ce.short_date(src["data_from"]), long_date(src["data_to"])))
        return "_Bills and votes await the parliament's API token (HU1); this is what became law._"
    if src:
        return "> " + STANDING_KARZAT.format(long_date(src["data_from"]),
                                             long_date(src["data_to"]), hu_store.KARZAT,
                                             hu_store.KARZAT_URL)
    return "> " + STANDING


def watchlist(config_dir=None):
    wl = dict(hu_store.watchlist())
    wl.setdefault(HU4, HU4_ENTRY)
    return wl


def long_date(iso):
    try:
        return ce.long_date(iso)
    except (TypeError, ValueError):
        return iso or "an unknown date"


def designation_english(kind, number, issuer, key):
    """'Act LVI of 2026', 'Government decree 225/2026', ..."""
    if kind == "fundamental_law":
        return "An amendment to the Fundamental Law"
    if kind == "act" and number:
        numeral, _, year = number.partition("/")
        return "Act {0} of {1} (Act {2})".format(numeral, year, hu_store.roman(numeral))
    names = {"ogy_resolution": "Resolution {0} of the Országgyűlés",
             "gov_resolution": "Government resolution {0}",
             "gov_decree": "Government decree {0}",
             "ab_decision": "Constitutional Court decision {0}",
             "ministerial_decree": "Decree {0} of " + (issuer or "a minister")}
    if kind in names and number:
        return names[kind].format(number)
    return key


def formula(title):
    folded = ce.noise_mod.fold(title)
    for pattern, english in FORMULAS:
        if pattern in folded:
            return english
    return None


def takeaway(r):
    issue = r["issue_key"].partition("/")[2]
    bits = ["{0}, published in Magyar Közlöny No. {1} of {2}{3}".format(
        designation_english(r["type"], r["number"], r["issuer"], r["entry_key"]), issue,
        long_date(r["date"]), ", page {0}".format(r["page"]) if r["page"] else "")]
    f = formula(r["title"])
    if f:
        bits.append("By its title: " + f[0].lower() + f[1:])
    if r["rule"] == HU4:
        bits.append("Shown under HU4 whatever its words; its subject is in the text, not "
                    "the title")
    return ". ".join(bits)


def motion_english(outcome, paper, motion):
    for pattern, english in MOTIONS:
        if pattern in (outcome or ""):
            return english.format(paper=paper or "the paper", motion=motion or "?")
    return None


def vote_lines(conn, r):
    """Tally, the split by group at the vote, and who broke with their group."""
    how = hu_store.MAJORITIES.get(r["majority"])
    lines = [ce.tally_line(r["yes"], r["no"], r["abstain"], result=r["result"],
                           how="needing " + how if how else None)]
    if r["secret"]:
        lines.append("Secret ballot: no member positions are recorded.")
        return lines
    pos = ce.rows(conn, "SELECT name, faction, position FROM hu_votes WHERE vote_ts = ?",
                  (r["vote_ts"],))
    if pos:
        lines.append(ce.split_line(ce.group_counts(
            [(p["faction"], p["position"]) for p in pos], hu_store.YES, hu_store.NO,
            hu_store.ABSTAIN), label="By group at the vote"))
        lines.append(ce.members_line(
            len(pos), ce.rebels([(p["name"], p["faction"], p["position"]) for p in pos],
                                hu_store.YES, hu_store.NO, skip=NO_GROUP)))
    return lines


def votes(conn, since, until, wl):
    """Recorded votes in the window on our ground (HU4, HU5, the watchlist)."""
    out = []
    for r in ce.rows(conn, "SELECT d.*, p.kind AS paper_kind, p.url AS paper_url FROM "
                           "hu_divisions d LEFT JOIN hu_papers p USING (paper_key) WHERE "
                           + ce.window_sql("d.date") + " ORDER BY d.vote_ts", (since, until)):
        paper = r["paper_key"]
        own_watch = bool(paper) and paper in wl
        hu4 = r["rule"] == HU4
        watched = own_watch or hu4
        if not ce.on_ground(r["areas"], watched):
            continue
        what = motion_english(r["outcome"], paper, r["motion"])
        kind = PAPER_KINDS.get(r["paper_kind"] or "")
        bits = [what or "A recorded vote{0}".format(" on " + paper if paper else "")]
        if kind and paper:
            bits.append("{0} is {1} {2}".format(paper, "an" if kind[0] in "aeiou" else "a", kind))
        if hu4:
            bits.append("Shown under HU4: an amendment to the Fundamental Law")
        lines = vote_lines(conn, r)
        if hu_store.is_karzat(r["source"]):
            lines.append(KARZAT_ITEM)
        terms = json.loads(r["matched_terms"] or "[]")
        if terms:
            lines.insert(0, "Matched (its paper's title): {0}.".format(", ".join(terms[:8])))
        it = ce.vote("hu", "{0} {1}".format(paper or r["motion"] or "vote", r["vote_ts"]),
                     r["date"], r["outcome"] or r["result"] or r["mode"],
                     ce.areas_of(r["areas"]), r["tier"], watched, lines,
                     terms=r["matched_terms"], url=r["paper_url"],
                     takeaway=". ".join(bits), group=("hu", paper) if paper else None,
                     group_title=r["title"],
                     final=any(f in (r["outcome"] or "") for f in FINAL),
                     watch_key=paper if own_watch else (HU4 if hu4 else None),
                     division=r["vote_ts"])
        it["karzat"] = hu_store.is_karzat(r["source"])
        out.append(it)
    return out


def paper_takeaway(r):
    kind = PAPER_KINDS.get(r["kind"], "paper")
    subs = json.loads(r["submitters"] or "[]")
    bits = ["{0} {1}, submitted {2}{3}".format(
        kind[0].upper() + kind[1:], r["paper_key"], long_date(r["submitted_on"]),
        " by " + "; ".join(subs[:3]) + (" and others" if len(subs) > 3 else "") if subs else "")]
    if r["addressee"]:
        bits.append("Put to the {0}".format(r["addressee"]))
    if r["status"]:
        bits.append("Status on {0}, as recorded: “{1}”".format(long_date(r["as_of"]),
                                                               r["status"]) if r["as_of"]
                    else "Status as recorded: “{0}”".format(r["status"]))
    if r["promulgated_issue"]:
        bits.append("Promulgated in Magyar Közlöny No. {0} of {1}{2}".format(
            r["promulgated_issue"].partition("/")[2], long_date(r["promulgated_on"]),
            " as " + r["law_ref"] if r["law_ref"] else ""))
    if r["rule"] == HU4:
        bits.append("Shown under HU4 whatever its words")
    return ". ".join(bits)


def papers(conn, since, until, wl):
    """Papers submitted in the window on our ground: bills, resolutions and
    reports as new items, interpellations and questions as questions."""
    out = []
    for r in ce.rows(conn, "SELECT * FROM hu_papers WHERE " + ce.window_sql("submitted_on")
                           + " ORDER BY submitted_on, paper_key", (since, until)):
        key = r["paper_key"]
        own_watch = key in wl
        hu4 = r["rule"] == HU4
        watched = own_watch or hu4
        if not ce.on_ground(r["areas"], watched):
            continue
        terms = json.loads(r["matched_terms"] or "[]")
        lines = ["Matched: {0}.".format(", ".join(terms[:8]))] if terms else []
        if hu_store.is_karzat(r["source"]):
            lines.append(KARZAT_ITEM)
        it = ce.item("hu", "question" if r["kind"] in QUESTION_KINDS else "new", key,
                     r["submitted_on"], r["title"] or key, ce.areas_of(r["areas"]), r["tier"],
                     watched, url=r["url"], terms=r["matched_terms"],
                     takeaway=paper_takeaway(r), lines=lines,
                     watch_key=None if own_watch or not hu4 else HU4)
        it["karzat"] = hu_store.is_karzat(r["source"])
        out.append(it)
    return out


def gazette(conn, since, until, wl):
    out = []
    for r in ce.rows(conn, "SELECT e.*, i.url AS issue_url FROM hu_gazette_entries e "
                           "LEFT JOIN hu_gazette_issues i USING (issue_key) WHERE "
                           + ce.window_sql("e.date"), (since, until)):
        key = r["entry_key"]
        own_watch = key in wl
        hu4 = r["rule"] == HU4
        watched = own_watch or hu4
        if r["type"] not in LAW_TYPES + GAZETTE_TYPES and not own_watch:
            continue
        if not ce.on_ground(r["areas"], watched):
            continue
        terms = json.loads(r["matched_terms"] or "[]")
        lines = ["Matched: {0}.".format(", ".join(terms[:8]))] if terms else []
        out.append(ce.item("hu", "law" if r["type"] in LAW_TYPES else "gazette", key,
                           r["date"], r["title"] or key, ce.areas_of(r["areas"]), r["tier"],
                           watched, url=r["issue_url"], terms=r["matched_terms"],
                           takeaway=takeaway(r), lines=lines,
                           watch_key=None if own_watch or not hu4 else HU4))
    return out


def items(conn, since, until, wl):
    """The gazette's laws and notices, and (from karzat, HU7) the votes and
    papers dated in the window."""
    return gazette(conn, since, until, wl) + votes(conn, since, until, wl) \
        + papers(conn, since, until, wl)


def post_render(conn, country, today, text, wl):
    """Credit karzat in full under Coverage when any of its items is shown."""
    if KARZAT_ITEM not in text or "\n## Coverage\n\n" not in text:
        return text
    src = karzat_source(conn)
    as_of = " Data as of {0} (karzat commit {1}).".format(
        long_date(src["data_to"]), (src["commit_sha"] or "")[:12]) if src else ""
    line = "- **Attribution.** {0}.{1} Licence: CC BY 4.0 (creativecommons.org/licenses/by/4.0)." \
        .format(hu_store.KARZAT_ATTRIBUTION, as_of)
    return text.replace("\n## Coverage\n\n", "\n## Coverage\n\n" + line + "\n", 1)


COUNTRY = ce.Country(
    cc="hu", name="Hungary", chamber="Országgyűlés, through the Magyar Közlöny",
    language="Hungarian",
    taxonomies=(("taxonomy-hu.yaml", "hu"),),
    items=items, watchlist=watchlist, flag=":flag-hu:",
    kinds=("law", "gazette", "vote", "new", "question"),
    members_note="Member positions only for the votes of 9 May to 28 August 2026, from "
                 "karzat's open data; after that the gazette records what became law, not "
                 "who voted",
    notice=notice, post_render=post_render,
    coverage=("The Magyar Közlöny is read in full, every issue; each contents entry is "
              "classified by its Hungarian title.",
              "Presidential (KE) and Prime Minister's (ME) decisions, mostly appointments, "
              "and the Kúria's local-government rulings are stored but not shown unless "
              "watched.",
              "The Hivatalos Értesítő and the Indokolások Tára (the explanatory memoranda) "
              "are not read.",
              "Votes and papers before the token (HU1) come from karzat's open data, a "
              "one-off backfill of 9 May to 28 August 2026 (tools/hu_karzat_backfill.py); "
              "a paper's status is as karzat last saw it."),
)


# --- the one-off read of the backfill ------------------------------------------------

SUMMARY_SINCE = "2026-05-08"       # exclusive: the term began on 9 May 2026


def backfill_summary(conn, config_dir=None):
    """Everything karzat's backfill put on our ground, from 9 May 2026 to the
    data's last day, in one document, for Chris to read once: what was loaded,
    the votes (grouped by paper, every vote, no cap), the bills and the
    questions, after the edition's own noise filters, with the attribution."""
    import sqlite3
    conn.row_factory = sqlite3.Row
    src = karzat_source(conn)
    if not src:
        return ("# Hungary: the karzat backfill\n\nNothing loaded: run "
                "`python3 tools/hu_karzat_backfill.py` first.")
    until = src["data_to"]
    dropped = []
    got = [it for it in ce.gather(conn, COUNTRY, SUMMARY_SINCE, until, config_dir, dropped)
           if it.get("karzat")]
    dropped = [it for it in dropped if it.get("karzat")]
    wl = watchlist(config_dir)
    counts = json.loads(src["counts"] or "{}")
    one = lambda sql: (ce.rows(conn, sql) or [[None]])[0][0]  # noqa: E731
    out = ["# Hungary: the karzat backfill, {0} to {1}".format(
               long_date(src["data_from"]), long_date(until)), "",
           "_Országgyűlés, 43rd term. A one-off read of the historical backfill (HU7), not an "
           "edition: the weekly editions show these items only in their own week._", "",
           "> **Source.** {0}. Licence: CC BY 4.0 (creativecommons.org/licenses/by/4.0). "
           "karzat commit {1}, derived {2}; votes to {3}. The parliament's own record conveys "
           "no rights, so this is a bridge to our own token (HU1), not a substitute.".format(
               hu_store.KARZAT_ATTRIBUTION, (src["commit_sha"] or "")[:12],
               ce.day(src["derived_at"]) or "?", long_date(until)), "",
           "## What was loaded", "",
           "- {0} papers ({1} bills), {2} recorded votes ({3} by name, {4} secret), {5} member "
           "positions, {6} members.".format(
               counts.get("papers"), one("SELECT COUNT(*) FROM hu_papers WHERE kind = 'T'"),
               counts.get("divisions"),
               one("SELECT COUNT(*) FROM hu_divisions WHERE secret = 0 AND kind = 'dontes'"),
               one("SELECT COUNT(*) FROM hu_divisions WHERE secret = 1"),
               counts.get("positions"), counts.get("members")),
           "- On our ground (stored, migration included): {0} papers, {1} votes, of which {2} "
           "under HU4 (amendments to the Fundamental Law) and {3} on interpellation answers "
           "(HU5).".format(
               one("SELECT COUNT(*) FROM hu_papers WHERE areas != '[]' OR rule = 'HU4' OR "
                   "watched = 1"),
               one("SELECT COUNT(*) FROM hu_divisions WHERE areas != '[]' OR rule = 'HU4' OR "
                   "watched = 1"),
               one("SELECT COUNT(*) FROM hu_divisions WHERE rule = 'HU4'"),
               one("SELECT COUNT(*) FROM hu_divisions WHERE rule = 'HU5' AND areas != '[]'")),
           "- Shown below: {0}; left out by the edition's filters: {1}.".format(
               ce.count_text(got) or "nothing", ce.dropped_text(dropped) or "nothing"), ""]
    for kind, heading, _, _ in ce.SECTIONS:
        these = [it for it in got if it["kind"] == kind]
        if not these:
            continue
        out += ["## " + heading, ""]
        if kind == "vote":
            for _, g in ce.vote_groups(sorted(these, key=lambda i: (i["date"], i["key"]))):
                out += ce.vote_lines(g, wl)
        else:
            for it in sorted(these, key=lambda i: (i["date"], i["key"])):
                out += ce.item_lines(it, wl)
        out.append("")
    out += ["## How to read it", "",
            "- Classified by taxonomy-hu v{0} on each paper's Hungarian title; a vote takes "
            "its paper's areas. No model read anything (X16); a tier-2 match can be noise.".format(
                ce.taxonomy_version("taxonomy-hu.yaml")),
            "- Groups are the parliament's own, at the vote. Positions are stored as recorded "
            "(igen, nem, tartózkodott, and the ways of not voting); “against their group's "
            "majority” counts igen and nem only, so an abstention is never named. Which way a "
            "vote cut is a human call, never made here.",
            "- Migration is stored but not shown (area 11).", ""]
    return "\n".join(out)

