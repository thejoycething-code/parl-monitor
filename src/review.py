"""Review-file round-trip (handoff sections 7, 8).

Score>=2 items land in a human-editable checklist `review-<week>.md`. The human
sets PRIORITY (ACT/WATCH/NOTE), OWNER and WHY per item; those edits are parsed
back and written to the items table, and the edition is then rendered from the
store. Score-0 items are logged to `discards` for the monthly false-negative
review. A blank PRIORITY means "drop from this edition".

The stub triage scores tier-1/watchlist items 2 and tier-2 items 1, so only
tier-1 and watchlist items reach the review file until the live triage pass
elevates tier-2 items.
"""

from __future__ import annotations

import json
import os

VALID_TAGS = ("ACT", "WATCH", "NOTE")

REVIEW_HEADER = """# Review checklist for the edition of {week}

Edit each item below, then run the render step.
- PRIORITY: one of ACT, WATCH, NOTE. Leave blank to DROP the item from this edition.
- OWNER: required for ACT (render is refused otherwise).
- WHY: one line, <=35 words, CitizenGO voice, British spelling, no em dashes.

Do not edit the `### item:` id lines.

---
"""


def suggested_tag(tier):
    """A gentle default the human can override (never ACT: ACT needs an owner)."""
    return "WATCH" if tier in (1, None) else "NOTE"


def generate_review_file(conn, week, path):
    """Write the checklist of score>=2, not-yet-reviewed items for the edition.

    Merge-preserving: if the file already exists, PRIORITY/OWNER/WHY the human
    has set are carried into the regenerated file, never overwritten. A pull
    re-run must not cost the reviewer their morning's decisions.
    """
    existing = {}
    if os.path.exists(path):
        try:
            existing = {d.item_id: d for d in parse_review_file(path)}
        except Exception:
            existing = {}

    rows = conn.execute(
        "SELECT id, source_feed, title, issue_areas, matched_terms, tier, triage_score, why_it_matters "
        "FROM items WHERE triage_score >= 2 AND priority_tag IS NULL ORDER BY source_feed, id"
    ).fetchall()

    blocks = [REVIEW_HEADER.format(week=week)]
    for r in rows:
        areas = ", ".join(str(a) for a in json.loads(r["issue_areas"] or "[]"))
        matched = ", ".join(json.loads(r["matched_terms"] or "[]"))
        blocks.append("### item: {0}".format(r["id"]))
        blocks.append("- feed: {0} | areas: {1} | score: {2}".format(r["source_feed"], areas, r["triage_score"]))
        blocks.append("- matched: {0}".format(matched))
        blocks.append("- title: {0}".format(r["title"]))
        prior = existing.get(r["id"])
        blocks.append("PRIORITY: {0}".format(
            (prior.priority if prior and prior.priority else None) or suggested_tag(r["tier"])))
        blocks.append("OWNER: {0}".format(prior.owner if prior and prior.owner else ""))
        blocks.append("WHY: {0}".format(
            (prior.why if prior and prior.why else None) or r["why_it_matters"] or ""))
        blocks.append("")

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(blocks))
    return path, len(rows)


def _value(line, key):
    return line.split(":", 1)[1].strip() if line.lower().startswith(key + ":") else None


def parse_review_file(path):
    """Parse an edited review file into a list of edits."""
    edits = []
    current = None
    with open(path, "r", encoding="utf-8") as handle:
        for raw in handle:
            line = raw.rstrip("\n")
            if line.startswith("### item:"):
                if current:
                    edits.append(current)
                current = {"id": line.split("item:", 1)[1].strip(),
                           "priority": None, "owner": None, "why": None}
            elif current is not None:
                for key in ("priority", "owner", "why"):
                    got = _value(line, key)
                    if got is not None:
                        current[key] = got
    if current:
        edits.append(current)
    return edits


def apply_review(conn, edits):
    """Write edits back to items. Returns (kept, dropped)."""
    kept, dropped = 0, 0
    for e in edits:
        priority = (e.get("priority") or "").upper()
        if priority not in VALID_TAGS:
            dropped += 1
            continue
        conn.execute(
            "UPDATE items SET priority_tag = ?, owner = ?, why_it_matters = ? WHERE id = ?",
            (priority, e.get("owner") or None, e.get("why") or None, e["id"]),
        )
        kept += 1
    conn.commit()
    return kept, dropped


def apply_draft_defaults(conn):
    """--draft: promote unreviewed score>=2 items with the suggested tag."""
    rows = conn.execute(
        "SELECT id, tier, why_it_matters, title FROM items WHERE triage_score >= 2 AND priority_tag IS NULL"
    ).fetchall()
    for r in rows:
        conn.execute(
            "UPDATE items SET priority_tag = ?, why_it_matters = ? WHERE id = ?",
            (suggested_tag(r["tier"]), r["why_it_matters"] or r["title"], r["id"]),
        )
    conn.commit()
    return len(rows)


def log_discards(conn, week, discard_rows):
    """Record score-0 items for the monthly false-negative review."""
    for item_id, title, matched_terms in discard_rows:
        conn.execute("INSERT INTO discards (edition, item_id, title, matched_terms) VALUES (?, ?, ?, ?)",
                     (week, item_id, title, matched_terms))
    conn.commit()
