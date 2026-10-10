"""France: the Assemblée nationale and, since FR5 (10 October 2026), the
Sénat, from the fr_* tables (src/fr_store.py, tools/fr_rollcalls.py,
tools/fr_senat.py).

Items: every dossier législatif on our ground (taxonomy-fr for `fr`, plus
config/watchlist-fr.yaml by dossier uid) whose latest act fell in the
window. The store keeps only a dossier's latest act, not its deposit date,
so a dossier whose latest act is its first-reading deposit or referral to
committee is new and any other act is a stage move, with the AN's own label
for the act. An act dated after the edition (a committee meeting already
scheduled) goes to the week ahead.

Votes: every scrutin public names every deputy's position with the group
at the vote, so each vote carries its tally, the result in the AN's own
words, the group split and the deputies who voted against their group's
majority; nothing is derived. A mise au point (a deputy saying afterwards
they meant otherwise) never changes the record and is counted, not
applied. A dossier's scrutins are one group, the vote solennel or the vote
on the whole text decisive.

THE SÉNAT (FR5). Its scrutins sit in fr_divisions with chamber 'senat' and
every senator's position with the group at the vote, so they render like
the Assemblée's, said to be the Sénat's. The Senate's data records the
votes for and against and the majority required, never a word for the
outcome, so no result is shown for them, only the counts and the absolute
majority of votes cast (half the votes cast, plus one, rounded down). A
Senate scrutin on a law the Assemblée also has is grouped with the
Assemblée's dossier. Senate-only dossiers (fr_senat_dossiers, 'SEN-...')
on our ground are new items when first deposited in the window, and any
Senate dossier on our ground with a sitting already scheduled in the next
two weeks is in the week ahead.

FR4 (Chris, 10 October 2026): the first job is the aide à mourir law's
application decrees. There is no Journal officiel collector yet, so the
week ahead carries a standing note, "Aide à mourir: decrees to watch",
drawn from the `decrees` list of the law's entry in config/watchlist-fr.yaml.

THE WEEK AHEAD (10 October 2026): the AN's ordre du jour, séances and
committee meetings, from its Agenda.json.zip (src/agendas/fr.py, read into
country_agenda by the weekly job), each point matched to its dossier by
ref. A dossier's scheduled act from fr_dossiers is still shown when the
agenda has no point on that dossier; the FR4 note comes last.
"""

from __future__ import annotations

import datetime
import json

from src import agenda
from src import country_edition as ce

AN = "https://www.assemblee-nationale.fr/dyn/{0}"
SENAT_SCRUTIN = "https://www.senat.fr/scrutin-public/{0}/scr{0}-{1}.html"
SENAT_DOSSIER = "https://www.senat.fr/dossier-legislatif/{0}.html"
POS_YES, POS_NO, POS_ABST = ("pour",), ("contre",), ("abstention",)
NO_LINE = ("NI",)
AIDE_A_MOURIR = "DLR5L17N51670"
AHEAD_DAYS = 14
# A first-reading deposit or referral: the dossier is new.
NEW_ACTS = ("-DEPOT", "-COM-FOND-SAISIE", "-COM-AVIS-SAISIE", "-COM-CAE-SAISIE")
FIRST = ("AN1-", "ANLUNI-", "SN1-")
VOTE_TYPES = {"SPO": "scrutin public ordinaire", "SPS": "scrutin public solennel",
              "MOC": "motion de censure"}


def legislature_of(ref):
    """'DLR5L17N51670' -> 17."""
    try:
        return int(ref.split("L", 2)[2].split("N", 1)[0])
    except (AttributeError, IndexError, ValueError):
        return 17


def dossier_url(ref, an_path=None):
    if not ref:
        return None
    return AN.format("{0}/dossiers/{1}".format(legislature_of(ref), an_path or ref))


def scrutin_url(legislature, number, chamber="an"):
    if chamber == "senat":
        # For a Senate scrutin `legislature` holds its session year (fr_store).
        return SENAT_SCRUTIN.format(legislature, number)
    return AN.format("{0}/scrutins/{1}".format(legislature, number))


def is_new(code):
    code = code or ""
    return code.startswith(FIRST) and code.endswith(NEW_ACTS)


def _dossier_item(r, wl, kind, take):
    w = r["dossier_ref"] in wl
    return ce.item("fr", kind, r["dossier_ref"], r["last_act_at"], r["title"],
                   ce.areas_of(r["areas"]), r["tier"], w,
                   status=r["last_act_label"], url=dossier_url(r["dossier_ref"], r["an_path"]),
                   terms=r["matched_terms"], takeaway=take)


def _take(r, ahead=False):
    bits = [ce.clean(r["procedure"]) or "Dossier"]
    if ahead:
        bits.append("{0} on {1}".format(ce.clean(r["last_act_label"]) or "next act",
                                        ce.long_date(ce.day(r["last_act_at"]))))
    else:
        bits.append("latest act on {0}".format(ce.long_date(ce.day(r["last_act_at"]))))
    if r["promulgated_at"]:
        bits.append("promulgated {0}".format(ce.long_date(ce.day(r["promulgated_at"]))))
    return ", ".join(bits[:1]) + "; " + "; ".join(bits[1:])


def _dossiers(conn, since, until, wl):
    out = []
    for r in ce.rows(conn, "SELECT * FROM fr_dossiers WHERE " + ce.window_sql("last_act_at"),
                     (since, until)):
        if not ce.on_ground(r["areas"], r["dossier_ref"] in wl):
            continue
        out.append(_dossier_item(r, wl, "new" if is_new(r["last_act"]) else "moved", _take(r)))
    return out


def _votes(conn, since, until, wl):
    out = []
    groups = {g["organe_ref"]: g["abbr"] or g["organe_ref"]
              for g in ce.rows(conn, "SELECT organe_ref, abbr FROM fr_groups")}
    senat_titles = {r["dossier_ref"]: r["title"] for r in
                    ce.rows(conn, "SELECT dossier_ref, title FROM fr_senat_dossiers")}
    for r in ce.rows(conn, "SELECT d.*, s.title AS dossier_title FROM fr_divisions d "
                           "LEFT JOIN fr_dossiers s USING (dossier_ref) WHERE "
                           + ce.window_sql("d.date"), (since, until)):
        senat = r["chamber"] == "senat"
        w = bool(r["dossier_ref"]) and r["dossier_ref"] in wl
        if not ce.on_ground(r["areas"], w):
            continue
        if senat:
            cast = (r["pour"] or 0) + (r["contre"] or 0)
            lines = [ce.tally_line(r["pour"], r["contre"], r["abstentions"], None,
                                   "Sénat, scrutin public; absolute majority of votes cast: "
                                   "{0}".format(cast // 2 + 1) if cast else "Sénat, scrutin public")]
        else:
            lines = [ce.tally_line(r["pour"], r["contre"], r["abstentions"], r["result"],
                                   VOTE_TYPES.get(r["vote_type"], r["vote_type"]))]
        got = ce.rows(conn, "SELECT m.name, v.acteur_ref, v.group_ref, v.position, v.intended FROM fr_votes v "
                            "LEFT JOIN fr_members m USING (acteur_ref) WHERE v.division_key=?",
                            (r["division_key"],))
        pairs = [(v["name"] or v["acteur_ref"], groups.get(v["group_ref"], v["group_ref"]), v["position"])
                 for v in got]
        if pairs:
            lines.append(ce.split_line(ce.group_counts([(g, p) for _, g, p in pairs],
                                                       POS_YES, POS_NO, POS_ABST), "By group"))
            lines.append(ce.members_line(len(pairs), ce.rebels(pairs, POS_YES, POS_NO,
                                                               skip=NO_LINE),
                                         "Groups as at the vote."))
        mises = sum(1 for v in got if v["intended"])
        if mises:
            lines.append("{0} mise(s) au point: deputies who said afterwards they meant to vote "
                         "otherwise; the record above stands.".format(mises))
        title = ce.clean(r["title"])
        bare = title.lower()[4:] if senat and title.lower().startswith("sur ") else title.lower()
        final = r["vote_type"] == "SPS" or bare.startswith(("l'ensemble", "l’ensemble"))
        if senat:
            take = "Sénat, scrutin {0} of the {1}-{2} session".format(
                r["number"], r["legislature"], int(r["legislature"]) + 1)
        else:
            take = "Assemblée nationale, scrutin {0}".format(r["number"])
        if r["dossier_ref"]:
            take += ", on dossier {0}".format(r["dossier_ref"])
            if r["dossier_via"] == "title":
                take += " (joined by its title)"
        out.append(ce.vote("fr", r["division_key"], r["date"], title, ce.areas_of(r["areas"]),
                           r["tier"], w, lines,
                           url=scrutin_url(r["legislature"], r["number"], r["chamber"]),
                           terms=r["matched_terms"], takeaway=take,
                           own=bool(ce.areas_of(r["own_areas"])),
                           group=r["dossier_ref"] or None,
                           group_title=r["dossier_title"] or senat_titles.get(r["dossier_ref"]),
                           final=final, watch_key=r["dossier_ref"] if w else None))
    return out


def _senat_watched(r, wl):
    for k in (r["dossier_ref"], r["an_dossier_ref"]):
        if k and k in wl:
            return k
    return None


def _senat_item(r, wl, kind, take):
    hit = _senat_watched(r, wl)
    return ce.item("fr", kind, r["dossier_ref"], r["deposited"] if kind == "new"
                   else r["last_sitting"], r["title"], ce.areas_of(r["areas"]), r["tier"],
                   hit is not None, status=r["state"], url=SENAT_DOSSIER.format(r["signet"]),
                   terms=r["matched_terms"], takeaway=take, watch_key=hit)


def _senat_dossiers(conn, since, until, wl):
    """FR5: Senate-only dossiers on our ground first deposited in the window
    (a dossier the Assemblée also has comes through the Assemblée's)."""
    out = []
    for r in ce.rows(conn, "SELECT * FROM fr_senat_dossiers WHERE an_dossier_ref IS NULL AND "
                     + ce.window_sql("deposited"), (since, until)):
        if not ce.on_ground(r["areas"], _senat_watched(r, wl) is not None):
            continue
        out.append(_senat_item(r, wl, "new", "Sénat: {0}, deposited on {1}".format(
            ce.clean(r["kind"]) or "dossier", ce.long_date(ce.day(r["deposited"])))))
    return out


def items(conn, since, until, wl):
    return (_dossiers(conn, since, until, wl) + _votes(conn, since, until, wl)
            + _senat_dossiers(conn, since, until, wl))


def decrees_note(today, wl):
    """FR4: the standing 'decrees to watch' item, from the law's watchlist
    entry; None when the entry carries no `decrees` list."""
    entry = wl.get(AIDE_A_MOURIR) or {}
    decrees = entry.get("decrees") if isinstance(entry, dict) else None
    if not decrees:
        return None
    lines = ["To watch for in the Journal officiel:"]
    lines += ["- {0}".format(ce.clean(d)) for d in decrees]
    if entry.get("decrees_note"):
        lines.append(ce.clean(entry["decrees_note"]))
    return ce.item("fr", "agenda", "aide-a-mourir-decrees", today,
                   "Aide à mourir: decrees to watch", ce.areas_of(entry.get("areas") or [2]),
                   1, True, url=dossier_url(AIDE_A_MOURIR, "fin_de_vie_17e"), lines=lines,
                   watch_key=AIDE_A_MOURIR,
                   takeaway=("A standing note, not a new event (FR4): the law is promulgated and "
                             "what happens next is regulatory. No collector reads the Journal "
                             "officiel yet, so these are checked by hand"))


def week_ahead(conn, today, wl):
    """The AN's agenda points on our ground (src/agenda.py), then acts
    already scheduled on dossiers on our ground that the agenda does not
    cover, then the FR4 standing note."""
    until = (datetime.date.fromisoformat(today)
             + datetime.timedelta(days=AHEAD_DAYS)).isoformat()
    out = agenda.ahead_items(conn, "fr", today, wl, AHEAD_DAYS)
    covered = set()
    for r in ce.rows(conn, "SELECT refs FROM country_agenda WHERE cc = 'fr' AND date >= ? "
                     "AND date <= ?", (today, until)):
        covered.update(agenda.loads(r["refs"]))
    for r in ce.rows(conn, "SELECT * FROM fr_dossiers WHERE " + ce.window_sql("last_act_at"),
                     (today, until)):
        if not ce.on_ground(r["areas"], r["dossier_ref"] in wl) or r["dossier_ref"] in covered:
            continue
        out.append(_dossier_item(r, wl, "agenda", _take(r, ahead=True)))
    # FR5: Senate sittings already scheduled on dossiers on our ground.
    for r in ce.rows(conn, "SELECT * FROM fr_senat_dossiers WHERE "
                     + ce.window_sql("last_sitting"), (today, until)):
        if not ce.on_ground(r["areas"], _senat_watched(r, wl) is not None):
            continue
        out.append(_senat_item(r, wl, "agenda", "Sénat: {0}, sitting scheduled on {1}".format(
            ce.clean(r["kind"]) or "dossier", ce.long_date(ce.day(r["last_sitting"])))))
    note = decrees_note(today, wl)
    if note:
        out.append(note)
    return out


COUNTRY = ce.Country(
    cc="fr", name="France", chamber="Assemblée nationale and Sénat", language="French",
    taxonomies=(("taxonomy-fr.yaml", "fr"),),
    items=items, week_ahead=week_ahead, ahead_note=agenda.ahead_note_fn("fr"),
    flag=":flag-fr:",
    members_note=("Every scrutin public names every deputy's or senator's position with the "
                  "group at the vote; nothing is derived, and a mise au point is counted, never "
                  "applied"),
    coverage=("Dossiers, scrutins and deputies come from the Assemblée nationale's open data "
              "(the weekly zips are archived, FR3).",
              "The Sénat (FR5) comes from data.senat.fr's Dosleg dump, read at most weekly and "
              "only when it changed; it records no outcome word, so Senate votes show their "
              "counts and the majority required.",
              "The store keeps a dossier's latest act only: an act in the week that a later "
              "scheduled act has overtaken shows under the week ahead instead.",
              "The aide à mourir decrees (FR4) have no collector yet: the week ahead carries a "
              "standing note from config/watchlist-fr.yaml until one exists."),
)
