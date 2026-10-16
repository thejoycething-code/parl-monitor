"""A gov_docs mirror of consultations the petitions layer already stores
(country_petitions, src/petitions.py): Argentina's consultapublica (cp),
Brazil's Brasil Participativo (bp), Colombia's SUCOP drafts (sucop). One
read per week, in the petitions step; the gov_docs step re-files the rows
so the country countdown has one place to look (src/gov_docs.deadline_rows).

The module's name starts with "_" so src/gov_docs.countries() skips it.
"""

from __future__ import annotations

from src import gov_docs as G


def mirror_for(source, doc_type, body=None):
    """A mirror function (conn, cc, today) re-filing country_petitions rows of
    one source as gov_docs entries of `doc_type`."""

    def mirror(conn, cc, today):
        start = G.window_start(today)
        try:
            rows = conn.execute(
                "SELECT item_id, title, summary, text, status, opened, closes, body, url, last_seen "
                "FROM country_petitions WHERE cc = ? AND source = ? AND (closes >= ? OR opened >= ? "
                "OR (closes IS NULL AND last_seen >= ?))", (cc, source, start, start, start)).fetchall()
            ever = conn.execute("SELECT COUNT(*), MAX(last_seen) FROM country_petitions WHERE cc = ? "
                                "AND source = ?", (cc, source)).fetchone()
        except Exception as exc:                        # noqa: BLE001
            return G.fetched([], gaps=["country_petitions unreadable: {0}".format(str(exc)[:160])])
        out = []
        for r in rows:
            own = str(r[0]).split(":", 1)[-1]
            out.append(G.entry(source, own, r[1], doc_type, body=r[7] or body, published=r[5],
                               closing_date=r[6], url=r[8], summary=r[2] or r[3], status=r[4]))
        gaps = []
        if not ever or not ever[0]:
            gaps.append("country_petitions holds no '{0}' rows for {1} (has the petitions step "
                        "run?)".format(source, cc))
        return G.fetched(out, gaps=gaps, note="mirrored from country_petitions source '{0}' "
                         "(last read {1})".format(source, ever[1] if ever else None))

    return mirror
