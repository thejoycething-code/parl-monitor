"""The daily sweep's direct readers: what is NEW on our ground today (bills,
motions, questions, agenda points), read from sources that publish it the
same day cheaply and openly, into the daily job's THROWAWAY store
(src/country_day_sweep.py; tools/country_vote_briefs.py --daily).

The companion of src/vote_brief_sources.py, which reads the day's VOTES into
the same scratch store first. Each reader here is a thin layer over the
country's own collector (tools/<cc>_rollcalls.py, tools/<cc>_chamber.py,
src/agendas/<cc>.py): the collector's parsers, classifiers and storing
functions write only the items started in the window into the scratch
store, so the edition adapter (src/editions/<cc>.py) reads them exactly as it
reads the store and the sweep keys each item exactly as the weekly edition
does. Nothing here writes the store.

A reader is a class with:

  collect(conn, client, since, today, log) -> items stored. Bills, motions
      and questions started after `since`, through the cheapest query the
      source answers (a date filter, or the newest page of a list sorted
      newest first); never the whole-term lists the weekly reads.
  AGENDA      True when the country has a src/agendas module the sweep reads
              (agenda.collect over the next AGENDA_DAYS).
  ACTIVE_FROM ISO date before which the reader is skipped (Spain: the Cortes
              were dissolved on 6 October 2026; the XVI legislature sits from
              23 December).
  ONCE_A_DAY  True for a reader too heavy to repeat at both daily slots
              (France: an 8.4 MB zip); the sweep's ledger says when it last ran.
  ARCHIVE_ON_HIT  True when the reader fetches a large payload unarchived and
              archives it only on a day it yields an alert (France).
  extra_items(conn, since, until, wl) -> [item]   optional: items the
              country's edition does not carry but the sweep alerts (the
              Netherlands' new motions: its edition is votes, speeches and
              questions, NL3).

MEASURED COSTS (11 October 2026, from the laptop; a quiet weekend):

  nl  2 requests: new Moties, Amendementen and bills (Zaak, GestartOp in the
      window, 245 since 1 October in one page of 250, 88 KB); Kamervragen
      (nl_chamber.questions, one page). Agenda: 1 (Activiteit, 3 weeks).
  pl  3 requests: the term's processes sorted by number, newest 150 (24 KB
      for 30; every process started since June); interpellations and written
      questions, newest first (pl_chamber.questions, 1 page each, 35 KB).
      Agenda: 1 (proceedings). The Sejm API timed out on the laptop on 10
      October; the Mini reads it for the weekly.
  ch  2 requests: businesses submitted in the window, German and French
      (OData, 351 since 1 October, 152 KB for the German); no Italian pass
      (CH6 stays the weekly's). Agenda: 1-2 (Meeting, Session).
  br  1-2 requests: the Câmara's proposições (PL, PLP, PEC, PDL) presented in
      the window (100 a page: 13 in the week to 11 October, 61 in a sitting
      week); requests for information (br_chamber.questions, 1 page + 2 per
      request on our ground for its author, within a 60 s budget). Agenda:
      the Câmara's events + 1 pauta per deliberative event (at most 80) and
      the Senado's month.
  it  2 requests: Senate SPARQL, every bill reading presented in the window
      (both chambers; 15 since 1 October, 0.9 s) and their TESEO subjects.
      Agenda: 2 (the Camera's calendar).
  at  2 requests: the Parliament's item list (filter 101) for each chamber
      restricted by DATUM_VON to the window (204 rows for the Nationalrat's
      week, 0.9 s; the weekly's whole-period list is 17 MB and 55-65 s).
      Agenda: 1 + 1 per Tagesordnung (robots.txt checked).
  fr  1 request, once a day: the Assemblée's Agenda.json.zip (8.4 MB, 37 s
      on the laptop), the only same-day source of its ordre du jour. Bills
      and questions are NOT daily: Dossiers_Legislatifs.json.zip is 10.7 MB
      and the question dumps 55 MB, rebuilt nightly; the Saturday collection
      reads them. The zip is archived only on a day it yields an alert (the
      weekly archives it every Saturday, FR3).
  es  3 requests from 23 December 2026: the Congreso's open-data page and
      its two initiative files (0.4 and 0.7 MB). Agenda: 1 page.

ADDED ON BRANCH gaps-day-sweep (11 October 2026, measured from the laptop;
the whole daily run, votes and sweep, went from 55 s to about 2 minutes):

  fr  + the dossiers deposited in the window: the AN's own dossier list,
      newest deposit first, 50 a page (363 KB, 1 s; one page covers five
      or six days), classified on the short title; robots.txt asks 30 s
      between pages, so a busy window's second page waits. Once a day with
      the agenda. Written questions stay weekly: the Journal officiel
      publishes them on Tuesdays and the dumps are 49-55 MB.
  be  1-2 requests: the Chamber's recent-documents listing (the week's
      documents by dossier, 61 KB), French, then Dutch on a day with a new
      dossier (Crawl-delay 5 s). A dossier whose document 001 is dated in
      the window is new; its page (type, authors) is the weekly's.
  pt  1 request: the Assembleia's latest-initiatives page (four weeks deep,
      569 KB served gzipped, 1.3-2.7 s). Questions stay weekly (a 7.8 MB
      dump; the website pages them ten at a time behind postbacks).
  hr  1 request: the Sabor's "Novi akti" (acts received, not yet on an
      agenda, dated; 48 KB, 0.5 s), the sweep's own items (extra_items):
      the Croatian edition's new items are agenda appearances, which a
      throwaway store cannot tell. The agenda index is 1.3 MB and 30 s.
  sk  2 requests: the term's prints and interpellations (NR SR open data,
      637 and 425 KB, 1-5 s; no date filter, no compression).
  ar  1 request, once a day: the Diputados register (datos.hcdn.gob.ar,
      not www.hcdn.gob.ar, AR4) restricted to the window, no retry (the host
      rations requests). Agenda: the Senate's weeks (3 pages, 14 s).
  Latin America, read through the Latam alerts' path (LATAM below;
  src/country_day_sweep.latam_candidates):
  cl  1 request: the Senate's tramitación since the window (both chambers'
      new bills and the Senate's votes; 0.2-0.8 MB, 3-9 s) + the senators'
      list on a day with a Senate vote. Cámara votes stay weekly.
  pe  3 requests: the SPLEY list per chamber code with its presentation-date
      filter (under 20 KB, 3 s). Never the expediente endpoint (PE2).
  ec  2 requests: the periods and the plenary's vote list for the window
      (5 KB, 2-3 s), tallies only (EC_POSITIONS off). No bills (EC4).
  bo  1 request: the Diputados' bill posts modified in the window (4 KB);
      register re-stamps alert only when watched. Bills only (BO2).
  do  1-5 requests: the SIL's iniciativas, newest first, ten a page, until a
      page has nothing deposited in the window (0.7 s and 11 KB a page).
  pa  2 requests: segLegis's newest 20 items (93 KB, 5 s).
  hn  about 8 requests, 8 s on a quiet day: press releases, the four stages'
      newest files, the newest sessions (agendas of at most 4), La Gaceta.
  uy  once a day: a one-byte request for the pedidos file's Last-Modified,
      then the file itself only when it moved (1.09 MB, 17-34 s, no gzip;
      the only source of pedidos de informes, UY3).

NOT SWEPT: Mexico (its hosts refuse UK connections, the Mini's too; and the
Gaceta lists iniciativas only per period, no date filter); Colombia (no
cheap list carries a filing date; each bill's page is 750 KB, and CO3 rules
out its votes); El Salvador (a vote's subject comes only from the session
archive, filed days late and 40 s a sitting day); Hungary (not measured in
this pass).
"""

from __future__ import annotations

import datetime
import html
import json
import os
import re
import sys
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)


SWEEP = ("nl", "pl", "ch", "br", "it", "at", "fr", "es", "be", "pt", "hr", "sk", "ar",
         "cl", "pe", "ec", "bo", "do", "pa", "hn", "uy")
LATAM = ("cl", "pe", "ec", "bo", "do", "pa", "hn", "uy")   # the Latam alerts' path
AGENDA_DAYS = 14            # what the sweep reads ahead, as the edition shows
QUESTION_BUDGET_S = 60.0    # Brazil's per-request author lookups, at most


class Reader:
    AGENDA = True
    ACTIVE_FROM = None
    ONCE_A_DAY = False
    ARCHIVE_ON_HIT = False

    @staticmethod
    def collect(conn, client, since, today, log=print):
        return 0

    extra_items = None


def _throttle(client, host, seconds):
    """The collector's per-host throttle on the sweep's client, where it has one
    (a NoArchive wrapper passes the call through)."""
    setter = getattr(client, "set_host_throttle", None)
    if setter:
        setter(host, seconds)


class retries:
    """Cap the client's retries while a block runs: `with retries(client, 0):`.
    The daily sweep has the weekly as its backstop, so a host that refuses is
    a [gap] line for the day, not minutes of backoff (Argentina's register,
    refused, cost 282 s with the default retries on 11 October 2026)."""

    def __init__(self, client, most):
        self.client, self.most, self.old = getattr(client, "client", client), most, None

    def __enter__(self):
        self.old = getattr(self.client, "max_retries", None)
        if self.old is not None:
            self.client.max_retries = min(self.old, self.most)
        return self

    def __exit__(self, *exc):
        if self.old is not None:
            self.client.max_retries = self.old
        return False


def chamber_run(cc, conn, client, since, today, log=print, budget=QUESTION_BUDGET_S):
    """A src/chamber_store.Run over the scratch store, for a country's own
    question fetcher (tools/<cc>_chamber.py)."""
    from src import chamber_store as cs
    from src import drain
    return cs.Run(cc, conn, client, today, since, drain.Budget(budget),
                  cs.load_taxonomies(cc), log=log)


def run_questions(cc, module, conn, client, since, today, log=print):
    """The chamber collector's questions step over the scratch store; returns
    the questions stored on our ground. A gap there is logged, not raised:
    the rest of the country's sweep still counts."""
    run = chamber_run(cc, conn, client, since, today, log)
    module.questions(run)
    conn.commit()
    if run.gaps:
        log("  [gap] {0}: the questions step recorded {1} gap(s)".format(cc, run.gaps))
    return run.questions


# --- the Netherlands ----------------------------------------------------------------

NL_SOORTEN = ("Motie", "Amendement", "Wetgeving", "Initiatiefwetgeving")
NL_MAX_PAGES = 6
NL_KIND = {"Motie": "Motion", "Amendement": "Amendment", "Wetgeving": "Bill",
           "Initiatiefwetgeving": "Private member's bill"}


class NL(Reader):
    """New motions, amendments and bills (Zaak, by GestartOp) and Kamervragen.
    The Dutch edition carries votes, speeches and questions only (NL3), so
    the motions are the sweep's own items (extra_items); a motion is voted
    within a week or two and the vote brief takes it from there."""

    @staticmethod
    def zaken_url(since):
        import nl_chamber
        soorten = " or ".join("Soort eq '{0}'".format(s) for s in NL_SOORTEN)
        return nl_chamber.BASE + "Zaak?" + urllib.parse.urlencode({
            "$filter": "Verwijderd eq false and ({0}) and GestartOp ge {1}T00:00:00Z".format(
                soorten, since),
            "$select": "Id,Nummer,Soort,Onderwerp,Titel,GestartOp,Kabinetsappreciatie,Afgedaan",
            "$expand": "Kamerstukdossier($select=Nummer,Toevoeging,Titel)",
            "$orderby": "GestartOp desc", "$top": 250})

    @staticmethod
    def collect(conn, client, since, today, log=print):
        import nl_chamber
        import nl_rollcalls as nlr
        tax = nlr.load_taxonomy(log=lambda *_a: None)
        url, page, zaken = NL.zaken_url(since), 0, []
        while url and page < NL_MAX_PAGES:     # a budget debate tables hundreds of motions
            got = client.get_json(url, "nl-sweep", "zaken-since-{0}-p{1}".format(since, page))
            zaken += (got or {}).get("value") or []
            url, page = (got or {}).get("@odata.nextLink"), page + 1
        n = ours = 0
        for raw in zaken:
            z = nlr.parse_zaak(raw)
            if not z["nummer"] or (z["gestart"] or "") <= since:
                continue
            n += 1
            ours += nlr.on_our_ground(nlr.store_zaak(conn, z, tax, today))
        conn.commit()
        log("nl: {0} motion(s), amendment(s) and bill(s) started since {1}, {2} on our "
            "ground".format(n, since, ours))
        return ours + run_questions("nl", nl_chamber, conn, client, since, today, log)

    @staticmethod
    def extra_items(conn, since, until, wl):
        from src import country_edition as ce
        from src.editions import nl as nl_edition
        out = []
        marks = ",".join("?" * len(NL_SOORTEN))
        for r in ce.rows(conn, "SELECT * FROM nl_zaken WHERE soort IN ({0}) AND {1}".format(
                marks, ce.window_sql("gestart")), NL_SOORTEN + (since, until)):
            dossiers = json.loads(r["dossiers"] or "[]")
            titles = json.loads(r["dossier_titels"] or "[]")
            hit = next((k for k in [r["zaak_nummer"]] + dossiers if k in wl), None)
            if not ce.on_ground(r["areas"], hit is not None):
                continue
            take = "{0} {1}".format(NL_KIND.get(r["soort"], r["soort"]), r["zaak_nummer"])
            if dossiers:
                take += ", in dossier {0}{1}".format(dossiers[0], ": " + titles[0] if titles else "")
            if r["kabinetsappreciatie"]:
                take += "; the government's advice: {0}".format(r["kabinetsappreciatie"])
            out.append(ce.item("nl", "new", r["zaak_nummer"], r["gestart"], r["onderwerp"],
                               ce.areas_of(r["areas"]), r["tier"], hit is not None,
                               url=nl_edition.zaak_url(r["zaak_nummer"]),
                               terms=r["matched_terms"], takeaway=ce.clip(take, 260),
                               own=bool(ce.areas_of(r["own_areas"])), watch_key=hit))
        return out


# --- Poland -------------------------------------------------------------------------

PL_NEWEST = 150


class PL(Reader):
    """The newest processes of the term (the API's list sorted by number,
    newest first: every process started since June in one page) and the
    interpellations and written questions received in the window."""

    @staticmethod
    def collect(conn, client, since, today, log=print):
        import pl_chamber
        import pl_rollcalls as plr
        term = pl_chamber.TERM
        got = client.get_json("{0}/term{1}/processes?limit={2}&sort_by=-number".format(
            plr.API, term, PL_NEWEST), plr.FEED, "sweep-processes-{0}".format(today), timeout=60)
        tax = plr.load_taxonomy()
        n = 0
        for p in got or []:
            start = (p.get("processStartDate") or "")[:10]
            if not start or start <= since:
                continue
            plr.store_process(conn, p, term, tax, today)
            n += 1
        conn.commit()
        log("pl: {0} process(es) started since {1}".format(n, since))
        return n + run_questions("pl", pl_chamber, conn, client, since, today, log)


# --- Switzerland ---------------------------------------------------------------------

class CH(Reader):
    """Businesses submitted in the window (Curia Vista through OData), German
    and French, classified as the weekly does; interpellations, questions and
    the Fragestunde are the edition's questions, motions and postulates its
    new items."""

    @staticmethod
    def collect(conn, client, since, today, log=print):
        import ch_rollcalls as chr_
        tax = chr_.Taxonomies()
        cond = "SubmissionDate gt datetime'{0}T23:59:59'".format(since)
        slug = "sweep-business-{0}".format(since)
        pairs = chr_._pair(
            chr_.fetch_all(client, chr_.odata_url("Business", "Language eq 'DE' and " + cond,
                                                  chr_.BUSINESS_FIELDS), slug + "-de"),
            chr_.fetch_all(client, chr_.odata_url("Business", "Language eq 'FR' and " + cond,
                                                  chr_.BUSINESS_FIELDS), slug + "-fr"))
        ours = 0
        for de, fr in pairs:
            ours += chr_.on_our_ground(chr_.store_business(conn, tax, de, fr, today))
        conn.commit()
        log("ch: {0} business(es) submitted since {1}, {2} on our ground".format(
            len(pairs), since, ours))
        return len(pairs)


# --- Brazil --------------------------------------------------------------------------

BR_TYPES = "PL,PLP,PEC,PDL"
BR_PROPOSICOES = ("{0}/proposicoes?siglaTipo={1}&dataApresentacaoInicio={2}"
                  "&dataApresentacaoFim={3}&itens=100&ordem=DESC&ordenarPor=id")


class BR(Reader):
    """The Câmara's bills, constitutional amendments and legislative decrees
    presented in the window (API v2, classified on their ementa, as the
    weekly classifies a bill before its record is read) and its requests for
    information (tools/br_chamber.py)."""

    @staticmethod
    def collect(conn, client, since, today, log=print):
        import br_chamber
        import br_rollcalls as brr
        start = (datetime.date.fromisoformat(since) + datetime.timedelta(days=1)).isoformat()
        url, page, n = BR_PROPOSICOES.format(brr.CAMARA_API, BR_TYPES, start, today), 0, 0
        while url and page < 10:
            got = client.get_json(url, brr.FEED, "sweep-proposicoes-{0}-p{1}".format(start, page))
            for p in got.get("dados") or []:
                b = {"camara_id": brr._int(p.get("id")), "sigla": brr._clean(p.get("siglaTipo")),
                     "numero": brr._int(p.get("numero")), "ano": brr._int(p.get("ano")),
                     "ementa": brr._clean(p.get("ementa")),
                     "presented": (p.get("dataApresentacao") or "")[:10] or None}
                b["bill_key"] = brr.bill_key(b["sigla"], b["numero"], b["ano"], b["camara_id"])
                if brr.store_bill(conn, b, today, log=log):
                    n += 1
            url = next((l.get("href") for l in got.get("links") or [] if l.get("rel") == "next"),
                       None)
            page += 1
        conn.commit()
        brr.reclassify(conn, tax=brr.load_taxonomy(), log=lambda *_a: None)
        log("br: {0} Câmara proposição(ões) presented since {1}".format(n, since))
        return n + run_questions("br", br_chamber, conn, client, since, today, log)


# --- Italy ---------------------------------------------------------------------------

def q_bills_presented(leg, since):
    import it_rollcalls as itr
    return itr.PREFIXES + """SELECT ?d ?fase ?iddl ?titolo ?breve ?natura ?iniz ?pres ?stato ?statodata WHERE {{
 ?d a osr:Ddl ; osr:legislatura {0} ; osr:fase ?fase ; osr:titolo ?titolo ; osr:dataPresentazione ?pres .
 OPTIONAL {{ ?d osr:idDdl ?iddl }} OPTIONAL {{ ?d osr:titoloBreve ?breve }}
 OPTIONAL {{ ?d osr:natura ?natura }} OPTIONAL {{ ?d osr:descrIniziativa ?iniz }}
 OPTIONAL {{ ?d osr:statoDdl ?stato }} OPTIONAL {{ ?d osr:dataStatoDdl ?statodata }}
 FILTER(STR(?pres) > "{1}") }} LIMIT {2}""".format(int(leg), since.replace('"', ""),
                                                  itr.SPARQL_CAP)


def q_teseo_presented(leg, since):
    import it_rollcalls as itr
    return itr.PREFIXES + """SELECT DISTINCT ?d ?label WHERE {{
 ?d a osr:Ddl ; osr:legislatura {0} ; osr:dataPresentazione ?pres ; osr:classificazione ?c .
 ?c osr:livello ?liv ; dc:subject ?t . ?t skos:prefLabel ?label
 FILTER(STR(?pres) > "{1}" && STR(?liv) = "Generale") }} LIMIT {2}""".format(
        int(leg), since.replace('"', ""), itr.SPARQL_CAP)


class IT(Reader):
    """Every bill reading presented in the window, both chambers, from the
    Senate's SPARQL endpoint (which carries the Camera's readings too), with
    its TESEO subjects, classified as the weekly does."""

    @staticmethod
    def collect(conn, client, since, today, log=print):
        import it_rollcalls as itr
        leg = itr.LEGISLATURE
        tax = itr.filt.load_taxonomy(itr.taxonomy_path(), country=itr.TAXONOMY_COUNTRY)
        wl = itr.empty_watchlist()
        rows = itr.sparql(client, q_bills_presented(leg, since), "sweep-bills-{0}".format(since))
        subj = itr.sparql(client, q_teseo_presented(leg, since), "sweep-teseo-{0}".format(since))
        bills = itr.attach_subjects(itr.parse_bills(rows, leg), subj)
        for b in bills.values():
            itr.store_bill(conn, b, itr.classify_bill(tax, wl, b), today)
        conn.commit()
        log("it: {0} bill reading(s) presented since {1}".format(len(bills), since))
        return len(bills)


# --- Austria -------------------------------------------------------------------------

class AT(Reader):
    """The Parliament's item list (filter 101) for each chamber, restricted
    to items received in the window (the DATUM_VON range, found 11 October
    2026: one small reply instead of the weekly's 17 MB period list)."""

    @staticmethod
    def collect(conn, client, since, today, log=print):
        import at_rollcalls as atr
        tax = atr.filt.load_taxonomy(atr.TAXONOMY, country=atr.TAXONOMY_COUNTRY)
        wl = atr.empty_watchlist()
        start = (datetime.date.fromisoformat(since) + datetime.timedelta(days=1)).isoformat()
        n = ours = 0
        for chamber in atr.CHAMBERS:
            body = json.dumps({"NRBR": [chamber], "GP_CODE": [atr.CURRENT_GP],
                               "DATUM_VON": [start, today]})
            reply = client.post_json(atr.ITEMS, body, atr.FEED,
                                     "sweep-items-{0}-{1}".format(chamber, start), timeout=120)
            items, missing = atr.parse_items(reply)
            if missing:
                raise ValueError("the item list header lacks {0}".format(missing))
            items = [it for it in items if (it["introduced"] or "") > since]
            ours += atr.store_items(conn, items, tax, wl, today)
            n += len(items)
        conn.commit()
        log("at: {0} item(s) received since {1}, {2} on our ground".format(n, since, ours))
        return n


# --- France --------------------------------------------------------------------------

FR_LIST = "https://www.assemblee-nationale.fr/dyn/{0}/dossiers?page={1}&limit={2}"
FR_CRAWL_DELAY_S = 30.0        # www.assemblee-nationale.fr robots.txt, 11 October 2026
FR_PAGE = 50
FR_MAX_PAGES = 3
FR_MONTHS = {"janvier": 1, "février": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
             "juillet": 7, "août": 8, "septembre": 9, "octobre": 10, "novembre": 11,
             "décembre": 12}
FR_DEPOT = re.compile(r"Dépôt [^<]{0,60}? le \w+ (\d{1,2})(?:er)? (\w+) (\d{4})")
# The reading the list prints -> the act-code prefix the edition reads as new.
FR_READING = (("Lecture unique", "ANLUNI"), ("1ère lecture", "AN1"))


def fr_dossiers(markup, legislature):
    """[dossier as fr_rollcalls.parse_dossier shapes it] from one page of the
    AN's dossier list. The list gives the deposit date, not the latest act:
    the deposit is stored as the act (the edition's "new"), the stage in the
    AN's own words as its label."""
    out = []
    for block in markup.split("_style-dossier-legislatif")[1:]:
        uid = re.search(r"data-id=\"(DLR\w+)", block)
        link = re.search(r"(?s)<a class=\"link _big\" href=\"/dyn/\d+/dossiers/([^\"]+)\">(.*?)</a>",
                         block)
        proc = re.search(r"(?s)<span class=\"_bold\">(.*?)</span>", block)
        depot = FR_DEPOT.search(html.unescape(block))
        stage = re.search(r"(?s)_colored-primary _bold\">(.*?)</span>", block)
        if not (uid and link and depot and depot.group(2).lower() in FR_MONTHS):
            continue
        stage = _squash(stage.group(1)) if stage else ""
        stage = stage.split(":", 1)[-1].strip()
        prefix = next((p for word, p in FR_READING if stage.startswith(word)), None)
        out.append({"uid": uid.group(1), "legislature": legislature, "title": _squash(link.group(2)),
                    "an_path": link.group(1), "senat_url": None,
                    "procedure": _squash(proc.group(1)) if proc else None, "initiator": None,
                    "last_act": prefix + "-DEPOT" if prefix else None,
                    "last_act_label": stage.split(",", 1)[-1].strip() or None,
                    "last_act_at": datetime.date(int(depot.group(3)),
                                                 FR_MONTHS[depot.group(2).lower()],
                                                 int(depot.group(1))).isoformat(),
                    "promulgated_at": None, "doc_titles": []})
    return out


class FR(Reader):
    """The Assemblée's ordre du jour (src/agendas/fr.py), once a day, and the
    dossiers deposited in the window: the AN's own dossier list, newest
    deposit first, 50 a page (one page covers about ten days), classified and
    stored as the weekly does (fr_rollcalls.classify_dossier, store_dossier),
    on the dossier's short title only (the list carries no document titles).
    Written questions stay with the Saturday collection: the Journal officiel
    publishes them once a week. The agenda zip is fetched unarchived and
    archived on a day it yields an alert (archive_hit)."""

    ONCE_A_DAY = True
    ARCHIVE_ON_HIT = True

    @staticmethod
    def collect(conn, client, since, today, log=print):
        import fr_rollcalls as frr
        from src import filter as filt
        _throttle(client, "www.assemblee-nationale.fr", FR_CRAWL_DELAY_S)
        lists = getattr(client, "client", client)     # archived as usual: only the zip waits

        leg = frr.LEGISLATURE
        tax = filt.load_taxonomy(frr.taxonomy_path(), country=frr.TAXONOMY_COUNTRY)
        wl = frr.empty_watchlist()
        n = ours = 0
        for page in range(1, FR_MAX_PAGES + 1):
            got = fr_dossiers(lists.get_text(FR_LIST.format(leg, page, FR_PAGE), frr.FEED,
                                              "sweep-dossiers-{0}-p{1}".format(today, page)), leg)
            if not got:
                if page == 1:
                    raise ValueError("the AN's dossier list carries no dossier")
                break
            for d in got:
                if d["last_act_at"] <= since or not d["last_act"]:
                    continue
                res = frr.classify_dossier(tax, wl, d)
                frr.store_dossier(conn, d, res, today)
                n += 1
                ours += frr.on_our_ground(res.issue_areas)
            if min(d["last_act_at"] for d in got) <= since:
                break
        conn.commit()
        log("fr: {0} dossier(s) deposited since {1}, {2} on our ground".format(n, since, ours))
        return n


# --- Spain ---------------------------------------------------------------------------

class ES(Reader):
    """Proyectos and proposiciones de ley from the Congreso's open data (the
    weekly's own files, two requests), from the XVI legislature's first
    sitting on 23 December 2026; until then nothing new can be tabled."""

    ACTIVE_FROM = "2026-12-23"

    @staticmethod
    def collect(conn, client, since, today, log=print):
        import es_rollcalls as esr
        tax = esr.load_taxonomy()
        read, ours, gaps = esr.pull_initiatives(conn, client, today, tax=tax, log=log)
        if gaps and not read:
            raise ValueError("the Congreso's initiative files were not read")
        log("es: {0} initiative(s) read, {1} on our ground".format(read, ours))
        return read



# === Added on branch gaps-day-sweep (11 October 2026) ===================

# --- Argentina -----------------------------------------------------------------------

class AR(Reader):
    """The Diputados register of expedientes (datos.hcdn.gob.ar, "Proyectos
    Parlamentarios", updated daily from the Trámite Parlamentario) restricted
    to the expedientes published in the window: ONE request, the weekly's own
    query (ar_rollcalls.proyectos_sql) with the window's dates in place of a
    calendar month, stored through ar_rollcalls.store_bill as the weekly does
    (ar_bills, `published`, which the edition windows on). Senate expedientes
    reach the store only through the actas that name them, so the Senate's
    new business is its agenda (src/agendas/ar.py, www.senado.gob.ar).

    ONCE A DAY: datos.hcdn.gob.ar turns a client away after a few dozen
    requests on a bad day (ar_rollcalls docstring), and the weekly needs up
    to eight of its own; one request a day keeps the sweep well clear of it.
    A refusal is a [gap] line for the day, nothing more. www.hcdn.gob.ar is
    never read here (AR4).

    MEASURED 11 October 2026 from the laptop (London), since 4 October: one
    register request, 26 expedientes (all dated 5 and 6 October; none yet
    for 7 to 9 October), 12 KB, 1.6 s; 3 on our ground. A month's query a
    minute later timed out twice, so this stays at one request a day. The
    Senate agenda's three week pages: 46 KB, 14 s."""

    ONCE_A_DAY = True

    @staticmethod
    def collect(conn, client, since, today, log=print):
        import ar_rollcalls as arr
        from src.http import FetchError
        start = (datetime.date.fromisoformat(since) + datetime.timedelta(days=1)).isoformat()
        end = (datetime.date.fromisoformat(today) + datetime.timedelta(days=1)).isoformat()
        _throttle(client, "datos.hcdn.gob.ar", arr.DATOS_THROTTLE_S)
        try:
            with retries(client, 0):     # one try: a refusal is the day's [gap], nothing more
                payload = client.get_json(arr._sql_url(arr.proyectos_sql(start, end)), arr.FEED,
                                          "sweep-proyectos-{0}".format(start), timeout=30)
            recs = payload["result"]["records"]
        except (FetchError, KeyError, TypeError) as exc:
            raise ValueError("the Diputados register was not read: {0}".format(
                str(exc)[:120]))
        if len(recs) >= arr.DATOS_WINDOW_CAP:
            log("  [gap] ar: the register hit its cap of {0} rows; some may be missing".format(
                arr.DATOS_WINDOW_CAP))
        tax, wl = arr.load_terms(), arr.empty_watchlist()
        n = ours = 0
        for r in recs:
            rec = arr.proyecto_record(r)
            if not rec or (rec["published"] or "") <= since:
                continue
            ours += arr.on_our_ground(arr.store_bill(conn, tax, wl, rec, today).issue_areas)
            n += 1
        conn.commit()
        log("ar: {0} Diputados expediente(s) published since {1}, {2} on our ground".format(
            n, since, ours))
        return n


def _squash(text):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text or ""))).strip()


# --- Belgium -------------------------------------------------------------------------

BE_ROW = re.compile(r"(?is)flwbn\.cfm\?lang=\w&legislat=(\d+)&dossierID=(\d+)\">\s*\d+\s*</A>"
                    r"\s*</div>\s*</td>\s*<td>\s*<div class=\"linklist_1\">(.*?)</div>")
BE_DOC = re.compile(r"(?is)docn=\d+K\d{4}(\d{3})&[^>]*>\s*\d{3}\s*</A>\s*Dat\w*\s*:\s*"
                    r"(\d{2})/(\d{2})/(\d{4})\s*([^<]*)")


def be_recent(markup):
    """{(legislature, number): (title, deposited or None)} from the recent-
    documents listing: deposited is the date of the dossier's document 001
    when the listing carries it (the dossier was opened that week)."""
    out = {}
    for leg, num, cell in BE_ROW.findall(markup):
        title = _squash(re.split(r"(?i)<br\s*/?>", cell, maxsplit=1)[0]) or None
        first = None
        for docnum, d, m, y, _label in BE_DOC.findall(cell):
            if docnum == "001":
                first = "{0}-{1}-{2}".format(y, m, d)
        out[(int(leg), int(num))] = (title, first)
    return out


class BE(Reader):
    """Dossiers opened in the window: the Chamber's recent-documents listing
    (the week's documents by dossier), in French and in Dutch; a dossier
    whose document 001 is dated in the window is new, stored with both
    titles and that date as its deposit, and classified as the weekly does
    (be_rollcalls._upsert_dossier). No dossier page is read, so doc_type,
    status and authors stay empty until the weekly reads the page; the
    edition then says "Dossier 56/1800". The date is document 001's, which
    can follow the Chamber's own deposit date by a day or two."""

    AGENDA = False

    @staticmethod
    def collect(conn, client, since, today, log=print):
        import be_rollcalls as be
        _throttle(client, "www.lachambre.be", be.CRAWL_DELAY_S)
        fr = be_recent(be.decode(client.get_bytes(be.RECENT, be.FEED, "sweep-recent-fr")))
        if not fr:
            raise ValueError("the recent-documents listing carries no dossier")
        new = {k: v for k, v in fr.items() if v[1] and v[1] > since}
        nl = {}
        if new:
            nl = be_recent(be.decode(client.get_bytes(be.RECENT.replace("language=fr", "language=nl"),
                                                      be.FEED, "sweep-recent-nl")))
        ours = 0
        for (leg, num), (title_fr, deposited) in sorted(new.items()):
            key = be._upsert_dossier(conn, leg, num, today, title_fr=title_fr,
                                     title_nl=(nl.get((leg, num)) or (None, None))[0],
                                     deposited=deposited)
            row = conn.execute("SELECT areas FROM be_dossiers WHERE dossier_key=?", (key,)).fetchone()
            ours += bool(row and row[0] not in (None, "[]"))
        conn.commit()
        log("be: {0} dossier(s) opened since {1}, {2} on our ground".format(len(new), since, ours))
        return len(new)


# --- Portugal ------------------------------------------------------------------------

PT_LATEST = "/Paginas/UltimasIniciativasEntradas.aspx"
PT_ROW = re.compile(r"(?s)<p class=\"date\">\s*(\d\d)\.(\d\d)\s*</p>\s*<p class=\"time\">\s*(\d{4})"
                    r"\s*</p>.*?DetalheIniciativa\.aspx\?BID=(\d+)[^>]*>\s*<p class=\"title\">"
                    r"\s*(.*?)\s*</p>.*?<p class=\"desc\">\s*(.*?)\s*</p>")
PT_NAME = re.compile(r"^(.+?)\s+(\d+)/([IVXL]+)/\d+\s*(?:\[(.*)\])?$")
# The Assembleia's IniTipo letters, as its dumps print them beside IniDescTipo.
PT_TYPES = {"Projeto de Lei": "J", "Proposta de Lei": "P", "Projeto de Resolução": "R",
            "Proposta de Resolução": "S", "Projeto de Deliberação": "D",
            "Apreciação Parlamentar": "A", "Inquérito Parlamentar": "I",
            "Projeto de Revisão Constitucional": "C"}
PT_GROUP = re.compile(r"^[A-Z][A-Z\-]*$")
PT_NOT_GROUPS = ("PAR",)       # the President of the Assembleia, not a group


def pt_latest(markup):
    """Initiatives from the latest-entries page, as pt_rollcalls.parse_initiative
    shapes them (no events, no votes: the page has neither)."""
    out = []
    for d, m, y, bid, name, desc in PT_ROW.findall(markup):
        got = PT_NAME.match(_squash(name))
        if not got:
            continue
        type_desc, number, leg, by = got.groups()
        itype = PT_TYPES.get(type_desc)
        if not itype:
            continue
        who = [w.strip() for w in re.split(r"[,/]", by or "") if w.strip()]
        groups = who and all(PT_GROUP.match(w) and w not in PT_NOT_GROUPS for w in who)
        out.append({"key": "{0}/{1}/{2}".format(leg, itype, int(number)), "ini_id": int(bid),
                    "legislature": leg, "type": itype, "type_desc": type_desc,
                    "number": int(number), "title": _squash(desc) or None, "epigraph": None,
                    "authors_gp": sorted(who) if groups else [],
                    "author_other": None if groups else (by or None), "authors": [],
                    "entered": "{0}-{1}-{2}".format(y, m, d), "latest_phase": None,
                    "latest_phase_at": None, "law_published": None, "vetoes": 0,
                    "text_url": None, "divisions": []})
    return out


class PT(Reader):
    """Initiatives entered in the window, from the Assembleia's latest-entries
    page (the website's own list, four weeks deep), classified and stored as
    the weekly does (pt_rollcalls.classify_initiative, store_initiative). The
    page gives each one's number, type, author and title; its phases and
    votes are the weekly's (the 97 MB Iniciativas dump)."""

    AGENDA = False

    @staticmethod
    def collect(conn, client, since, today, log=print):
        import pt_rollcalls as pt
        from src import filter as filt
        if hasattr(client, "enable_gzip"):
            client.enable_gzip("www.parlamento.pt")
        page = client.get_text(pt.SITE + PT_LATEST, pt.FEED, "sweep-latest-{0}".format(today))
        listed = pt_latest(page)
        if not listed:
            raise ValueError("the latest-initiatives page lists nothing")
        tax = filt.load_taxonomy(pt.taxonomy_path(), country=pt.TAXONOMY_COUNTRY)
        wl = pt.empty_watchlist()
        n = ours = 0
        for ini in listed:
            if ini["legislature"] != pt.CURRENT_LEGISLATURE or ini["entered"] <= since:
                continue
            res = pt.classify_initiative(tax, wl, ini)
            pt.store_initiative(conn, ini, res, today)
            n += 1
            ours += pt.on_our_ground(res.issue_areas)
        conn.commit()
        log("pt: {0} initiative(s) entered since {1}, {2} on our ground".format(n, since, ours))
        return n


# --- Croatia -------------------------------------------------------------------------

HR_NEW_ACTS = "/hr/sjednice/novi-akti"
HR_ROW = re.compile(r"(?s)<div class=\"date export-row-data\">\s*(\d\d)\.(\d\d)\.(\d{4})\.\s*</div>"
                    r"\s*<div class=\"title export-row-data\">(.*?)</div>.*?<a href=\"([^\"]+)\">")
HR_TABLE = """CREATE TABLE IF NOT EXISTS hr_sweep_acts (
    act_key       TEXT PRIMARY KEY,   -- the bill '11/352', or 'act:<page slug>'
    received      TEXT,               -- the date the list prints
    title         TEXT,
    url           TEXT,
    bill_key      TEXT,
    areas         TEXT,
    matched_terms TEXT,
    tier          INTEGER,
    first_seen    TEXT
)"""


def hr_new_acts(markup):
    out = []
    for d, m, y, title, href in HR_ROW.findall(markup):
        href = html.unescape(href).replace("/index.php/", "/", 1)
        out.append({"received": "{0}-{1}-{2}".format(y, m, d), "title": _squash(title),
                    "url": ("https://www.sabor.hr" + href) if href.startswith("/") else href,
                    "slug": href.rstrip("/").rsplit("/", 1)[-1]})
    return out


class HR(Reader):
    """Acts received by the Sabor and not yet on a plenary agenda (its "Novi
    akti" list, dated). The Croatian edition's new items are agenda
    appearances (hr_items, keyed on the agenda's tid and new against the
    store's history), which a throwaway store cannot tell; so these are the
    sweep's own items (extra_items), classified with the collector's own
    hr_rollcalls.classify and keyed on the bill ('11/352') as the edition
    keys it, so the week's edition and the sweep never alert one bill twice.
    An act put on an agenda the day it arrives leaves the list unseen; the
    weekly carries it."""

    AGENDA = False

    @staticmethod
    def collect(conn, client, since, today, log=print):
        import hr_rollcalls as hr
        _throttle(client, "www.sabor.hr", hr.THROTTLE_S)
        page = client.get_text(hr.SITE + HR_NEW_ACTS, hr.FEED, "sweep-novi-akti-{0}".format(today))
        acts = hr_new_acts(page)
        if not acts and "export-row-data" not in page:
            raise ValueError("the new-acts page has changed: no rows found")
        conn.execute(HR_TABLE)
        tax = hr.load_taxonomy()
        n = ours = 0
        for a in acts:
            if a["received"] <= since:
                continue
            bill_key, _marker = hr.parse_bill(a["title"])
            areas, matched, tier = hr.classify(tax, a["title"], None, bill_key)
            conn.execute(
                "INSERT OR REPLACE INTO hr_sweep_acts (act_key, received, title, url, bill_key, "
                "areas, matched_terms, tier, first_seen) VALUES (?,?,?,?,?,?,?,?,?)",
                (bill_key or "act:" + a["slug"], a["received"], a["title"], a["url"], bill_key,
                 areas, matched, tier, today))
            n += 1
            ours += hr.on_our_ground(areas)
        conn.commit()
        log("hr: {0} act(s) received since {1}, {2} on our ground".format(n, since, ours))
        return n

    @staticmethod
    def extra_items(conn, since, until, wl):
        from src import country_edition as ce
        out = []
        for r in ce.rows(conn, "SELECT * FROM hr_sweep_acts WHERE " + ce.window_sql("received"),
                         (since, until)):
            watched = bool(r["bill_key"]) and r["bill_key"] in wl
            if not ce.on_ground(r["areas"], watched):
                continue
            out.append(ce.item("hr", "new", r["act_key"], r["received"], r["title"],
                               ce.areas_of(r["areas"]), r["tier"], watched, url=r["url"],
                               terms=r["matched_terms"],
                               takeaway="Received by the Sabor; not yet on a plenary agenda",
                               watch_key=r["bill_key"] if watched else None))
        return out


# --- Slovakia ------------------------------------------------------------------------

class SK(Reader):
    """Prints (tlače) delivered and interpellations submitted in the window:
    the term's two open-data lists (one call each; the API takes no date
    filter), parsed, classified and stored as the weekly does, only the
    window's rows kept. A print's documents (SK6) and its votes' positions
    stay the weekly's."""

    AGENDA = False

    @staticmethod
    def collect(conn, client, since, today, log=print):
        import sk_rollcalls as skr
        from src import filter as filt
        term = skr.CURRENT_TERM
        tax, wl = skr.load_taxonomy(), skr.empty_watchlist()
        bills = skr.parse_bills(skr._od(client, "Bill/Bills?termNr={0}".format(term),
                                        "sweep-bills-{0}-{1}".format(term, today)))
        n = ours = 0
        for b in bills:
            if (b["delivered"] or "")[:10] <= since:
                continue
            res = skr.classify_bill(tax, wl, b)
            skr.store_bill(conn, b, res, today)
            n += 1
            ours += skr.on_our_ground(res.issue_areas)
        asked = skr.parse_interpellations(skr._od(
            client, "Interpellation/Interpellations?termNr={0}".format(term),
            "sweep-interpellations-{0}-{1}".format(term, today)))
        q = 0
        for i in asked:
            if (i["submitted"] or "")[:10] <= since:
                continue
            res = filt.filter_item(tax, wl, i["subject"])
            skr.store_interpellation(conn, i, res, today)
            q += 1
            ours += skr.on_our_ground(res.issue_areas)
        conn.commit()
        log("sk: {0} print(s) delivered and {1} interpellation(s) submitted since {2}, {3} on "
            "our ground".format(n, q, since, ours))
        return n + q


# --- Latin America (read through the Latam alerts' path, src/country_day_sweep.py) --

def _day_after(since):
    return (datetime.date.fromisoformat(since) + datetime.timedelta(days=1)).isoformat()


# --- Chile ---------------------------------------------------------------------------

class CL(Reader):
    """Bills introduced in the window (both chambers) and the Senate's votes
    in it, from one Senate tramitación request (the weekly's own service and
    parser), classified on title and materias as the weekly does. A vote's
    bill is stored with it, so the vote inherits the bill's areas."""

    AGENDA = False

    @staticmethod
    def collect(conn, client, since, today, log=print):
        import cl_rollcalls as clr
        tax = clr.filt.load_taxonomy(clr.taxonomy_path(), country=clr.TAXONOMY_COUNTRY)
        fecha = urllib.parse.quote(datetime.date.fromisoformat(since).strftime("%d/%m/%Y"), safe="")
        projects = clr.parse_senate_projects(client.get_bytes(
            clr.SEN_SINCE.format(fecha), clr.FEED, "sweep-tramitacion-since-{0}".format(since),
            timeout=180))
        if projects is None:
            raise ValueError("the Senate's tramitación service sent no project list")
        new = ours = 0
        voted = []
        for p in projects:
            fresh = (p["introduced"] or "") > since
            votes = [v for v in p["votes"] if (v["date"] or "") > since]
            if not (fresh or votes):
                continue
            areas = clr.store_bill(conn, tax, p, today)
            if fresh:
                new += 1
                ours += clr.on_our_ground(areas)
            if votes:
                voted.append((p["boletin"], votes))
        nvotes = vours = 0
        if voted:
            senators, _gaps = clr.fetch_senators(conn, client, today, log)
            for s in senators:
                clr.store_member(conn, s, "senado", today)
            index, unresolved = clr.SenatorIndex(senators), set()
            for boletin, votes in voted:
                s, o = clr.store_senate_votes(conn, tax, boletin, votes, index, today, unresolved)
                nvotes += s
                vours += o
            if unresolved:
                log("  cl: {0} senator name(s) not resolved".format(len(unresolved)))
        conn.commit()
        log("cl: {0} bill(s) introduced since {1}, {2} on our ground; {3} Senate vote(s), "
            "{4} on our ground".format(new, since, ours, nvotes, vours))
        return new + nvotes


# --- Peru ----------------------------------------------------------------------------

PE_CODES = ("S", "D", "C")


class PE(Reader):
    """Proyectos de ley presented in the window, per chamber code, from the
    SPLEY list with its presentation-date filter (the weekly's own API and
    parser; never the expediente endpoint, PE2). Votes stay with the weekly
    (PDF records of up to 2.2 MB)."""

    AGENDA = False

    @staticmethod
    def collect(conn, client, since, today, log=print):
        import pe_rollcalls as per
        tax, wl = per.load_taxonomy(), per.empty_watchlist()
        watch = per.pe_store.watchlist()
        n = ours = 0
        for code in PE_CODES:
            body = json.loads(per.bill_request(per.CURRENT_PERIOD, code, 0))
            body["fecPresentacionDesde"] = _day_after(since)
            reply = client.post_json(per.SPLEY, json.dumps(body), per.FEED,
                                     "sweep-spley-{0}-{1}".format(code, since))
            rows = ((reply or {}).get("data") or {}).get("proyectos") or []
            if len(rows) >= per.PAGE_SIZE:
                log("  [gap] pe: {0} filled a whole page; the rest waits for the "
                    "weekly".format(code))
            for rec in rows:
                b = per.parse_bill(rec)
                if (b["presented"] or "") <= since:
                    continue
                res = per.classify_bill(tax, wl, b, watch)
                per.store_bill(conn, b, res, today)
                n += 1
                ours += per.on_our_ground(res.issue_areas)
        conn.commit()
        log("pe: {0} proyecto(s) presented since {1}, {2} on our ground".format(n, since, ours))
        return n


# --- Ecuador -------------------------------------------------------------------------

EC_POSITIONS = False     # True: positions and the roster's party split for a hit


class EC(Reader):
    """The plenary's votes in the window (votingList, the weekly's own
    service and parser), classified on their theme and proposal, with their
    totals. With EC_POSITIONS, a vote on our ground also gets every member's
    position and, once, the sitting roster for the party split (without the
    roster the split would read 'unknown', so the two go together). No bills
    (EC4)."""

    AGENDA = False

    @staticmethod
    def collect(conn, client, since, today, log=print):
        import ec_rollcalls as ecr
        _throttle(client, "datos.asambleanacional.gob.ec", ecr.THROTTLE_S)
        _throttle(client, "www.asambleanacional.gob.ec", ecr.THROTTLE_S)   # robots.txt
        tax = ecr.load_taxonomy()
        period = ecr.current_period(ecr.pull_periods(conn, client, today, log), today)
        if period is None:
            raise ValueError("the Asamblea's period list named no current period")
        pid = period[0]
        start = _day_after(since)
        votes = ecr.parse_vote_list(client.get_bytes(
            ecr.VOTES_URL.format(period=pid, start=start, end=today), ecr.FEED,
            "sweep-votes-{0}-{1}-{2}".format(pid, start, today)))
        if votes is None:
            raise ValueError("the vote list for {0}..{1} was not a list".format(start, today))
        n = ours = 0
        roster = False
        for v in votes:
            if (v["date"] or "") <= since:
                continue
            key, areas = ecr.store_division(conn, v, pid, tax, today)
            n += 1
            if not ecr.on_our_ground(areas):
                continue
            ours += 1
            if not EC_POSITIONS:
                continue
            if not roster:
                ecr.pull_roster(conn, client, today, log)
                roster = True
            positions = ecr.parse_detail(client.get_bytes(
                ecr.DETAIL_URL.format(vid=v["voting_id"]), ecr.FEED,
                "detail-{0}".format(v["voting_id"])))
            if positions:
                ecr.store_positions(conn, key, positions)
            else:
                log("  [gap] ec: {0}: the detail listed no position".format(key))
        conn.commit()
        log("ec: {0} plenary vote(s) since {1}, {2} on our ground".format(n, since, ours))
        return n


# --- Bolivia -------------------------------------------------------------------------

class BO(Reader):
    """The Diputados' bill records modified in the window (WordPress `ley`,
    modified_after, newest first), merged and classified by the weekly's
    own functions; items_bo reads them as register updates (a new bill is a
    new record). Bills only (BO2). The Senado's stage lists carry no dates,
    and the written questions (BO4) have not moved since May 2026: both stay
    with the weekly."""

    AGENDA = False

    @staticmethod
    def collect(conn, client, since, today, log=print):
        import bo_rollcalls as bor
        tax, wl, watch = bor.load_taxonomy(), bor.empty_watchlist(), bor.bo_store.watchlist()
        gaps = []
        url = (bor.DIP + "/ley?orderby=modified&order=desc&_fields=" + bor.DIP_FIELDS
               + "&modified_after=" + since + "T23:59:59")
        recs, ok = bor._wp_pages(client, url, "sweep-dip-ley-{0}".format(since), gaps.append)
        if not ok and not recs:
            raise ValueError("the Diputados bill list was not read: {0}".format(gaps[:1]))
        bills = [b for b in bor._latest_per_key(bor.parse_dip_bill(r) for r in recs)
                 if (b["dip_modified"] or "")[:10] > since]
        ours = 0
        for b in bills:
            areas, _moved = bor.upsert_bill(conn, b, tax, wl, watch, today)
            ours += bor.on_our_ground(areas)
        conn.commit()
        log("bo: {0} Diputados bill record(s) modified since {1}, {2} on our ground".format(
            len(bills), since, ours))
        return len(bills)


def _after(value, since):
    return bool(value) and value[:10] > since


# --- the Dominican Republic --------------------------------------------------------

DO_MAX_PAGES = 10     # 100 iniciativas: a fortnight's deposits at the busiest


class DO(Reader):
    """The Cámara de Diputados' iniciativas deposited in the window, from the
    SIL's own list (newest number first, ten a page), classified as the
    weekly does. Votes are the weekly's (positions take a request per ten
    deputies); stage moves of older bills too."""

    AGENDA = False

    @staticmethod
    def collect(conn, client, since, today, log=print):
        import do_rollcalls as dor
        from src import do_store
        _throttle(client, dor.HOST, dor.HOST_THROTTLE_S)
        tax, wl, watch = dor.load_taxonomy(), dor.empty_watchlist(), do_store.watchlist()
        pid = dor.PERIODS[dor.CURRENT_PERIOD]
        n = ours = 0
        for page in range(1, DO_MAX_PAGES + 1):
            url = dor.api("iniciativa/getIniciativas", pid, page=page, keyword="")
            reply = client.get_json(url, dor.FEED, "sweep-bills-{0}-p{1}".format(since, page))
            rows = (reply or {}).get("results") or []
            fresh = 0
            for rec in rows:
                b = dor.parse_bill(rec)
                if not b["bill_key"] or not _after(b["deposited"], since):
                    continue
                res = dor.classify_bill(tax, wl, b, watch)
                dor.store_bill(conn, b, res, today)
                n, fresh = n + 1, fresh + 1
                ours += dor.on_our_ground(res.issue_areas)
            if not rows or fresh == 0:
                break
        conn.commit()
        log("do: {0} iniciativa(s) deposited since {1}, {2} on our ground".format(n, since, ours))
        return n


# --- Panama ------------------------------------------------------------------------

PA_MAX_PAGES = 2      # 40 items: three to six weeks of the term


class PA(Reader):
    """The newest items of segLegis (anteproyectos and proyectos, newest
    first, 20 a page), those presented in the window stored as the weekly
    stores them. No stage histories: a move is the weekly's."""

    AGENDA = False

    @staticmethod
    def collect(conn, client, since, today, log=print):
        import pa_rollcalls as par
        tax = par.load_taxonomy()
        seg = par.SegLegis(client)
        page = seg.show_all(seg.first())
        n = ours = 0
        for number in range(1, PA_MAX_PAGES + 1):
            rows = par.parse_rows(page)
            if not rows:
                raise ValueError("segLegis page {0} listed no bill".format(number))
            for row in rows:
                if not _after(row["presented"], since):
                    continue
                areas, _moved, _read = par.store_bill(conn, row, tax, today)
                n += 1
                ours += par.on_our_ground(areas)
            nxt = par.next_page_number(page, number)
            if nxt is None or min(r["presented"] for r in rows) <= since:
                break
            page = seg.page(page, nxt)
        conn.commit()
        log("pa: {0} item(s) presented since {1}, {2} on our ground".format(n, since, ours))
        return n


# --- Honduras ----------------------------------------------------------------------

HN_NEWS_PAGE = 10
HN_NEWS_PAGES = 5
HN_SESSIONS = 20
HN_MAX_AGENDAS = 4    # 2 requests of about 3 s each per session; the rest wait for the weekly


def hn_months(since, today):
    """(year, month) for each month from the day after `since` to `today`."""
    d = datetime.date.fromisoformat(since) + datetime.timedelta(days=1)
    end = datetime.date.fromisoformat(today)
    out = []
    while (d.year, d.month) <= (end.year, end.month):
        out.append((d.year, d.month))
        d = (d.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
    return out


class HN(Reader):
    """Press releases, legislative files, sessions with their agendas and La
    Gaceta's issues dated in the window, each from the endpoint the weekly
    reads, newest first, stored by the weekly's own storers."""

    AGENDA = False

    @staticmethod
    def collect(conn, client, since, today, log=print):
        import hn_rollcalls as hnr
        tax = hnr.load_taxonomy()
        got = {"press": 0, "files": 0, "sessions": 0, "gazette": 0}
        ours = 0
        # Press releases, newest first, until one predates the window.
        for page in range(HN_NEWS_PAGES):
            skip = page * HN_NEWS_PAGE
            _total, posts = hnr.parse_news(client.get_json(
                hnr.NEWS_API.format(limit=HN_NEWS_PAGE, skip=skip), hnr.FEED,
                "sweep-news-{0}-{1}".format(since, skip)))
            for p in posts:
                if _after(p["created_at"], since):
                    ours += hnr.on_our_ground(hnr.store_news(conn, p, tax, today))
                    got["press"] += 1
            if not posts or any(not _after(p["created_at"], since) for p in posts):
                break
        # The ten most recently touched files in each stage.
        for code in hnr.ESTADOS:
            data = hnr.unwrap(client.get_json("{0}/expediente?estado={1}".format(hnr.API, code),
                                              hnr.FEED, "sweep-expediente-{0}".format(code)),
                              "expediente")
            for b in hnr.parse_expedientes(data):
                if _after(b["fecha"], since):
                    ours += hnr.on_our_ground(hnr.store_bill(conn, b, tax, today))
                    got["files"] += 1
        # Sessions in the window and their agendas.
        data = hnr.unwrap(client.get_json("{0}/sesiones?page=1&pageSize={1}".format(
            hnr.API, HN_SESSIONS), hnr.FEED, "sweep-sesiones-{0}".format(since)), "sesiones")
        for s in hnr.parse_sessions(data):
            if _after(s["schedule"], since):
                hnr.store_session(conn, s, today)
                got["sessions"] += 1
        conn.commit()
        if got["sessions"]:
            _read, _stored, agenda_ours, gaps = hnr.pull_agendas(conn, client, today, tax=tax,
                                                                 log=log, limit=HN_MAX_AGENDAS)
            ours += agenda_ours
            if gaps:
                log("  [gap] hn: {0} session agenda(s) unread".format(gaps))
        # La Gaceta, the month listing (and its later pages) for each month.
        for year, month in hn_months(since, today):
            start, done = 0, set()
            while start is not None and start not in done:
                done.add(start)
                url = hnr.GACETA_MONTH.format(year=year, month=hnr.MONTHS[month - 1])
                page = client.get_text(url + ("?start={0}".format(start) if start else ""),
                                       hnr.FEED, "sweep-gaceta-{0}-{1:02d}-{2}".format(
                                           year, month, start))
                issues, starts = hnr.parse_gazette(page)
                for g in issues:
                    if _after(g["date"], since):
                        ours += hnr.on_our_ground(hnr.store_issue(conn, g, tax, today))
                        got["gazette"] += 1
                later = [s for s in starts if s > start]
                start = later[0] if later and issues else None
        conn.commit()
        log("hn: since {0}, {1[press]} press release(s), {1[files]} file(s), {1[sessions]} "
            "session(s), {1[gazette]} Gaceta issue(s); {2} on our ground".format(since, got, ours))
        return sum(got.values())


# --- Uruguay -----------------------------------------------------------------------

def _last_modified(client, url, feed, slug):
    """The file's Last-Modified as an ISO date, from a one-byte Range request;
    None when the server does not say."""
    from email.utils import parsedate_to_datetime
    client.get_bytes(url, feed, slug, first_bytes=1)
    value = (getattr(client, "last_headers", None) or {}).get("Last-Modified")
    try:
        return parsedate_to_datetime(value).date().isoformat() if value else None
    except (TypeError, ValueError):
        return None


class UY(Reader):
    """The Cámara de Representantes' pedidos de informes dated in the window,
    from its open-data file (the weekly's own, 1.09 MB), read once a day and
    only when its Last-Modified moved after `since`. Laws (IMPO, a numbered
    walk at IMPO's 10 s crawl delay) and the Diario's vote totals (PDFs
    filed months late) stay the weekly's."""

    AGENDA = False
    ONCE_A_DAY = True

    @staticmethod
    def collect(conn, client, since, today, log=print):
        import uy_rollcalls as uyr
        changed = _last_modified(client, uyr.QUESTIONS_URL, uyr.FEED,
                                 "sweep-pedidos-head-{0}".format(today))
        if changed is not None and changed <= since:
            log("uy: the pedidos file is unchanged since {0}; not read".format(changed))
            return 0
        raw = client.get_bytes(uyr.QUESTIONS_URL, uyr.FEED, "pedidos-informe")
        tax = uyr.load_taxonomy()
        n = ours = 0
        for q in uyr.parse_questions(uyr.load_json_bytes(raw)):
            if _after(q["date"], since):
                ours += uyr.on_our_ground(uyr.store_question(conn, q, tax, today))
                n += 1
        conn.commit()
        log("uy: {0} pedido(s) de informes since {1}, {2} on our ground".format(n, since, ours))
        return n


READERS = {"nl": NL, "pl": PL, "ch": CH, "br": BR, "it": IT, "at": AT, "fr": FR, "es": ES,
           "be": BE, "pt": PT, "hr": HR, "sk": SK, "ar": AR, "cl": CL, "pe": PE, "ec": EC, "bo": BO, "do": DO, "pa": PA, "hn": HN,
           "uy": UY}


def agenda(conn, cc, client, today, log=print, days=AGENDA_DAYS):
    """The country's agenda over the next `days` into the scratch store
    (src/agenda.collect). Returns (points, on our ground, gaps)."""
    from src import agenda as ag
    return ag.collect(conn, cc, client, today, days=days, log=log)


class NoArchive:
    """A client whose every fetch skips the archive (France's agenda zip; see
    FR). `fetched` keeps (feed, slug, bytes) of each binary reply, so the run
    can archive it on a day it yields an alert without fetching it again."""

    def __init__(self, client):
        self.client = client
        self.fetched = []

    def get_bytes(self, url, feed, slug, timeout=None, first_bytes=None, archive=True,
                  headers=None):
        raw = self.client.get_bytes(url, feed, slug, timeout=timeout, archive=False)
        self.fetched.append((feed, slug, raw))
        return raw

    def get_json(self, url, feed, slug, timeout=None, archive=True):
        return self.client.get_json(url, feed, slug, timeout=timeout, archive=False)

    def get_text(self, url, feed, slug, timeout=None, archive=True, **kw):
        return self.client.get_text(url, feed, slug, timeout=timeout, archive=False, **kw)

    def __getattr__(self, name):
        return getattr(self.client, name)


def archive_hit(client, fetched, log=print):
    """Archive what a NoArchive client read, on a day with an alert from it,
    through the client's own archive (data/raw/<date>/<feed>_<slug>.json.gz)."""
    for feed, slug, raw in fetched:
        try:
            path = client._archive(raw, feed, slug)
            log("  archived {0}".format(os.path.relpath(path, ROOT)))
        except (AttributeError, OSError) as exc:
            log("  [gap] could not archive {0}_{1}: {2}".format(feed, slug, str(exc)[:100]))
