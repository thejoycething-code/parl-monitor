"""Paraná: the Assembleia Legislativa's own open-data API (source `alep`),
the repository's ONE plain-HTTP source (13 October 2026).

Chris, 13 October 2026: "Allow the narrow exception". ALEP documents an
open-data API (transparencia.assembleia.pr.leg.br/servicos/dados-abertos)
whose base URL is plain HTTP; its https port presents a self-signed
certificate and answers 403, and the https bill search demands a reCAPTCHA
token (never bypassed). The exception is recorded in exactly one place,
src/http.PLAIN_HTTP_EXCEPTIONS, and tests/test_db_state.PlainHttpTests fails
on any other http:// URL. The conditions, all kept here:

  * GET only, the honest User-Agent, no credentials. The API's bill LIST is a
    POST (/proposicao/filtrar), so it is NOT used: bills are read one by one
    with the documented GET /proposicao/{código}. Códigos are one sequence
    for every kind of document (ofícios, requerimentos, indicações ...),
    rising with time, with small holes; the reader walks up from the last
    código seen, stops after ALEP_MISS_STOP misses in a row, and keeps PL,
    PLC, PDL and PEC. A numbered-later draft ("AGUARDANDO RECEBIMENTO",
    "ELABORAÇÃO") is asked again on later runs; so are holes below the top
    (a few times), and a few bills on our ground for their stage.
  * Every item it gives says "(via ALEP open data, unencrypted)" in the
    edition (src/brs_store.VIA).
  * A law ALEP names for a bill (normasLegais) is CROSS-CHECKED against the
    Casa Civil's https law list already read (source `pr`, stored before this
    source): the same number with a different title, or the same title under
    a different number, is a gap line, and the HTTP copy is not trusted for
    it (the bill's status keeps ALEP's words, marked as ALEP's).
  * robots.txt is read every run (over the same scheme, the exception's
    `robots` URL); the run's budget bounds the walk, plus a request cap.

WHAT IT GIVES: bills (number, ementa, author as printed, received date),
their stage (the latest substantive tramitação step and where), plenary
results ("1º TURNO - APROVADO": result only, the API prints no tally) and
committee decisions ("APROVADO O PARECER FAVORÁVEL"), as brs_votes rows with
no tallies. MEMBERS' VOTES: the API has none (ALEP's "Controle de votações"
is a reCAPTCHA-gated search, never bypassed).

Called from tools/br_states.py (ALT_FETCHERS["alep"]) with that module, so the
shared Result, classifier and budget are the same objects.
"""

from __future__ import annotations

import datetime
import difflib
import json
import re

from src import brs_store
from src.http import PLAIN_HTTP_EXCEPTIONS, FetchError, plain_http_allowed

ALEP_API = PLAIN_HTTP_EXCEPTIONS["alep"]["prefix"]      # the one plain-HTTP prefix
ALEP_HOST = "webservices.assembleia.pr.leg.br"
ALEP_BILL_KINDS = ("PL", "PLC", "PDL", "PEC")
ALEP_PAGE = "https://consultas.assembleia.pr.leg.br/#/pesquisa-legislativa"
# The highest código on 13 October 2026 was 131522 (PL 795/2026 of 6 October
# is 131469); a first read starts a little below it.
ALEP_SEED_CODE = 131400
ALEP_REQUEST_CAP = 200      # GETs a run, every kind together
ALEP_MISS_STOP = 40         # misses in a row that mean "the top" (holes of 10 seen)
ALEP_HOLE_TRIES = 3         # runs a hole below the top is asked again
ALEP_HOLE_CAP = 30
ALEP_PENDING_DAYS = 60      # an unnumbered draft is asked again for two months
ALEP_PENDING_CAP = 30
ALEP_RECHECK_CAP = 10       # bills on our ground re-read for their stage, a run
ALEP_THROTTLE = 1.0

# siglaTipoProposicao -> (kind, name); everything else (REQ, IND, OFC, RP,
# VET, emendas ...) is not a bill.
ALEP_TYPES = {"PRO": ("PL", "Projeto de Lei"), "PLC": ("PLC", "Projeto de Lei Complementar"),
              "PDL": ("PDL", "Projeto de Decreto Legislativo"),
              "PEC": ("PEC", "Proposta de Emenda à Constituição")}
DRAFT = re.compile(r"AGUARDANDO RECEBIMENTO|ELABORA", re.I)
DROPPED = re.compile(r"CANCELAD", re.I)
# Tramitação actions that are handling, not a stage.
ROUTINE = re.compile(r"^(INFORMA[ÇC][ÃA]O|DESPACHO|ENCAMINHADO|ELABORA[ÇC][ÃA]O DA [ÍI]NTEGRA|"
                     r"INCLUS[ÃA]O DE DOCUMENTO|OF[ÍI]CIO|AUTUADO|RECEBIDO|JUNTADA|"
                     r"DECLARA[ÇC][ÃA]O DO AUTOR|ARQUIVAD)", re.I)
PLENARY = re.compile(r"(TURNO|REDA[ÇC][ÃA]O FINAL|VOTA[ÇC][ÃA]O)[^|]*?\b(APROVAD|REJEITAD)", re.I)
COMMITTEE = re.compile(r"\b(APROVAD|REJEITAD)[OA]S? O PARECER", re.I)
# descricaoTipoNormaLegal, folded ('Emenda Constitucional - EC' -> 'emenda
# constitucional ec'); resolutions and decretos legislativos are not laws.
NORMA_KINDS = {"lei": ("Lei", "Lei"), "lei complementar": ("LC", "Lei Complementar"),
               "emenda constitucional": ("EC", "Emenda Constitucional"),
               "emenda constitucional ec": ("EC", "Emenda Constitucional")}
TITLE_MISMATCH = 0.5        # below: same number, different law
TITLE_SAME = 0.95           # character match above: the same law under another number


def _date(text):
    return (text or "")[:10] or None


def _plain(text):
    import unicodedata
    t = unicodedata.normalize("NFKD", text or "")
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


STOP = frozenset("a o e as os de da do das dos em no na nos nas ao aos que para por com se "
                 "um uma sua seu e ou the estado parana municipio lei".split())


def _words(text):
    return {w for w in _plain(text).split() if len(w) > 2 and w not in STOP}


def similarity(a, b):
    """0..1, accents, case and punctuation folded: the better of the
    character match and the share of the shorter text's words found in the
    other (the Casa Civil redrafts ALEP's capitals into its own súmula: 'O
    EVENTO FESTA DO DIVINO ... A SER REALIZADO' vs 'a Festa do Divino ...,
    realizada', 0.56 by characters, 0.8 by words)."""
    pa, pb = _plain(a), _plain(b)
    if not pa or not pb:
        return 0.0
    chars = difflib.SequenceMatcher(None, pa, pb).ratio()
    wa, wb = _words(a), _words(b)
    words = len(wa & wb) / min(len(wa), len(wb)) if wa and wb else 0.0
    return max(chars, words)


def same_text(a, b):
    """Near-identical wording (a number check needs more than shared words:
    utilidade-pública laws differ only in the association's name)."""
    pa, pb = _plain(a), _plain(b)
    return bool(pa and pb) and difflib.SequenceMatcher(None, pa, pb).ratio() >= TITLE_SAME


def _actions(v):
    """Every tramitação action, in order, each with where it happened."""
    out = []
    for t in v.get("tramites") or []:
        for a in t.get("acoes") or []:
            out.append(dict(a, local=(t.get("local") or "").strip()))
    out.sort(key=lambda a: (a.get("data") or "", a.get("ordem") or 0))
    return out


def norma_of(n):
    """One normasLegais entry -> (kind, kind_name, number, year, ementa) or None."""
    k = NORMA_KINDS.get(_plain(n.get("descricaoTipoNormaLegal")))
    if not k or n.get("numero") is None or not n.get("ano"):
        return None
    return k[0], k[1], int(n["numero"]), int(n["ano"]), (n.get("ementa") or "").strip() or None


def parse_proposicao(v, clean=lambda t: t):
    """A GET /proposicao/{código} answer's `valor` -> dict with the bill
    (or None when it is not a numbered bill), its votes, its laws, and
    whether it is a draft to ask again."""
    out = {"bill": None, "votes": [], "normas": [], "draft": False}
    t = ALEP_TYPES.get((v.get("siglaTipoProposicao") or "").strip())
    if not t:
        return out
    status_word = (v.get("status") or "").strip()
    if DROPPED.search(status_word):
        return out
    if v.get("numero") is None or not v.get("ano"):
        out["draft"] = bool(DRAFT.search(status_word)) or not status_word
        return out
    number, year = int(v["numero"]), int(v["ano"])
    key = brs_store.bill_key("pr", t[0], number, year)
    acts = _actions(v)
    stage = [a for a in acts if a.get("descricao") and not ROUTINE.search(a["descricao"].strip())]
    status, when = None, None
    if stage:
        last = stage[-1]
        status = "{0} ({1})".format(clean(last["descricao"].strip()), clean(last["local"])) \
            if last["local"] else clean(last["descricao"].strip())
        when = _date(last.get("data"))
    elif v.get("localAtual"):
        status = "Em {0}".format(clean(v["localAtual"].strip()))
    for n in v.get("normasLegais") or []:
        got = norma_of(n)
        if got:
            out["normas"].append(got)
    if out["normas"]:
        # The law ALEP says the bill became: ALEP's word, marked as such
        # (crosscheck() compares it with the Casa Civil's https list).
        k, _kn, num, yr, _e = out["normas"][0]
        status = "Became {0} {1}/{2} (per ALEP)".format(k, num, yr)
    elif status_word.upper().startswith("ARQUIV"):
        status = "ARQUIVADA"
        when = _date(acts[-1].get("data")) if acts else when
    local = (v.get("localAtual") or "").strip()
    out["bill"] = {
        "bill_key": key, "uf": "pr", "source": "alep", "source_id": str(v.get("codigo")),
        "kind": t[0], "kind_name": t[1], "number": number, "year": year,
        "title": clean(v.get("ementa")), "authors": clean(v.get("autor")),
        "presented": _date(v.get("dataRecebimento") or v.get("dataEntrada")),
        "status": status, "status_date": when,
        "committees": clean(local) if "COMISS" in local.upper() else None,
        "url": ALEP_PAGE}
    for a in acts:
        d = (a.get("descricao") or "").strip()
        obs = (a.get("observacao") or "").strip()
        if PLENARY.search(d):
            m = PLENARY.search(d)
            body, desc = "plenary", clean(d)
            result = "Aprovado" if m.group(2).upper().startswith("APROVAD") else "Rejeitado"
        elif COMMITTEE.search(obs) and "COMISS" in a["local"].upper():
            m = COMMITTEE.search(obs)
            body, desc = clean(a["local"]), clean(obs)
            result = "Aprovado" if m.group(1).upper().startswith("APROVAD") else "Rejeitado"
        else:
            continue
        out["votes"].append({"vote_key": "pr/alep-{0}".format(a.get("codigo")), "uf": "pr",
                             "bill_key": key, "date": _date(a.get("data")), "body": body,
                             "description": desc, "result": result,
                             "yes": None, "no": None, "abstain": None})
    return out


def crosscheck(conn, normas):
    """Gap lines for laws ALEP names that the Casa Civil's https list (source
    'pr', already stored) contradicts. `normas`: [(bill_key, kind, number,
    year, ementa)]. A law the Casa Civil has not listed is not a mismatch."""
    gaps = []
    for bill, kind, number, year, ementa in normas:
        key = brs_store.bill_key("pr", kind, number, year)
        row = conn.execute("SELECT title FROM brs_bills WHERE source='pr' AND bill_key=?",
                           (key,)).fetchone()
        if row is not None:
            if ementa and row[0] and similarity(ementa, row[0]) < TITLE_MISMATCH:
                gaps.append("ALEP open data (unencrypted) cross-check: {0} is {1} by ALEP, but the "
                            "Casa Civil (https) gives {1} as \"{2}\", not \"{3}\"; ALEP's copy not "
                            "trusted".format(bill, key.split("/", 1)[1], row[0][:90], ementa[:90]))
            continue
        if not ementa:
            continue
        for other, title in conn.execute(
                "SELECT bill_key, title FROM brs_bills WHERE source='pr' AND kind=? AND year=?",
                (kind, year)):
            if title and same_text(ementa, title):
                gaps.append("ALEP open data (unencrypted) cross-check: {0} became {1} by ALEP, but "
                            "the Casa Civil (https) lists that law as {2}; ALEP's number not "
                            "trusted".format(bill, key.split("/", 1)[1], other.split("/", 1)[1]))
                break
    return gaps


def fetch_alep(client, ctx, bs):
    """The reader. `bs` is tools/br_states (Result, classified, decode ...)."""
    res = bs.Result("alep", "pr")
    tax, budget, known = ctx["tax"], ctx["budget"], ctx["known"]
    meta = dict(ctx["meta"].get("alep") or {})
    today = ctx["today"]
    start = int(meta.get("next") or ALEP_SEED_CODE)
    holes = {int(k): int(n) for k, n in (meta.get("holes") or {}).items()}
    pending = {int(k): d for k, d in (meta.get("pending") or {}).items()}
    asked = [0]
    normas = []
    listed = {}

    def get(code):
        url = "{0}proposicao/{1}".format(ALEP_API, int(code))
        # Belt and braces: the reader never builds a URL outside the exception.
        if not plain_http_allowed(url, "GET"):
            raise FetchError(url, bs.FEED, "alep", 0, "outside the plain-HTTP exception")
        asked[0] += 1
        data = json.loads(bs.decode(client.get_bytes(url, bs.FEED, "alep-{0}".format(code),
                                                     archive=False)))
        return data.get("valor") if isinstance(data, dict) else None

    def take(code, v):
        got = parse_proposicao(v, bs._clean)
        if got["draft"]:
            pending.setdefault(code, today)
            return
        pending.pop(code, None)
        b = got["bill"]
        if not b:
            return
        listed[b["bill_key"]] = b
        res.votes.extend(got["votes"])
        normas.extend((b["bill_key"], n[0], n[2], n[3], n[4]) for n in got["normas"])

    def room():
        return asked[0] < ALEP_REQUEST_CAP and not budget.exhausted()

    last_hit, code, misses, missing = start - 1, start, 0, []
    try:
        # 1. the new códigos, walking up from the last one seen
        while room():
            v = get(code)
            if v:
                take(code, v)
                last_hit, misses = code, 0
            else:
                missing.append(code)
                misses += 1
                if misses >= ALEP_MISS_STOP:
                    break
            code += 1
        walked_to = code
        # 2. holes below the top, drafts, and bills on our ground for their stage
        for h in sorted(holes)[-ALEP_HOLE_CAP:]:
            if not room():
                break
            v = get(h)
            if v:
                take(h, v)
                holes.pop(h)
            else:
                holes[h] += 1
        for p in sorted(pending)[:ALEP_PENDING_CAP]:
            if not room():
                break
            first = pending[p]
            try:
                old = (datetime.date.fromisoformat(today) - datetime.date.fromisoformat(first)).days
            except ValueError:
                old = 0
            if old > ALEP_PENDING_DAYS:
                pending.pop(p)
                continue
            v = get(p)
            if v:
                take(p, v)
        ours = sorted((sid, key) for sid, key in known["source_ids"].get("pr", {}).items()
                      if key not in listed and sid.isdigit()
                      and key.split("/", 1)[1].split()[0] in ALEP_BILL_KINDS
                      and bs.on_our_ground(json.loads(known["bills"].get(key, (None, None))[1] or "[]")))
        turn = int(meta.get("recheck_from") or 0)
        batch = [o for o in ours if int(o[0]) > turn][:ALEP_RECHECK_CAP] or ours[:ALEP_RECHECK_CAP]
        for sid, _key in batch:
            if not room():
                break
            v = get(int(sid))
            if v:
                take(int(sid), v)
            meta["recheck_from"] = int(sid)
    except (FetchError, ValueError) as e:
        if not listed and asked[0] <= 1:
            return bs._fail(res, "ALEP open data (Paraná, unencrypted)", e)
        res.gap("ALEP open data: " + bs.gap_text(e))
        walked_to = code
    if asked[0] >= ALEP_REQUEST_CAP or budget.exhausted():
        res.gap("ALEP open data: request cap or time budget reached at código {0}; "
                "the next run resumes".format(walked_to))
    # The top: códigos after the last one seen are asked again next run.
    nxt = walked_to if misses < ALEP_MISS_STOP else last_hit + 1
    for h in missing:
        if h < last_hit:
            holes.setdefault(h, 0)
    holes = {h: n for h, n in holes.items() if n < ALEP_HOLE_TRIES}
    if len(holes) > ALEP_HOLE_CAP:
        holes = dict(sorted(holes.items())[-ALEP_HOLE_CAP:])
    res.meta = {"next": max(nxt, start), "holes": {str(k): n for k, n in holes.items()},
                "pending": {str(k): d for k, d in pending.items()},
                "recheck_from": meta.get("recheck_from"), "asked": asked[0]}
    for b in listed.values():
        b = bs.classified(tax, b, ctx.get("watch_path"))
        res.bills.append(b)
        bs._through(res, b)
    if normas:
        res.after_store = lambda conn: crosscheck(conn, normas)
    return res
