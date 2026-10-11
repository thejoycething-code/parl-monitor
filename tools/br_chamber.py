#!/usr/bin/env python3
"""Brazil: the Câmara's requests for information and plenary speeches.

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

SPEECHES (11 October 2026, branch gaps-speeches), within a small budget.
The open-data API gives discursos only per deputy (513 requests a week), so
the step reads the Câmara's own search by date instead: the SitCamaraWS
service ListarDiscursosPlenario (www.camara.leg.br/SitCamaraWS/
SessoesReunioes.asmx, keyless; robots.txt disallows none of /SitCamaraWS or
/internet/sitaqweb, measured 11 October 2026) lists every plenary speech in
a date range in ONE request (August 2026: 239 speeches, 300 KB): session,
phase (Ordem do Dia, Breves Comunicações, ...), speaker with party and
state at the speech, the Câmara's own index terms (txtIndexacao) and its
summary (sumário). The index and summary are only a PRE-FILTER: a speech
whose summary or index is on our ground (tier 1 or 2; 26 of August's 239) is
then read whole, one request each, from the Câmara's speech page
(internet/sitaqweb/TextoHTML.asp, about 6 KB), and stored only if its OWN
WORDS match (the long-transcript guard, src/chamber_store.py). The words of
anyone the speech quotes taking the floor (the President's interventions,
"O SR. PRESIDENTE (...) -") and the stage notes ("(Palmas.)") are cut. So a
sitting week costs one list and a few dozen speech pages. A speech the
summary misses is missed: the summary is written by the Câmara's own
indexers and names the subjects spoken on.

The speaker's member_key comes from br_members (the Câmara's deputies, by
name and state); a guest at a solemn session has none. The list of 1 to 9
October 2026 was empty (an election week); summaries follow the sitting by
days, so Brazil is not a same-day source (no live read).
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
    return HONORIFIC.sub("", " ".join(m.group(0).split()))[:160] or None


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


# --- speeches ------------------------------------------------------------------------

LIST = ("https://www.camara.leg.br/SitCamaraWS/SessoesReunioes.asmx/ListarDiscursosPlenario"
        "?dataIni={0}&dataFim={1}&codigoSessao=&parteNomeParlamentar=&siglaPartido=&siglaUF=")
TEXT = ("https://www.camara.leg.br/internet/sitaqweb/TextoHTML.asp?etapa=5&nuSessao={sessao}"
        "&nuQuarto={quarto}&nuOrador={orador}&nuInsercao={insercao}&sgFaseSessao={fase}"
        "&Data={data}")
SIGLAS = (("Proposta de Emenda à Constituição", "PEC"), ("Projeto de Lei Complementar", "PLP"),
          ("Projeto de Lei", "PL"), ("Medida Provisória", "MPV"),
          ("Projeto de Decreto Legislativo", "PDL"), ("Projeto de Resolução", "PRC"))
_BILL = re.compile(r"(Proposta de Emenda à Constituição|Projeto de Lei Complementar|"
                   r"Projeto de Lei|Medida Provisória|Projeto de Decreto Legislativo|"
                   r"Projeto de Resolução)(?:\s*\([A-Z]+\))?\s+n[ºo°]\s*([\d.]+),?\s+de\s+(\d{4})")
_LABEL = re.compile(r"(?:\bO SR\.|\bA SRA\.)\s+([^()\n]{2,80}?)\s*\(([^)]*)\)\s*[-–—]\s*")
_STAGE = re.compile(r"\((?:Palmas|Pausa|Manifestação|Manifestações|Risos|Apupos|Vaias|"
                    r"Não identificad|Intervenção|Intervenções|Tumulto|Soa a campainha|"
                    r"Procede-se)[^()]*\)")


def _iso(ddmmyyyy):
    d, m, y = (ddmmyyyy or "").strip()[:10].split("/")
    return "{0}-{1}-{2}".format(y, m, d)


def _br(iso):
    y, m, d = iso.split("-")
    return "{0}/{1}/{2}".format(d, m, y)


def listed_speeches(xml_text):
    """[{sessao, data, fase, fase_desc, orador, nome, partido, uf, hora, quarto,
    insercao, indexacao, sumario}] from ListarDiscursosPlenario."""
    import xml.etree.ElementTree as ET
    out = []
    root = ET.fromstring(xml_text)
    for s in root.iter("sessao"):
        sessao = (s.findtext("codigo") or "").strip()
        data = (s.findtext("data") or "").strip()
        for f in s.iter("faseSessao"):
            for d in f.iter("discurso"):
                hora = (d.findtext("horaInicioDiscurso") or "").strip()
                out.append({
                    "sessao": sessao, "data": _iso(data) if data else None,
                    "fase": (f.findtext("codigo") or "").strip(),
                    "fase_desc": (f.findtext("descricao") or "").strip(),
                    "orador": (d.findtext("orador/numero") or "").strip(),
                    "nome": (d.findtext("orador/nome") or "").strip(),
                    "partido": (d.findtext("orador/partido") or "").strip() or None,
                    "uf": (d.findtext("orador/uf") or "").strip() or None,
                    "hora": hora[11:16] if len(hora) >= 16 else None,
                    "quarto": (d.findtext("numeroQuarto") or "").strip(),
                    "insercao": (d.findtext("numeroInsercao") or "").strip(),
                    "indexacao": (d.findtext("txtIndexacao") or "").strip(),
                    "sumario": (d.findtext("sumario") or "").strip()})
    return out


def speech_words(page):
    """The speaker's own words from a TextoHTML page: from the first
    'O SR. NAME (PARTY - UF. ...) -' label on, keeping only the turns of
    that first speaker (an interruption by the chair or a colleague is cut),
    without the stage notes."""
    t = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", page or "")
    t = re.sub(r"(?i)<\s*(br|/p|/div)\b[^>]*>", "\n", t)
    import html as htmlmod
    t = htmlmod.unescape(re.sub(r"<[^>]+>", " ", t))
    t = "\n".join(" ".join(ln.split()) for ln in t.split("\n") if ln.strip())
    labels = list(_LABEL.finditer(t))
    if not labels:
        return ""
    first = " ".join(labels[0].group(1).split()).upper()
    parts = []
    for i, m in enumerate(labels):
        end = labels[i + 1].start() if i + 1 < len(labels) else len(t)
        if " ".join(m.group(1).split()).upper() == first:
            parts.append(t[m.end():end])
    words = _STAGE.sub(" ", "\n".join(parts))
    return "\n".join(" ".join(ln.split()) for ln in words.split("\n") if ln.strip())


def bill_of(sumario):
    """'PL 956/2015' named first in a summary, or None."""
    m = _BILL.search(sumario or "")
    if not m:
        return None
    sigla = next(code for words, code in SIGLAS if m.group(1) == words)
    return "{0} {1}/{2}".format(sigla, int(m.group(2).replace(".", "")), m.group(3))


def deputies(conn):
    """{(folded name, UF): member_key} of the Câmara; shared keys map to None."""
    from src.noise import fold
    out = {}
    try:
        rows = conn.execute("SELECT member_key, name, uf FROM br_members WHERE chamber = 'camara'"
                            ).fetchall()
    except Exception:                               # noqa: BLE001
        return {}
    for key, name, uf in rows:
        k = (" ".join(fold(name or "").lower().split()), uf)
        out[k] = None if k in out else key
    return out


def speeches(run):
    from src.noise import fold
    try:
        raw = run.client.get_text(LIST.format(_br(run.since), _br(run.today)), FEED,
                                  "discursos-{0}-{1}".format(run.since, run.today), timeout=120)
        listed = listed_speeches(raw)
    except (FetchError, ValueError, SyntaxError) as exc:
        run.gap("speech list since {0} unreadable: {1}".format(run.since, str(exc)[:100]))
        return
    members = deputies(run.conn)
    ementas = {}
    sessions = {}
    for sp in listed:
        sessions.setdefault((sp["sessao"], sp["data"]), {"n": 0, "pre": 0, "matched": 0,
                                                         "chars": 0, "done": 0})["n"] += 1
    fetched = 0
    for sp in listed:
        sess = sessions[(sp["sessao"], sp["data"])]
        pre = cs.classify_question(run.taxes, sp["sumario"], sp["indexacao"])
        if not pre:
            sess["done"] += 1
            continue
        sess["pre"] += 1
        sid = "{0}#{1}-{2}".format(sp["sessao"], sp["quarto"], sp["insercao"])
        if cs.read_state(run.conn, CC, sid)[1] == "read":
            sess["done"] += 1
            continue
        if run.out_of_time("speeches", fetched):
            break
        url = TEXT.format(sessao=sp["sessao"], quarto=sp["quarto"], orador=sp["orador"],
                          insercao=sp["insercao"], fase=sp["fase"], data=_br(sp["data"]))
        try:
            page = run.client.get_text(url, FEED, "texto-{0}-{1}-{2}".format(
                sp["sessao"], sp["quarto"], sp["insercao"]))
        except FetchError as exc:
            run.gap("speech {0} unreadable: {1}".format(sid, str(exc)[:80]))
            continue
        fetched += 1
        sess["done"] += 1
        words = speech_words(page)
        sess["chars"] += len(words)
        bill = bill_of(sp["sumario"])
        if bill and bill not in ementas:
            row = run.conn.execute("SELECT ementa FROM br_bills WHERE bill_key=?",
                                   (bill,)).fetchone()
            ementas[bill] = row[0] if row and row[0] else None
        if bill:
            debate = "{0}{1}".format(bill, ": " + ementas[bill] if ementas.get(bill) else "")
            debate_id = bill
        else:
            debate = "{0}, sessão {1}".format(sp["fase_desc"] or sp["fase"], sp["sessao"])
            debate_id = cs.short_id(sp["sessao"], sp["fase"])
        title = cs.classify_title(run.taxes, debate)
        m = cs.classify_speech(run.taxes, words, title)
        hit = 0
        if m:
            hit = 1
            sess["matched"] += 1
            key = members.get((" ".join(fold(sp["nome"]).lower().split()), sp["uf"]))
            run.speech({"speech_id": sid, "doc_id": "sessao-{0}".format(sp["sessao"]),
                        "date": sp["data"], "chamber": "Câmara dos Deputados",
                        "debate_id": debate_id, "debate": debate, "speaker": sp["nome"],
                        "party": sp["partido"], "role": "member" if key else
                        "not a deputy on the roster", "person_id": key, "text": words,
                        "url": url, "title_areas": title.areas}, m)
        if not run.dry_run:
            cs.mark_read(run.conn, CC, sid, "speech-file", sp["data"], None, 1, hit, len(words),
                         run.today)
    for (sessao, data), s in sorted(sessions.items(), key=lambda x: (x[0][1] or "", x[0][0])):
        run.read("sessao-{0}".format(sessao), "speeches", data,
                 "{0} pre-filtered on the summary".format(s["pre"]), s["n"], s["matched"],
                 s["chars"], "read" if s["done"] >= s["n"] else "partial")
    run.log("  [discursos] {0} plenary speech(es) since {1} in {2} session(s); {3} on our ground "
            "by the Câmara's summary, read whole; {4} on our ground in their own words".format(
                len(listed), run.since, len(sessions), sum(s["pre"] for s in sessions.values()),
                sum(s["matched"] for s in sessions.values())))


if __name__ == "__main__":
    sys.exit(cs.main(CC, {"questions": questions, "speeches": speeches}, doc=__doc__))
