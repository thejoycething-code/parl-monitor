"""Triage pass: score candidate items 0-3 and draft why_it_matters (handoff 7).

Tier-2 matches and all watchlist hits go through this scoring. Phase 1 runs with
TRIAGE=stub (deterministic, no API); the live pass calls Claude in batches of up
to 20. Everything downstream must work end to end with the stub (CLAUDE.md).

Model: the handoff pins `claude-sonnet-4-6`, which is not a valid id; corrected
to `claude-sonnet-5` (see docs/api-notes.md). Only the live pass uses it.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

TRIAGE_MODEL = "claude-sonnet-5"
BATCH_SIZE = 20

# Verbatim system prompt (handoff section 7).
SYSTEM_PROMPT = """You are the triage layer of CitizenGO UK's parliamentary monitor. CitizenGO campaigns
on: abortion (pro-life), assisted dying (opposed), youth gender medicine (opposed to
paediatric transition), conversion practices bans (concerned re therapy/parental/religious
freedom), single-sex spaces (sex-based rights), parental rights in education, free speech
and online safety overreach, freedom of religion or belief, marriage and family, surrogacy
(opposed to commercial surrogacy).

For each item, return JSON: {"id": ..., "score": 0-3, "areas": [..],
"why_it_matters": "..."}.
Score 0 = irrelevant to every area. 1 = background only. 2 = belongs in the weekly
digest. 3 = likely campaign or lobbying trigger.
why_it_matters: maximum 35 words, CitizenGO voice: direct, concrete, no hedging,
British spelling, no em dashes. State the implication, not a summary.
Score on relevance to the areas above regardless of whether an item helps or hurts
the campaign position: opposition activity scores as highly as friendly activity.
Return only the JSON array."""


@dataclass
class TriageItem:
    id: str
    title: str
    text: str
    tier: int            # from filter (1 or 2), or None for watchlist-only
    issue_areas: list
    watchlist_hit: bool


@dataclass
class TriageResult:
    id: str
    score: int
    areas: list
    why_it_matters: str
    stub: bool = False


# -- stub -------------------------------------------------------------------

def score_stub(items):
    """Deterministic scoring (handoff 7): tier-1 -> 2, tier-2 -> 1, watchlist -> 2.

    All are flagged for the human review file; why_it_matters is left blank for
    a human to write.
    """
    results = []
    for item in items:
        score = 2 if (item.tier == 1 or item.watchlist_hit) else 1
        results.append(TriageResult(id=item.id, score=score, areas=list(item.issue_areas),
                                    why_it_matters="", stub=True))
    return results


# -- live -------------------------------------------------------------------

def _batches(items, size=BATCH_SIZE):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def _build_payload(batch):
    user = [{"id": it.id, "title": it.title, "text": (it.text or "")[:2000],
             "candidate_areas": it.issue_areas} for it in batch]
    return {
        "model": TRIAGE_MODEL,
        "max_tokens": 1500,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": json.dumps(user)}],
    }


def _default_transport(payload, api_key):  # pragma: no cover - real network
    import urllib.request

    request = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def _parse_reply(reply):
    """Extract the JSON array from a Messages API reply."""
    text = "".join(block.get("text", "") for block in (reply.get("content") or []))
    data = json.loads(text)
    out = []
    for row in data:
        out.append(TriageResult(id=row.get("id"), score=row.get("score"),
                                areas=row.get("areas") or [],
                                why_it_matters=row.get("why_it_matters") or ""))
    return out


def score_live(items, api_key=None, transport=None):
    """Score via Claude in batches of 20. transport is injectable for testing."""
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY required for live triage (use TRIAGE=stub otherwise)")
    transport = transport or _default_transport
    results = []
    for batch in _batches(items):
        reply = transport(_build_payload(batch), api_key)
        results.extend(_parse_reply(reply))
    return results


# -- session mode: a queue file scored inside a Claude Code session ----------
#
# TRIAGE=session writes the scoring rubric + pending items to a markdown file.
# A Claude Code session (running on the user's existing entitlement, no API
# key) fills in SCORE/WHY per item; parse_queue_file reads them back. The same
# file also works for fully manual scoring.

QUEUE_HEADER = """# Triage queue for the edition of {week}

Score each item using the rubric below, then run the render step
(`python3 run_weekly.py --render {week}`), which applies these scores.

SCORE: 0 = irrelevant to every area. 1 = background only. 2 = belongs in the
weekly digest. 3 = likely campaign or lobbying trigger. Score on relevance
regardless of whether an item helps or hurts the campaign position.
WHY: maximum 35 words, CitizenGO voice: direct, concrete, no hedging, British
spelling, no em dashes. State the implication, not a summary.

Do not edit the `### item:` id lines.

<!-- scoring context (verbatim from handoff section 7):
{system_prompt}
-->

---
"""


def generate_queue_file(conn, watchlist, week, path):
    """Write pending items + rubric to a session-scorable queue file."""
    items = pending_items(conn, watchlist)
    blocks = [QUEUE_HEADER.format(week=week, system_prompt=SYSTEM_PROMPT)]
    for item in items:
        areas = ", ".join(str(a) for a in item.issue_areas)
        blocks.append("### item: {0}".format(item.id))
        blocks.append("- tier: {0} | candidate areas: {1} | watchlist hit: {2}".format(
            item.tier, areas or "-", "yes" if item.watchlist_hit else "no"))
        blocks.append("- title: {0}".format(item.title))
        blocks.append("SCORE: ")
        blocks.append("WHY: ")
        blocks.append("")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(blocks))
    return path, len(items)


def parse_queue_file(path):
    """Parse a scored queue file into TriageResults. Unscored items are skipped."""
    results = []
    current_id, score, why = None, None, ""

    def flush():
        if current_id is not None and score is not None:
            results.append(TriageResult(id=current_id, score=score, areas=[], why_it_matters=why))

    with open(path, "r", encoding="utf-8") as handle:
        for raw in handle:
            line = raw.rstrip("\n")
            if line.startswith("### item:"):
                flush()
                current_id, score, why = line.split("item:", 1)[1].strip(), None, ""
            elif line.upper().startswith("SCORE:"):
                value = line.split(":", 1)[1].strip()
                score = int(value) if value.isdigit() else None
            elif line.upper().startswith("WHY:"):
                why = line.split(":", 1)[1].strip()
    flush()
    return results


# -- dispatch ---------------------------------------------------------------

def triage(items, mode=None, **kwargs):
    """Dispatch on mode ('stub'|'live'); defaults to the TRIAGE env var or stub."""
    mode = mode or os.environ.get("TRIAGE", "stub")
    if mode == "live":
        return score_live(items, **kwargs)
    return score_stub(items)


# -- pending-queue pass over the store ---------------------------------------

def pending_items(conn, watchlist=None):
    """Items stored with triage_score NULL, as TriageItems awaiting scoring.

    watchlist (filter.Watchlist) lets us mark watchlist hits so the minimum
    score 2 rule (handoff section 6) is enforced at scoring time.
    """
    entity_names = {e[0] for e in (watchlist.entities if watchlist else [])}
    rows = conn.execute(
        "SELECT id, title, issue_areas, matched_terms, tier FROM items WHERE triage_score IS NULL"
    ).fetchall()
    items = []
    for r in rows:
        matched = json.loads(r["matched_terms"] or "[]")
        items.append(TriageItem(
            id=r["id"], title=r["title"], text="", tier=r["tier"],
            issue_areas=json.loads(r["issue_areas"] or "[]"),
            watchlist_hit=any(t in entity_names for t in matched),
        ))
    return items


def apply_scores(conn, items, results):
    """Write triage results back to the store, enforcing the watchlist floor.

    Returns (scored, discards) where discards are (item_id, title) of score-0
    rows for the discards log.
    """
    by_id = {i.id: i for i in items}
    discards = []
    for r in results:
        item = by_id.get(r.id)
        if item is None:
            continue
        score = r.score if r.score is not None else 0
        if item.watchlist_hit and score < 2:
            score = 2  # watchlist entities are included at minimum score 2
        conn.execute(
            "UPDATE items SET triage_score = ?, why_it_matters = COALESCE(NULLIF(?, ''), why_it_matters) "
            "WHERE id = ?",
            (score, r.why_it_matters or "", r.id),
        )
        if score == 0:
            discards.append((r.id, item.title))
    conn.commit()
    return len(results), discards


def partition(results):
    """Split scored results into (review_queue >=2, background ==1, discards ==0)."""
    review, background, discards = [], [], []
    for r in results:
        if r.score is not None and r.score >= 2:
            review.append(r)
        elif r.score == 0:
            discards.append(r)
        else:
            background.append(r)
    return review, background, discards
