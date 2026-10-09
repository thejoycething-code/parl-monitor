"""Austria: the Nationalrat and Bundesrat, from the at_* tables
(src/at_store.py, tools/at_rollcalls.py).

Items: every Verhandlungsgegenstand on our ground (taxonomy-atch for `at`,
plus config/watchlist-at.yaml by key). Bills and motions introduced in the
week are new; older ones whose latest parliamentary step fell in the week
are stage moves; written questions and their answers have their own
sections; committee reports theirs.

Votes are recorded BY KLUB: the record names the Klubs for and against,
never the members. Per X5 each member is given their Klub's position, and
the edition says so: DERIVED, with the Klub at the member's latest
sighting (at_store.derived_member_positions). One floor vote is recorded on
every item it touched (a Regierungsvorlage, its committee report and the
Abänderungsantrag share an anchor in the protocol), so votes are folded by
(sitting, anchor) and shown once, on the watched or government item.
"""

from __future__ import annotations

from src import at_store
from src import country_edition as ce

SITE = "https://www.parlament.gv.at"

# The Parliament's item types (art), in English.
ART = {
    "RV": "Government bill (Regierungsvorlage)",
    "A": "Members' bill (Selbständiger Antrag)",
    "A(E)": "Motion for a resolution (Entschließungsantrag)",
    "UEA": "Motion for a resolution moved in plenary",
    "AA": "Amendment moved in plenary (Abänderungsantrag)",
    "AAA": "Amendment moved in committee",
    "EAA": "Motion for a resolution moved in committee",
    "AEA": "Committee motion for a resolution (Ausschussentschließungsantrag)",
    "AUB": "Committee report (Ausschussbericht)",
    "BNR": "Nationalrat decision sent to the Bundesrat",
    "E": "Resolution (Entschließung)",
    "J": "Written question (schriftliche Anfrage)",
    "M": "Oral question (mündliche Anfrage)",
    "AB": "Answer to a written question (Anfragebeantwortung)",
    "BRH": "Court of Audit report",
    "BS": "Other decision",
    "APNR": "Amendment made in the Nationalrat plenary",
    "VER": "Report",
}
QUESTIONS = ("J", "M")
ANSWERS = ("AB",)
REPORTS = ("AUB",)
FINAL = ("dritter lesung", "keinen einspruch")


def art_text(art):
    base = (art or "").replace("-BR", "")
    text = ART.get(base) or art or "Item"
    return text + (" in the Bundesrat" if (art or "").endswith("-BR") else "")


def kind_of(art):
    base = (art or "").replace("-BR", "")
    if base in QUESTIONS:
        return "question"
    if base in ANSWERS:
        return "answer"
    if base in REPORTS:
        return "report"
    return None


def status_text(status):
    if status == 5:
        return "concluded (stage 5 of 5)"
    if status == 1:
        return "received (stage 1 of 5)"
    if status:
        return "in progress (stage {0} of 5)".format(status)
    return None


def item_url(key):
    return "{0}/gegenstand/{1}".format(SITE, key)


def _items(conn, since, until, wl):
    out = []
    win = ce.window_sql("introduced")
    moved = ce.window_sql("last_date")
    for r in ce.rows(conn, "SELECT * FROM at_items WHERE ({0}) OR ({1})".format(win, moved),
                     (since, until, since, until)):
        w = r["item_key"] in wl
        if not ce.on_ground(r["areas"], w):
            continue
        new = since < ce.day(r["introduced"]) <= until
        kind = kind_of(r["art"]) or ("new" if new else "moved")
        if kind in ("question", "answer", "report") and not new:
            continue                    # a question's later steps are its answer
        date = r["introduced"] if new else r["last_date"]
        take = art_text(r["art"])
        if r["citation"]:
            take += ", {0}".format(r["citation"])
        st = status_text(r["status"])
        if kind == "moved":
            take += "; latest parliamentary step on {0}".format(ce.long_date(ce.day(r["last_date"])))
        if st:
            take += "; {0}".format(st)
        out.append(ce.item("at", kind, r["item_key"], date, r["title"], ce.areas_of(r["areas"]),
                           r["tier"], w, url=item_url(r["item_key"]), terms=r["matched_terms"],
                           takeaway=take))
    return out


ART_RANK = ("RV", "A", "A(E)", "UEA", "AUB", "BNR", "AA", "AAA")


def _rank(row, wl):
    art = (row["art"] or "").replace("-BR", "")
    return (row["item_key"] not in wl,
            ART_RANK.index(art) if art in ART_RANK else len(ART_RANK), row["item_key"])


def _votes(conn, since, until, wl):
    got = ce.rows(conn, "SELECT d.*, i.title AS item_title, i.art, i.tier, i.matched_terms, "
                        "i.areas AS item_areas FROM at_divisions d JOIN at_items i USING (item_key) "
                        "WHERE " + ce.window_sql("d.date"), (since, until))
    # One floor or committee vote, recorded on several items: keep one row.
    best = {}
    for r in got:
        anchor = r["division_key"].split("@", 1)[-1]
        if anchor not in best or _rank(r, wl) < _rank(best[anchor], wl):
            best[anchor] = r
    out = []
    for anchor, r in best.items():
        w = r["item_key"] in wl
        areas_raw = r["areas"] or r["item_areas"]
        if not ce.on_ground(areas_raw, w):
            continue
        sides = {"Dafür": [], "Dagegen": []}
        for v in ce.rows(conn, "SELECT klub, position FROM at_votes WHERE division_key=? "
                               "ORDER BY klub", (r["division_key"],)):
            sides.setdefault(v["position"], []).append(v["klub"])
        result = r["outcome"] or ""
        if r["unanimous"]:
            result = (result + ", einstimmig").strip(", ")
        how = "Klub vote" if r["body"] in ("NR", "BR") else "committee vote, Klubs"
        if r["roll_call"]:
            how = "namentliche Abstimmung"
        derived = at_store.derived_member_positions(conn, r["division_key"])
        lines = [ce.tally_line(r["yes_count"], r["no_count"], None, result, how)
                 if r["roll_call"] else
                 "Result as recorded: “{0}” ({1}).".format(result or "?", how),
                 ce.side_line(sides.get("Dafür"), sides.get("Dagegen"), "By Klub"),
                 ce.derived_line(len(derived), "Klub vote; Klub at the member's latest sighting")]
        body = {"NR": "Nationalrat", "BR": "Bundesrat"}.get(r["body"], r["body"])
        question = ce.clean(r["question"]) or "Vote"
        url = SITE + r["protocol_url"] if (r["protocol_url"] or "").startswith("/") else \
            (r["protocol_url"] or item_url(r["item_key"]))
        what = art_text(r["art"])
        out.append(ce.vote("at", r["division_key"], r["date"], question, ce.areas_of(areas_raw),
                           r["tier"], w, lines, url=url, terms=r["matched_terms"],
                           takeaway="{0}, on {1} {2}".format(body, what[0].lower() + what[1:],
                                                             r["item_key"]),
                           group=r["item_key"], group_title=r["item_title"],
                           watch_key=r["item_key"],
                           final=any(f in question.lower() for f in FINAL)))
    return out


def items(conn, since, until, wl):
    return _items(conn, since, until, wl) + _votes(conn, since, until, wl)


COUNTRY = ce.Country(
    cc="at", name="Austria", chamber="Nationalrat and Bundesrat", language="German",
    taxonomies=(("taxonomy-atch.yaml", "at"),),
    items=items, flag=":flag-at:",
    members_note=("Votes are recorded by Klub only; member positions shown are DERIVED from "
                  "the Klub vote (X5), with the Klub at the member's latest sighting"),
    coverage=("Votes are read from the history pages of items on our ground; a namentliche "
              "Abstimmung's member names (phase 1b) are not read yet.",
              "Classification is on titles only (taxonomy-atch); the Parliament's Schlagworte "
              "are stored, not matched."),
)
