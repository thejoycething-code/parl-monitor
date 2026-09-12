"""Prove the footage clock before cutting anything (12 September 2026).

The stream's clock and Hansard's are two different instruments. On 11 September
the estimator that fills Hansard's sparse timestamps ran ten minutes past the next
one, and nineteen clips were cut from the wrong minutes before anyone measured
it. The measurement is cheap -- two 180p probes and two short transcriptions --
so every footage run does it first and writes the offsets into pack.json, and the
DM quotes them. Anchors: the debate's first contribution (the opener is called by
name and begins at a printed timestamp) and its last (the closing words, or the
Question put). An offset beyond TOLERANCE_S stops the run: the clocks are wrong
and cutting on them makes confident rubbish.
"""

import datetime
import json
import os

from src import socialcut as sc

TOLERANCE_S = 20.0
PROBE_S = 90.0
FRESH_HOURS = 12


def anchors(state, speeches):
    """[(label, sitting_seconds, first_25_words)] for the opener and the closer."""
    from src import speechcut
    out = []
    rows = [(speechcut._clock_seconds(state, c.get("at")), s["name"], c.get("text") or "")
            for s in speeches for c in (s.get("contributions") or []) if (c.get("words") or 0) >= 60]
    rows = [r for r in rows if r[0] is not None]
    if not rows:
        return out
    rows.sort(key=lambda r: r[0])
    first, last = rows[0], rows[-1]
    out.append(("opener %s at %s" % (first[1], _hms(first[0])), first[0], " ".join(first[2].split()[:25])))
    if last is not first:
        out.append(("closer %s at %s" % (last[1], _hms(last[0])), last[0], " ".join(last[2].split()[:25])))
    return out


def _hms(s):
    return "%d:%02d:%02d" % (int(s // 3600), int(s % 3600 // 60), int(s % 60))


def measure(pack_dir, ff, whisper_model="small.en", probe=None, log=print):
    """Probe each anchor and return [(label, expected_s, heard_s or None, offset_s or None)].

    `probe(manifest, start_s, end_s, out_path) -> [(word, start, end)]` with times in
    sitting seconds; the default fetches 180p by HLS segment and transcribes.
    """
    from src import alignclip, hlsfetch
    state = json.load(open(os.path.join(pack_dir, "pack.json")))
    speeches = sc.parse_speeches(open(os.path.join(pack_dir, "speeches.md"), encoding="utf-8").read())
    hd = os.path.join(pack_dir, "clips", "align")
    os.makedirs(hd, exist_ok=True)

    def default_probe(manifest, a, b, out):
        file_start, _raw = hlsfetch.fetch_window(manifest, a, b, out, ff, height=180, margin=0, log=None)
        words = alignclip.transcribe(out, out + ".wav", ff, model_size=whisper_model, words_json=out + ".words.json", log=lambda *_a: None)
        return [(w, s + file_start, e + file_start) for w, s, e in words]
    probe = probe or default_probe
    results = []
    for label, at, head in anchors(state, speeches):
        out = os.path.join(hd, "probe-%d.mp4" % int(at))
        try:
            words = probe(state.get("manifest"), max(0.0, at - 30.0), at + PROBE_S, out)
            span = sc.word_span(words, head, min_ratio=0.5) if words else None
        except Exception as exc:                                    # noqa: BLE001
            log("  [align] %s: probe failed: %s" % (label, exc)); words, span = [], None
        if span:
            heard = words[span[0]][1]
            results.append((label, at, heard, heard - at))
            log("  [align] %s: heard %+.1fs from Hansard's clock (match %.2f)" % (label, heard - at, span[2]))
        else:
            results.append((label, at, None, None))
            log("  [align] %s: first words not heard within the probe" % label)
    return results


def check(pack_dir, ff, whisper_model="small.en", probe=None, log=print, tolerance=TOLERANCE_S, force=False):
    """Measure unless a fresh measurement is on record; raise SystemExit when the
    clocks disagree by more than `tolerance`. Returns the record."""
    path = os.path.join(pack_dir, "pack.json")
    state = json.load(open(path))
    rec = state.get("alignment")
    if rec and not force:
        try:
            age = datetime.datetime.now() - datetime.datetime.fromisoformat(rec["measured_at"])
            if age < datetime.timedelta(hours=FRESH_HOURS) and rec.get("ok"):
                log("  [align] on record: %s" % rec["summary"]); return rec
        except (KeyError, ValueError):
            pass
    results = measure(pack_dir, ff, whisper_model, probe=probe, log=log)
    offsets = [r[3] for r in results if r[3] is not None]
    ok = bool(offsets) and all(abs(o) <= tolerance for o in offsets)
    summary = "; ".join("%s: %s" % (r[0], ("%+.1fs" % r[3]) if r[3] is not None else "not heard") for r in results) or "no anchors"
    rec = {"measured_at": datetime.datetime.now().isoformat(timespec="seconds"), "ok": ok, "tolerance_s": tolerance,
           "anchors": [{"label": r[0], "expected_s": r[1], "heard_s": r[2], "offset_s": r[3]} for r in results], "summary": summary}
    state["alignment"] = rec
    json.dump(state, open(path, "w"), indent=1)
    if not ok:
        raise SystemExit("footage clock check FAILED (%s). The stream and Hansard disagree by more than %.0fs; "
                         "nothing was cut. Rebuild the pack (tools/debate_pack.py) or check event_start in pack.json." % (summary, tolerance))
    return rec
