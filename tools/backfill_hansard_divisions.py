#!/usr/bin/env python3
"""Commons divisions before 9 March 2016, from Hansard, into the ledger and the review queue.

    python3 tools/backfill_hansard_divisions.py                    # 2010-01-01 to 2016-03-08
    python3 tools/backfill_hansard_divisions.py 2013-01-01 2013-12-31
    python3 tools/backfill_hansard_divisions.py --dry-run          # search and report, store nothing

Christopher, 28 September 2026: "Build the pre-2016 votes collector." The
Commons Votes API starts on 9 March 2016, so the ledger held no Commons vote
of the 2010 or 2015 Parliaments; src/ingest/hansard_divisions.py says why
Hansard can supply them and how.

TWO PATHS, the same two the post-2016 record already has:

  LEDGERED -- a division whose TITLE the taxonomy matches at tier 1 (or a
      watched Bill), found by searching the division sweep terms. The same
      rule tools/backfill_divisions.py applies to the Votes API: "Assisted
      Dying (No. 2) Bill" names its subject, so its voters are recorded
      under div:h<id>, with the question put as the excerpt the stance model
      reads.

  REVIEW QUEUE, NEVER LEDGERED -- a division whose title names only a
      vehicle ("Health and Social Care (Re-committed) Bill") but which sits
      in the SAME DEBATE as our tagged speeches that day. That is how the
      2011 abortion-counselling amendment appears, and why it cannot be
      ledgered by script: its meaning is in the amendment, not the title. The
      queue gives the question, the amendment and its mover as Hansard
      records them; a human decides what each vote meant and adds it to
      config/vote_tracker.yaml with `source: hansard`, and
      tools/ledger_tracker_divisions.py then records its voters.

Writes data/division-candidates-pre2016.json and
docs/division-candidates-pre2016.md. Idempotent: record_votes upserts, and a
fetch is archived under data/raw.
"""

from __future__ import annotations

import argparse
import datetime
import importlib.util
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, filter as filt, intel  # noqa: E402
from src.debatepack import hansard_url  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402
from src.ingest import hansard_divisions as hd  # noqa: E402

QUEUE_JSON = os.path.join(ROOT, "data", "division-candidates-pre2016.json")
QUEUE_MD = os.path.join(ROOT, "docs", "division-candidates-pre2016.md")
DEFAULT_START = "2010-01-01"


def _finder():
    """The post-2016 candidate finder, for its same-debate test -- one rule
    for what "sat in the same debate" means, not two."""
    spec = importlib.util.spec_from_file_location(
        "find_division_candidates", os.path.join(ROOT, "tools", "find_division_candidates.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_settings():
    import yaml
    with open(os.path.join(ROOT, "config", "settings.yaml"), encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def tracked_hansard_ids():
    import yaml
    with open(os.path.join(ROOT, "config", "vote_tracker.yaml"), encoding="utf-8") as h:
        cfg = yaml.safe_load(h) or {}
    return {int(d["id"]) for d in (cfg.get("divisions") or [])
            if str(d.get("source") or "").lower() == "hansard" and d.get("id")}


def ledgered_ids(conn):
    return {int(re.match(r"div:h(\d+):", r[0]).group(1)) for r in conn.execute(
        "SELECT DISTINCT ref FROM mp_events WHERE kind='vote' AND ref LIKE 'div:h%'")
        if re.match(r"div:h(\d+):", r[0])}


def speech_debates(conn, start, end):
    """[(date, raw debate title)] of tagged speeches in the window, deduplicated:
    the searches the queue needs, one per debate per day."""
    out = set()
    for r in conn.execute(
            "SELECT date, line FROM mp_events WHERE kind='debate' AND date BETWEEN ? AND ? "
            "AND areas IS NOT NULL AND areas != '[]'", (start, end)):
        title = re.sub(r"^Spoke:\s*", "", r[1] or "")
        title = re.sub(r"\s*\(re: [^)]*\)$", "", title).strip()
        if title:
            out.add((r[0], title))
    return sorted(out)


def search_term(title):
    """A debate title as a Hansard search term: the words before any colon or
    bracket. "Health and Social Care (Re-committed) Bill" is searched as
    "Health and Social Care", which finds all four of 7 September 2011's
    divisions; the full title with its brackets is not a reliable query."""
    head = title.split(":", 1)[0]
    head = re.split(r"\s*\(", head, 1)[0]
    return " ".join(head.split())[:80]


def row_summary(row, ctx):
    date = (row.get("Date") or "")[:10]
    return {
        "id": int(row["Id"]), "external_id": str(row.get("ExternalId")),
        "section_ext": row.get("DebateSectionExtId"), "date": date,
        "title": " ".join((row.get("DebateSection") or "").split()),
        "ayes": row.get("AyesCount"), "noes": row.get("NoesCount"),
        "question": ctx.get("question"), "proposed": ctx.get("proposed"),
        "mover": ctx.get("mover"),
        "hansard": hansard_url("Commons", date, row.get("DebateSectionExtId"))
        if row.get("DebateSectionExtId") else None,
    }


def run(conn, client, tax, wl, start, end, dry_run=False, log=print):
    finder = _finder()
    hidden = finder.hidden_areas()
    names = intel.area_names(os.path.join(ROOT, "config", "taxonomy.yaml"))
    terms = load_settings().get("division_sweep_terms") or []
    tracked, held = tracked_hansard_ids(), ledgered_ids(conn)
    day_debates = finder.debate_titles_by_date(conn)

    # 1. LEDGERED: the title sweep.
    seen, ledgered = set(), []
    for term in terms:
        try:
            rows = hd.search(client, term, start, end)
        except FetchError as exc:
            log("  [gap] hansard division search '{0}': {1}".format(term, exc.cause))
            continue
        for row in rows:
            did = int(row["Id"])
            if did in seen:
                continue
            seen.add(did)
            title = " ".join((row.get("DebateSection") or "").split())
            r = filt.filter_item(tax, wl, title)
            if not (r.tier == 1 or r.watchlist_hits):
                continue
            ctx = hd.context(client, row.get("DebateSectionExtId"), row.get("ExternalId"))
            summary = dict(row_summary(row, ctx), areas=sorted(r.issue_areas),
                           matched=r.matched_terms[:3] + r.watchlist_hits[:1])
            # Re-recorded even when already held: record_votes upserts, and
            # the line carries the question, so a fix to how the question is
            # read reaches the ledger on the next run.
            if dry_run:
                summary["voters"] = None
            else:
                try:
                    division, voters = hd.parse(hd.fetch(client, row["ExternalId"]), ctx.get("question"),
                                               ctx.get("proposed"), ctx.get("mover"))
                except FetchError as exc:
                    log("  [gap] hansard division {0}: {1}".format(did, exc.cause))
                    continue
                summary["voters"] = intel.record_votes(conn, division, voters, hd.PREFIX, r.issue_areas)
            ledgered.append(summary)
            log("  ledger  {0} h{1:<5} {2:>3}-{3:<3} {4} | {5}".format(
                summary["date"], did, summary["ayes"], summary["noes"], title[:52],
                (summary["question"] or "?")[:50]))

    # 2. REVIEW QUEUE: divisions in the same debate as our tagged speeches.
    queue = []
    searches = speech_debates(conn, start, min(end, hd.FIRST_VOTES_API_DATE))
    log("  same-debate search: {0} debate-day(s) with tagged speeches".format(len(searches)))
    asked = set()
    for date, title in searches:
        key = (date, search_term(title))
        if key in asked or not key[1]:
            continue
        asked.add(key)
        try:
            rows = hd.search(client, key[1], date, date)
        except FetchError as exc:
            log("  [gap] hansard division search '{0}' {1}: {2}".format(key[1], date, exc.cause))
            continue
        for row in rows:
            did = int(row["Id"])
            if did in seen:
                continue
            seen.add(did)
            dtitle = " ".join((row.get("DebateSection") or "").split())
            day_areas = finder.same_debate_areas(dtitle, day_debates.get(date, []))
            if not day_areas:
                continue
            ctx = hd.context(client, row.get("DebateSectionExtId"), row.get("ExternalId"))
            shown = {a for a, n in day_areas.items()
                     if a not in hidden and n >= finder.MIN_AREA_SPEECHES}
            queue.append(dict(row_summary(row, ctx), day_areas=day_areas,
                              hidden_only=not shown, tracked=did in tracked))
    queue.sort(key=lambda c: (c["hidden_only"], -sum(c["day_areas"].values()), c["date"]))

    if not dry_run:
        with open(QUEUE_JSON, "w", encoding="utf-8") as fh:
            json.dump({"start": start, "end": end, "generated": datetime.date.today().isoformat(),
                       "ledgered": ledgered, "candidates": queue}, fh, indent=1, ensure_ascii=False)
        with open(QUEUE_MD, "w", encoding="utf-8") as fh:
            fh.write(render(ledgered, queue, names, start, end))
    log("hansard-divisions: {0} ledgered by title ({1} voter rows), {2} for review "
        "({3} displayable){4}".format(
            len(ledgered), sum(s["voters"] for s in ledgered if isinstance(s.get("voters"), int)),
            len(queue), sum(1 for c in queue if not c["hidden_only"]),
            " (dry run, nothing stored)" if dry_run else ""))
    return ledgered, queue


def _areas(ids, names):
    return ", ".join(str(names.get(a, a)) for a in ids)


def render(ledgered, queue, names, start, end):
    out = ["# Commons divisions before March 2016 - review", "",
           "*From Hansard, {0} to {1}. The Commons Votes API begins on 9 March 2016; "
           "these are the divisions before it.*".format(start, end), "",
           "## Ledgered by title ({0})".format(len(ledgered)), "",
           "Recorded automatically, as every title-matched division is: the title names "
           "the subject. They feed member stance through the model, which is shown the "
           "question put. Add one to `config/vote_tracker.yaml` (with `source: hansard`) "
           "only if it should appear on the public tracker.", ""]
    for s in ledgered:
        out.append("- **{date}** h{id} {title}, {ayes}-{noes}. Question: {q}{mover}".format(
            q=s["question"] or "not found", mover=(" Moved by " + s["mover"] + ".") if s["mover"] else "",
            **{k: s[k] for k in ("date", "id", "title", "ayes", "noes")}))
    out += ["", "## For review ({0})".format(len(queue)), "",
            "**Nothing here is in the ledger.** Each division's title names only the Bill "
            "it amended; our speeches sat in the same debate that day. For each, decide "
            "whether it belongs on the record and what an Aye meant, checked against "
            "Hansard and against the mover's own vote. Then add it to "
            "`config/vote_tracker.yaml` as `id: <h id>`, `source: hansard`, "
            "`hansard_ext: <external id>`, with meaning lines.", ""]
    for c in queue:
        # hidden_only: no displayable area with enough speeches to mean
        # anything -- migration, or a stray speech or two in a long debate.
        flag = "  *[weak or migration-only evidence: listed, not a priority]*" if c["hidden_only"] else ""
        out += ["### {date} - {title} ({ayes}-{noes}){flag}".format(flag=flag, **c),
                "- id: `{id}` | hansard_ext: `{external_id}`".format(**c),
                "- question put: {0}".format(c["question"] or "not found in the record"),
                "- proposed: {0}".format(c["proposed"] or "not found"),
                "- mover: {0}".format(c["mover"] or "not stated by the clerk; check Hansard"),
                "- same debate: {0}".format(", ".join(
                    "{0} x{1}".format(names.get(a, a), n)
                    for a, n in sorted(c["day_areas"].items(), key=lambda kv: -kv[1]))),
                "- Hansard: {0}".format(c["hansard"] or "-"),
                "", "DECISION: ", ""]
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("start", nargs="?", default=DEFAULT_START)
    ap.add_argument("end", nargs="?", default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    last = (datetime.date.fromisoformat(hd.FIRST_VOTES_API_DATE)
            - datetime.timedelta(days=1)).isoformat()
    end = min(args.end or last, last)
    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
    wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))
    print("hansard divisions {0} -> {1}".format(args.start, end))
    run(conn, client, tax, wl, args.start, end, dry_run=args.dry_run)
    print("ledger:", intel.ledger_stats(conn))
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
