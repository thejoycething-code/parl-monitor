#!/usr/bin/env python3
"""Campaigns Brief drafts for German subjects.

    python3 tools/de_briefs.py             # new subjects since the last run
    python3 tools/de_briefs.py --list      # show subjects, write nothing
    python3 tools/de_briefs.py --force SLUG

Christopher, 24 September 2026: "Build the campaign briefs." Germany could
observe and could not act: it had deadlines from the day the petitions
collector landed, and nothing that turns a deadline into a brief someone can
work from.

WHAT IT REUSES, AND WHY THAT MATTERS. The house style, the twelve narrative
fields, Red Fox Four, the Evaluate rows, the marker parsing and the
brief_log ledger all come from tools/make_briefs.py rather than being copied.
A second brief format would drift from Christopher's own within a month, and
brief_status.py, check_brief_approvals.py and publish_briefs_to_drive.py all
read brief_log -- a German brief in a parallel table would be invisible to
every one of them. German slugs carry a 'de-' prefix so the two are
distinguishable in one list.

WHAT IS GERMAN ABOUT IT
-----------------------
The SUBJECTS. Two kinds, and both must be live:

  * a Vorgang the judge scored 3 whose stage is still live -- "Überwiesen",
    "Beschlussempfehlung liegt vor", anything not concluded or lapsed. A
    brief on a bill that has already passed is a history essay.
  * a Bundestag e-petition open for co-signature and on our ground. These
    are the only German items carrying a DEADLINE, which is what makes them
    briefable at all.

Migration is excluded, as everywhere: collated, never campaigned.

The BRIEF IS WRITTEN IN ENGLISH, deliberately, and this is a judgement worth
stating. The German campaign copy itself will be German -- but a brief is an
internal planning document, and the monitor's own German frame already writes
why-lines in English "because the reader is the London team"
(src/triage.SYSTEM_PROMPT_DE). Following that precedent keeps one house style
across three jurisdictions. The German team drafting actual copy is a
separate step and a separate skill.

THE FACTS COME FROM THE STORE, the narrative from the model, and the two are
never confused. RF4 scores are never auto-filled: the Cheat Sheet is explicit
that scoring is the campaigner's judgement. A failed narrative draft says so
loudly at the top of the file rather than leaving placeholders that read like
considered blanks -- the fault that shipped five hollow Westminster briefs on
21 September.

ONE BRIEF PER SUBJECT EVER. A campaigner's edits must not be overwritten by a
scheduled run, so regeneration is --force only.

ONE WRITER AT A TIME on data/parl-monitor.db.
"""

from __future__ import annotations

import argparse
import datetime
import importlib.util
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, intel  # noqa: E402

BRIEFS_DIR = os.path.join(ROOT, "briefs")
TAXONOMY = os.path.join(ROOT, "config", "taxonomy-de.yaml")
EXCLUDED_AREAS = {11}       # migration: collated, never campaigned
SLUG_PREFIX = "de-"

# How much of the title survives in a slug. Short enough to stay readable in
# a filename, and ALWAYS followed by the source id -- see _slug.
SLUG_TITLE_CHARS = 48


def _slug(mb, title, source_id):
    """'de-<title>-<id>'. The id is not decoration, it is the uniqueness.

    Two different EU citizens' initiatives -- "My Voice, My Choice" on
    abortion access and "Verbot von Konversionsmaßnahmen" -- both begin
    "Mitteilung der Kommission über die Europäische Bürgerinitiative", so
    their truncated slugs were IDENTICAL. Both are campaign-relevant and one
    would have silently overwritten the other's file and its brief_log row.
    The id also makes the slug stable: brief_log is keyed on it, so a slug
    that shifted when a title was edited would orphan the campaigner's
    record of the brief.
    """
    stem = mb.slugify(title or "")[:SLUG_TITLE_CHARS].strip("-")
    return "{0}{1}-{2}".format(SLUG_PREFIX, stem or "subject", source_id)


def _make_briefs():
    """The Westminster generator, imported for its shared machinery.

    Loaded by path rather than `import` because tools/ is not a package.
    """
    spec = importlib.util.spec_from_file_location(
        "make_briefs", os.path.join(ROOT, "tools", "make_briefs.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _de_monitor():
    spec = importlib.util.spec_from_file_location(
        "de_monitor", os.path.join(ROOT, "tools", "de_monitor.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def subjects(conn, today=None):
    """Brief-worthy German subjects: live score-3 Vorgänge and open petitions.

    LIVE is the whole point. A Vorgang the House has already adopted or
    rejected is not a campaign, and tools/de_monitor.stage_of already knows
    the difference -- reusing it means the brief generator and the edition
    can never disagree about what is still running.
    """
    mb, dm = _make_briefs(), _de_monitor()
    today = today or datetime.date.today().isoformat()
    names = intel.area_names(TAXONOMY)
    out = []

    for r in conn.execute(
            "SELECT * FROM de_vorgaenge WHERE triage_score = 3 AND areas IS "
            "NOT NULL AND areas != '[]' ORDER BY datum DESC").fetchall():
        kind, _ = dm.stage_of(r["stand"])
        if kind in ("concluded", "lapsed"):
            continue
        areas = [a for a in json.loads(r["areas"] or "[]")
                 if a not in EXCLUDED_AREAS]
        if not areas:
            continue
        out.append({
            "kind": "vorgang",
            "slug": _slug(mb, r["titel"], r["vorgang_id"]),
            "title": r["titel"], "areas": areas,
            "area_labels": [names.get(a) for a in areas],
            "stage": r["stand"], "sponsor": r["initiative"],
            "deadline": None,
            "why": r["why_it_matters"],
            "url": "https://dip.bundestag.de/vorgang/{0}/{1}".format(
                mb.slugify(r["titel"] or "vorgang")[:60] or "vorgang",
                r["vorgang_id"]),
        })

    for r in conn.execute(
            "SELECT * FROM de_petitions WHERE closes >= ? AND areas IS NOT "
            "NULL AND areas != '[]' ORDER BY closes", (today,)).fetchall():
        areas = [a for a in json.loads(r["areas"] or "[]")
                 if a not in EXCLUDED_AREAS]
        if not areas:
            continue
        out.append({
            "kind": "petition",
            "slug": _slug(mb, r["title"], r["petition_id"]),
            "title": r["title"], "areas": areas,
            "area_labels": [names.get(a) for a in areas],
            "stage": "open for co-signature",
            "sponsor": None,
            "deadline": r["closes"],
            "why": r["why_it_matters"],
            "url": r["url"],
        })
    return out


def facts(conn, subject):
    """What the store knows, for the model to draft FROM rather than invent.

    Everything here is quoted from the record. The model is told to use only
    these; a brief that invents a German parliamentarian's position would be
    the worst thing this file could produce.
    """
    dm = _de_monitor()
    names = intel.area_names(TAXONOMY)
    got = {
        "subject": subject["title"],
        "kind": subject["kind"],
        "stage": subject["stage"],
        "areas": subject["area_labels"],
        "brought_by": subject["sponsor"],
        "deadline": subject["deadline"],
        "judge_why_it_matters": subject["why"],
    }
    area_set = set(subject["areas"])

    # What members have actually SAID on these areas, with their placement.
    speeches = []
    try:
        for r in conn.execute(
                "SELECT s.speaker, s.party, s.date, s.excerpt, s.areas, "
                "st.stance FROM de_speeches s LEFT JOIN stance st "
                "ON st.ref = 'de-speech:' || s.speech_id "
                "WHERE s.areas IS NOT NULL AND s.areas != '[]' "
                "ORDER BY s.date DESC LIMIT 200").fetchall():
            if not (set(json.loads(r["areas"] or "[]")) & area_set):
                continue
            speeches.append({
                "member": r["speaker"], "party": r["party"], "date": r["date"],
                "stance": r["stance"],
                "said": " ".join((r["excerpt"] or "").split())[:240]})
            if len(speeches) >= 6:
                break
    except Exception:                                       # noqa: BLE001
        pass
    got["what_members_said"] = speeches

    # Committee activity on the same ground.
    reports = []
    try:
        for r in conn.execute(
                "SELECT datum, committee, titel, areas FROM "
                "de_committee_reports WHERE areas IS NOT NULL AND areas != "
                "'[]' ORDER BY datum DESC LIMIT 120").fetchall():
            if not (set(json.loads(r["areas"] or "[]")) & area_set):
                continue
            reports.append({"date": r["datum"], "committee": r["committee"],
                            "title": " ".join((r["titel"] or "").split())[:160]})
            if len(reports) >= 4:
                break
    except Exception:                                       # noqa: BLE001
        pass
    got["committee_activity"] = reports

    # Anything before the Constitutional Court on the same ground: a pending
    # judgment can make or unmake a campaign and the team should know.
    karlsruhe = []
    try:
        for r in conn.execute(
                "SELECT case_no, senat, stage, subject, areas FROM "
                "de_judgments WHERE areas IS NOT NULL AND areas != '[]'"
        ).fetchall():
            if not (set(json.loads(r["areas"] or "[]")) & area_set):
                continue
            karlsruhe.append({
                "case": r["case_no"], "senate": r["senat"],
                "stage": r["stage"],
                "about": " ".join((r["subject"] or "").split())[:200]})
    except Exception:                                       # noqa: BLE001
        pass
    got["before_the_constitutional_court"] = karlsruhe
    got["area_names"] = {str(a): names.get(a) for a in subject["areas"]}
    return got


def render(subject, fields, mb, today, drafted):
    """The brief, in the house shape minus the Westminster-only blocks.

    No Five Column Analysis tally and no RF1 expectation: both are computed
    from the Westminster ledger (mp_events, the stance table's UK refs) and
    Germany has neither. Rendering them empty would look like a campaign
    nobody had analysed rather than a jurisdiction where that analysis does
    not yet exist, so each is named as absent with the reason.
    """
    name = fields.get("campaign_name") or subject["title"]
    lines = ["# Campaigns Brief (DRAFT): {0}".format(name), ""]
    if not drafted:
        lines.append("> **{0}**".format(
            mb.DRAFT_FAILED_NOTE.strip(" -").format(subject["slug"])
            .replace("tools/make_briefs.py", "tools/de_briefs.py")))
        lines.append("")
    lines.append("> Generated by parl-monitor on {0} from the GERMAN store. "
                 "Facts come from the store; narrative fields are drafts for "
                 "the campaigner to own; RF4 scores are deliberately empty "
                 "because scoring is the campaigner's judgement.".format(today))
    lines.append("")
    lines.append("> **The areas on this brief come from "
                 "`config/taxonomy-de.yaml`, which no German speaker has "
                 "verified.** Written in English because the monitor's reader "
                 "is the London team, as the German triage frame already is. "
                 "The campaign copy itself is German and is a separate step.")
    lines.append("")

    lines.append("## General information")
    lines.append("")
    lines.append("| Field | Value |")
    lines.append("|---|---|")
    rows = [("Subject", subject["title"]),
            ("Kind", subject["kind"]),
            ("Topic", ", ".join(
                mb.AREA_TOPIC.get(a, "?") for a in subject["areas"])),
            ("Areas", ", ".join(x for x in subject["area_labels"] if x)),
            ("Stage", subject["stage"]),
            ("Brought by", subject["sponsor"] or "-"),
            ("Deadline", subject["deadline"] or "none published"),
            ("Source", subject["url"] or "-")]
    for k, v in rows:
        lines.append("| {0} | {1} |".format(k, str(v or "-").replace("|", "/")))
    lines.append("")
    if subject["why"]:
        lines.append("**Why the judge flagged it:** {0}".format(subject["why"]))
        lines.append("")

    lines.append("## The campaign")
    lines.append("")
    for fid, question in mb.NARRATIVE_FIELDS:
        value = fields.get(fid)
        lines.append("### {0}".format(question))
        lines.append("")
        lines.append(value if value else "[CAMPAIGNER]")
        lines.append("")

    lines.append("## Red Fox Four")
    lines.append("")
    lines.append("*Scores are the campaigner's judgement and are never "
                 "auto-filled.*")
    lines.append("")
    lines.append("| Question | Score | Evidence from the store |")
    lines.append("|---|---|---|")
    for tag, question in mb.RF4:
        lines.append("| **{0}** {1} | | |".format(tag, question))
    lines.append("")

    lines.append("## What the record shows")
    lines.append("")
    lines.append("*Not analysis -- the store's own rows, so the campaigner "
                 "can check every claim above against them.*")
    lines.append("")
    said = subject.get("_facts", {}).get("what_members_said") or []
    if said:
        lines.append("| Member | Fraktion | Date | Stance | Said |")
        lines.append("|---|---|---|---|---|")
        for s in said:
            lines.append("| {0} | {1} | {2} | {3} | {4} |".format(
                (s["member"] or "?").replace("|", "/"), s["party"] or "-",
                s["date"] or "?",
                # 0 is "neutral or direction unclear", not a positive
                # score: "+0" reads as a judgement that was never made.
                ("-" if s["stance"] is None else
                 "0" if s["stance"] == 0 else "{0:+d}".format(s["stance"])),
                (s["said"] or "").replace("|", "/")))
        lines.append("")
    else:
        lines.append("No member has spoken on this ground in the protocols "
                     "read. That is a gap in what we have collected, not "
                     "proof of silence in the Bundestag.")
        lines.append("")
    cttee = subject.get("_facts", {}).get("committee_activity") or []
    if cttee:
        lines.append("**In committee:** " + " · ".join(
            "{0} ({1})".format(c["committee"] or "?", c["date"] or "?")
            for c in cttee))
        lines.append("")
    karlsruhe = subject.get("_facts", {}).get(
        "before_the_constitutional_court") or []
    if karlsruhe:
        lines.append("**Before the Constitutional Court on this ground:** "
                     + " · ".join("{0} ({1})".format(k["case"], k["stage"] or "?")
                                  for k in karlsruhe))
        lines.append("")

    lines.append("## Not in this brief, and why")
    lines.append("")
    lines.append("- **Five Column Analysis tally.** Computed from the "
                 "Westminster ledger; Germany has no equivalent yet, so an "
                 "empty tally here would read as an unanalysed campaign "
                 "rather than a jurisdiction the analysis does not cover.")
    lines.append("- **RF1 expectation.** Same reason: it is derived from past "
                 "UK campaign performance.")
    lines.append("- **Targeting Inactive Members.** The candidate list is a "
                 "UK petitions table.")
    lines.append("")

    lines.append("## Evaluate (after the campaign)")
    lines.append("")
    for row in mb.EVALUATE_ROWS:
        lines.append("- {0}: ".format(row))
    lines.append("")
    return "\n".join(lines)


def write_brief(conn, subject, mb, api_key, today):
    got = facts(conn, subject)
    subject["_facts"] = got
    fields = mb.draft_narrative(subject, got, api_key)
    drafted = bool(fields)
    body = render(subject, fields or {}, mb, today, drafted)
    if not os.path.isdir(BRIEFS_DIR):
        os.makedirs(BRIEFS_DIR)
    path = os.path.join(BRIEFS_DIR, subject["slug"] + ".md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body)
    mb.ensure_log(conn)
    conn.execute(
        "INSERT INTO brief_log (slug, subject, generated_at, path, status) "
        "VALUES (?,?,?,?,?) ON CONFLICT(slug) DO UPDATE SET "
        "generated_at=excluded.generated_at, path=excluded.path",
        (subject["slug"], subject["title"], today,
         os.path.relpath(path, ROOT), "draft"))
    conn.commit()
    return path, drafted


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--list", action="store_true",
                    help="show the subjects and write nothing")
    ap.add_argument("--force", help="regenerate one brief by slug")
    args = ap.parse_args()

    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    today = datetime.date.today().isoformat()
    mb = _make_briefs()
    mb.ensure_log(conn)
    found = subjects(conn, today)

    if args.list:
        print("de-briefs: {0} subject(s) brief-worthy.".format(len(found)))
        for s in found:
            # NOT truncated. A listing that cuts the slug makes two
            # distinct subjects look like one -- which is exactly how the
            # collision that prompted the id suffix appeared to still be
            # there after it had been fixed.
            print("  {0}\n      {1:<10} {2}".format(
                s["slug"], s["kind"], s["deadline"] or s["stage"] or ""))
        conn.close()
        return 0

    # Belt and braces: the id makes a collision impossible, and if one ever
    # happens anyway it must stop the run rather than overwrite a brief.
    seen = {}
    for s in found:
        if s["slug"] in seen:
            print("de-briefs: REFUSING TO RUN -- two subjects share the slug "
                  "{0!r}:\n  {1}\n  {2}".format(
                      s["slug"], seen[s["slug"]], s["title"]))
            conn.close()
            return 1
        seen[s["slug"]] = s["title"]

    logged = {r[0] for r in conn.execute("SELECT slug FROM brief_log")}
    if args.force:
        # resolve_slug returns (slug, complaint), NOT a bare slug. Assigning
        # the tuple made every comparison fail and printed a friendly "no
        # current subject matches" -- which is precisely the confusion that
        # function exists to prevent: "nothing new" and "no such brief" must
        # never look the same.
        wanted, complaint = mb.resolve_slug(args.force, found, logged)
        if complaint:
            print("de-briefs: {0}".format(complaint))
            conn.close()
            return 1
        found = [s for s in found if s["slug"] == wanted]
        if not found:
            print("de-briefs: {0!r} is in the log but is no longer a current "
                  "subject -- the bill has concluded or the petition has "
                  "closed. The existing brief stands; nothing regenerated."
                  .format(wanted))
            conn.close()
            return 1
    else:
        # ONE BRIEF PER SUBJECT EVER: a campaigner's edits must survive a
        # scheduled run.
        found = [s for s in found if s["slug"] not in logged]

    from src import publish
    api_key = publish.load_secrets().get("anthropic_api_key")
    written = failed = 0
    for s in found:
        path, drafted = write_brief(conn, s, mb, api_key, today)
        written += 1
        failed += 0 if drafted else 1
        print("  {0}  {1}".format(os.path.relpath(path, ROOT),
                                  "" if drafted else "(NARRATIVE DRAFT FAILED)"))
    print("de-briefs: {0} brief(s) written{1}.".format(
        written,
        "" if not failed else ", {0} with no narrative".format(failed)))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
