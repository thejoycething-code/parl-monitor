"""Build a debate pack (src/debatepack.py) for one debate.

    python3 tools/debate_pack.py --date 2026-09-07 --find surrogacy            # build (reads direction: one API call)
    python3 tools/debate_pack.py --date 2026-09-07 --debate <hansard ext id>    # by id instead of title search
        [--house Commons] [--event <parliamentlive url or guid>] [--venue "Westminster Hall"] [--no-read]
    python3 tools/debate_pack.py --pack data/packs/<folder> --apply             # after filling checklist.md
    python3 tools/debate_pack.py --pack data/packs/<folder> --download [--quality 1300]   # clips of confirmed speakers
    python3 tools/debate_pack.py --pack data/packs/<folder> --download-debate --from 16:30 --to 18:00   # the whole debate, one file

Footage needs yt-dlp (pip install --user yt-dlp) and an ffmpeg (pip install
--user imageio-ffmpeg); both are found automatically. The sitting's footage is found through
parliamentlive.tv's archive search for the date (any day since December 2007);
--event overrides it.
Reading direction spends one API call per twenty speakers, cached in
pack.json so a re-run never pays twice.
"""

import argparse
import datetime
import json
import os
import shutil
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import debatepack as dp, filter as filt, publish, spend, db  # noqa: E402
from src.http import HttpClient  # noqa: E402


def tools():
    yt = shutil.which("yt-dlp") or os.path.expanduser("~/Library/Python/3.9/bin/yt-dlp")
    ff = shutil.which("ffmpeg")
    if not ff:
        try:
            import imageio_ffmpeg
            ff = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:                                   # noqa: BLE001
            ff = None
    return (yt if os.path.exists(yt) else None), ff


def build(args):
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    if args.debate:
        ext, title, section = args.debate, None, None
        payload = dp.fetch_debate(client, ext)
        title = (payload.get("Overview") or {}).get("Title") or "Debate"
    else:
        found = dp.find_debate(client, args.date, args.find, args.house)
        if not found:
            print("no debate titled like '{0}' on {1} in the {2} yet. Hansard publishes text a few hours after the "
                  "House rises; try again later, or give --debate <ext id>.".format(args.find, args.date, args.house))
            return 1
        if len(found) > 1:
            print("several debates match; name one with --debate:")
            for t, sec, e in found:
                print("  {0}  {1}  [{2}]".format(e, t, sec))
            return 1
        title, section, ext = found[0]
        payload = dp.fetch_debate(client, ext)
    rows = dp.contributions(payload, args.date)
    speaks = dp.speakers(rows)
    mins = dp.minister(rows)
    if not speaks:
        print("Hansard has the section but no contributions yet for {0}; try again later.".format(title))
        return 1
    tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
    wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))
    r = filt.filter_item(tax, wl, title, " ".join(s["text"] for s in speaks)[:20000])
    areas = [a for a in (r.issue_areas or []) if a != 11] or list(tax.terms)
    patterns = [it[1] for a in areas for _t, items in sorted((tax.terms.get(a) or {}).items()) for it in items]

    folder = os.path.join(dp.PACKS, "{0}-{1}".format(args.date, dp.slug(title)))
    os.makedirs(folder, exist_ok=True)
    state_path = os.path.join(folder, "pack.json")
    state = json.load(open(state_path)) if os.path.exists(state_path) else {}
    directions = state.get("directions") or {}
    # Re-read a speaker whose words have grown since they were read: Hansard
    # publishes in tranches, and Jim Shannon was read on a 53-word
    # intervention and kept that reading when his 1,000-word speech arrived
    # (2026-09-07). The reading is cached against the word count it saw.
    def stale(s):
        d = directions.get(str(s["member_id"] or s["name"]))
        return d is None or (d.get("words") is not None and s["words"] > d["words"] * 1.5 + 40)
    missing = [s for s in speaks if stale(s)]
    if missing and not args.no_read:
        key = publish.load_secrets().get("anthropic_api_key") or os.environ.get("ANTHROPIC_API_KEY")
        if key:
            conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
            got = dp.read_direction(missing, title, areas, key,
                                    usage_sink=lambda usage, model: spend.record(conn, "debate-pack", model, usage))
            conn.close()
            for s in missing:
                key_ = str(s["member_id"] or s["name"])
                if key_ in got:
                    got[key_]["words"] = s["words"]
            directions.update(got)
            print("direction read for {0} speaker(s) ({1} API call(s))".format(len(got), (len(missing) + 19) // 20))
        else:
            print("no anthropic_api_key: directions not read (pass --no-read to silence this)")
    guid = dp.event_guid(args.event) if args.event else state.get("event")
    event_start = None
    manifest = state.get("manifest")
    yt, ff = tools()
    venue = args.venue or ("Westminster Hall" if section == "WestHall" else
                           ("House of Lords" if args.house == "Lords" else "House of Commons"))
    if not guid:
        # Any date since December 2007: the site's own archive search, by day.
        # Today's sittings sometimes appear there only once they have begun,
        # so the front page is the fallback for the current day.
        try:
            guid = dp.pick_event(dp.search_events(args.date, "Lords" if args.house == "Lords" else "Commons"), venue)
        except Exception as exc:                            # noqa: BLE001
            print("parliamentlive.tv search unavailable ({0})".format(exc))
        if not guid and args.date == datetime.date.today().isoformat():
            try:
                with urllib.request.urlopen(urllib.request.Request("https://parliamentlive.tv/Commons", headers={
                        "User-Agent": "Mozilla/5.0"}), timeout=30) as resp:
                    guid = dp.pick_event(dp.todays_events(resp.read().decode("utf-8", "replace")), venue)
            except Exception as exc:                        # noqa: BLE001
                print("parliamentlive.tv listing unavailable ({0}); footage links need --event".format(exc))
        if not guid:
            print("no {0} sitting found on parliamentlive.tv for {1}; give --event <url> if you have it".format(venue, args.date))
    if guid and yt and not manifest:
        try:
            manifest, es = dp.manifest_for(guid, yt)
            state["event_start"] = es.isoformat()
        except Exception as exc:                            # noqa: BLE001
            print("footage: {0}".format(exc))
    if state.get("event_start"):
        event_start = datetime.datetime.fromisoformat(state["event_start"])
    confirmed = dp.parse_checklist(os.path.join(folder, "checklist.md"))
    dp.write_pack(folder, {"title": title, "house": args.house, "date": args.date, "ext_id": ext}, speaks, directions,
                  confirmed, mins, patterns, guid=guid, event_start=event_start)
    state.update({"title": title, "house": args.house, "date": args.date, "ext_id": ext, "event": guid,
                  "manifest": manifest, "directions": directions, "areas": areas,
                  "speakers": [{"key": str(s["member_id"] or s["name"]), "name": s["name"], "party": s["party"],
                                "seat": s["seat"], "spans": [(a.isoformat(), b.isoformat()) for a, b in s["spans"]],
                                "first": s["first"].isoformat() if s["first"] else None} for s in speaks]})
    json.dump(state, open(state_path, "w"), indent=1)
    print("pack: {0}".format(os.path.relpath(folder, ROOT)))
    print("  {0} speakers, {1} read by the pass, {2} confirmed onside so far; minister: {3}".format(
        len(speaks), len(directions), sum(1 for v in confirmed.values() if v == "yes"),
        mins["attributed"] if mins else "none found"))
    print("  footage: {0}".format("event {0}, manifest ready".format(guid) if manifest else
                                  ("event {0} (no manifest: yt-dlp missing?)".format(guid) if guid else "none (give --event)")))
    print("  next: fill checklist.md, then --apply; then --download for the confirmed speakers")
    return 0


def apply(args):
    # Reads direction for speakers not yet in pack.json (cached ones cost
    # nothing): Hansard publishes a debate in tranches, and a re-apply that
    # skipped the new speakers left three of seven unread (2026-09-07).
    a = argparse.Namespace(date=None, debate=None, find=None, house=None, event=None, venue=None, no_read=args.no_read)
    state = json.load(open(os.path.join(args.pack, "pack.json")))
    a.date, a.debate, a.house, a.event = state["date"], state["ext_id"], state["house"], state.get("event")
    return build(a)


def download(args):
    state = json.load(open(os.path.join(args.pack, "pack.json")))
    yt, ff = tools()
    if not yt:
        print("yt-dlp not found: pip install --user yt-dlp")
        return 1
    manifest = state.get("manifest")
    if not manifest:
        print("no stream for this pack: build it with --event <parliamentlive url> first")
        return 1
    clips = os.path.join(args.pack, "clips")
    os.makedirs(clips, exist_ok=True)
    tz = dp.LONDON
    if args.download_debate:
        d = datetime.date.fromisoformat(state["date"])
        h1, m1 = map(int, args.frm.split(":")); h2, m2 = map(int, args.to.split(":"))
        start = datetime.datetime(d.year, d.month, d.day, h1, m1, tzinfo=tz)
        end = datetime.datetime(d.year, d.month, d.day, h2, m2, tzinfo=tz)
        out = os.path.join(clips, "00-whole-debate-{0}-{1}.mp4".format(args.frm.replace(":", ""), args.to.replace(":", "")))
        dp.download_clip(manifest, start, end, out, yt, ff, args.quality)
        print("downloaded {0} ({1:.1f} MB)".format(os.path.relpath(out, ROOT), os.path.getsize(out) / 1e6))
        return 0
    confirmed = dp.parse_checklist(os.path.join(args.pack, "checklist.md"))
    wanted = [s for s in state["speakers"] if confirmed.get(s["key"]) == "yes"]
    if not wanted:
        print("nobody is marked ONSIDE: yes in checklist.md yet; nothing downloaded. (--download-debate fetches the whole debate.)")
        return 1
    n = 0
    for i, s in enumerate(wanted, 1):
        for j, (a, b) in enumerate(s["spans"], 1):
            start, end = datetime.datetime.fromisoformat(a), datetime.datetime.fromisoformat(b)
            name = dp.slug(s["name"])
            out = os.path.join(clips, "{0:02d}-{1}-{2}-{3}.mp4".format(i, name, j, start.astimezone(tz).strftime("%H%M%S")))
            if os.path.exists(out):
                continue
            try:
                dp.download_clip(manifest, start, end, out, yt, ff, args.quality)
                n += 1
                print("  {0} ({1:.1f} MB)".format(os.path.relpath(out, ROOT), os.path.getsize(out) / 1e6))
            except Exception as exc:                        # noqa: BLE001
                print("  {0}: {1}".format(s["name"], exc))
    print("{0} clip(s) downloaded to {1}".format(n, os.path.relpath(clips, ROOT)))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date"); ap.add_argument("--find"); ap.add_argument("--debate")
    ap.add_argument("--house", default="Commons"); ap.add_argument("--event"); ap.add_argument("--venue")
    ap.add_argument("--no-read", action="store_true")
    ap.add_argument("--pack"); ap.add_argument("--apply", action="store_true")
    ap.add_argument("--download", action="store_true"); ap.add_argument("--download-debate", action="store_true")
    ap.add_argument("--from", dest="frm"); ap.add_argument("--to"); ap.add_argument("--quality", default="1300")
    args = ap.parse_args()
    if args.pack and (args.download or args.download_debate):
        return download(args)
    if args.pack and args.apply:
        return apply(args)
    if args.date and (args.find or args.debate):
        return build(args)
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
