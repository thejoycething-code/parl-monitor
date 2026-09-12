"""Full speeches as 16:9 clips, word-exact, subtitled (Christopher, 2026-09-11).

The reel pipeline (socialcut) cuts a 30-60 second passage and crops it vertical.
This cuts the WHOLE speech, keeps the 1920x1080 frame, and burns subtitles and a
name plate, so a speech can go out in full on YouTube or a page while the reel
goes to Instagram. Same machinery, three differences:

* the passage is the whole contribution, so the trim is anchored on its FIRST and
  LAST twenty-five Hansard words, each located in the window's transcript. Hansard
  timestamps alone are a minute out either way (the shotlist's 16:30:00 for a member
  who stood at 16:30:41), which is why the old --download clips began mid-sentence
  of the previous speaker;
* the footage is the speaker's own Hansard span fetched by HLS segment at 1080p
  with a margin, not the whole sitting (a ten-minute speech is about 225 MB);
* captions are the Hansard text of the speech in 16:9-sized cards, each timed
  against the part's own transcript (card_times), so a misheard word in the
  transcript never reaches the screen but the timing is what was spoken.

Interventions are skipped: a contribution under MIN_WORDS words is a question to
someone else's speech, not a speech.
"""

import datetime
import json
import os
import re
import shutil

from src import alignclip, socialcut as sc

MIN_WORDS = 120            # below this a contribution is an intervention
MERGE_GAP_S = 240.0        # a speaker's next contribution within this of the last one's end is the same speech
ANCHOR_WORDS = 25          # Hansard words used to find the speech's first and last moment
MARGIN_S = 25.0            # fetched either side of the Hansard span
TAIL_MARGINS = (25.0, 150.0, 420.0)   # forward margins tried until the speech's last words are heard
PLAY = (1920, 1080)
CAPTION_POS = (960, 985)
CAPTION_SIZE = 46
CAPTION_MAX_CHARS = 44
PLATE_Y, PLATE_X = 840, 80
TAIL = 0.8


def sitting_seconds(state, iso):
    return (datetime.datetime.fromisoformat(iso) - datetime.datetime.fromisoformat(state["event_start"])).total_seconds()


def plan(state, speeches, onside_fn, min_words=MIN_WORDS, only=None):
    """[(speaker, contribution, (start_s, end_s))]: each onside speaker's speeches,
    each matched to the Hansard span that begins nearest its clock time.

    `speeches` is socialcut.parse_speeches output; `onside_fn(speaker) -> bool`
    is the caller's rule (confirmed, or the pass read standing in). A speech with
    no span within 120 seconds of its time is reported, not guessed at.
    """
    out = []
    spans_by_name = {}
    for sp in state.get("speakers") or []:
        spans_by_name[(sp.get("name") or "").strip().lower()] = [
            (sitting_seconds(state, a), sitting_seconds(state, b)) for a, b in (sp.get("spans") or [])]
    for s in speeches:
        if not onside_fn(s):
            continue
        if only and _bare(s["name"]) not in {_bare(o) for o in only}:
            continue
        spans = spans_by_name.get(re.sub(r"\s*MP$", "", s["name"]).strip().lower(), [])
        placed = []
        for c in s.get("contributions") or []:
            if not (c.get("text") or "").strip():
                continue
            at = _clock_seconds(state, c.get("at"))
            match = None
            if at is not None and spans:
                match = min(spans, key=lambda ab: abs(ab[0] - at))
                if abs(match[0] - at) > 120:
                    match = None
            placed.append((c, match))
        for c, span in merge_speech(placed):
            if (c.get("words") or 0) < min_words:
                continue
            out.append((s, c, span))
    return out


def merge_speech(placed, gap=MERGE_GAP_S):
    """A speech interrupted by interventions is one speech: Karen Bradley's on
    11 September 2026 came out as five clips because each answer after an
    intervention is its own Hansard contribution. Consecutive contributions whose
    spans sit within `gap` seconds of each other are merged -- text joined, words
    summed, the span from the first start to the last end -- so the clip carries
    the interventions and the replies, as the viewer in the gallery heard them.
    Unplaced contributions (no span) are never merged with anything."""
    out = []
    for c, span in placed:
        if out and span and out[-1][1] and span[0] - out[-1][1][1] <= gap and span[0] >= out[-1][1][0]:
            prev, pspan = out[-1]
            merged = dict(prev)
            merged["text"] = (prev.get("text") or "") + " " + (c.get("text") or "")
            merged["words"] = (prev.get("words") or 0) + (c.get("words") or 0)
            merged["merged"] = prev.get("merged", 1) + 1
            merged["ends_at"] = c.get("at")
            out[-1] = (merged, (pspan[0], max(pspan[1], span[1])))
        else:
            out.append((dict(c), span))
    return out


def _bare(name):
    return re.sub(r"\s*MP$", "", name or "").strip().lower()


def _clock_seconds(state, hms):
    """A Hansard clock time (London, 'HH:MM:SS') -> seconds into the sitting."""
    if not hms:
        return None
    from src import debatepack as dp
    ev = datetime.datetime.fromisoformat(state["event_start"]).astimezone(dp.LONDON)
    h, m, s = (int(x) for x in hms.split(":"))
    t = ev.replace(hour=h, minute=m, second=s)
    if t < ev - datetime.timedelta(hours=6):        # a sitting that ran past midnight
        t += datetime.timedelta(days=1)
    return (t - ev).total_seconds()


def anchors(text, n=ANCHOR_WORDS):
    words = (text or "").split()
    return " ".join(words[:n]), " ".join(words[-n:])


def trim_bounds(words, text, file_start, span, margin=MARGIN_S, log=None):
    """(start, end) within the window file: the first Hansard words in, the last out.
    Falls back to the Hansard span (rebased to the file) for whichever end the
    transcript could not place, and says so."""
    head, tail = anchors(text)
    first = sc.word_span(words, head, min_ratio=0.5)
    # The tail is searched only AFTER the head. Once the window is widened forward by
    # up to seven minutes it holds the speaker's later contributions and other members'
    # replies, and a stock closing ("I will not give way", "I commend the Bill to the
    # House") can match earlier or later than the one this speech ends on; the earlier
    # case put the end before the start and forced a five-second stub (11 Sept 2026).
    after = first[1] + 1 if first else 0
    last = sc.word_span(words[after:], tail, min_ratio=0.5)
    if last:
        last = (last[0] + after, last[1] + after, last[2])
    note = []
    if first:
        start, _ = sc.cut_bounds(words, first[0], first[0])
    else:
        start = max(0.0, span[0] - file_start); note.append("start from Hansard time")
    if last:
        end = words[last[1]][2] + TAIL
    else:
        end = span[1] - file_start; note.append("end from Hansard time")
    if end <= start + 5:
        end = max(start + 5, span[1] - file_start); note.append("end forced after start")
    if log and note:
        log("  [trim] " + "; ".join(note))
    return start, end, (first[2] if first else None), (last[2] if last else None)


def caption_items(name, party, duration, heard, text):
    cards = sc.chunk_caption(text, max_chars=CAPTION_MAX_CHARS)
    times = sc.card_times(heard, cards, text)
    return {"name": name, "party": party, "duration": duration,
            "cards": [(c, t[0], t[1]) for c, t in zip(cards, times)]}


def ass_landscape(item):
    return sc.ass_document([item], sc.FONT, PLAY, CAPTION_POS, CAPTION_SIZE, PLATE_Y, PLATE_X)


def srt(item):
    """A plain .srt of the same cards, for platforms that take their own captions."""
    def ts(t):
        ms = int(round((t % 1) * 1000)); t = int(t)
        return "%02d:%02d:%02d,%03d" % (t // 3600, t % 3600 // 60, t % 60, ms)
    out = []
    for i, (lines, a, b) in enumerate(item["cards"], 1):
        out += [str(i), "%s --> %s" % (ts(a), ts(max(b, a + 0.8))), "\n".join(lines), ""]
    return "\n".join(out)


def build(pack_dir, ff, log=print, whisper_model="small.en", only=None, provisional=True, height=1080):
    """Cut every onside speech in the pack as a subtitled 16:9 clip. Returns the report rows."""
    from src import debatereport, debatepack as dp, hlsfetch
    state = json.load(open(os.path.join(pack_dir, "pack.json")))
    speeches = sc.parse_speeches(open(os.path.join(pack_dir, "speeches.md"), encoding="utf-8").read())

    def onside(s):
        return s.get("confirmed") == "yes" or (provisional and debatereport.stands_in_for_onside(s))
    todo = plan(state, speeches, onside, only=only)
    if not todo:
        raise SystemExit("no onside speech of %d words or more to cut" % MIN_WORDS)
    from src import alignment
    alignment.check(pack_dir, ff, whisper_model=whisper_model, log=log)
    manifest = state.get("manifest")
    if not manifest:
        raise SystemExit("pack.json has no manifest; run tools/debate_pack.py --pack F --download once, or social_cut, to resolve the stream")
    clips = os.path.join(pack_dir, "clips")
    hd, final = os.path.join(clips, "speech-hd"), os.path.join(clips, "final")
    for d in (hd, final):
        os.makedirs(d, exist_ok=True)
    fontsdir = os.path.join(hd, "fonts"); os.makedirs(fontsdir, exist_ok=True)
    for f in ("/System/Library/Fonts/HelveticaNeue.ttc", "/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf"):
        if os.path.exists(f) and not os.path.exists(os.path.join(fontsdir, os.path.basename(f))):
            shutil.copy(f, fontsdir)
    logo = sc.LOGO if os.path.exists(sc.LOGO) else None
    rows = []
    n = 0
    for s, c, span in todo:
        n += 1
        tag = "%02d-%s-%s" % (n, sc.slug(s["name"]), (c.get("at") or "").replace(":", ""))
        if span is None:
            log("  %s: no Hansard span within two minutes of %s; skipped" % (s["name"], c.get("at")))
            rows.append((s, c, None, "no span")); continue
        window = os.path.join(hd, tag + "-window.mp4")
        words_json = os.path.join(hd, tag + "-window.words.json")
        # The span's END is an estimate (the next contribution's start, itself
        # estimated), and on 11 September it fell short: sixteen of nineteen clips
        # anchored their start and lost their tail, ending on Hansard time. So the
        # window grows FORWARD until the speech's last words are heard, or the cap.
        start = end = r1 = r2 = None
        for tail_margin in TAIL_MARGINS:
            if os.path.exists(window) and os.path.exists(window + ".json"):
                have = json.load(open(window + ".json"))
                if have.get("tail_margin", MARGIN_S) < tail_margin or have.get("tail_margin") is None and tail_margin != TAIL_MARGINS[0]:
                    for f in (window, words_json, os.path.join(hd, tag + "-window.wav")):
                        if os.path.exists(f):
                            os.remove(f)
            if not os.path.exists(window):
                file_start, raw = hlsfetch.fetch_window(manifest, span[0], span[1] + (tail_margin - MARGIN_S), window, ff, height=height, margin=MARGIN_S, log=None)
                json.dump({"file_start": file_start, "tail_margin": tail_margin}, open(window + ".json", "w"))
                log("  %s: fetched %.0f MB for %s (tail margin %.0fs)" % (s["name"], raw / 1e6, c.get("at"), tail_margin))
            file_start = json.load(open(window + ".json"))["file_start"]
            words = alignclip.transcribe(window, os.path.join(hd, tag + "-window.wav"), ff, model_size=whisper_model, words_json=words_json, log=lambda *_a: None)
            start, end, r1, r2 = trim_bounds(words, c["text"], file_start, span, log=None)
            if r2 is not None or tail_margin == TAIL_MARGINS[-1]:
                break
            log("  %s: last words not heard within %.0fs of the span's end; widening" % (s["name"], tail_margin))
        if r1 is None or r2 is None:
            log("  [trim] %s%s" % ("start from Hansard time" if r1 is None else "", "; end from Hansard time" if r2 is None else ""))
        part = os.path.join(hd, tag + ".mp4")
        sc._run([ff, "-y", "-loglevel", "error", "-ss", "%.3f" % start, "-i", window, "-t", "%.3f" % (end - start),
                 "-vf", "fps=25,format=yuv420p", "-c:v", "libx264", "-crf", "18", "-preset", "medium",
                 "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2", part])
        dur = sc._dur(ff, part)
        heard = alignclip.transcribe(part, os.path.join(hd, tag + "-part.wav"), ff, model_size=whisper_model,
                                     words_json=os.path.join(hd, tag + "-part.words.json"), log=lambda *_a: None)
        name = s["name"] if s["name"].endswith(" MP") else s["name"] + " MP"
        party = " · ".join(x for x in (sc.PARTY.get(s.get("party"), s.get("party")), s.get("seat")) if x)
        item = caption_items(name, party, dur, heard, c["text"])
        ass_path = os.path.join(hd, tag + ".ass")
        open(ass_path, "w", encoding="utf-8").write(ass_landscape(item))
        open(os.path.join(final, "speech-" + tag + ".srt"), "w", encoding="utf-8").write(srt(item))
        clean = os.path.join(final, "speech-" + tag + "-clean.mp4")
        shutil.copy(part, clean)
        filt = ("[1:v]scale=%d:-1[lg];[0:v][lg]overlay=%d:70[v1];[v1]" % (sc.LOGO_W, PLAY[0] - sc.LOGO_W - 70) if logo else "[0:v]") + \
               "ass=%s:fontsdir=%s[v]" % (ass_path, fontsdir)
        out = os.path.join(final, "speech-" + tag + ".mp4")
        sc._run([ff, "-y", "-loglevel", "error", "-i", part] + (["-i", logo] if logo else []) +
                ["-filter_complex", filt, "-map", "[v]", "-map", "0:a", "-c:v", "libx264", "-crf", "18", "-preset", "medium",
                 "-c:a", "copy", "-movflags", "+faststart", out])
        log("  %-28s %s  %6.1fs  in %.2f out %.2f  -> %s" % (s["name"], c.get("at"), dur, r1 or 0, r2 or 0, os.path.basename(out)))
        rows.append((s, c, (start, end, dur, r1, r2), os.path.relpath(out, pack_dir)))
    write_report(pack_dir, rows)
    return rows


def write_report(pack_dir, rows):
    lines = ["# Full speeches, 16:9", "",
             "Cut from each onside speaker's own Hansard span at 1080p, trimmed to the speech's first and last",
             "Hansard words as heard, subtitled from the Hansard text timed against the speech. Clips in",
             "clips/final/speech-*.mp4 (subtitled) and *-clean.mp4 (no burn), with a .srt each. Parliamentary",
             "Recording Unit terms apply.", ""]
    for s, c, cut, where in rows:
        if cut is None:
            lines.append("* %s, %s: %s" % (s["name"], c.get("at"), where)); continue
        start, end, dur, r1, r2 = cut
        lines.append("* %s, %s: %.0f s (%d Hansard words); anchors matched %s / %s; %s"
                     % (s["name"], c.get("at"), dur, c.get("words") or 0,
                        "%.2f" % r1 if r1 else "Hansard time", "%.2f" % r2 if r2 else "Hansard time", where))
    open(os.path.join(pack_dir, "speeches-cut.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")


ASPECTS = {
    # name: (crop width in the 1920x1080 source, output size, caption pos, caption size, max chars, plate y, plate x)
    "16:9": (1920, (1920, 1080), CAPTION_POS, CAPTION_SIZE, CAPTION_MAX_CHARS, PLATE_Y, PLATE_X),
    "4:5": (864, (1080, 1350), (540, 1215), 50, 30, 1030, 60),
}


def recaption(pack_dir, ff, log=print, only=None, provisional=True, aspect="16:9", crop=None):
    """Re-time and re-burn the captions on parts already in clips/speech-hd: no fetching,
    no transcribing. For the clips whose caption timing was wrong (11 September 2026),
    and for another aspect: "4:5" crops the 16:9 part to 864x1080 about the speaker's
    reel crop (sequence.md `crop:`, else centre) and scales to 1080x1350."""
    from src import debatereport
    state = json.load(open(os.path.join(pack_dir, "pack.json")))
    speeches = sc.parse_speeches(open(os.path.join(pack_dir, "speeches.md"), encoding="utf-8").read())
    crops = {}
    seq_path = os.path.join(pack_dir, "sequence.md")
    if os.path.exists(seq_path):
        for e in sc.parse_sequence(open(seq_path, encoding="utf-8").read()):
            crops[_bare(e["name"])] = e.get("crop") or "centre"
    crop_w, play, cpos, csize, cmax, plate_y, plate_x = ASPECTS[aspect]
    suffix = "" if aspect == "16:9" else "-" + aspect.replace(":", "x")

    def onside(s):
        return s.get("confirmed") == "yes" or (provisional and debatereport.stands_in_for_onside(s))
    clips = os.path.join(pack_dir, "clips")
    hd, final = os.path.join(clips, "speech-hd"), os.path.join(clips, "final")
    fontsdir = os.path.join(hd, "fonts")
    logo = sc.LOGO if os.path.exists(sc.LOGO) else None
    done = []
    n = 0
    for s, c, span in plan(state, speeches, onside, only=only):
        n += 1
        # The part is found by speaker and clock, not by its ordinal: a --only run
        # numbers from 01 while the parts on disk carry the full run's numbers.
        stem = "%s-%s" % (sc.slug(s["name"]), (c.get("at") or "").replace(":", ""))
        found = [f for f in os.listdir(hd) if re.match(r"\d+-%s\.mp4$" % re.escape(stem), f)]
        if not found:
            log("  %s %s: no part on disk; run the cut first" % (s["name"], c.get("at")))
            continue
        # the newest, not the highest-numbered: an earlier run's parts can linger beside the current set
        tag = max(found, key=lambda f: os.path.getmtime(os.path.join(hd, f)))[:-4]
        part, words_json = os.path.join(hd, tag + ".mp4"), os.path.join(hd, tag + "-part.words.json")
        if not os.path.exists(words_json):
            log("  %s %s: part has no transcript on disk; run the cut first" % (s["name"], c.get("at")))
            continue
        heard = [tuple(w) for w in json.load(open(words_json))]
        dur = sc._dur(ff, part)
        name = s["name"] if s["name"].endswith(" MP") else s["name"] + " MP"
        party = " · ".join(x for x in (sc.PARTY.get(s.get("party"), s.get("party")), s.get("seat")) if x)
        cards = sc.chunk_caption(c["text"], max_chars=cmax)
        times = sc.card_times(heard, cards, c["text"])
        item = {"name": name, "party": party, "duration": dur, "cards": [(cd, tm[0], tm[1]) for cd, tm in zip(cards, times)]}
        ass_path = os.path.join(hd, tag + suffix + ".ass")
        open(ass_path, "w", encoding="utf-8").write(sc.ass_document([item], sc.FONT, play, cpos, csize, plate_y, plate_x))
        open(os.path.join(final, "speech-" + tag + suffix + ".srt"), "w", encoding="utf-8").write(srt(item))
        chain, src = [], "[0:v]"
        if aspect != "16:9":
            # `crop` overrides for this run: the Chamber's cameras alternate a medium shot with
            # a wide two-shot, and one speaker can stand at x=900 in one and x=540 in the other
            # (Carla Lockhart, 11 Sept 2026); a centre crop cut her off in the second.
            x = sc.crop_x(crop or crops.get(_bare(s["name"]), "centre"), frame_w=1920, crop_w=crop_w)
            geometry = "crop=%d:1080:%d:0,scale=%d:%d:flags=lanczos,format=yuv420p" % (crop_w, x, play[0], play[1])
            clean = os.path.join(final, "speech-" + tag + suffix + "-clean.mp4")
            sc._run([ff, "-y", "-loglevel", "error", "-i", part, "-vf", geometry, "-c:v", "libx264", "-crf", "18",
                     "-preset", "medium", "-c:a", "copy", "-movflags", "+faststart", clean])
            chain.append("[0:v]" + geometry + "[c]"); src = "[c]"
        if logo:
            lx, ly = ((play[0] - sc.LOGO_W - 70), 70) if aspect == "16:9" else (60, 60)
            chain.append("[1:v]scale=%d:-1[lg]" % sc.LOGO_W)
            chain.append("%s[lg]overlay=%d:%d[v1]" % (src, lx, ly)); src = "[v1]"
        chain.append("%sass=%s:fontsdir=%s[v]" % (src, ass_path, fontsdir))
        filt = ";".join(chain)
        out = os.path.join(final, "speech-" + tag + suffix + ".mp4")
        sc._run([ff, "-y", "-loglevel", "error", "-i", part] + (["-i", logo] if logo else []) +
                ["-filter_complex", filt, "-map", "[v]", "-map", "0:a", "-c:v", "libx264", "-crf", "18", "-preset", "medium",
                 "-c:a", "copy", "-movflags", "+faststart", out])
        gaps = sum(b[1] - a[2] for a, b in zip(item["cards"], item["cards"][1:]) if b[1] - a[2] > 3)
        log("  %-28s %s  %6.1fs  %3d cards, %.0fs uncaptioned  -> %s" % (s["name"], c.get("at"), dur, len(cards), gaps, os.path.basename(out)))
        done.append(out)
    return done
