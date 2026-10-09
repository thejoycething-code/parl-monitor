#!/usr/bin/env python3
"""Brazil, National Congress: members, nominal votes of the Câmara dos
Deputados and the Senado Federal with every member's position, the Câmara
party orientations, and the proposições the votes are about.

    python3 tools/br_rollcalls.py                    # the current year (and any backlog)
    python3 tools/br_rollcalls.py --from-year 2023   # back to the legislature's start
    python3 tools/br_rollcalls.py --dry-run          # count this year's votes, store nothing
    python3 tools/br_rollcalls.py --reclassify       # re-derive areas, offline
    python3 tools/br_rollcalls.py --db /tmp/br.db    # anywhere but the store

PHASE 1 (9 October 2026); see docs/brazil-scope.md. Every source is
official, open and keyless:

  * dadosabertos.camara.leg.br/arquivos/votacoes/json/votacoes-<year>.json
    -- every votação of the year in ONE file (8 MB for 2026, rebuilt daily
    about 07:00 UTC), with the yes/no/other totals that tell a nominal vote
    from a symbolic one. Two companion files, votacoesProposicoes (which
    proposições each vote is about) and votacoesOrientacoes (how each party
    leader told the bench to vote), come the same way.
  * dadosabertos.camara.leg.br/api/v2/votacoes/<id>/votos -- every deputy's
    position on one vote, with party and state AT THE VOTE. Asked once per
    nominal vote (450-550 a year), never for a symbolic one, which has none.
  * dadosabertos.camara.leg.br/api/v2/proposicoes/<id> -- the voted bill's
    record, read once, for its keywords: the Câmara's indexers write the words
    an ementa leaves out (PL 1904/2024 cites "arts. 124 to 128 of the Penal
    Code"; its keywords say "aborto").
  * legis.senado.leg.br/dadosabertos/votacao?dataInicio=..&dataFim=.. --
    every nominal Senate vote of up to a year in ONE call, positions included.
  * .../api/v2/deputados and .../dadosabertos/senador/lista/atual.json --
    the members in office.

ONLY NOMINAL VOTES ARE DIVISIONS. Both houses decide most things by
symbolic vote, which records no member's position: in 2025 the Câmara held
13,827 votações and 550 were nominal; the Senate held 128 nominal votes, 72
of them secret ballots on nominations. A secret ballot is stored with its
positions as the Senate prints them ('Votou': voted, not how).

NOTHING IS CLASSIFIED BY TERM YET. The English taxonomy is blind to
Portuguese (measured: 20 of 14,443 Câmara bills of 2025-26 and 0 of 1,597
nominal votes). Until Christopher approves a Portuguese list and
config/taxonomy-pt.yaml is generated from it, areas come only from
config/watchlist-br.yaml, by proposição KEY. The day that file exists this
collector reads it with no code change; run --reclassify then.

A BILL'S NUMBER CAN CHANGE. Since 2019 the two houses share one numbering,
but an older Câmara bill takes a new number when it reaches the Senate, and
the Câmara's own record then shows the new one (PL 3179/2012 became
PL 1338/2022). The Câmara ID does not change, so a bill seen under a new
number is renamed in place, divisions and all, and the rename is logged.

Separation guarantee: writes br_* tables and the shared gaps table only.
ONE WRITER AT A TIME on the store.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import br_store, db, drain, filter as filt  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402

FEED = "br-rollcalls"
# The 57th legislature opened on 1 February 2023 and runs to 31 January 2027.
LEGISLATURE_START_YEAR = 2023
TAXONOMY_PT = os.path.join(ROOT, "config", "taxonomy-pt.yaml")
# The country this collector matches for: a shared language list
# (taxonomy-es, -pt, -nl, -it, -fr, -atch) tags a country's own terms
# [only: ...] and filter.load_taxonomy keeps only ours (10 October 2026).
TAXONOMY_COUNTRY = "br"
CAMARA_API = "https://dadosabertos.camara.leg.br/api/v2"
CAMARA_BULK = "https://dadosabertos.camara.leg.br/arquivos/{0}/json/{0}-{1}.json"
SENADO = "https://legis.senado.leg.br/dadosabertos"
BUDGET_S = drain.DEFAULT_S
# Migration is collated, never campaigned (src/partner.py HIDDEN_AREAS).
HIDDEN_AREAS = (11,)
# Since 2019 both houses share one numbering (see src/br_store.py KEYS).
UNIFIED_FROM = 2019
# The proposição a vote is ABOUT, in order of preference, when the Câmara
# links several: an urgency request (REQ) is linked beside the bill it
# speeds up, and the bill is what the vote means.
SUBSTANTIVE = ("PEC", "PLP", "PL", "PLV", "MPV", "PDL", "PDC", "PRC", "PLN")


def today_iso():
    return datetime.date.today().isoformat()


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _clean(value):
    value = (value or "").strip() if isinstance(value, str) else value
    return value or None


def bill_key(sigla, numero, ano, camara_id=None, chamber="camara"):
    """'PL', 1904, 2024 -> 'PL 1904/2024'. A pre-2019 Senate proposição is
    'SF ...'; a Câmara record with no number or year is 'camara:<id>'."""
    sigla, numero, ano = (sigla or "").strip().upper(), _int(numero), _int(ano)
    if not sigla or not numero or not ano:
        return "camara:{0}".format(camara_id) if camara_id else None
    key = "{0} {1}/{2}".format(sigla, numero, ano)
    if chamber == "senado" and ano < UNIFIED_FROM:
        key = "SF " + key
    return key


def on_our_ground(areas):
    return any(a not in HIDDEN_AREAS for a in (areas or []))


def years_to_read(conn, today, from_year=None):
    """Which Câmara/Senate years to (re-)read: the current one; the last one
    as well in January and February, while late records still land; and any
    year from `from_year` (default: the legislature's first) that the store
    holds no vote for yet -- the first run's backfill."""
    d = datetime.date.fromisoformat(today)
    first = from_year or LEGISLATURE_START_YEAR
    have = {r[0] for r in conn.execute(
        "SELECT DISTINCT substr(date, 1, 4) FROM br_divisions WHERE chamber='camara'")}
    years = []
    for y in range(first, d.year + 1):
        if y == d.year or (y == d.year - 1 and d.month <= 2) or str(y) not in have:
            years.append(y)
    return years


def _gap(conn, today, detail):
    conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) VALUES (?,?,?)",
                 (today, FEED, detail))


# --- parsing: Câmara ---------------------------------------------------------

def parse_camara_votacoes(obj):
    """votacoes-<year>.json -> the NOMINAL votes only, as division dicts.
    A symbolic vote carries 0/0/0 and no positions anywhere."""
    out = []
    for v in (obj or {}).get("dados") or []:
        yes, no, other = (_int(v.get("votosSim")) or 0, _int(v.get("votosNao")) or 0,
                          _int(v.get("votosOutros")) or 0)
        if yes + no + other == 0:
            continue
        approved = v.get("aprovacao")
        out.append({
            "chamber": "camara", "source_id": v["id"], "date": (v.get("data") or "")[:10] or None,
            "organ": _clean(v.get("siglaOrgao")), "description": _clean(v.get("descricao")),
            "result": {1: "approved", 0: "rejected"}.get(_int(approved)),
            "yes": yes, "no": no, "other": other, "secret": 0,
        })
    return out


def parse_camara_links(obj):
    """votacoesProposicoes-<year>.json -> {idVotacao: [bill dict, ...]}."""
    out = {}
    for r in (obj or {}).get("dados") or []:
        p = r.get("proposicao_") or {}
        if not p.get("id"):
            continue
        b = {"camara_id": _int(p["id"]), "sigla": _clean(p.get("siglaTipo")),
             "numero": _int(p.get("numero")), "ano": _int(p.get("ano")),
             "ementa": _clean(p.get("ementa"))}
        b["bill_key"] = bill_key(b["sigla"], b["numero"], b["ano"], b["camara_id"])
        out.setdefault(r["idVotacao"], [])
        if all(x["camara_id"] != b["camara_id"] for x in out[r["idVotacao"]]):
            out[r["idVotacao"]].append(b)
    return out


def parse_camara_orientations(obj):
    """votacoesOrientacoes-<year>.json -> {idVotacao: [(bloc, orientation)]}.
    Blank orientations (a leader who gave none) are dropped. Bloc names are
    as printed, truncated by the Câmara itself ('Solidaried')."""
    out = {}
    for r in (obj or {}).get("dados") or []:
        bloc, said = _clean(r.get("siglaBancada")), _clean(r.get("orientacao"))
        if bloc and said:
            out.setdefault(r["idVotacao"], []).append((bloc, said))
    return out


def main_bill(linked):
    """The substantive proposição a vote is about, or None."""
    for sigla in SUBSTANTIVE:
        for b in linked:
            if b["sigla"] == sigla and b["bill_key"]:
                return b
    return None


def parse_camara_votos(obj):
    """/votacoes/<id>/votos -> positions. Only deputies who registered appear;
    absence is implicit. A registered deputy with no vote has tipoVoto null."""
    out = []
    for r in (obj or {}).get("dados") or []:
        dep = r.get("deputado_") or {}
        if not dep.get("id"):
            continue
        out.append({"member_key": "camara-{0}".format(dep["id"]), "source_id": str(dep["id"]),
                    "name": _clean(dep.get("nome")), "position": _clean(r.get("tipoVoto")),
                    "party": _clean(dep.get("siglaPartido")), "uf": _clean(dep.get("siglaUf"))})
    return out


def parse_camara_proposicao(obj):
    p = (obj or {}).get("dados") or {}
    status = p.get("statusProposicao") or {}
    b = {"camara_id": _int(p.get("id")), "sigla": _clean(p.get("siglaTipo")),
         "numero": _int(p.get("numero")), "ano": _int(p.get("ano")),
         "ementa": _clean(p.get("ementa")), "ementa_detalhada": _clean(p.get("ementaDetalhada")),
         "keywords": _clean(p.get("keywords")),
         "presented": (p.get("dataApresentacao") or "")[:10] or None,
         "status": _clean(status.get("descricaoSituacao")), "url": _clean(p.get("urlInteiroTeor"))}
    b["bill_key"] = bill_key(b["sigla"], b["numero"], b["ano"], b["camara_id"])
    return b


def parse_camara_deputados(obj):
    return [{"member_key": "camara-{0}".format(d["id"]), "chamber": "camara",
             "source_id": str(d["id"]), "name": _clean(d.get("nome")),
             "party": _clean(d.get("siglaPartido")), "uf": _clean(d.get("siglaUf"))}
            for d in (obj or {}).get("dados") or [] if d.get("id")]


# --- parsing: Senado ---------------------------------------------------------

def parse_senado_votacoes(rows):
    """/votacao -> division dicts with their positions and bill. The totals
    are null in the Senate's own record, so they are counted here."""
    out = []
    for v in rows or []:
        positions = []
        for p in v.get("votos") or []:
            if not p.get("codigoParlamentar"):
                continue
            positions.append({"member_key": "senado-{0}".format(p["codigoParlamentar"]),
                              "source_id": str(p["codigoParlamentar"]),
                              "name": _clean(p.get("nomeParlamentar")),
                              "position": _clean(p.get("siglaVotoParlamentar")),
                              "party": _clean(p.get("siglaPartidoParlamentar")),
                              "uf": _clean(p.get("siglaUFParlamentar"))})
        said = [p["position"] for p in positions]
        bill = {"senado_codigo": _int(v.get("codigoMateria")), "sigla": _clean(v.get("sigla")),
                "numero": _int(v.get("numero")), "ano": _int(v.get("ano")),
                "ementa": _clean(v.get("ementa"))}
        bill["bill_key"] = bill_key(bill["sigla"], bill["numero"], bill["ano"], chamber="senado")
        out.append({
            "chamber": "senado", "source_id": str(v["codigoSessaoVotacao"]),
            "date": (v.get("dataSessao") or "")[:10] or None, "organ": "PLEN",
            "description": _clean(v.get("descricaoVotacao")),
            "result": _clean(v.get("resultadoVotacao")),
            "yes": said.count("Sim"), "no": said.count("Não"),
            "other": len(said) - said.count("Sim") - said.count("Não"),
            "secret": 1 if v.get("votacaoSecreta") == "S" else 0,
            "bill": bill if bill["bill_key"] else None, "positions": positions,
        })
    return out


def parse_senadores(obj):
    rows = (((obj or {}).get("ListaParlamentarEmExercicio") or {}).get("Parlamentares")
            or {}).get("Parlamentar") or []
    if isinstance(rows, dict):
        rows = [rows]
    out = []
    for r in rows:
        ident = r.get("IdentificacaoParlamentar") or {}
        if ident.get("CodigoParlamentar"):
            out.append({"member_key": "senado-{0}".format(ident["CodigoParlamentar"]),
                        "chamber": "senado", "source_id": str(ident["CodigoParlamentar"]),
                        "name": _clean(ident.get("NomeParlamentar")),
                        "party": _clean(ident.get("SiglaPartidoParlamentar")),
                        "uf": _clean(ident.get("UfParlamentar"))})
    return out


# --- storing -----------------------------------------------------------------

def store_bill(conn, b, today, detail=False, log=print):
    """Upsert one proposição. A Câmara ID already stored under another key is
    the renumbering case: the row (and every division citing it) moves to
    the new key, and it is logged."""
    key = b["bill_key"]
    if not key:
        return None
    if b.get("camara_id"):
        row = conn.execute("SELECT bill_key FROM br_bills WHERE camara_id=? AND bill_key<>?",
                           (b["camara_id"], key)).fetchone()
        if row:
            rename_bill(conn, row[0], key, log=log, today=today)
    conn.execute(
        "INSERT INTO br_bills (bill_key, sigla, numero, ano, camara_id, senado_codigo, ementa, "
        "ementa_detalhada, keywords, presented, status, url, detail_fetched, first_seen, last_seen) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(bill_key) DO UPDATE SET "
        "camara_id=COALESCE(excluded.camara_id, br_bills.camara_id), "
        "senado_codigo=COALESCE(excluded.senado_codigo, br_bills.senado_codigo), "
        "ementa=COALESCE(excluded.ementa, br_bills.ementa), "
        "ementa_detalhada=COALESCE(excluded.ementa_detalhada, br_bills.ementa_detalhada), "
        "keywords=COALESCE(excluded.keywords, br_bills.keywords), "
        "presented=COALESCE(excluded.presented, br_bills.presented), "
        "status=COALESCE(excluded.status, br_bills.status), "
        "url=COALESCE(excluded.url, br_bills.url), "
        "detail_fetched=MAX(COALESCE(excluded.detail_fetched, 0), COALESCE(br_bills.detail_fetched, 0)), "
        "last_seen=excluded.last_seen",
        (key, b.get("sigla"), b.get("numero"), b.get("ano"), b.get("camara_id"),
         b.get("senado_codigo"), b.get("ementa"), b.get("ementa_detalhada"), b.get("keywords"),
         b.get("presented"), b.get("status"), b.get("url"), 1 if detail else 0, today, today))
    return key


def rename_bill(conn, old, new, log=print, today=None):
    """Move a renumbered bill to its new key. If the new key already exists
    (the Senate side stored it first), the two rows merge into it. The old
    number is kept in `former_keys` (with the date in `renamed_on`), so the
    edition can show both numbers."""
    log("  renumbered: {0} is now {1} (same Câmara ID)".format(old, new))
    today = today or today_iso()
    row = conn.execute("SELECT former_keys FROM br_bills WHERE bill_key=?", (old,)).fetchone()
    former = br_store.former_keys(row[0] if row else None)
    exists = conn.execute("SELECT former_keys FROM br_bills WHERE bill_key=?", (new,)).fetchone()
    if exists:
        former = br_store.former_keys(exists[0]) + former
        conn.execute(
            "UPDATE br_bills SET camara_id=(SELECT camara_id FROM br_bills WHERE bill_key=?), "
            "keywords=COALESCE(keywords, (SELECT keywords FROM br_bills WHERE bill_key=?)) "
            "WHERE bill_key=?", (old, old, new))
        conn.execute("DELETE FROM br_bills WHERE bill_key=?", (old,))
    else:
        conn.execute("UPDATE br_bills SET bill_key=? WHERE bill_key=?", (new, old))
    former = [k for k in dict.fromkeys(former + [old]) if k != new]
    conn.execute("UPDATE br_bills SET former_keys=?, renamed_on=? WHERE bill_key=?",
                 (br_store.dumps(former), today, new))
    conn.execute("UPDATE br_divisions SET bill_key=? WHERE bill_key=?", (new, old))
    for dkey, linked in conn.execute(
            "SELECT division_key, linked_bills FROM br_divisions WHERE linked_bills LIKE ?",
            ('%"' + old + '"%',)).fetchall():
        keys = [new if k == old else k for k in json.loads(linked or "[]")]
        conn.execute("UPDATE br_divisions SET linked_bills=? WHERE division_key=?",
                     (br_store.dumps(keys), dkey))


def store_division(conn, d, today, bill=None, linked=()):
    key = "{0}-{1}".format(d["chamber"], d["source_id"])
    linked_keys = [b["bill_key"] for b in linked if b.get("bill_key")]
    conn.execute(
        "INSERT INTO br_divisions (division_key, chamber, source_id, date, organ, description, "
        "result, yes, no, other, secret, bill_key, linked_bills, positions_fetched, "
        "first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,0,?,?) "
        "ON CONFLICT(division_key) DO UPDATE SET date=excluded.date, organ=excluded.organ, "
        "description=excluded.description, result=excluded.result, yes=excluded.yes, "
        "no=excluded.no, other=excluded.other, secret=excluded.secret, "
        "bill_key=COALESCE(excluded.bill_key, br_divisions.bill_key), "
        "linked_bills=excluded.linked_bills, last_seen=excluded.last_seen",
        (key, d["chamber"], d["source_id"], d["date"], d["organ"], d["description"],
         d["result"], d["yes"], d["no"], d["other"], d["secret"],
         bill["bill_key"] if bill else None, br_store.dumps(linked_keys), today, today))
    return key


def store_positions(conn, dkey, positions, date, chamber, today):
    for p in positions:
        conn.execute(br_store.MEMBER_UPSERT,
                     (p["member_key"], chamber, p["source_id"], p["name"], p["party"], p["uf"],
                      None, date, today, today))
        conn.execute("INSERT OR REPLACE INTO br_votes (division_key, member_key, position, "
                     "party, uf) VALUES (?,?,?,?,?)",
                     (dkey, p["member_key"], p["position"], p["party"], p["uf"]))
    conn.execute("UPDATE br_divisions SET positions_fetched=1 WHERE division_key=?", (dkey,))


def store_orientations(conn, dkey, rows):
    for bloc, said in rows:
        conn.execute("INSERT OR REPLACE INTO br_orientations (division_key, bloc, orientation) "
                     "VALUES (?,?,?)", (dkey, bloc, said))


# --- pulling -----------------------------------------------------------------

def pull_camara_year(conn, client, today, year, log=print):
    """One year's vote list, links and orientations from the bulk files.
    Every nominal vote is (re)stamped; positions come later. Returns
    (nominal, gaps)."""
    files = {}
    for name in ("votacoes", "votacoesProposicoes", "votacoesOrientacoes"):
        try:
            files[name] = client.get_json(CAMARA_BULK.format(name, year), FEED,
                                          "camara-{0}-{1}".format(name, year))
        except (FetchError, ValueError) as exc:
            _gap(conn, today, "camara {0} {1}: {2}".format(name, year, exc))
            log("  [gap] camara {0} {1}: {2}".format(name, year, str(exc)[:80]))
            if name == "votacoes":
                return 0, 1
            files[name] = None
    divisions = parse_camara_votacoes(files["votacoes"])
    links = parse_camara_links(files.get("votacoesProposicoes"))
    orient = parse_camara_orientations(files.get("votacoesOrientacoes"))
    for d in divisions:
        linked = links.get(d["source_id"], [])
        for b in linked:
            store_bill(conn, b, today, log=log)
        dkey = store_division(conn, d, today, bill=main_bill(linked), linked=linked)
        store_orientations(conn, dkey, orient.get(d["source_id"], []))
    conn.commit()
    return len(divisions), 1 if files.get("votacoesProposicoes") is None or \
        files.get("votacoesOrientacoes") is None else 0


def pull_camara_positions(conn, client, today, log=print, limit=None, budget=None):
    """Every Câmara division still without its positions, newest first.
    Returns (fetched, gaps). A run cut short resumes here next time."""
    pending = conn.execute(
        "SELECT division_key, source_id, date FROM br_divisions WHERE chamber='camara' "
        "AND COALESCE(positions_fetched, 0)=0 ORDER BY date DESC, division_key").fetchall()
    done = gaps = 0
    for dkey, sid, date in pending:
        if limit is not None and done >= limit:
            log("  fetch cap ({0}) reached; {1} vote(s) left for the next run "
                "-- disclosed, not silent".format(limit, len(pending) - done))
            break
        if budget is not None and budget.exhausted():
            log(budget.disclose("Câmara vote positions", done))
            break
        try:
            raw = client.get_json("{0}/votacoes/{1}/votos".format(CAMARA_API, sid), FEED,
                                  "camara-votos-" + sid, archive=False)
        except (FetchError, ValueError) as exc:
            _gap(conn, today, "camara votos {0}: {1}".format(sid, exc))
            log("  [gap] camara votos {0}: {1}".format(sid, str(exc)[:80]))
            gaps += 1
            continue
        positions = parse_camara_votos(raw)
        if not positions:
            # A vote the year file counts as nominal but the API holds no
            # position for: a hole in the source, said, and retried next run.
            _gap(conn, today, "camara votos {0}: no positions returned".format(sid))
            log("  [gap] camara votos {0}: no positions returned".format(sid))
            gaps += 1
            continue
        store_positions(conn, dkey, positions, date, "camara", today)
        conn.commit()
        done += 1
    return done, gaps


def pull_bill_details(conn, client, today, log=print, budget=None):
    """The Câmara record of every bill a division is about, read once, for
    its keywords, detailed ementa and status. Returns (read, gaps)."""
    pending = conn.execute(
        "SELECT DISTINCT b.bill_key, b.camara_id FROM br_bills b JOIN br_divisions d "
        "ON d.bill_key=b.bill_key WHERE b.camara_id IS NOT NULL "
        "AND COALESCE(b.detail_fetched, 0)=0 ORDER BY b.bill_key").fetchall()
    done = gaps = 0
    for key, cid in pending:
        if budget is not None and budget.exhausted():
            log(budget.disclose("Câmara bill records", done))
            break
        try:
            raw = client.get_json("{0}/proposicoes/{1}".format(CAMARA_API, cid), FEED,
                                  "camara-proposicao-{0}".format(cid))
        except (FetchError, ValueError) as exc:
            _gap(conn, today, "camara proposicao {0} ({1}): {2}".format(cid, key, exc))
            log("  [gap] camara proposicao {0}: {1}".format(cid, str(exc)[:80]))
            gaps += 1
            continue
        b = parse_camara_proposicao(raw)
        if b["bill_key"]:
            store_bill(conn, b, today, detail=True, log=log)
            conn.commit()
            done += 1
    return done, gaps


def pull_senado_year(conn, client, today, year, log=print):
    """Every nominal Senate vote of one year, positions included, in one
    call (the API refuses a window over a year). Returns (stored, gaps)."""
    end = min(datetime.date(year, 12, 31), datetime.date.fromisoformat(today))
    url = "{0}/votacao?dataInicio={1}-01-01&dataFim={2}".format(SENADO, year, end.isoformat())
    try:
        rows = client.get_json(url, FEED, "senado-votacao-{0}".format(year))
    except (FetchError, ValueError) as exc:
        _gap(conn, today, "senado votacao {0}: {1}".format(year, exc))
        log("  [gap] senado votacao {0}: {1}".format(year, str(exc)[:80]))
        return 0, 1
    divisions = parse_senado_votacoes(rows if isinstance(rows, list) else [])
    for d in divisions:
        if d["bill"]:
            store_bill(conn, d["bill"], today, log=log)
        dkey = store_division(conn, d, today, bill=d["bill"],
                              linked=[d["bill"]] if d["bill"] else [])
        store_positions(conn, dkey, d["positions"], d["date"], "senado", today)
    conn.commit()
    return len(divisions), 0


def pull_members(conn, client, today, log=print):
    """The deputies and senators in office. Returns (count, gaps)."""
    rows, gaps = [], 0
    for url, slug, parse in (
            ("{0}/deputados?itens=1000".format(CAMARA_API), "camara-deputados", parse_camara_deputados),
            ("{0}/senador/lista/atual.json".format(SENADO), "senado-senadores", parse_senadores)):
        try:
            got = parse(client.get_json(url, FEED, slug))
        except (FetchError, ValueError) as exc:
            _gap(conn, today, "{0}: {1}".format(slug, exc))
            log("  [gap] {0}: {1}".format(slug, str(exc)[:80]))
            gaps += 1
            continue
        chamber = got[0]["chamber"] if got else None
        if chamber:
            conn.execute("UPDATE br_members SET in_office=0 WHERE chamber=?", (chamber,))
        rows += got
    for m in rows:
        conn.execute(br_store.MEMBER_UPSERT,
                     (m["member_key"], m["chamber"], m["source_id"], m["name"], m["party"],
                      m["uf"], 1, today, today, today))
        # The chamber's current list is the authority on today's name.
        conn.execute("UPDATE br_members SET name=? WHERE member_key=?", (m["name"], m["member_key"]))
    conn.commit()
    return len(rows), gaps


# --- classifying (offline) ---------------------------------------------------

def load_taxonomy(path=TAXONOMY_PT):
    """The Portuguese taxonomy, once it exists; None until then."""
    return filt.load_taxonomy(path, country=TAXONOMY_COUNTRY) if os.path.exists(path) else None


def empty_watchlist():
    """The Brazil watchlist is applied by KEY (br_store.add_watch_areas), so
    the filter itself gets no title entities."""
    return filt.Watchlist(entities=[], bill_titles=[], act_shorts=[])


def _match(tax, *fields):
    if tax is None:
        return filt.FilterResult()
    return filt.filter_item(tax, empty_watchlist(), *fields)


def classify_bill(tax, key, ementa, detalhada, keywords, watch_path=None):
    res = _match(tax, ementa or "", detalhada or "", keywords or "")
    return br_store.add_watch_areas(res, key, watch_path)


def reclassify(conn, tax=None, log=print, watch_path=None):
    """Re-derive every bill's areas, then every division's: its own text plus
    the areas of every proposição it is linked to. Run at the end of every
    pull, and by hand after a taxonomy or watchlist change."""
    changed_b = changed_d = 0
    bill_areas = {}
    for key, ementa, det, kw, areas in conn.execute(
            "SELECT bill_key, ementa, ementa_detalhada, keywords, areas FROM br_bills").fetchall():
        res = classify_bill(tax, key, ementa, det, kw, watch_path)
        new = br_store.dumps(res.issue_areas)
        bill_areas[key] = res.issue_areas or []
        changed_b += new != (areas or "[]")
        conn.execute("UPDATE br_bills SET areas=?, matched_terms=?, tier=? WHERE bill_key=?",
                     (new, br_store.dumps((res.matched_terms or []) + (res.watchlist_hits or [])),
                      res.tier, key))
    for dkey, desc, bkey, linked, areas in conn.execute(
            "SELECT division_key, description, bill_key, linked_bills, areas "
            "FROM br_divisions").fetchall():
        own = _match(tax, desc or "")
        lent = set()
        for k in set(json.loads(linked or "[]")) | ({bkey} if bkey else set()):
            lent |= set(bill_areas.get(k, []))
        combined = sorted(set(own.issue_areas or []) | lent)
        new = br_store.dumps(combined)
        changed_d += new != (areas or "[]")
        conn.execute("UPDATE br_divisions SET own_areas=?, areas=?, matched_terms=?, tier=? "
                     "WHERE division_key=?",
                     (br_store.dumps(own.issue_areas), new, br_store.dumps(own.matched_terms),
                      own.tier if own.tier is not None else (2 if combined else None), dkey))
    conn.commit()
    log("br-rollcalls: classified ({0}); {1} bill(s) and {2} division(s) changed area".format(
        "taxonomy-pt + watchlist-br" if tax is not None else "watchlist-br only: no taxonomy-pt yet",
        changed_b, changed_d))
    return changed_b, changed_d


def summary(conn, log=print):
    n = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
    ours = lambda t: sum(on_our_ground(json.loads(a or "[]"))  # noqa: E731
                         for (a,) in conn.execute("SELECT areas FROM {0}".format(t)))
    log("  store: {0} Câmara and {1} Senate nominal vote(s), {2} on our ground; "
        "{3} still without positions; {4} proposição(ões), {5} on our ground; "
        "{6} member(s), {7} position(s), {8} orientation(s)".format(
            n("SELECT COUNT(*) FROM br_divisions WHERE chamber='camara'"),
            n("SELECT COUNT(*) FROM br_divisions WHERE chamber='senado'"), ours("br_divisions"),
            n("SELECT COUNT(*) FROM br_divisions WHERE COALESCE(positions_fetched,0)=0"),
            n("SELECT COUNT(*) FROM br_bills"), ours("br_bills"),
            n("SELECT COUNT(*) FROM br_members"), n("SELECT COUNT(*) FROM br_votes"),
            n("SELECT COUNT(*) FROM br_orientations")))


def run(conn, client, today, years, budget=None, limit=None, members=True, camara=True,
        senado=True, tax=None, log=print):
    """One full pull. Returns the number of gaps."""
    gaps = 0
    if members:
        count, g = pull_members(conn, client, today, log=log)
        gaps += g
        log("br-rollcalls: {0} member(s) in office".format(count))
    for year in years:
        if camara:
            nominal, g = pull_camara_year(conn, client, today, year, log=log)
            gaps += g
            log("br-rollcalls: Câmara {0}: {1} nominal vote(s) listed".format(year, nominal))
        if senado:
            stored, g = pull_senado_year(conn, client, today, year, log=log)
            gaps += g
            log("br-rollcalls: Senado {0}: {1} nominal vote(s) with positions".format(year, stored))
    if camara:
        done, g = pull_camara_positions(conn, client, today, log=log, limit=limit, budget=budget)
        gaps += g
        log("br-rollcalls: Câmara positions fetched for {0} vote(s)".format(done))
        done, g = pull_bill_details(conn, client, today, log=log, budget=budget)
        gaps += g
        log("br-rollcalls: {0} Câmara bill record(s) read".format(done))
    reclassify(conn, tax=tax, log=log)
    return gaps


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--from-year", type=int,
                    help="backfill from this year (default: the legislature's first, {0})".format(
                        LEGISLATURE_START_YEAR))
    ap.add_argument("--no-camara", action="store_true")
    ap.add_argument("--no-senado", action="store_true")
    ap.add_argument("--no-members", action="store_true")
    ap.add_argument("--reclassify", action="store_true",
                    help="re-derive areas for stored bills and divisions, offline")
    ap.add_argument("--budget-seconds", type=float, default=BUDGET_S)
    ap.add_argument("--limit", type=int, help="stop after this many Câmara position fetches")
    ap.add_argument("--dry-run", action="store_true",
                    help="count this year's nominal votes in both houses, store nothing")
    args = ap.parse_args()
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    today = today_iso()
    tax = load_taxonomy()
    if args.dry_run:
        year = datetime.date.fromisoformat(today).year
        cam = parse_camara_votacoes(client.get_json(CAMARA_BULK.format("votacoes", year), FEED,
                                                    "dry", archive=False))
        sen = client.get_json("{0}/votacao?dataInicio={1}-01-01&dataFim={2}".format(
            SENADO, year, today), FEED, "dry", archive=False)
        print("br-rollcalls: {0}: Câmara {1} nominal vote(s), Senado {2}".format(
            year, len(cam), len(sen)))
        return 0
    conn = db.init_db(db.connect(args.db))
    if args.reclassify:
        reclassify(conn, tax=tax)
        summary(conn)
        conn.close()
        return 0
    years = years_to_read(conn, today, args.from_year)
    print("br-rollcalls: reading {0}".format(", ".join(str(y) for y in years)))
    gaps = run(conn, client, today, years, budget=drain.Budget(args.budget_seconds),
               limit=args.limit, members=not args.no_members, camara=not args.no_camara,
               senado=not args.no_senado, tax=tax)
    summary(conn)
    conn.close()
    # 3 = stored what it could and recorded gaps (jobs/br-weekly.sh publishes
    # it anyway); anything else non-zero is a crash.
    return 3 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
