"""Amendments to watched Bills (Christopher, 2026-09-07: "the largest blind spot").

The board tracks stages; nobody read the amendment papers. The abortion
decriminalisation clause (Crime and Policing Bill, New Clause 1) and the
conversion-practices amendments arrived exactly there, as amendments to
Home Office and Justice Bills, never as Bills of their own.

The Bills API lists every stage of a Bill and every amendment tabled at a
stage, paged 100 at a time, with the marshalled-list number (NC42, 12,
Amendment 94), sponsors, a decision (Agreed / NegativedOnDivision /
NoDecision / NotCalled / NotMoved / Withdrawn / NotSelected) and a short
summary; the detail call adds the full amendment lines and the member's
explanatory statement. Measured 2026-09-07 on the Crime and Policing Bill's
Commons committee stage: 184 amendments, 78 agreed, 45 negatived on
division.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

API = "https://bills-api.parliament.uk/api/v1"
PUBLIC = "https://bills.parliament.uk/bills/{bill}/stages/{stage}/amendments/{amendment}"
_TAG = re.compile(r"<[^>]+>")


@dataclass
class Amendment:
    amendment_id: str
    bill_id: int
    stage_id: int
    stage: str = None
    house: str = None
    marshalled: str = None       # NC42, 12, Amendment 94
    kind: str = None             # AddClauseOrSchedule | EditBillBody | DeleteClauseOrSchedule
    summary: str = ""            # summaryText lines joined, markup stripped
    lead: str = None
    sponsors: list = field(default_factory=list)
    decision: str = None
    explanatory: str = ""        # from the detail call
    lines: str = ""              # amendment text, from the detail call

    @property
    def url(self):
        return PUBLIC.format(bill=self.bill_id, stage=self.stage_id, amendment=self.amendment_id)

    @property
    def text(self):
        return " ".join(x for x in (self.summary, self.explanatory, self.lines) if x)

    @property
    def label(self):
        m = self.marshalled or self.amendment_id
        if m and m.isdigit():
            return "Amendment {0}".format(m)
        return m


def _clean(parts):
    if isinstance(parts, str):
        parts = [parts]
    out = []
    for p in parts or []:
        if isinstance(p, dict):
            p = p.get("text") or ""
        out.append(_TAG.sub(" ", str(p)))
    return " ".join(" ".join(out).split())


def parse_stage(row):
    return {"id": row.get("id"), "description": row.get("description"), "house": row.get("house")}


def parse_amendment(row, bill_id=None, stage=None, house=None):
    sponsors = [s.get("name") for s in (row.get("sponsors") or []) if isinstance(s, dict) and s.get("name")]
    lead = next((s.get("name") for s in (row.get("sponsors") or []) if isinstance(s, dict) and s.get("isLead")), None)
    return Amendment(
        amendment_id=str(row.get("amendmentId") or row.get("id")), bill_id=bill_id or row.get("billId"),
        stage_id=row.get("billStageId"), stage=stage, house=house,
        marshalled=row.get("marshalledListText"), kind=row.get("amendmentType"),
        summary=_clean(row.get("summaryText")), lead=lead or (sponsors[0] if sponsors else None),
        sponsors=sponsors, decision=row.get("decision"),
        explanatory=_clean(row.get("explanatoryText")) if row.get("explanatoryText") else "",
        lines=_clean(row.get("amendmentLines")) if row.get("amendmentLines") else "",
    )


def fetch_stages(client, bill_id):
    payload = client.get_json("{0}/Bills/{1}/Stages?Take=60".format(API, bill_id), "bills",
                              "stages-{0}".format(bill_id))
    return [parse_stage(r) for r in (payload.get("items") or [])]


def fetch_amendments(client, bill_id, stage, page=100, max_pages=40):
    """Every amendment at one stage (paged)."""
    out, skip = [], 0
    for _ in range(max_pages):
        payload = client.get_json(
            "{0}/Bills/{1}/Stages/{2}/Amendments?Take={3}&Skip={4}".format(API, bill_id, stage["id"], page, skip),
            "bills", "amendments-{0}-{1}-s{2}".format(bill_id, stage["id"], skip))
        rows = payload.get("items") or []
        out.extend(parse_amendment(r, bill_id, stage.get("description"), stage.get("house")) for r in rows)
        skip += page
        if len(rows) < page or skip >= (payload.get("totalResults") or 0):
            break
    return out


def fetch_detail(client, amendment):
    """Fill explanatory statement and amendment lines from the detail call."""
    payload = client.get_json(
        "{0}/Bills/{1}/Stages/{2}/Amendments/{3}".format(API, amendment.bill_id, amendment.stage_id, amendment.amendment_id),
        "bills", "amendment-{0}".format(amendment.amendment_id))
    amendment.explanatory = _clean(payload.get("explanatoryText")) if payload.get("explanatoryText") else amendment.explanatory
    amendment.lines = _clean(payload.get("amendmentLines")) if payload.get("amendmentLines") else amendment.lines
    return amendment


DECISION_WORDS = {
    "Agreed": "agreed", "NegativedOnDivision": "negatived on division", "Negatived": "negatived",
    "NoDecision": "tabled, not yet reached", "NotCalled": "not called", "NotMoved": "not moved",
    "Withdrawn": "withdrawn", "NotSelected": "not selected",
}


def decision_word(decision):
    return DECISION_WORDS.get(decision or "", (decision or "tabled").lower())
