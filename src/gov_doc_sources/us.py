"""United States: the Federal Register, mirrored from us_fr_documents.

tools/us_federal_register.py (jobs/us-weekly.sh) already reads
www.federalregister.gov/api/v1/documents.json (a documented, keyless API,
src/robots_guard.DOCUMENTED_APIS) every week and classifies each document
with the shared taxonomy. The gov_docs layer re-files its rows rather than
fetching twice (Chris, 16 October 2026: "the repo has us_federal_register.py;
reuse"):

  * a Proposed Rule is a 'regulation_draft' whose closing_date is its
    comments_close_on (the comment deadline, as printed): a DEADLINE row in
    the countdown when it is on our ground;
  * a Rule is a 'regulation'; a Presidential Document (executive order,
    proclamation, memorandum) a 'publication', the body named "The President".

The collector's own classification is kept (it matches the CFR index terms
too, with its boilerplate rule for 8 CFR), and the gov_docs precision gate
(a non-deadline document needs tier 1) applies on top, as everywhere else. The step runs after the collector in the US
weekly, so the mirror is this week's read.

Agency NOTICES are not read by the collector (about 10,000 since January
2025, nearly all permits, meetings and information collections); notices of
public listening sessions on our ground would be a later addition.
"""

from __future__ import annotations

import json

from src import gov_docs as G

CC = "us"
TAXONOMIES = (("taxonomy.yaml", None),)
FR = "https://www.federalregister.gov/documents/"
TYPES = {"Proposed Rule": "regulation_draft", "Rule": "regulation",
         "Presidential Document": "publication"}


def _agencies(raw):
    try:
        got = json.loads(raw) if raw else []
    except (TypeError, ValueError):
        return None
    return "; ".join(str(a) for a in got if a) or None


def mirror(conn, cc, today):
    start = G.window_start(today)
    try:
        rows = conn.execute(
            "SELECT document_number, doc_type, subtype, title, abstract, action, agencies, "
            "publication_date, comments_close_on, html_url, areas, matched_terms, tier FROM us_fr_documents WHERE "
            "publication_date >= ? OR comments_close_on >= ?", (start, today)).fetchall()
    except Exception as exc:                                # noqa: BLE001
        return G.fetched([], gaps=["us_fr_documents unreadable: {0}".format(str(exc)[:160])])
    out = []
    for r in rows:
        kind = TYPES.get(r[1])
        if not kind:
            continue
        body = "The President" if r[1] == "Presidential Document" else _agencies(r[6])
        summary = " ".join(x for x in (r[5], r[4]) if x)
        out.append(G.entry("fr", r[0], r[3], kind, body=body, published=r[7],
                           closing_date=r[8] if kind == "regulation_draft" else None,
                           url=r[9] or FR + r[0], summary=summary,
                           status=r[2] or r[1], classified=(r[10], r[11], r[12])))
    last = conn.execute("SELECT MAX(last_seen) FROM us_fr_documents").fetchone()[0] \
        if rows is not None else None
    gaps = []
    if not rows:
        gaps.append("us_fr_documents holds nothing in the window (has the Federal Register step run?)")
    return G.fetched(out, note="mirrored from us_fr_documents (last read {0})".format(last),
                     gaps=gaps)


SOURCES = (
    G.Source(code="fr", name="Federal Register (proposed rules, rules, presidential documents)",
             url="https://www.federalregister.gov/api/v1/documents.json", mirror=mirror),
)
