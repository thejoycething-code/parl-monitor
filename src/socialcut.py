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
        goal = target * (len(lines) + 1)
        # break before this word if that lands the line nearer its target than taking it would
        if cur and len(lines) < n_lines - 1 and abs(used - goal) <= abs(used + len(w) + 1 - goal):
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


_CLAUSE_END = re.compile(r"(?<=[,;:])\s+")


def _fits(words, max_chars, max_lines):
    return len(_wrap(words, max_chars)) <= max_lines


def _card(words, max_chars, max_lines):
    """Balance a group of words that is known to fit; keep the greedy wrap if balancing overruns."""
    n = len(_wrap(words, max_chars))
    lines = _balanced(words, n, max_chars)
    return lines if len(lines) <= max_lines else _wrap(words, max_chars)


def chunk_caption(text, max_chars=CAPTION_MAX_CHARS, max_lines=CAPTION_MAX_LINES):
    """Cards of at most `max_lines` lines of at most `max_chars` characters.

    A card never crosses a sentence boundary. A sentence that needs more than one
    card is split at its clauses (commas, semicolons, colons) so a card ends where a
    breath would; a clause that is itself too long is split into pairs of lines."""
    cards = []
    for sentence in _SENTENCE_END.split((text or "").strip()):
        if not sentence.split():
            continue
        clauses = [c.split() for c in _CLAUSE_END.split(sentence) if c.split()]
        cur = []
        for clause in clauses:
            if cur and _fits(cur + clause, max_chars, max_lines):
                cur = cur + clause
                continue
            if cur:
                cards.append(_card(cur, max_chars, max_lines))
                cur = []
            if _fits(clause, max_chars, max_lines):
                cur = clause
                continue
            # a clause too long for one card: spread its words evenly over as few cards as fit,
            # so no card is left holding two orphaned words
            groups = _even_groups(clause, max_chars, max_lines)
            for g in groups[:-1]:
                cards.append(_card(g, max_chars, max_lines))
            cur = groups[-1]             # the clause's tail may still join the next clause
        if cur:
            cards.append(_card(cur, max_chars, max_lines))
    return cards


def _even_groups(words, max_chars, max_lines):
    """Split words into the fewest groups that each fit a card; among those, the split
    whose longest group is shortest (so the cards are of a size)."""
    n = len(words)
    best = [None] * (n + 1)          # best[j] = (cards, longest_card_chars, cut) for words[:j]
    best[0] = (0, 0, None)
    for j in range(1, n + 1):
        for i in range(j - 1, -1, -1):
            group = words[i:j]
            if not _fits(group, max_chars, max_lines):
                if len(group) > 1:
                    break
                continue
            if best[i] is None:
                continue
            cand = (best[i][0] + 1, max(best[i][1], len(" ".join(group))), i)
            if best[j] is None or cand[:2] < best[j][:2]:
                best[j] = cand
        if best[j] is None:          # a single word longer than a line: let it stand alone
            best[j] = (best[j - 1][0] + 1, max(best[j - 1][1], len(words[j - 1])), j - 1)
    groups, j = [], n
    while j > 0:
        i = best[j][2]
        groups.append(words[i:j])
        j = i
    return groups[::-1]


def card_times(words, cards, passage):
    """When each caption card should appear, from the transcript's word timings.

    THE EXACT CASE FIRST. When the transcript's word count equals the cards' token
    count -- true for all six speakers of the surrogacy cut, because the passage is
    already the words as heard -- each card simply owns the next N words. No
    alignment, no interpolation, nothing to be approximately wrong about.

    That is worth stating plainly because two cleverer attempts were worse. Spreading
    cards across the window by token FRACTION assumes an even speaking pace and put
    two cards 0.77s and 0.99s off. Aligning each card independently then mistimed
    short fragments: on Steve Yemm it put one card 0.61s early and the next 0.61s
    late, a boundary in the wrong place rather than a drift.

    The alignment path remains for the case the exact one cannot serve: a transcript
    that heard a different number of words from the passage. There, cards that align
    confidently anchor the rest, and a card nobody can place is interpolated between
    its neighbours rather than dragging them off their words.
    """
    counts = [len(alignclip.tokens(" ".join(c))) for c in cards]
    if words and sum(counts) == len(words):
        out, i = [], 0
        for k in counts:
            out.append((words[i][1], words[i + k - 1][2]))
            i += k
        return out
    return _card_times_by_alignment(words, cards, passage, counts)


def _card_times_by_alignment(words, cards, passage, counts):
    """Fallback for a transcript whose word count differs from the passage."""
    n = len(words)
    if not cards:
        return []
    if not n:
        return [(0.0, 0.0) for _c in cards]
    anchors = []
    for card in cards:
        hit = alignclip.align(words, " ".join(card), min_ratio=0.5)
        anchors.append((hit[0], hit[1]) if hit else None)
    if not any(anchors):
        total = len(alignclip.tokens(passage)) or 1
        out, pos = [], 0
        for k in counts:
            i0 = min(n - 1, int(round(pos / float(total) * n)))
            i1 = min(n - 1, max(i0, int(round((pos + k) / float(total) * n)) - 1))
            out.append((words[i0][1], words[i1][2]))
            pos += k
        return out
    first_t, last_t = words[0][1], words[-1][2]
    out = list(anchors)
    for i, got in enumerate(anchors):
        if got is not None:
            continue
        prev = next((anchors[j][1] for j in range(i - 1, -1, -1) if anchors[j]), first_t)
        nxt = next((anchors[j][0] for j in range(i + 1, len(anchors)) if anchors[j]), last_t)
        gap = [j for j in range(i, len(anchors)) if anchors[j] is None and
               all(anchors[k] is None for k in range(i, j + 1))]
        share = (nxt - prev) / float(len(gap) + 1) if nxt > prev else 0.0
        k = gap.index(i)
        out[i] = (prev + share * k, prev + share * (k + 1))
    for i in range(len(out) - 2, -1, -1):
        if out[i][0] > out[i + 1][0]:
            out[i] = (out[i + 1][0], min(out[i][1], out[i + 1][0]))
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
            if manifest is None:
                # pack.json already holds it; yt-dlp is only needed for a pack that
                # never resolved one, and never for the fetching itself.
                manifest = state.get("manifest")
                if not manifest:
                    manifest, _es = dp.manifest_for(state["event"], yt)
            found = locate_passage(pack_dir, state, e, ff, manifest, whole=whole,
                                   whisper_model=whisper_model, log=log)
            if not found:
                raise SystemExit("could not place the passage for %s. Check it against "
                                 "what was said, or transcribe the whole debate "
                                 "(tools/social_cut.py --pack F --transcribe)." % e["name"])
            a, b = found
            # Only the passage is fetched at 1080p, by HLS segment: about 7 MB and two
            # seconds, against a 515 MB download of the sitting and an hour of
            # transcription. That is what takes the Mac out of the loop.
            from src import hlsfetch
            for attempt, margin in ((1, 8.0), (2, 45.0)):
                file_start, raw = hlsfetch.fetch_window(manifest, a, b, window, ff,
                                                        height=1080, margin=margin, log=None)
                log("  %s: fetched %.1f MB from %.0fs" % (e["name"], raw / 1e6, file_start))
                ws = alignclip.transcribe(window, os.path.join(hd, s + ".wav"), ff,
                                          model_size=whisper_model, words_json=words_json,
                                          log=lambda *_a: None)
                if alignclip.align(ws, e["passage"], min_ratio=0.55):
                    break
                if attempt == 1:
                    log("  %s: passage not in the first window, widening" % e["name"])
                    os.remove(window)
                    if os.path.exists(words_json):
                        os.remove(words_json)
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
        # Caption times come from the PART's OWN transcript, not from the window's
        # rebased by the cut start. Two transcriptions of the same audio place words
        # differently -- measured 0.51s and 0.71s apart on Steve Yemm's cards
        # (2026-09-10) -- and the part is what a viewer watches, so the part is the
        # authority. This is why three earlier attempts at card timing all failed:
        # each was timing against the wrong audio. One short transcription per part.
        heard = alignclip.transcribe(part, os.path.join(hd, s + "-part.wav"), ff,
                                     model_size=whisper_model,
                                     words_json=os.path.join(hd, s + "-part.words.json"),
                                     log=lambda *_a: None)
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


# Reel length, in seconds of speech (Christopher, 2026-09-09): "above 30 seconds
# ideally and below 60. With very good speeches, going above 60 is fine."
# The edition's text quotes are sized in CHARACTERS (quotes.FLOOR/TARGET/CAP, about
# 28s of speech) because 380 characters is what a reader will take; a reel is watched,
# not read, so it is sized in seconds instead and runs two to three times longer.
REEL_FLOOR_S = 30.0
REEL_TARGET_S = 45.0
REEL_CAP_S = 60.0
REEL_HARD_CAP_S = 95.0     # the ceiling even for a very good speech
REEL_STRONG_HITS = 3       # on-topic sentences that earn the licence to run past the cap


def spoken_seconds(text):
    """Estimated spoken length at the Commons' pace (debatepack.WORDS_PER_SECOND)."""
    from src import debatepack
    return len((text or "").split()) / float(debatepack.WORDS_PER_SECOND)


def reel_passage(text, patterns, floor_s=REEL_FLOOR_S, target_s=REEL_TARGET_S,
                 cap_s=REEL_CAP_S, hard_cap_s=REEL_HARD_CAP_S):
    """The best whole-sentence passage of one speech to cut as a reel, or None.

    Same seed-and-grow shape as quotes.shareable, and the same `usable` guard
    against passages that misrepresent the member (a concession, someone else's
    point, an opening question). The difference is the measure: sentences are
    added until the window reaches `target_s` seconds of speech, it must clear
    `floor_s`, and it stops at `cap_s` -- unless the window is carrying
    REEL_STRONG_HITS or more on-topic sentences, which is what "a very good
    speech" looks like from here, and then it may run to `hard_cap_s`.
    """
    from src import quotes
    body = quotes.strip_openers(text or "")
    sents = quotes.sentences(body) if body else []
    if not sents:
        return None
    scored = [(i, quotes._matches(s, patterns)) for i, s in enumerate(sents)]
    hits = [i for i, n in scored if n and spoken_seconds(sents[i]) <= hard_cap_s]
    if not hits:
        return None
    for seed in sorted(hits, key=lambda i: (scored[i][1], -i), reverse=True):
        for back in (True, False):
            got = _grow_seconds(sents, scored, seed, floor_s, target_s, cap_s, hard_cap_s, back)
            if got and quotes.usable(got):
                return got
    return None


def _grow_seconds(sents, scored, seed, floor_s, target_s, cap_s, hard_cap_s, back=True):
    """Grow a whole-sentence window around `seed` toward `target_s`, or None."""
    from src import quotes
    start = end = seed
    if back and quotes._DEPENDENT.match(sents[seed]) and seed > 0:
        if spoken_seconds(" ".join(sents[seed - 1:end + 1])) <= hard_cap_s:
            start = seed - 1

    def span():
        return " ".join(sents[start:end + 1])

    def ceiling():
        # a window thick with on-topic sentences has earned the longer run
        strong = sum(1 for i in range(start, end + 1) if scored[i][1])
        return hard_cap_s if strong >= REEL_STRONG_HITS else cap_s

    while spoken_seconds(span()) < target_s:
        grew = False
        if end + 1 < len(sents) and spoken_seconds(" ".join(sents[start:end + 2])) <= ceiling():
            end += 1
            grew = True
        elif start > 0 and spoken_seconds(" ".join(sents[start - 1:end + 1])) <= ceiling():
            start -= 1
            grew = True
        if not grew:
            break
    out = span()
    return out if spoken_seconds(out) >= floor_s else None


PARTY = {"Con": "Conservative", "Lab": "Labour", "Lab/Co-op": "Labour", "LD": "Liberal Democrat", "DUP": "DUP", "SNP": "SNP",
         "Green": "Green", "Ind": "Independent", "PC": "Plaid Cymru", "Ref": "Reform UK", "UUP": "UUP", "SDLP": "SDLP", "Alliance": "Alliance", "TUV": "TUV"}
_QUOTE_HEAD = re.compile(r"^## (.+?)\s*\((.+?),\s*(.+?)\)\s*$")


def draft_sequence(quotes_md, title, date, limit=8):
    """A first sequence.md from quotes.md: the confirmed-onside speakers in speaking
    order, each with their first quote. A starting point to reorder and trim, never
    the finished thing; the campaigner chooses the order and the words."""
    entries, cur = [], None
    for raw in (quotes_md or "").splitlines():
        m = _QUOTE_HEAD.match(raw.strip())
        if m:
            cur = {"name": m.group(1).strip(), "party": PARTY.get(m.group(2).strip(), m.group(2).strip()), "seat": m.group(3).strip(), "quote": ""}
            entries.append(cur)
        elif cur is not None and raw.startswith(">") and not cur["quote"]:
            cur["quote"] = raw.lstrip("> ").strip()
    entries = [e for e in entries if e["quote"]][:limit]
    out = ["# Sequence: %s, %s" % (title, date), "",
           "DRAFT written by tools/social_cut.py --draft from quotes.md: speakers confirmed onside in checklist.md, in speaking order, first quote each.",
           "Reorder, cut to about six, trim each quote to one or two sentences (twenty seconds at most), and change the words to what was SPOKEN once the report shows them.",
           "Add `crop: left|centre|right|<x>` where the contact sheet shows a speaker off-centre. Delete these notes when done.", ""]
    for e in entries:
        name = e["name"] if e["name"].endswith(" MP") or e["name"].startswith(("Lord", "Baroness", "The")) else e["name"] + " MP"
        out += ["## %s" % name, "party: %s · %s" % (e["party"], e["seat"]), "> %s" % e["quote"], ""]
    if not entries:
        out += ["(quotes.md has no confirmed speakers yet: fill ONSIDE: yes/no in checklist.md, run tools/debate_pack.py --pack F --apply, then --draft again.)", ""]
    return "\n".join(out)


# A speaker heading is "## Name (Party, Seat)" -- EXCEPT a minister's, which
# debatepack writes as bare "## Dame Diana Johnson". Requiring the parenthesis
# made her section leak into the speaker above it, and her "Neutral" pass read
# then overwrote his confirmed "yes" (Shastri-Hurst, 2026-09-09), dropping a
# confirmed onside speaker from every reel without a word.
_SPEECH_HEAD = re.compile(r"^## (.+?)(?:\s*\((.+?),\s*(.+?)\))?\s*$")
# The "· **confirmed: yes**" suffix is written only once the checklist is applied. A
# blank checklist writes none, and a regex that required it read NO pass read for any
# speaker before confirmation -- so nothing could be drafted the evening of a debate.
_PASS_READ = re.compile(r"^\*\*Pass read:\*\*\s*(.+?)\s*(?:—|--)\s*(.*?)\s*(?:·\s*\*\*confirmed:\s*(\w+)\*\*)?\s*$", re.I)
_CONTRIB = re.compile(r"^\*(\d{2}:\d{2}:\d{2}),\s*([\d,]+) words(?:.*?\[Hansard\]\((\S+?)\))?")


def parse_speeches(text):
    """speeches.md -> [{name, party, seat, pass_read, confirmed, contributions}].

    Each contribution keeps its own text, because a reel must be cut from ONE
    contribution: joining a speech to a later intervention would produce a
    passage that reads well and cannot be cut, the two halves being minutes apart.
    """
    out, cur, con = [], None, None
    for raw in (text or "").splitlines():
        line = raw.rstrip()
        m = _SPEECH_HEAD.match(line)
        if m:
            cur = {"name": m.group(1).strip(), "party": (m.group(2) or "").strip(),
                   "seat": (m.group(3) or "").strip(),
                   "pass_read": "", "confirmed": "", "contributions": []}
            out.append(cur)
            con = None
            continue
        if cur is None:
            continue
        m = _PASS_READ.match(line)
        if m:
            if not cur["pass_read"]:      # the FIRST reading in the section is this speaker's
                cur["pass_read"], cur["confirmed"] = m.group(1).strip(), (m.group(3) or "").strip().lower()
            continue
        m = _CONTRIB.match(line)
        if m:
            con = {"at": m.group(1), "words": int(m.group(2).replace(",", "")),
                   "url": (m.group(3) or "").rstrip(")"), "text": ""}
            cur["contributions"].append(con)
            continue
        if con is not None and line.strip() and not line.startswith("*"):
            con["text"] = (con["text"] + " " + line.strip()).strip()
    return out


PROVISIONAL_LINE = ("PROVISIONAL: speakers taken from the stance pass, not the checklist. Confirm "
                    "ONSIDE in checklist.md and edit this file before the cut is used.")


def draft_reel_sequence(speeches_md, title, date, patterns, limit=8, onside_only=True):
    """A sequence.md whose passages are REEL length, cut from the full speeches.

    Unlike draft_sequence (which lifts quotes.md's short reading quotes), this
    runs reel_passage over each speaker's longest single contribution, so the
    proposed passage is already 30-60 seconds of speech. Speakers with no usable
    reel-length passage are listed at the foot rather than dropped in silence:
    a speech that cannot be cut is a fact the campaigner should see.
    """
    speakers = parse_speeches(speeches_md)
    picked, skipped = [], []
    for s in speakers:
        onside = s["confirmed"] == "yes" or (not onside_only and s["confirmed"] != "no") \
            or (s["confirmed"] not in ("yes", "no") and s["pass_read"].lower().startswith("with us"))
        if onside_only and s["confirmed"] == "no":
            skipped.append((s, "checklist says not onside"))
            continue
        if not onside:
            skipped.append((s, "not confirmed onside"))
            continue
        best = max(s["contributions"], key=lambda c: c["words"], default=None)
        passage = reel_passage(best["text"], patterns) if best else None
        if not passage:
            skipped.append((s, "no usable passage of 30s or more"))
            continue
        picked.append((s, passage))
    picked.sort(key=lambda p: spoken_seconds(p[1]), reverse=True)
    out = ["# Sequence: %s, %s" % (title, date), "",
           "DRAFT by tools/social_cut.py --draft: passages are %.0f-%.0f seconds of speech, taken from each"
           % (REEL_FLOOR_S, REEL_CAP_S),
           "speaker's longest contribution and ordered longest first. Reorder, trim to about six, and correct",
           "the words to what was SPOKEN once social-cut.md reports what the transcriber heard.", ""]
    if any(s["confirmed"] != "yes" for s, _p in picked[:limit]):
        # the pass read stood in for a blank checklist: say so where the campaigner will read it
        out += [PROVISIONAL_LINE, ""]
    for s, passage in picked[:limit]:
        name = s["name"] if s["name"].endswith(" MP") else s["name"] + " MP"
        out += ["## %s" % name,
                "party: %s · %s" % (PARTY.get(s["party"], s["party"]), s["seat"]),
                "> %s" % passage, ""]
    if skipped:
        out += ["<!-- not proposed:"] + \
               ["     %-34s %s" % (s["name"], why) for s, why in skipped] + ["-->", ""]
    if not picked:
        out += ["(No speaker has a usable passage of %.0f seconds or more. Confirm ONSIDE lines in checklist.md,"
                % REEL_FLOOR_S, "run tools/debate_pack.py --pack F --apply, then --draft again.)", ""]
    return "\n".join(out)


def speaker_spans(state, name):
    """The speaker's Hansard spans in sitting seconds, longest first.

    ALL of them, not just the longest: Jonathan Hinder spoke twice on 7 Sept and the
    passage wanted was in his second, shorter contribution, so a longest-span-only
    search reported "not heard inside their own span" for words he plainly said
    (found 2026-09-10). The union of first-to-last is not used either -- a member who
    intervenes early and speaks late would span an hour and a half.
    """
    want = re.sub(r"\s+MP$", "", (name or "")).strip().lower()
    try:
        event_start = datetime.datetime.fromisoformat(state["event_start"])
    except (KeyError, ValueError):
        return []
    out = []
    for sp in state.get("speakers") or []:
        if (sp.get("name") or "").strip().lower() != want:
            continue
        for pair in sp.get("spans") or []:
            try:
                a = (datetime.datetime.fromisoformat(pair[0]) - event_start).total_seconds()
                b = (datetime.datetime.fromisoformat(pair[1]) - event_start).total_seconds()
            except (ValueError, IndexError, TypeError):
                continue
            out.append((max(0.0, a), b))
    return sorted(out, key=lambda p: p[1] - p[0], reverse=True)


def speaker_span(state, name):
    """The longest span, kept for callers that want one. Prefer speaker_spans."""
    got = speaker_spans(state, name)
    return got[0] if got else None


PROBE_HEIGHT = 180      # enough to transcribe; a speaker's whole span costs a few MB


def locate_passage(pack_dir, state, entry, ff, manifest, whole=None,
                   whisper_model="small.en", log=print):
    """(start, end) of the entry's passage in sitting seconds, or None.

    Two routes, cheapest first. If the whole debate has already been transcribed the
    answer is free. Otherwise Hansard's span for that speaker is fetched at 180p --
    a few MB -- transcribed, and the passage aligned inside it. Either way the 1080p
    fetch that follows is only the passage itself.
    """
    if whole:
        got = alignclip.align(whole, entry["passage"], min_ratio=0.5)
        if got:
            return got[0], got[1]
        log("  %s: not found in the whole-debate transcript, probing their span" % entry["name"])
    spans = speaker_spans(state, entry["name"])
    if not spans:
        log("  %s: no Hansard span for that name in pack.json" % entry["name"])
        return None
    from src import hlsfetch
    hd = os.path.join(pack_dir, "clips", "hd")
    for i, span in enumerate(spans):
        probe = os.path.join(hd, "%s-probe%d.mp4" % (slug(entry["name"]), i))
        words_json = probe.replace(".mp4", ".words.json")
        if not os.path.exists(words_json):
            lo, hi = max(0.0, span[0] - 5), span[1] + 5
            file_start, raw = hlsfetch.fetch_window(manifest, lo, hi, probe, ff,
                                                    height=PROBE_HEIGHT, margin=0, log=None)
            log("  %s: probed %.0f-%.0fs at %dp (%.1f MB)"
                % (entry["name"], lo, hi, PROBE_HEIGHT, raw / 1e6))
            json.dump({"file_start": file_start}, open(probe + ".meta.json", "w"))
        meta = json.load(open(probe + ".meta.json"))
        words = alignclip.transcribe(probe, probe.replace(".mp4", ".wav"), ff,
                                     model_size=whisper_model, words_json=words_json,
                                     log=lambda *_a: None)
        got = alignclip.align(words, entry["passage"], min_ratio=0.5)
        if got:
            return got[0] + meta["file_start"], got[1] + meta["file_start"]
    log("  %s: passage not heard in any of their %d span(s)" % (entry["name"], len(spans)))
    return None


def transcribe_whole(pack_dir, ff, whisper_model="small.en", log=print):
    """Word timings for the whole-debate recording (clips/00-whole-debate-*.mp4),
    cached as clips/whole-debate.words.json, so passages can be found in time."""
    clips = os.path.join(pack_dir, "clips")
    media = sorted(f for f in os.listdir(clips) if f.startswith("00-whole-debate") and f.endswith(".mp4")) if os.path.isdir(clips) else []
    if not media:
        raise SystemExit("no clips/00-whole-debate-*.mp4: run tools/debate_pack.py --pack F --download-debate --from HH:MM --to HH:MM first")
    return alignclip.transcribe(os.path.join(clips, media[-1]), os.path.join(clips, "whole-debate.wav"), ff, model_size=whisper_model,
                                words_json=os.path.join(clips, "whole-debate.words.json"), log=log)


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
