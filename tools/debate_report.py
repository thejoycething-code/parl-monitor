#!/usr/bin/env python3
"""Write a debate's report and social copy, ask for approval, then publish a canvas.

    python3 tools/debate_report.py --pack data/packs/<folder>            # generate, then DM for approval
    python3 tools/debate_report.py --pack data/packs/<folder> --dry-run  # what it would send the writer, no spend
    python3 tools/debate_report.py --pack data/packs/<folder> --preview  # the canvas, shared with you alone
    python3 tools/debate_report.py --pack data/packs/<folder> --publish  # canvas to #campaigns-en-gb

The order is deliberate and not negotiable in code: generate, DM, preview if you want to
see the rendering, and only then, on a separate explicit run, publish. Nothing reaches the channel without a person running
--publish, because the report quotes named MPs and the onside list is a human judgement.

Reads the pack's speeches.md (full text, per-contribution Hansard links) and
checklist.md's confirmed onside list. Writes report.md, social.md and report.json into
the pack. Costs one Anthropic call, about 5p, recorded in api_spend as 'debate-report'.
"""

import argparse
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import db, debatereport as dr, publish, socialcut as sc  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(pack):
    meta = json.load(open(os.path.join(pack, "pack.json")))
    speeches_path = os.path.join(pack, "speeches.md")
    if not os.path.exists(speeches_path):
        raise SystemExit("no speeches.md in %s: build the pack first" % pack)
    speeches = sc.parse_speeches(open(speeches_path, encoding="utf-8").read())
    meta["speakers_total"] = len(speeches)
    meta["hansard_url"] = "https://hansard.parliament.uk/{0}/{1}/debates/{2}/".format(
        meta.get("house", "Commons"), meta.get("date"), meta.get("ext_id"))
    return meta, speeches


def reels_in(pack):
    """The reels already cut, from social-cut.md, so the DM can list what is ready."""
    import re
    path = os.path.join(pack, "social-cut.md")
    out = []
    if not os.path.exists(path):
        return out
    for m in re.finditer(r"^## \d+\.\s*(.+?)\s*—.*?([\d.]+)s", open(path, encoding="utf-8").read(), re.M):
        out.append({"name": m.group(1).strip(), "duration": float(m.group(2)), "party": ""})
    return out


def generate(args):
    pack = args.pack.rstrip("/")
    from src import packlock
    packlock.acquire(pack, "debate_report", force=bool(os.environ.get("PARL_FORCE_LOCK")))
    meta, speeches = load(pack)
    speakers = dr.speaker_brief(speeches, provisional=args.provisional)
    onside = [s for s in speakers if s["confirmed_onside"]]
    print("%s: %d speakers, %d %s" % (meta.get("title"), len(speakers), len(onside),
                                      "onside by the pass read (PROVISIONAL)" if args.provisional else "confirmed onside"))
    if args.dry_run:
        payload = dr.build_payload(meta, speakers, provisional=args.provisional)
        chars = len(payload["messages"][0]["content"])
        print("would send %d speakers, %d characters (~%d tokens, about $%.2f)"
              % (len(speakers), chars, chars // 4, (chars / 4 * 3 + 1500 * 15) / 1e6))
        for s in speakers:
            print("   %-26s %-14s %5d words  onside=%s" % (s["name"], s["party"], s["words"] or 0, s["confirmed_onside"]))
        return
    secrets = publish.load_secrets()
    key = secrets.get("anthropic_api_key")
    if not key:
        raise SystemExit("no anthropic_api_key in config/secrets.yaml")
    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    sections, problems, usage = dr.generate(meta, speeches, key, conn=conn, provisional=args.provisional)
    conn.commit()
    conn.close()
    banner = "<!-- %s -->\n\n" % dr.PROVISIONAL_NOTE if args.provisional else ""
    if sections.get("REPORT"):
        open(os.path.join(pack, "report.md"), "w", encoding="utf-8").write(banner + sections["REPORT"] + "\n")
    if sections.get("SOCIAL"):
        open(os.path.join(pack, "social.md"), "w", encoding="utf-8").write(banner + sections["SOCIAL"] + "\n")
    json.dump({"generated": datetime.datetime.now().isoformat(timespec="seconds"),
               "usage": usage, "problems": problems, "provisional": bool(args.provisional),
               "words": dr.word_count(sections.get("REPORT") or "")},
              open(os.path.join(pack, "report.json"), "w"), indent=1)
    print("report %d words; %d check(s) failed" % (dr.word_count(sections.get("REPORT") or ""), len(problems)))
    for p in problems:
        print("  [check] %s" % p)
    if args.no_dm:
        print("not DMing (--no-dm). Files written into the pack.")
        return
    text = dr.approval_dm(meta, sections, reels_in(pack), problems, pack, provisional=args.provisional)
    result = publish.slack_dm(secrets, text)
    print("DM:", result.get("message_ts") or result)


def load_selection(pack):
    path = os.path.join(pack, "selection.json")
    return json.load(open(path)) if os.path.exists(path) else None


def preview_canvas(args):
    """The canvas as it will render, shared with the DM recipient alone. Never the channel.

    Runs on any report, provisional or failing checks included: the point is to see it.
    The notes at the top of the preview say what state it is in."""
    pack = args.pack.rstrip("/")
    meta, _speeches = load(pack)
    report_path = os.path.join(pack, "report.md")
    if not os.path.exists(report_path):
        raise SystemExit("no report.md in the pack: generate it first")
    report = open(report_path, encoding="utf-8").read()
    report = "\n".join(l for l in report.splitlines() if not l.startswith("<!-- PROVISIONAL"))
    state = {}
    if os.path.exists(os.path.join(pack, "report.json")):
        state = json.load(open(os.path.join(pack, "report.json")))
    title = "PREVIEW: %s — %s" % (meta.get("title"), meta.get("date"))
    body = dr.canvas_body(meta, report, preview=True, provisional=bool(state.get("provisional")),
                          problems=state.get("problems"), selection=load_selection(pack))
    result = publish.slack_preview_canvas(publish.load_secrets(), title, body, dr.canvas_summary(meta, preview=True))
    if result.get("canvas_url"):
        print("preview canvas (you alone):", result["canvas_url"])
        state.setdefault("previews", []).append({"at": datetime.datetime.now().isoformat(timespec="seconds"),
                                                 "canvas_url": result["canvas_url"]})
        json.dump(state, open(os.path.join(pack, "report.json"), "w"), indent=1)
    else:
        print("preview failed:", result)
        raise SystemExit(1)


def publish_canvas(args):
    pack = args.pack.rstrip("/")
    meta, _speeches = load(pack)
    report_path = os.path.join(pack, "report.md")
    if not os.path.exists(report_path):
        raise SystemExit("no report.md in the pack: generate it first (without --publish)")
    report = open(report_path, encoding="utf-8").read()
    state = {}
    if os.path.exists(os.path.join(pack, "report.json")):
        state = json.load(open(os.path.join(pack, "report.json")))
    blockers = dr.publish_blockers(state, force=args.force)
    if blockers:
        print("refusing to publish:")
        for b in blockers:
            print("  " + b)
        for p in state.get("problems") or []:
            print("  [check] %s" % p)
        print("Failed checks: fix the report by hand, re-run generation, or pass --force. "
              "Provisional: confirm the checklist and regenerate; no flag clears it.")
        raise SystemExit(2)
    if args.with_clips:
        # to Drive, never to Slack: the canvas gets the folder link
        from src import drivepack
        url, done = drivepack.publish(pack, log=print)
        state["drive_upload"] = {"url": url, "files": len(done)}
        meta = json.load(open(os.path.join(pack, "pack.json")))
        meta["speakers_total"] = len(_speeches); meta["hansard_url"] = "https://hansard.parliament.uk/{0}/{1}/debates/{2}/".format(
            meta.get("house", "Commons"), meta.get("date"), meta.get("ext_id"))
    title = "%s — %s" % (meta.get("title"), meta.get("date"))
    secrets = publish.load_secrets()
    result = publish.slack_publish_canvas(secrets, title, dr.canvas_body(meta, report, selection=load_selection(pack)), dr.canvas_summary(meta))
    if result.get("canvas_url"):
        print("canvas:", result["canvas_url"])
        state["published"] = {"at": datetime.datetime.now().isoformat(timespec="seconds"),
                              "canvas_url": result["canvas_url"], "message_ts": result.get("message_ts")}
        if args.with_clips:
            state["published"]["clips"] = state.get("drive_upload")
        json.dump(state, open(os.path.join(pack, "report.json"), "w"), indent=1)
    else:
        print("publish failed:", result)
        raise SystemExit(1)


def clips_to_upload(pack):
    """The captioned reel, then the full-speech clips of the speakers in sequence.md,
    in sequence order: [(path, title)]. Nothing under clips/stale."""
    import glob
    import re
    final = os.path.join(pack, "clips", "final")
    out = []
    reel = os.path.join(final, "social-cut-vertical-1080-captioned.mp4")
    if os.path.exists(reel):
        out.append((reel, "Reel (vertical, captioned)"))
    seq = os.path.join(pack, "sequence.md")
    names = [e["name"] for e in sc.parse_sequence(open(seq, encoding="utf-8").read())] if os.path.exists(seq) else []
    for name in names:
        slug = sc.slug(re.sub(r"\s*MP$", "", name))
        for path in sorted(glob.glob(os.path.join(final, "speech-*-%s-*.mp4" % slug))):
            if path.endswith("-clean.mp4"):
                continue
            out.append((path, "%s — full speech (16:9, subtitled)" % re.sub(r"\s*MP$", "", name)))
    return out


def upload_clips(pack, secrets, thread_ts):
    """Upload the clips into the thread under the channel message; report each."""
    done = []
    for path, title in clips_to_upload(pack):
        result = publish.slack_upload_file(secrets, path, title, thread_ts=thread_ts,
                                           comment="Parliamentary Recording Unit terms apply to any campaign use of this footage.")
        status = "ok %.0f MB" % (result["bytes"] / 1e6) if result.get("file_id") else "FAILED: %s" % (result.get("error") or result.get("skipped"))
        print("  clip %-60s %s" % (os.path.basename(path), status))
        done.append({"file": os.path.relpath(path, pack), "title": title, "result": result})
    return done


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pack", required=True)
    ap.add_argument("--dry-run", action="store_true", help="show what would be sent and spend nothing")
    ap.add_argument("--no-dm", action="store_true", help="write the files, do not DM")
    ap.add_argument("--provisional", action="store_true",
                    help="let the pass read stand in for a blank checklist; the result is marked and cannot be published")
    ap.add_argument("--preview", action="store_true", help="the canvas as it will render, shared with you alone via DM; never the channel")
    ap.add_argument("--publish", action="store_true", help="post the approved report as a canvas to the channel")
    ap.add_argument("--force", action="store_true", help="publish even though checks failed (say why in the channel)")
    ap.add_argument("--with-clips", action="store_true", help="with --publish: put the reel, clips and logs on Drive first (tools/drive_pack.py) and link the folder from the canvas")
    args = ap.parse_args()
    if args.preview and args.publish:
        raise SystemExit("--preview or --publish, not both")
    if args.preview:
        preview_canvas(args)
    elif args.publish:
        publish_canvas(args)
    else:
        generate(args)


if __name__ == "__main__":
    main()
