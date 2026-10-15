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

The week ahead is the councils' order of business from the sessions programme
(src/agendas/ch.py): empty between sessions, which the Coverage line says.

THE CANTONS (CH7, 13 October 2026): the cantonal parliaments read by
tools/ch_cantons.py (ch_canton_acts, ch_canton_divisions; Zuerich, Bern,
Geneva, Vaud, Ticino) are a "Cantons" section of their own after the
Watchlist (Country.extra_sections), never mixed into the Federal
Assembly's. An act is new by its submission date, or, in a canton that
prints none (Geneva, Vaud, Ticino), by the day we first saw it after that
canton's first read; otherwise it is a stage move by its status date. Bern's
votes come with their published tallies, grouped on the act they name.
Titles are verbatim in the canton's language. Basel-Stadt, Thurgau and
Basel-Landschaft (since 13 October 2026, from data.bs.ch, data.tg.ch and
data.bl.ch with written permission) carry members' votes (ch_canton_votes), shown as the federal
votes are (tally, Fraktion split, members against their Fraktion), and a
"Source:" line linking the dataset, as Basel-Stadt's CC BY licence asks.
Basel-Stadt's business items come, since the same day, from the Grand
Council's own raw data exports (grosserrat.bs.ch, offered by its
Parlamentsdienst): their "Source:" line links the Grand Council's page of
the business; its votes keep the data.bs.ch dataset link.
"""

from __future__ import annotations

import re

from src import agenda
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
        reb = ce.rebels(pairs, POS_YES, POS_NO, skip=NO_LINE) if pairs else None
        if pairs:
            lines.append(ce.split_line(ce.group_counts([(g, p) for _, g, p in pairs],
                                                       POS_YES, POS_NO, POS_ABST),
                                       "By Fraktion"))
            lines.append(ce.members_line(len(pairs), reb, "Fraktion as printed on the vote."))
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
                           watch_key=key if w else None,
                           positions=pairs or None, rebels=reb))
    return out


def items(conn, since, until, wl):
    return _businesses(conn, since, until, wl) + _votes(conn, since, until, wl)


# --- the cantonal parliaments (CH7) ---------------------------------------------

CANTON_NAMES = {"zh": "Kantonsrat Zürich", "be": "Grosser Rat Bern",
                "ge": "Grand Conseil de Genève", "vd": "Grand Conseil vaudois",
                "ti": "Gran Consiglio ticinese", "sg": "Kantonsrat St. Gallen",
                "bl": "Landrat Basel-Landschaft", "bs": "Grosser Rat Basel-Stadt",
                "tg": "Grosser Rat Thurgau", "ag": "Kanton Aargau (Gesetzessammlung)"}
CANTONS_READ = ("zh", "be", "sg", "bl", "bs", "tg", "ag", "ge", "vd", "ti")
CANTONS_UNDATED = ("ge", "vd", "ti", "bs")
CANTONS_DOC = ce.REPO + "docs/switzerland-cantons-scope.md"
# Read from an open-data API whose robots.txt refuses programs, with the
# owner's written permission (13 October 2026; src/robots_guard.PERMISSIONS).
# The licence asks for the data source to be linked: every item carries its
# dataset link, and so does the coverage line.
OPEN_DATA = {
    "bs": ("data.bs.ch", "CC BY 4.0, Parlamentsdienst des Grossen Rates Basel-Stadt",
           (("Geschäfte", "https://data.bs.ch/explore/assets/100311/"),
            ("Dokumente", "https://data.bs.ch/explore/assets/100313/"),
            ("Vorgänge", "https://data.bs.ch/explore/assets/100314/"),
            ("Abstimmungen", "https://data.bs.ch/explore/assets/100186/"))),
    "tg": ("data.tg.ch", "CC0 1.0, Staatskanzlei Kanton Thurgau",
           (("Geschäfte", "https://data.tg.ch/explore/dataset/sk-stat-140/"),
            ("Vorstösser", "https://data.tg.ch/explore/dataset/sk-stat-141/"),
            ("Abstimmungen", "https://data.tg.ch/explore/dataset/sk-stat-136/"))),
    "bl": ("data.bl.ch", "free use, source must be cited (opendata.swiss terms_by), "
                         "Landeskanzlei des Kantons Basel-Landschaft",
           (("Geschäfte", "https://data.bl.ch/explore/assets/13090/"),
            ("Unterlagen", "https://data.bl.ch/explore/assets/13130/"),
            ("Vorstösser", "https://data.bl.ch/explore/assets/13140/"),
            ("Abstimmungen", "https://data.bl.ch/explore/assets/13080/"))),
}
# Read from a parliament's own raw data exports, offered by its staff (13
# October 2026; robots.txt allows them). The Source line links the
# parliament's page of each business.
OWN_EXPORTS = {
    "bs": ("grosserrat.bs.ch", "Peter Frankenbach, Parlamentsdienst des Grossen Rates",
           (("Geschäfte", "https://grosserrat.bs.ch/component/gribs?chosentable=ges&view=exporter"
                          "&Itemid=105&format=json"),
            ("Dokumente", "https://grosserrat.bs.ch/component/gribs?chosentable=dok&view=exporter"
                          "&Itemid=105&format=json"),
            ("Vorgänge", "https://grosserrat.bs.ch/component/gribs?chosentable=vor&view=exporter"
                         "&Itemid=105&format=json"),
            ("Sitzungen", "https://grosserrat.bs.ch/component/gribs?chosentable=siz&view=exporter"
                          "&Itemid=105&format=json"),
            # 15 October 2026: committee assignments, the committees they name, members.
            ("Zuweisungen", "https://grosserrat.bs.ch/component/gribs?chosentable=zuw&view=exporter"
                            "&Itemid=105&format=json"),
            ("Gremien", "https://grosserrat.bs.ch/component/gribs?chosentable=gre&view=exporter"
                        "&Itemid=105&format=json"),
            ("Ratsmitglieder", "https://grosserrat.bs.ch/component/gribs?chosentable=adr&view=exporter"
                               "&Itemid=105&format=json"))),
}
# The host of an item's source_url, when it is a parliament's own page (the
# licence line of OPEN_DATA does not apply to it).
OWN_SOURCES = {"grosserrat.bs.ch": "Grosser Rat Basel-Stadt, from its Parlamentsdienst's "
                                   "Geschäfte export"}
CANTONS_BLOCKED = (
    "St. Gallen: its open-data portal's robots.txt disallows /api/ (not read); its "
    "parliament is read from its own business system instead (ratsinfo.sg.ch)",
    "Aargau: www.ag.ch's robots.txt disallows /grossrat (not read); only the acts published "
    "in the Aargauische Gesetzessammlung are read",
    "Lucerne, Valais and the other sixteen cantons are not read yet ([scope]({0}))".format(
        CANTONS_DOC),
)


def _canton_takeaway(r, new):
    bits = ["{0}: {1}".format(CANTON_NAMES.get(r["canton"], r["canton"]),
                              ce.clean(r["label"]) or r["kind"])]
    if r["initiative"]:
        bits.append("by {0}".format(ce.clip(ce.clean(r["initiative"]), 160)))
    if r["committee"]:
        bits.append("committee: {0}".format(ce.clean(r["committee"])))
    if new and r["presented"]:
        bits.append("submitted on {0}".format(ce.long_date(ce.day(r["presented"]))))
    elif new:
        bits.append("first seen by the weekly run of {0}".format(
            ce.long_date(ce.day(r["first_seen"]))))
    elif r["status_date"]:
        if r["status_seen"]:
            bits.append("status change seen by the weekly run of {0}".format(
                ce.long_date(ce.day(r["status_date"]))))
        else:
            bits.append("status dated {0}".format(ce.long_date(ce.day(r["status_date"]))))
    return "; ".join(bits)


# data.bs.ch and data.bl.ch answer /explore/dataset/<id>/ with a 302 to
# /explore/assets/<id>/ (15 October 2026): links go straight there, rows
# stored before that included.
_ODS_REDIRECTS = ("data.bs.ch", "data.bl.ch")


def direct_url(url):
    """A dataset link without the portal's redirect: /explore/dataset/ ->
    /explore/assets/ on data.bs.ch and data.bl.ch, and the old
    '?refine.<field>=<value>' filter in the form the portal redirects to."""
    host = url.split("/")[2] if url and "://" in url else ""
    if host not in _ODS_REDIRECTS or "/explore/dataset/" not in url:
        return url
    url = url.replace("/explore/dataset/", "/explore/assets/", 1)
    return re.sub(r"\?refine\.([\w]+)=([^&]*)", lambda m: "?refine={0}%3A{1}".format(
        m.group(1), m.group(2)), url)


def source_line(canton, url):
    """The dataset link an open-data canton's licence asks for, or the
    parliament's own page where the item came from its own export."""
    if not url:
        return None
    url = direct_url(url)
    host = url.split("/")[2] if "://" in url else ""
    if host in OWN_SOURCES:
        return "Source: [{0}]({1}) ({2}).".format(host, url, OWN_SOURCES[host])
    got = OPEN_DATA.get(canton)
    if not got:
        return None
    return "Source: [{0}]({1}) ({2}).".format(got[0], url, got[1])


def _canton_positions(conn, vote_key):
    return [(v["member"], v["parl_group"], v["position"]) for v in ce.rows(
        conn, "SELECT member, parl_group, position FROM ch_canton_votes WHERE vote_key=? "
              "ORDER BY member", (vote_key,))]


def canton_items(conn, since, until, wl):
    """The cantonal acts on our ground, new or moved in the window, and
    Bern's votes on them."""
    out = []
    undated = ",".join("'{0}'".format(c) for c in CANTONS_UNDATED)
    got = ce.rows(conn, "SELECT * FROM ch_canton_acts WHERE ({0}) OR ({1}) OR (presented IS NULL "
                        "AND COALESCE(baseline, 0)=0 AND canton IN ({2}) AND {3})".format(
                            ce.window_sql("presented"), ce.window_sql("status_date"), undated,
                            ce.window_sql("first_seen")),
                  (since, until, since, until, since, until))
    for r in got:
        w = r["act_key"] in wl
        if not ce.on_ground(r["areas"], w):
            continue
        if r["presented"]:
            new = since < ce.day(r["presented"]) <= until
        else:
            new = (r["canton"] in CANTONS_UNDATED and not r["baseline"]
                   and since < ce.day(r["first_seen"]) <= until)
        moved = bool(r["status_date"]) and since < ce.day(r["status_date"]) <= until
        if not new and not moved:
            continue
        if r["question"] and not new:
            continue
        kind = "question" if r["question"] else ("new" if new else "moved")
        date = (r["presented"] or r["first_seen"]) if new else r["status_date"]
        lines = []
        if r["title_fr"] and r["title_fr"] != r["title"]:
            lines.append("French title: *{0}*".format(ce.clip(r["title_fr"], 300)))
        src = source_line(r["canton"], r["source_url"])
        if src:
            lines.append(src)
        out.append(ce.item("ch", kind, r["act_key"], date, r["title"], ce.areas_of(r["areas"]),
                           r["tier"], w, status=r["status"], url=r["url"],
                           terms=r["matched_terms"], takeaway=_canton_takeaway(r, new),
                           lines=lines))
    for r in ce.rows(conn, "SELECT v.*, a.title AS act_title, a.label AS act_label FROM "
                           "ch_canton_divisions v LEFT JOIN ch_canton_acts a USING (act_key) WHERE "
                           + ce.window_sql("v.date"), (since, until)):
        w = bool(r["act_key"]) and r["act_key"] in wl
        if not ce.on_ground(r["areas"], w):
            continue
        title = ce.clean(r["subject"]) or "Abstimmung"
        name = CANTON_NAMES.get(r["canton"], "Grosser Rat")
        take = "{0}, on {1}".format(CANTON_NAMES.get(r["canton"], r["canton"]),
                                    ce.clean(r["act_label"]) or r["act_key"] or "an item")
        pairs = _canton_positions(conn, r["vote_key"])
        if r["counts_from"] == "tallied" and r["yes"] is None and r["no"] is None:
            # A vote between options: the counts per option are the result line.
            lines = ["Tally: {0} (tallied from the members' votes; {1} publishes no totals)."
                     .format(ce.clean(r["result"]) or "not available", OPEN_DATA.get(
                         r["canton"], ("the source",))[0])]
        elif r["counts_from"] == "tallied":
            lines = [ce.tally_line(r["yes"], r["no"], r["abstain"], r["result"],
                                   "tallied from the members' votes; {0} publishes no totals"
                                   .format(OPEN_DATA.get(r["canton"], ("the source",))[0]))]
        else:
            lines = [ce.tally_line(r["yes"], r["no"], r["abstain"], r["result"],
                                   "{0}, as published".format(name))]
        reb = ce.rebels(pairs, POS_YES, POS_NO) if pairs else None
        if pairs:
            lines.append(ce.split_line(ce.group_counts([(g, p) for _, g, p in pairs],
                                                       POS_YES, POS_NO, POS_ABST), "By Fraktion"))
            lines.append(ce.members_line(len(pairs), reb, "Fraktion as printed on the vote."))
        lines.append(source_line(r["canton"], r["source_url"]))
        out.append(ce.vote("ch", r["vote_key"], r["date"], title, ce.areas_of(r["areas"]),
                           r["tier"], w, lines,
                           url=r["url"], terms=r["matched_terms"], takeaway=take,
                           group="cantons:" + (r["act_key"] or r["vote_key"]),
                           group_title=r["act_title"],
                           watch_key=r["act_key"] if w else None,
                           positions=pairs or None, rebels=reb))
    return out


def canton_coverage(conn):
    read, never = [], []
    for code in CANTONS_READ:
        got = ce.rows(conn, "SELECT MAX(last_seen) AS seen, COUNT(*) AS n FROM ch_canton_acts "
                            "WHERE canton=?", (code,))
        if got and got[0]["seen"]:
            read.append("{0} {1}".format(CANTON_NAMES[code], ce.short_date(got[0]["seen"])))
        else:
            never.append(CANTON_NAMES[code])
    lines = ["Cantonal parliaments read (last read): {0}.".format(", ".join(read) or "none yet")]
    if never:
        lines.append("Not read yet: {0}.".format(", ".join(never)))
    for code, (host, offered, sets) in OWN_EXPORTS.items():
        lines.append("{0}'s business items are read from the Grand Council's own raw data "
                     "exports on {1}, offered by {2} (13 October 2026): {3}.".format(
                         CANTON_NAMES[code], host, offered, ", ".join(
                             "[{0}]({1})".format(n, u) for n, u in sets)))
    for code, (host, licence, sets) in OPEN_DATA.items():
        what = ("{0}'s votes (and its business items, if the Grand Council's exports fail) are"
                .format(CANTON_NAMES[code]) if code in OWN_EXPORTS
                else "{0} is".format(CANTON_NAMES[code]))
        lines.append("{0} read from {1}'s open-data API with the owner's written permission "
                     "(13 October 2026; robots.txt there refuses programs): {2}; {3}.".format(
                         what, host, ", ".join("[{0}]({1})".format(n, u)
                                               for n, u in sets), licence))
    lines += [b + "." for b in CANTONS_BLOCKED]
    lines.append("Cantonal titles are matched in their own language (taxonomy-atch, taxonomy-fr, "
                 "taxonomy-it for Ticino); Geneva is read through its keyword search, Vaud from "
                 "its lists of pending objects, Ticino from the order of the day. Basel-Stadt, "
                 "Thurgau and Basel-Landschaft fall back to their parliaments' own pages "
                 "(Basel-Landschaft: its newest documents on baselland.talus.ch) if their "
                 "exports and APIs fail (a gap line says so).")
    return lines


def cantons(conn, since, until, wl):
    intro = ["The cantonal parliaments' own business on our ground: Zürich, Bern, Geneva, Vaud "
             "and Ticino, each from its own system; titles verbatim in the canton's language, "
             "statuses in its own words. Bern's votes carry the Tagblatt's published tallies; "
             "Basel-Stadt's, Thurgau's and Basel-Landschaft's carry every member's vote, with "
             "the Fraktion split."]
    return [("Cantons", intro, canton_items(conn, since, until, wl), canton_coverage(conn))]


COUNTRY = ce.Country(
    cc="ch", name="Switzerland", chamber="Nationalrat and Ständerat", language="German or French",
    taxonomies=(("taxonomy-atch.yaml", "ch"), ("taxonomy-fr.yaml", "ch")),
    items=items, watchlist=watchlist, flag=":flag-ch:",
    week_ahead=agenda.week_ahead_fn("ch"), ahead_note=agenda.ahead_note_fn("ch"),
    members_note=("Both councils record every member's position, with the Fraktion at the vote; "
                  "the Nationalrat's tallies are counted from those positions"),
    coverage=("Businesses and Nationalrat votes come from the Parliament's OData service; "
              "Ständerat votes from its session spreadsheets.",
              "Matched on German (taxonomy-atch), French (taxonomy-fr) and, since CH6, Italian "
              "(taxonomy-it, Italy's list without its Italy-only terms) texts.",
              "Statuses are the Parliament's own German words. Federal popular votes are a "
              "later phase; five cantonal parliaments are read since CH7 (the Cantons section)."),
    extra_sections=cantons,
)
