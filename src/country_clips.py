"""Speech clips for social, for the new countries (11 October 2026).

The UK's footage tools (tools/pick_speeches.py, tools/social_cut.py,
tools/speech_cut.py; docs/debate-pack-social.md) generalised to the countries
whose speeches we store (src/chamber_store.py, `<cc>_speeches`: NL, CH, AT, FR,
BE) and whose parliament publishes the video in a form we can fetch and line up
with those speeches. config/clip-sources.yaml says, per country, where the
video is, how its times are found, what the reuse terms say and whether the
tool may fetch (status open, manual, needs-agreement, not-built).

TWO STEPS, both manual, like the UK's:

1. PICK (no network unless --live, no AI call). Speeches on our ground from the
   store (or read live from the country's own collector into memory), ranked by
   rules: tier 1 before tier 2, more of the taxonomy's terms, a member before a
   minister, long enough to hold a 30 to 60 second passage. For each, a passage
   of whole sentences grown around the sentence with the most matched terms to
   about 45 seconds of speech, never ending on a question. Written to a pack
   (data/clips/<cc>-<date>-<slug>/): candidates.md (all of them), sequence.md
   (the top N, in the UK's sequence shape plus a `speech:` line), pack.json and
   a README with the source, the terms and the credit. ON OUR GROUND IS NOT A
   STANCE: nothing is confirmed for any new country yet, so every pack says
   "awaiting sign-off"; the person who edits sequence.md decides who is in it.

2. CUT. For each sequence entry: the country's locator turns the stored speech
   into one or more spans of official video (the speech's own MP4 for CH and
   AT; the sitting's MP4 between the compte rendu's own second marks for FR;
   the speaker's turns in the Chamber's event table for BE; a file the person
   downloaded from Debat Direct for NL). Only the span is fetched (ffmpeg reads
   byte ranges), transcribed with Whisper in the speech's language, and the
   passage found by its words (alignclip.align on accent-folded words); the cut
   is word-exact (socialcut.cut_bounds). Captions are the passage's words timed
   against the cut part's own transcript (socialcut.card_times), the UK's
   brand style (socialcut.ass_document): a 9:16 vertical, a 16:9 landscape,
   an .srt each, a vertical reel of all clips, and the source credit burned in
   small on every frame. clips.md reports the match and what was heard.

TRIM-ONLY (13 October 2026). A country whose agreement allows clips only if
the footage is not distorted or modified (France: the Assemblee nationale's
Cellule GILDA, 12 October 2026) carries `edits: trim-only` in
config/clip-sources.yaml. The tool then enforces, on every ffmpeg command and
subtitle file it writes for that country: one continuous span, cut at its
start and end only; no speed change, no reordering, no joining of clips (no
reel), no crop (the 9:16 version is the whole picture letterboxed), no logo,
no name plate; the only overlays are the credit and the passage's captions.
Video filters outside TRIM_ONLY_FILTERS and subtitle styles outside
TRIM_ONLY_STYLES are refused (ClipRefused), and the passage must be heard at
TRIM_ONLY_MIN_RATIO or better so the captions follow the speech. What the
tool cannot enforce (that a person editing the files afterwards keeps to
the terms, that the captions' wording matches the audio word for word) is
written into the pack README and clips.md.

NEVER POSTED. Clips are files for a person: nothing here uploads, posts or
messages. Fetched source footage (windows/) is deleted after the country's
retention_days (the Dutch licence's one month, applied everywhere); finished
clips stay.

Needs ffmpeg and faster-whisper (the Mini's bundle; docs/mac-mini.md) and the
multilingual Whisper model ("small", fetched once on first use).
"""

from __future__ import annotations

import datetime
import json
import os
import re
import shutil
import sqlite3
import subprocess
import time
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(ROOT, "config", "clip-sources.yaml")
STORE = os.path.join(ROOT, "data", "parl-monitor.db")
PACKS = os.path.join(ROOT, "data", "clips")
UA = "CitizenGO-ParlMonitor/1.0 (contact: cjoyce@citizengo.net)"
FEED = "clips"

STATUSES = ("open", "manual", "needs-agreement", "allowed", "not-built")
EDITS = ("full", "trim-only")
AGREEMENT_FIELDS = ("date", "grantor", "conditions")
# trim-only: the only ffmpeg filters allowed (resize, letterbox, pixel format,
# frame rate, sample aspect, burned subtitles) and the only subtitle styles.
TRIM_ONLY_FILTERS = ("scale", "pad", "format", "fps", "setsar", "ass")
TRIM_ONLY_STYLES = ("Caption", "Credit")
TRIM_ONLY_MIN_RATIO = 0.75
TRIM_ONLY_NOTE = ("Trim-only (the agreement's terms): each clip is one continuous span of the "
                  "official video, cut at its start and end; no speed change, reordering, joining, "
                  "crop, logo or name plate; the only overlays are the credit and the captions. "
                  "Do not edit these files further, and check the captions against the audio "
                  "before use: they are the compte rendu's words for the passage.")
WORDS_PER_SECOND = 2.5          # debatepack's spoken pace; close enough in NL, DE, FR
PASSAGE_FLOOR_S = 20.0
PASSAGE_TARGET_S = 45.0
PASSAGE_CAP_S = 60.0
MIN_WORDS = 90                  # below this a turn cannot hold a passage
MARGIN_S = 4.0                  # fetched either side of a located span
WHISPER_MODEL = "small"         # multilingual; the UK's small.en is English only
AWAITING = "awaiting sign-off"


class ClipRefused(Exception):
    """The country's terms or status do not let the tool fetch or cut."""


# --- the sources file ------------------------------------------------------------

def load_sources(path=CONFIG):
    import yaml
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    for cc, entry in data.items():
        if (entry or {}).get("status") not in STATUSES:
            raise ValueError("{0}: status must be one of {1}".format(cc, ", ".join(STATUSES)))
        if (entry.get("edits") or "full") not in EDITS:
            raise ValueError("{0}: edits must be one of {1}".format(cc, ", ".join(EDITS)))
        if trim_only(entry) and entry.get("logo"):
            raise ValueError("{0}: edits: trim-only allows no logo overlay (logo: false)".format(cc))
    return data


def trim_only(entry):
    return (entry or {}).get("edits") == "trim-only"


def agreement_recorded(entry):
    """True when `agreement:` records the written agreement: for status
    allowed, a mapping with a date, a grantor and the conditions."""
    got = (entry or {}).get("agreement")
    if entry.get("status") == "allowed":
        return isinstance(got, dict) and all(str(got.get(k) or "").strip() for k in AGREEMENT_FIELDS)
    return bool(got)


def agreement_text(entry):
    got = (entry or {}).get("agreement")
    if isinstance(got, dict):
        return "written agreement of {0}, {1}: {2}".format(
            got.get("date"), got.get("grantor"), " ".join(str(got.get("conditions") or "").split()))
    return str(got) if got else ""


def filter_names(graph):
    """The filter names in an ffmpeg filtergraph ('[0:v]scale=..,pad=..[v]')."""
    out = []
    for part in re.split(r"[;,]", graph or ""):
        part = re.sub(r"^\s*(?:\[[^\]]*\]\s*)*", "", part)
        part = re.sub(r"(?:\[[^\]]*\]\s*)*$", "", part).strip()
        if part:
            out.append(part.split("=", 1)[0].strip())
    return out


def check_trim_only_cmd(entry, cmd):
    """Raise ClipRefused when a trim-only country's ffmpeg command would do
    more than trim: a filter outside TRIM_ONLY_FILTERS, a second input (a
    logo, another clip), a concat, a loop or an offset."""
    if not trim_only(entry):
        return
    cmd = [str(c) for c in cmd]
    for flag in ("-vf", "-af", "-filter_complex", "-filter:v", "-filter:a", "-lavfi"):
        for i, c in enumerate(cmd[:-1]):
            if c == flag:
                bad = [n for n in filter_names(cmd[i + 1]) if n not in TRIM_ONLY_FILTERS]
                if bad:
                    raise ClipRefused("trim-only: filter(s) {0} would modify the footage; refused"
                                      .format(", ".join(bad)))
    if cmd.count("-i") > 1:
        raise ClipRefused("trim-only: a second input (logo or another clip) is not allowed")
    for i, c in enumerate(cmd[:-1]):
        if c == "-f" and cmd[i + 1] == "concat":
            raise ClipRefused("trim-only: joining clips (a reel) is not allowed")
    for c in ("-stream_loop", "-itsoffset", "-itsscale"):
        if c in cmd:
            raise ClipRefused("trim-only: {0} would modify the footage; refused".format(c))


def check_trim_only_ass(entry, ass):
    """Raise ClipRefused when a trim-only clip's subtitles carry anything but
    the captions and the credit (exactly as recorded)."""
    if not trim_only(entry):
        return
    styles = re.findall(r"^Dialogue:\s*\d+,[^,]*,[^,]*,([^,]*),", ass or "", flags=re.M)
    bad = sorted({x for x in styles if x not in TRIM_ONLY_STYLES})
    if bad:
        raise ClipRefused("trim-only: overlay style(s) {0} are not allowed".format(", ".join(bad)))
    credit = entry.get("credit") or ""
    if not credit or not re.search(r"^Dialogue:[^\n]*,Credit,,0,0,0,," + re.escape(credit) + "$",
                                   ass or "", flags=re.M):
        raise ClipRefused("trim-only: the required credit ({0}) is missing".format(credit))


def strip_plate(ass):
    """The subtitles without the name plate (its Shape, Name and Party lines)."""
    return "".join(ln for ln in (ass or "").splitlines(True)
                   if not re.match(r"Dialogue:\s*\d+,[^,]*,[^,]*,(Shape|Name|Party),", ln))


def vertical_filter(entry, crop_spec):
    """The 9:16 version: a crop of the speaker, or for trim-only the whole
    picture scaled and letterboxed (nothing cut from the frame)."""
    from src import socialcut as sc
    if trim_only(entry):
        return ("scale=%d:-2:flags=lanczos,pad=%d:%d:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p"
                % (sc.FRAME_W, sc.FRAME_W, sc.FRAME_H))
    x = sc.crop_x(crop_spec)
    return "crop=%d:%d:%d:0,scale=%d:%d:flags=lanczos,format=yuv420p" % (
        sc.CROP_W, sc.CROP_H, x, sc.FRAME_W, sc.FRAME_H)


def gate(sources, cc, video=None):
    """None when the tool may fetch and cut for `cc`, else raise ClipRefused
    with the reason. `video` is a local file a person downloaded (manual)."""
    entry = sources.get(cc)
    if not entry:
        raise ClipRefused("{0}: not in config/clip-sources.yaml".format(cc))
    status = entry["status"]
    if status == "not-built":
        raise ClipRefused("{0}: no clip tool: {1}".format(cc, " ".join((entry.get("terms") or "").split())))
    if status in ("needs-agreement", "allowed") and not agreement_recorded(entry):
        raise ClipRefused("{0}: the reuse terms ask for prior written agreement for video and none "
                          "is recorded (config/clip-sources.yaml, {0}.agreement{1}). See {2}"
                          .format(cc, ": date, grantor and conditions" if status == "allowed" else "",
                                  entry.get("terms_url", "")))
    if status == "manual" and not video:
        raise ClipRefused("{0}: the tool cannot fetch this source; download the speech on {1} "
                          "and pass it with --video FILE".format(cc, entry.get("source")))
    return None


# --- words ------------------------------------------------------------------------

_FOLD = {"ß": "ss", "æ": "ae", "œ": "oe", "ø": "o", "ł": "l", "đ": "d", "’": "'", "‘": "'"}


def fold(text):
    """Lower case, accents off, ASCII: the form alignclip's tokeniser reads, so a
    French or German passage and Whisper's words compare word for word."""
    t = (text or "").lower()
    t = "".join(_FOLD.get(ch, ch) for ch in t)
    t = unicodedata.normalize("NFKD", t)
    return "".join(ch for ch in t if not unicodedata.combining(ch))


def fold_words(words):
    return [(fold(w), a, b) for w, a, b in words]


_SENT = re.compile(r"(?<=[.!?])\s+(?=[A-ZÀ-ÖØ-Þ0-9\"'«(])")


def sentences(text):
    flat = " ".join((text or "").split())
    return [s for s in _SENT.split(flat) if s.strip()]


def spoken_seconds(text):
    return len((text or "").split()) / WORDS_PER_SECOND


def _hits(sentence, terms):
    f = fold(sentence)
    return sum(1 for t in terms if t and fold(t) in f)


def choose_passage(text, terms, floor_s=PASSAGE_FLOOR_S, target_s=PASSAGE_TARGET_S, cap_s=PASSAGE_CAP_S):
    """The passage to cut: whole sentences grown around the sentence carrying the
    most of the speech's matched terms, toward `target_s` seconds of speech and
    never past `cap_s`; it must reach `floor_s` and must not end on a question
    (a question is rarely the speaker's position). None when no window fits."""
    sents = sentences(text)
    if not sents:
        return None
    scored = [_hits(s, terms) for s in sents]
    seeds = sorted(range(len(sents)), key=lambda i: (-scored[i], i))
    for seed in seeds:
        if spoken_seconds(sents[seed]) > cap_s:
            continue
        lo = hi = seed
        while spoken_seconds(" ".join(sents[lo:hi + 1])) < target_s:
            if hi + 1 < len(sents) and spoken_seconds(" ".join(sents[lo:hi + 2])) <= cap_s:
                hi += 1
            elif lo > 0 and spoken_seconds(" ".join(sents[lo - 1:hi + 1])) <= cap_s:
                lo -= 1
            else:
                break
        while hi > lo and sents[hi].rstrip().endswith("?"):
            hi -= 1
        out = " ".join(sents[lo:hi + 1])
        if spoken_seconds(out) >= floor_s and not out.rstrip().endswith("?"):
            return out
        if not scored[seed]:
            break
    return None


# --- pick ---------------------------------------------------------------------------

ROLE_RANK = {"member": 0}


def _loads(v):
    if isinstance(v, (list, tuple)):
        return list(v)
    try:
        return json.loads(v) if v else []
    except ValueError:
        return []


def store_rows(conn, cc, date=None, since=None, until=None):
    """Speeches on our ground from `<cc>_speeches` in a window (or on one day)."""
    sql = ("SELECT speech_id, doc_id, date, chamber, debate_id, debate, speaker, party, role, "
           "person_id, excerpt, text, url, areas, matched_terms, tier FROM {0}_speeches WHERE 1=1".format(cc))
    args = []
    if date:
        sql += " AND date = ?"
        args.append(date)
    if since:
        sql += " AND date >= ?"
        args.append(since)
    if until:
        sql += " AND date <= ?"
        args.append(until)
    conn.row_factory = sqlite3.Row
    return [dict(r) for r in conn.execute(sql + " ORDER BY date, speech_id", args)]


def live_rows(cc, date, client, log=print, budget=600.0):
    """The day's speeches on our ground read by the country's own collector into
    memory (src/country_live's Capture), so a pack can be picked before the
    weekly has stored them. Nothing is written to the store."""
    from src import chamber_store as cs, country_live as cl, drain
    conn = cl.scratch_conn(cc)
    mod = cl.collector(cc)
    if hasattr(mod, "configure"):
        mod.configure(client)
    since = (datetime.date.fromisoformat(date) - datetime.timedelta(days=1)).isoformat()
    run = cl.Capture(cc, conn, client, date, since, drain.Budget(budget), cs.load_taxonomies(cc),
                     dry_run=True, log=log)
    mod.speeches(run)
    conn.close()
    out = []
    for r in run.got:
        if r.get("date") != date:
            continue
        r = dict(r)
        r["matched_terms"] = r.pop("terms", [])
        out.append(r)
    return out


def select(rows, find=None, debate_id=None):
    if debate_id:
        rows = [r for r in rows if r.get("debate_id") == debate_id]
    if find:
        want = fold(find).split()
        rows = [r for r in rows if all(w in fold(r.get("debate") or "") for w in want)]
    return rows


def candidates(rows, min_words=MIN_WORDS):
    """Rank speeches for a clip and choose each one's passage. Chair and
    interjections never appear (the collectors do not store the chair)."""
    out = []
    for r in rows:
        role = (r.get("role") or "member").lower()
        if role in ("interjection", "chair", "president"):
            continue
        text = r.get("text") or ""
        if len(text.split()) < min_words:
            continue
        terms = _loads(r.get("matched_terms"))
        passage = choose_passage(text, terms)
        out.append(dict(r, terms=terms, passage=passage, words=len(text.split()),
                        role_rank=ROLE_RANK.get(role, 1)))
    out.sort(key=lambda c: (c["passage"] is None, c.get("tier") or 9, c["role_rank"],
                            -len(set(map(fold, c["terms"]))), -min(c["words"], 900), c["speech_id"]))
    return out


def slugify(text, n=48):
    return re.sub(r"[^a-z0-9]+", "-", fold(text))[:n].strip("-") or "debate"


def name_slug(name):
    return re.sub(r"[^a-z0-9]+", "-", fold(name)).strip("-")[:40] or "speaker"


def sequence_md(cc, cands, top, title, date):
    lines = ["# Sequence: {0} {1}, {2}".format(cc.upper(), title, date), "",
             "PROVISIONAL: speeches on our ground by classification, not a stance ({0}). "
             "Keep only speakers the campaign is entitled to show, reorder, correct each "
             "passage to the words as spoken, then run `tools/country_clips.py cut`.".format(AWAITING), ""]
    n = 0
    for c in cands:
        if not c["passage"] or n >= top:
            continue
        n += 1
        lines += ["## {0}".format((c.get("speaker") or "?").split(",")[0].strip()),
                  "speech: {0}".format(c["speech_id"]),
                  "party: {0}".format(c.get("party") or ""),
                  "crop: centre"]
        lines += ["> " + chunk for chunk in _wrap(c["passage"])]
        lines.append("")
    return "\n".join(lines)


def _wrap(text, width=96):
    out, cur = [], ""
    for w in text.split():
        if cur and len(cur) + 1 + len(w) > width:
            out.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    return out + ([cur] if cur else [])


def candidates_md(cc, cands, title, date):
    lines = ["# Candidates: {0} {1}, {2}".format(cc.upper(), title, date), "",
             "Ranked by rule (tier, terms matched, member before minister, length); "
             "no stance is implied ({0}).".format(AWAITING), ""]
    for i, c in enumerate(cands, 1):
        lines.append("{0}. **{1}** ({2}), {3}, tier {4}, {5} words, `{6}`".format(
            i, c.get("speaker"), c.get("party") or "no party", c.get("role") or "member",
            c.get("tier"), c["words"], c["speech_id"]))
        lines.append("   debate: {0}".format(c.get("debate") or "?"))
        lines.append("   terms: {0}".format(", ".join(c["terms"][:8]) or "none recorded"))
        lines.append("   passage: {0}".format(
            ('"' + c["passage"] + '" (~%.0fs)' % spoken_seconds(c["passage"])) if c["passage"]
            else "none: no 20-60 s window of whole sentences"))
        lines.append("")
    return "\n".join(lines)


def readme(cc, entry, title, date):
    st = entry.get("status")
    lines = ["# Speech clips: {0}, {1} ({2})".format(cc.upper(), title, date), "",
             "Made by tools/country_clips.py. Files for a person: nothing here is posted, "
             "uploaded or sent anywhere by the tool.", "",
             "Status for {0}: **{1}**.".format(cc.upper(), st)]
    if st in ("needs-agreement", "allowed") and not agreement_recorded(entry):
        lines.append("The terms ask for written agreement before the video is reused; the cut "
                     "step refuses until it is recorded in config/clip-sources.yaml.")
    elif entry.get("agreement"):
        lines.append("Agreement: {0}.".format(agreement_text(entry).rstrip(".")))
    if trim_only(entry):
        lines += ["", TRIM_ONLY_NOTE]
    lines += ["", "Source: {0}".format(entry.get("source")), "",
              "Reuse terms ({0}): {1}".format(entry.get("terms_url", "no URL"),
                                              " ".join((entry.get("terms") or "").split())), "",
              "Credit burned into each clip: `{0}`".format(entry.get("credit", "")),
              "Credit for the post text: `{0}`".format(" ".join((entry.get("post_credit") or "").split())), "",
              "Stance: the speeches are on our ground by classification; no reading is "
              "confirmed ({0}). Whether a speaker belongs in a campaign clip is the "
              "campaigner's call.".format(AWAITING), "",
              "Fetched source footage in windows/ is deleted after {0} days.".format(
                  entry.get("retention_days", 30))]
    return "\n".join(lines) + "\n"


def write_pack(cc, rows, cands, entry, top=6, date=None, title=None, out_dir=PACKS):
    date = date or (rows[0]["date"] if rows else datetime.date.today().isoformat())
    title = title or (cands[0].get("debate") if cands else "debate") or "debate"
    pack = os.path.join(out_dir, "{0}-{1}-{2}".format(cc, date, slugify(title)))
    os.makedirs(pack, exist_ok=True)
    keep = ("speech_id", "doc_id", "date", "chamber", "debate_id", "debate", "speaker", "party",
            "role", "person_id", "url", "tier", "terms", "passage", "words")
    state = {"country": cc, "date": date, "title": title, "made": datetime.date.today().isoformat(),
             "speeches": [{k: c.get(k) for k in keep} for c in cands]}
    with open(os.path.join(pack, "pack.json"), "w", encoding="utf-8") as fh:
        json.dump(state, fh, ensure_ascii=False, indent=1)
    with open(os.path.join(pack, "candidates.md"), "w", encoding="utf-8") as fh:
        fh.write(candidates_md(cc, cands, title, date))
    seq = os.path.join(pack, "sequence.md")
    if os.path.exists(seq):
        shutil.copy(seq, os.path.join(pack, "sequence-previous.md"))
    with open(seq, "w", encoding="utf-8") as fh:
        fh.write(sequence_md(cc, cands, top, title, date))
    with open(os.path.join(pack, "README.md"), "w", encoding="utf-8") as fh:
        fh.write(readme(cc, entry, title, date))
    return pack


def parse_sequence(text):
    """sequence.md in the UK's shape (socialcut.parse_sequence: `## Name`,
    `party:`, `crop:`, the passage as `>` lines) plus `speech:`, the stored
    speech it comes from. Entries without a passage are dropped."""
    entries, cur = [], None
    for raw in (text or "").splitlines():
        line = raw.rstrip()
        if line.startswith("## "):
            cur = {"name": line[3:].strip(), "party": "", "crop": "centre", "passage": "", "speech": None}
            entries.append(cur)
        elif cur is None or not line.strip() or line.startswith("#"):
            continue
        elif line.startswith(">"):
            cur["passage"] = (cur["passage"] + " " + line.lstrip("> ").strip()).strip()
        else:
            m = re.match(r"^(party|crop|speech)\s*:\s*(.*)$", line.strip(), re.I)
            if m:
                cur[m.group(1).lower()] = m.group(2).strip()
    return [e for e in entries if e["passage"]]


# --- locators: a stored speech -> spans of official video --------------------------

class Span(dict):
    """{media, start, end, note}: start/end seconds into `media` (end None = to
    the end of the file)."""


def _client(cc):
    from src.http import HttpClient
    from src.robots_guard import guard
    # Belgium's robots.txt asks for a 5 s crawl delay; the rest get a polite 1 s.
    return guard(HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"), throttle=5.0 if cc == "be" else 1.0), FEED)


def locate_ch(row, client):
    m = re.match(r"^transcript:(\d+)$", row["speech_id"])
    if not m:
        raise LookupError("not a Bulletin transcript id: {0}".format(row["speech_id"]))
    return [Span(media="https://par-pcache.simplex.tv/content/simvid_1.mp4?externalid=" + m.group(1),
                 start=0.0, end=None, note="the Bulletin's own video of this speech")]


AT_BASE = "https://www.parlament.gv.at"
AT_MEDIA = "https://api.ausp.cloud.insysgo.com/media/clean/{0}.mp4"
AT_ROBOTS_BLOCKED = ("/aktuelles/mediathek/XXVIII/NRSITZ/19", "/aktuelles/mediathek/XXVIII/VER/53")
_AT_REDNER = re.compile(r'uuid:"([0-9a-f-]{36})",ts:(\d+),std_id:(\d+)')


def at_redner(page):
    """{std_id: (uuid, ts)} from a Mediathek page's embedded data."""
    return {int(s): (u, int(t)) for u, t, s in _AT_REDNER.findall(page or "")}


def locate_at(row, client):
    doc, _, fname = row["speech_id"].partition("#")
    m = re.search(r"_(\d+)\.html$", fname)
    if not m:
        raise LookupError("no protocol number in {0}".format(row["speech_id"]))
    path = "/aktuelles/mediathek/" + doc.strip("/")
    if any(path.startswith(p) for p in AT_ROBOTS_BLOCKED):
        raise LookupError("robots.txt disallows {0}".format(path))
    page = client.get_text(AT_BASE + path, FEED, "at-mediathek-" + doc.replace("/", "-"))
    red = at_redner(page).get(int(m.group(1)))
    if not red:
        raise LookupError("speech {0} not in the Mediathek page for {1}".format(m.group(1), doc))
    reply = json.loads(client.get_text(AT_MEDIA.format(red[0]), FEED, "at-media-" + red[0][:8], archive=False))
    if reply.get("STATUS") != "OK" or not reply.get("URL"):
        raise LookupError("the Mediathek has not built the download yet ({0}); try again later".format(reply))
    return [Span(media=reply["URL"], start=0.0, end=None, note="the Mediathek's own download of this speech")]


FR_OPENDATA = "https://www.assemblee-nationale.fr/dyn/opendata/{0}.xml"
FR_PORTAL = "https://videos.assemblee-nationale.fr/"
MONTHS_FR = ("janvier", "fevrier", "mars", "avril", "mai", "juin", "juillet", "aout", "septembre",
             "octobre", "novembre", "decembre")


def fr_video_slug_bits(date, n):
    d = datetime.date.fromisoformat(date)
    return ("{0}ere-seance".format(n) if n == 1 else "{0}eme-seance".format(n),
            "{0}-{1}-{2}".format(d.day, MONTHS_FR[d.month - 1], d.year))


def fr_video_links(listing, date, n):
    """Video page paths on the portal's seance-publique list for the date's n-th sitting."""
    seance, day = fr_video_slug_bits(date, n)
    links = sorted(set(re.findall(r'href="(video\.[^"]+)"', listing or "")))
    return [l for l in links if seance in l and l.endswith(day)]


def fr_video_page(page, doc_id):
    """The sitting's MP4 when the page's reportUrl names this compte rendu, else None."""
    rep = re.search(r"reportUrl\s*=\s*'([^']+)'", page or "")
    if not rep or not rep.group(1).rstrip("/").endswith(doc_id):
        return None
    mp4 = re.search(r'<meta property="og:video" content="([^"]+\.mp4)"', page or "")
    return mp4.group(1) if mp4 else None


def fr_span(timed, index):
    """(start, end) seconds of speech `index` in parse_sitting_timed's list: its
    first paragraph's stime to the next speech's (or its own last + 10 min)."""
    sp = timed[index]
    t0, t1 = sp[5], sp[6]
    if t0 is None:
        return None
    nxt = next((s[5] for s in timed[index + 1:] if s[5] is not None and s[5] > t0), None)
    end = nxt if nxt is not None else (t1 or t0) + 600.0
    # A heckle printed as its own paragraph ("Mme Sarah Legrain: Et alors ?") carries
    # the second it was shouted while the speaker talks on: on N016 #267 (213 words)
    # the next stime came 23 s in. So the span is at least the speech's words at a
    # slow pace (2 words a second) plus 15 s.
    return t0, max(end, t0 + len((sp[4] or "").split()) / 2.0 + 15.0)


def locate_fr(row, client):
    import importlib.util
    spec = importlib.util.spec_from_file_location("fr_chamber_clips", os.path.join(ROOT, "tools", "fr_chamber.py"))
    fr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fr)
    doc, _, idx = row["speech_id"].partition("#")
    xml = client.get_bytes(FR_OPENDATA.format(doc), FEED, "fr-cr-" + doc)
    date, timed = fr.parse_sitting_timed(xml)
    span = fr_span(timed, int(idx))
    if not span:
        raise LookupError("no stime on speech {0}".format(row["speech_id"]))
    n = fr.sitting_number_of_day(xml) or 1
    listing = client.get_text(FR_PORTAL + "seance-publique", FEED, "fr-portal-list")
    for link in fr_video_links(listing, date, n):
        page = client.get_text(FR_PORTAL + link, FEED, "fr-video-" + link[6:30])
        mp4 = fr_video_page(page, doc)
        if mp4:
            return [Span(media=mp4, start=max(0.0, span[0] - MARGIN_S), end=span[1] + MARGIN_S,
                         note="sitting video, stime {0:.0f}-{1:.0f} s".format(*span))]
    raise LookupError("no video on the portal's seance-publique list for {0} ({1}, sitting {2}); "
                      "the list holds recent sittings only".format(doc, date, n))


BE_API = "https://media.lachambre.be/api/archive"
BE_MP4 = "https://www1.lachambre.be/broadcast_lq_x/{0}"


def _hms(t):
    h, m, s = (t or "0:0:0").split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def be_spans(meeting, speaker):
    """Every turn of `speaker` in the meeting's event table, longest first."""
    events = [e for t in (meeting.get("eventTable") or {}).get("topics") or [] for e in t.get("events") or []]
    events.sort(key=lambda e: _hms(e.get("time")))
    want = set(fold(speaker).replace("-", " ").split())
    out = []
    for i, e in enumerate(events):
        got = set(fold(e.get("speaker")).replace("-", " ").split())
        if not want or not got or not (want <= got or got <= want or len(want & got) >= 2):
            continue
        a = _hms(e["time"])
        b = _hms(events[i + 1]["time"]) if i + 1 < len(events) else a + 900.0
        out.append((a, b))
    return sorted(out, key=lambda s: s[0] - s[1])


def locate_be(row, client):
    leg, _, number = (row.get("doc_id") or "").partition("/")
    key, cont = None, None
    for _page in range(8):
        url = BE_API + "?limit=50" + ("&continueKey=" + cont if cont else "")
        listing = client.get_json(url, FEED, "be-archive-" + (cont or "0")[:20])
        for m in listing.get("items") or []:
            if str(m.get("legislature")) == leg and m.get("meetingType") == "P" and str(m.get("meetingNr")) == number:
                key = m["key"]
                break
        cont = listing.get("continueKey")
        if key or not cont:
            break
    if not key:
        raise LookupError("plenary {0} not in the Chamber's video archive listing".format(row.get("doc_id")))
    meeting = client.get_json(BE_API + "/" + key, FEED, "be-meeting-" + key)
    spans = be_spans(meeting, row.get("speaker") or "")
    if not spans:
        raise LookupError("{0} has no turn in the event table of {1}".format(row.get("speaker"), key))
    media = BE_MP4.format(meeting["stream"])
    # An interruption is its own event while the speaker talks on (as in France's
    # record): a span is at least the speech's words at 2 a second plus 15 s.
    n = row.get("words") or len((row.get("text") or "").split())
    floor = n / 2.0 + 15.0 if n else 0.0
    spans = [(a, max(b, a + floor)) for a, b in spans]
    return [Span(media=media, start=max(0.0, a - MARGIN_S), end=b + MARGIN_S,
                 note="turn at {0:.0f} s".format(a)) for a, b in spans]


def locate_nl(row, client, video=None):
    if not video:
        raise LookupError("NL: pass the Debat Direct download with --video")
    return [Span(media=os.path.abspath(video), start=0.0, end=None, note="downloaded from Debat Direct")]


LOCATORS = {"ch": locate_ch, "at": locate_at, "fr": locate_fr, "be": locate_be}


def locate(cc, row, client, video=None):
    if video:
        return locate_nl(row, client, video)
    if cc not in LOCATORS:
        raise LookupError("{0}: no locator".format(cc))
    return LOCATORS[cc](row, client)


DD_API = "https://cdn.debatdirect.tweedekamer.nl/api"


def dd_politicians(politicians, speaker):
    """Debat Direct ids for a speaker as the Handelingen print them ('Van der
    Plas', 'Tijs van den Brink'): the surname with its prefix, or the full name."""
    want = fold(speaker).strip()
    if not want:
        return set()
    return {p.get("id") for p in politicians
            if want in (fold(p.get("lastName")), fold(p.get("name"))) or fold(p.get("name")).endswith(" " + want)}


def debatdirect_moments(date, speaker, debate, client):
    """Where to find a Dutch speech on Debat Direct, for the person downloading
    it: [(debate name, start time, url)] of the speaker's turns that day in the
    plenary debates whose name shares words with the stored debate's title."""
    agenda = client.get_json("{0}/agenda/{1}".format(DD_API, date), FEED, "nl-dd-agenda-" + date)
    actors = client.get_json("{0}/actors/{1}".format(DD_API, date), FEED, "nl-dd-actors-" + date)
    ids = dd_politicians(actors.get("politicians") or [], speaker)
    title = {w[:6] for w in fold(debate or "").split() if len(w) > 3}
    out = []
    for d in agenda.get("debates") or []:
        words = {w[:6] for w in fold(d.get("name")).split() if len(w) > 3}
        if "plenair" not in fold(d.get("locationName")) or not (title & words):
            continue
        detail = client.get_json("{0}/debates/{1}".format(DD_API, d["id"]), FEED, "nl-dd-debate-" + d["id"][:8])
        for e in sorted(detail.get("events") or [], key=lambda e: e.get("eventStart") or ""):
            if e.get("eventType") == "speaker" and e.get("objectId") in ids:
                out.append((d.get("name"), e["eventStart"],
                            "https://debatdirect.tweedekamer.nl/{0}/{1}/plenaire-zaal/{2}".format(
                                date, (d.get("categoryIds") or ["overig"])[0], d.get("slug"))))
    return out


# --- fetching, aligning, cutting, rendering ----------------------------------------

def tools():
    ff = shutil.which("ffmpeg")
    if not ff:
        try:
            import imageio_ffmpeg
            ff = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:                                    # noqa: BLE001
            ff = None
    return ff


def _run(cmd):
    subprocess.run(cmd, check=True, capture_output=True)


def fetch_window(ff, span, out_path):
    """Pull only the span from the source (a URL or a local file) with ffmpeg:
    over HTTP it seeks by byte range, so a speech in a four-hour sitting costs
    the speech. -> seconds of the source at which the window begins."""
    start = max(0.0, float(span.get("start") or 0.0))
    cmd = [ff, "-y", "-loglevel", "error"]
    if str(span["media"]).startswith("http"):
        cmd += ["-user_agent", UA]
    if start:
        cmd += ["-ss", "%.2f" % start]
    cmd += ["-i", span["media"]]
    if span.get("end") is not None:
        cmd += ["-t", "%.2f" % (float(span["end"]) - start)]
    cmd += ["-c", "copy", "-movflags", "+faststart", out_path]
    _run(cmd)
    return start


def find_passage(words, passage, min_ratio=0.5):
    """(first, last, ratio) word indices of the passage in a transcript, on folded words."""
    from src import socialcut as sc
    return sc.word_span(fold_words(words), fold(passage), min_ratio=min_ratio)


CREDIT_STYLE = "Style: Credit,{font},{size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,1.5,0,9,40,40,40,1"


def with_credit(ass, credit, duration, size):
    """Add the source credit, small, top right, for the clip's whole length."""
    from src import socialcut as sc
    if not credit:
        return ass
    head, sep, events = ass.partition("[Events]")
    head = head.rstrip("\n") + "\n" + CREDIT_STYLE.format(font=sc.FONT, size=size) + "\n\n"
    line = "Dialogue: 3,%s,%s,Credit,,0,0,0,,%s\n" % (sc._ts(0.0), sc._ts(max(duration, 0.5)), credit)
    return head + sep + events + line


def caption_item(name, party, duration, heard, passage, max_chars, max_words):
    """The UK's caption cards and their times, timed on folded words so accents
    and umlauts match Whisper's spelling."""
    from src import socialcut as sc
    cards = sc.chunk_caption(passage, max_chars=max_chars, max_words=max_words)
    folded_cards = [[fold(l) for l in c] for c in cards]
    times = sc.card_times(fold_words(heard), folded_cards, fold(passage))
    return {"name": name, "party": party, "duration": duration,
            "cards": [(c, t[0], t[1]) for c, t in zip(cards, times)]}


def purge(pack_dir, days, now=None, log=print):
    """Delete fetched source footage older than `days` (the windows/ folder)."""
    wdir = os.path.join(pack_dir, "windows")
    if not os.path.isdir(wdir):
        return 0
    now = now or time.time()
    gone = 0
    for f in os.listdir(wdir):
        p = os.path.join(wdir, f)
        if os.path.isfile(p) and now - os.path.getmtime(p) > days * 86400:
            os.remove(p)
            gone += 1
    if gone:
        log("purged {0} source file(s) older than {1} days from {2}".format(gone, days, wdir))
    return gone


def cut_pack(pack_dir, sources=None, only=None, video=None, model=WHISPER_MODEL, locate_only=False,
             client=None, log=print):
    """Cut every sequence entry (or `only` names) of a pack. -> report rows."""
    from src import alignclip, socialcut as sc, speechcut
    sources = sources or load_sources()
    state = json.load(open(os.path.join(pack_dir, "pack.json"), encoding="utf-8"))
    cc = state["country"]
    entry = sources.get(cc) or {}
    if not locate_only:
        gate(sources, cc, video=video)
    by_id = {s["speech_id"]: s for s in state["speeches"]}
    seq = parse_sequence(open(os.path.join(pack_dir, "sequence.md"), encoding="utf-8").read())
    if only:
        want = {fold(n) for n in only}
        seq = [e for e in seq if fold(e["name"]) in want]
    if video and len(seq) != 1:
        raise SystemExit("--video is one speaker's download: name that speaker with --only")
    client = client or _client(cc)
    trim = trim_only(entry)

    def run(cmd):
        check_trim_only_cmd(entry, cmd)
        _run(cmd)
    retention = int(entry.get("retention_days") or 30)
    purge(pack_dir, retention, log=log)
    ff = None if locate_only else tools()
    if not locate_only and not ff:
        raise SystemExit("no ffmpeg (the Mini's bundle: pip install imageio-ffmpeg)")
    wdir, final = os.path.join(pack_dir, "windows"), os.path.join(pack_dir, "final")
    os.makedirs(wdir, exist_ok=True)
    os.makedirs(final, exist_ok=True)
    lang = entry.get("language")
    report, items = [], []
    for n, e in enumerate(seq, 1):
        row = by_id.get(e.get("speech"))
        if not row:
            report.append((e, "SKIPPED", "no `speech:` line naming a speech in pack.json", None))
            continue
        try:
            spans = locate(cc, row, client, video=video)
        except Exception as exc:                             # noqa: BLE001
            report.append((e, "NOT LOCATED", str(exc)[:200], None))
            log("  {0}: not located: {1}".format(e["name"], exc))
            continue
        if locate_only:
            report.append((e, "LOCATED", "; ".join("{0} [{1}-{2}] {3}".format(
                s["media"], s["start"], s["end"], s["note"]) for s in spans), None))
            log("  {0}: {1} span(s), first {2}".format(e["name"], len(spans), spans[0]["note"]))
            continue
        s = "%02d-%s" % (n, name_slug(e["name"]))
        found = None
        for k, span in enumerate(spans):
            window = os.path.join(wdir, "{0}-{1}.mp4".format(s, k))
            words_json = window[:-4] + ".words.json"
            if not os.path.exists(window):
                try:
                    fetch_window(ff, span, window)
                except subprocess.CalledProcessError as exc:
                    log("  {0}: fetch failed: {1}".format(e["name"], (exc.stderr or b"")[-200:]))
                    continue
            words = alignclip.transcribe(window, window[:-4] + ".wav", ff, model_size=model,
                                         words_json=words_json, log=lambda *_a: None, language=lang)
            got = find_passage(words, e["passage"],
                               min_ratio=TRIM_ONLY_MIN_RATIO if trim else 0.5)
            if got:
                found = (window, words, got, span)
                break
        if not found:
            report.append((e, "NOT HEARD", "passage not heard in {0} span(s); correct sequence.md "
                                           "to the words as spoken".format(len(spans)), None))
            log("  {0}: passage not heard; skipped".format(e["name"]))
            continue
        window, words, (first, last, ratio), span = found
        start, end = sc.cut_bounds(words, first, last)
        part, vpart = os.path.join(wdir, s + "-part.mp4"), os.path.join(wdir, s + "-v.mp4")
        run([ff, "-y", "-loglevel", "error", "-ss", "%.3f" % start, "-i", window, "-t", "%.3f" % (end - start),
             "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=25,format=yuv420p",
             "-c:v", "libx264", "-crf", "18", "-preset", "medium",
             "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2", part])
        run([ff, "-y", "-loglevel", "error", "-i", part, "-vf", vertical_filter(entry, e.get("crop")),
             "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-c:a", "copy", vpart])
        dur = sc._dur(ff, part)
        heard = alignclip.transcribe(part, part[:-4] + ".wav", ff, model_size=model,
                                     words_json=part[:-4] + ".words.json", log=lambda *_a: None, language=lang)
        party = e.get("party") or row.get("party") or ""
        vitem = caption_item(e["name"], party, dur, heard, e["passage"], sc.CAPTION_MAX_CHARS, sc.CAPTION_MAX_WORDS)
        litem = caption_item(e["name"], party, dur, heard, e["passage"],
                             speechcut.CAPTION_MAX_CHARS, speechcut.CAPTION_MAX_WORDS)
        fontsdir = os.path.join(wdir, "fonts")
        sc.copy_fonts(fontsdir)
        logo = sc.LOGO if (entry.get("logo") and not trim and os.path.exists(sc.LOGO)) else None
        credit = entry.get("credit") or ""
        outs = []
        for kind, src, item, ass_text, size in (
                ("vertical", vpart, vitem, sc.ass_document([vitem], sc.FONT, (sc.FRAME_W, sc.FRAME_H), sc.CAPTION_POS,
                                                            sc.CAPTION_SIZE, sc.PLATE_Y, 60), 34),
                ("landscape", part, litem, speechcut.ass_landscape(litem), 30)):
            ass_path = os.path.join(wdir, "{0}-{1}.ass".format(s, kind))
            ass_out = with_credit(strip_plate(ass_text) if trim else ass_text, credit, dur, size)
            check_trim_only_ass(entry, ass_out)
            with open(ass_path, "w", encoding="utf-8") as fh:
                fh.write(ass_out)
            out = os.path.join(final, "{0}-{1}-{2}.mp4".format(cc, s, kind))
            filt = ("[1:v]scale=%d:-1[lg];[0:v][lg]overlay=60:70[v1];[v1]" % (sc.LOGO_W if kind == "vertical" else 240)
                    if logo else "[0:v]") + "ass=%s:fontsdir=%s[v]" % (ass_path, fontsdir)
            run([ff, "-y", "-loglevel", "error", "-i", src] + (["-i", logo] if logo else []) +
                ["-filter_complex", filt, "-map", "[v]", "-map", "0:a", "-c:v", "libx264", "-crf", "18",
                 "-preset", "medium", "-c:a", "copy", "-movflags", "+faststart", out])
            with open(out[:-4] + ".srt", "w", encoding="utf-8") as fh:
                fh.write(speechcut.srt(item))
            outs.append(out)
        items.append(outs[0])
        heard_text = " ".join(w for w, _a, _b in heard)
        report.append((e, "CUT", "%.1fs, match %.2f, from %s at %.1f s (%s); heard: %s" % (
            dur, ratio, "the downloaded file" if video else span["media"], span["start"] + start,
            span["note"], heard_text[:600]), outs))
        log("  {0:<28} {1:5.1f}s  match {2:.2f}".format(e["name"], dur, ratio))
    if len(items) > 1 and trim:
        log("  no reel: the agreement allows trimming only, not joining clips")
    elif len(items) > 1:
        lst = os.path.join(wdir, "concat.txt")
        with open(lst, "w") as fh:
            fh.write("".join("file '%s'\n" % os.path.abspath(p) for p in items))
        _run([ff, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy",
              "-movflags", "+faststart", os.path.join(final, "{0}-reel-vertical.mp4".format(cc))])
    write_report(pack_dir, cc, entry, report, locate_only)
    return report


def write_report(pack_dir, cc, entry, report, locate_only=False):
    lines = ["# Clips: {0}".format(cc.upper()), "",
             "Credit on every frame: `{0}`. For the post text: `{1}`.".format(
                 entry.get("credit", ""), " ".join((entry.get("post_credit") or "").split())),
             "Nothing here has been posted. {0}.".format(AWAITING.capitalize()), ""]
    if entry.get("agreement"):
        lines += ["Agreement: {0}.".format(agreement_text(entry).rstrip(".")), ""]
    if trim_only(entry):
        lines += [TRIM_ONLY_NOTE + " No reel is made.", ""]
    for e, status, detail, outs in report:
        lines.append("## {0}: {1}".format(e["name"], status))
        lines.append(detail)
        for o in outs or []:
            lines.append("- " + os.path.relpath(o, pack_dir))
        lines.append("")
    name = "locate.md" if locate_only else "clips.md"
    with open(os.path.join(pack_dir, name), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


def sources_table(sources):
    rows = ["| Country | Status | Source | Credit |", "|---|---|---|---|"]
    for cc, e in sources.items():
        st = e["status"] + (" (agreement recorded{0})".format(
            " " + str(e["agreement"].get("date")) if isinstance(e.get("agreement"), dict) else "")
            if e.get("agreement") else "") + (", trim-only" if trim_only(e) else "")
        rows.append("| {0} | {1} | {2} | {3} |".format(cc.upper(), st, e.get("source", ""), e.get("credit", "")))
    return "\n".join(rows)

