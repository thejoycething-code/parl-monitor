"""The GERMAN debate pack: round-up, onside checklist, quotes, shot list.

Christopher, 25 September 2026: "Build the debate packs." The Westminster
pack (src/debatepack.py) has existed since 7 September; Germany could not
have one while bundestag.de was refusing our connections, and the block
lifted overnight.

One debate in, one folder out (data/packs/de-<date>-<slug>/), the same four
files as Westminster so a reader who knows one knows the other:

  roundup.md    the agenda item, who led it, the minister's line, every
                speaker with their party
  checklist.md  THE CHECK: one ONSIDE: line per speaker for a human to fill.
                Nothing is quoted or clipped as "onside" until a person has
                said so.
  quotes.md     whole-sentence, on-topic passages per speaker
  shotlist.csv  per speaker: the clock time they rose and a link that opens
                the Bundestag's own recording of THAT speech

WHERE GERMANY DIFFERS FROM WESTMINSTER, measured 25 September 2026:

  * The Stenografischer Bericht carries NO per-speech timecodes. Hansard
    timecodes every contribution; protocol 21/96 has four "Uhr" mentions in
    858,106 characters, and three of them are about voting urns. So the
    Westminster trick of reading a clock time off each contribution is not
    available, and interpolating from "Beginn: 09:00 Uhr" across a sitting
    that ended at 02:15 would drift by hours.

  * The Mediathek is BETTER than interpolation, and better than Hansard:
    it publishes one video PER SPEECH, each with the speaker's name, their
    party, and the wall-clock second they rose (22:50:40). Sitting 96 has
    309 of them. So the clock times in a German pack are the Bundestag's
    own, not our arithmetic -- there is nothing to interpolate.

  * The join is therefore name+party against the protocol, not a timecode.
    join_media() says how many speeches it matched, because a silent 40%
    match rate would look exactly like a quiet debate.

FOOTAGE IS LINKED, NEVER DOWNLOADED. The Westminster pack downloads clips
under the Parliamentary Recording Unit's terms, which the pack's README
repeats restrict campaign use. The Bundestag's terms are its own and we have
not read them, so this pack links to the Bundestag's player and stops there.
Downloading is a decision for someone who has read the licence.
"""

from __future__ import annotations

import csv
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACKS = os.path.join(ROOT, "data", "packs")

# The Mediathek's own list endpoint, as the site's own page calls it. The
# ids in the path are its internal content nodes; sitzung and wahlperiode
# carry a '#' before the number, which is the site's convention and not a
# fragment. It serves 8 rows at a time whatever limit says, and reports the
# total as data-hits, so the caller pages on offset until it has them all.
MEDIA_LIST = ("https://www.bundestag.de/ajax/filterlist/de/mediathek/"
              "442338-442338?limit=8&noFilterSet=false"
              "&offset={offset}&sitzung=442332%23{sitzung}"
              "&wahlperiode=442334%23{wahlperiode}")
VIDEO_URL = "https://www.bundestag.de/mediathek/video?videoid={0}"
PAGE_SIZE = 8

BEGINN = re.compile(r"Beginn:\s*(\d{1,2}):(\d{2})\s*Uhr")
_HITS = re.compile(r'data-hits="(\d+)"')
_ENTRY = re.compile(r'videoid=(\d+)')
_TIME = re.compile(r'icon-time"></i>\s*(\d{2}:\d{2}:\d{2})')
_PARA = re.compile(r"<p[^>]*>(.*?)</p>", re.S)
_TAG = re.compile(r"<[^>]+>")
_TOP = re.compile(r'bt-top-headline">(.*?)</h3>', re.S)


def _text(raw):
    import html
    return " ".join(html.unescape(_TAG.sub("", raw or "")).split())


def sitting_start(protocol_text):
    """(hour, minute) of 'Beginn: 09:00 Uhr', or None.

    The one clock the protocol does give. Not used to place speeches -- the
    Mediathek does that -- but a pack whose recording cannot be found still
    says when the sitting opened.
    """
    hit = BEGINN.search(protocol_text or "")
    return (int(hit.group(1)), int(hit.group(2))) if hit else None


def parse_media_page(html_text):
    """[{videoid, clock, speaker, party, top}] from one Mediathek page."""
    top = _TOP.search(html_text or "")
    top = _text(top.group(1)) if top else ""
    out = []
    for m in _ENTRY.finditer(html_text or ""):
        # One entry's markup runs to the next videoid, or to the end.
        nxt = _ENTRY.search(html_text, m.end())
        chunk = html_text[m.start():nxt.start() if nxt else len(html_text)]
        paras = [_text(p) for p in _PARA.findall(chunk)]
        paras = [p for p in paras if p and not p.startswith("©")]
        clock = _TIME.search(chunk)
        # One entry per agenda item is the WHOLE debate rather than a
        # speech, and its person block carries the generic plenary photo's
        # caption ("Blick in den Plenarsaal") where a speaker's name would
        # be. Taking it for a speaker put a photograph in the speaker list.
        # It is kept, not dropped: the recording of the whole debate is the
        # one link a reader most often wants.
        whole = "Gesamter TOP" in chunk
        # paras: [clock, name, party-or-role, ...]. The copyright lines are
        # dropped above; anything after the role is caption furniture.
        speaker = "" if whole else (paras[1] if len(paras) > 1 else "")
        party = "" if whole else (paras[2] if len(paras) > 2 else "")
        out.append({"videoid": m.group(1),
                    "clock": clock.group(1) if clock else "",
                    "speaker": speaker, "party": party, "top": top,
                    "whole_top": whole})
    return out


def media_hits(html_text):
    """How many videos the sitting has in total, per the page's own count."""
    hit = _HITS.search(html_text or "")
    return int(hit.group(1)) if hit else 0


def fetch_media(client, wahlperiode, sitzung, fetch=None, log=print,
                max_pages=60):
    """Every video entry for one sitting, paging on offset.

    Paced deliberately: this host stopped answering us entirely on
    24 September after about 2,000 requests in a day, and a sitting is ~40
    pages. max_pages is a stop, not a target.
    """
    get = fetch or (lambda url: client.get_text(
        url, "de-media", "sitzung-{0}-{1}".format(wahlperiode, sitzung),
        archive=False))
    rows, offset, total = [], 0, None
    for _page in range(max_pages):
        html_text = get(MEDIA_LIST.format(offset=offset, sitzung=sitzung,
                                          wahlperiode=wahlperiode))
        if total is None:
            total = media_hits(html_text)
        page = parse_media_page(html_text)
        if not page:
            break
        rows.extend(page)
        offset += PAGE_SIZE
        if total and len(rows) >= total:
            break
    if total and len(rows) < total:
        log("  [gap] de-media: {0} of {1} entries for sitting {2}/{3}".format(
            len(rows), total, wahlperiode, sitzung))
    return rows


def surname(name):
    """The last word of a name, lowercased, for joining.

    The protocol prints 'Dr. Konrad Körner'; the Mediathek prints
    'Körner, Dr. Konrad'. Titles and order differ, the surname does not.
    """
    # Parenthesised parts are dropped first: the Bericht prints a
    # constituency after the name to tell two members apart ("Michael Brand
    # (Fulda)"), and taking the last word would have made the join key
    # "(fulda)" and matched nobody.
    # Parenthesised parts go first: the Bericht prints a constituency after
    # the name to tell two members apart ("Michael Brand (Fulda)"), and the
    # last word would otherwise be "(fulda)".
    cleaned = re.sub(r"\([^)]*\)", " ", name or "")
    # The two sources disagree on ORDER. The Bericht writes "Axel Müller"
    # and a role follows a comma ("Laumann, Minister"); the Mediathek can
    # write "Müller, Axel". Either way the surname is the last word before
    # the first comma when there is one, and the last word when there is
    # not -- so both "Brand, Michael" and "Michael Brand" key on "brand".
    head = cleaned.split(",")[0] if "," in cleaned else cleaned
    parts = [p for p in head.split() if p and not p.endswith(".")]
    return parts[-1].lower() if parts else ""


def join_media(speeches, media):
    """Attach a video entry to each speech, by surname and party.

    Returns (rows, matched). The count is returned and not merely logged
    because a join that quietly matches half the speakers produces a pack
    that looks complete and is not.
    """
    by_surname = {}
    for entry in media:
        if entry.get("whole_top"):
            continue
        by_surname.setdefault(surname(entry["speaker"]), []).append(entry)
    rows, matched = [], 0
    for speech in speeches:
        key = surname(speech.get("speaker"))
        hit = None
        for cand in by_surname.get(key, []):
            if cand.get("used"):
                continue
            party = (speech.get("party") or "").lower()
            if party and cand["party"] and party not in cand["party"].lower():
                continue
            hit = cand
            break
        if hit is not None:
            hit["used"] = True
            matched += 1
        rows.append(dict(speech, video=hit))
    return rows, matched


def tops(media):
    """{agenda heading: [entries]} for a sitting, in first-seen order."""
    out = {}
    for entry in media:
        out.setdefault(entry.get("top") or "", []).append(entry)
    return out


def select_top(media, term):
    """The entries for the agenda item whose heading matches `term`.

    Selection is by the MEDIATHEK's agenda heading, not by searching speech
    bodies. Searching the text was the first design and it failed on the
    first real sitting: the protocol DIP serves on the day is a
    Vorabfassung, and sitting 96's ran 7, 8, 9, 10, 12 -- TOP 11 was not in
    it at all, while the Mediathek had the whole debate on video. The
    recording is complete on the day and the transcript is not, so the
    recording decides who spoke.
    """
    want = (term or "").lower()
    for heading, entries in tops(media).items():
        if want and want in heading.lower():
            return heading, entries
    return None, []


def align_bodies(speakers, speeches):
    """Match a debate's speakers to their speeches IN THE PROTOCOL, by order.

    Keying on surname alone was wrong, and quietly so. The protocol is the
    whole sitting day -- TOPs 7 to 41 in sitting 96 -- so the first speech by
    "Brand" might belong to a debate five hours away, and the pack would
    print it under this one. Michael Brand led the motion being debated and
    came out with "nothing on topic", which is what sent me looking.

    Both sources are chronological, so the debate is a contiguous run of
    protocol speeches whose surnames follow the Mediathek's order. This
    takes the start that matches the most of them in sequence. A speaker the
    run never reaches keeps no body rather than borrowing someone else's.

    Returns ({index in speakers: speech}, matched).
    """
    want = [surname(s.get("speaker")) for s in speakers]
    if not want or not speeches:
        return {}, 0
    names = [surname(sp.get("speaker")) for sp in speeches]
    best_hits, best_map = 0, {}
    for start in range(len(names)):
        j, hits, mapping = start, 0, {}
        for i, key in enumerate(want):
            # 40 headings is far more than one agenda item, and stops a
            # near-miss run from reaching across the whole sitting.
            for k in range(j, min(len(names), start + 40)):
                if names[k] == key:
                    mapping[i] = speeches[k]
                    hits += 1
                    j = k + 1
                    break
        if hits > best_hits:
            best_hits, best_map = hits, mapping
        if hits == len(want):
            break
    return best_map, best_hits


CHAIR_ROLE = re.compile(r"Bundestags(?:vize)?präsident(?:in)?|"
                        r"^(?:Vize)?präsident(?:in)?\b", re.I)


def is_chair(role):
    """The presiding officer. They appear in the Mediathek like any other
    speaker -- Josephine Ortleb had three entries in one debate, all of them
    calling the next speaker -- and the protocol parser already drops them,
    so without this the pack listed procedure as contributions and then
    reported it as text it could not find."""
    return bool(CHAIR_ROLE.search(role or ""))


def rows_from_media(entries, speeches):
    """One row per SPEAKER in the agenda item, words attached where the
    protocol has them.

    A speaker the protocol does not carry keeps their row, with no body and
    a note. Dropping them would make a Vorabfassung's omissions look like
    silence.
    """
    speakers = [e for e in entries
                if not e.get("whole_top") and not is_chair(e.get("party"))]
    # The Mediathek lists newest first; a debate reads in the order it
    # happened, and the alignment depends on that order.
    speakers = sorted(speakers, key=lambda e: e.get("clock") or "")
    bodies, matched = align_bodies(speakers, speeches)
    rows = []
    for i, entry in enumerate(speakers):
        hit = bodies.get(i)
        rows.append({
            "speaker": entry["speaker"], "party": entry["party"],
            "role": (hit or {}).get("role") or "",
            "body": (hit or {}).get("body") or "",
            "excerpt": (hit or {}).get("excerpt") or "",
            "video": entry,
        })
    return rows, matched


def whole_debate_video(media):
    """The 'Gesamter TOP' entry: the recording of the whole debate."""
    for entry in media:
        if entry.get("whole_top"):
            return entry
    return None


# The Mediathek's heading repeats what the folder name already carries:
# "24.09.2026 96. Sitzung TOP 9 Änderung des Transplantationsgesetzes".
TOP_PREFIX = re.compile(r"^\s*\d{2}\.\d{2}\.\d{4}\s+\d+\.\s*Sitzung\s+"
                        r"(?:TOP\s+(?:ZP\s*)?[\w.]+\s+)?", re.I)
UMLAUT = {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}


def short_title(heading):
    """The agenda item without the date and sitting the folder already says."""
    return TOP_PREFIX.sub("", heading or "").strip() or (heading or "Debatte")


def slug(title, limit=44):
    """Transliterated, not stripped: "Änderung" became "nderung" on the first
    real pack, which is not a word and not searchable."""
    low = short_title(title).lower()
    for k, v in UMLAUT.items():
        low = low.replace(k, v)
    out = re.sub(r"[^a-z0-9]+", "-", low).strip("-")
    return out[:limit].rstrip("-") or "debatte"


def pack_dir(date, title):
    return os.path.join(PACKS, "de-{0}-{1}".format(date, slug(title)))


def _who(row):
    bits = [row.get("speaker") or "A member"]
    role = (row.get("party") or row.get("role") or "").strip()
    if role and role != "member":
        bits.append("({0})".format(role))
    return " ".join(bits)


def render_roundup(debate, rows, matched, start=None):
    out = ["# {0}".format(short_title(debate.get("title")) or "Debatte"), "",
           "*{0}, Sitzung {1}. {2} speaker{3}.*".format(
               debate.get("date") or "", debate.get("sitzung") or "",
               len(rows), "" if len(rows) == 1 else "s"), ""]
    if start:
        out += ["Sitting opened {0:02d}:{1:02d}.".format(*start), ""]
    # EVERY speaker here has a recording: the list comes from the Mediathek.
    # What varies is whether the protocol carries their WORDS, which on the
    # day it often does not -- DIP serves a Vorabfassung.
    out += ["Every speaker below has a recording. The protocol carries the "
            "words of {0} of {1}.".format(matched, len(rows)), "",
        "## Who spoke", "",
        "| # | Speaker | Party or role | Rose | Recording |",
        "|---|---|---|---|---|"]
    for i, row in enumerate(rows, 1):
        video = row.get("video")
        out.append("| {0} | {1} | {2} | {3} | {4} |".format(
            i, row.get("speaker") or "-",
            row.get("party") or row.get("role") or "-",
            (video or {}).get("clock") or "-",
            "[watch]({0})".format(VIDEO_URL.format(video["videoid"]))
            if video else "not found"))
    out += ["", "*Direction is NOT read here. Who is with us is the "
            "checklist's question, and a human answers it.*", ""]
    return "\n".join(out)


def render_checklist(debate, rows):
    out = ["# Onside check - {0}".format(short_title(debate.get("title"))), "",
           "*One line per speaker. Write yes or no after ONSIDE:. Nothing is "
           "quoted or clipped as onside until you have. Leave a line blank to "
           "skip it; blank is not agreement.*", "",
           "Do not edit the `### speaker:` lines.", "", "---", ""]
    for row in rows:
        out += ["### speaker: {0}".format(row.get("speaker") or "-"),
                "- party or role: {0}".format(
                    row.get("party") or row.get("role") or "-"),
                "- said: {0}".format((row.get("excerpt") or "")[:220]),
                "ONSIDE: ", "NOTE: ", ""]
    return "\n".join(out)


def render_quotes(debate, rows, patterns, limit=3):
    """Whole sentences that mention what the debate is about.

    Same bar as the member pages: a sentence, not a fragment, and never a
    sentence assembled from pieces. A speaker with nothing on topic is
    listed with nothing under them rather than dropped, so the pack does not
    imply they were silent.
    """
    out = ["# Quotes - {0}".format(short_title(debate.get("title"))), "",
           "*Whole sentences, verbatim, from the Stenografischer Bericht. "
           "Onside is not decided here.*", ""]
    for row in rows:
        out.append("## {0}".format(_who(row)))
        found = sentences_matching(row.get("body") or "", patterns, limit)
        out += ["> {0}".format(s) for s in found] or ["*Nothing on topic.*"]
        out.append("")
    return "\n".join(out)


# Words in an agenda heading that carry no subject.
# "sitzung" is here as well as in TOP_PREFIX: the prefix only strips when the
# heading carries the date, and a heading without it left "Sitzung" as the
# subject of the debate.
_STOP = {"sitzung", "tagesordnungspunkt", "zusatzpunkt",
         "aenderung", "änderung", "gesetz", "gesetzes", "antrag", "beratung",
         "bericht", "erste", "zweite", "dritte", "lesung", "abschliessende",
         "abschließende", "beratungen", "ohne", "aussprache", "eines",
         "einer", "eine", "und", "der", "die", "das", "des", "dem", "den",
         "zur", "zum", "von", "vom", "fuer", "für", "ueber", "über"}


def topic_terms(heading, stem=12):
    """Search stems from the agenda heading, for finding on-topic sentences.

    STEMS, not words. German compounds: the heading says
    "Transplantationsgesetzes" and the speeches say "Transplantation",
    "Transplantationsmedizin", "Organtransplantation". Matching the heading's
    word verbatim found nothing at all in the first real pack -- every
    speaker came out "nothing on topic" in a debate entirely about it.
    """
    out = []
    for word in re.findall(r"[A-Za-zÄÖÜäöüß-]{4,}", short_title(heading)):
        low = word.lower()
        if low in _STOP or len(low) < 6:
            continue
        out.append(word[:stem])
    return out


_SENT = re.compile(r"[^.!?]+[.!?]")


def sentences_matching(body, patterns, limit=3):
    text = " ".join((body or "").split())
    out = []
    for hit in _SENT.finditer(text):
        s = hit.group(0).strip()
        if len(s) < 40 or len(s) > 400:
            continue
        low = s.lower()
        if any(p.lower() in low for p in patterns):
            out.append(s)
        if len(out) >= limit:
            break
    return out


def write_shotlist(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as handle:
        w = csv.writer(handle)
        w.writerow(["speaker", "party_or_role", "rose", "videoid", "url"])
        for row in rows:
            video = row.get("video") or {}
            w.writerow([row.get("speaker") or "", row.get("party") or "",
                        video.get("clock") or "", video.get("videoid") or "",
                        VIDEO_URL.format(video["videoid"]) if video else ""])
    return path


README = """# {title}

{date}, Sitzung {sitzung} of the {wahlperiode}. Wahlperiode.

  roundup.md    every speaker, with the clock time they rose and a link to
                the Bundestag's recording of that speech
  checklist.md  THE CHECK. Write yes or no on each ONSIDE: line. Nothing in
                this pack is an assessment of whose side anyone is on.
  quotes.md     whole sentences, verbatim, on the debate's subject
  shotlist.csv  the same speakers as a spreadsheet

Clock times and recordings are the Bundestag's own, one video per speech,
not our arithmetic: the Stenografischer Bericht carries no per-speech
timecodes and nothing here interpolates them.

FOOTAGE IS LINKED, NOT DOWNLOADED. The Bundestag's terms of use for its
recordings are its own and we have not read them. Anyone proposing to
download, cut or publish this footage should read them first.
"""


def write_pack(debate, rows, matched, patterns, start=None, root=None):
    folder = root or pack_dir(debate.get("date") or "", debate.get("title") or "")
    os.makedirs(folder, exist_ok=True)
    files = {
        "README.md": README.format(
            title=short_title(debate.get("title")), date=debate.get("date") or "",
            sitzung=debate.get("sitzung") or "", wahlperiode=debate.get("wahlperiode") or ""),
        "roundup.md": render_roundup(debate, rows, matched, start),
        "checklist.md": render_checklist(debate, rows),
        "quotes.md": render_quotes(debate, rows, patterns),
    }
    for name, text in files.items():
        with open(os.path.join(folder, name), "w", encoding="utf-8") as handle:
            handle.write(text.rstrip() + "\n")
    write_shotlist(os.path.join(folder, "shotlist.csv"), rows)
    return folder


def parse_checklist(path):
    """-> [(speaker, onside, note)] for speakers a human answered."""
    out, cur, onside, note = [], None, None, ""

    def flush():
        if cur and onside is not None:
            out.append((cur, onside, note))

    with open(path, encoding="utf-8") as handle:
        for raw in handle:
            line = raw.rstrip("\n")
            if line.startswith("### speaker:"):
                flush()
                cur, onside, note = line.split(":", 1)[1].strip(), None, ""
            elif line.upper().startswith("ONSIDE:"):
                v = line.split(":", 1)[1].strip().lower()
                onside = True if v in ("yes", "y", "ja") else (
                    False if v in ("no", "n", "nein") else None)
            elif line.upper().startswith("NOTE:"):
                note = line.split(":", 1)[1].strip()
    flush()
    return out
