"""Read the clause a division title only numbers, and match on THAT.

The division sweep matches division TITLES against the taxonomy. A report-stage
or committee vote is titled "Health Bill: Report Stage: New Clause 142", which
carries no term, so the 8 September 2026 puberty blockers vote (division 2421,
NC142) and the single-sex NHS facilities vote (2422, NC143) were invisible to
it and found only by chance, from a passing reference at Women and Equalities
questions (see the comment above `id: gender-medicine` in
config/vote_tracker.yaml). The Crime and Policing Bill's New Clause 1 --
abortion decriminalisation -- had the same shape.

So when a title names a new clause, new schedule or amendment of a Bill, this
reads that clause from the official Bills API (bills-api.parliament.uk, keyless,
no robots.txt): the Bill by its short title, the stage of the right House that
SAT ON THE DIVISION DATE, the amendment whose marshalled-list number matches
(NC142, NS3, 36), then the detail call for the amendment lines and the member's
explanatory statement. The caller runs the taxonomy over that text; a match is
recorded with its source, "clause text", so a reviewer can see why a vote with
a bare title was flagged.

Fail loud. A title that names a clause we cannot read is NOT "no match": it is
reported "could not read clause text (<reason>)" so the gap is visible in the
edition's gaps and the review queue. Known unreadable shapes, said so up front
rather than discovered by wasted calls:

  Clause N stand part the Bills API carries amendments, not the Bill's own
                      clauses.

LORDS AMENDMENT N (Commons ping-pong) is read a different way. Its number
follows the consolidated "Lords amendments" paper, which is published only on
publications.parliament.uk -- behind a Cloudflare challenge, measured 13
October 2026, and not fetched -- and is NOT in the Bills API: the Commons
"Consideration of Lords amendments" stage and every later "Consideration of
Lords message" / "Consideration of Commons amendments" stage list zero
amendments (Crime and Policing Bill, stages 20642 to 20699; Pension Schemes
Bill, 20643 and 20663). The Lords' own marshalled numbers differ, so guessing a
mapping would read the WRONG clause, which is worse than reading none.

So the Commons' own debate is read instead, from the Hansard API
(hansard-api.parliament.uk, keyless, no robots.txt -- it answers 404 -- unlike
hansard.parliament.uk, which is Cloudflare-challenged and not fetched):

  1. the division is found in Hansard's division search for its day (and the
     next: a late sitting's divisions are filed under the following date) by
     its number or its Aye/No counts, which also resolves a misspelt title
     ("Pensions Scheme Bill"); that row names its debate section. Hansard
     sometimes files the divisions of a sitting in a separate "Unpublished
     Divisions: <Bill> (<date>)" section; both it and the Bill's own debate
     that day are read.
  2. in those sections, the clerk prints, before each motion on a Lords
     amendment, the heading of the clause it amends or inserts ("After Clause
     117" / "Review of public service pension schemes"), and members describe
     the amendments by number in the debate ("Lords amendment 77 would
     require the Government to publish a full review ..."). The heading and
     every non-procedural sentence naming the amendment are its text.
  3. second route: where the heading names a NEW clause, the Lords' own stages
     in the Bills API (committee, report, third reading) are searched for the
     one AGREED amendment inserting a clause of exactly that title; its full
     text and explanatory statement are added (Lords report amendment 157 is
     Lords Amendment 77 above). Only a unique title match is used: a heading
     naming an existing clause ("Clause 40") cannot say WHICH of the Lords'
     amendments to it this is, and is not guessed.

These are recorded with match source "Hansard (Lords amendment)". A
member's sentence is commentary, not the amendment, so the ledger gate reads
only the heading or the Lords' own explanatory statement for these.

Lords divisions name only the Bill; the amendment is in the motion notes
("Lord German moved amendment 73, after clause 48, ..."), which the Lords'
own marshalled numbering matches, so the same lookup serves them.

Cached twice: in memory per run (a Bill's search, stages and amendment list are
fetched once however many of its divisions a week holds), and in the store
(`clause_text`, one row per division read successfully) so a division is never
re-read. Failures are not cached: the next run tries again.
"""

from __future__ import annotations

import datetime
import json
import re
from dataclasses import dataclass, field
from urllib.parse import quote

from src.ingest import amendments as amd

API = amd.API
MAX_REFS = 12          # a title listing more than this is a ping-pong omnibus
MAX_RANGE = 25         # "Amendments 3 to 9" expands; a 3-to-300 range does not
SOURCE = "clause text"
HANSARD = "https://hansard-api.parliament.uk"
HANSARD_PUBLIC = "https://hansard.parliament.uk/Commons/{date}/debates/{ext}/{slug}"
HANSARD_SOURCE = "Hansard (Lords amendment)"
HANSARD_STAGE = "Commons consideration of Lords amendments (Hansard)"
MAX_SENTENCES = 40     # per amendment: a long group debate names some amendments often

LORDS_PAPER = ("Lords amendment numbers follow the Lords amendments paper, published "
               "only on publications.parliament.uk (Cloudflare challenge, not fetched) "
               "and not in the Bills API")
STAND_PART = "the Bills API carries amendments, not the Bill's own clauses"

_BILL = re.compile(r"^(?P<bill>.+?\bBill\b(?:\s*\[(?:Lords|HL)\])?)", re.I)
_NUM = r"\d+[A-Z]{0,2}"
_LIST = re.compile(r"\s*(?:,|\band\b)?\s*({0})(?:\s+to\s+({0}))?".format(_NUM))


@dataclass
class Ref:
    kind: str        # new_clause | new_schedule | amendment | lords_amendment | stand_part
    number: str      # "142", "35A"

    @property
    def marshalled(self):
        """The Bills API's marshalledListText for this reference."""
        return {"new_clause": "NC", "new_schedule": "NS"}.get(self.kind, "") + self.number

    @property
    def label(self):
        return {"new_clause": "New Clause {0}", "new_schedule": "New Schedule {0}",
                "amendment": "Amendment {0}", "lords_amendment": "Lords Amendment {0}",
                "stand_part": "Clause {0} stand part"}[self.kind].format(self.number)


@dataclass
class Lookup:
    status: str                      # none | ok | unreadable
    bill: str = None
    refs: list = field(default_factory=list)
    bill_id: int = None
    stage: str = None
    stage_id: int = None
    clauses: list = field(default_factory=list)   # [{label, amendment_id, url, decision, explanatory, text}]
    reason: str = None
    cached: bool = False

    @property
    def gap(self):
        """The fail-loud line: unreadable, or read only in part."""
        if self.status == "none" or not self.reason:
            return None
        return "could not read clause text ({0})".format(self.reason)


# -- parsing ------------------------------------------------------------------

def _numbers(text, start):
    """Numbers listed from `start`: "4, 6 and 9", "3 to 7", "4B and 4C"."""
    out, pos = [], start
    while True:
        m = _LIST.match(text, pos)
        if not m or not m.group(1):
            return out
        lo, hi = m.group(1), m.group(2)
        if hi and lo.isdigit() and hi.isdigit() and 0 < int(hi) - int(lo) <= MAX_RANGE:
            out.extend(str(n) for n in range(int(lo), int(hi) + 1))
        else:
            out.extend(x for x in (lo, hi) if x)
        pos = m.end()


def bill_name(title):
    """The Bill a division title names, or None (SIs, opposition days, motions)."""
    m = _BILL.match(" ".join((title or "").split()))
    return m.group("bill").strip() if m else None


def parse_refs(title, house="Commons", notes=None):
    """(bill, [Ref]) for the clauses a division is about; (None, []) when none.

    Commons titles carry the reference after the Bill ("Health Bill: Report
    Stage: New Clause 142"); Lords titles are the bare Bill, and the motion
    notes carry it ("moved amendment 73"). Reasoned amendments to second
    reading, a King's Speech "amendment (p)" and Commons amendments "in lieu"
    lettered (a) to (j) are not clause references and yield nothing.
    """
    title = " ".join((title or "").split())
    bill = bill_name(title)
    if not bill:
        return None, []
    refs = []
    if (house or "").lower() == "lords":
        text = " ".join((notes or "").split())
        if re.search(r"\bmoved\s+Motion\b", text, re.I):
            return bill, []              # ping-pong motion: no marshalled number to read
        for m in re.finditer(r"\bmoved\s+amendments?\s+", text, re.I):
            refs.extend(Ref("amendment", n) for n in _numbers(text, m.end()))
    else:
        rest = title[len(bill):]
        for m in re.finditer(r"\bNew Clauses?\s+", rest, re.I):
            refs.extend(Ref("new_clause", n) for n in _numbers(rest, m.end()))
        for m in re.finditer(r"\bNew Schedules?\s+", rest, re.I):
            refs.extend(Ref("new_schedule", n) for n in _numbers(rest, m.end()))
        for m in re.finditer(r"\bLords Amendments?\s+", rest, re.I):
            refs.extend(Ref("lords_amendment", n) for n in _numbers(rest, m.end()))
        for m in re.finditer(r"\bClause\s+(\d+)\s+stand part", rest, re.I):
            refs.append(Ref("stand_part", m.group(1)))
        # The House's own amendments: only at a committee or report stage, and
        # never in ping-pong, where "insist on Amendments 4A" names Commons
        # amendments to Lords amendments that the Bills API does not list.
        if not re.search(r"\bLords\b|\binsist\b|\bin lieu\b", rest, re.I):
            for m in re.finditer(r"(?<!Reasoned )(?<!New )\bAmendments?\s+(?=\d)", rest, re.I):
                refs.extend(Ref("amendment", n) for n in _numbers(rest, m.end()))
    seen, out = set(), []
    for r in refs:
        if (r.kind, r.number) not in seen:
            seen.add((r.kind, r.number))
            out.append(r)
    return bill, out


def base_name(title):
    """Comparable Bill name: 'Health Bill' == 'Health Act 2026' == 'Health Bill [HL]'.

    The Bills API keeps a Bill's record after Royal Assent under the Act's
    name (the Crime and Policing Bill is now "Crime and Policing Act 2026")."""
    t = (title or "").replace("’", "'").lower()
    t = re.sub(r"\[(lords|hl)\]", " ", t)
    # "(No. 2)", "(No.2)": the Commons title carries it, the API's short title
    # and the Act do not ("Finance Act 2026"); the sitting date tells them apart.
    t = re.sub(r"\(no\.?\s*\d+\)", " ", t)
    t = re.sub(r"\b(bill|act(\s+\d{4})?(\s+ch\s+\d+)?)\s*$", " ", t.strip())
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", t).split())


def _norm_marshalled(text):
    return re.sub(r"^amendment\s*", "", (text or "").strip().lower()).replace(" ", "").upper()


def _iso(value):
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()[:10]
    return (value or "")[:10]


# -- Hansard: the Commons debate on Lords amendments -------------------------

_ITEM = re.compile(r"\s*(?:,|\band\b|\bor\b)?\s*({0})\b(?:\s+to\s+({0})\b)?".format(_NUM))
_AMDT = re.compile(r"\bamendments?\s+(?=\d)", re.I)
# The clerk's and the Chair's words around a question: they name the number but
# say nothing about what the amendment does. A motion still locates the heading.
_MOTION = re.compile(r"That (?:this|the) House|beg to move|Question put|Motion made", re.I)
_PROCEDURAL = re.compile(_MOTION.pattern + r"|\b(?:dis)?agreed to\b|convenient to discuss|"
                         r"financial privilege|Commons disagreement|"
                         r"\bmotions? to (?:dis)?agree\b|\bGovernment motions?\b", re.I)
_FIRST = re.compile(r"\bLords(?:\s+in\s+their)?\s+amendments?\s+({0})".format(_NUM), re.I)
_SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z“\"'(])")
_UNPUBLISHED = re.compile(r"^\s*Unpublished Divisions:\s*(?P<bill>.+?)\s*\((?P<date>\d{1,2} \w+ \d{4})\)\s*$", re.I)
_NEW_CLAUSE = re.compile(r"insert the following new (?:Clause|Schedule)\W*(?P<title>.+)$", re.I)


def _htext(item):
    """An item's text. Tags are removed WITHOUT a space: Hansard splits a number
    across them ("<em>Lords amendment 7</em><em>8</em>" is amendment 78)."""
    text = re.sub(r"<[^>]+>", "", item.get("Value") or "").replace(" ", " ")
    text = re.sub(r"\bamendment s\b", "amendments", text)
    return "\n".join(" ".join(p.split()) for p in text.splitlines() if p.strip())


def _within(number, lo, hi):
    if hi is None:
        return number == lo
    if number.isdigit() and lo.isdigit() and hi.isdigit():
        return int(lo) <= int(number) <= int(hi)
    a, b, n = (re.match(r"(\d+)([A-Z]*)$", x) for x in (lo, hi, number))
    if a and b and n and a.group(1) == b.group(1) == n.group(1):
        return a.group(2) <= n.group(2) <= b.group(2)          # "38V to 38X"
    return number in (lo, hi)


def mentions(sentence, number):
    """Does this sentence name amendment `number`, alone, in a list or in a range?"""
    for m in _AMDT.finditer(sentence):
        pos = m.end()
        while True:
            it = _ITEM.match(sentence, pos)
            if not it:
                break
            if _within(number, it.group(1), it.group(2)):
                return True
            pos = it.end()
    return False


def _norm_title(text):
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", (text or "").replace("’", "'").lower()).split())


def new_clause_title(summary):
    """The title of the clause an amendment inserts, or None."""
    m = _NEW_CLAUSE.search(summary or "")
    return _norm_title(m.group("title")) if m else None


def _heading_before(entries, idx):
    """The clause heading the clerk printed just above item `idx`, or []."""
    out, section = [], entries[idx][0].get("ExtId")
    for ov, it in reversed(entries[:idx]):
        if ov.get("ExtId") != section:
            break
        tag = it.get("HRSTag") or ""
        if it.get("ItemType") == "Timestamp" or tag == "hs_ColumnNumber" or not _htext(it):
            continue
        if tag.startswith(("hs_8", "hs_7")):
            out.insert(0, _htext(it))
            continue
        break
    return out


def describe_lords_amendment(entries, number):
    """(heading lines, sentences, section overview) for Lords amendment `number`.

    entries is [(section overview, item)] in debate order."""
    heading, sentences, where, seen = None, [], None, set()
    for idx, (ov, it) in enumerate(entries):
        if it.get("ItemType") != "Contribution":
            continue
        for para in _htext(it).split("\n"):
            for sent in _SENT.split(para):
                if not mentions(sent, number):
                    continue
                if _PROCEDURAL.search(sent):
                    # The heading above a motion is the clause of the FIRST
                    # amendment it names; a motion on "Lords amendments 15 to
                    # 24, ... and 88" sits under Clause 40, which 88 is not in.
                    first = _FIRST.search(sent)
                    if heading is None and _MOTION.search(sent) and first and first.group(1) == number:
                        heading = _heading_before(entries, idx)
                        where = where or ov
                    continue
                if sent not in seen and len(sentences) < MAX_SENTENCES:
                    seen.add(sent)
                    sentences.append(sent)
                    where = where or ov
    return heading or [], sentences, where


def _hansard_url(ov):
    return HANSARD_PUBLIC.format(date=_iso(ov.get("Date")), ext=ov.get("ExtId"),
                                 slug=re.sub(r"[^A-Za-z0-9]", "", ov.get("Title") or ""))


def _similar(a, b):
    """Same Bill, allowing a misspelt title ("Pensions Scheme Bill")."""
    import difflib
    a, b = base_name(a), base_name(b)
    return a == b or difflib.SequenceMatcher(None, a, b).ratio() >= 0.85


def _section_bill(section):
    """(Bill name, date or None) a Hansard division row's debate section names."""
    m = _UNPUBLISHED.match(section or "")
    if m:
        try:
            when = datetime.datetime.strptime(m.group("date"), "%d %B %Y").date().isoformat()
        except ValueError:
            when = None
        return m.group("bill"), when
    return (section or "").strip(), None


# -- the reader ---------------------------------------------------------------

class ClauseReader:
    """Looks up division clause text through the Bills API, with both caches."""

    def __init__(self, client, conn=None):
        self.client = client
        self.conn = conn
        self._search, self._stages, self._amendments = {}, {}, {}
        self._hdays, self._hdebates = {}, {}

    # store cache -----------------------------------------------------------
    def _cached(self, key):
        if self.conn is None or not key:
            return None
        try:
            row = self.conn.execute(
                "SELECT bill, bill_id, stage, stage_id, refs, clauses FROM clause_text "
                "WHERE division_key = ?", (key,)).fetchone()
        except Exception:                                   # noqa: BLE001 - pre-migration store
            return None
        if not row:
            return None
        return Lookup("ok", bill=row[0], bill_id=row[1], stage=row[2], stage_id=row[3],
                      refs=[Ref(**r) for r in json.loads(row[4] or "[]")],
                      clauses=json.loads(row[5] or "[]"), cached=True)

    def _store(self, key, lk):
        if self.conn is None or not key or lk.status != "ok":
            return
        try:
            self.conn.execute(
                "INSERT OR REPLACE INTO clause_text (division_key, bill, bill_id, stage, stage_id, "
                "refs, clauses, fetched_at) VALUES (?,?,?,?,?,?,?,?)",
                (key, lk.bill, lk.bill_id, lk.stage, lk.stage_id,
                 json.dumps([r.__dict__ for r in lk.refs]), json.dumps(lk.clauses),
                 datetime.date.today().isoformat()))
            self.conn.commit()
        except Exception:                                   # noqa: BLE001 - read-only store
            pass

    # Bills API ---------------------------------------------------------------
    def _bills_named(self, bill):
        key = base_name(bill)
        if key not in self._search:
            payload = self.client.get_json(
                "{0}/Bills?SearchTerm={1}&SortOrder=DateUpdatedDescending&Take=20".format(
                    API, quote(re.sub(r"\s*\[(Lords|HL)\]|\s*\(No\.?\s*\d+\)", "", bill))),
                "bills", "clause-search-{0}".format(key), archive=False)
            self._search[key] = [b for b in (payload.get("items") or [])
                                 if base_name(b.get("shortTitle")) == key]
        return self._search[key]

    def _bill_stages(self, bill_id):
        if bill_id not in self._stages:
            payload = self.client.get_json(
                "{0}/Bills/{1}/Stages?Take=60".format(API, bill_id),
                "bills", "clause-stages-{0}".format(bill_id), archive=False)
            self._stages[bill_id] = payload.get("items") or []
        return self._stages[bill_id]

    def _stage_amendments(self, bill_id, stage):
        sid = stage.get("id")
        if (bill_id, sid) not in self._amendments:
            out, skip = [], 0
            for _ in range(40):
                payload = self.client.get_json(
                    "{0}/Bills/{1}/Stages/{2}/Amendments?Take=100&Skip={3}".format(API, bill_id, sid, skip),
                    "bills", "clause-amendments-{0}-{1}-s{2}".format(bill_id, sid, skip), archive=False)
                rows = payload.get("items") or []
                out.extend(amd.parse_amendment(r, bill_id, stage.get("description"), stage.get("house"))
                           for r in rows)
                skip += 100
                if len(rows) < 100 or skip >= (payload.get("totalResults") or 0):
                    break
            self._amendments[(bill_id, sid)] = out
        return self._amendments[(bill_id, sid)]

    def _stages_on(self, bill, date, house):
        """[(bill record, stage)] for every stage of a Bill so named, in this House, that sat on `date`."""
        out = []
        for b in self._bills_named(bill):
            for s in self._bill_stages(b.get("billId")):
                if (s.get("house") or "").lower() != (house or "").lower():
                    continue
                if any(_iso(x.get("date")) == date for x in (s.get("stageSittings") or [])):
                    out.append((b, s))
        return out

    # Hansard ----------------------------------------------------------------
    def _hansard_rows(self, day):
        """Hansard's Commons division rows for one day: every one in a debate
        on a Bill (the search term matches the debate title)."""
        if day not in self._hdays:
            out, skip = [], 0
            for _ in range(10):
                payload = self.client.get_json(
                    "{0}/search/divisions.json?queryParameters.searchTerm=Bill"
                    "&queryParameters.startDate={1}&queryParameters.endDate={1}"
                    "&queryParameters.house=Commons&queryParameters.skip={2}"
                    "&queryParameters.take=100".format(HANSARD, day, skip),
                    "hansard", "clause-hdiv-{0}-s{1}".format(day, skip), archive=False) or {}
                rows = payload.get("Results") or []
                out.extend(rows)
                skip += len(rows)
                if not rows or skip >= int(payload.get("TotalResultCount") or 0):
                    break
            self._hdays[day] = out
        return self._hdays[day]

    def _hansard_debate(self, ext):
        """[(section overview, item)] for a debate section and its children, in order."""
        if ext not in self._hdebates:
            payload = self.client.get_json("{0}/debates/debate/{1}.json".format(HANSARD, ext),
                                           "hansard", "clause-hdebate-{0}".format(ext), archive=False) or {}
            out = []

            def walk(node):
                ov = node.get("Overview") or {}
                out.extend((ov, it) for it in (node.get("Items") or []))
                for child in node.get("ChildDebates") or []:
                    walk(child)
            walk(payload)
            self._hdebates[ext] = out
        return self._hdebates[ext]

    def _hansard_sections(self, bill, date, number=None, counts=None):
        """(debate section ext ids, the Bill's name as Hansard prints it) for a division.

        The division itself is found by its number or Aye/No counts on its
        day or the next (a sitting past midnight files under the next date);
        its section is read, and so is every debate that day on a Bill of the
        same name -- Hansard can file the divisions of a sitting apart from the
        debate, as "Unpublished Divisions: Crime and Policing Bill (14 April
        2026)", and the motions and the speeches then sit in different places."""
        nxt = (datetime.date.fromisoformat(date) + datetime.timedelta(days=1)).isoformat()
        rows = [(date, r) for r in self._hansard_rows(date)] + [(nxt, r) for r in self._hansard_rows(nxt)]
        ids, names, hansard_bill = [], {(base_name(bill), date)}, None
        hits = []
        for _, r in rows:
            if _iso(r.get("Date")) not in (date, nxt):
                continue
            by_number = number is not None and str(r.get("Number")) == str(number)
            by_counts = counts is not None and (r.get("AyesCount"), r.get("NoesCount")) == tuple(counts)
            if by_number or by_counts:
                hits.append(r)
        if len(hits) > 1:
            # equal counts on another Bill's division: keep the ones named like ours
            named = [r for r in hits if _similar(_section_bill(r.get("DebateSection"))[0], bill)]
            hits = named or hits[:0]
        for r in hits:
            name, when = _section_bill(r.get("DebateSection"))
            ids.append(r.get("DebateSectionExtId"))
            names.add((base_name(name), when or _iso(r.get("Date"))))
            hansard_bill = hansard_bill or name
        for day, r in rows:
            name, when = _section_bill(r.get("DebateSection"))
            if not when and (base_name(name), _iso(r.get("Date"))) in names:
                ids.append(r.get("DebateSectionExtId"))
                hansard_bill = hansard_bill or name
        out = []
        for ext in ids:
            if ext and ext not in out:
                out.append(ext)
        return out, " ".join((hansard_bill or bill).split())

    def _lords_stage_amendment(self, bill, date, title):
        """The one amendment AGREED at a Lords stage of this Bill inserting a
        clause titled `title`, or None (none, or more than one)."""
        hits = []
        for b in self._bills_named(bill):
            stages = self._bill_stages(b.get("billId"))
            # the Bill whose Commons stage sat that day, not an older Act of the same name
            if not any(_iso(x.get("date")) == date for s in stages for x in (s.get("stageSittings") or [])):
                continue
            for s in stages:
                if (s.get("house") or "").lower() != "lords" or not re.search(
                        r"committee|report|3rd reading|third reading", s.get("description") or "", re.I):
                    continue
                for a in self._stage_amendments(b.get("billId"), s):
                    if a.decision == "Agreed" and new_clause_title(a.summary) == title:
                        hits.append(a)
        return hits[0] if len(hits) == 1 else None

    def _earlier_considerations(self, bill, date):
        """Earlier Commons sittings on Lords amendments to this Bill, newest first."""
        days = set()
        for b in self._bills_named(bill):
            stages = self._bill_stages(b.get("billId"))
            if not any(_iso(x.get("date")) == date for s in stages for x in (s.get("stageSittings") or [])):
                continue
            for s in stages:
                if (s.get("house") or "").lower() == "commons" and re.search(
                        r"consideration of lords", s.get("description") or "", re.I):
                    days.update(_iso(x.get("date")) for x in (s.get("stageSittings") or []))
        return sorted((d for d in days if d and d < date), reverse=True)

    def _gather(self, found, refs, entries, day):
        """Add what these debate entries say about each ref to found[label]."""
        for ref in refs:
            heading, sentences, where = describe_lords_amendment(entries, ref.number)
            got = found[ref.label]
            if heading and not got["heading"]:
                got["heading"], got["where"] = heading, got["where"] or where
            new = [x for x in sentences if x not in got["sentences"]]
            if new:
                got["sentences"].extend(new[:MAX_SENTENCES - len(got["sentences"])])
                got["where"] = got["where"] or where
                if day not in got["days"]:
                    got["days"].append(day)

    def _clause(self, ref, got, hbill, date):
        head = ": ".join(got["heading"])
        clause = {"label": ref.label, "source": HANSARD_SOURCE, "amendment_id": None,
                  "url": _hansard_url(got["where"]), "decision": None, "explanatory": head,
                  "text": " ".join(x for x in [head] + got["sentences"] if x)}
        earlier = [d for d in got["days"] if d != date]
        if earlier:
            clause["described_on"] = earlier
        heading = got["heading"]
        title = _norm_title(heading[-1]) if len(heading) >= 2 and re.match(
            r"(?:After|Before)\s+(?:Clause|Schedule)", heading[0], re.I) else None
        if title:
            try:
                found = self._lords_stage_amendment(hbill, date, title)
                if found:
                    amd.fetch_detail(self.client, found)
            except Exception:                               # noqa: BLE001 - Hansard text stands
                found = None
            if found:
                clause.update({"amendment_id": found.amendment_id, "lords_url": found.url,
                               "lords_stage": "{0} amendment {1}".format(found.stage, found.marshalled),
                               "explanatory": found.explanatory or head,
                               "text": clause["text"] + " " + found.text})
        return clause, (found.bill_id if title and found else None)

    def _lookup_lords(self, lk, refs, date, key, number=None, counts=None):
        """Lords amendments by number, from the Commons debate in Hansard."""
        lk.stage = HANSARD_STAGE
        try:
            sections, hbill = self._hansard_sections(lk.bill, date, number, counts)
            entries = [e for ext in sections for e in self._hansard_debate(ext)]
        except Exception as exc:                            # noqa: BLE001 - fail loud
            lk.reason = "Hansard API unavailable for {0} on {1}: {2}".format(lk.bill, date, str(exc)[:120])
            return lk
        if not entries:
            lk.reason = "no Hansard debate on '{0}' with this division on {1} ({2})".format(
                lk.bill, date, LORDS_PAPER)
            return lk
        found = {r.label: {"heading": [], "sentences": [], "where": None, "days": []} for r in refs}
        self._gather(found, refs, entries, date)
        if any(not found[r.label]["sentences"] for r in refs):
            # Ping-pong: a later round's debate argues the motion, not the
            # amendments ("insists on its disagreement with the Lords in their
            # Amendments 15 to 24 ..."), but a Lords amendment keeps its number
            # through every round, and the first consideration described it.
            try:
                days = self._earlier_considerations(hbill, date)
            except Exception:                               # noqa: BLE001 - what was read stands
                days = []
            for day in days:
                left = [r for r in refs if not found[r.label]["sentences"]]
                if not left:
                    break
                try:
                    sections, _ = self._hansard_sections(hbill, day)
                    old = [e for ext in sections for e in self._hansard_debate(ext)]
                except Exception:                           # noqa: BLE001 - try the next sitting
                    continue
                self._gather(found, left, old, day)
        missing = []
        for ref in refs:
            got = found[ref.label]
            if not got["heading"] and not got["sentences"]:
                missing.append(ref.label)
                continue
            clause, bill_id = self._clause(ref, got, hbill, date)
            lk.clauses.append(clause)
            lk.bill_id = lk.bill_id or bill_id
        if not lk.clauses:
            lk.reason = "{0} not described in the Hansard debate of {1} ({2})".format(
                ", ".join(missing), date, LORDS_PAPER)
            return lk
        lk.status = "ok"
        if missing:
            lk.reason = "partly read; missing {0}".format(", ".join(missing))
        self._store(key, lk)
        return lk

    # the lookup --------------------------------------------------------------
    def lookup(self, title, date, house="Commons", notes=None, division_id=None,
               number=None, counts=None):
        """Lookup for one division. Never raises: a failure is status 'unreadable'.

        number (the division's number in the session) and counts ((ayes, noes))
        find a Lords-amendment division in Hansard; either will do."""
        house = "Lords" if (house or "").lower() == "lords" else "Commons"
        bill, refs = parse_refs(title, house, notes)
        if not refs:
            return Lookup("none", bill=bill)
        key = "{0}{1}".format(house[0].lower(), division_id) if division_id else None
        hit = self._cached(key)
        if hit:
            return hit
        lk = Lookup("unreadable", bill=bill, refs=refs[:MAX_REFS])
        if len(refs) > MAX_REFS:
            lk.reason = "title names {0} clauses; read the first {1}".format(len(refs), MAX_REFS)
        readable = [r for r in lk.refs if r.kind in ("new_clause", "new_schedule", "amendment")]
        lords = [r for r in lk.refs if r.kind == "lords_amendment"]
        if lords and house == "Commons":
            return self._lookup_lords(lk, lords, _iso(date), key, number, counts)
        if not readable:
            lk.reason = STAND_PART
            return lk
        date = _iso(date)
        try:
            stages = self._stages_on(bill, date, house)
        except Exception as exc:                            # noqa: BLE001 - fail loud, not silent
            lk.reason = "Bills API unavailable for {0}: {1}".format(bill, str(exc)[:120])
            return lk
        if not stages:
            lk.reason = "no {0} stage of '{1}' sat on {2} in the Bills API".format(house, bill, date)
            return lk
        # A report day also sits a programme motion, a money resolution and
        # third reading; amending stages are tried first, and a stage whose
        # list fails is only fatal if the clause is found nowhere else.
        stages.sort(key=lambda bs: not re.search(r"committee|report|consideration|remaining",
                                                 bs[1].get("description") or "", re.I))
        missing, broken = [], []
        for ref in readable:
            found = None
            for b, s in stages:
                try:
                    rows = self._stage_amendments(b.get("billId"), s)
                except Exception as exc:                    # noqa: BLE001
                    broken.append("{0}: {1}".format(s.get("description"), str(exc)[:100]))
                    continue
                found = next((a for a in rows if _norm_marshalled(a.marshalled) == ref.marshalled), None)
                if found:
                    lk.bill_id, lk.stage, lk.stage_id = b.get("billId"), s.get("description"), s.get("id")
                    break
            if not found:
                missing.append(ref.label + (" (amendments unavailable at {0})".format(
                    "; ".join(sorted(set(broken)))) if broken else ""))
                continue
            try:
                amd.fetch_detail(self.client, found)
            except Exception as exc:                        # noqa: BLE001
                missing.append("{0} (detail: {1})".format(ref.label, str(exc)[:80]))
                continue
            lk.clauses.append({"label": ref.label, "amendment_id": found.amendment_id,
                               "url": found.url, "decision": found.decision,
                               "explanatory": found.explanatory, "text": found.text})
        if missing and not lk.clauses:
            lk.reason = "{0} not found at the {1} stage(s) sitting {2}".format(
                ", ".join(missing), house, date)
            return lk
        lk.status = "ok"
        if missing:
            lk.reason = "partly read; missing {0}".format(", ".join(missing))
        self._store(key, lk)
        return lk


def match(lookup, tax, wl):
    """(FilterResult, [labels that matched]) over the clause text; (None, []) if none read.

    Each clause is matched on its own so the record names the clause that
    carried the term; the returned result is over the matching clauses only,
    with title="" because a clause body has no heading of its own (a broad
    watchlist name cited inside it is a citation, not the subject)."""
    from src import filter as filt
    if lookup.status != "ok":
        return None, []
    hits = [c for c in lookup.clauses
            if filt.filter_item(tax, wl, c.get("text") or "", title="").matched()]
    if not hits:
        return filt.FilterResult(), []
    result = filt.filter_item(tax, wl, *[c.get("text") or "" for c in hits], title="")
    return result, [c["label"] for c in hits]


def ledger_ok(lookup, labels, tax, wl):
    """May a clause-text match put the division's voters in the ledger?

    Only when a tier-1 term is in what the clause is FOR -- its explanatory
    statement, or failing one its heading and opening -- not merely somewhere
    in its body. Measured on the Parliament so far (tools/check_clause_text.py,
    13 Oct 2026): Sentencing Bill NC20 (division 2163) is a child-cruelty
    register whose body lists offences under the Offences against the Person
    Act 1861, a tier-1 abortion term; ledgering it would score 600 members on
    abortion for a vote about child cruelty. The item is still stored, so
    triage and a human see it; only the automatic ledger waits for a stronger
    signal. NC142 (puberty blockers) states its purpose and passes.

    A Lords amendment read from Hansard has no body of its own: its text is
    members' sentences about it, which are argument, not purpose. Only its
    clause heading, or the Lords' own explanatory statement when the second
    route found one, can open the ledger.
    """
    return gated(lookup, labels, tax, wl) is not None


def gated(lookup, labels, tax, wl, result=None):
    """The part of a clause-text match that may enter the ledger, or None.

    Per area (16 October 2026, Chris; the same rule as src/amendtext.gated):
    only the areas whose own TIER-1 term is in a matched clause's purpose
    (ledger_ok above says what the purpose is), with only those terms, tier
    1. A clause whose explanatory statement names an abortion offence and
    whose body lists other offences enters the ledger on abortion only; the
    rest of the match stays on the item for triage. Never wider than the
    whole match (`result`, recomputed when not given)."""
    from src import filter as filt
    if result is None:
        result, _ = match(lookup, tax, wl)
    if not result:
        return None
    allowed = set(result.issue_areas or [])
    terms_ok = set(result.matched_terms or [])
    areas, terms = set(), []
    for c in lookup.clauses:
        if c.get("label") not in labels:
            continue
        if c.get("source") == HANSARD_SOURCE:
            purpose = c.get("explanatory") or ""
        else:
            purpose = c.get("explanatory") or (c.get("text") or "")[:300]
        if not purpose:
            continue
        text = filt._fold(purpose)
        for area, tier, term in filt._scan_taxonomy(text.lower(), text, tax):
            if tier != 1 or area not in allowed or term not in terms_ok:
                continue
            areas.add(area)
            if term not in terms:
                terms.append(term)
    if not areas:
        return None
    return filt.FilterResult(matched_terms=terms, issue_areas=sorted(areas), tier=1)


def match_source(lookup, labels=None):
    """What the match was made on: "clause text" (the Bills API amendment) or
    "Hansard (Lords amendment)" (the Commons debate, src docstring)."""
    for c in lookup.clauses:
        if labels is None or c.get("label") in labels:
            return c.get("source") or SOURCE
    return SOURCE


def describe(lookup, labels):
    """The 'why' line a reviewer sees: which clause, from where."""
    hit = [c for c in lookup.clauses if c["label"] in labels]
    urls = [c["url"] for c in hit if c.get("url")]
    extra = ["{0} {1}".format(c["lords_stage"], c["lords_url"]) for c in hit if c.get("lords_stage")]
    return "{0}: {1} of the {2} ({3})".format(match_source(lookup, labels), ", ".join(labels), lookup.bill,
                                             lookup.stage or "?") + (" " + urls[0] if urls else "") + (
        "; text from the Lords' {0}".format("; ".join(extra)) if extra else "")
