#!/usr/bin/env python3
"""The Congressional Record: floor speeches on our ground, by member and bill.

    python3 tools/us_record.py                          # unread days of the Congress, newest first
    python3 tools/us_record.py --since 2026-09-01       # only days from this date
    python3 tools/us_record.py --budget-seconds 600     # stop after ten minutes, resume next run
    python3 tools/us_record.py --dry-run                # list the days that would be read
    python3 tools/us_record.py --db /tmp/us.db --raw-dir /tmp/us-raw   # a scratch run
    python3 tools/us_record.py --reclassify             # re-derive areas, offline

PHASE 3a (9 October 2026); see docs/us-scope.md. The Hansard of Congress.

THE SOURCE is GovInfo's CREC collection: one PACKAGE per day of the Record
(both chambers and the Extensions of Remarks), split into GRANULES, one per
segment of the day (a bill's debate, a member's statement, a tribute, the
prayer). Three requests per kind of thing, all official:

  * api.govinfo.gov/published/<from>/<to>?collection=CREC -- the days
    issued, with GovInfo's lastModified. KEYED (api.data.gov; the key goes
    as an X-Api-Key header, never in a URL, a log or a gap row). One
    request lists a whole Congress (376 packages from 3 January 2025).
  * www.govinfo.gov/metadata/pkg/<package>/mods.xml -- the day's metadata,
    every granule at once: its heading, its class, the members speaking
    (Bioguide ID, party and state AT THE TIME, the label the Record prints
    for them: 'Mrs. MOODY') and every bill it cites, with GovInfo's own
    context (TITLE and HEADERLINE: the granule is ABOUT the bill;
    FIRSTPARAGRAPH and OTHER: it cites it). Keyless; 1 to 4 MB a day.
  * www.govinfo.gov/content/pkg/<package>/html/<granule>.htm -- one
    granule's text. Keyless. Read only for SPEECH granules (below).
Congress.gov's congressional-record endpoints were probed too: they index
the same issues by volume and number and point back to GovInfo's files.

NO KEY, NO RUN. A missing key is one [gap] line and the step skips: the
listing is the only way to know which days exist.

WHAT A SPEECH IS. A granule with a member speaking (a congMember in its
metadata), in the House, the Senate or the Extensions of Remarks, and not
procedure (SKIP_CLASSES: adjournment, orders for tomorrow, cloture
signatories, amendment texts, vote explanations, and the rest). Inside it a
TURN is a paragraph opening with a speaker label ('  Mr. WALBERG. Mr.
Speaker, ...') and the paragraphs after it up to the next label; the chair
('The SPEAKER pro tempore', 'The PRESIDING OFFICER') and the clerk's lines
('The Clerk read the title of the bill', the bill text that follows) end a
turn and are nobody's. A SPEECH is everything one member said in one
granule: speech_key '<granule>/<bioguide>'. A label is resolved against
the members the granule's own metadata names, exactly or by a unique
surname; one that resolves to nobody is stored with its label and no
Bioguide, never a guess, and counted per day (us_record_days.unresolved).

ONLY SPEECHES ON OUR GROUND ARE STORED, with an excerpt (the best-matching
passage, clipped) and a word count, never the text. Every speech granule's
bills are stored, ours or not (us_record_bills), so a bill line can say how
often the floor spoke to it.

THE RULE (classify_speech; the one place it lives):
  * `own_areas` is what the member's OWN WORDS matched, passage by passage
    (src/filter.match_passages: a passage counts only on a tier-1 term), with
    the granule's heading as a passage of its own (a debate's title match is
    real, as in every Hansard collector here). Never a bill's areas.
  * `areas` adds a bill's areas in exactly two cases, and `areas_from`
    says which:
      - 'watch': the granule is ABOUT a bill on config/watchlist-us.yaml
        (GovInfo context TITLE or HEADERLINE). By KEY, as everywhere in the US.
      - 'bill': the speech's own text is AMBIGUOUS -- it matched nothing --
        AND the granule is ABOUT a bill AND that bill's own TITLES (its
        display and official titles: not its CRS summary, nor the short
        title of an Act folded into it) are on our ground AND the member
        spoke at least
        MIN_WORDS words. A member arguing for H.R. 28 who never says
        "women's sports" is still speaking to it; one yielding two minutes
        is not a speech, and an appropriations bill (on our ground only by
        its summary's Hyde language) lends nothing, which is the lesson the
        roll calls taught (tools/us_rollcalls.py).
  * Otherwise `areas` is `own_areas`.

INCREMENTAL BY DATE. Every run lists the days since the Congress began
(the previous one too in a new Congress's first weeks), re-stamps what it
already holds, and reads, NEWEST FIRST, every day not yet read, every day
whose read left a gap, and any day of the last REREAD_DAYS that GovInfo
has modified since (the daily edition is revised into the bound one; older
revisions are left alone). Newest first means a budget-capped backfill
fills the weeks the edition needs before the old ones. A day stopped by the
budget is not marked read and is read again whole.

RAW ARCHIVE. The listing (it carries no key) and each day's metadata are
archived to the raw tree; a granule's page only when a speech in it is
stored. Every other granule's page is re-fetchable from its URL.

Separation guarantee: writes us_record_days, us_record_speeches,
us_record_bills, the shared gaps table and its own source_runs heartbeat.
ONE WRITER AT A TIME on the store.
"""

from __future__ import annotations

import argparse
import datetime
import html
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, drain, filter as filt, us_store  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402

FEED = "us-record"
HEARTBEAT = "US record"
TAXONOMY = os.path.join(ROOT, "config", "taxonomy.yaml")
LISTING = ("https://api.govinfo.gov/published/{0}/{1}?collection=CREC&pageSize=1000"
           "&offsetMark=%2A")
MODS = "https://www.govinfo.gov/metadata/pkg/{0}/mods.xml"
PAGE = "https://www.govinfo.gov/content/pkg/{0}/html/{1}.htm"
DETAILS = "https://www.govinfo.gov/app/details/{0}/{1}"
# The MODS namespace, in Clark notation: an identifier, never fetched.
MODS_NS = "{http://www.loc.gov/mods/v3}"
NS = {"m": MODS_NS[1:-1]}
BUDGET_S = 600.0
# GovInfo revises a day's Record for weeks (the daily edition into the bound
# one); a modified day this recent is read again.
REREAD_DAYS = 30
# Below this a turn is procedure ("I yield two minutes to the gentleman"),
# not a speech that can stand on its bill.
MIN_WORDS = 150
EXCERPT = 400
HIDDEN_AREAS = (11,)
SECTIONS = {"HOUSE": "house", "SENATE": "senate", "EXTENSIONS": "extensions"}
# Granule classes that carry a member's name but are procedure, not speech.
# Measured on 17 September 2026 (139 granules, 69 with a member named).
SKIP_CLASSES = frozenset({
    "ADJOURNMENT", "CALLTOORDER", "FRONTMATTER", "PRAYER", "PLEDGE", "HJOURNAL",
    "HDESIGNATION", "CASTATEMENT", "EXECUTIVECOMM", "HPUBBILLS", "HADDSPONSORS",
    "SAUTHORITY", "SORDERFOR", "SAMENDMENTTEXT", "SAMENDMENTTEXTIND", "SAMENDMENTSSUB",
    "SCLOTURE", "SCONSENTAGREE", "SCOSPONSORS", "SINTROBILLS", "SSUBMISSION", "SSTATEMENTS",
    "SREFERRED", "SDISCHARGED", "SREADFIRST", "SMSGHOUSE", "SMSGEXEC", "MSGPRESIDENT",
    "SEXECCAL", "SEXECREPORT", "SCOMMREPORT", "SCONFIRMATIONS", "SWITHDRAWAL",
    "SCONBUSINESS", "PERSONALEXPLAIN", "VOTEEXPLAIN"})
CONTEXT_RANK = {"TITLE": 0, "HEADERLINE": 1, "FIRSTPARAGRAPH": 2, "OTHER": 3}
ABOUT = ("TITLE", "HEADERLINE")


# --- the day's metadata --------------------------------------------------------

def _t(el, path):
    v = el.findtext(path, namespaces=NS) if el is not None else None
    return " ".join(v.split()) if v and v.strip() else None


def bill_key(congress, btype, number):
    try:
        return "{0}/{1}/{2}".format(int(congress), btype.lower(), int(number))
    except (TypeError, ValueError, AttributeError):
        return None


def parse_mods(raw):
    """A day's package MODS -> [granule dict], in the Record's order."""
    root = ET.fromstring(raw)
    out = []
    for ri in root.findall("m:relatedItem", NS):
        if ri.get("type") != "constituent":
            continue
        ext = ri.find("m:extension", NS)
        if ext is None:
            continue
        gid = _t(ext, "m:accessId")
        if not gid:
            continue
        members = []
        for cm in ext.findall("m:congMember", NS):
            parsed = None
            name = None
            for n in cm.findall("m:name", NS):
                if n.get("type") == "parsed":
                    parsed = " ".join((n.text or "").split()) or None
                elif n.get("type") == "authority-fnf":
                    name = " ".join((n.text or "").split()) or None
            members.append({"bioguide": cm.get("bioGuideId") or None, "parsed": parsed,
                            "name": name, "party": cm.get("party") or None,
                            "state": cm.get("state") or None,
                            "chamber": cm.get("chamber"), "role": cm.get("role")})
        bills = {}
        for b in ext.findall("m:bill", NS):
            key = bill_key(b.get("congress"), b.get("type"), b.get("number"))
            if not key:
                continue
            ctx = (b.get("context") or "OTHER").upper()
            if key not in bills or CONTEXT_RANK.get(ctx, 9) < CONTEXT_RANK.get(bills[key], 9):
                bills[key] = ctx
        cls = (_t(ext, "m:granuleClass") or "").upper()
        chamber = (_t(ext, "m:chamber") or "").lower() or (
            "house" if cls in ("HOUSE", "EXTENSIONS") else "senate" if cls == "SENATE" else None)
        out.append({
            "granule_id": gid,
            "title": _t(ri, "m:titleInfo/m:title"),
            "section": SECTIONS.get(cls),
            "granule_class": cls,
            "sub_class": (_t(ext, "m:subGranuleClass") or "").upper() or None,
            "chamber": chamber,
            "date": _t(ext, "m:granuleDate"),
            "citation": next((_t(i, ".") for i in ri.findall("m:identifier", NS)
                              if i.get("type") == "preferred citation"), None),
            "members": members,
            "bills": sorted(bills.items(), key=lambda kv: (CONTEXT_RANK.get(kv[1], 9), kv[0])),
        })
    return out


def speakers(granule):
    """Members SPEAKING in the granule (some metadata names others)."""
    return [m for m in granule["members"] if (m.get("role") or "SPEAKING").upper() == "SPEAKING"]


def is_speech_granule(g):
    return bool(g["section"]) and bool(speakers(g)) and g["sub_class"] not in SKIP_CLASSES


def subject_bill(g):
    """The bill the granule is ABOUT (title or headline), or None."""
    return next((k for k, ctx in g["bills"] if ctx in ABOUT), None)


# --- a granule's text into turns ---------------------------------------------

_SURNAME = r"[A-Z][a-z]?[A-Z][A-Za-z'\-\[\]]*"
LABEL = re.compile(r"^  ((?:Mr|Mrs|Ms|Miss|Dr)\. {0}(?: {0})*(?: of [A-Z][A-Za-z]+(?: [A-Z][A-Za-z]+)*)?)\. "
                   .format(_SURNAME))
# Lines that open a turn that is nobody's: the chair, the clerk, the
# Record's own notes, and a member named in a procedural line ("Mr. PADILLA
# (for himself and ...) submitted the following resolution").
NOT_SPEECH = re.compile(
    r"^  (?:The (?:Acting |ACTING )?(?:SPEAKER|PRESIDING OFFICER|PRESIDENT|VICE PRESIDENT|"
    r"CHAIR(?:MAN|WOMAN)?)\b"
    r"|The (?:Clerk|legislative clerk|bill clerk|assistant (?:legislative|bill) clerk|"
    r"Chair (?:recognizes|announces|lays|will))\b"
    r"|The text of the |The question (?:was|is) |The yeas and nays |A recorded vote|"
    r"The (?:motion|amendment|resolution|bill|joint resolution) (?:was|is) (?:agreed|passed|"
    r"rejected|laid|ordered)"
    r"|(?:By )?(?:Mr|Mrs|Ms|Miss|Dr)\. " + _SURNAME + r"[^.]*?(?: \(|:| submitted| introduced| "
    r"proposed| sent| asked))")
_PRE = re.compile(r"<pre>(.*?)</pre>", re.S | re.I)
_TAG = re.compile(r"<[^>]+>")


def page_text(raw):
    """The <pre> body of a granule page, entities decoded, tags dropped."""
    text = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else raw
    m = _PRE.search(text)
    return html.unescape(_TAG.sub("", m.group(1) if m else text))


def norm_label(label):
    return " ".join((label or "").split())


def parse_turns(text):
    """[(label or None, text)]: label None is the chair, the clerk, or a
    heading before the first speaker."""
    turns, label, buf = [], None, []
    for line in text.splitlines():
        m = LABEL.match(line)
        if m:
            turns.append((label, buf))
            label, buf = norm_label(m.group(1)), [line[m.end():]]
            continue
        if NOT_SPEECH.match(line):
            turns.append((label, buf))
            label, buf = None, [line]
            continue
        buf.append(line)
    turns.append((label, buf))
    out = []
    for lab, lines in turns:
        body = "\n".join(lines).strip()
        if body:
            out.append((lab, body))
    return out


def _surname(label):
    m = re.match(r"^(?:Mr|Mrs|Ms|Miss|Dr)\. (.+?)(?: of .+)?$", label or "")
    return m.group(1).upper() if m else None


def _match(want, members):
    exact = {m["bioguide"]: m for m in members if norm_label(m.get("parsed")) == want}
    if len(exact) == 1:
        return next(iter(exact.values()))
    sur = _surname(want)
    same = {m["bioguide"]: m for m in members if sur and _surname(m.get("parsed")) == sur}
    return next(iter(same.values())) if len(same) == 1 else None


def resolve(label, members, fallbacks=()):
    """The member a label names: from the granule's own metadata, exactly or
    by a unique surname; then from each fallback roster in turn (the day's
    other granules, then the store's members of the chamber). None when
    nobody, never a guess. Measured 16 September 2026: Mr. VAN EPPS spoke in
    five granules whose metadata did not name him."""
    want = norm_label(label)
    for roster in (members,) + tuple(fallbacks):
        m = _match(want, roster or [])
        if m:
            return m
    return None


class Roster:
    """The store's members of a chamber as a fallback roster, with the
    label the Record would print ('Mr. VAN EPPS'), surname only: the
    honorific is not stored, so it is matched by surname alone, uniquely."""

    def __init__(self, conn):
        self.conn, self.cache = conn, {}

    def chamber(self, chamber):
        if chamber not in self.cache:
            rows = []
            try:
                rows = self.conn.execute(
                    "SELECT bioguide, name, party, state FROM us_members WHERE chamber=? "
                    "AND name IS NOT NULL", (chamber,)).fetchall()
            except Exception:                                   # noqa: BLE001
                rows = []
            self.cache[chamber] = [
                {"bioguide": b, "name": n, "party": p, "state": st, "role": "SPEAKING",
                 # 'Matt Van Epps' -> 'Mr. VAN EPPS': only the surname is compared.
                 "parsed": "Mr. " + " ".join(n.split()[1:]).upper() if len(n.split()) > 1 else None}
                for (b, n, p, st) in rows]
        return self.cache[chamber]


def member_speeches(text, members, fallbacks=()):
    """{key: speech}: one per member who spoke in the granule. A granule
    with ONE member speaking and no label at all (a few Extensions and
    statements print none) is theirs whole."""
    turns = parse_turns(text)
    found, unresolved = {}, 0
    for label, body in turns:
        if not label:
            continue
        m = resolve(label, members, fallbacks)
        key = (m or {}).get("bioguide") or "label:" + label
        if not m:
            unresolved += 1
        s = found.setdefault(key, {"member": m, "label": label, "paras": []})
        s["paras"].append(re.sub(r"\s*\n\s*", " ", body))
    if not found and len(members) == 1:
        m = members[0]
        found[m["bioguide"] or "label:?"] = {"member": m, "label": m.get("parsed"),
                                             "paras": [re.sub(r"\s*\n\s*", " ", b)
                                                       for _l, b in turns]}
    for s in found.values():
        s["text"] = "\n".join(s["paras"])
        s["words"] = len(s["text"].split())
    return found, unresolved


# --- classification -------------------------------------------------------------

def empty_watchlist():
    return filt.Watchlist(entities=[], bill_titles=[], act_shorts=[])


def lead(text, n=EXCERPT):
    t = " ".join((text or "").split())
    return t if len(t) <= n else t[:n].rsplit(" ", 1)[0] + "..."


# A short title that names an Act ("Military Chaplains Modernization Act of
# 2026") may be a PORTION of an omnibus: BILLSTATUS lists the short titles of
# every Act folded into the NDAA, and on the 119th's backfill the FY2027
# NDAA lent "freedom of religion" to 31 speeches through that one. So a bill
# lends from its display title and its official titles ("To prohibit
# taxpayer funded abortions."), never from another Act's name.
_ACT_TITLE = re.compile(r"\bAct(?: of \d{4})?\.?$")


def lending_titles(title, short_titles):
    return [t for t in [title] + [x for x in short_titles or [] if not _ACT_TITLE.search(x.strip())]
            if t]


class BillTitles:
    """A bill's areas from its OWN TITLES alone (never the CRS summary, never
    an included Act's short title: lending_titles), cached."""

    def __init__(self, conn, tax, wl):
        self.conn, self.tax, self.wl, self.cache = conn, tax, wl, {}

    def areas(self, key):
        if key not in self.cache:
            row = self.conn.execute("SELECT title, short_titles FROM us_bills WHERE bill_key=?",
                                    (key,)).fetchone() if key else None
            areas = []
            if row:
                titles = lending_titles(row[0], json.loads(row[1] or "[]"))
                res = filt.filter_item(self.tax, self.wl, *titles)
                areas = sorted(set(res.issue_areas or []))
            self.cache[key] = areas
        return self.cache[key]


def classify_speech(tax, wl, title, text, words, subject, bill_titles, watch=None):
    """(own_areas, areas, areas_from, terms, tier, excerpt): the rule in the
    module docstring."""
    matches = filt.match_passages(tax, wl, text, title=title)
    own, terms, excerpt = filt.aggregate_passages(matches, max_excerpt=EXCERPT)
    if excerpt and title and " ".join(title.split()).startswith(excerpt.rstrip(".")[:40]):
        # The heading matched best; the takeaway should be the member's words.
        body = filt.match_passages(tax, wl, text)
        excerpt = filt.aggregate_passages(body, max_excerpt=EXCERPT)[2] or lead(text)
    tier = 1 if any(m.result.tier == 1 for m in matches) else (2 if matches else None)
    areas, source = set(own), "own" if own else None
    watched = (watch if watch is not None else us_store.watchlist()).get(subject) if subject else None
    if watched:
        areas |= set(watched[0])
        source = source or "watch"
        terms = list(terms) + ["watch:" + subject]
    elif not own and subject and words >= MIN_WORDS:
        lent = bill_titles(subject) if callable(bill_titles) else bill_titles.areas(subject)
        if [a for a in lent if a not in HIDDEN_AREAS]:
            areas |= set(lent)
            source = "bill"
            terms = list(terms) + ["bill:" + subject]
    if source in ("watch", "bill") and not excerpt:
        # The member's first substantive paragraph, not "I move to suspend
        # the rules and pass the bill".
        paras = [p for p in (text or "").split("\n") if len(p.split()) >= 40]
        excerpt = lead(paras[1] if len(paras) > 1 else (paras or [text])[0])
    return sorted(own), sorted(areas), source, terms, tier or (2 if areas else None), excerpt


def on_our_ground(areas):
    return any(a not in HIDDEN_AREAS for a in (areas or []))


# --- storing ----------------------------------------------------------------------

def store_speech(conn, pkg, g, key, s, cls, today):
    own, areas, source, terms, tier, excerpt = cls
    m = s["member"] or {}
    conn.execute(
        "INSERT INTO us_record_speeches (speech_key, granule_id, package_id, date, chamber, "
        "section, sub_class, title, citation, bioguide, speaker, name, party, state, words, "
        "bill_keys, subject_bill, own_areas, areas, areas_from, matched_terms, tier, excerpt, "
        "url, first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(speech_key) DO UPDATE SET date=excluded.date, chamber=excluded.chamber, "
        "section=excluded.section, sub_class=excluded.sub_class, title=excluded.title, "
        "citation=excluded.citation, bioguide=excluded.bioguide, speaker=excluded.speaker, "
        "name=excluded.name, party=excluded.party, state=excluded.state, words=excluded.words, "
        "bill_keys=excluded.bill_keys, subject_bill=excluded.subject_bill, "
        "own_areas=excluded.own_areas, areas=excluded.areas, areas_from=excluded.areas_from, "
        "matched_terms=excluded.matched_terms, tier=excluded.tier, excerpt=excluded.excerpt, "
        "url=excluded.url, last_seen=excluded.last_seen",
        ("{0}/{1}".format(g["granule_id"], m.get("bioguide") or key), g["granule_id"],
         pkg["packageId"], g["date"] or pkg["dateIssued"], g["chamber"] or "house",
         g["section"], g["sub_class"], g["title"], g["citation"], m.get("bioguide"),
         s["label"], m.get("name"), m.get("party"), m.get("state"), s["words"],
         us_store.dumps([k for k, _c in g["bills"]]), subject_bill(g),
         us_store.dumps(own), us_store.dumps(areas), source, us_store.dumps(terms), tier,
         excerpt, DETAILS.format(pkg["packageId"], g["granule_id"]), today, today))


def store_bills(conn, pkg, g):
    n = len(speakers(g))
    for key, ctx in g["bills"]:
        conn.execute("INSERT OR REPLACE INTO us_record_bills (granule_id, bill_key, context, "
                     "date, chamber, speakers) VALUES (?,?,?,?,?,?)",
                     (g["granule_id"], key, ctx, g["date"] or pkg["dateIssued"], g["chamber"], n))


def store_day(conn, pkg, totals, status, note, today):
    conn.execute(
        "INSERT INTO us_record_days (package_id, date, congress, last_modified, granules, "
        "speech_granules, speeches, ours, unresolved, status, note, read_at, first_seen, last_seen) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(package_id) DO UPDATE SET "
        "date=excluded.date, congress=excluded.congress, last_modified=excluded.last_modified, "
        "granules=excluded.granules, speech_granules=excluded.speech_granules, "
        "speeches=excluded.speeches, ours=excluded.ours, unresolved=excluded.unresolved, "
        "status=excluded.status, note=excluded.note, read_at=excluded.read_at, "
        "last_seen=excluded.last_seen",
        (pkg["packageId"], pkg["dateIssued"], _int(pkg.get("congress")), pkg.get("lastModified"),
         totals["granules"], totals["speech_granules"], totals["speeches"], totals["ours"],
         totals["unresolved"], status, note, today, today, today))


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


STOPPED = object()
# Pages fetched at once. GovInfo's pages answer in 0.4 to 4 seconds each
# (measured 9 October 2026), so one at a time a day of 60 speech granules
# took two minutes. HttpClient caps a host at four in flight and keeps its
# 0.2 s spacing between request starts, so this is polite by construction.
WORKERS = 4


def fetch_pages(client, pid, granules, budget=None):
    """Yield (granule, page bytes | FetchError | STOPPED) in the Record's
    order, WORKERS at a time; STOPPED once the budget runs out."""
    from concurrent.futures import ThreadPoolExecutor

    def one(g):
        try:
            return client.get_bytes(PAGE.format(pid, g["granule_id"]), FEED,
                                    "page-" + g["granule_id"], archive=False)
        except FetchError as exc:
            return exc

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        for i in range(0, len(granules), WORKERS * 2):
            if budget is not None and budget.exhausted():
                yield None, STOPPED
                return
            batch = granules[i:i + WORKERS * 2]
            for g, page in zip(batch, pool.map(one, batch)):
                yield g, page


def read_day(conn, client, pkg, tax, wl, today, bill_titles, budget=None, log=print, watch=None,
             roster=None):
    """Read one day. Returns its totals, or None when the budget stopped it
    part-way (nothing marked read; the next run reads it again whole)."""
    pid = pkg["packageId"]
    totals = {"granules": 0, "speech_granules": 0, "speeches": 0, "ours": 0, "unresolved": 0,
              "fetched": 0, "gaps": 0}
    try:
        raw = client.get_bytes(MODS.format(pid), FEED, "mods-" + pid)
        granules = parse_mods(raw)
    except (FetchError, ET.ParseError) as exc:
        db.record_gap(conn, FEED, "{0} metadata: {1}".format(pid, str(exc)[:160]), today)
        store_day(conn, pkg, totals, "gap", "metadata not read", today)
        conn.commit()
        totals["gaps"] = 1
        return totals
    totals["granules"] = len(granules)
    kept, problems = set(), []
    wanted = [g for g in granules if is_speech_granule(g)]
    day_roster = {}
    for g in granules:
        for m in speakers(g):
            if m.get("bioguide"):
                day_roster.setdefault(g["chamber"], {})[m["bioguide"]] = m
    roster = roster if roster is not None else Roster(conn)
    for g, page in fetch_pages(client, pid, wanted, budget):
        if page is STOPPED:
            conn.commit()
            return None
        totals["speech_granules"] += 1
        store_bills(conn, pkg, g)
        if isinstance(page, FetchError):
            problems.append("{0}: {1}".format(g["granule_id"], str(page.cause)[:80]))
            continue
        totals["fetched"] += 1
        found, unresolved = member_speeches(
            page_text(page), speakers(g),
            (list(day_roster.get(g["chamber"], {}).values()), roster.chamber(g["chamber"])))
        totals["speeches"] += len(found)
        totals["unresolved"] += unresolved
        subject = subject_bill(g)
        archived = False
        for key, s in found.items():
            cls = classify_speech(tax, wl, g["title"], s["text"], s["words"], subject,
                                  bill_titles, watch=watch)
            if not on_our_ground(cls[1]):
                continue
            store_speech(conn, pkg, g, key, s, cls, today)
            kept.add("{0}/{1}".format(g["granule_id"], (s["member"] or {}).get("bioguide") or key))
            totals["ours"] += 1
            if not archived:
                client.archive(page, FEED, "page-" + g["granule_id"])
                archived = True
    # A speech stored by an earlier read that this read no longer finds on
    # our ground (a taxonomy change, a corrected page) goes.
    for (sk,) in conn.execute("SELECT speech_key FROM us_record_speeches WHERE package_id=?",
                              (pid,)).fetchall():
        if sk not in kept:
            conn.execute("DELETE FROM us_record_speeches WHERE speech_key=?", (sk,))
    for p in problems:
        db.record_gap(conn, FEED, "{0} page {1}".format(pid, p), today)
    totals["gaps"] = len(problems)
    store_day(conn, pkg, totals, "gap" if problems else "read",
              "{0} page(s) not read".format(len(problems)) if problems else None, today)
    conn.commit()
    return totals


# --- which days ---------------------------------------------------------------------

def congress_key():
    from src import publish
    return us_store.clean_key(publish.load_secrets().get("congress_api_key"))


def first_date(today):
    """The first day of the Congress, or of the previous one while it is
    still being caught up (us_store.catch_up_congress)."""
    congress = us_store.catch_up_congress(today) or us_store.congress_on(today)
    return us_store.congress_start(congress).isoformat()


def list_days(client, key, since, until):
    """Every CREC package issued in [since, until]. Raises FetchError.
    GovInfo's end date is EXCLUSIVE (measured: 17 to 18 September lists the
    17th alone), so the day after `until` is asked for."""
    end = (datetime.date.fromisoformat(until) + datetime.timedelta(days=1)).isoformat()
    url, out, page = LISTING.format(since, end), [], 0
    while url:
        page += 1
        raw = client.get_bytes(url, FEED, "listing", headers={"X-Api-Key": key})
        # The reply carries no key (it went as a header), so it is archived.
        client.archive(raw, FEED, "listing-{0}-{1}-p{2}".format(since, until, page))
        data = json.loads(raw.decode("utf-8"))
        out += [p for p in data.get("packages") or [] if p.get("packageId")]
        url = data.get("nextPage")
    return out


def due(conn, packages, today, congresses):
    """The days to read, newest first, and the number already held."""
    held = {r[0]: (r[1], r[2]) for r in conn.execute(
        "SELECT package_id, status, last_modified FROM us_record_days")}
    recent = (datetime.date.fromisoformat(today) - datetime.timedelta(days=REREAD_DAYS)).isoformat()
    todo, have = [], 0
    for p in packages:
        if congresses and _int(p.get("congress")) not in congresses:
            continue
        got = held.get(p["packageId"])
        if got is None or got[0] != "read":
            todo.append(p)
        elif (p.get("lastModified") or "") > (got[1] or "") and p["dateIssued"] >= recent:
            todo.append(p)
        else:
            have += 1
    todo.sort(key=lambda p: (p["dateIssued"], p["packageId"]), reverse=True)
    return todo, have


def restamp(conn, packages, today):
    for p in packages:
        conn.execute("UPDATE us_record_days SET last_seen=? WHERE package_id=?",
                     (today, p["packageId"]))
    conn.commit()


def stamp(conn, today):
    conn.execute("INSERT OR REPLACE INTO source_runs (source, last_run, run_id, note) "
                 "VALUES (?,?,?,?)", (HEARTBEAT, today, os.environ.get("GITHUB_RUN_ID"),
                                      "step heartbeat: tools/us_record.py"))
    conn.commit()


def pull(conn, client, today, key, since=None, until=None, tax=None, budget=None,
         limit=None, log=print, dry_run=False):
    """Returns (days read, speeches on our ground, gaps)."""
    us_store.ensure_schema(conn)
    tax = tax if tax is not None else filt.load_taxonomy(TAXONOMY)
    wl = empty_watchlist()
    since = since or first_date(today)
    until = until or today
    try:
        packages = list_days(client, key, since, until)
    except (FetchError, ValueError) as exc:
        # str(exc) carries the URL, never the key (a header).
        db.record_gap(conn, FEED, "listing {0} to {1}: {2}".format(since, until, exc), today)
        return 0, 0, 1
    congresses = {c for c in (us_store.congress_on(today), us_store.catch_up_congress(today)) if c}
    if since < first_date(today):
        congresses = set()          # an explicit earlier --since reads what it asks for
    todo, have = due(conn, packages, today, congresses)
    log("us-record: {0} day(s) listed from {1} to {2}; {3} held, {4} to read".format(
        len(packages), since, until, have, len(todo)))
    if dry_run:
        for p in todo[:10]:
            log("  would read {0} ({1})".format(p["packageId"], p.get("lastModified")))
        return 0, 0, 0
    restamp(conn, packages, today)
    titles = BillTitles(conn, tax, wl)
    roster = Roster(conn)
    days = ours = gaps = fetched = 0
    for p in todo:
        if limit is not None and days >= limit:
            log("  day cap ({0}) reached; the rest are read on later runs -- disclosed, "
                "not silent".format(limit))
            break
        if budget is not None and budget.exhausted():
            log(budget.disclose("Record days", days))
            break
        t = read_day(conn, client, p, tax, wl, today, titles, budget=budget, log=log,
                     roster=roster)
        if t is None:
            log(budget.disclose("Record days", days) + " ({0} stopped part-way; read again "
                                                     "next run)".format(p["packageId"]))
            break
        days += 1
        ours += t["ours"]
        gaps += t["gaps"]
        fetched += t["fetched"]
    log("us-record: {0} day(s) read, {1} granule page(s) fetched, {2} speech(es) on our "
        "ground, {3} gap(s); {4} day(s) still to read".format(
            days, fetched, ours, gaps, max(0, len(todo) - days)))
    if client.last_headers.get("x-ratelimit-remaining"):
        log("  api.data.gov: {0} of {1} requests left this hour".format(
            client.last_headers.get("x-ratelimit-remaining"),
            client.last_headers.get("x-ratelimit-limit")))
    return days, ours, gaps


# --- offline -------------------------------------------------------------------------

def reclassify(conn, log=print):
    """Re-apply the bill rule to stored speeches after a taxonomy or
    watchlist change. Offline, so it cannot see the text: own_areas stay
    as read; a speech's lent areas are re-derived. A speech that newly
    matches needs its day read again (delete its us_record_days row)."""
    tax = filt.load_taxonomy(TAXONOMY)
    wl = empty_watchlist()
    titles = BillTitles(conn, tax, wl)
    watch = us_store.watchlist()
    changed = dropped = 0
    for (sk, own, words, subject, areas) in conn.execute(
            "SELECT speech_key, own_areas, words, subject_bill, areas FROM us_record_speeches"
    ).fetchall():
        own = json.loads(own or "[]")
        new, source = set(own), "own" if own else None
        if subject and watch.get(subject):
            new |= set(watch[subject][0])
            source = source or "watch"
        elif not own and subject and (words or 0) >= MIN_WORDS:
            lent = titles.areas(subject)
            if [a for a in lent if a not in HIDDEN_AREAS]:
                new |= set(lent)
                source = "bill"
        value = us_store.dumps(sorted(new))
        changed += value != (areas or "[]")
        if not on_our_ground(new):
            # Only speeches on our ground are stored: one that was there only
            # on a lent area no longer lent goes.
            conn.execute("DELETE FROM us_record_speeches WHERE speech_key=?", (sk,))
            dropped += 1
            continue
        conn.execute("UPDATE us_record_speeches SET areas=?, areas_from=? WHERE speech_key=?",
                     (value, source, sk))
    conn.commit()
    log("us-record: reclassified; {0} speech(es) changed area, {1} left our ground and "
        "were dropped".format(changed, dropped))
    return changed


def summary(conn, log=print):
    n = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
    log("  store: {0} day(s) of the Record read ({1} to {2}), {3} speech granule(s), {4} "
        "member speech(es), {5} on our ground stored ({6} by {7} member(s)); {8} label(s) "
        "unresolved".format(
            n("SELECT COUNT(*) FROM us_record_days WHERE status='read'"),
            n("SELECT MIN(date) FROM us_record_days"), n("SELECT MAX(date) FROM us_record_days"),
            n("SELECT COALESCE(SUM(speech_granules),0) FROM us_record_days"),
            n("SELECT COALESCE(SUM(speeches),0) FROM us_record_days"),
            n("SELECT COUNT(*) FROM us_record_speeches"),
            n("SELECT COUNT(*) FROM us_record_speeches WHERE bioguide IS NOT NULL"),
            n("SELECT COUNT(DISTINCT bioguide) FROM us_record_speeches"),
            n("SELECT COALESCE(SUM(unresolved),0) FROM us_record_days")))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--raw-dir", help="archive raw payloads here instead of data/raw "
                                      "(scratch runs)")
    ap.add_argument("--since", help="ISO date; default: the first day of the Congress")
    ap.add_argument("--until", help="ISO date; default: today")
    ap.add_argument("--budget-seconds", type=float, default=BUDGET_S)
    ap.add_argument("--limit", type=int, help="read at most this many days")
    ap.add_argument("--dry-run", action="store_true", help="list the days due, read nothing")
    ap.add_argument("--reclassify", action="store_true",
                    help="re-derive lent areas for stored speeches, offline")
    args = ap.parse_args()
    today = datetime.date.today().isoformat()
    conn = db.init_db(db.connect(args.db))
    if args.reclassify:
        reclassify(conn)
        conn.close()
        return 0
    key = congress_key()
    if not key:
        db.record_gap(conn, FEED, "no congress_api_key: the Congressional Record step "
                                  "skipped (GovInfo's listing is keyed)", today)
        conn.close()
        return 1
    client = HttpClient(raw_dir=args.raw_dir or os.path.join(ROOT, "data", "raw"))
    _days, _ours, gaps = pull(conn, client, today, key, since=args.since, until=args.until,
                              budget=drain.Budget(args.budget_seconds), limit=args.limit,
                              dry_run=args.dry_run)
    if not args.dry_run:
        summary(conn)
        if not gaps:
            stamp(conn, today)
    conn.close()
    return 1 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
