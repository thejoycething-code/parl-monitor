"""Senedd (Welsh Parliament) watching-brief ingester -- phase 1: questions.

What probing established (2026-08-21, full table in docs/api-notes.md):

  * There is NO usable data API. data-style endpoints do not exist; the
    ModernGov XML exports serve HTML shells; the Record's /Search?q= IGNORES
    its query server-side (three different terms returned byte-identical
    pages). What works is the Record's per-id pages:
    record.senedd.wales/WrittenQuestion/<id>.
  * IDs are DENSE sequential integers (~93000 = May 2024, ~100230 = Aug
    2026, ~60/week), so discovery is ID-WALKING: no search, no sweep terms,
    the taxonomy classifies every question -- Holyrood's property by a
    different route. A nonexistent id serves the site shell WITHOUT a
    "Tabled on" line: that absence is the miss signature.
  * record.senedd.wales accepts the project's honest CitizenGO User-Agent.
    business.senedd.wales (ModernGov) rejects it with a WAF 403 and answers
    only to browser UAs -- so PARTY IS NOT HELD in phase 1: question pages
    carry member name and constituency but not party, and the enrichment
    source would require pretending to be a browser, which is a decision,
    not a default. Recorded, not worked around.
  * Answered pages carry "Answered by <minister> | Answered on <date>" and
    the full answer text inline. A "(w)" marker beside the reference means
    tabled in Welsh; the page still carries English text.
"""

from __future__ import annotations

import html as _html
import re
from dataclasses import dataclass

QUESTION_URL = "https://record.senedd.wales/WrittenQuestion/{0}"

_TABLED = re.compile(r"Tabled on (\d\d)/(\d\d)/(\d\d\d\d)")
_ANSWERED = re.compile(
    r"Answered by (.+?) \| Answered on (\d\d)/(\d\d)/(\d\d\d\d)")
_TO_BE = re.compile(r"To be answered by:\s*(.+)")


def _lines(page):
    body = re.sub(r"<script.*?</script>|<style.*?</style>", "", page, flags=re.S)
    text = re.sub(r"<[^>]+>", "\n", body)
    return [_html.unescape(l.strip()) for l in text.split("\n") if l.strip()]


def _iso(d, m, y):
    return "{0}-{1}-{2}".format(y, m, d)


@dataclass
class Question:
    wq_id: int
    reference: str          # 'WQ100032'
    member_name: str
    constituency: str
    dated: str              # tabled
    welsh: bool             # tabled in Welsh ('(w)' marker)
    body: str
    answered_by: str        # minister title (answered or to-be)
    answered: str           # answer date, None while pending
    answer: str             # answer text, None while pending


def parse_question(page, wq_id):
    """Question from one page, or None on the miss signature.

    The page layout is positional: name / constituency / WQnnnnn / (e|w) /
    Tabled on ... / question text / answer block. Anchoring on the WQ
    reference and the Tabled line keeps the parse independent of the site
    chrome above and below.
    """
    if "Tabled on" not in page:
        return None
    lines = _lines(page)
    ref = "WQ{0}".format(wq_id)
    try:
        i = next(k for k, l in enumerate(lines) if l == ref)
    except StopIteration:
        return None
    name = lines[i - 2] if i >= 2 else ""
    seat = lines[i - 1] if i >= 1 else ""
    welsh = (i + 1 < len(lines) and lines[i + 1].strip("()") == "w")
    t = next((k for k in range(i, min(i + 6, len(lines)))
              if _TABLED.search(lines[k])), None)
    if t is None:
        return None
    dated = _iso(*reversed(_TABLED.search(lines[t]).groups()))
    dated = "{0}-{1}-{2}".format(*_TABLED.search(lines[t]).groups()[::-1])
    # Question text: lines after Tabled until the answer/to-be marker.
    q_parts, answered_by, answered, answer_parts = [], None, None, []
    mode = "question"
    for l in lines[t + 1:]:
        if l.startswith("Contact us"):
            break
        m = _ANSWERED.search(l)
        if m:
            answered_by = m.group(1).strip()
            answered = "{0}-{1}-{2}".format(m.group(4), m.group(3), m.group(2))
            mode = "answer"
            continue
        m = _TO_BE.search(l)
        if m:
            answered_by = m.group(1).strip()
            mode = "done"
            continue
        if mode == "question":
            q_parts.append(l)
        elif mode == "answer":
            answer_parts.append(l)
    return Question(
        wq_id=wq_id, reference=ref, member_name=name, constituency=seat,
        dated=dated, welsh=welsh,
        body=" ".join(" ".join(q_parts).split()),
        answered_by=answered_by,
        answered=answered,
        answer=" ".join(" ".join(answer_parts).split()) or None)


def fetch_question(client, wq_id, timeout=30):
    """Question or None (miss). archive=False: ~170KB of site chrome per page
    and the store keeps the parsed text whole; the id IS the provenance."""
    page = client.get_text(QUESTION_URL.format(wq_id), "senedd",
                           "wq-{0}".format(wq_id), timeout=timeout,
                           archive=False)
    return parse_question(page, wq_id)
