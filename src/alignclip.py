"""Cut a passage from footage by its WORDS, not by estimated position.

Christopher, 2026-09-07: "For Jonathan Hinder and others there's extra
text." A passage's place inside a speech had been estimated from word
counts at spoken pace, and Hansard's clocks sit a minute or two off the
recording, so every cut needed room and a trim. This transcribes the
recording once with word-level timestamps (faster-whisper, small English
model, on the CPU), aligns the passage's words to the transcript, and cuts
at the first and last word. Whisper mishears a word here and there, so the
match is a fuzzy sequence alignment and the cut is tested by its score.
"""

from __future__ import annotations

import difflib
import json
import os
import re
import subprocess

_TOKEN = re.compile(r"[a-z0-9']+")
CHROME = re.compile(r"Toggle showing location of\s*Column\s*\d+(?:WH)?", re.I)   # Hansard web furniture pasted with a quote


def tokens(text):
    return _TOKEN.findall(CHROME.sub(" ", text or "").lower().replace("’", "'"))


def transcribe(media_path, wav_path, ffmpeg, model_size="small.en", words_json=None, log=print):
    """-> [(word, start_s, end_s)] for the whole recording; cached as JSON."""
    if words_json and os.path.exists(words_json):
        return [tuple(w) for w in json.load(open(words_json))]
    subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", media_path, "-vn", "-ac", "1", "-ar", "16000", wav_path], check=True)
    from faster_whisper import WhisperModel
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments, _info = model.transcribe(wav_path, word_timestamps=True, language="en", beam_size=3)
    words = []
    for s in segments:
        for w in s.words or []:
            words.append((w.word.strip(), float(w.start), float(w.end)))
    if words_json:
        json.dump(words, open(words_json, "w"))
    log("transcribed {0} words".format(len(words)))
    return words


def align(words, passage, min_ratio=0.6):
    """Locate `passage` in the transcript. -> (start_s, end_s, ratio) or None.

    Slides a window of the passage's length (with slack) over the
    transcript tokens and keeps the best difflib ratio; anchors the cut on
    the first and last matched words inside that window."""
    want = tokens(passage)
    if not want:
        return None
    have = [tokens(w)[0] if tokens(w) else "" for w, _a, _b in words]
    n = len(want)
    best = (0.0, None)
    for lo in range(0, max(1, len(have) - n // 2)):
        for extra in (0, n // 8 + 1):
            hi = min(len(have), lo + n + extra)
            ratio = difflib.SequenceMatcher(None, want, have[lo:hi], autojunk=False).ratio()
            if ratio > best[0]:
                best = (ratio, (lo, hi))
    ratio, span = best
    if not span or ratio < min_ratio:
        return None
    lo, hi = span
    sm = difflib.SequenceMatcher(None, want, have[lo:hi], autojunk=False)
    blocks = [b for b in sm.get_matching_blocks() if b.size]
    if not blocks:
        return None
    # Anchor on the matched words, then reach back over a misheard head and
    # forward over a misheard tail by the number of passage words the match
    # did not cover: "It should concern us all that" heard as something else
    # lost the opening; "worth keeping" heard as "safe gorges" lost the close
    # (2026-09-07). Bounded by the transcript.
    first = lo + blocks[0].b - blocks[0].a
    last = lo + blocks[-1].b + blocks[-1].size - 1 + (len(want) - (blocks[-1].a + blocks[-1].size))
    first = max(0, min(first, len(words) - 1))
    last = max(first, min(last, len(words) - 1))
    return words[first][1], words[last][2], ratio


def cut(media_path, start_s, end_s, out_path, ffmpeg, pad_before=0.35, pad_after=0.5):
    ss = max(0.0, start_s - pad_before)
    subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-ss", "%.2f" % ss, "-i", media_path, "-t", "%.2f" % (end_s + pad_after - ss),
                    "-vf", "scale=1024:576,fps=25", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-ar", "48000", "-ac", "2",
                    out_path], check=True)
    return out_path


def parse_cuts(text):
    """'## Name' headings, each followed by the passage to cut."""
    out = []
    for block in re.split(r"^## ", text, flags=re.M)[1:]:
        name, _, body = block.partition("\n")
        passage = " ".join(body.split())
        if passage:
            out.append((name.strip(), passage))
    return out
