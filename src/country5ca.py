"""5CA with stance sign-off for the new country editions (10 October 2026).

The parity layer of docs/country-parity-handover.md, item 2, for every new
country whose store holds member-level or party-group votes: Italy,
Switzerland, France, the Netherlands, Belgium, Poland, Croatia, Slovakia,
Spain, Brazil, Argentina, Mexico, Chile, Peru, Ecuador, the Dominican
Republic, El Salvador, Guatemala and Hungary (member level), and Austria,
Portugal and the Netherlands (party groups, X5).

It generalises what Canada, the US, Ireland and Australia already do
(tools/ca_5ca.py, src/readings5ca.py) and reuses src/readings5ca.py for the
placement, the sheet and the checkbox format. Four parts:

1. THE DRAFTER (`draft`). For every watched or tier-1 vote in a country's
   store it appends an entry to config/<cc>_stance.yaml, never touching an
   entry already there. The draft is made by RULES, not by a model (no AI
   call, X16), from three things only:
     * the issue area(s) the collector stamped on the vote;
     * the DIRECTION of the bill or motion voted on, read from the
       `bill_directions` section of the same file: whether passing it is
       with CitizenGO (`with`) or against it (`against`). Those lines were
       written by Claude from each watchlist's own description on
       10 October 2026 and are drafts too; a bill with no line has no
       direction, and nothing is guessed for it;
     * what KIND of vote it was, read from the vote's own wording: on the
       whole text or a motion itself (`final`), a motion to reject it
       (`reject`, the sides swap), an amendment or a single article
       (`amendment`), the timetable or the handling (`procedural`), or
       wording the rules do not recognise (`other`).
   Only a final or reject vote on a bill WITH a direction gets proposed
   values (`status: draft`, yea/nay on the -2..2 scale, why lines and the
   reasoning). A procedural vote gets `status: draft` with `placeable:
   false` (evidence only, once confirmed). Everything else is
   `status: needs_reading` with a `read_first:` line saying what a person
   must read: CitizenGO's side is never invented where the direction is
   unclear.

2. THE SIGN-OFF, as Canada's C-218 (drafted, then confirmed by a named
   person on a date). `confirm` turns `status: draft` into
   `status: confirmed` and stamps `confirmed_by:` and `confirmed_on:`. It
   refuses an entry that is `needs_reading` (a person writes the values
   first, then confirms), an entry with no values and no `placeable: false`,
   and a call with no name. Confirming from the checkbox guide
   (docs/5ca-<cc>-readings.md) works as in Ireland: tick, then
   `--sign-from-doc --by NAME`. Nothing here ever confirms on its own; the
   weekly job drafts, rewrites the guides (keeping any ticks not yet
   applied) and reports.

3. THE 5CA (`build_rows`, `run_sheets`): src/readings5ca.py's placement over
   the CONFIRMED readings only. `readings5ca.status` reads this file's
   `status:` field (an additive change there): `draft` and `needs_reading`
   are unsigned, and `confirmed` counts only with both `confirmed_by` and
   `confirmed_on`. A sheet is written only for a chamber and area with at
   least one confirmed reading that places someone; otherwise no sheet, and
   a stale one is removed, so an unconfirmed stance never reaches a
   published 5CA. Unconfirmed votes appear on a sheet's rows only as
   "awaiting sign-off -- not placed", with no direction. Party-group
   countries (AT, PT, NL show of hands) use the stores' own X5 derivations
   (`<cc>_store.derived_member_positions`): each derived row is labelled
   DERIVED, weighs less than a recorded vote (4 against 5), and its
   confidence says so.

4. THE DIGEST (`digest_text`, tools/stance_digest.py): one weekly DM to
   Chris listing what awaits sign-off, by country.

Read-only on the store. Writes config/<cc>_stance.yaml (append only, or the
confirm edit), docs/5ca-<cc>-readings.md and data/5ca/<cc>-5ca-*.csv.
"""

from __future__ import annotations

import datetime
import json
import os
import re
import sqlite3

from src import readings5ca as r5

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(ROOT, "config")
DOCS = os.path.join(ROOT, "docs")
OUT_DIR = os.path.join(ROOT, "data", "5ca")
SIGNERS_PATH = os.path.join(CONFIG, "stance_signers.yaml")
ALWAYS_SIGNS = ("Christopher", "Chris")       # Chris signs for every country
WEIGHTS = {"vote": 5, "derived": 4}
DRAFTED_BY = "tools/country_5ca.py (rules, no AI)"


def fold(text):
    from src.filter import _fold
    return " ".join(_fold(text or "").lower().split())


def _json_list(raw):
    if raw is None:
        return []
    if isinstance(raw, (list, tuple)):
        return [str(x) for x in raw if x not in (None, "")]
    try:
        got = json.loads(raw)
    except (TypeError, ValueError):
        return [str(raw)] if str(raw).strip() else []
    if isinstance(got, list):
        return [str(x) for x in got if x not in (None, "")]
    return [str(got)] if got not in (None, "") else []


def areas_of(raw):
    out = []
    for a in _json_list(raw):
        if str(a).isdigit():
            out.append(int(a))
    return sorted(set(out))


# --- the countries -----------------------------------------------------------------
#
# Each spec says, for one store: which divisions there are (`div_sql`, one row
# per division with the columns key, chamber, date, question, subject, areas,
# tier, result, yes, no, abstain, plus anything `refs` and `hint` read); which
# keys of a division may be watched (`refs`); each division's positions
# (`positions`: SQL returning member_id, name, party, position, or a store's
# X5 derivation); the sitting roster (`roster`: member_id, name, party,
# chamber, sitting); and which stored positions are a Yes, a No and an
# abstention (folded, lower case). `labels` name the lobbies as the chamber
# does.

class Spec:
    def __init__(self, cc, name, div_sql, positions, roster, yea, nay, abstain=(),
                 refs=None, hint=None, labels=("Yes", "No"), derived=None,
                 watchlist=None, extra_watched=None, chambers=None, note="", own_key=None):
        self.cc, self.name = cc, name
        self.div_sql, self.positions_sql, self.roster_sql = div_sql, positions, roster
        self.yea = {fold(x) for x in yea}
        self.nay = {fold(x) for x in nay}
        self.abstain = {fold(x) for x in abstain}
        self.refs = refs or (lambda r: [])
        self.hint = hint or (lambda r: None)
        self.labels = labels
        self.derived = derived            # fn(conn, key) -> [dict] (X5), or None
        self.watchlist_fn = watchlist
        self.extra_watched = extra_watched or (lambda r, wl: None)
        self.chambers = chambers or {}
        self.note = note
        self.own_key = own_key            # fn(row) -> the key of the item voted on itself

    def side(self, position):
        p = fold(position)
        if p in self.yea:
            return "yea"
        if p in self.nay:
            return "nay"
        if p in self.abstain:
            return "abstain"
        return None


def _edition_watchlist(cc):
    def load():
        from src import country_edition as ce
        return ce.watchlist_of(ce.adapter(cc))
    return load


def _latam_watchlist(cc):
    def load():
        from src import latam
        return latam.watchlist(cc)
    return load


def _ch_refs(r):
    from src import ch_store
    if r["short_number"]:
        return [r["short_number"]]
    if r["business_id"]:
        try:
            return [ch_store.short_number(r["business_id"])]
        except (TypeError, ValueError):
            return []
    return []


def _it_refs(r):
    keys = _json_list(r["bill_keys"])
    if r["bill_key"] and r["bill_key"] not in keys:
        keys.insert(0, r["bill_key"])
    return keys


def _br_refs(r):
    keys = [r["bill_key"]] if r["bill_key"] else []
    return keys + _json_list(r["linked_bills"]) + _json_list(r["former_keys"])


def _ar_refs(r):
    keys = _json_list(r["exp_keys"])
    return keys + [x for x in _json_list(r["exp_others"]) if x not in keys]


def _mx_watched(r, wl):
    for key, entry in wl.items():
        for v in (entry.get("votaciones") or []) if isinstance(entry, dict) else []:
            try:
                if int(v) == int(r["votaciont"] or -1):
                    return key
            except (TypeError, ValueError):
                continue
    return None


def _hu_watched(r, wl):
    return "HU4" if r["rule"] == "HU4" and "HU4" in wl else None


def _derive(module, cc):
    def derive(conn, key):
        import importlib
        store = importlib.import_module("src.{0}_store".format(module))
        return store.derived_member_positions(conn, key)
    return derive


SPECS = {
    "it": Spec(
        "it", "Italy",
        "SELECT d.division_key AS key, d.chamber, d.date, d.title AS question, "
        "b.title AS subject, d.areas, d.tier, d.bill_key, d.bill_keys, d.is_final, "
        "d.outcome AS result, d.ayes AS yes, d.noes AS no, d.abstentions AS abstain "
        "FROM it_divisions d LEFT JOIN it_bills b USING (bill_key)",
        "SELECT v.member_key AS member_id, COALESCE(m.name, v.member_key) AS name, v.grp AS party, "
        "v.position FROM it_votes v LEFT JOIN it_members m USING (member_key) WHERE v.division_key=?",
        "SELECT member_key AS member_id, name, grp AS party, chamber, 1 AS sitting FROM it_members",
        ("aye",), ("no",), ("abstain",), refs=_it_refs,
        hint=lambda r: "final" if r["is_final"] else None, labels=("Favorevole", "Contrario"),
        watchlist=_edition_watchlist("it"), chambers={"camera": "Camera", "senato": "Senato"}),
    "ch": Spec(
        "ch", "Switzerland",
        "SELECT d.division_key AS key, d.council AS chamber, d.date, "
        "COALESCE(NULLIF(d.subject,''), d.meaning_yes) AS question, "
        "COALESCE(b.title_de, b.title_fr, d.draft_title) AS subject, d.meaning_yes, d.meaning_no, "
        "d.areas, d.tier, d.short_number, d.business_id, d.result, d.yes, d.no, d.abstain "
        "FROM ch_divisions d LEFT JOIN ch_businesses b USING (business_id)",
        "SELECT v.person_number AS member_id, TRIM(COALESCE(m.first_name,'') || ' ' || "
        "COALESCE(m.last_name,'')) AS name, v.parl_group AS party, v.position FROM ch_votes v "
        "LEFT JOIN ch_members m USING (person_number) WHERE v.division_key=?",
        "SELECT person_number AS member_id, TRIM(COALESCE(first_name,'') || ' ' || "
        "COALESCE(last_name,'')) AS name, parl_group AS party, council AS chamber, "
        "COALESCE(active, 1) AS sitting FROM ch_members",
        ("Ja",), ("Nein",), ("Enthaltung",), refs=_ch_refs, labels=("Ja", "Nein"),
        watchlist=_edition_watchlist("ch"),
        chambers={"NR": "Nationalrat", "SR": "Ständerat", "N": "Nationalrat", "S": "Ständerat"}),
    "fr": Spec(
        "fr", "France",
        "SELECT d.division_key AS key, d.chamber, d.date, d.title AS question, "
        "s.title AS subject, d.areas, d.tier, d.dossier_ref, d.result, d.pour AS yes, "
        "d.contre AS no, d.abstentions AS abstain "
        "FROM fr_divisions d LEFT JOIN fr_dossiers s USING (dossier_ref)",
        "SELECT v.acteur_ref AS member_id, COALESCE(m.name, v.acteur_ref) AS name, "
        "COALESCE(g.abbr, g.label, v.group_ref) AS party, v.position FROM fr_votes v "
        "LEFT JOIN fr_members m USING (acteur_ref) LEFT JOIN fr_groups g "
        "ON g.organe_ref = v.group_ref WHERE v.division_key=?",
        "SELECT m.acteur_ref AS member_id, m.name, COALESCE(g.abbr, g.label, m.group_ref) AS party, "
        "m.chamber, COALESCE(m.current, 1) AS sitting FROM fr_members m "
        "LEFT JOIN fr_groups g ON g.organe_ref = m.group_ref",
        ("pour",), ("contre",), ("abstention",), refs=lambda r: [r["dossier_ref"]] if r["dossier_ref"] else [],
        labels=("Pour", "Contre"), watchlist=_edition_watchlist("fr"),
        chambers={"an": "Assemblée nationale"}),
    "nl": Spec(
        "nl", "Netherlands",
        "SELECT d.besluit_id AS key, 'tk' AS chamber, d.date, "
        "COALESCE(z.soort,'') || ': ' || COALESCE(z.onderwerp, d.besluit_tekst, '') AS question, "
        "z.dossier_titels AS subject, d.areas, z.tier, d.zaak_nummer, z.dossiers, "
        "d.besluit_tekst AS result, d.voor AS yes, d.tegen AS no, NULL AS abstain "
        "FROM nl_divisions d LEFT JOIN nl_zaken z USING (zaak_nummer)",
        None,
        "SELECT persoon_id AS member_id, name, fractie AS party, 'tk' AS chamber, 1 AS sitting "
        "FROM nl_members",
        ("Voor",), ("Tegen",), (), labels=("Voor", "Tegen"),
        refs=lambda r: [r["zaak_nummer"]] + _json_list(r["dossiers"]),
        derived=_derive("nl", "nl"), watchlist=_edition_watchlist("nl"),
        own_key=lambda r: r["zaak_nummer"],
        chambers={"tk": "Tweede Kamer"},
        note="Most votes are by show of hands: each member is given the fractie's vote (X5)."),
    "be": Spec(
        "be", "Belgium",
        "SELECT d.division_key AS key, 'kamer' AS chamber, d.date, "
        "COALESCE(d.heading_nl, d.heading_fr) AS question, COALESCE(s.title_nl, s.title_fr) AS subject, "
        "d.areas, NULL AS tier, d.dossier_key, d.outcome AS result, d.yes, d.no, d.abstain "
        "FROM be_divisions d LEFT JOIN be_dossiers s USING (dossier_key)",
        "SELECT COALESCE(v.member_key, v.member_name) AS member_id, COALESCE(m.name, v.member_name) "
        "AS name, v.group_seen AS party, v.position FROM be_votes v LEFT JOIN be_members m "
        "USING (member_key) WHERE v.division_key=?",
        "SELECT member_key AS member_id, name, party_group AS party, 'kamer' AS chamber, "
        "COALESCE(current, 1) AS sitting FROM be_members",
        ("yes",), ("no",), ("abstain",), refs=lambda r: [r["dossier_key"]] if r["dossier_key"] else [],
        labels=("Ja / Oui", "Nee / Non"), watchlist=_edition_watchlist("be"),
        chambers={"kamer": "Kamer"}),
    "pl": Spec(
        "pl", "Poland",
        "SELECT division_key AS key, 'sejm' AS chamber, substr(voted_at,1,10) AS date, "
        "COALESCE(topic, title) AS question, title AS subject, areas, tier, process_keys, "
        "NULL AS result, yes, no, abstain FROM pl_divisions",
        "SELECT v.mp_key AS member_id, COALESCE(m.name, v.mp_key) AS name, v.club AS party, "
        "v.position FROM pl_votes v LEFT JOIN pl_members m USING (mp_key) WHERE v.division_key=?",
        "SELECT mp_key AS member_id, name, club AS party, 'sejm' AS chamber, "
        "COALESCE(active, 1) AS sitting FROM pl_members",
        ("YES",), ("NO",), ("ABSTAIN",), refs=lambda r: _json_list(r["process_keys"]),
        labels=("Za", "Przeciw"), watchlist=_edition_watchlist("pl"), chambers={"sejm": "Sejm"}),
    "hr": Spec(
        "hr", "Croatia",
        "SELECT d.division_key AS key, 'sabor' AS chamber, substr(d.voted_at,1,10) AS date, "
        "d.title AS question, COALESCE(i.title, d.title) AS subject, d.areas, d.tier, d.bill_key, "
        "d.tid, d.yes_means_reject, d.outcome AS result, d.yes, d.no, d.abstain "
        "FROM hr_divisions d LEFT JOIN hr_items i ON i.tid = d.tid",
        "SELECT v.slug AS member_id, COALESCE(m.name, v.slug) AS name, v.party_seen AS party, "
        "v.position FROM hr_votes v LEFT JOIN hr_members m USING (slug) WHERE v.division_key=?",
        "SELECT slug AS member_id, name, party, 'sabor' AS chamber, "
        "CASE WHEN mandate = 'Aktivan' THEN 1 ELSE 0 END AS sitting FROM hr_members",
        ("for",), ("against",), ("abstained",),
        refs=lambda r: ([r["bill_key"]] if r["bill_key"] else []) + ["item:{0}".format(r["tid"])],
        hint=lambda r: "inverted" if r["yes_means_reject"] else None, labels=("Za", "Protiv"),
        watchlist=_edition_watchlist("hr"), chambers={"sabor": "Sabor"}),
    "sk": Spec(
        "sk", "Slovakia",
        "SELECT d.voting_id AS key, 'nrsr' AS chamber, d.date, d.name AS question, "
        "b.title AS subject, d.areas, d.tier, d.bill_key, d.result, d.agreed AS yes, "
        "d.disagreed AS no, d.abstained AS abstain FROM sk_divisions d LEFT JOIN sk_bills b "
        "USING (bill_key)",
        "SELECT v.mp_id AS member_id, COALESCE(m.name, v.mp_id) AS name, v.club AS party, "
        "v.position FROM sk_votes v LEFT JOIN sk_members m USING (mp_id) WHERE v.voting_id=?",
        "SELECT mp_id AS member_id, name, club AS party, 'nrsr' AS chamber, "
        "CASE WHEN term = (SELECT MAX(term) FROM sk_members) THEN 1 ELSE 0 END AS sitting "
        "FROM sk_members",
        ("Z",), ("P",), ("?",), refs=lambda r: [r["bill_key"]] if r["bill_key"] else [],
        labels=("Za", "Proti"), watchlist=_edition_watchlist("sk"), chambers={"nrsr": "Národná rada"}),
    "es": Spec(
        "es", "Spain",
        "SELECT division_key AS key, chamber, date, "
        "TRIM(COALESCE(title,'') || ' ' || COALESCE(subgroup,'')) AS question, "
        "COALESCE(section, session_title) AS subject, areas, tier, initiative_key, "
        "assent AS result, yes, no, abstain FROM es_divisions",
        "SELECT name AS member_id, name, grupo AS party, position FROM es_votes WHERE division_key=?",
        "SELECT name AS member_id, name, grupo AS party, 'congreso' AS chamber, "
        "CASE WHEN baja IS NULL AND legislature = (SELECT MAX(legislature) FROM es_members) "
        "THEN 1 ELSE 0 END AS sitting FROM es_members",
        ("Sí", "Si"), ("No",), ("Abstención",),
        refs=lambda r: [r["initiative_key"] or r["key"]], labels=("Sí", "No"),
        watchlist=_edition_watchlist("es"), chambers={"congreso": "Congreso"}),
    "br": Spec(
        "br", "Brazil",
        "SELECT d.division_key AS key, d.chamber, d.date, d.description AS question, "
        "b.ementa AS subject, d.areas, d.tier, d.bill_key, d.linked_bills, b.former_keys, "
        "d.result, d.yes, d.no, d.other AS abstain FROM br_divisions d LEFT JOIN br_bills b "
        "USING (bill_key)",
        "SELECT v.member_key AS member_id, COALESCE(m.name, v.member_key) AS name, v.party, "
        "v.position FROM br_votes v LEFT JOIN br_members m USING (member_key) WHERE v.division_key=?",
        "SELECT member_key AS member_id, name, party, chamber, COALESCE(in_office, 1) AS sitting "
        "FROM br_members",
        ("Sim",), ("Não", "Nao"), ("Abstenção", "Abstencao"), refs=_br_refs,
        labels=("Sim", "Não"), watchlist=_edition_watchlist("br"),
        chambers={"camara": "Câmara", "senado": "Senado"}),
    "ar": Spec(
        "ar", "Argentina",
        "SELECT d.division_key AS key, d.chamber, d.date, "
        "TRIM(COALESCE(d.vote_type,'') || ': ' || COALESCE(d.title,'')) AS question, "
        "d.title AS subject, d.areas, d.tier, d.exp_keys, "
        "(SELECT json_group_array(b.exp_other) FROM ar_bills b WHERE b.exp_other IS NOT NULL "
        " AND d.exp_keys LIKE '%' || b.exp_key || '%') AS exp_others, "
        "d.result, d.ayes AS yes, d.noes AS no, d.abstentions AS abstain FROM ar_divisions d",
        "SELECT v.member_key AS member_id, COALESCE(m.name, v.member_key) AS name, v.bloc AS party, "
        "v.position FROM ar_votes v LEFT JOIN ar_members m USING (member_key) WHERE v.division_key=?",
        "SELECT member_key AS member_id, name, bloc AS party, chamber, COALESCE(current, 1) AS sitting "
        "FROM ar_members",
        ("AFIRMATIVO",), ("NEGATIVO",), ("ABSTENCIÓN", "ABSTENCION"), refs=_ar_refs,
        labels=("Afirmativo", "Negativo"), watchlist=_edition_watchlist("ar"),
        chambers={"senado": "Senado", "diputados": "Diputados", "sen": "Senado", "dip": "Diputados"}),
    "mx": Spec(
        "mx", "Mexico",
        "SELECT division_key AS key, chamber, date, title AS question, title AS subject, areas, tier, "
        "ini_keys, votaciont, NULL AS result, favor AS yes, contra AS no, abstencion AS abstain "
        "FROM mx_divisions",
        "SELECT v.member_key AS member_id, COALESCE(m.name, v.member_key) AS name, v.party, "
        "v.position FROM mx_votes v LEFT JOIN mx_members m USING (member_key) WHERE v.division_key=?",
        "SELECT member_key AS member_id, name, party, 'diputados' AS chamber, "
        "CASE WHEN legislature = (SELECT MAX(legislature) FROM mx_members) THEN 1 ELSE 0 END "
        "AS sitting FROM mx_members",
        ("A favor",), ("En contra",), ("Abstención", "Abstencion"),
        refs=lambda r: _json_list(r["ini_keys"]), extra_watched=_mx_watched,
        labels=("A favor", "En contra"), watchlist=_edition_watchlist("mx"),
        chambers={"diputados": "Cámara de Diputados", "dip": "Cámara de Diputados"}),
    "hu": Spec(
        "hu", "Hungary",
        "SELECT d.vote_ts AS key, 'ogy' AS chamber, d.date, "
        "COALESCE(d.outcome, d.result, d.motion) AS question, COALESCE(d.title, p.title) AS subject, "
        "d.areas, d.tier, d.paper_key, d.rule, d.result, d.yes, d.no, d.abstain "
        "FROM hu_divisions d LEFT JOIN hu_papers p USING (paper_key)",
        "SELECT name AS member_id, name, faction AS party, position FROM hu_votes WHERE vote_ts=?",
        "SELECT name AS member_id, name, faction AS party, 'ogy' AS chamber, "
        "COALESCE(current, 1) AS sitting FROM hu_members",
        ("igen",), ("nem",), ("tartozkodott",),
        refs=lambda r: [r["paper_key"]] if r["paper_key"] else [], extra_watched=_hu_watched,
        labels=("Igen", "Nem"), watchlist=_edition_watchlist("hu"), chambers={"ogy": "Országgyűlés"},
        note="karzat records only (9 May to 28 August 2026) until the W-API token arrives."),
    "at": Spec(
        "at", "Austria",
        "SELECT d.division_key AS key, d.body AS chamber, d.date, d.question, i.title AS subject, "
        "COALESCE(d.areas, i.areas) AS areas, i.tier, d.item_key, d.outcome AS result, "
        "d.yes_count AS yes, d.no_count AS no, NULL AS abstain "
        "FROM at_divisions d LEFT JOIN at_items i USING (item_key) WHERE d.body IN ('NR', 'BR')",
        None,
        "SELECT pad AS member_id, name, klub AS party, chamber, 1 AS sitting FROM at_members",
        ("Dafür",), ("Dagegen",), (), refs=lambda r: [r["item_key"]] if r["item_key"] else [],
        labels=("Dafür", "Dagegen"), derived=_derive("at", "at"), watchlist=_edition_watchlist("at"),
        chambers={"NR": "Nationalrat", "BR": "Bundesrat"},
        note="Only the Klub's vote is recorded: every member row is DERIVED (X5). "
             "Committee votes are not sheeted (no membership list)."),
    "pt": Spec(
        "pt", "Portugal",
        "SELECT d.division_key AS key, 'ar' AS chamber, d.date, "
        "TRIM(COALESCE(d.phase,'') || ': ' || COALESCE(d.description,'')) AS question, "
        "i.title AS subject, d.areas, d.tier, d.ini_key, d.result, NULL AS yes, NULL AS no, "
        "NULL AS abstain FROM pt_divisions d LEFT JOIN pt_initiatives i USING (ini_key)",
        None,
        "SELECT cad_id AS member_id, name, party, 'ar' AS chamber, "
        "CASE WHEN situation LIKE 'Efetiv%' THEN 1 ELSE 0 END AS sitting FROM pt_members",
        ("A Favor",), ("Contra",), ("Abstenção", "Abstencao"),
        refs=lambda r: [r["ini_key"]] if r["ini_key"] else [], labels=("A favor", "Contra"),
        derived=_derive("pt", "pt"), watchlist=_edition_watchlist("pt"),
        chambers={"ar": "Assembleia da República"},
        note="Groups vote as blocks; deputies named in the record are facts, the rest DERIVED (X5)."),
    # --- Latin America (collected per country; the Latam monitor reads them) -----
    "cl": Spec(
        "cl", "Chile",
        "SELECT d.division_key AS key, d.chamber, d.date, "
        "TRIM(COALESCE(d.description,'') || ' ' || COALESCE(d.text,'')) AS question, "
        "b.title AS subject, d.areas, d.tier, d.boletin, d.result, d.yes, d.no, d.abstain "
        "FROM cl_divisions d LEFT JOIN cl_bills b USING (boletin)",
        "SELECT v.member_key AS member_id, COALESCE(m.name, v.member_key) AS name, v.party, "
        "v.position FROM cl_votes v LEFT JOIN cl_members m USING (member_key) WHERE v.division_key=?",
        "SELECT member_key AS member_id, name, party, chamber, 1 AS sitting FROM cl_members",
        ("Afirmativo", "Si", "Sí"), ("En Contra", "No"), ("Abstención", "Abstencion"),
        refs=lambda r: [r["boletin"]] if r["boletin"] else [], labels=("Afirmativo", "En contra"),
        watchlist=_latam_watchlist("cl"), chambers={"camara": "Cámara", "senado": "Senado"}),
    "pe": Spec(
        "pe", "Peru",
        "SELECT division_key AS key, chamber, date, subject AS question, subject, areas, tier, "
        "bill_refs, NULL AS result, yes, no, abstain FROM pe_divisions",
        "SELECT COALESCE(v.member_key, v.name_raw) AS member_id, COALESCE(m.name, v.name_raw) AS name, "
        "COALESCE(v.bancada, m.bancada) AS party, v.position FROM pe_votes v LEFT JOIN pe_members m "
        "USING (member_key) WHERE v.division_key=?",
        "SELECT member_key AS member_id, name, bancada AS party, chamber, 1 AS sitting FROM pe_members",
        ("SI", "Sí", "A favor"), ("NO", "En contra"), ("ABST", "Abstención", "Abstencion"),
        refs=lambda r: _json_list(r["bill_refs"]), labels=("Sí", "No"),
        watchlist=_latam_watchlist("pe")),
    "ec": Spec(
        "ec", "Ecuador",
        "SELECT division_key AS key, 'asamblea' AS chamber, date, "
        "TRIM(COALESCE(theme,'') || ' / ' || COALESCE(proposal,'')) AS question, theme AS subject, "
        "areas, tier, NULL AS result, yes, no, abstain FROM ec_divisions",
        "SELECT v.name_key AS member_id, v.name, COALESCE(ro.party, ro.party_slug) AS party, v.position "
        "FROM ec_votes v LEFT JOIN ec_roster ro ON ro.name_key = v.name_key WHERE v.division_key=?",
        "SELECT name_key AS member_id, name, COALESCE(party, party_slug) AS party, 'asamblea' AS chamber, "
        "1 AS sitting FROM ec_roster",
        ("SI", "Sí", "Afirmativo"), ("NO", "Negativo"), ("ABSTENCION", "Abstención", "BLANCO"),
        refs=lambda r: [r["key"]], labels=("Sí", "No"), watchlist=_latam_watchlist("ec")),
    "do": Spec(
        "do", "Dominican Republic",
        "SELECT division_key AS key, 'cd' AS chamber, date, COALESCE(motion, title) AS question, "
        "title AS subject, areas, tier, bill_refs, NULL AS result, yes, no, abstain FROM do_divisions",
        "SELECT v.member_key AS member_id, COALESCE(m.name, v.name) AS name, v.party, v.position "
        "FROM do_votes v LEFT JOIN do_members m USING (member_key) WHERE v.division_key=?",
        "SELECT member_key AS member_id, name, party, 'cd' AS chamber, 1 AS sitting FROM do_members",
        ("SI",), ("NO",), (), refs=lambda r: _json_list(r["bill_refs"]), labels=("Sí", "No"),
        watchlist=_latam_watchlist("do"), chambers={"cd": "Cámara de Diputados"}),
    "sv": Spec(
        "sv", "El Salvador",
        "SELECT v.division_key AS key, 'al' AS chamber, v.date, "
        "TRIM(COALESCE(v.label,'') || ': ' || COALESCE(d.extracto, p.extracto, p.leyenda, '')) AS question, "
        "COALESCE(d.extracto, p.leyenda) AS subject, v.areas, v.tier, v.expediente, v.item_key, "
        "NULL AS result, v.yes, v.no, v.abstain FROM sv_divisions v "
        "LEFT JOIN sv_dictamenes d ON d.dictamen_key = v.item_key "
        "LEFT JOIN sv_piezas p ON p.pieza_key = v.item_key",
        "SELECT name AS member_id, name, party, position FROM sv_votes WHERE division_key=?",
        "SELECT name AS member_id, name, party, 'al' AS chamber, 1 AS sitting FROM sv_members",
        ("SI",), ("NO",), ("ABST",),
        refs=lambda r: [x for x in (r["expediente"], r["item_key"]) if x], labels=("Sí", "No"),
        watchlist=_latam_watchlist("sv")),
    "gt": Spec(
        "gt", "Guatemala",
        "SELECT division_key AS key, 'congreso' AS chamber, date, title AS question, title AS subject, "
        "areas, tier, iniciativa, procedural, NULL AS result, yes, no, NULL AS abstain FROM gt_divisions",
        "SELECT v.name_key AS member_id, v.name, m.bloque AS party, v.position FROM gt_votes v "
        "LEFT JOIN gt_members m ON m.name_key = v.name_key WHERE v.division_key=?",
        "SELECT name_key AS member_id, name, bloque AS party, 'congreso' AS chamber, 1 AS sitting "
        "FROM gt_members",
        ("A favor", "SI", "Sí"), ("En contra", "NO"), (),
        refs=lambda r: [r["iniciativa"]] if r["iniciativa"] else [],
        hint=lambda r: "procedural" if r["procedural"] else None, labels=("A favor", "En contra"),
        watchlist=_latam_watchlist("gt"), note="Party is the member's current bloc (GT4, X6)."),
}

COUNTRIES = tuple(SPECS)
PARTY_GROUP = ("at", "pt", "nl")


# --- what kind of vote it was --------------------------------------------------------
#
# Folded (accents off, lower case) patterns over the first QUESTION_CHARS of
# the vote's own wording (a long quoted amendment must not match on a stray
# word deep inside it), in this order: a whole-text vote that names its parts
# (Mexico's "en lo general y en lo particular", Brazil's "aprovada em primeiro
# turno" of a PEC), a motion to reject, an amendment or article, procedure,
# and the whole text. Amendment before procedure on purpose: when a wording
# is both, `needs_reading` is the safe side.

QUESTION_CHARS = 400

FINAL_FIRST = (r"en lo general y en lo particular", r"en general y en particular",
               r"aprovad\w*,? em (primeiro|segundo) turno", r"votacao final global")
PROCEDURAL = (r"porzadk\w* dzienn", r"przerw\w* w posiedzeniu", r"odroczeni", r"skroceni\w* termin",
              r"wybor\w* skladu", r"wniosek formaln", r"sobre la mesa", r"de urgencia",
              r"orden del dia", r"liberad\w* de", r"remitid\w*.*comision", r"ordnungsantrag",
              r"fristsetzung", r"pridelen\w* navrhu", r"skrateni\w* lehot",
              r"pristupeni k tretiemu citaniu ihned", r"prorroga", r"subcomision", r"requerimento",
              r"preferencia", r"dispensa\w* (de |da )?reda", r"recurso da decisao", r"baixa\w* (a |a )?comissao",
              r"targyalasara", r"surgossegi", r"szabalyszeru", r"napirend", r"suspension de seance",
              r"habilitacion", r"mocion de orden", r"vuelta a comision", r"verzoek bij regeling",
              r"^brief", r"bez (kierowania|odsylania)", r"urgenza")
REJECT = (r"wniosek o odrzuceni", r"motion de rejet", r"rejet prealable", r"questione pregiudiziale",
          r"questione sospensiva", r"nichteintret", r"voorstel tot verwerping", r"proposition de rejet",
          r"nepokracova", r"totalidad de devolucion", r"ablehnenden ausschussbericht",
          r"proposta de rejeicao", r"\bq\.? preg", r"questioni pregiudiziali", r"ablehnung der motion",
          r"rejet de la motion", r"rejeter la motion")
AMENDMENT = (r"poprawk", r"wniosek mniejszosci", r"amendement", r"emendament", r"\bem\.", r"\bemm\.",
             r"articolo aggiuntivo", r"\bart\.? agg", r"\bodg\b", r"ordine del giorno",
             r"abanderungsantrag", r"zusatzantrag", r"^art\.", r"\bart\. \d", r"^articolo",
             r"pozmenujuc", r"enmienda", r"indicacion", r"propuesta de modificacion",
             r"modificacion propuesta", r"modificacion presentada", r"modosito", r"destaque",
             r"mantido o texto", r"\bemenda", r"^l'article", r"votacion separada por puntos",
             r"en particular", r"en lo particular", r"konzeptantrag", r"^ziffer", r"ruckweisung",
             r"^articulo", r"\bpunto \d", r"^em \d", r"\bem \d", r"proposition de la commission",
             r"noch offenen bestimmungen")
FINAL = (r"nad caloscia", r"ponownym uchwaleni", r"votazione finale", r"voto finale",
         r"gesamtabstimmung", r"schlussabstimmung", r"vote sur l'ensemble", r"vote final",
         r"abstimmung uber die motion", r"\beintreten\b", r"l'ensemble d", r"votacao na generalidade",
         r"votacao final", r"dritter lesung", r"zweiter lesung", r"entschliessungsantrag",
         r"keinen einspruch", r"geheel van het", r"ensemble du projet", r"ensemble de la proposition",
         r"ako o celku", r"prerokovany v druhom citani", r"navrhu uznesenia", r"votacion de conjunto",
         r"toma en consideracion", r"votacion del dictamen", r"konacni prijedlog", r"prvo citanje",
         r"aprovado o projeto", r"en lo general", r"en general", r"sometido a votacion el proyecto",
         r"aprobad\w* en (primera|segunda|unica) lectura", r"onallo inditvany", r"tercer debate",
         r"redaccion final", r"^(gewijzigde |nader gewijzigde )?motie", r"^motie:",
         r"^(wetgeving|initiatiefwetgeving):", r"proposicion no de ley", r"mocion consecuencia",
         r"^proposicion de ley", r"proyecto de ley, iniciado", r"^(dictamen|pieza)\b",
         r"adopter le postulat", r"adopter la motion", r"annahme der motion", r"annahme des postulats")

MOTION = r"^(motie|amendement)?:? ?(gewijzigde |nader gewijzigde )?(motie|amendement)"

KIND_WORDS = {"final": "a vote on the whole text or the motion itself",
              "reject": "a motion to reject the text (the sides are swapped)",
              "inverted": "a vote whose Yes rejects the text (the record says so)",
              "amendment": "an amendment, an article or one point",
              "procedural": "procedure (the timetable or the handling)",
              "other": "a kind of vote the rules do not recognise"}


def vote_kind(question, hint=None):
    """('final' | 'reject' | 'inverted' | 'amendment' | 'procedural' | 'other',
    the pattern that decided it). A store's own flag (`hint`) wins."""
    if hint in KIND_WORDS:
        return hint, "the store's own flag"
    q = fold(question)[:QUESTION_CHARS]
    for kind, pats in (("final", FINAL_FIRST), ("reject", REJECT), ("amendment", AMENDMENT),
                       ("procedural", PROCEDURAL), ("final", FINAL)):
        for p in pats:
            if re.search(p, q):
                return kind, p
    return "other", None


# --- the stance file ----------------------------------------------------------------

def stance_path(cc, config_dir=None):
    return os.path.join(config_dir or CONFIG, "{0}_stance.yaml".format(cc))


def doc_path(cc, docs_dir=None):
    return os.path.join(docs_dir or DOCS, "5ca-{0}-readings.md".format(cc))


def load(cc, config_dir=None):
    """(divisions, bill_directions, meta), each {key: entry}, drafts included."""
    import yaml
    path = stance_path(cc, config_dir)
    if not os.path.exists(path):
        return {}, {}, {}
    with open(path, encoding="utf-8") as h:
        cfg = yaml.safe_load(h) or {}
    divs = {str(e["key"]): e for e in (cfg.get("divisions") or []) if e.get("key")}
    bills = {str(e["key"]): e for e in (cfg.get("bill_directions") or []) if e.get("key")}
    return divs, bills, {k: v for k, v in cfg.items() if k not in ("divisions", "bill_directions")}


def header(cc):
    name = SPECS[cc].name
    return """# {name}: what a recorded vote MEANS for CitizenGO, for the 5CA.
#
# Written by tools/country_5ca.py (src/country5ca.py), the 5CA-with-sign-off
# layer of docs/country-parity-handover.md (item 2), 10 October 2026. The
# rule is Canada's: which lobby is CitizenGO's is a HUMAN judgement, and
# nothing places anyone until a named person has confirmed it.
#
# status:
#   draft          proposed by the drafter's rules (or by Claude): unsigned,
#                  places nobody.
#   needs_reading  no direction proposed: the drafter could not tell which
#                  side is ours without reading the text. A person writes
#                  `yea:`/`nay:` (and why lines), then confirms.
#   confirmed      signed: `confirmed_by:` (a named person) and
#                  `confirmed_on:` (the date) are both required, or it still
#                  counts as unsigned.
#
# To confirm: tick the box in docs/5ca-{cc}-readings.md and run
#   python3 tools/country_5ca.py --cc {cc} --sign-from-doc --by NAME
# or confirm by key:
#   python3 tools/country_5ca.py --cc {cc} --confirm KEY [KEY ...] --by NAME
# To strike a reading for good, write `placeable: false` and a `reason:`.
#
# bill_directions: whether PASSING a bill or motion is with CitizenGO
# (`with`) or against it (`against`). Drafted by Claude on 10 October 2026
# from each watchlist entry's own description, never from a model call; a
# bill with no line gets no proposed values. Edit or add lines here: the
# next --draft uses them for NEW votes (an existing entry is never
# rewritten).
#
# divisions: one entry per watched or tier-1 vote, appended by --draft.
# Keys are the store's division keys. `yea:`/`nay:` are the stance (-2..2)
# of voting Yes / No as the chamber records it ({yea} / {nay}). An
# abstention never places anyone. Keep `divisions:` the LAST section: the
# drafter appends to the end of this file.
""".format(name=name, cc=cc, yea=SPECS[cc].labels[0], nay=SPECS[cc].labels[1])


def _q(text):
    """A YAML double-quoted scalar (JSON's escapes are valid YAML)."""
    return json.dumps(" ".join(str(text).split()), ensure_ascii=False)


def entry_yaml(e):
    """One `divisions` entry as YAML text, in a fixed order."""
    order = ("key", "status", "title", "on", "dated", "chamber", "areas", "tier", "watched",
             "result", "lobbies", "vote_kind", "placeable", "reason", "yea", "why_yea", "nay",
             "why_nay", "read_first", "reasoning", "flag", "drafted")
    lines = []
    for k in order:
        if k not in e or e[k] is None or e[k] == "":
            continue
        v = e[k]
        if isinstance(v, bool):
            val = "true" if v else "false"
        elif isinstance(v, int):
            val = str(v)
        elif isinstance(v, list):
            val = "[" + ", ".join(str(x) for x in v) + "]"
        elif k == "status":
            val = v
        else:
            val = _q(v)
        lines.append("{0}{1}: {2}".format("  - " if not lines else "    ", k, val))
    return "\n".join(lines) + "\n"


# --- reading a store ---------------------------------------------------------------

def connect_ro(path):
    conn = sqlite3.connect("file:{0}?mode=ro".format(path), uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _rows(conn, sql, params=()):
    try:
        return [dict(r) for r in conn.execute(sql, params)]
    except sqlite3.OperationalError:
        return []


def divisions(conn, cc):
    """Every division of a country's store, as dicts, oldest first."""
    rows = _rows(conn, SPECS[cc].div_sql)
    rows.sort(key=lambda r: (str(r.get("date") or ""), str(r["key"])))
    for r in rows:
        r["key"] = str(r["key"])
        r["date"] = str(r.get("date") or "")[:10]
    return rows


def watched_key(spec, r, wl):
    for k in spec.refs(r):
        if k and k in wl:
            return k
    return spec.extra_watched(r, wl)


def qualifying(conn, cc, wl=None):
    """The watched or tier-1 divisions, each with `watch_key` (or None)."""
    spec = SPECS[cc]
    wl = spec.watchlist_fn() if wl is None else wl
    out = []
    for r in divisions(conn, cc):
        w = watched_key(spec, r, wl)
        if w is None and r.get("tier") != 1:
            continue
        if w is None and not areas_of(r.get("areas")):
            continue
        r["watch_key"] = w
        out.append(r)
    return out


def positions(conn, cc, key):
    """[{member_id, name, party, position, derived, basis}] for one division."""
    spec = SPECS[cc]
    if spec.derived is not None:
        try:
            got = spec.derived(conn, key)
        except sqlite3.OperationalError:
            return []
        return [dict(p, member_id=str(p["member_id"] if p["member_id"] is not None else p["name"]))
                for p in got]
    out = []
    for r in _rows(conn, spec.positions_sql, (key,)):
        out.append({"member_id": str(r["member_id"]), "name": r["name"], "party": r["party"],
                    "position": r["position"], "derived": False, "basis": "recorded vote"})
    return out


def lobbies(spec, pos):
    """'Yes: A 10, B 2. No: C 5. Abstain: D 1' counted from the positions."""
    sides = {"yea": {}, "nay": {}, "abstain": {}}
    for p in pos:
        s = spec.side(p["position"])
        if s:
            sides[s][p["party"] or "?"] = sides[s].get(p["party"] or "?", 0) + 1
    parts = []
    for s, label in (("yea", spec.labels[0]), ("nay", spec.labels[1]), ("abstain", "Abstain")):
        if sides[s]:
            parts.append("{0}: {1}".format(label, ", ".join(
                "{0} {1}".format(p, n) for p, n in sorted(sides[s].items(), key=lambda kv: -kv[1]))))
    if not parts:
        return None
    text = ". ".join(parts)
    if any(p["derived"] for p in pos):
        text += " (counts include members DERIVED from their group's vote, X5)"
    return text


# --- the drafter ---------------------------------------------------------------------

def _area_text(areas):
    from src.latam import AREA_LABELS
    return ", ".join("{0} ({1})".format(a, AREA_LABELS.get(a, "area {0}".format(a))) for a in areas) \
        or "no area stamped"


def _direction_for(r, bills, spec):
    """(key, entry) of the bill direction that applies to this vote, or (None, None)."""
    for k in [r.get("watch_key")] + list(spec.refs(r)):
        if k and k in bills and bills[k].get("direction") in ("with", "against"):
            return k, bills[k]
    return None, None


def draft_entry(cc, r, bills, pos=None, today=None):
    """The drafted entry for one qualifying division (a dict, not yet YAML)."""
    spec = SPECS[cc]
    today = today or datetime.date.today().isoformat()
    areas = areas_of(r.get("areas"))
    kind, why_kind = vote_kind(r.get("question"), spec.hint(r))
    q = r5.clip(r.get("question"), 240)
    e = {"key": r["key"], "title": q or "(no wording stored)",
         "on": r5.clip(r.get("subject"), 200) if r.get("subject") and r.get("subject") != r.get("question") else None,
         "dated": r.get("date") or None,
         "chamber": r.get("chamber"),
         "areas": areas, "tier": r.get("tier") if isinstance(r.get("tier"), int) else None,
         "watched": r.get("watch_key"), "vote_kind": kind,
         "drafted": "{0}, {1}".format(DRAFTED_BY, today)}
    tally = [x for x in (("{0} {1}".format(spec.labels[0], r["yes"]) if r.get("yes") is not None else None),
                         ("{0} {1}".format(spec.labels[1], r["no"]) if r.get("no") is not None else None),
                         ("Abstain {0}".format(r["abstain"]) if r.get("abstain") else None)) if x]
    e["result"] = "; ".join(x for x in (r5.clip(r.get("result"), 120), ", ".join(tally)) if x) or None
    if pos:
        e["lobbies"] = r5.clip(lobbies(spec, pos), 600)
    area_line = "Area {0}.".format(_area_text(areas))
    if kind == "procedural":
        e.update(status="draft", placeable=False,
                 reason="Procedural ({0}): it decides the timetable or the handling, not the "
                        "substance, so neither lobby tells members apart on our ground.".format(
                            r5.clip(q, 120)),
                 reasoning="{0} The wording reads as {1}.".format(area_line, KIND_WORDS[kind]))
        return e
    bkey, bill = _direction_for(r, bills, spec)
    if bill and spec.own_key is not None and bkey != spec.own_key(r) \
            and re.search(MOTION, fold(r.get("question"))):
        # A motion tabled in a bill's dossier is its own text: the bill's
        # direction says nothing about it (the Netherlands' moties).
        e.update(status="needs_reading",
                 read_first="A motion tabled in the dossier of {0} ({1}): its own text decides which "
                            "side is ours, not the bill's direction. Read it, then write "
                            "yea/nay.".format(bkey, bill["direction"]),
                 reasoning="{0} The bill's direction does not carry to a motion.".format(area_line))
        return e
    if kind in ("final", "reject", "inverted") and bill:
        s = 1 if bill["direction"] == "with" else -1
        swap = kind in ("reject", "inverted")
        yea = -2 * s if swap else 2 * s
        what = r5.clip(bill.get("why") or bill.get("title") or bkey, 200).rstrip(".")
        short = r5.clip(re.split(r"(?<=[a-z\)])[.;] ", what)[0], 90)
        passing = "rejecting" if swap else "passing"
        e.update(status="draft", yea=yea, nay=-yea,
                 why_yea="Voted {0} on {1} ({2}): {3} it, {4} CitizenGO's position.".format(
                     spec.labels[0], bkey, short, "for rejecting" if swap else "for passing",
                     "with" if yea > 0 else "against"),
                 why_nay="Voted {0} on {1} ({2}): against {3} it, {4} CitizenGO's position.".format(
                     spec.labels[1], bkey, short, passing, "with" if -yea > 0 else "against"),
                 reasoning="{0} Bill direction on file for {1} ({2}): passing it is {3} us -- {4}. "
                           "This vote is {5}, so {6} is {7} us.".format(
                               area_line, bkey, "CONFIRMED" if bill.get("status") == "confirmed"
                               else "a draft", "WITH" if s > 0 else "AGAINST", what, KIND_WORDS[kind],
                               spec.labels[0], "with" if yea > 0 else "against"))
        flags = []
        if kind == "inverted":
            flags.append("The record says a Yes here REJECTS the text; check the question put.")
        if bill.get("flag"):
            flags.append("On the bill's direction: " + bill["flag"])
        if flags:
            e["flag"] = " ".join(flags)
        return e
    if kind in ("final", "reject", "inverted"):
        refs = ", ".join(k for k in spec.refs(r) if k) or "this item"
        e.update(status="needs_reading",
                 read_first="{0}, but no bill direction is on file for {1}: CitizenGO's position on "
                            "'{2}' needs a human reading. Add a `bill_directions` line or write "
                            "yea/nay here.".format(KIND_WORDS[kind][0].upper() + KIND_WORDS[kind][1:],
                                                   refs, r5.clip(r.get("subject") or q, 140)),
                 reasoning="{0} Direction unclear from the store: nothing proposed.".format(area_line))
        return e
    if kind == "amendment":
        e.update(status="needs_reading",
                 read_first="An amendment, an article or one point ('{0}'): which side is ours depends "
                            "on its text, which the store does not hold. Read it, then write "
                            "yea/nay.".format(r5.clip(q, 120)),
                 reasoning="{0}{1}".format(area_line, " The bill's direction ({0}: {1}) does not settle an "
                                           "amendment's.".format(bkey, bill["direction"]) if bill else ""))
        return e
    e.update(status="needs_reading",
             read_first="The kind of vote could not be read from its wording ('{0}'): read the "
                        "question put, then write yea/nay.".format(r5.clip(q, 120)),
             reasoning="{0} Nothing proposed.".format(area_line))
    return e


def draft(conn, cc, config_dir=None, today=None, log=print, wl=None):
    """Append drafts for every qualifying division not yet in the stance file.
    Returns {'new': n, 'draft': n, 'procedural': n, 'needs_reading': n,
    'existing': n}. An existing entry is never touched."""
    spec = SPECS[cc]
    path = stance_path(cc, config_dir)
    divs, bills, _ = load(cc, config_dir)
    counts = {"new": 0, "draft": 0, "procedural": 0, "needs_reading": 0, "existing": len(divs)}
    blocks = []
    for r in qualifying(conn, cc, wl):
        if r["key"] in divs:
            continue
        e = draft_entry(cc, r, bills, positions(conn, cc, r["key"]), today)
        divs[r["key"]] = e
        blocks.append(entry_yaml(e))
        counts["new"] += 1
        if e["status"] == "needs_reading":
            counts["needs_reading"] += 1
        elif e.get("placeable") is False:
            counts["procedural"] += 1
        else:
            counts["draft"] += 1
    if not blocks and os.path.exists(path):
        return counts
    if not os.path.exists(path):
        text = header(cc) + "\nbill_directions: []\n\ndivisions:\n"
    else:
        with open(path, encoding="utf-8") as h:
            text = h.read()
        last = [ln for ln in text.splitlines() if re.match(r"^[A-Za-z_]+:", ln)]
        if not last or not last[-1].startswith("divisions:"):
            raise SystemExit("{0}: `divisions:` is not the last section; the drafter appends "
                             "to the end and will not write".format(path))
        if re.search(r"^divisions:\s*\[\]\s*$", text, re.M):
            text = re.sub(r"^divisions:\s*\[\]\s*$", "divisions:", text, flags=re.M)
        if not text.endswith("\n"):
            text += "\n"
    if blocks:
        text += "\n  # --- drafted {0} by {1} ---\n".format(today or datetime.date.today().isoformat(),
                                                           DRAFTED_BY)
        text += "\n".join(blocks)
    with open(path, "w", encoding="utf-8") as h:
        h.write(text)
    log("{0}: {1} new draft(s) -> {2} ({3} with proposed values, {4} procedural, {5} need "
        "reading; {6} already on file)".format(spec.name, counts["new"], os.path.relpath(path, ROOT)
                                               if path.startswith(ROOT) else path, counts["draft"],
                                               counts["procedural"], counts["needs_reading"],
                                               counts["existing"]))
    return counts


# --- the sign-off --------------------------------------------------------------------

def signers(cc):
    """Named signers for a country (config/stance_signers.yaml) plus Chris."""
    import yaml
    named = []
    if os.path.exists(SIGNERS_PATH):
        with open(SIGNERS_PATH, encoding="utf-8") as h:
            got = (yaml.safe_load(h) or {}).get("signers") or {}
        named = [str(x) for x in (got.get(cc) or [])]
    return named + [x for x in ALWAYS_SIGNS if x not in named]


def confirmable(e):
    """None when the entry can be confirmed as it stands, else the reason not."""
    if not e:
        return "no such entry"
    st = e.get("status")
    if st == "confirmed":
        return "already confirmed"
    if st == "needs_reading":
        return "needs_reading: write yea/nay (or placeable: false) and set status: draft first"
    if e.get("placeable") is not False and all(e.get(k) is None for k in r5.VALUE_KEYS):
        return "no values to confirm"
    return None


_KEY_LINE = re.compile(r"""^\s*-\s+key:\s*(?:"((?:[^"\\]|\\.)*)"|'([^']*)'|([^#\s][^#]*?))\s*(?:#.*)?$""")


def line_key(line):
    """The key on a `- key: ...` line (double-quoted, single-quoted or bare),
    or None. Keys may hold '#' (Austria's), so a quoted key is read whole."""
    m = _KEY_LINE.match(line.rstrip("\n"))
    if not m:
        return None
    if m.group(1) is not None:
        return json.loads('"{0}"'.format(m.group(1)))
    return (m.group(2) if m.group(2) is not None else m.group(3)).strip()


def confirm(cc, keys, by, on=None, config_dir=None, log=print):
    """Confirm drafted entries by key: status draft -> confirmed, with
    confirmed_by and confirmed_on. A text edit (comments survive). Returns
    the keys confirmed; refuses the rest with the reason."""
    by = (by or "").strip()
    if not by:
        raise SystemExit("--by NAME is required: a confirmation names the person")
    allowed = signers(cc)
    if by not in allowed:
        raise SystemExit("{0} is not a named signer for {1} ({2}); add them to "
                         "config/stance_signers.yaml first".format(by, cc, ", ".join(allowed)))
    on = on or datetime.date.today().isoformat()
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", on):
        raise SystemExit("--on must be an ISO date")
    divs, _, _ = load(cc, config_dir)
    path = stance_path(cc, config_dir)
    with open(path, encoding="utf-8") as h:
        lines = h.read().splitlines(keepends=True)
    ok, refused = [], []
    want = set()
    for k in keys:
        why = confirmable(divs.get(k))
        if why:
            refused.append((k, why))
        else:
            want.add(k)
    out, current, in_divs = [], None, False
    for line in lines:
        if re.match(r"^[A-Za-z_]+:", line):
            in_divs = line.startswith("divisions:")
        k = line_key(line)
        if k is not None:
            current = k if in_divs and k in want else None
        if current and re.match(r"^\s*status:\s*draft\s*(#.*)?$", line):
            ind = re.match(r"^(\s*)", line).group(1)
            out.append("{0}status: confirmed\n{0}confirmed_by: {1}\n{0}confirmed_on: \"{2}\"\n".format(
                ind, _q(by), on))
            ok.append(current)
            current = None
            continue
        out.append(line)
    if ok:
        with open(path, "w", encoding="utf-8") as h:
            h.write("".join(out))
    for k, why in refused:
        log("  refused {0}: {1}".format(k, why))
    log("{0}: confirmed {1} reading(s) by {2} on {3}{4}".format(
        cc, len(ok), by, on, ": " + ", ".join(ok) if ok else ""))
    return ok


def sign_from_doc(cc, by, on=None, config_dir=None, docs_dir=None, log=print):
    with open(doc_path(cc, docs_dir), encoding="utf-8") as h:
        keys = r5.ticked_keys(h.read())
    divs, _, _ = load(cc, config_dir)
    keys = [k for k in keys if (divs.get(k) or {}).get("status") != "confirmed"]
    if not keys:
        log("{0}: nothing ticked that is not already confirmed".format(cc))
        return []
    return confirm(cc, keys, by, on, config_dir, log)


def _fmt(v):
    return "no value" if v is None else "{0:+d}".format(v)


def signoff_markdown(cc, config_dir=None, keep_ticks=()):
    """docs/5ca-<cc>-readings.md: the proposed readings and the procedural
    calls as checkboxes (tick, then --sign-from-doc --by NAME), the ones that
    need reading as a list. `keep_ticks` are keys ticked in the previous
    version and not yet applied: they stay ticked."""
    spec = SPECS[cc]
    divs, bills, _ = load(cc, config_dir)
    keep = set(keep_ticks)
    groups = {"proposed": [], "procedural": [], "needs_reading": [], "confirmed": []}
    for k, e in divs.items():
        st = e.get("status")
        if st == "confirmed" and confirmable(dict(e, status="draft")) is None \
                and e.get("confirmed_by") and e.get("confirmed_on"):
            groups["confirmed"].append((k, e))
        elif st == "needs_reading" or st not in ("draft", "confirmed"):
            groups["needs_reading"].append((k, e))
        elif e.get("placeable") is False:
            groups["procedural"].append((k, e))
        else:
            groups["proposed"].append((k, e))
    for g in groups.values():
        g.sort(key=lambda kv: (str(kv[1].get("dated") or ""), kv[0]), reverse=True)
    out = ["# {0} 5CA: readings to sign".format(spec.name), "",
           "Drafted by `tools/country_5ca.py` (src/country5ca.py) from the store's watched and "
           "tier-1 votes, by rules, never by a model. **Nothing here places anyone until a named "
           "person confirms it.** {0}".format(spec.note).strip(), "",
           "**How to sign.** Tick `[x]` on each reading you accept as drafted, then run "
           "`python3 tools/country_5ca.py --cc {0} --sign-from-doc --by NAME` (it sets "
           "`status: confirmed` with `confirmed_by` and `confirmed_on` in `config/{0}_stance.yaml`). "
           "To change a value, edit the stance file first. A reading that needs reading has no "
           "box: write `yea:`/`nay:` in the stance file, set `status: draft`, then confirm it.".format(cc),
           "", "Counts: {0} proposed, {1} procedural (evidence only), {2} need reading, {3} confirmed."
           .format(*(len(groups[g]) for g in ("proposed", "procedural", "needs_reading", "confirmed"))),
           ""]
    labels = {"yea": spec.labels[0], "nay": spec.labels[1]}
    if groups["proposed"]:
        out += ["## Proposed readings", ""]
        for k, e in groups["proposed"]:
            box = "[x]" if k in keep else "[ ]"
            out.append("### {0} `{1}` {2}".format(box, k, r5.clip(e.get("title"), 160)))
            out.append("")
            meta = [str(x) for x in (e.get("dated"), spec.chambers.get(e.get("chamber"), e.get("chamber")),
                                     e.get("result")) if x]
            if meta:
                out.append("- **When / result:** " + "; ".join(meta))
            if e.get("on"):
                out.append("- **On:** " + r5.clip(e["on"], 300))
            if e.get("lobbies"):
                out.append("- **Lobbies:** " + r5.clip(e["lobbies"], 400))
            out.append("- **Proposed direction:** {0} {1} ({2}); {3} {4} ({5})".format(
                labels["yea"], _fmt(e.get("yea")), r5.clip(e.get("why_yea"), 220),
                labels["nay"], _fmt(e.get("nay")), r5.clip(e.get("why_nay"), 220)))
            if e.get("reasoning"):
                out.append("- **Reasoning:** " + r5.clip(e["reasoning"], 500))
            if e.get("flag"):
                out.append("- **Flag for you:** " + r5.clip(e["flag"], 300))
            out.append("")
    if groups["procedural"]:
        out += ["## Procedural (evidence only once confirmed)", ""]
        for k, e in groups["procedural"]:
            box = "[x]" if k in keep else "[ ]"
            out.append("### {0} `{1}` {2}".format(box, k, r5.clip(e.get("title"), 160)))
            out.append("")
            out.append("- {0}; {1}".format(e.get("dated") or "?", r5.clip(e.get("reason"), 300)))
            out.append("")
    if groups["needs_reading"]:
        out += ["## Needs reading (no box: write the values first)", ""]
        for k, e in groups["needs_reading"]:
            out.append("- `{0}` {1} {2} [{3}]: {4}".format(
                k, e.get("dated") or "?", r5.clip(e.get("title"), 110), e.get("vote_kind") or "?",
                r5.clip(e.get("read_first"), 220)))
        out.append("")
    if groups["confirmed"]:
        out += ["## Confirmed", ""]
        for k, e in groups["confirmed"]:
            out.append("### [x] `{0}` {1}".format(k, r5.clip(e.get("title"), 160)))
            out.append("")
            out.append("- {0} {1} / {2} {3}; confirmed by {4} on {5}".format(
                labels["yea"], _fmt(e.get("yea")), labels["nay"], _fmt(e.get("nay")),
                e.get("confirmed_by"), e.get("confirmed_on")))
            out.append("")
    if bills:
        out += ["## Bill directions on file (inputs to the drafts; they place nobody)", ""]
        for k, b in bills.items():
            out.append("- `{0}` {1}: {2} ({3})".format(k, b.get("direction"),
                                                      r5.clip(b.get("why"), 200), b.get("status") or "draft"))
        out.append("")
    return "\n".join(out) + "\n"


def write_signoff_doc(cc, config_dir=None, docs_dir=None, log=print):
    """Rewrite the guide, keeping ticks on entries not yet confirmed (the
    weekly job must never throw away a tick a person made). Returns the
    keys ticked but not applied."""
    path = doc_path(cc, docs_dir)
    keep = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as h:
            ticked = r5.ticked_keys(h.read())
        divs, _, _ = load(cc, config_dir)
        keep = [k for k in ticked if (divs.get(k) or {}).get("status") != "confirmed"]
    divs, _, _ = load(cc, config_dir)
    if not divs:
        return keep
    with open(path, "w", encoding="utf-8") as h:
        h.write(signoff_markdown(cc, config_dir, keep))
    if keep:
        log("  {0}: {1} ticked in the guide but not yet confirmed (run --sign-from-doc --by NAME)"
            .format(cc, len(keep)))
    return keep


# --- the 5CA sheet -------------------------------------------------------------------

def _is_confirmed(e):
    return r5.status(e) == "confirmed"


def build_rows(conn, cc, chamber, area, entries, today=None):
    """(rows, divisions listed, the latest decisive division) for one chamber
    and area: src/readings5ca.py's placement over CONFIRMED readings only."""
    spec = SPECS[cc]
    today = today or datetime.date.today().isoformat()
    listed = [e for e in entries.values()
              if area in (e.get("areas") or []) and str(e.get("chamber") or "") == str(chamber)]
    listed.sort(key=lambda e: (str(e.get("dated") or ""), str(e["key"])))
    roster = {}
    for m in _rows(conn, spec.roster_sql):
        if str(m.get("chamber") or chamber) not in (chamber, spec.chambers.get(chamber)):
            continue
        roster[str(m["member_id"])] = m
    per = {}

    def rec(pid):
        return per.setdefault(pid, {"scored": [], "lines": [], "voted": False, "name": None,
                                    "party": None, "derived": False})

    for pid, m in roster.items():
        if m.get("sitting"):
            rec(pid)
    votes = {}
    for e in listed:
        key = str(e["key"])
        pos = positions(conn, cc, key)
        votes[key] = {str(p["member_id"]): p for p in pos}
        base = "{0} {1}{2}".format(e.get("dated") or "?", r5.clip(e.get("title"), 90),
                                   " (on {0})".format(r5.clip(e.get("on"), 60)) if e.get("on") else "")
        for p in pos:
            pid = str(p["member_id"])
            r = rec(pid)
            r["name"] = r["name"] or p["name"]
            r["party"] = p["party"] or r["party"]
            side = spec.side(p["position"])
            if p["derived"]:
                label = "VOTE {0} DERIVED from the {1} group vote (X5): {2}".format(
                    p["position"] or "?", p["party"] or "?", base)
            else:
                label = "VOTE {0} ({1}): {2}".format(p["position"] or "?", p["party"] or "?", base)
            if side not in ("yea", "nay"):
                r["lines"].append(label + " [no direction recorded]")
                continue
            r["voted"] = True
            s, why = r5.value(e, side)
            if s is not None:
                kind = "derived" if p["derived"] else "vote"
                r["derived"] = r["derived"] or p["derived"]
                r["scored"].append((s, e.get("dated") or "", label, kind))
                r["lines"].append("{0} [{1:+d}: {2}]".format(label, s, r5.clip(why, 120)))
            else:
                st = r5.status(e)
                r["lines"].append("{0} [{1}]".format(
                    label, "awaiting sign-off -- not placed" if st in ("draft", "unread")
                    else r5.not_placed(e)))
    decisive = [e for e in listed if _is_confirmed(e)
                and max(e.get("yea") or 0, e.get("nay") or 0) >= 2]
    latest = decisive[-1] if decisive else None
    rows = []
    for pid, r in per.items():
        m = roster.get(pid) or {}
        sitting = bool(m.get("sitting")) if m else False
        if not sitting and not r["voted"]:
            continue
        cap = None
        if latest is not None and not r["derived"]:
            got = votes.get(str(latest["key"]), {}).get(pid)
            if got is not None and spec.side(got["position"]) not in ("yea", "nay"):
                cap = ("CAPPED at +: recorded as '{0}' on the latest confirmed decisive vote "
                       "({1}, {2}). ++ means 'will vote with us'.".format(
                           got["position"], latest.get("dated"), r5.clip(latest.get("title"), 60)))
        row = r5.finish_row(pid, r["lines"], r["scored"], WEIGHTS, m.get("name") or r["name"],
                            m.get("party") or r["party"], None, sitting, cap_note=cap, today=today)
        best = r5.place(r["scored"], WEIGHTS)[2]
        if best is not None and best[3] == "derived":
            row["based_on"] = "DERIVED from the group vote (X5), {0}".format(best[1][:10])
            row["confidence"] = "derived (group vote, confirmed reading; not the member's own record)"
            row["decision_maker"] += " [DERIVED]"
        rows.append(row)
    return r5.sort_rows(rows), listed, latest


def sheet_path(cc, chamber, area, out_dir=None):
    from src.latam import AREA_LABELS
    name = AREA_LABELS.get(area, "area-{0}".format(area))
    return os.path.join(out_dir or OUT_DIR, "{0}-5ca-{1}-{2}.csv".format(
        cc, r5.slug(str(chamber)), r5.slug(name)))


def sheet_pairs(cc, entries):
    """Every (chamber, area) a country's readings touch, excluded areas left out."""
    excluded = r5.excluded_areas(ROOT)
    pairs = set()
    for e in entries.values():
        for a in e.get("areas") or []:
            if a not in excluded:
                pairs.add((str(e.get("chamber") or ""), a))
    return sorted(pairs, key=lambda p: (str(p[0]), p[1]))


def publishable_sheets(conn, cc, config_dir=None, today=None, entries=None):
    """THE GATE, shared by the CSV sheets and the web pages (tools/make_country_5ca_web.py):
    yield one dict per chamber and area that has at least one CONFIRMED reading
    placing someone, and None-valued `rows` for the rest so a caller can remove a
    stale output. Keys: chamber, area, rows, listed, signed, unsigned, placed."""
    if entries is None:
        entries = load(cc, config_dir)[0]
    for chamber, area in sheet_pairs(cc, entries):
        listed_here = [e for e in entries.values()
                       if area in (e.get("areas") or []) and str(e.get("chamber") or "") == chamber]
        if not any(_is_confirmed(e) for e in listed_here):
            # No confirmed reading here: nothing can place anyone, so the store
            # is not even read (a country awaiting sign-off needs no store).
            yield {"chamber": chamber, "area": area, "rows": None, "listed": listed_here,
                   "signed": 0, "unsigned": 0, "placed": 0}
            continue
        rows, listed, _latest = build_rows(conn, cc, chamber, area, entries, today)
        placed = [r for r in rows if r["column"] != "0"]
        s, u = r5.area_counts([{"division_key": str(e["key"])} for e in listed],
                              {str(e["key"]): e for e in listed})
        yield {"chamber": chamber, "area": area, "rows": rows if placed else None,
               "listed": listed, "signed": s, "unsigned": u, "placed": len(placed)}


def run_sheets(conn, cc, config_dir=None, out_dir=None, today=None, log=print):
    """Write a sheet for every chamber and area with at least one CONFIRMED
    reading that places someone; remove a sheet whose readings are no longer
    confirmed. Returns the paths written."""
    from src.latam import AREA_LABELS
    out_dir = out_dir or OUT_DIR
    written = []
    for sh in publishable_sheets(conn, cc, config_dir, today):
        chamber, area, rows = sh["chamber"], sh["area"], sh["rows"]
        path = sheet_path(cc, chamber, area, out_dir)
        if rows is None:
            if os.path.exists(path):
                os.remove(path)
                log("  {0} {1}: no confirmed reading places anyone now; removed {2}".format(
                    cc, area, os.path.basename(path)))
            continue
        footer = r5.readings_line(sh["signed"], sh["unsigned"], AREA_LABELS.get(area, str(area)))
        if cc in PARTY_GROUP:
            footer += " Rows marked [DERIVED] carry the group's vote, not the member's own (X5)."
        tally = r5.write_sheet(path, rows, footer)
        written.append(path)
        log("  {0} {1} {2}: {3} placed; {4} confirmed / {5} unconfirmed -> {6}  ({7})".format(
            cc, chamber, AREA_LABELS.get(area, area), sh["placed"], sh["signed"], sh["unsigned"],
            os.path.basename(path),
            "  ".join("{0} x{1}".format(c, tally[c]) for c in r5.COLUMNS)))
    return written


# --- counts and the digest ------------------------------------------------------------

def counts(cc, config_dir=None):
    divs, bills, _ = load(cc, config_dir)
    c = {"proposed": 0, "procedural": 0, "needs_reading": 0, "confirmed": 0, "bills": len(bills)}
    for e in divs.values():
        st = r5.status(e)
        if st in ("confirmed", "unplaceable") and e.get("status") == "confirmed":
            c["confirmed"] += 1
        elif e.get("status") == "needs_reading" or st == "unread":
            c["needs_reading"] += 1
        elif e.get("placeable") is False:
            c["procedural"] += 1
        else:
            c["proposed"] += 1
    return c


def digest_text(today=None, config_dir=None, docs_dir=None, per_country=4, countries=COUNTRIES):
    """The weekly 'stances awaiting sign-off' DM, or None when nothing waits."""
    today = today or datetime.date.today().isoformat()
    y, w, _ = datetime.date.fromisoformat(today).isocalendar()
    parts, waiting = [], 0
    for cc in countries:
        if not os.path.exists(stance_path(cc, config_dir)):
            continue
        spec = SPECS[cc]
        c = counts(cc, config_dir)
        pending = c["proposed"] + c["procedural"] + c["needs_reading"]
        if not pending:
            continue
        waiting += pending
        names = [s for s in signers(cc) if s not in ALWAYS_SIGNS]
        ticked = []
        dp = doc_path(cc, docs_dir)
        if os.path.exists(dp):
            divs, _, _ = load(cc, config_dir)
            with open(dp, encoding="utf-8") as h:
                ticked = [k for k in r5.ticked_keys(h.read())
                          if (divs.get(k) or {}).get("status") != "confirmed"]
        head = "*{0}* ({1}): {2} proposed, {3} procedural, {4} need reading, {5} confirmed".format(
            spec.name, "signer: " + ", ".join(names) if names else "country signer not named yet",
            c["proposed"], c["procedural"], c["needs_reading"], c["confirmed"])
        if ticked:
            head += "; *{0} ticked in the guide, not yet applied*".format(len(ticked))
        lines = [head]
        divs, _, _ = load(cc, config_dir)
        props = sorted(((k, e) for k, e in divs.items() if e.get("status") == "draft"
                        and e.get("placeable") is not False),
                       key=lambda kv: (str(kv[1].get("dated") or ""), kv[0]), reverse=True)
        for k, e in props[:per_country]:
            lines.append("  - `{0}` {1} {2}: {3} {4} / {5} {6}".format(
                k, e.get("dated") or "?", r5.clip(e.get("title"), 70), spec.labels[0],
                _fmt(e.get("yea")), spec.labels[1], _fmt(e.get("nay"))))
        if len(props) > per_country:
            lines.append("  - and {0} more proposed".format(len(props) - per_country))
        lines.append("  Guide: docs/5ca-{0}-readings.md".format(cc))
        parts.append("\n".join(lines))
    if not waiting:
        return None
    return ("*Stances awaiting sign-off*, week {0} of {1}: {2} readings across {3} countries. "
            "Nothing places anyone in a 5CA until a named person confirms it.\n\n{4}\n\n"
            "To confirm: tick in the country's guide, then "
            "`python3 tools/country_5ca.py --cc CC --sign-from-doc --by NAME`, or "
            "`--confirm KEY --by NAME`. Who signs for each country is "
            "config/stance_signers.yaml (country teams are the natural owners)."
            .format(w, y, waiting, len(parts), "\n\n".join(parts)))
