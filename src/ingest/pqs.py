"""Written questions ingester (handoff 4.2).

Quirks encoded:
  * never use answeredWhenFrom (dramatically slower) or expandMember=true;
    results come newest-first, filter dateAnswered client-side;
  * store dateTabled: the canonical deep link cannot be built without it;
  * search matching is loose (Parliament's relevance is poor), so nothing here
    is a publishable hit; everything goes on to filter + triage.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from urllib.parse import quote

from src.ingest.bills import parse_api_date

PQ_API = "https://questions-statements-api.parliament.uk/api/writtenquestions/questions"


@dataclass
class WrittenQuestion:
    id: int
    uin: str
    heading: str
    question_text: str
    answer_text: str
    asking_member_id: int
    answering_body: str
    date_tabled: datetime.date
    date_answered: datetime.date
    house: str

    @property
    def url(self):
        # https://questions-statements.parliament.uk/written-questions/detail/YYYY-MM-DD/{uin}
        tabled = self.date_tabled.isoformat() if self.date_tabled else "unknown"
        return "https://questions-statements.parliament.uk/written-questions/detail/{0}/{1}".format(tabled, self.uin)


def parse_question(value):
    return WrittenQuestion(
        id=value.get("id"),
        uin=value.get("uin"),
        heading=value.get("heading"),
        question_text=value.get("questionText"),
        answer_text=value.get("answerText"),
        asking_member_id=value.get("askingMemberId"),
        answering_body=value.get("answeringBodyName"),
        date_tabled=parse_api_date(value.get("dateTabled")),
        date_answered=parse_api_date(value.get("dateAnswered")),
        house=value.get("house"),
    )


def parse_response(payload):
    """PQ envelope is {totalResults, results:[{value:{...}}]}."""
    return [parse_question(row.get("value") or {}) for row in (payload.get("results") or [])]


def fetch_questions(client, term, take=6):
    url = "{0}?searchTerm={1}&answered=Answered&take={2}".format(PQ_API, quote(term), take)
    return parse_response(client.get_json(url, "pq", "search-{0}".format(term)))


def since(questions, cutoff):
    """Client-side date filter: keep questions answered on/after cutoff."""
    return [q for q in questions if q.date_answered and q.date_answered >= cutoff]


def fetch_question(client, qid):
    """ONE question, in full, from the detail endpoint.

    The search endpoint that fetch_questions uses returns each question
    with questionText cut at about 255 characters and, on disk, 93 of 237
    archived questions ended mid-sentence (measured 2026-09-06). The
    detail endpoint returns the whole question AND the minister's
    answerText, which the list never carried at all. The archive name
    pq_detail-<id>.json.gz matches the pq_*.json.gz glob that
    stance.build_text_map reads, so downstream readers see the full text
    without knowing where it came from.
    """
    payload = client.get_json("{0}/{1}".format(PQ_API, qid), "pq",
                              "detail-{0}".format(qid))
    return parse_question(payload.get("value") or payload)


def complete(client, question, log=None):
    """The same question with full text, or the stub if the detail fetch
    fails -- a missing answer must never lose the row."""
    try:
        full = fetch_question(client, question.id)
    except Exception as exc:                          # noqa: BLE001
        if log:
            log("  [gap] pq {0} detail: {1}".format(question.id, exc))
        return question
    if not full.question_text:
        return question
    return full
