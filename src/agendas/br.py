"""Brazil: the pauta of both houses.

Câmara (dadosabertos.camara.leg.br, API v2): `/eventos` lists the sittings
and committee meetings in a window; each deliberative one has a `/pauta`,
the proposições to be taken with their rapporteur. Measured 10 October
2026: 9 events for 12 to 25 October (the House is in its election recess);
36 in the sitting week of 31 August.

Senado (legis.senado.leg.br/dadosabertos): `/plenario/agenda/mes/<date>`
is the plenary's agenda from a date to the end of that month, each sitting
with its Materias. Read for this month and, when the window crosses into
the next, that one too.

Refs are the proposição keys of br_bills and config/watchlist-br.yaml
('PL 2665/2022', 'PEC 221/2019'; a Senate matéria from before 2019 is
'SF PDS 240/2011', as tools/br_rollcalls.py keys it).
"""

from __future__ import annotations

import datetime

from src import agenda
from src.http import FetchError

CC = "br"
SOURCE = "the Câmara's eventos and pauta, the Senado's plenary agenda"
BILLS = ("br_bills", "bill_key", "ementa")
FEED = "br-agenda"
CAMARA = "https://dadosabertos.camara.leg.br/api/v2"
EVENTS = CAMARA + "/eventos?dataInicio={0}&dataFim={1}&itens=100&ordem=ASC&ordenarPor=dataHoraInicio"
PAUTA = CAMARA + "/eventos/{0}/pauta"
SENADO = "https://legis.senado.leg.br/dadosabertos/plenario/agenda/mes/{0}.json"
CAMARA_WEB = "https://www.camara.leg.br/evento-legislativo/{0}"
SENADO_WEB = "https://www25.senado.leg.br/web/atividade/materias/-/materia/{0}"
UNIFIED_FROM = 2019
MAX_PAUTAS = 80
SKIP = ("cancelad", "encerrad")


def key(sigla, numero, ano, senado=False):
    try:
        n, a = int(str(numero).strip()), int(str(ano).strip())
    except (TypeError, ValueError):
        return None
    sigla = (sigla or "").strip().upper()
    if not sigla or not n or not a:
        return None
    k = "{0} {1}/{2}".format(sigla, n, a)
    return "SF " + k if senado and a < UNIFIED_FROM else k


# --- Câmara -------------------------------------------------------------------

def deliberative(event):
    return ("deliberativa" in (event.get("descricaoTipo") or "").lower()
            and not any(s in (event.get("situacao") or "").lower() for s in SKIP))


def parse_events(reply):
    return [e for e in (reply or {}).get("dados") or []]


def parse_pauta(event, reply):
    """Points from one Câmara event's pauta."""
    start = event.get("dataHoraInicio") or ""
    date, time = start[:10] or None, (start[11:16] or None)
    orgaos = event.get("orgaos") or [{}]
    plenary = any(o.get("sigla") == "PLEN" for o in orgaos)
    body = "Câmara plenary" if plenary else "Câmara, {0}".format(orgaos[0].get("nome") or "committee")
    out = []
    for p in (reply or {}).get("dados") or []:
        rel = p.get("proposicaoRelacionada_") or {}
        prop = p.get("proposicao_") or {}
        refs = [key(rel.get("siglaTipo"), rel.get("numero"), rel.get("ano")),
                key(prop.get("siglaTipo"), prop.get("numero"), prop.get("ano"))]
        title = rel.get("ementa") or prop.get("ementa") or p.get("titulo")
        detail = " ".join(x for x in (p.get("titulo"), p.get("regime"), p.get("textoParecer"))
                          if x) or None
        out.append(agenda.point("camara-{0}-{1}".format(event.get("id"), p.get("ordem")),
                                date, title, body, "plenary" if plenary else "committee",
                                time, detail, refs=[r for r in refs if r],
                                url=CAMARA_WEB.format(event.get("id")),
                                status=event.get("situacao")))
    return out


# --- Senado ---------------------------------------------------------------------

def as_list(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def parse_senado(reply, today):
    """(points, sitting dates) from one month's plenary agenda, from today."""
    sessions = as_list((((reply or {}).get("AgendaPlenario") or {}).get("Sessoes") or {})
                       .get("Sessao"))
    out, sittings = [], []
    for s in sessions:
        date = s.get("Data")
        if not date or date < today:
            continue
        if "deliberativa" in (s.get("TipoSessao") or "").lower() and \
                "não" not in (s.get("TipoSessao") or "").lower():
            sittings.append(date)
        body = "Senado plenary, {0}".format(" ".join((s.get("TipoSessao") or "").split()).lower())
        for m in as_list((s.get("Materias") or {}).get("Materia")):
            k = key(m.get("SiglaMateria"), m.get("NumeroMateria"), m.get("AnoMateria"),
                    senado=(m.get("SiglaCasaIniciadora") or "SF") == "SF")
            title = m.get("Ementa") or m.get("DescricaoIdentificacaoMateria")
            detail = " ".join(x for x in (m.get("DescricaoIdentificacaoMateria"),
                                          m.get("Cabecalho"), m.get("Apreciacao")) if x) or None
            out.append(agenda.point("senado-{0}-{1}".format(s.get("CodigoSessao"),
                                                              m.get("CodigoMateria")),
                                    date, title, body, "plenary", s.get("Hora"), detail,
                                    refs=[k] if k else [],
                                    url=SENADO_WEB.format(m.get("CodigoMateria")),
                                    status=s.get("SituacaoSessao")))
    return out, sittings


def fetch(client, today, days, log=print):
    end = (datetime.date.fromisoformat(today) + datetime.timedelta(days=days)).isoformat()
    points, gaps, sittings = [], [], []
    try:
        events = parse_events(client.get_json(EVENTS.format(today, end), FEED,
                                              "eventos-{0}".format(today)))
    except (FetchError, ValueError) as exc:
        events = []
        gaps.append("Câmara eventos unreadable: {0}".format(str(exc)[:120]))
    read = 0
    for e in events:
        if not deliberative(e):
            continue
        if any(o.get("sigla") == "PLEN" for o in e.get("orgaos") or []):
            sittings.append((e.get("dataHoraInicio") or "")[:10])
        if read >= MAX_PAUTAS:
            gaps.append("Câmara pauta: stopped after {0} events".format(MAX_PAUTAS))
            break
        read += 1
        try:
            points += parse_pauta(e, client.get_json(PAUTA.format(e.get("id")), FEED,
                                                     "pauta-{0}".format(e.get("id"))))
        except (FetchError, ValueError) as exc:
            gaps.append("Câmara pauta {0} unreadable: {1}".format(e.get("id"), str(exc)[:80]))
    months = sorted({today[:7], end[:7]})
    for i, month in enumerate(months):
        first = today if i == 0 else month + "-01"
        try:
            got, days_ = parse_senado(client.get_json(SENADO.format(first.replace("-", "")),
                                                      FEED, "senado-{0}".format(first)), today)
        except (FetchError, ValueError) as exc:
            gaps.append("Senado agenda {0} unreadable: {1}".format(month, str(exc)[:80]))
            continue
        points += [p for p in got if p["date"] <= end]
        sittings += days_
    sittings = sorted(d for d in sittings if d and d >= today)
    return agenda.fetched(points, next_sitting=sittings[0] if sittings else None, gaps=gaps)
