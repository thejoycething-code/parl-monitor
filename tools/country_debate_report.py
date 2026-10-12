#!/usr/bin/env python3
"""After a debate in a new country: the report and social copy, a DM to Chris
for approval, then (only after explicit approval) a Slack canvas for him alone.

    python3 tools/country_debate_report.py --country be --date 2026-10-08 --list
    python3 tools/country_debate_report.py --country be --date 2026-10-08 --debate 56/143-13
        [--item KEY] [--pack data/packs/<folder>] [--clips data/clips/<folder>]
        [--live] [--reads FILE] [--db PATH] [--out DIR] [--no-dm]
    python3 tools/country_debate_report.py --from-clips data/clips/<folder> [--no-dm]
    python3 tools/country_debate_report.py --report data/debate-reports/<folder> --queue-out q.md [--limit N]
    python3 tools/country_debate_report.py --report data/debate-reports/<folder> --queue-in q.md
    python3 tools/country_debate_report.py --report data/debate-reports/<folder> --render [--dm]
    python3 tools/country_debate_report.py --report data/debate-reports/<folder> --approve --by "Chris"
    python3 tools/country_debate_report.py --report data/debate-reports/<folder> --publish [--force]
    python3 tools/country_debate_report.py --prompt          # the session judge's instruction

Countries: the ones whose speeches we store (src/chamber_store.py):
{countries}. Speeches come from the store (`<cc>_speeches`, the weekly's
chamber step), from the source the same day (--live: the country's own
collector into memory, nothing written), or from a clip pack's recorded
passages (--from-clips). Votes, meanings and readings come from the store and
config/<cc>_stance.yaml; --item names the bill or dossier key (by id, never
by title), --pack takes it from a debate pack (tools/country_debate_pack.py).

The order, as the UK's: generate (report.md, social.md, a DM to Chris alone
asking for approval); translations (a person in translations.yaml, or the free
session judge on the Mini, below), then --render (and --dm to re-send); then
--approve --by NAME, which records the approval against these exact files;
then --publish, which makes the canvas with the UK's Slack canvas code,
shared with Chris ALONE (never a channel), and on a re-run rewrites the same
canvas in place. Nothing is ever posted to a channel or a social network.

No paid AI. Our text is templates over the record. The translations are a
person's or the free session judge's, on the Mini (Claude Code on the plan
allowance, no API key):

    SESSION_JUDGE_PROMPT="$(python3 tools/country_debate_report.py --prompt)" \\
      bash tools/session_judge.sh tools/country_debate_report.py 40 20 --report data/debate-reports/<folder>
    python3 tools/country_debate_report.py --report data/debate-reports/<folder> --render --dm

Before every relevant reading is confirmed the report and the social copy are
AWAITING SIGN-OFF: what was said and how members voted, no verdicts.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import country5ca as c5  # noqa: E402
from src import country_debatereport as cdr  # noqa: E402
from src import country_debatepack as dp  # noqa: E402

__doc__ = __doc__.format(countries=", ".join(cdr.COUNTRIES))


def _state(folder):
    path = os.path.join(folder, "report.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    return {}


def _save_state(folder, state):
    with open(os.path.join(folder, "report.json"), "w", encoding="utf-8") as fh:
        json.dump(state, fh, ensure_ascii=False, indent=1)


def _inputs(folder):
    path = os.path.join(folder, "inputs.json")
    if not os.path.exists(path):
        raise SystemExit("no inputs.json in {0}: generate the report first".format(folder))
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def render(folder, config_dir=None, reads_path=None, log=print):
    """Render report.md and social.md from inputs.json, the stance file and
    the translations; store the checks. Returns (inputs, report, social, problems, state)."""
    from src import country_live as cl
    inp = _inputs(folder)
    entries = c5.load(inp["cc"], config_dir)[0]
    translations = cdr.write_translations(folder, inp)
    state = _state(folder)
    reads_path = reads_path or state.get("reads")
    reads = cl.load_reads(reads_path) if reads_path else {}
    report, rstate = cdr.render_report(inp, entries, translations, reads)
    social, sstate = cdr.render_social(inp, entries, translations)
    problems = cdr.checks(inp, report, social, rstate, translations, sstate)
    for name, text in (("report.md", report), ("social.md", social)):
        with open(os.path.join(folder, name), "w", encoding="utf-8") as fh:
            fh.write(text)
    state.update(rstate)
    state.update({"rendered": datetime.datetime.now().isoformat(timespec="seconds"),
                  "problems": problems, "reads": reads_path})
    _save_state(folder, state)
    log("{0}: {1} speaker(s), {2} vote(s), readings confirmed {3} of {4}; {5}".format(
        os.path.relpath(folder, ROOT), rstate["speakers"], rstate["votes"],
        rstate["readings_confirmed"], rstate["readings_in_scope"],
        "AWAITING SIGN-OFF" if not rstate["signed"] else "signed"))
    for p in problems:
        log("  [check] {0}".format(p))
    return inp, report, social, problems, state


def send_dm(folder, inp, report, social, problems, state, log=print):
    from src import publish
    text = cdr.approval_dm(inp, report, social, problems, state, folder)
    result = publish.slack_dm(cdr.secrets_for_chris(), text)
    log("DM to Chris: {0}".format(result.get("message_ts") or result))
    state = _state(folder)
    state.setdefault("dms", []).append({"at": datetime.datetime.now().isoformat(timespec="seconds"),
                                        "result": result.get("message_ts") or str(result)[:200]})
    _save_state(folder, state)
    return result


def load_pack(path):
    with open(os.path.join(path, "pack.json"), encoding="utf-8") as fh:
        pack = json.load(fh)
    pack["_folder"] = os.path.abspath(path)
    return pack


def generate(args):
    cc = (args.country or "").lower()
    clip_folder = args.clips
    if args.from_clips:
        cc_got, rows = cdr.from_clip_pack(args.from_clips)
        cc = cc or cc_got
        clip_folder = clip_folder or args.from_clips
        source = "clip pack {0}".format(os.path.relpath(os.path.abspath(args.from_clips), ROOT))
        date = args.date or (rows[0]["date"] if rows else None)
    else:
        if not cc or not args.date:
            raise SystemExit("give --country and --date (or --from-clips)")
        date = args.date
        if args.live:
            from src import country_clips as clips
            rows = cdr.from_live(cc, date, clips._client(cc))
            source = "live read of the source"
        else:
            if not os.path.exists(args.db):
                raise SystemExit("no store at {0} (pull it, or use --live)".format(args.db))
            conn = c5.connect_ro(args.db)
            try:
                rows = cdr.from_store(conn, cc, date)
            except sqlite3.OperationalError as exc:
                raise SystemExit("{0}: {1} (has the {2} chamber step run?)".format(args.db, exc, cc.upper()))
            conn.close()
            source = "store"
    if cc not in cdr.COUNTRIES:
        raise SystemExit("{0}: no speech collector (the countries: {1})".format(cc, ", ".join(cdr.COUNTRIES)))
    found = cdr.pick_debate(rows, debate_id=args.debate, find=args.find)
    if args.list or not found or (len(found) > 1 and not args.debate):
        print("{0}, {1}: {2} debate(s) on our ground ({3})".format(dp.name_of(cc), date, len(found), source))
        for d in found:
            print("  {0:<16} {1:>2} speakers  {2}".format(d["debate_id"], len(d["speakers"]), dp.clip(d["title"], 90)))
        if not found:
            return 1
        if args.list:
            return 0
        if len(found) > 1:
            print("several debates: rerun with --debate ID")
            return 1
    debate = found[0]
    pack = load_pack(args.pack) if args.pack else None
    if clip_folder is None:
        clip_folder = cdr.find_clip_pack(cc, date, debate["debate_id"])
    conn = c5.connect_ro(args.db) if os.path.exists(args.db) else None
    try:
        inp = cdr.gather(cc, debate, date, conn, item_ids=args.item or [], pack=pack,
                         clip_folder=clip_folder, source=source, config_dir=args.config_dir)
    finally:
        if conn is not None:
            conn.close()
    if conn is None:
        print("[note] no store at {0}: words only, no votes".format(args.db))
    inp["sample"] = bool(args.sample)
    folder = args.out or cdr.folder_for(cc, date, debate["title"])
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "inputs.json"), "w", encoding="utf-8") as fh:
        json.dump(inp, fh, ensure_ascii=False, indent=1)
    state = _state(folder)
    if state.get("approved"):
        state["approved_before_regeneration"] = state.pop("approved")
    state["generated"] = datetime.datetime.now().isoformat(timespec="seconds")
    state["sample"] = bool(args.sample)
    if args.reads:
        state["reads"] = os.path.abspath(args.reads)
    _save_state(folder, state)
    inp, report, social, problems, state = render(folder, args.config_dir, args.reads)
    if args.no_dm or args.sample:
        print("not DMing (--no-dm). Files in {0}".format(os.path.relpath(folder, ROOT)))
        return 0
    send_dm(folder, inp, report, social, problems, state)
    return 0


def approve(args):
    folder = args.report.rstrip("/")
    if not args.by or not args.by.strip():
        raise SystemExit("--approve needs --by NAME: the person approving")
    for name in ("report.md", "social.md"):
        if not os.path.exists(os.path.join(folder, name)):
            raise SystemExit("no {0} in {1}: generate first".format(name, folder))
    state = _state(folder)
    state["approved"] = {"by": args.by.strip(), "on": datetime.date.today().isoformat(),
                         "at": datetime.datetime.now().isoformat(timespec="seconds"),
                         "sha": cdr.files_sha(folder)}
    _save_state(folder, state)
    print("approved by {0}: report.md and social.md as they are now. --publish makes the canvas.".format(
        args.by.strip()))
    if state.get("problems"):
        print("note: {0} check(s) still fail; --publish refuses them unless --force".format(len(state["problems"])))
    return 0


def publish_canvas(args, transport=None):
    from src import publish
    folder = args.report.rstrip("/")
    inp = _inputs(folder)
    state = _state(folder)
    blockers = cdr.publish_blockers(folder, state, force=args.force)
    if blockers:
        print("refusing to publish:")
        for b in blockers:
            print("  " + b)
        for p in state.get("problems") or []:
            print("  [check] " + p)
        return 2
    with open(os.path.join(folder, "report.md"), encoding="utf-8") as fh:
        report = fh.read()
    translations = cdr.load_translations(folder)
    title_en, _ = cdr.english(translations, "title", inp["title"])
    title = cdr.canvas_title(inp, title_en)
    body = cdr.canvas_body(report, state)
    secrets = cdr.secrets_for_chris()
    held = (state.get("published") or {}).get("canvas_id")
    if held:
        result = publish.slack_update_canvas(secrets, held, body, transport=transport)
    else:
        lead = ("*{0}* (approved by {1}). The report as a canvas, shared with you alone; "
                "nothing is in a channel.".format(title, state["approved"]["by"]))
        result = publish.slack_preview_canvas(secrets, title, body, lead, transport=transport)
    if not result.get("canvas_id"):
        print("publish failed: {0}".format(result))
        return 1
    rec = state.get("published") or {"canvas_id": result["canvas_id"], "canvas_url": result.get("canvas_url"),
                                      "first": datetime.datetime.now().isoformat(timespec="seconds"),
                                      "revisions": 0}
    rec["revisions"] = rec.get("revisions", 0) + 1
    rec["last"] = datetime.datetime.now().isoformat(timespec="seconds")
    rec["approved_by"] = state["approved"]["by"]
    rec["forced"] = bool(args.force and state.get("problems"))
    state["published"] = rec
    _save_state(folder, state)
    print("canvas {0} ({1}): {2}".format("rewritten in place" if held else "created, shared with Chris alone",
                                         rec["canvas_id"], rec.get("canvas_url")))
    return 0


def main(argv=None, transport=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--country")
    ap.add_argument("--date")
    ap.add_argument("--list", action="store_true", help="list the day's debates on our ground and stop")
    ap.add_argument("--debate", help="the debate_id exactly (see --list)")
    ap.add_argument("--find", help="words the debate's title must contain (accents ignored)")
    ap.add_argument("--item", action="append", help="a bill, dossier or division key (repeatable)")
    ap.add_argument("--pack", help="a debate pack folder (tools/country_debate_pack.py)")
    ap.add_argument("--clips", help="a clip pack folder (tools/country_clips.py)")
    ap.add_argument("--from-clips", help="take the speeches from a clip pack's recorded passages")
    ap.add_argument("--live", action="store_true", help="read --date from the source (nothing stored)")
    ap.add_argument("--reads", help="a reads file (tools/country_live_debate.py --queue-out, filled)")
    ap.add_argument("--db", default=cdr.STORE)
    ap.add_argument("--config-dir", help="config directory (default config/)")
    ap.add_argument("--out", help="report folder (default data/debate-reports/<cc>-<date>-<slug>/)")
    ap.add_argument("--no-dm", action="store_true", help="write the files, do not DM")
    ap.add_argument("--sample", action="store_true", help="mark the report SAMPLE: never DMed, never published")
    ap.add_argument("--report", help="an existing report folder")
    ap.add_argument("--render", action="store_true", help="re-render from inputs.json and translations")
    ap.add_argument("--dm", action="store_true", help="with --render: send the approval DM again")
    ap.add_argument("--queue-out", help="write the pending translations for the session judge")
    ap.add_argument("--queue-in", help="read the session judge's translations back")
    ap.add_argument("--limit", type=int, help="with --queue-out: at most N items")
    ap.add_argument("--approve", action="store_true", help="record an approval (needs --by)")
    ap.add_argument("--by", help="who approves")
    ap.add_argument("--publish", action="store_true", help="the canvas, for Chris alone, after approval")
    ap.add_argument("--force", action="store_true", help="publish although checks failed (never without approval)")
    ap.add_argument("--prompt", action="store_true", help="print the session judge's instruction")
    args = ap.parse_args(argv)

    if args.prompt:
        print(cdr.TRANSLATE_PROMPT)
        return 0
    if args.report:
        folder = args.report.rstrip("/")
        if args.queue_out:
            inp = _inputs(folder)
            n = cdr.write_queue(args.queue_out, inp, cdr.write_translations(folder, inp), args.limit)
            print("session queue: {0} item(s) written".format(n))
            return 0
        if args.queue_in:
            import yaml
            inp = _inputs(folder)
            translations = cdr.write_translations(folder, inp)
            applied, refused = cdr.read_queue(args.queue_in, inp, translations)
            with open(os.path.join(folder, "translations.yaml"), "w", encoding="utf-8") as fh:
                fh.write(cdr.TRANSLATIONS_HEAD)
                yaml.safe_dump({"items": translations}, fh, allow_unicode=True, sort_keys=False, width=100)
            for r in refused:
                print("  refused: {0}".format(r))
            print("session queue: {0} item(s) scored".format(applied))
            return 0
        if args.approve:
            return approve(args)
        if args.publish:
            return publish_canvas(args, transport)
        inp, report, social, problems, state = render(folder, args.config_dir, args.reads)
        if args.dm and state.get("sample"):
            print("a SAMPLE is never DMed")
        elif args.dm:
            send_dm(folder, inp, report, social, problems, state)
        return 0
    if args.approve or args.publish or args.queue_out or args.queue_in or args.render:
        raise SystemExit("give --report FOLDER")
    return generate(args)


if __name__ == "__main__":
    sys.exit(main())
