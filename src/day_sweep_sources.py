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
"""

from __future__ import annotations

import datetime
import json
import os
import sys
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)


SWEEP = ("nl", "pl", "ch", "br", "it", "at", "fr", "es")
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

class FR(Reader):
    """The Assemblée's ordre du jour only (src/agendas/fr.py), once a day; its
    bills and questions stay with the Saturday collection (see the costs
    above). The agenda zip is fetched unarchived and archived on a day it
    yields an alert (archive_hit)."""

    ONCE_A_DAY = True
    ARCHIVE_ON_HIT = True


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


READERS = {"nl": NL, "pl": PL, "ch": CH, "br": BR, "it": IT, "at": AT, "fr": FR, "es": ES}


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
