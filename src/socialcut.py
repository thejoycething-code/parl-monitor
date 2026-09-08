"""The social cut: a short vertical video of MPs speaking, built from a debate pack.

What this encodes (learnt on the surrogacy debate, 7-8 September 2026):

* the sequence is a file the campaigner writes (`sequence.md` in the pack): who, in
  what order, which spoken words; the tool never chooses the order or the passage;
* footage is pulled fresh from the parliamentlive.tv archive at 1080p, one short
  window per excerpt, and each window is transcribed and the passage found by its
  words, because the archive's clock is not the live stream's;
* cuts are word-exact: hard in on the first word, a short tail after the last;
* the vertical is a full-height 9:16 crop placed per speaker (the picture, not a
  blurred letterbox), so each speaker fills the frame;
* captions are the SPOKEN words, one or two lines, centred on one fixed point so the
  text never moves between cards; Hansard wording belongs in the article, not on the
  picture, because a caption that differs from the audio reads as a misquote;
* the name plate is CitizenGO principal blue over an ink strip, shown for the first
  five seconds of each excerpt; the white logo sits top-left; no end card unless asked;
* a contact sheet (one frame per speaker) is written so the crop can be checked by eye.

Pure functions here are tested; the pipeline (`build`) needs yt-dlp, ffmpeg and
faster-whisper and is exercised by hand.
"""

import datetime
import json
import math
import os
import re
import shutil
import subprocess

from src import alignclip

# CitizenGO brand tokens (the Clacton page's :root): principal blue, ink, muted grey.
BLUE = "#4285F4"
INK = "#202124"
MUTED = "#52575C"
FONT = "Helvetica Neue"          # Roboto is the brand face; it is not installed on the build Mac
FRAME_W, FRAME_H = 1080, 1920
CROP_W, CROP_H = 608, 1080       # 9:16 of a 1080-tall frame (even width for yuv420p)
CAPTION_POS = (540, 1600)        # every caption card is centred here
CAPTION_SIZE = 66
CAPTION_MAX_CHARS = 30
CAPTION_MAX_LINES = 2
PLATE_SECONDS = 5.2
PLATE_Y = 1290
LOGO_W = 300
LOGO = os.path.join("docs", "logos", "citizengo-white.png")
CROP_ANCHORS = {"left": 0.40, "centre": 0.50, "center": 0.50, "right": 0.60}
TAIL = 0.55


def ass_colour(hex_rgb, alpha=0):
    """'#RRGGBB' -> ASS style colour '&HAABBGGRR&'."""
    h = hex_rgb.lstrip("#")
    return "&H%02X%s%s%s&" % (alpha, h[4:6], h[2:4], h[0:2])


def override_colour(hex_rgb):
    """'#RRGGBB' -> the '&HBBGGRR&' form used by \\1c overrides."""
    h = hex_rgb.lstrip("#")
    return "&H%s%s%s&" % (h[4:6], h[2:4], h[0:2])


# ---------------------------------------------------------------- the sequence file

def parse_sequence(text):
    """`sequence.md`:

        ## Shivani Raja MP
        party: Conservative · Leicester East
        crop: centre            (left | centre | right | a pixel x in the 1920 frame; default centre)
        > A child cannot consent to a surrogacy arrangement. They cannot understand
        > the promises adults have made.

    The blockquote is the passage as SPOKEN (Hansard wording is fine to start with;
    the report shows what was heard so it can be corrected). Order in the file is
    the order in the cut.
    """
    entries = []
    cur = None
    for raw in (text or "").splitlines():
        line = raw.rstrip()
        if line.startswith("## "):
            cur = {"name": line[3:].strip(), "party": "", "crop": "centre", "passage": ""}
            entries.append(cur)
        elif cur is None or not line.strip() or line.startswith("#"):
            continue
        elif line.startswith(">"):
            cur["passage"] = (cur["passage"] + " " + line.lstrip("> ").strip()).strip()
        else:
            m = re.match(r"^(party|crop)\s*:\s*(.+)$", line.strip(), re.I)
            if m:
                cur[m.group(1).lower()] = m.group(2).strip()
    return [e for e in entries if e["passage"]]


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


# ---------------------------------------------------------------- captions

_SENTENCE_END = re.compile(r"(?<=[.!?;])\s+")


def _wrap(words, max_chars):
    lines, cur = [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > max_chars:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        lines.append(cur)
    return lines


def _balanced(words, n_lines, max_chars):
    """Split words into n_lines lines of roughly equal length."""
    if n_lines <= 1:
        return [" ".join(words)]
    total = sum(len(w) + 1 for w in words)
    target = total / float(n_lines)
    lines, cur, used = [], [], 0
    for w in words:
        if cur and used + len(w) + 1 > target * (len(lines) + 1) and len(lines) < n_lines - 1:
            lines.append(" ".join(cur))
            cur = []
        cur.append(w)
        used += len(w) + 1
    if cur:
        lines.append(" ".join(cur))
    # a balanced line may still overrun on one long word: fall back to greedy wrapping
    if any(len(l) > max_chars for l in lines):
        return _wrap(words, max_chars)
    return lines


def chunk_caption(text, max_chars=CAPTION_MAX_CHARS, max_lines=CAPTION_MAX_LINES):
    """Cards of at most `max_lines` lines of at most `max_chars` characters. A card never
    crosses a sentence boundary; a long sentence becomes several balanced cards."""
    cards = []
    for sentence in _SENTENCE_END.split((text or "").strip()):
        words = sentence.split()
        if not words:
            continue
        n_lines = len(_wrap(words, max_chars))
        n_cards = int(math.ceil(n_lines / float(max_lines)))
        if n_cards <= 1:
            cards.append(_balanced(words, n_lines, max_chars))
            continue
        # split the sentence's words into n_cards groups of similar length, then balance each
        total = sum(len(w) + 1 for w in words)
        groups, cur, used = [], [], 0
        for w in words:
            if cur and used + len(w) + 1 > total * (len(groups) + 1) / float(n_cards) and len(groups) < n_cards - 1:
                groups.append(cur)
                cur = []
            cur.append(w)
            used += len(w) + 1
        if cur:
            groups.append(cur)
        for g in groups:
            n = min(max_lines, len(_wrap(g, max_chars)))
            cards.append(_balanced(g, n, max_chars))
    return cards


def card_times(words, cards, passage):
    """Time each card from the transcript words by position in the passage (token
    fraction), so a transcript that hears '50 %' for '50%' still lines up."""
    total = len(alignclip.tokens(passage)) or 1
    n = len(words)
    out, pos = [], 0
    for card in cards:
        k = len(alignclip.tokens(" ".join(card)))
        i0 = min(n - 1, int(round(pos / float(total) * n)))
        i1 = min(n - 1, max(i0, int(round((pos + k) / float(total) * n)) - 1))
        out.append((words[i0][1], words[i1][2]))
        pos += k
    return out


# ---------------------------------------------------------------- geometry

def crop_x(spec, frame_w=1920, crop_w=CROP_W):
    """Left edge of the 9:16 crop for a speaker position: a named anchor or a pixel x
    (the speaker's horizontal centre in the source frame)."""
    s = (spec or "centre").strip().lower()
    if s in CROP_ANCHORS:
        centre = CROP_ANCHORS[s] * frame_w
    else:
        try:
            centre = float(s)
        except ValueError:
            centre = 0.5 * frame_w
    return int(max(0, min(frame_w - crop_w, round(centre - crop_w / 2.0))))


def cut_bounds(words, first_i, last_i, tail=TAIL):
    """Hard in on the first word: if the previous word ends within 0.15s, cut in the
    gap; otherwise a hair before. Out after a short tail."""
    start = words[first_i][1]
    if first_i > 0 and start - words[first_i - 1][2] < 0.15:
        start = (start + words[first_i - 1][2]) / 2.0
    else:
        start = max(0.0, start - 0.05)
    return start, words[last_i][2] + tail


def word_span(words, passage, min_ratio=0.6):
    """Indices of the first and last transcript word of the passage, or None."""
    res = alignclip.align(words, passage, min_ratio=min_ratio)
    if not res:
        return None
    a, b, _r = res
    first = next(i for i, w in enumerate(words) if w[1] >= a - 1e-6)
    last = max(i for i, w in enumerate(words) if w[2] <= b + 1e-6)
    return first, max(first, last), _r


# ---------------------------------------------------------------- the ASS track

def _ts(t):
    return "%d:%02d:%05.2f" % (int(t // 3600), int(t % 3600 // 60), t % 60)


def ass_track(items, font=FONT):
    """items: [{name, party, duration, cards: [(lines, start, end)]}] in cut order,
    times relative to each item's own start."""
    head = "\n".join([
        "[Script Info]", "ScriptType: v4.00+", "PlayResX: %d" % FRAME_W, "PlayResY: %d" % FRAME_H,
        "WrapStyle: 2", "ScaledBorderAndShadow: yes", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: Caption,%s,%d,&H00FFFFFF,&H00FFFFFF,%s,%s,-1,0,0,0,100,100,0,0,1,5,0,5,80,80,0,1" % (font, CAPTION_SIZE, ass_colour(INK), ass_colour(INK)),
        "Style: Name,%s,56,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1" % font,
        "Style: Party,%s,40,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1" % font,
        "Style: Shape,%s,20,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1" % font,
        "", "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text", ""])
    ev, off = [], 0.0
    for it in items:
        dur = it["duration"]
        a, b = off + 0.1, off + min(dur, PLATE_SECONDS)
        w = max(int(len(it["name"]) * 31 + 90), int(len(it.get("party", "")) * 21 + 90))
        ev.append("Dialogue: 0,%s,%s,Shape,,0,0,0,,{\\an7\\pos(60,%d)\\1c%s\\bord0\\shad0\\fad(120,120)\\p1}m 0 0 l %d 0 l %d 78 l 0 78{\\p0}"
                  % (_ts(a), _ts(b), PLATE_Y, override_colour(BLUE), w, w))
        ev.append("Dialogue: 0,%s,%s,Shape,,0,0,0,,{\\an7\\pos(60,%d)\\1c%s\\bord0\\shad0\\fad(120,120)\\p1}m 0 0 l %d 0 l %d 60 l 0 60{\\p0}"
                  % (_ts(a), _ts(b), PLATE_Y + 78, override_colour(INK), w, w))
        ev.append("Dialogue: 1,%s,%s,Name,,0,0,0,,{\\pos(88,%d)\\fad(120,120)}%s" % (_ts(a), _ts(b), PLATE_Y + 8, it["name"]))
        if it.get("party"):
            ev.append("Dialogue: 1,%s,%s,Party,,0,0,0,,{\\pos(88,%d)\\fad(120,120)}%s" % (_ts(a), _ts(b), PLATE_Y + 86, it["party"]))
        cards = it["cards"]
        for i, (lines, s, e) in enumerate(cards):
            nxt = cards[i + 1][1] - 0.05 if i + 1 < len(cards) else dur - 0.05
            end = max(e, min(nxt, e + 1.2))
            ev.append("Dialogue: 2,%s,%s,Caption,,0,0,0,,{\\pos(%d,%d)}%s"
                      % (_ts(off + max(0.0, s - 0.1)), _ts(off + end), CAPTION_POS[0], CAPTION_POS[1], "\\N".join(lines)))
        off += dur
    return head + "\n".join(ev) + "\n"


# ---------------------------------------------------------------- the pipeline

def _dur(ff, path):
    info = subprocess.run([ff, "-i", path], capture_output=True, text=True).stderr
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", info)
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 0.0


def _run(cmd):
    subprocess.run(cmd, check=True, capture_output=True)


def build(pack_dir, ff, yt, render_only=False, log=print, whisper_model="small.en"):
    """Read sequence.md, pull 1080p windows, cut, crop, caption, render, report."""
    from src import debatepack as dp
    seq_path = os.path.join(pack_dir, "sequence.md")
    if not os.path.exists(seq_path):
        raise SystemExit("no sequence.md in the pack: write one (see docs/debate-pack-social.md)")
    entries = parse_sequence(open(seq_path, encoding="utf-8").read())
    if not entries:
        raise SystemExit("sequence.md has no entries with a passage")
    state = json.load(open(os.path.join(pack_dir, "pack.json")))
    clips = os.path.join(pack_dir, "clips")
    hd, final = os.path.join(clips, "hd"), os.path.join(clips, "final")
    for d in (hd, final):
        os.makedirs(d, exist_ok=True)
    whole = [tuple(x) for x in json.load(open(os.path.join(clips, "whole-debate.words.json")))] \
        if os.path.exists(os.path.join(clips, "whole-debate.words.json")) else None
    manifest = event_start = None
    items, report = [], []
    for e in entries:
        s = slug(e["name"])
        window = os.path.join(hd, s + "-window.mp4")
        words_json = os.path.join(hd, s + "-window.words.json")
        if not render_only and not os.path.exists(window):
            if whole is None:
                raise SystemExit("no clips/whole-debate.words.json: transcribe the whole debate first (tools/debate_pack.py --cut)")
            res = alignclip.align(whole, e["passage"], min_ratio=0.5)
            if not res:
                raise SystemExit("could not find the passage for %s in the whole-debate transcript" % e["name"])
            a, b, _r = res
            if manifest is None:
                manifest, event_start = dp.manifest_for(state["event"], yt)
            margin = 10
            for attempt in (1, 2):
                st = event_start + datetime.timedelta(seconds=a - margin)
                en = event_start + datetime.timedelta(seconds=b + margin)
                dp.download_clip(manifest, st, en, window, yt, ff, "1080", guid=state["event"], event_start=event_start, windowed=False)
                ws = alignclip.transcribe(window, os.path.join(hd, s + ".wav"), ff, model_size=whisper_model, words_json=words_json, log=lambda *_a: None)
                if alignclip.align(ws, e["passage"], min_ratio=0.55):
                    break
                if attempt == 1:
                    log("  %s: passage not in the first window, widening" % e["name"])
                    os.remove(window)
                    if os.path.exists(words_json):
                        os.remove(words_json)
                    margin = 45
        if not os.path.exists(words_json):
            alignclip.transcribe(window, os.path.join(hd, s + ".wav"), ff, model_size=whisper_model, words_json=words_json, log=lambda *_a: None)
        words = [tuple(x) for x in json.load(open(words_json))]
        span = word_span(words, e["passage"], min_ratio=0.5)
        if not span:
            raise SystemExit("could not place the passage for %s in its window; check sequence.md against the words heard" % e["name"])
        first, last, ratio = span
        start, end = cut_bounds(words, first, last)
        part, vpart = os.path.join(hd, s + ".mp4"), os.path.join(hd, s + "-v.mp4")
        _run([ff, "-y", "-loglevel", "error", "-ss", "%.3f" % start, "-i", window, "-t", "%.3f" % (end - start),
              "-vf", "fps=25,format=yuv420p", "-c:v", "libx264", "-crf", "18", "-preset", "medium",
              "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2", part])
        x = crop_x(e["crop"])
        _run([ff, "-y", "-loglevel", "error", "-i", part, "-vf", "crop=%d:%d:%d:0,scale=%d:%d:flags=lanczos,format=yuv420p" % (CROP_W, CROP_H, x, FRAME_W, FRAME_H),
              "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-c:a", "copy", vpart])
        dur = _dur(ff, vpart)
        heard = [(w, round(t0 - start, 2), round(t1 - start, 2)) for w, t0, t1 in words[first:last + 1]]
        cards = chunk_caption(e["passage"])
        times = card_times(heard, cards, e["passage"])
        items.append({"name": e["name"], "party": e["party"], "duration": dur, "cards": [(c, t[0], t[1]) for c, t in zip(cards, times)],
                      "part": part, "vpart": vpart})
        report.append((e, s, start, end, dur, x, ratio, " ".join(w for w, _a, _b in heard)))
        log("  %-28s %5.1fs  crop x=%d  match %.2f" % (e["name"], dur, x, ratio))
    # masters
    for key, out in (("part", "social-cut-1080.mp4"), ("vpart", "social-cut-vertical-1080.mp4")):
        lst = os.path.join(hd, "concat-%s.txt" % key)
        open(lst, "w").write("".join("file '%s'\n" % os.path.abspath(it[key]) for it in items))
        _run([ff, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", "-movflags", "+faststart", os.path.join(final, out)])
    ass = ass_track(items)
    open(os.path.join(pack_dir, "social-cut.ass"), "w", encoding="utf-8").write(ass)
    fontsdir = os.path.join(hd, "fonts")
    os.makedirs(fontsdir, exist_ok=True)
    for f in ("/System/Library/Fonts/HelveticaNeue.ttc", "/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf"):
        if os.path.exists(f) and not os.path.exists(os.path.join(fontsdir, os.path.basename(f))):
            shutil.copy(f, fontsdir)
    logo = LOGO if os.path.exists(LOGO) else None
    filt = ("[1:v]scale=%d:-1[lg];[0:v][lg]overlay=60:70[v1];[v1]" % LOGO_W if logo else "[0:v]") + \
           "ass=%s:fontsdir=%s[v]" % (os.path.join(pack_dir, "social-cut.ass"), fontsdir)
    cmd = [ff, "-y", "-loglevel", "error", "-i", os.path.join(final, "social-cut-vertical-1080.mp4")] + (["-i", logo] if logo else []) + \
          ["-filter_complex", filt, "-map", "[v]", "-map", "0:a", "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-c:a", "copy",
           "-movflags", "+faststart", os.path.join(final, "social-cut-vertical-1080-captioned.mp4")]
    _run(cmd)
    # contact sheet: one frame per speaker, mid-excerpt, from the captioned render
    frames, off = [], 0.0
    for i, it in enumerate(items):
        fr = os.path.join(hd, "frame-%d.jpg" % i)
        _run([ff, "-y", "-loglevel", "error", "-ss", "%.2f" % (off + it["duration"] / 2.0), "-i", os.path.join(final, "social-cut-vertical-1080-captioned.mp4"),
              "-frames:v", "1", "-vf", "scale=300:-1", fr])
        frames.append(fr)
        off += it["duration"]
    if len(frames) > 1:
        _run([ff, "-y", "-loglevel", "error"] + sum([["-i", f] for f in frames], []) +
             ["-filter_complex", "".join("[%d]" % i for i in range(len(frames))) + "hstack=inputs=%d" % len(frames), os.path.join(final, "social-cut-contact-sheet.jpg")])
    else:
        shutil.copy(frames[0], os.path.join(final, "social-cut-contact-sheet.jpg"))
    write_report(pack_dir, report, off)
    return items


def write_report(pack_dir, report, total):
    lines = ["# Social cut", "",
             "*Built by tools/social_cut.py from sequence.md. Captions are the words as spoken; correct the passage in sequence.md if what was heard differs, then re-run with `--render`.*", "",
             "Files: `clips/final/social-cut-vertical-1080-captioned.mp4` (post this), `clips/final/social-cut-vertical-1080.mp4` (clean vertical), `clips/final/social-cut-1080.mp4` (landscape master), `clips/final/social-cut-contact-sheet.jpg` (check the crops), `social-cut.ass` (caption track).", "",
             "Total %.1fs." % total, ""]
    off = 0.0
    for i, (e, s, start, end, dur, x, ratio, heard) in enumerate(report, 1):
        lines += ["## %d. %s — at %s in the cut, %.1fs, crop x=%d, match %.2f" % (i, e["name"], _ts(off)[2:], dur, x, ratio), "",
                  "> %s" % e["passage"], "", "Heard: *%s*" % heard, ""]
        off += dur
    open(os.path.join(pack_dir, "social-cut.md"), "w", encoding="utf-8").write("\n".join(lines))
