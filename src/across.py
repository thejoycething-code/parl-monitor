"""NOT RENDERED IN THE EDITION since 2026-09-07 (Christopher: "Remove the
'Across the parliaments' section from the edition"). Kept as a library:
the EU gap-build tests exercise collect()/render(), and the cross-store
query may yet serve a page. Nothing in run_weekly or digest calls it.

Across the parliaments: the same fight, seen in every chamber at once.

The system watches Westminster, Holyrood, the Senedd, the NI Assembly,
the European Parliament, the Commission, Strasbourg and the ECI register
-- as silos. The stories cross them: the RVE withdrawal right fell in
Wales, narrowed in Scotland and is under consultation in NI; message
scanning runs chat-control-EU against OSA-UK. This module renders the
crossings: any taxonomy area active in TWO OR MORE jurisdictions inside
the window earns a theme block, one line per jurisdiction, at most two
items each.

Read-only over every store table; the Westminster edition renders it as
"Across the parliaments" (Christopher wired EU into the Monday digest
deliberately here, 2026-09-02 -- the separation guarantee was about
accidental leakage, and this is neither accidental nor leakage).
"""

from __future__ import annotations

import datetime
import json

WINDOW_DAYS = 14


def _add(themes, area, jurisdiction, title, detail=""):
    if not area or not title:
        return
    themes.setdefault(area, {}).setdefault(jurisdiction, [])
    bucket = themes[area][jurisdiction]
    if len(bucket) < 2 and title not in [t for t, _ in bucket]:
        bucket.append((title, detail))


def collect(conn, today):
    """{area: {jurisdiction: [(title, detail), ...]}} for the window."""
    t = datetime.date.fromisoformat(today)
    since = (t - datetime.timedelta(days=WINDOW_DAYS)).isoformat()
    themes = {}

    def areas_of(raw):
        try:
            return [a for a in json.loads(raw or "[]") if isinstance(a, int)]
        except ValueError:
            return []

    # Westminster: this window's captured items -- tier 1 or scored 2+,
    # because a fortnight synthesis amplifies noise (a hospice charity
    # fundraiser reached the first draft through a tier-2 match).
    for r in conn.execute(
            "SELECT title, issue_areas FROM items WHERE captured_at >= ? "
            "AND issue_areas IS NOT NULL AND (tier = 1 OR "
            "COALESCE(triage_score, 0) >= 2)", (since,)):
        for a in areas_of(r["issue_areas"]):
            _add(themes, a, "Westminster", r["title"])
    # Devolved consultations still open.
    nations = {"scotland": "Scotland", "wales": "Wales", "ni": "N. Ireland"}
    for r in conn.execute(
            "SELECT nation, title, areas, closes FROM dg_consultations "
            "WHERE closes >= ? AND areas != '[]'", (today,)):
        for a in areas_of(r["areas"]):
            _add(themes, a, nations.get(r["nation"], r["nation"]),
                 r["title"], "consultation closes {0}".format(r["closes"]))
    # Devolved chambers: recent matched items.
    for table, name in (("sp_items", "Scotland"), ("sd_items", "Wales"),
                        ("ni_items", "N. Ireland")):
        try:
            rows = conn.execute(
                "SELECT title, areas FROM {0} WHERE dated >= ? AND "
                "areas IS NOT NULL AND areas != '[]' AND tier = 1"
                .format(table), (since,)).fetchall()
        except Exception:
            continue
        for r in rows:
            for a in areas_of(r["areas"]):
                _add(themes, a, name, r["title"])
    # The EU, all instruments.
    eu = [
        ("SELECT title, areas, 'feedback closes ' || closes AS d FROM "
         "eu_consultations WHERE closes >= ? AND areas != '[]'", (today,)),
        ("SELECT label AS title, areas, 'plenary ' || date AS d FROM "
         "eu_agenda WHERE date >= ? AND areas != '[]'", (today,)),
        ("SELECT label AS title, areas, 'voted ' || date AS d FROM "
         "eu_divisions WHERE date >= ? AND areas != '[]'", (since,)),
        ("SELECT title, areas, 'adopted ' || date AS d FROM eu_texts "
         "WHERE date >= ? AND areas != '[]'", (since,)),
        ("SELECT case_name AS title, areas, 'ECtHR ' || date AS d FROM "
         "eu_judgments WHERE date >= ? AND areas != '[]'", (since,)),
        ("SELECT title, areas, 'ECI, ' || COALESCE(supporters, 0) || "
         "' supporters' AS d FROM eu_ecis WHERE areas != '[]' AND "
         "status = 'ONGOING' AND ? = ?", (today, today)),
    ]
    for sql, params in eu:
        try:
            rows = conn.execute(sql, params).fetchall()
        except Exception:
            continue
        for r in rows:
            for a in areas_of(r["areas"]):
                _add(themes, a, "EU", r["title"], r["d"])
    return themes


def render(themes, area_names, min_jurisdictions=2):
    """Markdown for areas crossing jurisdictions; None when nothing crosses."""
    blocks = []
    for area in sorted(themes):
        js = themes[area]
        if len(js) < min_jurisdictions:
            continue
        lines = ["**{0}** ({1} jurisdictions)".format(
            area_names.get(area, str(area)), len(js))]
        for j in sorted(js):
            for title, detail in js[j]:
                lines.append("- {0}: {1}{2}".format(
                    j, title, " ({0})".format(detail) if detail else ""))
        blocks.append("\n".join(lines))
    if not blocks:
        return None
    return ("## Across the parliaments\n\n"
            "The same fight, wherever it is being fought this fortnight - "
            "an area appears here when two or more of the eight watched "
            "jurisdictions are active on it.\n\n"
            + "\n\n".join(blocks) + "\n")
