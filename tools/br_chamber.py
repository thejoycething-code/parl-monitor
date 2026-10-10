#!/usr/bin/env python3
"""Brazil: the Câmara's requests for information (requerimentos de informação).

    python3 tools/br_chamber.py                      # the last three weeks
    python3 tools/br_chamber.py --since 2026-09-01
    python3 tools/br_chamber.py --dry-run
    python3 tools/br_chamber.py --reclassify

Parity layer 5 (docs/country-parity-handover.md), 10 October 2026. From the
Câmara's open-data API (dadosabertos.camara.leg.br/api/v2, keyless; the
source tools/br_rollcalls.py reads); the rest is src/chamber_store.py.

QUESTIONS. A deputy's written question to a minister is a Requerimento de
Informação (siglaTipo RIC; the Constitution, art. 50 para. 2, gives the
minister thirty days). Listed a hundred to a page by presentation date
(about 17 between 1 and 9 October 2026, an election month; several hundred
in a sitting month), classified on the ementa alone ("Requer informações ao
Ministro da Saúde acerca de ..."), which names the minister. For a request
on our ground the author is asked for (/proposicoes/<id>/autores, then the
deputy's party): two requests per stored item, none for the rest. Whether it
was answered is not read: the register's situation field says where the
request is, not what the minister said.

SPEECHES ARE NOT COLLECTED (yet). The API gives discursos only per deputy
(/deputados/<id>/discursos): 513 requests a week at about five seconds each
from the laptop (measured 10 October 2026), 40 minutes against a weekly job
that already spends up to 45 on votes. A Mini-only job of its own would do
it; that is a scheduling decision for Chris, not built here.
"""

from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import chamber_store as cs  # noqa: E402
from src.http import FetchError  # noqa: E402

CC = "br"
FEED = "br-chamber"
API = "https://dadosabertos.camara.leg.br/api/v2"
PAGE = 100
MAX_PAGES = 30
PAGE_URL = "https://www.camara.leg.br/proposicoesWeb/fichadetramitacao?idProposicao={0}"


ADDRESSEE = re.compile(
    r"(?:Ministr[oa]|Minist[ée]rio|Presidente|Secret[áa]ri[oa]|Comandante|Controlador|"
    r"Advogad[oa]-Geral)\b.*?(?=,|;|\.\s|\s+(?:acerca|sobre|a respeito|em relação|referente|"
    r"quanto|para|no sentido|informações)\b|$)")
HONORIFIC = re.compile(r"^(?:(?:Excelent[íi]ssim[oa]|Exm[oa]\.?|Senhor[a]?|Sr[a]?\.?)\s+)+")


def addressee(ementa):
    """'Ministro de Estado da Saúde' from 'Requer informações ao Ministro de
    Estado da Saúde, Sr. ..., acerca de ...' (or 'ao Ministério da ...'), or None."""
    m = ADDRESSEE.search(ementa or "")
    if not m:
        return None
    return HONORIFIC.sub("", " ".join(m.group(0).split()))[:100] or None


def author(run, pid):
    """('Name', 'PARTY') of a request's first signatory, or (None, None)."""
    try:
        got = run.client.get_json("{0}/proposicoes/{1}/autores".format(API, pid), FEED,
                                  "autores-{0}".format(pid)).get("dados") or []
    except FetchError:
        return None, None
    got = sorted(got, key=lambda a: a.get("ordemAssinatura") or 99)
    if not got:
        return None, None
    name, uri = got[0].get("nome"), got[0].get("uri") or ""
    party = None
    if "/deputados/" in uri:
        try:
            dep = run.client.get_json(uri, FEED, "deputado-{0}".format(uri.rsplit("/", 1)[-1]))
            party = ((dep.get("dados") or {}).get("ultimoStatus") or {}).get("siglaPartido")
        except FetchError:
            pass
    if len(got) > 1:
        name = "{0} and {1} other(s)".format(name, len(got) - 1)
    return name, party


def questions(run):
    until = run.today
    url = ("{0}/proposicoes?siglaTipo=RIC&dataApresentacaoInicio={1}&dataApresentacaoFim={2}"
           "&itens={3}&ordem=DESC&ordenarPor=id".format(API, run.since, until, PAGE))
    listed, page = [], 1
    while page <= MAX_PAGES:
        try:
            got = run.client.get_json(url + "&pagina={0}".format(page), FEED,
                                      "ric-{0}-p{1}".format(run.since, page)).get("dados") or []
        except FetchError as exc:
            run.gap("requests for information since {0}, page {1}: {2}".format(
                run.since, page, str(exc)[:100]))
            return
        listed += got
        if len(got) < PAGE:
            break
        page += 1
    matched = 0
    for p in listed:
        ementa = p.get("ementa") or ""
        m = cs.classify_question(run.taxes, ementa)
        if not m:
            continue
        matched += 1
        known = run.conn.execute("SELECT asker, party FROM br_questions WHERE question_id=?",
                                 ("RIC {0}/{1}".format(p.get("numero"), p.get("ano")),)).fetchone()
        if known and known[0]:
            name, party = known
        elif run.out_of_time("request authors", matched):
            name, party = None, None
        else:
            name, party = author(run, p["id"])
        run.question({"question_id": "RIC {0}/{1}".format(p.get("numero"), p.get("ano")),
                      "kind": "request", "date": (p.get("dataApresentacao") or "")[:10],
                      "title": ementa, "text": None, "asker": name, "party": party,
                      "addressee": addressee(ementa), "answered": "untracked",
                      "url": PAGE_URL.format(p["id"])}, m)
    run.read("ric:{0}:{1}".format(run.since, run.today), "questions", run.today, None,
             len(listed), matched, 0)
    run.log("  [ric] {0} request(s) for information presented since {1}, {2} on our ground"
            .format(len(listed), run.since, matched))


if __name__ == "__main__":
    sys.exit(cs.main(CC, {"questions": questions}, doc=__doc__))
