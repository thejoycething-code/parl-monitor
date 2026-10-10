"""The daily vote briefs' direct readers: the last few days of votes, read
from sources that publish them the same day cheaply and openly, into a
THROWAWAY store (src/country_vote_brief.py, "two ways in").

One reader per country, each a thin layer over the country's own collector
(tools/<cc>_rollcalls.py): the collector's parsers, classifiers and storing
functions write the recent votes, the bills they are on and the positions
on our ground into a scratch sqlite file that holds nothing else, so the
edition adapter reads it exactly as it reads the store, and the brief keys
each vote exactly as the weekly run will. Nothing here writes the store,
and the scratch file is deleted after the run (tools/country_vote_briefs.py
--daily).

Each reader has two halves:

  collect(conn, client, since, today, log) -> votes stored. The votes on or
      after `since` and everything needed to classify them. Large parent
      lists the weekly collector already archives (the Sejm's print and
      process lists) are fetched with archive=False, as tools/ie_division_brief.py
      does for the Oireachtas bill list; the vote payloads are archived.
  positions(conn, client, today, log, keys) -> votes completed. Member
      positions for the votes the brief would send (`keys`: their division
      keys, from the brief's own candidates) that have none yet; without
      `keys`, for every vote on our ground or watched. Nothing is fetched
      for any other vote.

Measured costs per run on a sitting day (9-10 October 2026 shapes):

  nl  1 request (decisions with zaak, dossier and every position, $expand)
  pl  2 + 1 per sitting in the window + 1 per vote on our ground; the
      prints' processes from data/vote-briefs/pl-parents.json, which the
      weekly writes from the store; nothing beyond the 2 when no sitting
  ch  1 session list + 1 vote list per current session + business batches
      (40 a request, DE and FR) + 1 per vote on our ground; the Ständerat
      publishes only per session, so its votes come with the weekly
  br  Senado: 1 request (positions included); Câmara: the API's vote list
      (100 a page) + 1 detail per nominal vote + 1 per bill named + 1 per
      vote on our ground. The Câmara's bulk year files (8 MB) stay the
      weekly's.
  it  Senate: 2 SPARQL queries + 1 for the bills voted + 1 per vote on our
      ground; Camera: 1 Openpolis page + 1 per vote on our ground (its
      positions read 'SEC' until the Camera's record arrives: held).

France is NOT read daily: the Assemblée publishes its scrutins only as one
27 MB nightly zip (docs/france-scope.md), so French votes are briefed after
the Saturday collection (jobs/fr-weekly.sh). Reading only the zip's newest
members by HTTP range was tried on 10 October 2026 (the server honours
Range): its CDN answered two successive range requests from two different
builds of the file (26,987,736 and 26,960,828 bytes, no ETag check
possible across them), so a partial read cannot be trusted to be one file.
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

from src.http import FetchError  # noqa: E402

DAILY = ("nl", "pl", "ch", "br", "it")


def _ground(areas_json, *watched):
    """On our ground: a shown area, or watched."""
    try:
        areas = json.loads(areas_json or "[]")
    except (TypeError, ValueError):
        areas = []
    return any(a != 11 for a in areas) or any(watched)


def _wanted(keys, key, areas_json, *watched):
    """Fetch positions for this vote? Only for the votes the brief would send
    (`keys`, from src/country_vote_brief.candidates); without them, for every
    vote on our ground or watched."""
    if keys is not None:
        return key in keys
    return _ground(areas_json, *watched)


class NoArchive:
    """A client whose get_json never archives: for the parent lists the weekly
    collector archives already."""

    def __init__(self, client):
        self.client = client

    def get_json(self, url, feed, slug, timeout=None, archive=True):
        return self.client.get_json(url, feed, slug, timeout=timeout, archive=False)

    def __getattr__(self, name):
        return getattr(self.client, name)


# --- the Netherlands ----------------------------------------------------------------

class NL:
    """One OData query brings each decision with its zaak, dossier and every
    position (tools/nl_rollcalls.pull_decisions). Positions arrive up to a
    day after the result; the brief holds such a vote (positions_pending)."""

    @staticmethod
    def collect(conn, client, since, today, log=print):
        import nl_rollcalls as nlr
        tax = nlr.load_taxonomy(log=lambda *_a: None)
        n = nlr.pull_decisions(conn, client, today, since, tax, log=log, max_pages=6)
        if n["gaps"] and not n["read"]:
            raise ValueError("the Open Data Portaal's decisions were not read")
        return n["stored"]

    @staticmethod
    def positions(conn, client, today, log=print, keys=None):
        return 0                      # they come with the decision, or not yet


# --- Poland -------------------------------------------------------------------------

class PL:
    """The Sejm API: the votings index says which sittings voted in the
    window; a sitting's vote list carries the headers; a vote's detail every
    deputy's position and club. A vote is classified by the prints it cites,
    resolved to their legislative process (tools/pl_rollcalls.store_division).

    The print-to-process map comes from the store, not the API: the term's
    print list is 1.8 MB, and on 10 October 2026 it and the single-print
    endpoint both timed out four times running while the vote endpoints
    answered at once. So each weekly run (tools/country_vote_briefs.py
    --country pl --send) writes data/vote-briefs/pl-parents.json: every
    process on our ground or watched, with its areas, terms and tier, and
    the prints that belong to it. A process opened since the last weekly is
    not in it; its votes are classified on their own words until then."""

    PARENTS = "pl-parents.json"

    @staticmethod
    def export(conn):
        """{processes: [...], prints: {print_key: process_key}} for the
        processes on our ground or watched, from the store."""
        wl = _watch("pl")
        procs = [dict(r) for r in conn.execute(
            "SELECT process_key, term, number, title, document_type, start_date, "
            "areas, matched_terms, tier FROM pl_processes")
            if _ground(r["areas"], r["process_key"] in wl)]
        keys = {p["process_key"] for p in procs}
        prints = {r[0]: r[1] for r in conn.execute(
            "SELECT print_key, process_key FROM pl_prints WHERE process_key IS NOT NULL")
            if r[1] in keys}
        return {"processes": procs, "prints": prints}

    @staticmethod
    def seed(conn, parents, today):
        for p in parents.get("processes") or []:
            conn.execute(
                "INSERT OR REPLACE INTO pl_processes (process_key, term, number, title, "
                "document_type, start_date, areas, matched_terms, tier, first_seen, "
                "last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (p["process_key"], p["term"], p["number"], p.get("title"),
                 p.get("document_type"), p.get("start_date"), p.get("areas"),
                 p.get("matched_terms"), p.get("tier"), today, today))
        for print_key, process_key in (parents.get("prints") or {}).items():
            term, _, number = print_key.partition("/")
            conn.execute("INSERT OR REPLACE INTO pl_prints (print_key, term, number, process_key, "
                         "first_seen, last_seen) VALUES (?,?,?,?,?,?)",
                         (print_key, int(term), number, process_key, today, today))

    @staticmethod
    def collect(conn, client, since, today, log=print, parents_dir=None):
        import pl_rollcalls as plr
        parents = load_parents("pl", parents_dir)
        terms = [p["term"] for p in (parents or {}).get("processes") or [] if p.get("term")]
        if terms:
            term = max(int(t) for t in terms)          # one request fewer
        else:
            term, _ = plr.current_term(client.get_json(plr.TERMS, plr.FEED, "brief-terms",
                                                       archive=False))
        if term is None:
            raise ValueError("no current term in the Sejm's term list")
        index = client.get_json(plr.VOTE_INDEX.format(term), plr.FEED,
                                "brief-votings-{0}".format(term))
        sittings = sorted({d["proceeding"] for d in index or []
                           if (d.get("date") or "")[:10] >= since and int(d.get("votingsNum") or 0)})
        if not sittings:
            log("pl: no Sejm votes since {0}".format(since))
            return 0
        if parents is None:
            log("  pl: no {0} yet (the weekly writes it); votes classified on their own words".format(
                PL.PARENTS))
        else:
            PL.seed(conn, parents, today)
        tax = plr.load_taxonomy()
        n = 0
        for s in sittings:
            got = client.get_json(plr.SITTING.format(term, s), plr.FEED,
                                  "brief-sitting-{0}-{1}".format(term, s))
            for v in got or []:
                if (v.get("date") or "")[:10] >= since:
                    plr.store_division(conn, v, term, tax, today)
                    n += 1
        conn.commit()
        log("pl: {0} Sejm vote(s) since {1} at sitting(s) {2}".format(
            n, since, ", ".join(str(s) for s in sittings)))
        return n

    @staticmethod
    def positions(conn, client, today, log=print, keys=None):
        import pl_rollcalls as plr
        todo = [r for r in conn.execute(
            "SELECT division_key, term, sitting, number, areas, process_keys FROM pl_divisions "
            "WHERE positions IS NULL").fetchall()
            if _wanted(keys, r[0], r[4], *(k in _watch("pl") for k in json.loads(r[5] or "[]")))]
        if not todo:
            return 0
        plr.pull_members(conn, client, todo[0][1], today, log=log)
        done = 0
        for key, term, sitting, number, _a, _p in todo:
            v = client.get_json(plr.VOTE.format(term, sitting, number), plr.FEED,
                                "vote-{0}-{1}-{2}".format(term, sitting, number))
            if v.get("votes"):
                plr.store_positions(conn, key, v, term)
                done += 1
        conn.commit()
        return done


# --- Switzerland ---------------------------------------------------------------------

class CH:
    """The Parliament's OData service: the Nationalrat's votes of the current
    session, the businesses they are on (German and French, for the
    classification), and each vote's Voting rows on our ground."""

    @staticmethod
    def collect(conn, client, since, today, log=print):
        import ch_rollcalls as chr_
        sessions = chr_.pull_sessions(conn, client, today)
        live = [s for s in sessions if s["start"] and s["start"] <= today
                and (s["end"] or today) >= since]
        if not live:
            log("ch: no session since {0}".format(since))
            return 0
        tax = chr_.Taxonomies()
        for s in live:
            chr_.pull_nr_session(conn, client, tax, s["id"], today, log=log)
        conn.execute("DELETE FROM ch_votes WHERE division_key IN (SELECT division_key FROM "
                     "ch_divisions WHERE date < ?)", (since,))
        conn.execute("DELETE FROM ch_divisions WHERE date < ? OR date IS NULL", (since,))
        ids = [b for (b,) in conn.execute(
            "SELECT DISTINCT business_id FROM ch_divisions WHERE business_id IS NOT NULL")]
        chr_.refetch_businesses(conn, client, tax, today, ids, log=log)
        chr_.derive_division_areas(conn, tax)
        (n,) = conn.execute("SELECT COUNT(*) FROM ch_divisions").fetchone()
        log("ch: {0} Nationalrat vote(s) since {1}".format(n, since))
        return n

    @staticmethod
    def positions(conn, client, today, log=print, keys=None):
        import ch_rollcalls as chr_
        from src import ch_store
        wl = _watch("ch")
        done = 0
        for key, vote_id, areas, bid in conn.execute(
                "SELECT division_key, vote_id, areas, business_id FROM ch_divisions WHERE "
                "council='NR' AND COALESCE(positions, 0) = 0").fetchall():
            watched = bid is not None and (str(bid) in wl or
                                           ch_store.short_number(int(bid)) in wl)
            if not _wanted(keys, key, areas, watched):
                continue
            got = chr_.fetch_nr_positions(conn, client, vote_id, today)
            if got:
                chr_.store_positions(conn, key, got, tally=True)
                done += 1
        conn.commit()
        return done


# --- Brazil --------------------------------------------------------------------------

CAMARA_LIST = ("{0}/votacoes?dataInicio={1}&dataFim={2}&itens=100&ordem=ASC"
               "&ordenarPor=dataHoraRegistro")
_PLACAR = re.compile(r"Sim:\s*(\d+)\s*;\s*N[ãa]o:\s*(\d+)(?:\s*;\s*Absten[çc][ãa]o:\s*(\d+))?"
                     r"(?:\s*;\s*Total:\s*(\d+))?", re.I)
# The older wording: 'Resultado:  18 votos "Sim", 19 votos "Não".' (2334926-27).
_PLACAR_OLD = re.compile(r"(\d+)\s+votos?\s+\W?Sim\W?\s*,\s*(\d+)\s+votos?\s+\W?N[ãa]o", re.I)


def camara_nominal(rec):
    """A Câmara API vote list record -> a division dict when it was NOMINAL.
    The list carries no totals; a nominal vote's description ends with its
    count ('... Sim: 346; Não: 46; Abstenção: 3; Total: 395.', or in the
    older wording '18 votos "Sim", 19 votos "Não"'; measured on the nominal
    votes of 1-3 September 2026 and the bulk fixture), and a symbolic one
    has none. A nominal vote described some other way is the weekly's (the
    bulk year file's totals)."""
    desc = rec.get("descricao") or ""
    hit = _PLACAR.search(desc)
    if hit:
        yes, no = int(hit.group(1)), int(hit.group(2))
        total = int(hit.group(4)) if hit.group(4) else None
        other = (total - yes - no) if total is not None else int(hit.group(3) or 0)
    else:
        hit = _PLACAR_OLD.search(desc)
        if not hit:
            return None
        yes, no, other = int(hit.group(1)), int(hit.group(2)), 0
    approved = rec.get("aprovacao")
    return {"chamber": "camara", "source_id": rec["id"],
            "date": (rec.get("data") or "")[:10] or None,
            "organ": (rec.get("siglaOrgao") or "").strip() or None,
            "description": desc.strip() or None,
            "result": {1: "approved", 0: "rejected"}.get(approved if isinstance(approved, int)
                                                         else None),
            "yes": yes, "no": no, "other": max(other, 0), "secret": 0}


def camara_affected(detail):
    """The proposições a vote affected, from its detail, in the shape of
    tools/br_rollcalls.parse_camara_links (the bulk file's links)."""
    import br_rollcalls as brr
    out = []
    for p in ((detail or {}).get("dados") or {}).get("proposicoesAfetadas") or []:
        if not p.get("id"):
            continue
        b = {"camara_id": brr._int(p["id"]), "sigla": brr._clean(p.get("siglaTipo")),
             "numero": brr._int(p.get("numero")), "ano": brr._int(p.get("ano")),
             "ementa": brr._clean(p.get("ementa"))}
        b["bill_key"] = brr.bill_key(b["sigla"], b["numero"], b["ano"], b["camara_id"])
        if all(x["camara_id"] != b["camara_id"] for x in out):
            out.append(b)
    return out


class BR:
    """The Senado's vote API (one call, positions included) and the Câmara's
    API v2: its vote list, the detail of each nominal vote (the bills it
    affected), each bill's record (keywords) and the votes of those on our
    ground. Classification is tools/br_rollcalls.reclassify over the scratch
    store, the weekly's own."""

    @staticmethod
    def collect(conn, client, since, today, log=print):
        import br_rollcalls as brr
        n = 0
        rows = client.get_json("{0}/votacao?dataInicio={1}&dataFim={2}".format(
            brr.SENADO, since, today), brr.FEED, "brief-senado-votacao-{0}".format(since))
        for d in brr.parse_senado_votacoes(rows if isinstance(rows, list) else []):
            if d["bill"]:
                brr.store_bill(conn, d["bill"], today, log=log)
            dkey = brr.store_division(conn, d, today, bill=d["bill"],
                                      linked=[d["bill"]] if d["bill"] else [])
            brr.store_positions(conn, dkey, d["positions"], d["date"], "senado", today)
            n += 1
        url, page = CAMARA_LIST.format(brr.CAMARA_API, since, today), 0
        nominal = []
        while url and page < 20:
            got = client.get_json(url, brr.FEED, "brief-camara-votacoes-{0}-p{1}".format(since, page))
            nominal += [d for d in (camara_nominal(r) for r in got.get("dados") or []) if d]
            url = next((l.get("href") for l in got.get("links") or [] if l.get("rel") == "next"),
                       None)
            page += 1
        for d in nominal:
            detail = client.get_json("{0}/votacoes/{1}".format(brr.CAMARA_API, d["source_id"]),
                                     brr.FEED, "brief-camara-votacao-" + d["source_id"])
            linked = camara_affected(detail)
            for b in linked:
                brr.store_bill(conn, b, today, log=log)
            brr.store_division(conn, d, today, bill=brr.main_bill(linked), linked=linked)
            n += 1
        conn.commit()
        brr.pull_bill_details(conn, client, today, log=log)
        brr.reclassify(conn, tax=brr.load_taxonomy(), log=lambda *_a: None)
        log("br: {0} nominal vote(s) since {1} ({2} in the Câmara)".format(n, since, len(nominal)))
        return n

    @staticmethod
    def positions(conn, client, today, log=print, keys=None):
        import br_rollcalls as brr
        wl, want = _watch("br"), keys
        done = 0
        for dkey, sid, date, areas, bkey, linked in conn.execute(
                "SELECT division_key, source_id, date, areas, bill_key, linked_bills FROM "
                "br_divisions WHERE chamber='camara' AND COALESCE(positions_fetched, 0)=0").fetchall():
            bills = [bkey] + json.loads(linked or "[]")
            if not _wanted(want, dkey, areas, *(k in wl for k in bills if k)):
                continue
            raw = client.get_json("{0}/votacoes/{1}/votos".format(brr.CAMARA_API, sid), brr.FEED,
                                  "camara-votos-" + sid, archive=False)
            got = brr.parse_camara_votos(raw)
            if got:
                brr.store_positions(conn, dkey, got, date, "camara", today)
                try:
                    orient = client.get_json("{0}/votacoes/{1}/orientacoes".format(
                        brr.CAMARA_API, sid), brr.FEED, "brief-camara-orientacoes-" + sid)
                    brr.store_orientations(conn, dkey, [
                        (r.get("siglaBancada") or r.get("siglaPartidoBloco"),
                         r.get("orientacaoVoto")) for r in orient.get("dados") or []
                        if (r.get("siglaBancada") or r.get("siglaPartidoBloco"))
                        and r.get("orientacaoVoto")])
                except (FetchError, ValueError):
                    pass              # the orientations are a line, not the brief
                done += 1
        conn.commit()
        return done


# --- Italy ---------------------------------------------------------------------------

def q_bills_by_fase(leg, fases):
    import it_rollcalls as itr
    inlist = ", ".join('"{0}"'.format(f.replace('"', "")) for f in fases)
    return itr.PREFIXES + """SELECT ?d ?fase ?iddl ?titolo ?breve ?natura ?iniz ?pres ?stato ?statodata ?nlegge ?dlegge WHERE {{
 ?d a osr:Ddl ; osr:legislatura {0} ; osr:fase ?fase ; osr:titolo ?titolo .
 OPTIONAL {{ ?d osr:idDdl ?iddl }} OPTIONAL {{ ?d osr:titoloBreve ?breve }}
 OPTIONAL {{ ?d osr:natura ?natura }} OPTIONAL {{ ?d osr:descrIniziativa ?iniz }}
 OPTIONAL {{ ?d osr:dataPresentazione ?pres }} OPTIONAL {{ ?d osr:statoDdl ?stato }}
 OPTIONAL {{ ?d osr:dataStatoDdl ?statodata }} OPTIONAL {{ ?d osr:numeroLegge ?nlegge }}
 OPTIONAL {{ ?d osr:dataLegge ?dlegge }}
 FILTER(STR(?fase) IN ({1})) }} LIMIT {2}""".format(int(leg), inlist, itr.SPARQL_CAP)


def q_teseo_by_fase(leg, fases):
    import it_rollcalls as itr
    inlist = ", ".join('"{0}"'.format(f.replace('"', "")) for f in fases)
    return itr.PREFIXES + """SELECT DISTINCT ?d ?label WHERE {{
 ?d a osr:Ddl ; osr:legislatura {0} ; osr:fase ?fase ; osr:classificazione ?c .
 ?c osr:livello ?liv ; dc:subject ?t . ?t skos:prefLabel ?label
 FILTER(STR(?fase) IN ({1}) && STR(?liv) = "Generale") }} LIMIT {2}""".format(
        int(leg), inlist, itr.SPARQL_CAP)


class IT:
    """The Senate's SPARQL endpoint for its votes (the latest sittings), the
    readings they are on and each vote's positions; Openpolis for the
    Camera's newest votes and their positions. The bills come first so each
    vote is classified with its reading's areas, as the weekly does."""

    CAMERA_PAGE = 200

    @staticmethod
    def collect(conn, client, since, today, log=print):
        import it_rollcalls as itr
        leg = itr.LEGISLATURE
        tax = itr.filt.load_taxonomy(itr.taxonomy_path(), country=itr.TAXONOMY_COUNTRY)
        wl = itr.empty_watchlist()
        hi = int(itr.sparql(client, itr.q_senate_max_sitting(leg),
                            "brief-senate-max-sitting")[0]["hi"])
        senate = [d for d in itr.parse_senate_votes(itr.sparql(
            client, itr.q_senate_votes(leg, max(hi - 3, 0), hi + 1),
            "brief-senate-votes-{0}".format(hi))).values() if (d["date"] or "") >= since]
        url = itr.OPENPOLIS.format(leg) + "votings/?branch=C&page_size={0}".format(IT.CAMERA_PAGE)
        data = client.get_json(url, itr.FEED, "brief-camera-votings-{0}".format(today))
        camera = [v for v in itr.parse_camera_list(data.get("results"), leg)
                  if (v["date"] or "") >= since]
        sittings = {}
        for v in camera:
            sittings.setdefault(v["sitting"], []).append(v)
        for votes in sittings.values():
            bills = itr.infer_camera_bills(votes, leg)
            for v in votes:
                v["bill_key"], v["bill_inferred"] = bills.get(v["key"], (None, 0))
                v["bill_keys"] = [v["bill_key"]] if v["bill_key"] else []
        fases = sorted({k.split("/", 1)[1] for d in senate + camera for k in itr._keys(d) if "/" in k})
        if fases:
            rows = itr.sparql(client, q_bills_by_fase(leg, fases), "brief-bills-{0}".format(today))
            subj = itr.sparql(client, q_teseo_by_fase(leg, fases), "brief-teseo-{0}".format(today))
            for b in itr.attach_subjects(itr.parse_bills(rows, leg), subj).values():
                itr.store_bill(conn, b, itr.classify_bill(tax, wl, b), today)
        for d in senate + camera:
            itr.store_division(conn, d, tax, wl, today)
        conn.commit()
        log("it: {0} Senate and {1} Camera vote(s) since {2}".format(len(senate), len(camera), since))
        return len(senate) + len(camera)

    @staticmethod
    def positions(conn, client, today, log=print, keys=None):
        import it_rollcalls as itr
        wl = _watch("it")
        todo = [r for r in conn.execute(
            "SELECT division_key, chamber, date, areas, bill_keys FROM it_divisions WHERE "
            "positions_fetched=0").fetchall()
            if _wanted(keys, r[0], r[3], *(k in wl for k in json.loads(r[4] or "[]")))]
        if not todo:
            return 0
        members = {}
        if any(r[1] == "senato" for r in todo):
            members, _ = itr.pull_senators(conn, client, today, log=log)
        done = 0
        for key, chamber, date, _a, _k in todo:
            if chamber == "senato":
                _, lg, sitting, num = key.split("-")
                rows = itr.sparql(client, itr.q_senate_positions("{0}-{1}-{2}".format(lg, sitting, num)),
                                  "senate-positions-" + key)
                positions = [(m, p, itr.group_on((members.get(m) or {}).get("groups"), date))
                             for m, p in itr.parse_senate_positions(rows)]
            else:
                ident = key[len("camera-"):]
                rec = client.get_json(itr.OPENPOLIS.format(itr.LEGISLATURE) + "votings/{0}/".format(ident),
                                      itr.FEED, "camera-voting-" + ident)
                counts, plist, published = itr.parse_camera_detail(rec)
                if not published:
                    log("  it {0}: positions not yet published (all 'SEC')".format(key))
                    continue
                conn.execute("UPDATE it_divisions SET ayes=?, noes=?, abstentions=? WHERE "
                             "division_key=?", (counts["ayes"], counts["noes"],
                                                counts["abstentions"], key))
                positions = []
                for member, name, grp, position in plist:
                    itr.upsert_member(conn, member, "camera", name, grp, None, today)
                    positions.append((member, position, grp))
            if positions:
                itr.store_positions(conn, key, positions)
                done += 1
        conn.commit()
        return done


# --- shared -------------------------------------------------------------------------

def parents_path(cc, directory=None):
    from src import country_vote_brief as cvb
    return os.path.join(directory or cvb.LEDGER_DIR, "{0}-parents.json".format(cc))


def load_parents(cc, directory=None):
    path = parents_path(cc, directory)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def save_parents(cc, conn, directory=None):
    """Write data/vote-briefs/<cc>-parents.json from the store, for a reader
    that has an `export`. Returns the path, or None."""
    reader = READERS.get(cc)
    if reader is None or not hasattr(reader, "export"):
        return None
    got = reader.export(conn)
    path = parents_path(cc, directory)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(got, fh, ensure_ascii=False, indent=0, sort_keys=True)
        fh.write("\n")
    return path


def _watch(cc):
    """The country's watchlist keys (config/watchlist-<cc>.yaml), as strings."""
    from src import latam
    return {str(k) for k in latam.watchlist(cc)}


READERS = {"nl": NL, "pl": PL, "ch": CH, "br": BR, "it": IT}


def urlencode(**kw):
    return urllib.parse.urlencode(kw)
