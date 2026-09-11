"""The debate pack: round-up, onside quotes, shot list, clips -- for one debate.

Christopher, 2026-09-07: "For days like today when there's a key debate
happening -- surrogacy -- what can I do to create a round-up of the debate.
... capture onside quotes and capture video ... Build in a check so we can
assess who was and isn't onside."

One debate in, one folder out (data/packs/<date>-<slug>/):
  roundup.md    what it was, who led it, the minister's line, every speaker
                with the direction the stance pass read and its reason
  checklist.md  THE CHECK: one ONSIDE: line per speaker for a human to fill
                (yes / no). Nothing is quoted or clipped as "onside" until
                a person has said so; the pass's reading is shown as a
                first cut, never as the verdict.
  quotes.md     whole-sentence, on-topic quotes per speaker, each linked to
                the exact Hansard paragraph (same bar as the member pages)
  shotlist.csv  per speaker: clock time they rose, how long, and a link
                that opens the footage at that moment
  clips/        the footage, once --download is run for confirmed speakers

Sources. Hansard's debate call gives every contribution with the member,
the text and a timecode (wall clock, Europe/London). parliamentlive.tv's
stream is addressed by wall clock too -- its HLS manifest takes
start=...Z&end=...Z and returns just that window (measured 2026-09-07:
a two-minute window came back as 121 seconds) -- so a clip is fetched by
time, never by downloading the sitting.

Footage is Parliament's, licensed by the Parliamentary Recording Unit;
the pack's README repeats that the terms restrict campaign use, and the
decision to use a clip stays with the person who ticked the checklist.
"""

from __future__ import annotations

import csv
import datetime
import json
import os
import re
import subprocess
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACKS = os.path.join(ROOT, "data", "packs")
HANSARD_API = "https://hansard-api.parliament.uk"
LONDON = ZoneInfo("Europe/London")
_TAG = re.compile(r"<[^>]+>")
CHAIR = re.compile(r"\bSpeaker\b|in the Chair|Chairman|Deputy Speaker|Madam Deputy", re.I)
DIRECTION = {2: "With us, strongly", 1: "With us", 0: "Neutral or unclear", -1: "Against us", -2: "Against us, strongly"}
WORDS_PER_SECOND = 2.5   # ~150 words a minute, the Commons' spoken pace
PAD_BEFORE = 5      # seconds of footage before the member rises
PAD_AFTER = 4


# -- Hansard ----------------------------------------------------------------------

def find_debate(client, date, term, house="Commons", attempts=3, pause=5, sleep=None):
    """[(title, section, ext_id)] whose title contains `term` on that day.

    In the minutes after Hansard publishes, the section tree can come back
    with the new section one request and without it the next (measured
    2026-09-07: the surrogacy debate was found, then not, then found). An
    empty answer is retried a few times before it is believed."""
    import time
    sleep = sleep or time.sleep
    for attempt in range(attempts):
        out = _find_debate_once(client, date, term, house)
        if out or attempt == attempts - 1:
            return out
        sleep(pause)
    return []


def _find_debate_once(client, date, term, house):
    out = []
    names = client.get_json("{0}/overview/sectionsforday.json?house={1}&date={2}".format(HANSARD_API, house, date),
                            "hansard", "sections-{0}-{1}".format(house, date), archive=False) or []
    for sec in names:
        tree = client.get_json("{0}/overview/sectiontrees.json?section={1}&date={2}&house={3}".format(
            HANSARD_API, sec, date, house), "hansard", "tree-{0}-{1}-{2}".format(house, date, sec), archive=False)

        def walk(node):
            if isinstance(node, dict):
                if node.get("ExternalId") and node.get("Title") and term.lower() in node["Title"].lower():
                    out.append((node["Title"], sec, node["ExternalId"]))
                for c in node.get("SectionTreeItems") or []:
                    walk(c)
            elif isinstance(node, list):
                for c in node:
                    walk(c)
        walk(tree)
    return out


def fetch_debate(client, ext_id):
    return client.get_json("{0}/debates/debate/{1}.json".format(HANSARD_API, ext_id), "hansard",
                           "debate-{0}".format(ext_id))


def _clean(text):
    return " ".join(_TAG.sub(" ", text or "").split())


_ROLE = re.compile(r"Minister|Secretary of State|Under-Secretary|Parliamentary Secretary|Solicitor General|"
                   r"Attorney General|Chancellor|Leader of the House|Prime Minister|Lord Privy Seal|Paymaster", re.I)


def _parse_attributed(name):
    """'Dave Robertson (Lichfield) (Lab)' -> (name, seat, party).
    A minister is attributed by office with the name in brackets --
    'The Minister of State, Ministry of Justice (Sarah Sackman)' -- so the
    brackets hold the person and the prefix is the role, not a party."""
    raw = (name or "").strip()
    m = re.match(r"^(.*?)\s*\(([^()]+)\)\s*\(([^()]+)\)\s*$", raw)
    if m:
        return m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
    m = re.match(r"^(.*?)\s*\(([^()]+)\)\s*$", raw)
    if m:
        prefix, inner = m.group(1).strip(), m.group(2).strip()
        if _ROLE.search(prefix):
            return inner, None, None            # the person; the office is in `attributed`
        return prefix, None, inner
    return raw, None, None


def divisions(payload, date):
    """[{number, time, ayes, noes, result, question}] from the section's Division items.

    The question is the procedural contribution just before the division ("Question
    put accordingly, That the Bill now be read a Second time."). A debate's defining
    fact is often its result, and the report writer had no way of knowing it: the
    11 September 2026 Second Reading pack read as a debate that was still going on.
    """
    out, items = [], payload.get("Items") or []
    for i, it in enumerate(items):
        if it.get("ItemType") != "Division" or not it.get("Value"):
            continue
        parts = [p.strip() for p in _clean(it["Value"]).split("|")]
        try:
            number, time, ayes, noes = parts[0], parts[1], int(parts[2]), int(parts[3])
        except (IndexError, ValueError):
            continue
        result = next((p for p in parts if "accordingly" in p), "")
        question = ""
        for j in range(i - 1, max(-1, i - 4), -1):
            v = _clean(items[j].get("Value") or "")
            if items[j].get("ItemType") == "Contribution" and re.search(r"Question put|Question, That", v):
                question = v
                break
        out.append({"number": number, "time": time, "ayes": ayes, "noes": noes,
                    "result": result, "question": question, "date": date})
    return out


def _interpolate_starts(rows):
    """Place every unanchored contribution between the anchors around it.

    Two estimates, and the EARLIER wins. Running on from the previous contribution
    at spoken pace is right when the words between two timestamps are few and
    something unrecorded filled the gap (a division, a suspension); it overshoots
    when they are many, because members speak faster than the assumed pace and the
    estimate runs past the next timestamp -- ten minutes past, on 11 September 2026.
    Interpolating in proportion to words spoken is right when the gap is dense with
    speech and wrong when it is not, stretching a one-line intervention across nine
    silent minutes. A contribution cannot have started later than either says, so
    the minimum is the safe estimate. After the last anchor only the run-on exists."""
    def weight(r):
        return len(r["text"].split()) / WORDS_PER_SECOND + 6.0
    i = 0
    while i < len(rows):
        if not rows[i].get("anchored") or rows[i]["start"] is None:
            i += 1
            continue
        j = i + 1
        while j < len(rows) and not (rows[j].get("anchored") and rows[j]["start"] is not None):
            j += 1
        run = rows[i + 1:j]
        if run:
            if j < len(rows):
                span = (rows[j]["start"] - rows[i]["start"]).total_seconds()
                total = weight(rows[i]) + sum(weight(r) for r in run)
                acc = weight(rows[i])
                t, prev = rows[i]["start"], rows[i]
                for r in run:
                    interpolated = rows[i]["start"] + datetime.timedelta(seconds=span * acc / total)
                    t = t + datetime.timedelta(seconds=int(weight(prev)))      # the run-on estimate
                    r["start"] = min(interpolated, t)
                    acc += weight(r)
                    prev = r
            else:
                t = rows[i]["start"]
                prev = rows[i]
                for r in run:
                    t = t + datetime.timedelta(seconds=int(weight(prev)))
                    r["start"] = t
                    prev = r
        i = j


def contributions(payload, date):
    """Every spoken contribution in order, each with a start clock.

    Hansard timecodes are sparse -- a Timestamp item every few minutes and
    a Timecode on some contributions -- so a contribution without one takes
    the last clock seen, and its end is the next contribution's start."""
    rows = []
    clock = None
    pending = None
    for it in payload.get("Items") or []:
        if it.get("Timecode"):
            try:
                clock = datetime.datetime.fromisoformat(it["Timecode"]).replace(tzinfo=LONDON)
            except ValueError:
                pass
        if it.get("ItemType") == "Timestamp" and it.get("Value") and not it.get("Timecode"):
            m = re.match(r"(\d{1,2}):(\d{2})(?::(\d{2}))?", _clean(it["Value"]))
            if m:
                d = datetime.date.fromisoformat(date)
                clock = datetime.datetime(d.year, d.month, d.day, int(m.group(1)), int(m.group(2)),
                                          int(m.group(3) or 0), tzinfo=LONDON)
        if it.get("ItemType") == "Timestamp" or it.get("Timecode"):
            pending = clock                     # the next contribution starts here
        if it.get("ItemType") != "Contribution" or not it.get("Value") or not it.get("AttributedTo"):
            continue
        name, seat, party = _parse_attributed(it["AttributedTo"])
        text = _clean(it["Value"])
        # A contribution takes the clock only when one was printed just before it
        # (a Timestamp item, or its own Timecode). Everything between two such
        # anchors is placed by INTERPOLATION below, in proportion to the words
        # spoken -- not by running on from the previous estimate. On 11 September
        # 2026 the record carried 43 timestamps for 316 items and no timecodes;
        # extrapolating by word rate ran ten minutes past the next timestamp and
        # fetched Ashley Dalton's footage for Zubir Ahmed's speech.
        anchored = pending is not None
        start = pending if anchored else None
        pending = None
        rows.append({"order": it.get("OrderInSection"), "attributed": it["AttributedTo"], "name": name,
                     "seat": seat, "party": party, "member_id": it.get("MemberId"),
                     "ext_id": it.get("ExternalId"), "text": text, "anchored": anchored,
                     "start": start, "chair": bool(CHAIR.search(it["AttributedTo"]))})
    _interpolate_starts(rows)
    # END of a contribution: Hansard's clocks are sparse (a Timestamp every
    # few minutes), so "the next clock" credited a one-minute intervener with
    # the whole speech that followed (290 minutes, 2026-09-04). Length comes
    # from the words spoken at spoken pace, plus a little room, and is CAPPED
    # by the next clock -- never longer than the record allows.
    for i, r in enumerate(rows):
        nxt = next((x["start"] for x in rows[i + 1:] if x["start"] and (not r["start"] or x["start"] > r["start"])), None)
        r["est_seconds"] = int(len(r["text"].split()) / WORDS_PER_SECOND) + 6
        if r["start"]:
            est_end = r["start"] + datetime.timedelta(seconds=r["est_seconds"])
            r["end"] = min(nxt, est_end) if nxt else est_end
        else:
            r["end"] = None
    return rows


def speakers(rows):
    """One entry per member (the Chair excluded): joined text, first rise,
    total seconds on their feet, number of contributions."""
    out = {}
    for r in rows:
        if r["chair"]:
            continue
        key = r["member_id"] or r["name"]
        s = out.setdefault(key, {"member_id": r["member_id"], "name": r["name"], "seat": r["seat"], "party": r["party"],
                                 "attributed": r["attributed"], "texts": [], "spans": [], "ext_ids": [],
                                 "first": None, "seconds": 0, "count": 0})
        s["texts"].append(r["text"])
        s["ext_ids"].append(r["ext_id"])
        s["count"] += 1
        if r["start"]:
            s["first"] = s["first"] or r["start"]
            if r["end"]:
                s["spans"].append((r["start"], r["end"]))
                s["seconds"] += max(0, int((r["end"] - r["start"]).total_seconds()))
    for s in out.values():
        s["text"] = " ".join(s["texts"])
        s["words"] = len(s["text"].split())
    return sorted(out.values(), key=lambda s: -(s["words"]))


def minister(rows):
    """The first ministerial contribution: the line taken."""
    pat = re.compile(r"Minister|Secretary of State|Under-Secretary|Solicitor|Attorney|Parliamentary Secretary", re.I)
    for r in rows:
        if not r["chair"] and pat.search(r["attributed"] or ""):
            return r
    return None


# -- direction: the stance pass, then the human check ----------------------------------

def read_direction(speaks, title, areas, api_key, transport=None, usage_sink=None):
    """Stance results per speaker via the existing classifier. One call per
    twenty speakers; the caller caches the answers in pack.json so a re-run
    never pays twice."""
    from src import stance
    evidence = [stance.Evidence(ref="pack:{0}".format(s["member_id"] or s["name"]), kind="debate",
                                line="Spoke: {0}".format(title), areas=list(areas), text=s["text"][:6000])
                for s in speaks]
    out = {}
    for r in stance.classify_live(evidence, api_key=api_key, transport=transport, usage_sink=usage_sink):
        out[r.ref.split(":", 1)[1]] = {"stance": r.stance, "why": r.why}
    return out


def parse_checklist(path):
    """{speaker key: 'yes'|'no'} from the ONSIDE: lines a human filled in."""
    out, cur = {}, None
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.rstrip("\n")
            if line.startswith("### speaker:"):
                cur = line.split("speaker:", 1)[1].strip()
            elif cur and line.upper().startswith("ONSIDE:"):
                v = line.split(":", 1)[1].strip().lower()
                if v in ("yes", "y", "no", "n"):
                    out[cur] = "yes" if v.startswith("y") else "no"
    return out


# -- quotes ------------------------------------------------------------------------

def quotes_for(text, patterns, limit=3):
    """Up to `limit` shareable passages, best first, from one speaker's words."""
    from src import quotes
    found = []
    chunks = [c for c in re.split(r"(?<=[.!?])\s+(?=[A-Z“\"])", text) if c]
    # windows of ~6 sentences, stepping by 3, so a good passage is not split
    for i in range(0, max(1, len(chunks)), 3):
        window = " ".join(chunks[i:i + 6])
        q = quotes.shareable(window, patterns)
        if q and q not in found:
            found.append(q)
    found.sort(key=lambda q: -quotes.quotability(q))
    return found[:limit]


# -- video -------------------------------------------------------------------------

def event_guid(value):
    m = re.search(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", value or "", re.I)
    return m.group(1) if m else None


def todays_events(html_text):
    """[(guid, label)] from parliamentlive.tv's front listing (today only)."""
    out = []
    parts = re.split(r"Event/Index/", html_text or "")
    for part in parts[1:]:
        m = re.match(r"([0-9a-f-]{36})(.*)", part, re.S)
        if not m:
            continue
        label = " ".join(_TAG.sub(" ", m.group(2)[:600]).split())
        out.append((m.group(1), label[:120]))
    seen, uniq = set(), []
    for g, label in out:
        if g not in seen:
            seen.add(g)
            uniq.append((g, label))
    return uniq


SEARCH_URL = ("https://parliamentlive.tv/Search?Keywords=&Member=&MemberId=&House={house}&Business=&Start={date}&End={date}")


def search_events_html(html_text):
    """[(guid, label)] from parliamentlive.tv's archive search results: one
    'search-item' block per event, the venue in the thumbnail's alt text and
    the heading. Search covers every sitting since 4 December 2007."""
    out, seen = [], set()
    # the class attribute reads 'col-md-12 search-item': match the token, not the whole value
    for block in re.split(r'class="[^"]*\bsearch-item\b[^"]*"', html_text or "")[1:]:
        g = event_guid(block)
        if not g or g in seen:
            continue
        seen.add(g)
        alt = re.search(r'alt="([^"]*)"', block)
        head = re.search(r"<h5[^>]*>(.*?)</h5>", block, re.S)
        when = re.search(r"\b\d{1,2}\.\d{2}\s*[ap]m\b|\b\d{1,2}:\d{2}\b", _TAG.sub(" ", block))
        label = " ".join(x for x in ((alt.group(1) if alt else ""), (_clean(head.group(1)) if head else ""),
                                     (when.group(0) if when else "")) if x)
        out.append((g, label[:160]))
    return out


def search_events(date, house="", fetch=None):
    """Archived sittings on a date, via the site's own search form (GET)."""
    url = SEARCH_URL.format(house=house or "", date=date)
    if fetch is None:
        import urllib.request

        def fetch(u):
            with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=40) as r:
                return r.read().decode("utf-8", "replace")
    return search_events_html(fetch(url))


def pick_event(events, venue):
    """The guid whose label names the venue ('Westminster Hall', 'House of Commons'), BSL feed excluded."""
    for g, label in events:
        if venue.lower() in label.lower() and "BSL" not in label:
            return g
    return None


def manifest_for(guid, yt_dlp="yt-dlp"):
    """The stream's master manifest URL (without its start parameter) and
    the event's start, via yt-dlp's parliamentlive.tv extractor."""
    out = subprocess.run([yt_dlp, "-J", "--no-warnings", "https://parliamentlive.tv/Event/Index/{0}".format(guid)],
                         capture_output=True, text=True, timeout=120)
    if out.returncode:
        raise RuntimeError("yt-dlp could not read the event: {0}".format(out.stderr.strip()[:200]))
    data = json.loads(out.stdout)
    fmts = data.get("formats") or []
    man = next((f.get("manifest_url") for f in fmts if f.get("manifest_url")), None)
    if not man:
        raise RuntimeError("no manifest in yt-dlp output")
    return man.split("?")[0], datetime.datetime.fromtimestamp(data.get("timestamp") or 0, tz=datetime.timezone.utc)


def window_url(manifest_base, start, end):
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    return "{0}?start={1}&end={2}".format(manifest_base, start.astimezone(datetime.timezone.utc).strftime(fmt),
                                          end.astimezone(datetime.timezone.utc).strftime(fmt))


def offset_link(guid, start, event_start):
    if not (start and event_start):
        return "https://parliamentlive.tv/Event/Index/{0}".format(guid)
    secs = max(0, int((start - event_start).total_seconds()))
    return "https://parliamentlive.tv/Event/Index/{0}?in={1:02d}:{2:02d}:{3:02d}".format(
        guid, secs // 3600, (secs % 3600) // 60, secs % 60)


HEIGHTS = {"300": 180, "850": 360, "1300": 576, "3000": 1080}   # the live ladder's ids, still accepted


def format_selector(quality):
    """A height cap, whatever the caller wrote: '576', '576p', or a live
    format id. The archive copy of a sitting carries different format ids
    from the live stream (measured 2026-09-07: 383/966/1443/3245 against
    300/850/1300/3000), so ids are never passed through."""
    q = str(quality or "576").lower().rstrip("p")
    h = HEIGHTS.get(q) or (int(q) if q.isdigit() else 576)
    return "bv*[height<={0}]+ba/b[height<={0}]/b".format(h)


def window_is_honoured(manifest_base, start, end, fetch=None):
    """Does this stream return just the window asked for? The live stream
    does; the archive recording ignores the parameters and returns the whole
    sitting (9,700 seconds for a 30-second ask, measured 2026-09-07)."""
    import urllib.request
    if fetch is None:
        def fetch(u):
            with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=30) as r:
                return r.read().decode("utf-8", "replace")
    try:
        top = fetch(window_url(manifest_base, start, end))
        rend = [l for l in top.splitlines() if l and not l.startswith("#")]
        if not rend:
            return False
        u = rend[0] if rend[0].startswith("http") else manifest_base.rsplit("/", 1)[0] + "/" + rend[0]
        pl = fetch(u)
        total = sum(float(x) for x in re.findall(r"#EXTINF:([\d.]+)", pl))
        asked = (end - start).total_seconds()
        return 0 < total <= asked * 2 + 60
    except Exception:                                       # noqa: BLE001
        return False


def _hms(seconds):
    s = max(0, int(seconds))
    return "{0:02d}:{1:02d}:{2:02d}".format(s // 3600, (s % 3600) // 60, s % 60)


def download_clip(manifest_base, start, end, out_path, yt_dlp="yt-dlp", ffmpeg=None, quality="576",
                  guid=None, event_start=None, windowed=None):
    """Fetch one span of a sitting as an mp4.

    Two routes. WINDOW: while the stream is live or freshly ended, the
    manifest takes start=...&end=... and returns just that span. OFFSET: once
    the sitting is an archive recording, the window is ignored, so the clip
    is cut by offset from the recording's start with yt-dlp's section
    download (ffmpeg does the cut). The caller says which (windowed), or
    it is probed."""
    start = start - datetime.timedelta(seconds=PAD_BEFORE)
    end = end + datetime.timedelta(seconds=PAD_AFTER)
    if windowed is None:
        windowed = window_is_honoured(manifest_base, start, end)
    cmd = [yt_dlp, "--no-warnings", "-f", format_selector(quality), "--merge-output-format", "mp4", "-o", out_path]
    if ffmpeg:
        cmd[1:1] = ["--ffmpeg-location", ffmpeg]
    if windowed:
        cmd.append(window_url(manifest_base, start, end))
    else:
        if not (guid and event_start):
            raise RuntimeError("archive recording: need the event guid and its start to cut by offset")
        a = (start - event_start).total_seconds()
        b = (end - event_start).total_seconds()
        cmd += ["--download-sections", "*{0}-{1}".format(_hms(a), _hms(b)), "--force-keyframes-at-cuts",
                "https://parliamentlive.tv/Event/Index/{0}".format(guid)]
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    if out.returncode:
        raise RuntimeError("download failed: {0}".format((out.stderr or out.stdout).strip()[-300:]))
    return out_path


# -- the files ------------------------------------------------------------------------

def slug(title):
    return re.sub(r"[^a-z0-9]+", "-", (title or "debate").lower()).strip("-")[:60]


def hansard_url(house, date, ext_id, contribution=None):
    base = "https://hansard.parliament.uk/{0}/{1}/debates/{2}/".format(house, date, ext_id)
    return base + ("#contribution-{0}".format(contribution) if contribution else "")


def _clock(dt):
    return dt.astimezone(LONDON).strftime("%H:%M:%S") if dt else "?"


def write_pack(folder, meta, speaks, directions, confirmed, mins, patterns, guid=None, event_start=None):
    os.makedirs(folder, exist_ok=True)
    title, house, date, ext = meta["title"], meta["house"], meta["date"], meta["ext_id"]
    ext_ = ext
    label = lambda s: DIRECTION.get((directions.get(str(s["member_id"] or s["name"])) or {}).get("stance"), "Not read")
    why = lambda s: (directions.get(str(s["member_id"] or s["name"])) or {}).get("why") or ""
    who = lambda s: s["name"] + (" ({0})".format(", ".join(x for x in (s["party"], s["seat"]) if x)) if (s["party"] or s["seat"]) else "")
    key = lambda s: str(s["member_id"] or s["name"])

    # roundup
    out = ["# {0}".format(title), "",
           "*{0}, {1}. [Hansard]({2}){3}. Generated {4}.*".format(
               house, date, hansard_url(house, date, ext),
               " · [Footage](https://parliamentlive.tv/Event/Index/{0})".format(guid) if guid else "",
               datetime.datetime.now().strftime("%Y-%m-%d %H:%M")), "",
           "**Who spoke:** {0} members, {1} contributions{2}.".format(
               len(speaks), sum(s["count"] for s in speaks),
               "; opened by {0}".format(who(speaks_by_first(speaks)[0])) if speaks else ""), ""]
    for d in meta.get("divisions") or []:
        # the result is the debate's defining fact; the pack once read as a debate still going on
        out += ["**The House divided** (division {0}, {1}): {2} Ayes {3}, Noes {4}. {5}".format(
            d.get("number"), d.get("time"), d.get("question") or "", d.get("ayes"), d.get("noes"), d.get("result") or "").replace("  ", " "), ""]
    if mins:
        out += ["**The minister's line** ({0}): {1}".format(mins["attributed"], mins["text"][:700] + ("..." if len(mins["text"]) > 700 else "")), ""]
    out += ["## Speakers", "",
            "*Direction is the stance pass's first reading of the member's own words; the checklist is where a person confirms it.*", "",
            "| Member | Rose at | On their feet | Direction | What the pass read |", "|---|---|---|---|---|"]
    for s in speaks_by_first(speaks):
        conf = confirmed.get(key(s))
        mark = {"yes": " ✔ onside", "no": " ✘ not onside"}.get(conf, "")
        out.append("| [{0}]({1}) | {2} | {3} min | {4}{5} | {6} |".format(
            who(s), hansard_url(house, date, ext, s["ext_ids"][0] if s["ext_ids"] else None), _clock(s["first"]),
            max(1, round(s["seconds"] / 60)) if s["seconds"] else "?", label(s), mark, why(s).replace("|", "/")))
    out += ["", "*Nothing here is a verdict on a member until confirmed in checklist.md.*", ""]
    open(os.path.join(folder, "roundup.md"), "w", encoding="utf-8").write("\n".join(out))

    # checklist: never overwrite a human's answers, but ADD every speaker who
    # has arrived since it was written -- Hansard publishes in tranches, and a
    # checklist written on the first four speakers left eleven with nothing
    # to mark (2026-09-07).
    cpath = os.path.join(folder, "checklist.md")
    existing = open(cpath, encoding="utf-8").read() if os.path.exists(cpath) else None
    have = set(re.findall(r"^### speaker: (.+)$", existing or "", re.M))

    def entry(s):
        return ["### speaker: {0}".format(key(s)), "- {0}, rose {1}, {2} contribution(s), {3} words".format(
            who(s), _clock(s["first"]), s["count"], s["words"]),
            "- pass read: {0} — {1}".format(label(s), why(s)), "- opening words: {0}".format(s["text"][:220]),
            "ONSIDE: ", ""]
    if existing is None:
        c = ["# Onside check: {0} ({1})".format(title, date), "",
             "For each speaker, write ONSIDE: yes or ONSIDE: no. The stance pass's reading is shown as a first cut and is",
             "not the verdict. Only speakers marked yes are quoted in quotes.md and clipped by --download after --apply.",
             "Leave blank to decide later.", "", "Do not edit the `### speaker:` lines.", "", "---", ""]
        for s in speaks_by_first(speaks):
            c += entry(s)
        open(cpath, "w", encoding="utf-8").write("\n".join(c))
    else:
        added = [s for s in speaks_by_first(speaks) if key(s) not in have]
        if added:
            with open(cpath, "a", encoding="utf-8") as fh:
                fh.write("\n" + "\n".join(line for s in added for line in entry(s)))

    # quotes: confirmed speakers when any are confirmed; otherwise everyone the pass read as with us, marked unconfirmed
    q = ["# Quotes: {0} ({1})".format(title, date), ""]
    any_conf = any(v == "yes" for v in confirmed.values())
    q.append("*Whole sentences, on topic, linked to the paragraph in Hansard. {0}*".format(
        "Speakers confirmed onside in checklist.md." if any_conf else
        "UNCONFIRMED: speakers the stance pass read as with us; confirm in checklist.md and run --apply."))
    q.append("")
    for s in speaks_by_first(speaks):
        d = directions.get(key(s)) or {}
        take = confirmed.get(key(s)) == "yes" if any_conf else (d.get("stance") or 0) > 0
        if not take:
            continue
        found = quotes_for(s["text"], patterns)
        q += ["## {0}".format(who(s)), ""]
        if not found:
            q += ["*No passage clears the quote bar (whole sentences, on topic, 140–520 characters).*", ""]
        for text in found:
            q += ["> {0}".format(text), "", "— [Hansard]({0})".format(hansard_url(house, date, ext, s["ext_ids"][0] if s["ext_ids"] else None)), ""]
    open(os.path.join(folder, "quotes.md"), "w", encoding="utf-8").write("\n".join(q))

    # shot list
    with open(os.path.join(folder, "shotlist.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["speaker", "party", "seat", "direction", "onside_confirmed", "rose_at_london", "start_utc", "end_utc",
                    "seconds", "footage_link", "hansard_link"])
        for s in speaks_by_first(speaks):
            spans = s["spans"] or ([(s["first"], s["first"] + datetime.timedelta(minutes=3))] if s["first"] else [])
            for a, b in spans:
                w.writerow([s["name"], s["party"] or "", s["seat"] or "", label(s), confirmed.get(key(s), ""),
                            _clock(a), a.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                            b.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                            int((b - a).total_seconds()), offset_link(guid, a, event_start) if guid else "",
                            hansard_url(house, date, ext, s["ext_ids"][0] if s["ext_ids"] else None)])

    # speeches.md: every speaker's words in full, contribution by contribution,
    # with the pass's reading beside them. The check cannot be made on 220
    # characters of opening words (Christopher, 2026-09-07: "Do this for all
    # speakers to ensure data is correct" -- Jim Shannon read as against us on
    # a 53-word intervention while his speech said the opposite).
    sp = ["# Speeches in full: {0} ({1})".format(title, date), "",
          "*Each speaker's contributions as Hansard records them, with the stance pass's reading. Check the reading "
          "against the words, then mark ONSIDE in checklist.md.*", ""]
    for s in speaks_by_first(speaks):
        conf = confirmed.get(key(s))
        sp += ["## {0}".format(who(s)), "",
               "**Pass read:** {0}{1}{2}".format(label(s), " — " + why(s) if why(s) else "",
                                                  "  ·  **confirmed: {0}**".format(conf) if conf else ""), ""]
        for i, text in enumerate(s["texts"]):
            when = s["spans"][i][0] if i < len(s["spans"]) else s["first"]
            ext = s["ext_ids"][i] if i < len(s["ext_ids"]) else None
            sp += ["*{0}, {1} words · [Hansard]({2})*".format(_clock(when), len(text.split()),
                                                              hansard_url(house, date, ext_, ext)), "", text, ""]
    open(os.path.join(folder, "speeches.md"), "w", encoding="utf-8").write("\n".join(sp))

    readme = os.path.join(folder, "README.md")
    if not os.path.exists(readme):
        open(readme, "w", encoding="utf-8").write(
            "# Debate pack\n\nroundup.md, checklist.md (fill ONSIDE: yes/no), speeches.md (every word, for the check), quotes.md, shotlist.csv, clips/.\n\n"
            "Footage is Parliament's, licensed by the Parliamentary Recording Unit. Its terms restrict use in "
            "political campaigning and advertising: check them before a clip goes into anything public. "
            "The monitor records which speaker a person confirmed; the use of the footage is that person's decision.\n")
    return folder


def speaks_by_first(speaks):
    return sorted(speaks, key=lambda s: (s["first"] is None, s["first"] or datetime.datetime.max.replace(tzinfo=LONDON)))
