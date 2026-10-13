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

  Lords Amendment N   (Commons ping-pong) numbers follow the consolidated
                      "Lords amendments" paper, which is published only on
                      publications.parliament.uk -- behind a Cloudflare
                      challenge, measured 13 October 2026, and not fetched --
                      and is NOT in the Bills API: the Commons "Consideration
                      of Lords amendments" stage lists zero amendments (Crime
                      and Policing Bill, stage 20642). The Lords' own
                      marshalled numbers differ, so guessing would read the
                      WRONG clause, which is worse than reading none.
  Clause N stand part the Bills API carries amendments, not the Bill's own
                      clauses.

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


# -- the reader ---------------------------------------------------------------

class ClauseReader:
    """Looks up division clause text through the Bills API, with both caches."""

    def __init__(self, client, conn=None):
        self.client = client
        self.conn = conn
        self._search, self._stages, self._amendments = {}, {}, {}

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

    # the lookup --------------------------------------------------------------
    def lookup(self, title, date, house="Commons", notes=None, division_id=None):
        """Lookup for one division. Never raises: a failure is status 'unreadable'."""
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
        if not readable:
            lk.reason = LORDS_PAPER if any(r.kind == "lords_amendment" for r in lk.refs) else STAND_PART
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
    """
    from src import filter as filt
    for c in lookup.clauses:
        if c.get("label") not in labels:
            continue
        purpose = c.get("explanatory") or (c.get("text") or "")[:300]
        if filt.filter_item(tax, wl, purpose, title="").tier == 1:
            return True
    return False


def describe(lookup, labels):
    """The 'why' line a reviewer sees: which clause, from where."""
    urls = [c["url"] for c in lookup.clauses if c["label"] in labels]
    return "{0}: {1} of the {2} ({3})".format(SOURCE, ", ".join(labels), lookup.bill,
                                             lookup.stage or "?") + (" " + urls[0] if urls else "")
