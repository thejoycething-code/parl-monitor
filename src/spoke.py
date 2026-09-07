"""Who spoke, and which way: the debates of a week, speaker by speaker.

Christopher, 2026-09-07: "Build the 'Who spoke, and which way' feature."

Reads only. Speeches are already in the ledger (mp_events kind='debate',
ref 'hansard:<contribution id>') and already scored by the stance pass
(stance.stance -2..+2 with a one-line why). What was missing was a view
that put them together per debate. The debate's title, house and public
URL come from the raw Hansard search payloads under data/raw, which carry
the DebateSectionExtId the deep link needs; when the archive has no row
for a contribution the ledger line ("Spoke: <title>") stands in and the
row is unlinked rather than dropped.

A member who spoke several times in one debate is one row, carrying the
count and the strongest-scored contribution's direction and reason.
"""

from __future__ import annotations

import re

from src import quotes

_LINE = re.compile(r"^Spoke: (?P<title>.*?)(?: \(re: [^)]*\))?$")


def _title_from_line(line):
    m = _LINE.match(line or "")
    return (m.group("title") if m else (line or "")).strip()


def rows_for_window(conn, start, end):
    return conn.execute(
        "SELECT e.member_id, e.date, e.ref, e.line, e.areas, "
        "m.name, m.party, m.seat, m.house, s.stance, s.why "
        "FROM mp_events e "
        "LEFT JOIN members m ON m.id = e.member_id "
        "LEFT JOIN stance s ON s.ref = e.ref "
        "WHERE e.kind = 'debate' AND e.date >= ? AND e.date <= ? "
        "AND e.areas IS NOT NULL AND e.areas != '[]' "
        "ORDER BY e.date, e.line, m.name", (start, end)).fetchall()


def collect(conn, start, end, root=None, raw=None):
    """-> [ {title, house, date, url, speakers: [ {member_id, name, party,
    seat, stance, why, url, count} ]} ], one block per debate."""
    try:
        rows = rows_for_window(conn, start, end)
    except Exception:                                       # noqa: BLE001
        return []                                           # no stance table yet: nothing to say
    if not rows:
        return []
    if raw is None and root:
        try:
            raw = quotes.RawHansard(root)
        except Exception:                                   # noqa: BLE001
            raw = None
    blocks = {}
    for r in rows:
        meta = (raw.get(r["ref"])[1] if raw else None) or {}
        debate_id = meta.get("debate_id") or None
        title = (meta.get("debate") or _title_from_line(r["line"])).strip()
        house = meta.get("house") or r["house"]
        date = meta.get("date") or r["date"]
        key = debate_id or (date, title.lower())
        b = blocks.setdefault(key, {
            "title": title, "house": house, "date": date,
            "url": ("https://hansard.parliament.uk/{0}/{1}/debates/{2}/".format(house, date, debate_id)
                    if debate_id and house and date else None),
            "_speakers": {}})
        contrib_url = raw.url(r["ref"]) if raw else None
        stance = r["stance"]
        entry = {"member_id": r["member_id"], "name": r["name"], "party": r["party"],
                 "seat": r["seat"], "stance": stance, "why": r["why"], "url": contrib_url, "count": 1}
        s = b["_speakers"].get(r["member_id"])
        if s is None:
            b["_speakers"][r["member_id"]] = entry
        else:
            s["count"] += 1
            if stance is not None and (s["stance"] is None or abs(stance) > abs(s["stance"])):
                s.update({"stance": stance, "why": r["why"], "url": contrib_url or s["url"]})
    out = []
    for b in blocks.values():
        b["speakers"] = sorted(b.pop("_speakers").values(), key=lambda s: (s["name"] or ""))
        out.append(b)
    out.sort(key=lambda b: (b["date"] or "", b["title"]))
    return out
