"""Germany: the Bundestag, from the de_* tables (tools/de_rollcalls.py,
tools/de_documents.py), as a READER for the shared country frameworks.

Added 16 October 2026 (branch de-ca-gaps). The German edition is NOT
rendered from this adapter: tools/de_monitor.py keeps rendering and sending
its own edition (editions/de-monitor-<date>.md), in its own Westminster
frame. This module exists so the frameworks built for the new countries can
read Germany exactly as they read the others:

  * the same-day vote briefs (src/country_vote_brief.py), after the Sunday
    weekly and from the daily direct reader (src/vote_brief_sources.DE);
  * the daily sweep of new items (src/country_day_sweep.py), from DIP's
    Vorgänge and the Bundestag's agenda (src/day_sweep_sources.DE,
    src/agendas/de.py);
  * the shared agenda collector (tools/country_agenda.py de), which takes
    its taxonomy from here;
  * member profiles (src/member_profiles.py, profiles/de/).

ITEMS, Bundestag only (the Land votes stay the edition's own section):

  * recorded votes (namentliche Abstimmungen, abgeordnetenwatch): every
    member's position as recorded ('yes', 'no', 'abstain', 'no_show') with
    the member's Fraktion as the store keeps it (abgeordnetenwatch names it
    at each vote; de_members keeps the latest, so a member who changed
    Fraktion shows the new one), the Fraktion split, and the
    members who voted against their Fraktion's majority (fraktionslos
    members have no line to break). The result is the House's own outcome
    (field_accepted: 'angenommen' / 'abgelehnt'), never derived from the
    tallies. A vote on our ground by its label, the API's topics, or the
    Drucksache it inherited them from (de_divisions.areas).
  * DIP Vorgänge on our ground (taxonomy-de): bills, motions, EU items and
    reports first seen in the window are new; questions (Schriftliche,
    Mündliche Frage, Kleine and Große Anfrage) are questions; a Vorgang
    whose stage changed in the window is a stage move.
  * the week ahead: the shared agenda table (country_agenda, cc 'de',
    src/agendas/de.py): the plenary Tagesordnung and committee sittings.

Same classification as the edition: the store's own areas from
config/taxonomy-de.yaml (signed off by Chris on 29 September 2026; the
German team may still refine it), never a keyword of our own here.
"""

from __future__ import annotations

import datetime

from src import agenda
from src import country_edition as ce

BUNDESTAG = "5"              # abgeordnetenwatch's parliament id
QUESTION_TYPES = ("Schriftliche Frage", "Kleine Anfrage", "Mündliche Frage", "Große Anfrage")
NEW_TYPES_SKIP = ("Besetzung externer Gremien durch BT", "Besetzung interner Gremien des BT",
                  "Wahl des Präsidiums BR", "Immunitätsangelegenheit")
FRESH_DAYS = 30              # a Vorgang first seen now but dated long ago is a backfill
POS_YES, POS_NO = ("yes",), ("no",)
OUTCOME = {1: "angenommen", 0: "abgelehnt"}
TYPE_EN = {
    "Gesetzgebung": "Bill (Gesetzgebung)",
    "Antrag": "Motion (Antrag)",
    "Entschließungsantrag BT": "Motion for a resolution (Entschließungsantrag)",
    "EU-Vorlage": "EU proposal (EU-Vorlage)",
    "Rechtsverordnung": "Statutory instrument (Rechtsverordnung)",
    "Schriftliche Frage": "Written question (Schriftliche Frage)",
    "Mündliche Frage": "Oral question (Mündliche Frage)",
    "Kleine Anfrage": "Minor interpellation (Kleine Anfrage)",
    "Große Anfrage": "Major interpellation (Große Anfrage)",
    "Bericht, Gutachten, Programm": "Report (Bericht, Gutachten, Programm)",
    "Aktuelle Stunde": "Topical debate (Aktuelle Stunde)",
}


def clean_party(name):
    """The Fraktion label without the soft hyphen abgeordnetenwatch keeps
    ('BÜNDNIS 90/\\xadDIE GRÜNEN')."""
    return ce.clean((name or "").replace("­", "")) or None


def dip_url(vorgang_id, titel=None):
    """tools/de_monitor._dip: DIP's /vorgang/<slug>/<id> route (the bare id
    bounces to the home page)."""
    import re
    slug = re.sub(r"[^a-z0-9]+", "-", (titel or "").lower().replace("ä", "ae")
                  .replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")).strip("-")[:60]
    return "https://dip.bundestag.de/vorgang/{0}/{1}".format(slug.rstrip("-") or "vorgang",
                                                             vorgang_id)


def poll_url(vote_id):
    return "https://www.abgeordnetenwatch.de/api/v2/polls/{0}".format(vote_id)


def _fresh(datum, until):
    try:
        return (datetime.date.fromisoformat(until)
                - datetime.date.fromisoformat(ce.day(datum))).days <= FRESH_DAYS
    except (TypeError, ValueError):
        return True


def _vorgaenge(conn, since, until, wl):
    out = []
    for r in ce.rows(conn, "SELECT * FROM de_vorgaenge WHERE ({0}) OR ({1})".format(
            ce.window_sql("first_seen"), ce.window_sql("moved_date")),
            (since, until, since, until)):
        key = str(r["vorgang_id"])
        w = key in wl
        if not ce.on_ground(r["areas"], w):
            continue
        typ = r["vorgangstyp"] or ""
        new = since < ce.day(r["first_seen"]) <= until and _fresh(r["datum"], until)
        moved = bool(r["moved_date"]) and since < ce.day(r["moved_date"]) <= until
        if typ in QUESTION_TYPES:
            if not new:
                continue                    # a question's later step is its answer
            kind = "question"
        elif new:
            if typ in NEW_TYPES_SKIP:
                continue
            kind = "new"
        elif moved:
            kind = "moved"
        else:
            continue
        take = TYPE_EN.get(typ, typ or "Vorgang")
        if r["initiative"]:
            take += "; brought by {0}".format(ce.clip(r["initiative"], 120))
        if kind == "moved":
            take += "; stage {0} -> {1}".format(r["prev_stand"] or "?", r["stand"] or "?")
        elif r["stand"]:
            take += "; stage: {0}".format(r["stand"])
        date = r["moved_date"] if kind == "moved" else (r["datum"] or r["first_seen"])
        out.append(ce.item("de", kind, key, ce.day(date), r["titel"], ce.areas_of(r["areas"]),
                           r["tier"], w, status=r["stand"], url=dip_url(key, r["titel"]),
                           terms=r["matched_terms"], takeaway=take))
    return out


def positions(conn, vote_id):
    """[(name, Fraktion, position)] as stored for one Bundestag vote."""
    return [(r["name"], clean_party(r["party"]), r["position"]) for r in ce.rows(
        conn, "SELECT COALESCE(m.name, v.person_id) AS name, m.party, v.position FROM de_votes v "
              "LEFT JOIN de_members m ON m.person_id = v.person_id WHERE v.vote_id = ? "
              "ORDER BY m.name", (vote_id,))]


def _votes(conn, since, until, wl):
    out = []
    for r in ce.rows(conn, "SELECT * FROM de_divisions WHERE parliament = ? AND " +
                     ce.window_sql("date") + " ORDER BY date, vote_id",
                     (BUNDESTAG, since, until)):
        key = str(r["vote_id"])
        w = key in wl
        if not ce.on_ground(r["areas"], w):
            continue
        pos = positions(conn, key)
        groups = ce.group_counts([(g, p) for _n, g, p in pos], POS_YES, POS_NO, ("abstain",))
        reb = ce.rebels(pos, POS_YES, POS_NO)
        lines = [ce.tally_line(r["yes"], r["no"], r["abstain"], OUTCOME.get(r["accepted"]),
                               "namentliche Abstimmung"),
                 ce.split_line(groups, "By Fraktion"),
                 ce.members_line(len(pos), reb)]
        if r["absent"]:
            lines.append("{0} member(s) did not vote (as recorded: no_show).".format(r["absent"]))
        take = "Bundestag recorded vote"
        if r["committee"]:
            take += "; committee: {0}".format(ce.clip(r["committee"], 120))
        if r["inherited_from"]:
            take += "; areas from the Drucksache it voted on"
        out.append(ce.vote("de", key, r["date"], r["label"], ce.areas_of(r["areas"]), r["tier"],
                           w, lines, url=r["document_url"] or poll_url(key),
                           terms=r["matched_terms"], takeaway=take, final=True,
                           own=False if r["inherited_from"] else None,
                           positions=pos, rebels=reb))
    return out


def items(conn, since, until, wl):
    return _vorgaenge(conn, since, until, wl) + _votes(conn, since, until, wl)


def petition_deadlines(conn, today, until, wl):
    """The countdown's DEADLINE rows (src/country_countdown.forward_items'
    timeline_extra hook, 16 October 2026): Bundestag e-petitions on our
    ground open for co-signature that close today to `until` (de_petitions,
    tools/de_petitions.py). A petition the German judge scored below the bar
    stays out, as in the edition (degate's floor); one on migration alone is
    never shown (ce.areas_of hides area 11)."""
    from src import degate
    try:
        got = ce.rows(conn, "SELECT * FROM de_petitions WHERE closes >= ? AND closes <= ? AND {0} "
                            "ORDER BY closes".format(degate.SHOWN_SQL), (today, until))
    except Exception:                                   # noqa: BLE001 - an older store
        return []
    out = []
    for r in got:
        areas = ce.areas_of(r["areas"])
        if not areas:
            continue
        it = ce.item("de", "agenda", "pet:de:" + str(r["petition_id"]), r["closes"][:10], r["title"],
                     areas, r["tier"], False, url=r["url"], terms=r["matched_terms"],
                     body=r["excerpt"] or "")
        it.update(where="DEADLINE", detail="petition closes (co-signature)", keys=[], deadline=True,
                  extra=None)
        if r["triage_score"] is not None:
            it["de_score"], it["de_why"] = r["triage_score"], r["why_it_matters"]
        out.append(it)
    return out


def watchlist(config_dir=None):
    """config/watchlist-de.yaml's `bills` (DIP Vorgang ids); empty today."""
    got = ce.watchlist_file("de", config_dir)
    return {str(k): v for k, v in (got or {}).items()}


COUNTRY = ce.Country(
    cc="de", name="Germany", chamber="Bundestag", language="German",
    taxonomies=(("taxonomy-de.yaml", None),),
    items=items,
    week_ahead=agenda.week_ahead_fn("de"),
    ahead_note=agenda.ahead_note_fn("de"),
    kinds=("vote", "new", "moved", "question"),
    watchlist=watchlist,
    members_note=("Bundestag recorded votes carry every member's position; the Fraktion is "
                  "the member's latest as stored."),
    flag=":flag-de:",
    timeline_extra=petition_deadlines,
)
