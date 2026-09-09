"""Fetch one window of a parliamentlive.tv sitting by pulling only its HLS segments.

Why this exists. The archive offers no file to download: `vod-idx.ism/.mp4` is 403 at
the CDN, and Unified Streaming's `?t=start-end` clipping answers 206 but is IGNORED --
the "clipped" playlist still lists all 1,684 segments of a 162-minute sitting (measured
2026-09-09). What the archive does offer is the segments themselves: sequential `.ts`
files on plain HTTPS, no authentication, individually addressable.

So a 40-second excerpt costs about 7 MB and two seconds instead of a 515 MB download of
the whole sitting, and only the window needs transcribing rather than the whole debate --
which is the difference between a job that needs a Mac with an hour of CPU and one that
runs on a CI runner.

Sync. Video and audio are separate renditions whose segment boundaries do not line up,
so the two streams are muxed on their own timestamps and the window is trimmed ONCE,
afterwards, on the muxed file. Trimming each stream by its own lead offset was the
obvious shortcut and it is exactly how audio drifts away from the picture.
"""

import gzip
import os
import re
import subprocess
import urllib.request

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
HEIGHT_TO_VIDEO = {180: 300000, 360: 850000, 576: 1300000, 1080: 3000000}
MARGIN = 8.0          # seconds fetched either side, so the aligner has room to work


def _get(url, timeout=45):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=timeout) as handle:
        data = handle.read()
    return gzip.decompress(data) if data[:2] == b"\x1f\x8b" else data


def base_of(manifest_url):
    """The directory the media playlists and segments sit in."""
    return manifest_url.rsplit("/", 1)[0]


def video_playlist(height=1080):
    rate = HEIGHT_TO_VIDEO.get(int(height))
    if rate is None:
        raise ValueError("no rendition for height %s; have %s" % (height, sorted(HEIGHT_TO_VIDEO)))
    return "vod-idx-video=%d.m3u8" % rate


def audio_playlist(manifest_text=None):
    """The English audio rendition, read from the master when given."""
    if manifest_text:
        m = re.search(r'TYPE=AUDIO[^\n]*URI="([^"]+)"', manifest_text)
        if m:
            return m.group(1)
    return "vod-idx-audio_eng=64000.m3u8"


def segments_for(playlist_text, start_s, end_s):
    """(segment URIs covering [start_s, end_s], start time of the first of them).

    The second value matters: the fetched file begins at a segment boundary, not at
    `start_s`, so the caller must trim by the difference.
    """
    durations = [float(x) for x in re.findall(r"#EXTINF:([\d.]+)", playlist_text)]
    uris = [l.strip() for l in playlist_text.splitlines() if l.strip() and not l.startswith("#")]
    picked, clock, first = [], 0.0, None
    for dur, uri in zip(durations, uris):
        if clock + dur > start_s and clock < end_s:
            if first is None:
                first = clock
            picked.append(uri)
        clock += dur
    return picked, (first or 0.0)


def playlist_duration(playlist_text):
    return sum(float(x) for x in re.findall(r"#EXTINF:([\d.]+)", playlist_text))


def fetch_window(manifest_url, start_s, end_s, out_path, ffmpeg, height=1080,
                 margin=MARGIN, log=None):
    """Write `out_path` covering AT LEAST [start_s - margin, end_s + margin] of the sitting.

    Returns (file_start, bytes fetched), where `file_start` is the sitting time at which
    the written file begins. So for a time `t` measured inside the file,
    sitting time = t + file_start, and there is no other arithmetic to get wrong.

    The file is NOT trimmed to the requested window: it begins and ends on segment
    boundaries. Two reasons. Trimming is what desynchronises audio from picture, and the
    caller aligns the passage by its words inside the window anyway, so a few spare
    seconds either side are useful rather than waste. An earlier version returned the
    offset of the margin-extended start instead, and the caller's own conversion came out
    eight seconds wrong -- the same class of error that once put Tracy Gilbert's words
    under Shivani Raja's name.
    """
    base = base_of(manifest_url)
    master = _get(manifest_url).decode("utf-8", "replace")
    lo, hi = max(0.0, start_s - margin), end_s + margin
    v_txt = _get(base + "/" + video_playlist(height)).decode("utf-8", "replace")
    a_txt = _get(base + "/" + audio_playlist(master)).decode("utf-8", "replace")
    v_segs, v_first = segments_for(v_txt, lo, hi)
    a_segs, _a_first = segments_for(a_txt, lo, hi)
    if not v_segs or not a_segs:
        raise RuntimeError("no segments cover %.1f-%.1fs of a %.0fs recording"
                           % (lo, hi, playlist_duration(v_txt)))
    if log:
        log("segments: %d video, %d audio from %.1fs" % (len(v_segs), len(a_segs), v_first))
    stem = os.path.splitext(out_path)[0]
    raw = 0
    parts = {}
    for kind, segs in (("v", v_segs), ("a", a_segs)):
        parts[kind] = "%s-%s.ts" % (stem, kind)
        with open(parts[kind], "wb") as fh:
            for uri in segs:
                blob = _get(base + "/" + uri)
                raw += len(blob)
                fh.write(blob)
    # Mux on the streams' own timestamps and trim ONCE, afterwards: trimming each
    # stream by its own lead offset is how the audio drifts off the picture.
    muxed = "%s-muxed.mp4" % stem
    subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-copyts", "-i", parts["v"], "-copyts", "-i", parts["a"],
                    "-map", "0:v:0", "-map", "1:a:0", "-c", "copy", "-muxpreload", "0", "-muxdelay", "0", muxed],
                   check=True, capture_output=True)
    subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", muxed, "-c", "copy",
                    "-movflags", "+faststart", out_path], check=True, capture_output=True)
    for tmp in list(parts.values()) + [muxed]:
        if os.path.exists(tmp):
            os.remove(tmp)
    return v_first, raw
