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
