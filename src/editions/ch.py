"""Switzerland: the Nationalrat and the Staenderat, from the ch_* tables
(src/ch_store.py, tools/ch_rollcalls.py).

Items: every business (Geschaeft / objet) on our ground. The collector
matched the German text with taxonomy-atch and the French with taxonomy-fr,
both for `ch`, and since CH6 (10 October 2026) the Italian with Italy's
taxonomy-it for `ch`, plus config/watchlist-ch.yaml by Geschaeftsnummer.
taxonomy-it is deliberately not in COUNTRY.taxonomies: the noise filters
re-read German and French titles with those lists, where Italian terms are
false friends ("IVG"); an Italian matched term still counts as a distinct
term. A business submitted in the window is new
(questions, interpellations and Fragestunde questions have their own
section); an older motion, postulate, initiative or Federal Council
business whose status changed in the window is a stage move, with the
status in the Parliament's own German words. Items are keyed on the printed
number ('25.3944'), so the watchlist, written in Geschaeftsnummern
(20253944), is re-keyed here.

Votes: both councils record every member's position, with the Fraktion at
the vote, so each vote carries its tally, the Fraktion split and the
members who voted against their Fraktion's majority. The Nationalrat
publishes no totals and no result: its counts are tallied from the stored
positions and no result is shown; the Staenderat's spreadsheets publish
both. A business's votes (articles, the Gesamtabstimmung) are one group,
the Gesamtabstimmung or Schlussabstimmung decisive.

No agenda is collected, so there is no week ahead.
"""

from __future__ import annotations

from src import ch_store
from src import country_edition as ce

CURIA = "https://www.parlament.ch/de/ratsbetrieb/suche-curia-vista/geschaeft?AffairId={0}"
POS_YES, POS_NO, POS_ABST = ("ja",), ("nein",), ("enthaltung",)
COUNCIL = {"NR": "Nationalrat", "SR": "Ständerat"}
# The Fraktionen as the Parliament abbreviates them.
FRAKTION = {"V": "SVP", "S": "SP", "RL": "FDP", "M-E": "Mitte-EVP", "G": "Grüne",
            "GL": "GLP"}
NO_LINE = ("Fraktionslos",)
TYPES = {
    "Mo.": "Motion", "Po.": "Postulate", "Ip.": "Interpellation",
    "D.Ip.": "Urgent interpellation", "Fra.": "Question for the Fragestunde",
    "A": "Written question (Anfrage)", "DA": "Urgent written question (dringliche Anfrage)",
    "Pa. Iv.": "Parliamentary initiative", "Kt. Iv.": "Cantonal initiative",
    "BRG": "Federal Council business", "Pet.": "Petition",
    "PAG": "Parliamentary business (Geschäft des Parlaments)",
}
QUESTIONS = ("Ip.", "D.Ip.", "Fra.", "A", "DA")
FINAL = ("gesamtabstimmung", "schlussabstimmung", "vote sur l'ensemble", "vote final")
PLACEHOLDER = ("titel folgt", "titre suit")


def business_url(business_id):
    return CURIA.format(int(business_id)) if business_id else None


def title_of(de, fr):
    """The German title, or the French while the German is a placeholder."""
    de, fr = ce.clean(de), ce.clean(fr)
    if not de or de.lower().strip(" .") in PLACEHOLDER:
        return fr or de
    return de


def second_title(de, fr):
    """The French title as a line, when it is not the one shown."""
    shown = title_of(de, fr)
    fr = ce.clean(fr)
    if fr and fr != shown and fr.lower().strip(" .") not in PLACEHOLDER:
        return "French title: *{0}*".format(ce.clip(fr, 300))
    return None


def watchlist(config_dir=None):
    """{printed number: entry}: config/watchlist-ch.yaml, re-keyed from the
    Geschaeftsnummer (20253944) to the number items carry ('25.3944')."""
    out = {}
    for k, v in ce.watchlist_file("ch", config_dir).items():
        try:
            out[ch_store.short_number(int(k))] = v
        except (TypeError, ValueError):
            out[str(k)] = v
    return out


def _businesses(conn, since, until, wl):
    out = []
    for r in ce.rows(conn, "SELECT * FROM ch_businesses WHERE ({0}) OR ({1})".format(
            ce.window_sql("submission_date"), ce.window_sql("status_date")),
            (since, until, since, until)):
        key = r["short_number"] or ch_store.short_number(r["business_id"])
        w = key in wl
        if not ce.on_ground(r["areas"], w):
            continue
        new = since < ce.day(r["submission_date"]) <= until
        question = r["business_type"] in QUESTIONS
        if question and not new:
            continue                     # a question's later step is its answer
        kind = "question" if question else ("new" if new else "moved")
        take = "{0} {1}".format(TYPES.get(r["business_type"], r["business_type"] or "Business"),
                                key)
        if r["submitted_by"]:
            take += ", submitted by {0}".format(ce.clean(r["submitted_by"]))
        if r["submission_council"]:
            take += " in the {0}".format(COUNCIL.get(r["submission_council"],
                                                     r["submission_council"]))
        if kind == "moved" and r["status_date"]:
            take += "; status changed on {0}".format(ce.long_date(ce.day(r["status_date"])))
        out.append(ce.item("ch", kind, key, r["submission_date"] if new else r["status_date"],
                           title_of(r["title_de"], r["title_fr"]), ce.areas_of(r["areas"]),
                           r["tier"], w, status=r["status"], url=business_url(r["business_id"]),
                           terms=r["matched_terms"], takeaway=take,
                           lines=[ln for ln in [second_title(r["title_de"], r["title_fr"])] if ln]))
    return out


def _vote_title(r):
    return ce.clean(r["subject"]) or ce.clean(r["meaning_yes"]) or "Abstimmung"


def _votes(conn, since, until, wl):
    out = []
    for r in ce.rows(conn, "SELECT d.*, b.title_de, b.title_fr, b.business_type FROM "
                           "ch_divisions d LEFT JOIN ch_businesses b USING (business_id) WHERE "
                           + ce.window_sql("d.date"), (since, until)):
        key = r["short_number"] or (ch_store.short_number(r["business_id"])
                                    if r["business_id"] else None)
        w = bool(key) and key in wl
        if not ce.on_ground(r["areas"], w):
            continue
        council = COUNCIL.get(r["council"], r["council"])
        got = ce.rows(conn, "SELECT v.person_number, m.first_name, m.last_name, v.parl_group, v.position FROM "
                            "ch_votes v LEFT JOIN ch_members m USING (person_number) "
                            "WHERE v.division_key=?", (r["division_key"],))
        pairs = [("{0} {1}".format(v["first_name"] or "", v["last_name"] or "").strip() or str(v["person_number"]),
                  FRAKTION.get(v["parl_group"], v["parl_group"]), v["position"]) for v in got]
        if r["yes"] is None and r["no"] is None:
            lines = ["Tally: not available yet; the member positions behind it were not "
                     "read (the next weekly run fetches them)."]
        elif r["counts_from"] == "tallied":
            lines = [ce.tally_line(r["yes"], r["no"], r["abstain"], None,
                                   "tallied from the members' positions; the Nationalrat "
                                   "publishes no result")]
        else:
            lines = [ce.tally_line(r["yes"], r["no"], r["abstain"], r["result"],
                                   "{0}, as published".format(council))]
        title = _vote_title(r)
        yes_m, no_m = ce.clean(r["meaning_yes"]), ce.clean(r["meaning_no"])
        if yes_m and yes_m != title:
            lines.append("A yes meant: “{0}”{1}".format(
                yes_m, "; a no: “{0}”.".format(no_m) if no_m else "."))
        elif no_m:
            lines.append("A no meant: “{0}”.".format(no_m))
        if pairs:
            lines.append(ce.split_line(ce.group_counts([(g, p) for _, g, p in pairs],
                                                       POS_YES, POS_NO, POS_ABST),
                                       "By Fraktion"))
            lines.append(ce.members_line(len(pairs), ce.rebels(pairs, POS_YES, POS_NO,
                                                               skip=NO_LINE),
                                         "Fraktion as printed on the vote."))
        what = TYPES.get(r["business_type"], r["business_type"] or "business")
        take = "{0}, on {1} {2}".format(council, what[0].lower() + what[1:], key or "")
        if r["draft_title"]:
            take += " (draft: {0})".format(ce.clip(r["draft_title"], 120))
        areas = ce.areas_of(r["areas"])
        if w and not areas:              # a watched business the store has not read
            areas = ce.areas_of((wl.get(key) or {}).get("areas") or [])
        out.append(ce.vote("ch", r["division_key"], r["date"], title, areas,
                           r["tier"], w, lines, url=business_url(r["business_id"]),
                           terms=r["matched_terms"], takeaway=take.strip(),
                           own=bool(ce.areas_of(r["own_areas"])),
                           group="{0}:{1}".format(r["council"], key) if key else None,
                           group_title=title_of(r["title_de"], r["title_fr"]),
                           final=any(f in title.lower() for f in FINAL),
                           watch_key=key if w else None))
    return out


def items(conn, since, until, wl):
    return _businesses(conn, since, until, wl) + _votes(conn, since, until, wl)


COUNTRY = ce.Country(
    cc="ch", name="Switzerland", chamber="Nationalrat and Ständerat", language="German or French",
    taxonomies=(("taxonomy-atch.yaml", "ch"), ("taxonomy-fr.yaml", "ch")),
    items=items, watchlist=watchlist, flag=":flag-ch:",
    members_note=("Both councils record every member's position, with the Fraktion at the vote; "
                  "the Nationalrat's tallies are counted from those positions"),
    coverage=("Businesses and Nationalrat votes come from the Parliament's OData service; "
              "Ständerat votes from its session spreadsheets.",
              "Matched on German (taxonomy-atch), French (taxonomy-fr) and, since CH6, Italian "
              "(taxonomy-it, Italy's list without its Italy-only terms) texts.",
              "Statuses are the Parliament's own German words. Cantonal parliaments and federal "
              "popular votes are later phases."),
)
