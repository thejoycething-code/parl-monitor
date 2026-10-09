#!/usr/bin/env python3
"""Netherlands: the Tweede Kamer's fracties, members, and every vote with
every recorded position, from the Open Data Portaal.

    python3 tools/nl_rollcalls.py                  # the rolling window
    python3 tools/nl_rollcalls.py --since 2026-01-01
    python3 tools/nl_rollcalls.py --dry-run        # one page, store nothing
    python3 tools/nl_rollcalls.py --reclassify     # re-derive areas, offline
    python3 tools/nl_rollcalls.py --db /tmp/nl.db  # anywhere but the store

PHASE 1 (9 October 2026); see docs/netherlands-scope.md. One source, open,
keyless and official: the Tweede Kamer's OData v4 API at
gegevensmagazijn.tweedekamer.nl/OData/v4/2.0/. Measured that day:

  * Besluit (a decision) -> Stemming (one row per position) -> Zaak (the
    motion, amendment or bill voted on) -> Kamerstukdossier (the bill's
    dossier). One query with $expand brings all four, 250 decisions a page,
    about 13 seconds a page.
  * 4,860 votes since the current Kamer was installed on 12 November 2025:
    4,815 by show of hands (one position per fractie, with its seats) and
    45 roll calls (hoofdelijk: one position per member, 150 rows).
  * $top above 250 is a 400. Paging is by @odata.nextLink, never $skip.

POSITIONS ARRIVE LATE. The portal publishes a decision the evening it is
taken and its positions up to a day later: the 21 votes of 8 October 2026,
read at 06:00 the next morning, carried a result and no positions. So each
run re-reads a ROLLING WINDOW (the last six weeks of voting days), a
decision with no positions is stored with `positions_pending = 1`, and the
next run fills it. Still empty after two weeks is a gap.

A VOTE IS CLASSIFIED WITH ITS ZAAK AND DOSSIER. A motion's onderwerp ("Motie
van het lid X over ...") is its own text and is matched alone into
`own_areas`; `areas` adds the zaak's title and its dossier's title, so an
amendment to the Embryowet carries area 10 even when its own line says only
"over een verbod op het bevorderen van verboden handelingen".

CLASSIFICATION waits for Chris. The Dutch term list is PROPOSED in
docs/netherlands-scope.md and becomes config/taxonomy-nl.yaml only once he
approves it. Until that file exists, areas come from config/watchlist-nl.yaml
alone (by dossier number or zaaknummer, never title), and --reclassify
re-derives everything offline the day it lands. The English taxonomy is
not used: measured on 12,877 zaken of this Kamer it found 21 on our ground,
where the draft Dutch list found 393.

Separation guarantee: writes nl_* tables and the shared gaps table only.
ONE WRITER AT A TIME on the store.

Exit codes: 0 clean; 3 stored what it could and recorded gaps (the weekly
job still publishes); anything else is a failure.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
from urllib.parse import quote

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, drain, filter as filt, nl_store  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402

FEED = "nl-rollcalls"
BASE = "https://gegevensmagazijn.tweedekamer.nl/OData/v4/2.0/"
TAXONOMY = os.path.join(ROOT, "config", "taxonomy-nl.yaml")
# The current Kamer was installed after the election of 29 October 2025;
# 52 of today's 150 seats carry this start date (the rest are later
# replacements, or members re-seated from the previous Kamer). The first
# run reads from here.
TERM_START = "2025-11-12"
WINDOW_DAYS = 42
PENDING_GAP_DAYS = 14
BUDGET_S = 2700.0
# Migration is collated, never campaigned (src/partner.py HIDDEN_AREAS).
HIDDEN_AREAS = (11,)
# The portal answers in Amsterdam time; a filter needs an offset. +02:00 is
# right in summer and starts the window an hour early in winter, which only
# widens it.
TZ = "+02:00"

DECISIONS = (
    "Besluit?$filter={flt}&$expand={exp}")
DECISION_EXPAND = (
    "Stemming($filter=Verwijderd eq false;$select=Id,Soort,FractieGrootte,ActorNaam,"
    "ActorFractie,Vergissing,Persoon_Id,Fractie_Id),"
    "Zaak($select=Id,Nummer,Soort,Titel,Onderwerp,GestartOp,Kabinetsappreciatie,Afgedaan;"
    "$expand=Kamerstukdossier($select=Nummer,Toevoeging,Titel)),"
    "Agendapunt($select=Id,Onderwerp;$expand=Activiteit($select=Id,Datum,Soort))")
FRACTIES = ("Fractie?$filter=Verwijderd eq false and DatumInactief eq null"
            "&$select=Id,Afkorting,NaamNL,AantalZetels,DatumActief,DatumInactief")
MEMBERS = ("FractieZetelPersoon?$filter=Verwijderd eq false and TotEnMet eq null"
           "&$select=Id,Functie,Van,Persoon_Id"
           "&$expand=Persoon($select=Id,Roepnaam,Initialen,Tussenvoegsel,Achternaam),"
           "FractieZetel($select=Id;$expand=Fractie($select=Id,Afkorting))")
# Data minimisation: the Persoon record also carries date and place of
# birth, residence and gender. None of it is needed to report a vote, so
# none of it is requested.

TALLY = re.compile(r"\((\d+)\s*-\s*(\d+)\)")


def url(path):
    """Percent-encode a query path the way the portal accepts it: spaces and
    '+' encoded (a bare '+' is read as a space, which breaks a time offset),
    the OData punctuation and the string quotes left alone."""
    return BASE + quote(path, safe="$(),=;/?&:'-")


def _gap(conn, today, detail):
    conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) VALUES (?,?,?)",
                 (today, FEED, detail))


def iso_date(stamp):
    return (stamp or "")[:10] or None


def dossier_key(k):
    """{'Nummer': 36800, 'Toevoeging': 'XVI'} -> '36800-XVI'; no Toevoeging -> '36800'."""
    if not k or k.get("Nummer") is None:
        return None
    extra = (k.get("Toevoeging") or "").strip()
    return "{0}-{1}".format(k["Nummer"], extra) if extra else str(k["Nummer"])


def member_name(p):
    """Roepnaam, tussenvoegsel, achternaam: 'Kati Piri', 'Diederik van Dijk'."""
    if not p:
        return None
    first = p.get("Roepnaam") or p.get("Initialen")
    return " ".join(x for x in (first, p.get("Tussenvoegsel"), p.get("Achternaam")) if x) or None


def on_our_ground(areas):
    return any(a not in HIDDEN_AREAS for a in (areas or []))


# --- classification ----------------------------------------------------------

def load_taxonomy(path=TAXONOMY, log=print):
    """The Dutch taxonomy, or an empty one until Chris approves it."""
    if path and os.path.exists(path):
        return filt.load_taxonomy(path)
    log("  taxonomy-nl: not yet approved (docs/netherlands-scope.md); areas come "
        "from config/watchlist-nl.yaml alone until it is")
    return filt.Taxonomy(version="none", terms={}, exclusions=set())


def empty_watchlist():
    """watchlist-nl is applied by KEY (nl_store.add_watch_areas), so the
    filter itself gets no title entities."""
    return filt.Watchlist(entities=[], bill_titles=[], act_shorts=[])


def classify_zaak(tax, z, watch_path=None):
    """(own FilterResult, full FilterResult) for one parsed zaak."""
    wl = empty_watchlist()
    own = filt.filter_item(tax, wl, z["onderwerp"] or "", title=z["onderwerp"] or "")
    full = filt.filter_item(tax, wl, z["onderwerp"] or "", z["titel"] or "",
                            *z["dossier_titels"], title=z["onderwerp"] or "")
    nl_store.add_watch_areas(full, z["nummer"], z["dossiers"], path=watch_path)
    return own, full


# --- parsing -------------------------------------------------------------------

def parse_zaak(raw):
    ks = [k for k in (raw.get("Kamerstukdossier") or []) if k]
    return {
        "nummer": raw.get("Nummer"),
        "id": raw.get("Id"),
        "soort": raw.get("Soort"),
        "onderwerp": (raw.get("Onderwerp") or "").strip() or None,
        "titel": (raw.get("Titel") or "").strip() or None,
        "dossiers": [d for d in (dossier_key(k) for k in ks) if d],
        "dossier_titels": [(k.get("Titel") or "").strip() for k in ks if k.get("Titel")],
        "gestart": iso_date(raw.get("GestartOp")),
        "kabinetsappreciatie": raw.get("Kabinetsappreciatie"),
        "afgedaan": raw.get("Afgedaan"),
    }


def parse_decision(raw):
    """One expanded Besluit -> dict, or None when it is not a vote."""
    if not raw.get("StemmingsSoort") or raw.get("StemmingsSoort") == "Zonder stemming":
        return None
    ap = raw.get("Agendapunt") or {}
    act = ap.get("Activiteit") or {}
    positions = []
    for s in raw.get("Stemming") or []:
        if s.get("Verwijderd"):
            continue
        kind = "lid" if s.get("Persoon_Id") else "fractie"
        positions.append({
            "id": s.get("Id"), "kind": kind,
            "fractie": s.get("ActorFractie"), "fractie_id": s.get("Fractie_Id"),
            "persoon_id": s.get("Persoon_Id"), "actor": s.get("ActorNaam"),
            "position": s.get("Soort"),
            "zetels": s.get("FractieGrootte") if kind == "fractie" else None,
            "vergissing": 1 if s.get("Vergissing") else 0,
        })
    zaken = [parse_zaak(z) for z in (raw.get("Zaak") or []) if z.get("Nummer")]
    return {
        "id": raw.get("Id"),
        "deleted": bool(raw.get("Verwijderd")),
        "date": iso_date(act.get("Datum")),
        "stemmingssoort": raw.get("StemmingsSoort"),
        "besluit_soort": raw.get("BesluitSoort"),
        "besluit_tekst": raw.get("BesluitTekst"),
        "agendapunt": ap.get("Onderwerp"),
        "zaken": zaken,
        "positions": positions,
    }


def tally(d):
    """(voor, tegen, niet_deelgenomen): seats for a show of hands, members for
    a roll call. A group that declared its vote a mistake still counts as it
    voted: the Kamer's result stands, and `vergissing` records the claim.

    A GROUP CAN SPLIT on a show of hands. Measured on motion 2026Z08607:
    the Groep Markuszower row says Tegen with all 7 seats, and three of its
    members carry rows of their own saying Voor. Counting both gives 153 of
    150; so each member who votes apart counts once and comes off the
    group's seats."""
    out = {"Voor": 0, "Tegen": 0, "Niet deelgenomen": 0}
    apart = {}
    for p in d["positions"]:
        if p["kind"] == "lid":
            apart[p["fractie"]] = apart.get(p["fractie"], 0) + 1
    for p in d["positions"]:
        if p["position"] not in out:
            continue
        if p["kind"] == "fractie":
            out[p["position"]] += max((p["zetels"] or 0) - apart.get(p["fractie"], 0), 0)
        else:
            out[p["position"]] += 1
    if not d["positions"]:
        hit = TALLY.search(d.get("besluit_tekst") or "")
        if hit:
            return int(hit.group(1)), int(hit.group(2)), None
        return None, None, None
    return out["Voor"], out["Tegen"], out["Niet deelgenomen"]


# --- storing -------------------------------------------------------------------

def store_zaak(conn, z, tax, today, watch_path=None):
    own, full = classify_zaak(tax, z, watch_path)
    conn.execute(
        "INSERT INTO nl_zaken (zaak_nummer, zaak_id, soort, onderwerp, titel, dossiers, "
        "dossier_titels, gestart, kabinetsappreciatie, afgedaan, own_areas, areas, "
        "matched_terms, tier, first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(zaak_nummer) DO UPDATE SET zaak_id=excluded.zaak_id, soort=excluded.soort, "
        "onderwerp=excluded.onderwerp, titel=excluded.titel, dossiers=excluded.dossiers, "
        "dossier_titels=excluded.dossier_titels, gestart=excluded.gestart, "
        "kabinetsappreciatie=excluded.kabinetsappreciatie, afgedaan=excluded.afgedaan, "
        "own_areas=excluded.own_areas, areas=excluded.areas, "
        "matched_terms=excluded.matched_terms, tier=excluded.tier, last_seen=excluded.last_seen",
        (z["nummer"], z["id"], z["soort"], z["onderwerp"], z["titel"],
         nl_store.dumps(z["dossiers"]), nl_store.dumps(z["dossier_titels"]), z["gestart"],
         z["kabinetsappreciatie"], None if z["afgedaan"] is None else int(bool(z["afgedaan"])),
         nl_store.dumps(own.issue_areas), nl_store.dumps(full.issue_areas),
         nl_store.dumps((full.matched_terms or []) + (full.watchlist_hits or [])),
         full.tier, today, today))
    return full.issue_areas


def delete_division(conn, besluit_id):
    conn.execute("DELETE FROM nl_votes WHERE besluit_id=?", (besluit_id,))
    return conn.execute("DELETE FROM nl_divisions WHERE besluit_id=?", (besluit_id,)).rowcount


def store_division(conn, d, tax, today, watch_path=None):
    """Store one vote, its zaak and its positions. Returns the vote's areas.

    Positions are replaced wholesale on every read: the portal's set for a
    decision is authoritative, and a position it withdraws must not linger."""
    areas = set()
    for z in d["zaken"]:
        areas.update(store_zaak(conn, z, tax, today, watch_path))
    voor, tegen, niet = tally(d)
    zaak = d["zaken"][0]["nummer"] if d["zaken"] else None
    conn.execute(
        "INSERT INTO nl_divisions (besluit_id, zaak_nummer, date, stemmingssoort, besluit_soort, "
        "besluit_tekst, agendapunt, voor, tegen, niet_deelgenomen, positions_pending, areas, "
        "first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(besluit_id) DO UPDATE SET zaak_nummer=excluded.zaak_nummer, "
        "date=excluded.date, stemmingssoort=excluded.stemmingssoort, "
        "besluit_soort=excluded.besluit_soort, besluit_tekst=excluded.besluit_tekst, "
        "agendapunt=excluded.agendapunt, voor=excluded.voor, tegen=excluded.tegen, "
        "niet_deelgenomen=excluded.niet_deelgenomen, "
        "positions_pending=excluded.positions_pending, areas=excluded.areas, "
        "last_seen=excluded.last_seen",
        (d["id"], zaak, d["date"], d["stemmingssoort"], d["besluit_soort"], d["besluit_tekst"],
         d["agendapunt"], voor, tegen, niet, 0 if d["positions"] else 1,
         nl_store.dumps(sorted(areas)), today, today))
    conn.execute("DELETE FROM nl_votes WHERE besluit_id=?", (d["id"],))
    for p in d["positions"]:
        conn.execute(
            "INSERT OR REPLACE INTO nl_votes (stemming_id, besluit_id, kind, fractie, fractie_id, "
            "persoon_id, actor, position, zetels, vergissing) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (p["id"], d["id"], p["kind"], p["fractie"], p["fractie_id"], p["persoon_id"],
             p["actor"], p["position"], p["zetels"], p["vergissing"]))
        if p["persoon_id"]:
            # A roll call names members who may have left since; keep them,
            # without overwriting what the members list says about the sitting ones.
            conn.execute(
                "INSERT INTO nl_members (persoon_id, name, fractie, first_seen, last_seen) "
                "VALUES (?,?,?,?,?) ON CONFLICT(persoon_id) DO NOTHING",
                (p["persoon_id"], p["actor"], p["fractie"], today, today))
    return sorted(areas)


# --- pulling -------------------------------------------------------------------

def window_start(conn, today, since=None):
    """The first voting day this run re-reads: --since, else the start of the
    Kamer on an empty store, else six weeks back."""
    if since:
        return since
    (have,) = conn.execute("SELECT COUNT(*) FROM nl_divisions").fetchone()
    if not have:
        return TERM_START
    start = datetime.date.fromisoformat(today) - datetime.timedelta(days=WINDOW_DAYS)
    return max(start.isoformat(), TERM_START)


def decisions_url(start):
    # No Verwijderd filter on the Besluit itself: a decision the Kamer
    # withdrew comes back flagged, and the store drops it.
    flt = ("StemmingsSoort ne null and Agendapunt/Activiteit/Datum ge "
           "{0}T00:00:00{1}".format(start, TZ))
    return url(DECISIONS.format(flt=flt, exp=DECISION_EXPAND))


def pull_decisions(conn, client, today, start, tax, log=print, budget=None,
                   watch_path=None, max_pages=None):
    """Every vote on a voting day from `start` on. Returns a dict of counts."""
    n = {"read": 0, "stored": 0, "ours": 0, "pending": 0, "deleted": 0, "gaps": 0, "pages": 0}
    next_url = decisions_url(start)
    while next_url:
        if budget is not None and budget.exhausted():
            log(budget.disclose("decision pages", n["pages"]))
            _gap(conn, today, "decisions from {0}: time budget reached after {1} page(s)".format(
                start, n["pages"]))
            n["gaps"] += 1
            break
        if max_pages is not None and n["pages"] >= max_pages:
            break
        try:
            page = client.get_json(next_url, FEED, "besluit-{0}-p{1:03d}".format(start, n["pages"]))
        except (FetchError, ValueError) as exc:
            _gap(conn, today, "decisions from {0}, page {1}: {2}".format(start, n["pages"], exc))
            log("  [gap] decisions page {0}: {1}".format(n["pages"], str(exc)[:80]))
            n["gaps"] += 1
            break
        n["pages"] += 1
        for raw in page.get("value") or []:
            d = parse_decision(raw)
            if d is None:
                continue
            n["read"] += 1
            if d["deleted"]:
                n["deleted"] += delete_division(conn, d["id"])
                continue
            areas = store_division(conn, d, tax, today, watch_path)
            n["stored"] += 1
            n["ours"] += on_our_ground(areas)
            if not d["positions"]:
                n["pending"] += 1
        conn.commit()
        next_url = page.get("@odata.nextLink")
    return n


def check_pending(conn, today, log=print):
    """A vote still without positions two weeks on is a gap, not a lag."""
    cutoff = (datetime.date.fromisoformat(today)
              - datetime.timedelta(days=PENDING_GAP_DAYS)).isoformat()
    rows = conn.execute("SELECT besluit_id, zaak_nummer, date FROM nl_divisions "
                        "WHERE positions_pending=1 AND date < ?", (cutoff,)).fetchall()
    for besluit_id, zaak, date in rows:
        _gap(conn, today, "vote {0} on {1} ({2}): no positions after {3} days".format(
            besluit_id, zaak, date, PENDING_GAP_DAYS))
        log("  [gap] vote on {0} ({1}): still no positions".format(zaak, date))
    conn.commit()
    return len(rows)


def pull_fracties(conn, client, today):
    page = client.get_json(url(FRACTIES), FEED, "fracties")
    rows = page.get("value") or []
    for f in rows:
        conn.execute(
            "INSERT INTO nl_fracties (fractie_id, afkorting, naam, zetels, actief_van, actief_tot, "
            "first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(fractie_id) DO UPDATE SET "
            "afkorting=excluded.afkorting, naam=excluded.naam, zetels=excluded.zetels, "
            "actief_van=excluded.actief_van, actief_tot=excluded.actief_tot, "
            "last_seen=excluded.last_seen",
            (f.get("Id"), f.get("Afkorting"), f.get("NaamNL"), f.get("AantalZetels"),
             iso_date(f.get("DatumActief")), iso_date(f.get("DatumInactief")), today, today))
    conn.commit()
    return len(rows)


def parse_members(rows):
    out = []
    for r in rows or []:
        p = r.get("Persoon") or {}
        pid = r.get("Persoon_Id") or p.get("Id")
        if not pid:
            continue
        fr = ((r.get("FractieZetel") or {}).get("Fractie") or {})
        out.append({"persoon_id": pid, "name": member_name(p), "fractie": fr.get("Afkorting"),
                    "functie": r.get("Functie"), "seat_from": iso_date(r.get("Van"))})
    return out


def pull_members(conn, client, today):
    rows, next_url, i = [], url(MEMBERS), 0
    while next_url:
        page = client.get_json(next_url, FEED, "members-p{0:03d}".format(i))
        rows += page.get("value") or []
        next_url, i = page.get("@odata.nextLink"), i + 1
    members = parse_members(rows)
    for m in members:
        conn.execute(
            "INSERT INTO nl_members (persoon_id, name, fractie, functie, seat_from, first_seen, "
            "last_seen) VALUES (?,?,?,?,?,?,?) ON CONFLICT(persoon_id) DO UPDATE SET "
            "name=COALESCE(excluded.name, nl_members.name), fractie=excluded.fractie, "
            "functie=excluded.functie, seat_from=excluded.seat_from, last_seen=excluded.last_seen",
            (m["persoon_id"], m["name"], m["fractie"], m["functie"], m["seat_from"], today, today))
    conn.commit()
    return len(members)


# --- offline -------------------------------------------------------------------

def reclassify(conn, tax, log=print, watch_path=None):
    """Re-derive zaak areas, then each vote's from its zaak, offline, after a
    taxonomy or watchlist-nl change."""
    changed_z = changed_d = 0
    for (nummer, onderwerp, titel, dossiers, titels, areas) in conn.execute(
            "SELECT zaak_nummer, onderwerp, titel, dossiers, dossier_titels, areas "
            "FROM nl_zaken").fetchall():
        z = {"nummer": nummer, "onderwerp": onderwerp, "titel": titel,
             "dossiers": json.loads(dossiers or "[]"), "dossier_titels": json.loads(titels or "[]")}
        own, full = classify_zaak(tax, z, watch_path)
        new = nl_store.dumps(full.issue_areas)
        changed_z += new != (areas or "[]")
        conn.execute("UPDATE nl_zaken SET own_areas=?, areas=?, matched_terms=?, tier=? "
                     "WHERE zaak_nummer=?",
                     (nl_store.dumps(own.issue_areas), new,
                      nl_store.dumps((full.matched_terms or []) + (full.watchlist_hits or [])),
                      full.tier, nummer))
    for (bid, zaak, areas) in conn.execute(
            "SELECT besluit_id, zaak_nummer, areas FROM nl_divisions").fetchall():
        row = conn.execute("SELECT areas FROM nl_zaken WHERE zaak_nummer=?", (zaak,)).fetchone()
        new = row[0] if row else "[]"
        changed_d += new != (areas or "[]")
        conn.execute("UPDATE nl_divisions SET areas=? WHERE besluit_id=?", (new, bid))
    conn.commit()
    log("nl-rollcalls: reclassified; {0} zaak/zaken and {1} vote(s) changed area".format(
        changed_z, changed_d))
    return changed_z, changed_d


def summary(conn, log=print):
    n = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
    ours = lambda t: sum(on_our_ground(json.loads(a or "[]"))  # noqa: E731
                         for (a,) in conn.execute("SELECT areas FROM {0}".format(t)))
    log("  store: {0} vote(s) ({1} roll call(s)), {2} on our ground, {3} awaiting positions; "
        "{4} zaak/zaken, {5} on our ground; {6} position(s); {7} member(s), {8} fractie(s)".format(
            n("SELECT COUNT(*) FROM nl_divisions"),
            n("SELECT COUNT(*) FROM nl_divisions WHERE stemmingssoort='Hoofdelijk'"),
            ours("nl_divisions"), n("SELECT COUNT(*) FROM nl_divisions WHERE positions_pending=1"),
            n("SELECT COUNT(*) FROM nl_zaken"), ours("nl_zaken"),
            n("SELECT COUNT(*) FROM nl_votes"), n("SELECT COUNT(*) FROM nl_members"),
            n("SELECT COUNT(*) FROM nl_fracties")))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--since", help="first voting day to read (YYYY-MM-DD); default: the window")
    ap.add_argument("--taxonomy", default=TAXONOMY,
                    help="Dutch taxonomy (default config/taxonomy-nl.yaml, once approved)")
    ap.add_argument("--no-members", action="store_true")
    ap.add_argument("--reclassify", action="store_true",
                    help="re-derive areas for stored zaken and votes, offline")
    ap.add_argument("--budget-seconds", type=float, default=BUDGET_S)
    ap.add_argument("--dry-run", action="store_true",
                    help="read one page of the window, store nothing")
    args = ap.parse_args(argv)
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"), throttle=1.0)
    today = datetime.date.today().isoformat()
    tax = load_taxonomy(args.taxonomy)
    if args.dry_run:
        start = args.since or (datetime.date.today()
                               - datetime.timedelta(days=WINDOW_DAYS)).isoformat()
        page = client.get_json(decisions_url(start), FEED, "dry", archive=False)
        votes = [d for d in (parse_decision(r) for r in page.get("value") or []) if d]
        print("nl-rollcalls: dry run from {0}: {1} vote(s) on the first page, {2} with "
              "positions".format(start, len(votes), sum(1 for d in votes if d["positions"])))
        return 0
    conn = db.init_db(db.connect(args.db))
    if args.reclassify:
        reclassify(conn, tax)
        summary(conn)
        conn.close()
        return 0
    budget = drain.Budget(args.budget_seconds)
    gaps = 0
    if not args.no_members:
        try:
            print("nl-rollcalls: {0} fractie(s), {1} sitting member(s)".format(
                pull_fracties(conn, client, today), pull_members(conn, client, today)))
        except (FetchError, ValueError) as exc:
            _gap(conn, today, "members: {0}".format(exc))
            conn.commit()
            print("  [gap] members: {0}".format(str(exc)[:80]))
            gaps += 1
    start = window_start(conn, today, args.since)
    n = pull_decisions(conn, client, today, start, tax, budget=budget)
    gaps += n["gaps"]
    print("nl-rollcalls: {read} vote(s) read from {start} ({pages} page(s)), {ours} on our "
          "ground, {pending} awaiting positions, {deleted} withdrawn, {gaps} gap(s)".format(
              start=start, **n))
    stale = check_pending(conn, today)
    gaps += stale
    summary(conn)
    conn.close()
    return 3 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
