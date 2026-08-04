"""Stance layer: classify ledger evidence onto the 5CA gradient.

The ledger measures ACTIVITY, not DIRECTION -- an asker pressing for tighter
borders and a peer pressing against them ledger identically (docs/5ca-notes.md).
This pass reads the evidence text (the member's question framing, the motion
text they signed) and scores the MEMBER'S OWN ACTION against CitizenGO's
position: +2 strong ally .. -2 strong opponent, 0 when neutral, procedural or
unclear. Scores are stored per ref in the stance table; an EDM's sponsor and
every co-signatory inherit the motion's direction (signing endorses the text).

Division votes and Hansard speeches (September) will outrank these
text-derived scores in the 5CA generator's evidence hierarchy.

Mirrors triage.py: stub-free live pass, injectable transport, batches of 20.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

STANCE_MODEL = "claude-sonnet-5"
BATCH_SIZE = 20

SYSTEM_PROMPT = """You are the stance-classification layer of CitizenGO UK's parliamentary monitor.
CitizenGO's positions: abortion (pro-life), assisted dying (opposed), youth gender
medicine (opposed to paediatric transition), conversion practices bans (concerned re
therapy/parental/religious freedom), single-sex spaces (defends sex-based rights),
parental rights in education (supports), free speech (defends; wary of online safety
overreach), freedom of religion or belief (defends), marriage and family (supports),
surrogacy (opposed to commercial surrogacy), migration (border control and integrity,
opposed to illegal migration).

Each input is a parliamentary action BY A MEMBER: a written question they asked
(text = the member's own question, never the government's answer) or an Early Day
Motion they sponsored or signed (text = the motion they endorsed).

Score the member's action relative to CitizenGO's position on the areas given:
 +2 clearly advances/aligns with the position (strong ally signal)
 +1 leans toward it
  0 neutral, procedural, factual information-seeking, or direction unclear
 -1 leans against it
 -2 clearly opposes it (strong opponent signal)

Rules: judge only the text supplied; most written questions are neutral
information-seeking and score 0 -- only score direction the framing itself shows.
Never infer stance from the member's party or name. An EDM's text is an endorsed
position, so motions usually carry direction.

For each input return JSON: {"ref": ..., "stance": -2..2, "why": "..."}.
why: maximum 20 words, concrete, British spelling, no em dashes.
Return only the JSON array."""


@dataclass
class Evidence:
    ref: str             # 'pq:123' / 'edm:456' -- shared by sponsor + signatories
    kind: str
    line: str
    areas: list = field(default_factory=list)
    text: str = ""       # full question / motion text where recoverable


@dataclass
class StanceResult:
    ref: str
    stance: int
    why: str


# -- storage ------------------------------------------------------------------

def ensure_table(conn):
    conn.execute("CREATE TABLE IF NOT EXISTS stance ("
                 "ref TEXT PRIMARY KEY, stance INTEGER, why TEXT, "
                 "model TEXT, scored_at TEXT)")
    conn.commit()


def unscored_refs(conn):
    """Distinct text-bearing ledger refs with no stance row yet.

    One representative row per ref: sponsor/signatory events share their
    motion's ref and therefore its (single) stance classification.
    """
    ensure_table(conn)
    return conn.execute(
        "SELECT e.ref, MIN(e.kind) AS kind, MIN(e.line) AS line, MIN(e.areas) AS areas "
        "FROM mp_events e LEFT JOIN stance s ON s.ref = e.ref "
        "WHERE s.ref IS NULL AND e.kind != 'vote' GROUP BY e.ref").fetchall()


def store_scores(conn, results, scored_at, model=STANCE_MODEL):
    ensure_table(conn)
    for r in results:
        if r.ref is None or r.stance is None:
            continue
        conn.execute(
            "INSERT OR REPLACE INTO stance (ref, stance, why, model, scored_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (r.ref, max(-2, min(2, int(r.stance))), r.why or "", model, scored_at))
    conn.commit()


# -- live classification ------------------------------------------------------

def _batches(items, size=BATCH_SIZE):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def _build_payload(batch):
    user = [{"ref": ev.ref, "kind": ev.kind, "areas": ev.areas,
             "line": ev.line, "text": (ev.text or "")[:1500]} for ev in batch]
    return {
        "model": STANCE_MODEL,
        "max_tokens": 4000,  # 20 whys at ~20 words never approaches this
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
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def _parse_reply(reply):
    """Extract results, tolerating markdown fences and truncated arrays.

    A max_tokens cut mid-array (seen live 2026-08-04) loses at most the last
    entry; the salvage keeps every complete object so the idempotent re-run
    only has the remainder to score.
    """
    text = "".join(block.get("text", "") for block in (reply.get("content") or [])).strip()
    if text.startswith("```"):
        text = text.strip("`").lstrip("json").strip()
    try:
        data = json.loads(text)
    except ValueError:
        cut = text.rfind("}")
        if cut < 0:
            raise
        data = json.loads(text[:cut + 1] + "]")
    return [StanceResult(ref=row.get("ref"), stance=row.get("stance"),
                         why=row.get("why") or "")
            for row in data]


def classify_batch(batch, api_key=None, transport=None):
    """One live call over up to BATCH_SIZE Evidence items."""
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("anthropic_api_key required for stance classification")
    transport = transport or _default_transport
    return _parse_reply(transport(_build_payload(batch), api_key))


def classify_live(evidence, api_key=None, transport=None):
    results = []
    for batch in _batches(evidence):
        results.extend(classify_batch(batch, api_key=api_key, transport=transport))
    return results


# -- 5CA sheet generation -----------------------------------------------------

COLUMNS = ("++", "+", "0", "-", "--")

# Evidence hierarchy (docs/5ca-notes.md): sponsoring a motion outranks signing
# one, which outranks question framing. Votes/speeches will slot in above all
# three when September lands them in the ledger.
KIND_WEIGHT = {"edm": 3, "edm-signed": 2, "pq": 1}


def stance_to_column(stance):
    return {2: "++", 1: "+", 0: "0", -1: "-", -2: "--"}[max(-2, min(2, stance or 0))]


def suggest_rows(conn, area):
    """One 5CA Plan row per member active on `area`, strongest evidence first.

    Placement rule: the most directional evidence wins, ties broken by kind
    weight then recency; members whose evidence is all-neutral sit at 0. A
    sign conflict (both + and - evidence) is flagged in the comments -- the
    campaigner decides, the tool never averages opposing signals away.
    """
    ensure_table(conn)
    rows = conn.execute(
        "SELECT e.member_id, e.date, e.kind, e.ref, e.line, e.areas, "
        "s.stance, s.why, m.name, m.party, m.seat, m.house "
        "FROM mp_events e LEFT JOIN stance s ON s.ref = e.ref "
        "LEFT JOIN members m ON m.id = e.member_id "
        "ORDER BY e.date DESC").fetchall()

    per_member = {}
    for r in rows:
        areas = json.loads(r["areas"]) if r["areas"] else []
        if area not in areas:
            continue
        per_member.setdefault(r["member_id"], []).append(r)

    out = []
    for mid, evs in per_member.items():
        best = max(evs, key=lambda r: (abs(r["stance"] or 0),
                                       KIND_WEIGHT.get(r["kind"], 0),
                                       r["date"]))
        stance = best["stance"] or 0
        signs = {(1 if (r["stance"] or 0) > 0 else -1)
                 for r in evs if (r["stance"] or 0) != 0}
        conflict = len(signs) > 1
        first = evs[0]
        name = first["name"] or "Member {0}".format(mid)
        detail = ", ".join(x for x in (first["party"], first["seat"]) if x)
        comments = []
        if conflict:
            comments.append("CONFLICTING SIGNALS - review all evidence")
        for r in sorted(evs, key=lambda r: r["date"], reverse=True):
            note = " [{0}{1}]".format(
                stance_to_column(r["stance"]) if r["stance"] is not None else "unscored",
                ": " + r["why"] if r["why"] else "")
            comments.append("{0} {1}: {2}{3}".format(
                r["date"], r["kind"].upper(), r["line"], note))
        out.append({
            "member_id": mid,
            "decision_maker": name + (" ({0})".format(detail) if detail else ""),
            "house": first["house"] or "",
            "column": stance_to_column(stance),
            "conflict": conflict,
            "n_events": len(evs),
            "comments": " | ".join(comments),
        })

    order = {c: i for i, c in enumerate(COLUMNS)}
    out.sort(key=lambda r: (order[r["column"]], -r["n_events"], r["decision_maker"]))
    return out
