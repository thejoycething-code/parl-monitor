"""Brazil: the state assemblies' forward business (regional_agenda, 16 October 2026).

The past half (tools/br_states.py, src/brs_store.py) reads bills, stages and
votes; this module reads what each Assembleia Legislativa has BOOKED: the
plenary sessions with their pauta / ordem do dia, and committee meetings
with their pauta. Region codes are br_states' lower-case UFs
(src/brs_store.STATES), so the renderer can join the two. Every route was
probed live on 16 October 2026 with robots.txt read first
(docs/brazil-regions-scope.md, "Forward agenda").

2026 is an election year (first round 4 October, run-off 25 October):
plenaries are thin and agendas are published a day or two ahead, so most
assemblies show a handful of booked sittings and few named items. That is
expected; the readers are built for the normal rhythm.

  sp   ALESP's legislative portal API (legis-api-portal-prd.al.sp.gov.br, the
       JSON its own SPA loads; no robots.txt, 404): the plenary sessions of
       the window (sessoes-plenarias/consulta), each one's ordem do dia or
       "pauta para emendas" (HTML inside the JSON), and the committee
       meetings (colegiado/reunioes) with each meeting's pauta.
  mg   ALMG's open-data API (dadosabertos.almg.gov.br/api/v2/, allowed at our
       request; paging and sorting stay disallowed, so a search that holds
       more than one page is split by date, never paged): committee meetings
       (comissoes/reunioes/pesquisa: an audiência's purpose, or the booked
       meeting) and plenary meetings (plenario/reunioes/pesquisa, then each
       meeting's detalhes with its Ordem do Dia).
  rj   ALERJ's Ordem do Dia service (www2.alerj.rj.gov.br/ordemdodia/): the
       month calendar marks the days with a pauta; each day's pauta
       (pauta/?op=D&data=Y;M;D, HTML) is read item by item. The server takes
       about 30 s a request. The calendar shows the current month only (the
       next month is an ASP.NET postback): horizon the month's end.
  pr   ALEP's transparency portal (transparencia.assembleia.pr.leg.br, robots
       allow all): the JSON its pautas page loads (ordem-do-dia/ajax,
       ccj/ajax, comissoes-tematicas/ajax, page 1, newest first) and, for
       sittings in the window, the ordem do dia / pauta PDF (pypdf).
  pe   ALEPE (www.alepe.pe.gov.br, robots allow all): the month agenda (a form
       POST, operacao=lerAgendaMensal) for plenary, committee and solemn
       meetings, and for each plenary day the Ordem do Dia (POST lerOrdem,
       then the detalhe-ordem-do-dia page).
  ce   ALECE's agenda (www.al.ce.gov.br/agenda?datetimes=..., one page for the
       window): solemn sessions in the Plenário and committee hearings. The
       ordinary sessions' ordem do dia (www2 pdr/ordem_do_dia.php) is posted
       on the day and is not read.
  pa   ALEPA's Pautas do Plenário (www.alepa.pa.gov.br/Home/Page/PautasdoPlenario,
       newest first) and, for a dated pauta in the window, its
       Legislativo/DetalhesPauta page.
  SAPL houses (pb, am, al, pi, ro, to, ac): the Interlegis SAPL REST API,
       /api/sessao/sessaoplenaria/?data_inicio__gte=<today>, and for a booked
       session with a published pauta its /api/sessao/ordemdia/ (one page of
       100; SAPL_ORDEM_CAP sessions a house). Every SAPL robots.txt asks
       Crawl-delay: 60, so all houses are asked IN PARALLEL on the first SAPL
       region's turn (about a minute each) and the other regions use the
       result.

Not read, each with its reason on every run: see REGIONS (Bahia's agendas
moved to a host that refuses us, RS/ES/DF/AP do not answer from outside
Brazil, SC answers GitHub's runners only, and so on).
"""

from __future__ import annotations

import datetime
import html as _html
import io
import json
import re
import threading
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

from src import regional_agenda as ra
from src.http import FetchError

CC = "br"
TAXONOMIES = (("taxonomy-pt.yaml", "br"),)
FEED = ra.feed(CC)

SP_API = "https://legis-api-portal-prd.al.sp.gov.br"
SP_SITE = "https://www.al.sp.gov.br"
MG_API = "https://dadosabertos.almg.gov.br/api/v2/"
RJ_OD = "https://www2.alerj.rj.gov.br/ordemdodia/"
PR_PAUTAS = "https://transparencia.assembleia.pr.leg.br/plenario/pautas/"
PE = "https://www.alepe.pe.gov.br"
CE_AGENDA = "https://www.al.ce.gov.br/agenda?datetimes={0}"
PA = "https://www.alepa.pa.gov.br"
PA_LIST = PA + "/Home/Page/PautasdoPlenario"

SAPL_HOSTS = {
    "pb": "sapl.al.pb.leg.br", "am": "sapl.al.am.leg.br", "al": "sapl.al.al.leg.br",
    "pi": "sapl.al.pi.leg.br", "ro": "sapl.al.ro.leg.br", "to": "sapl.al.to.leg.br",
    "ac": "sapl.al.ac.leg.br",
}
SAPL_ORDEM_CAP = 2       # ordem do dia reads per house per run (a minute each)

THROTTLES = {"legis-api-portal-prd.al.sp.gov.br": 1.5, "dadosabertos.almg.gov.br": 1.5,
             "www2.alerj.rj.gov.br": 5.0, "transparencia.assembleia.pr.leg.br": 2.0,
             "storage2.assembleia.pr.leg.br": 2.0, "www.alepe.pe.gov.br": 2.0,
             "www.al.ce.gov.br": 2.0, "www.alepa.pa.gov.br": 2.0}
for _h in SAPL_HOSTS.values():
    THROTTLES[_h] = 60.0

PR_PDF_CAP = 8           # PDFs read per run in Paraná
MG_MAX_SPLITS = 12       # searches per kind (a busy window is split by date)

_SPACE = re.compile(r"\s+")


def _one(text):
    return ra.one_line(_html.unescape(text or ""))


def _hm(text):
    m = re.search(r"(\d{1,2})[:h](\d{2})", text or "")
    return "{0:02d}:{1}".format(int(m.group(1)), m.group(2)) if m else None


def _units(ctx, complete, meetings):
    """The whole window when everything booked in it was read in full, else
    only the meetings that were (a failed one keeps its stored rows)."""
    if complete:
        return [ra.window(ctx.today, ctx.until)]
    return [ra.meeting(m) for m in meetings]


def pdf_text(raw):
    """Text of a PDF (pypdf), pages joined; '' when it cannot be read."""
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(raw))
        return "\n".join((p.extract_text() or "") for p in reader.pages)
    except Exception:                                   # noqa: BLE001 - a bad PDF is a gap
        return ""


# --- a numbered agenda in plain text (PDF or HTML) ----------------------------------

_REF = re.compile(
    r"\b((?:Projeto|Proposta|Proposi[çc][ãa]o|Veto|Emenda|Requerimento|Indica[çc][ãa]o|Mo[çc][ãa]o|"
    r"Mensagem|Of[íi]cio)[^\n]{0,80}?n?\s*[º°o]?\s*[\d.]+(?:-[A-Z])?/\d{4}|"
    r"\b(?:PLC?|PEC|PDL|PR|VET|RQ\w*|IND)\s*[\d.]+/\d{4})", re.I)
_STOP = re.compile(r"^(?:Parecer|Pareceres|Relator|Relatoria|Relatores|Autoria da Emenda|"
                   r"Di[áa]rio Oficial|Avulso|Com pedido|Artigo \d+|\d+ emendas?\.?$)", re.I)
_AUTHOR = re.compile(r"^(?:Autoria|Autor|Autora|Autores|De autoria)\b", re.I)


def reference(text):
    m = _REF.search(text or "")
    return _one(m.group(1)) if m else None


def numbered_items(lines, start, header=()):
    """Group lines into items at each line matching `start` (a regex with
    the item's heading in its last group). Returns [(heading, ementa,
    authors, notes)]. Running page headers in `header` are dropped."""
    out, cur = [], None
    for raw in lines:
        line = _one(raw)
        if not line or line in header or re.match(r"^\d{1,3}$", line):
            continue
        m = start.match(line)
        if m:
            cur = {"head": m.group(m.lastindex), "body": [], "authors": [], "notes": [],
                   "stop": False}
            out.append(cur)
            continue
        if cur is None:
            continue
        if _AUTHOR.match(line) or (cur["authors"] and cur["authors"][-1].endswith(",")
                                   and not cur["body"]):
            cur["authors"].append(line)
        elif _STOP.match(line):
            cur["stop"] = True
            cur["notes"].append(line)
        elif cur["stop"]:
            cur["notes"].append(line)
        elif not cur["body"] and not line[:1].isalpha() and not line[:1] in "\"“(":
            cur["notes"].append(line)
        else:
            cur["body"].append(line)
    res = []
    for c in out:
        head = c["head"].rstrip(" .;:")
        # A heading wrapped onto the next line ('... Projeto de Lei' / 'nº 12/2026.').
        while c["body"] and not reference(head) and reference(head + " " + c["body"][0]):
            head = (head + " " + c["body"].pop(0)).rstrip(" .;:")
        res.append((head, " ".join(c["body"]).strip(), "; ".join(c["authors"]),
                    " ".join(c["notes"]).strip()))
    return res


def text_item(dated, head, ementa, body, order, meeting_id, detail=None, url=None,
              item_time=None):
    business = "{0}: {1}".format(head, ementa) if ementa else head
    return ra.item(dated, business, body, item_time=item_time, order=order,
                   meeting_id=meeting_id, detail=detail, reference=reference(head),
                   url=url)


# --- São Paulo: ALESP's portal API ---------------------------------------------------

_SP_BLOCK = re.compile(r"<(?:div|p)\b[^>]*>(.*?)</(?:div|p)>", re.S | re.I)


def parse_sp_corpo(corpo):
    """An ALESP ordem do dia / pauta body (HTML) -> [(ref, heading, ementa,
    authors, section)]: one per propositura block (a <div> or <p> holding a
    /propositura/ link), the section the nearest <h3>/<h4>/centred title."""
    out, section = [], None
    pos = 0
    text = corpo or ""
    for m in re.finditer(r"<(h[1-6])[^>]*>(.*?)</\1>|<p[^>]*text-align:center[^>]*>(.*?)</p>|"
                         r"<(?:div|p)\b[^>]*>(.*?)</(?:div|p)>", text, re.S | re.I):
        if m.group(2) is not None or m.group(3) is not None:
            section = _one(ra.clean(m.group(2) or m.group(3)))
            continue
        block = m.group(4) or ""
        link = re.search(r'<a[^>]*href="/propositura/\d+"[^>]*>(.*?)</a>', block, re.S)
        if not link:
            continue
        ref = _one(ra.clean(link.group(1)))
        lines = [l for l in ra.clean(block).split("\n") if l.strip()]
        head = _one(lines[0]) if lines else ref
        ementa = authors = ""
        for l in lines[1:]:
            l = _one(l)
            if l.lower().startswith("ementa:"):
                ementa = l.split(":", 1)[1].strip()
            elif l.lower().startswith("autoria:"):
                authors = l.split(":", 1)[1].strip()
        out.append((ref, head, ementa, authors, section))
        pos = m.end()
    return out


def sp_session_items(sess, doc, ctx, kind):
    """Items of one ALESP session from its ordem do dia or pauta JSON."""
    dated, item_time = (sess.get("dtInicio") or "")[:10], _hm(sess.get("dtInicio"))
    mid = "sp-sessao-{0}".format(sess.get("id"))
    url = "{0}/sessao-plenaria/{1}/{2}".format(SP_SITE, sess.get("id"), kind)
    out = []
    for n, (ref, head, ementa, authors, section) in enumerate(
            parse_sp_corpo((doc or {}).get("corpo")), 1):
        stage = re.sub(r"^\d+\s*-\s*", "", head)
        stage = stage.replace(ref, "").strip(" -")
        detail = "; ".join(x for x in (
            "Pauta para emendas e recursos" if kind == "pauta" else None, section, stage or None,
            "Autoria: " + authors if authors else None) if x)
        out.append(ra.item(dated, "{0}: {1}".format(ref, ementa) if ementa else ref, "Plenário",
                           item_time=item_time, order=n, meeting_id=mid, detail=detail,
                           reference=ref, url=url, key="{0}-{1}".format(kind, ra.slug(ref))))
    return out


def sp_session_slot(sess):
    """A session with nothing published: a solemn session's own subject, else
    'to be announced'."""
    dated, item_time = (sess.get("dtInicio") or "")[:10], _hm(sess.get("dtInicio"))
    mid = "sp-sessao-{0}".format(sess.get("id"))
    tipo = sess.get("tipo") or ""
    tipo = tipo.get("nome") if isinstance(tipo, dict) else tipo
    desc = _one(sess.get("descricao"))
    url = "{0}/sessao-plenaria/{1}".format(SP_SITE, sess.get("id"))
    if desc and "solene" in (tipo or "").lower():
        return ra.item(dated, "{0}: {1}".format(tipo, desc),
                       "Plenário", item_time=item_time, meeting_id=mid, url=url,
                       detail=sess.get("titulo"), item_type="chamber business")
    return ra.item(dated, "", "Plenário", item_time=item_time, meeting_id=mid, url=url,
                   detail=_one("{0} {1}".format(sess.get("titulo") or tipo, desc or "")))


def sp_meeting_items(meet, pauta):
    """Items of one ALESP committee meeting from its pauta page."""
    dated, item_time = (meet.get("dtReuniao") or "")[:10], _hm(meet.get("dtReuniao"))
    names = [c.get("nome") for c in meet.get("colegiadosRelacionados") or [] if c.get("nome")]
    body = " / ".join(names) or "Comissão"
    mid = "sp-reuniao-{0}".format(meet.get("idReuniao"))
    url = "{0}/comissao/reuniao/{1}".format(SP_SITE, meet.get("idReuniao"))
    out = []
    for n, row in enumerate((pauta or {}).get("content") or [], 1):
        proc = row.get("processoDadosView") or {}
        ref = _one(proc.get("txDescricao"))
        if not ref:
            continue
        ementa = _one(proc.get("txEmenta"))
        out.append(ra.item(dated, "{0}: {1}".format(ref, ementa) if ementa else ref, body,
                           item_time=item_time, order=row.get("nuOrdem") or n, meeting_id=mid,
                           detail=("Autoria: " + _one(proc.get("txNomeAutores"))
                                   if proc.get("txNomeAutores") else None),
                           reference=ref, url=url, key="pauta-" + ra.slug(ref)))
    if not out:
        out.append(ra.item(dated, "", body, item_time=item_time, meeting_id=mid, url=url,
                           detail=_one(meet.get("txAssunto")) or meet.get("tituloReuniao")))
    return out


def read_sp(client, ctx):
    q = urllib.parse.urlencode({"page": 0, "size": 100, "dataInicial": ctx.today,
                                "dataFinal": ctx.until})
    sessions = client.get_json("{0}/sessoes-plenarias/consulta?{1}".format(SP_API, q), FEED,
                               "sp-sessoes")
    items, gaps, read_ok, meetings = [], [], True, []
    for sess in (sessions or {}).get("content") or []:
        dated = (sess.get("dtInicio") or "")[:10]
        if not ctx.in_window(dated) or "cancel" in (sess.get("situacao") or "").lower():
            continue
        kind = "ordem-do-dia" if sess.get("temOrdemDoDia") else (
            "pauta" if sess.get("temPauta") else None)
        got = []
        if kind and not ctx.out_of_time():
            try:
                doc = client.get_json("{0}/sessoes-plenarias/{1}/{2}".format(
                    SP_API, sess["id"], kind), FEED, "sp-{0}-{1}".format(kind, sess["id"]))
                got = sp_session_items(sess, doc, ctx, kind)
            except FetchError as exc:
                gaps.append("sp: session {0} {1}: {2}".format(sess["id"], kind, exc))
                read_ok = False
                continue
        items += got or [sp_session_slot(sess)]
        meetings.append("sp-sessao-{0}".format(sess["id"]))
    q = urllib.parse.urlencode({"page": 0, "size": 100, "dataInicio": ctx.today,
                                "dataFim": ctx.until})
    try:
        meets = client.get_json("{0}/colegiado/reunioes?{1}".format(SP_API, q), FEED,
                                "sp-reunioes")
    except FetchError as exc:
        gaps.append("sp: committee meetings: {0}".format(exc))
        meets, read_ok = {}, False
    for meet in (meets or {}).get("content") or []:
        dated = (meet.get("dtReuniao") or "")[:10]
        status = ((meet.get("status") or {}).get("txNome") or "").lower()
        if not ctx.in_window(dated) or "cancel" in status:
            continue
        pauta = None
        if not ctx.out_of_time():
            try:
                pauta = client.get_json("{0}/colegiado/reuniao/{1}/pauta?page=0&size=100".format(
                    SP_API, meet["idReuniao"]), FEED, "sp-pauta-{0}".format(meet["idReuniao"]))
            except FetchError as exc:
                gaps.append("sp: meeting {0} pauta: {1}".format(meet["idReuniao"], exc))
                read_ok = False
                continue
        items += sp_meeting_items(meet, pauta)
        meetings.append("sp-reuniao-{0}".format(meet["idReuniao"]))
    return ra.RegionRead(items, _units(ctx, read_ok, meetings),
                         source="ALESP legis-api-portal (sessões plenárias, colegiado/reuniões)",
                         gaps=gaps)


# --- Minas Gerais: ALMG's open-data API ------------------------------------------------

_MG_FORBIDDEN = re.compile(r"[?&](?:p|tp|ord|ordenacao)=")


def mg_url(path, **params):
    """An ALMG API URL, never with a paging or sorting parameter (robots.txt
    disallows them)."""
    url = MG_API + path + "?" + "&".join("{0}={1}".format(k, v) for k, v in params.items())
    if _MG_FORBIDDEN.search(url):
        raise ValueError("ALMG API: paging/sorting parameters are disallowed: " + url)
    return url


def _ymd(day):
    return day.replace("-", "")


def _halves(d1, d2):
    a, b = datetime.date.fromisoformat(d1), datetime.date.fromisoformat(d2)
    mid = a + datetime.timedelta(days=(b - a).days // 2)
    return (d1, mid.isoformat()), ((mid + datetime.timedelta(days=1)).isoformat(), d2)


def mg_search(client, path, key, ctx, slug):
    """Every record of a date-filtered pesquisa over the window, splitting
    a range that holds more than one page (paging is disallowed). Returns
    (records, complete)."""
    pending, records, complete, asked = [(ctx.today, ctx.until)], [], True, 0
    while pending:
        d1, d2 = pending.pop(0)
        if asked >= MG_MAX_SPLITS or ctx.out_of_time():
            return records, False
        asked += 1
        data = client.get_json(mg_url(path, formato="json", ini=_ymd(d1), fim=_ymd(d2)), FEED,
                               "{0}-{1}".format(slug, _ymd(d1)))
        res = (data or {}).get(key) or {}
        rows = next((v for v in res.values() if isinstance(v, list)), [])
        total = int(res.get("numeroOcorrencias") or 0)
        size = int(res.get("tamanhoPagina") or 20)
        if total > size and d1 != d2:
            pending[:0] = list(_halves(d1, d2))
            continue
        if total > size:
            complete = False
        records += rows
    return records, complete


def mg_committee_items(meet):
    """One ALMG committee meeting: its purpose (an audiência pública, a debate)
    as the item, the requerimento as reference; else a booked slot."""
    com = meet.get("comissao") or {}
    name = _one(com.get("nome")) or "Comissão"
    if not name.lower().startswith("comiss"):
        name = "Comissão de " + name
    dated, item_time = (meet.get("data") or "")[:10], _hm(meet.get("hora"))
    mid = "mg-reuniao-{0}".format(meet.get("id"))
    url = "https://www.almg.gov.br/atividade-parlamentar/comissoes/reuniao/?idTipo=1&dia={0}".format(
        dated)
    reqs = meet.get("requerimentos") or []
    refs = ["{0} {1}/{2}".format(((r.get("tipo") or {}).get("sigla") or "RQ"), r.get("numero"),
                                 r.get("ano")) for r in reqs if r.get("numero")]
    kind = "Audiência pública" if meet.get("audienciaPublica") == "S" else _one(
        (meet.get("tipoReuniao") or {}).get("descricao"))
    finalidade = _one(meet.get("finalidade"))
    if finalidade:
        return [ra.item(dated, "{0}: {1}".format(kind, finalidade) if kind else finalidade, name,
                        item_time=item_time, order=1, meeting_id=mid,
                        detail="; ".join(_one(r.get("ementa")) for r in reqs if r.get("ementa"))
                        or None, reference=", ".join(refs) or None, url=url,
                        item_type="committee evidence" if meet.get("audienciaPublica") == "S"
                        else None)]
    return [ra.item(dated, "", name, item_time=item_time, meeting_id=mid, url=url,
                    detail="{0} reunião {1}".format(kind or "", meet.get("numero") or "").strip())]


def mg_plenary_items(detail, dated, hora):
    """plenario/reunioes/detalhes -> one item per proposição on the Ordem
    do Dia (any phase)."""
    reu = (detail or {}).get("reuniao") or {}
    head = reu.get("reuniao") or {}
    mid = "mg-plenario-{0}".format(head.get("id") or "{0}-{1}".format(dated, hora))
    out, n = [], 0
    for phase in (reu.get("segundaParte") or {}).values():
        if not isinstance(phase, dict):
            continue
        for it in phase.get("ordemDoDia") or []:
            prop = it.get("proposicao") or {}
            tipo = prop.get("tipo") or {}
            if not prop.get("numero"):
                continue
            ref = "{0} {1}/{2}".format((tipo.get("sigla") or "").rstrip(".") or tipo.get(
                "descricao") or "", prop.get("numero"), prop.get("ano"))
            label = "{0} nº {1}/{2}".format(tipo.get("descricao") or ref, prop.get("numero"),
                                           prop.get("ano"))
            ementa = _one(prop.get("ementaOuAssunto"))
            n += 1
            out.append(ra.item(dated, "{0}: {1}".format(label, ementa) if ementa else label,
                               "Plenário", item_time=hora, order=it.get("ordem") or n,
                               meeting_id=mid, detail=_one(it.get("descricao")) or None,
                               reference=ref, key="od-" + ra.slug(ref),
                               url="https://www.almg.gov.br/atividade-parlamentar/plenario/"))
    return out, mid


def read_mg(client, ctx):
    items, gaps, meetings = [], [], []
    meets, complete = mg_search(client, "comissoes/reunioes/pesquisa", "resultadoPesquisa", ctx,
                                "mg-comissoes")
    if not complete:
        gaps.append("mg: committee meetings: a day holds more than one page, or the split "
                    "budget ran out (paging is disallowed by robots.txt)")
    for meet in meets:
        if meet.get("reuniaoDesconvocada") == "S" or not ctx.in_window((meet.get("data") or "")[:10]):
            continue
        items += mg_committee_items(meet)
        meetings.append("mg-reuniao-{0}".format(meet.get("id")))
    plen_ok = True
    try:
        plen, plen_ok = mg_search(client, "plenario/reunioes/pesquisa",
                                  "resultadoPesquisaReunioesPlenario", ctx, "mg-plenario")
    except FetchError as exc:
        gaps.append("mg: plenary meetings: {0}".format(exc))
        plen, plen_ok = [], False
    for m in plen:
        dated, hora = (m.get("dia") or "")[:10], (m.get("hora") or "")[:5]
        if m.get("reuniaoDesconvocada") == "S" or not ctx.in_window(dated) or not hora:
            continue
        got, mid = [], "mg-plenario-{0}".format(m.get("idReuniao") or dated)
        try:
            y, mo, d = dated.split("-")
            det = client.get_json(mg_url("plenario/reunioes/detalhes/{0}/{1}/{2}/{3}".format(
                y, mo, d, hora), formato="json"), FEED, "mg-plen-{0}".format(_ymd(dated)))
            got, mid = mg_plenary_items(det, dated, hora)
        except FetchError as exc:
            gaps.append("mg: plenary {0} {1}: {2}".format(dated, hora, exc))
            plen_ok = False
        items += got or [ra.item(dated, "", "Plenário", item_time=hora, meeting_id=mid,
                                 detail=_one((m.get("tipoReuniao") or {}).get("nome")))]
        meetings.append(mid)
    return ra.RegionRead(items, _units(ctx, complete and plen_ok, meetings),
                         source="ALMG open-data API (comissões/plenário reuniões)", gaps=gaps)


# --- Rio de Janeiro: ALERJ's Ordem do Dia service ---------------------------------------

def parse_rj_calendar(page):
    """The month calendar -> (year, month, [days with a pauta])."""
    y = re.search(r"var ano\s*=\s*(\d{4})", page or "")
    m = re.search(r"var mes\s*=\s*(\d{1,2})", page or "")
    days = [int(d) for d in re.findall(r'class="cla_TD dia_com_pauta[^"]*">(\d{1,2})<', page or "")]
    return (int(y.group(1)) if y else None, int(m.group(1)) if m else None, sorted(set(days)))


_RJ_ITEM = re.compile(r"^(\d{1,3})º\)\s*(.+)$")


def parse_rj_pauta(page, dated):
    """One day's ALERJ pauta -> items: 'PROJETO DE LEI Nº 1961/2023: <ementa>',
    the discussion stage and the committees' opinions as detail."""
    lines = ra.clean(page).split("\n")
    out, stage, session, cur = [], None, "Sessão Ordinária", None
    for line in lines:
        line = _one(line)
        if re.match(r"^SESS[ÃA]O (ORDIN|EXTRA)", line):
            session = line.title()
        elif re.match(r"^(EM (\d|DISCUSS|TRAMITA|REGIME|VOTA)|DISCUSS[ÃA]O|VOTA[ÇC][ÃA]O)", line):
            stage = line
        m = _RJ_ITEM.match(line)
        if m:
            text = m.group(2)
            ref = re.split(r"\s*,\s*de autoria", text, 1)[0].strip(" ,")
            ementa = re.split(r",\s*que\s+", text, 1)
            ementa = ementa[1].strip(" .") if len(ementa) > 1 else ""
            cur = {"n": int(m.group(1)), "ref": ref, "ementa": ementa, "notes": [stage] if stage else []}
            out.append(cur)
        elif cur is not None and re.match(r"^(PARECER|RELATOR)", line):
            cur["notes"].append(line)
    res = []
    for c in out:
        res.append(ra.item(dated, "{0}: {1}".format(c["ref"], c["ementa"]) if c["ementa"] else c["ref"],
                           "Plenário", order=c["n"], meeting_id="rj-{0}".format(dated),
                           detail="; ".join(c["notes"])[:1500] or None,
                           reference=_one(c["ref"]), url=RJ_OD,
                           key="od-" + ra.slug(c["ref"])))
    return res


def read_rj(client, ctx):
    page = client.get_text(RJ_OD, FEED, "rj-calendario")
    year, month, days = parse_rj_calendar(page)
    if not year:
        raise FetchError(RJ_OD, FEED, "rj-calendario", 1, "calendar not found on the page")
    last = (datetime.date(year + (month == 12), month % 12 + 1, 1) - datetime.timedelta(days=1))
    end = min(last.isoformat(), ctx.until)
    items, gaps, ok = [], [], True
    for d in days:
        dated = datetime.date(year, month, d).isoformat()
        if not ctx.in_window(dated):
            continue
        if ctx.out_of_time():
            ok = False
            break
        try:
            text = client.get_text("{0}pauta/?op=D&data={1};{2};{3}".format(RJ_OD, year, month, d),
                                   FEED, "rj-pauta-{0}".format(dated))
        except FetchError as exc:
            gaps.append("rj: pauta of {0}: {1}".format(dated, exc))
            ok = False
            continue
        got = parse_rj_pauta(text, dated)
        items += got or [ra.item(dated, "", "Plenário", meeting_id="rj-{0}".format(dated),
                                 url=RJ_OD)]
    units = [ra.window(ctx.today, end)] if ok and end >= ctx.today else []
    return ra.RegionRead(items, units, source="ALERJ Ordem do Dia (www2.alerj.rj.gov.br/ordemdodia)",
                         note="calendar of the current month only (to {0})".format(end), gaps=gaps)


# --- Paraná: ALEP's transparency portal ---------------------------------------------------

_PR_ITEM = re.compile(r"^(?:Item\s*)?(\d{1,3})\s*[–\-]\s*(.+)$", re.I)
_PR_HEADER = {"Assembleia Legislativa do Estado do Paraná", "ASSEMBLEIA LEGISLATIVA DO ESTADO DO PARANÁ",
              "Centro Legislativo Presidente Aníbal Khury", "Diretoria de Assistência ao Plenário",
              "_____________________________"}


def parse_pr_pdf(text):
    """An ALEP ordem do dia or committee pauta (PDF text) -> [(heading,
    ementa, authors, notes)]."""
    lines = [l for l in (text or "").split("\n") if not re.match(r"^_+$", l.strip())]
    return [r for r in numbered_items(lines, _PR_ITEM, header=_PR_HEADER) if reference(r[0])]


def _pr_when(stamp):
    """'2026-10-13T17:30:00.000000Z' (UTC) -> ('2026-10-13', '14:30') in Brasília."""
    try:
        t = datetime.datetime.strptime(stamp[:19], "%Y-%m-%dT%H:%M:%S") - datetime.timedelta(hours=3)
        return t.date().isoformat(), t.strftime("%H:%M")
    except (TypeError, ValueError):
        return (stamp or "")[:10] or None, None


def parse_pr_list(data, kind):
    """A pautas/ajax reply -> [dict(id, dated, time, body, title, pdfs)]."""
    out = []
    groups = ((data or {}).get("data") or {}).values()
    for group in groups:
        rows = []
        if isinstance(group, dict):              # comissões: week -> committee -> meetings
            for meetings in group.values():
                rows += meetings
        else:
            rows = group
        for r in rows:
            if kind == "comissoes":
                dated, hora = (r.get("data") or "")[:10], None
                body = _one(r.get("comissao"))
                files = ((r.get("arquivos") or {}).get("pauta")) or []
                title = _one(r.get("nome_reuniao"))
                rid = "{0}-{1}".format(ra.slug(body, 30), dated)
            else:
                if r.get("publicado") is False:
                    continue
                dated, hora = _pr_when(r.get("data_sessao"))
                body = "Plenário" if kind == "ordem" else "Comissão de Constituição e Justiça"
                files = r.get("arquivos") or []
                title = _one(r.get("titulo"))
                rid = r.get("id")
            pdfs = [(f.get("titulo"), f.get("url")) for f in files
                    if (f.get("extension") or f.get("tipo_arquivo") or "").lower() == "pdf"
                    and f.get("url")]
            out.append({"id": "pr-{0}-{1}".format(kind, rid), "dated": dated, "time": hora,
                        "body": body, "title": title, "pdfs": pdfs})
    return out


def read_pr(client, ctx):
    items, gaps, meetings, ok, pdfs_read = [], [], [], True, 0
    for kind, path in (("ordem", "ordem-do-dia/ajax?page=1"), ("ccj", "ccj/ajax?page=1"),
                       ("comissoes", "comissoes-tematicas/ajax?page=1")):
        try:
            data = client.get_json(PR_PAUTAS + path, FEED, "pr-{0}".format(kind))
        except FetchError as exc:
            if kind == "ordem":
                raise
            gaps.append("pr: {0} list: {1}".format(kind, exc))
            ok = False
            continue
        for s in parse_pr_list(data, kind):
            if not ctx.in_window(s["dated"]):
                continue
            got = []
            pdf = s["pdfs"][0] if s["pdfs"] else None
            if pdf and pdfs_read < PR_PDF_CAP and not ctx.out_of_time():
                pdfs_read += 1
                try:
                    text = pdf_text(client.get_bytes(pdf[1], FEED, "pr-pdf-{0}".format(
                        ra.slug(s["id"], 40))))
                    for n, (head, ementa, authors, notes) in enumerate(parse_pr_pdf(text), 1):
                        got.append(text_item(s["dated"], head, ementa, s["body"], n, s["id"],
                                             detail="; ".join(x for x in (authors, notes) if x)
                                             or None, url=pdf[1], item_time=s["time"]))
                except FetchError as exc:
                    gaps.append("pr: {0} PDF: {1}".format(s["title"], exc))
                    ok = False
            elif pdf:
                ok = False
            items += got or [ra.item(s["dated"], "", s["body"], item_time=s["time"],
                                     meeting_id=s["id"], detail=s["title"],
                                     url=pdf[1] if pdf else None)]
            meetings.append(s["id"])
    return ra.RegionRead(items, _units(ctx, ok, meetings),
                         source="ALEP transparência: pautas (ordem do dia, CCJ, comissões) + PDFs",
                         gaps=gaps)


# --- Pernambuco: ALEPE's agenda and ordem do dia ---------------------------------------------

def parse_pe_month(page):
    """The month agenda -> [dict(dated, title, time, local, author, desc)]."""
    out = []
    m = re.search(r'class="agenda-list"(.*?)(?:<aside|$)', page or "", re.S)
    chunk = m.group(1) if m else ""
    for day in re.split(r'<h3 class="title-date"[^>]*>', chunk)[1:]:
        dated = ra.find_date(ra.clean(day.split("</h3>", 1)[0]))
        for li in re.findall(r"<li>(.*?)</li>", day, re.S):
            title = re.search(r'<strong class="title">(.*?)</strong>', li, re.S)
            lines = [l for l in ra.clean(li).split("\n") if l]
            fields = {}
            rest = []
            for l in lines[1:]:
                k = re.match(r"^(Hora|Local|Autor):\s*(.*)$", l)
                if k:
                    fields[k.group(1)] = k.group(2).strip()
                else:
                    rest.append(l)
            out.append({"dated": dated, "title": _one(ra.clean(title.group(1)) if title else lines[0]),
                        "time": _hm(fields.get("Hora")), "local": fields.get("Local", ""),
                        "author": fields.get("Autor", ""), "desc": " ".join(rest)})
    return out


def parse_pe_ordem_list(page):
    """The ordem do dia of a date -> [(docid, title, url)]."""
    return [(d, _one(t), PE + "/detalhe-ordem-do-dia/?docid={0}&data={1}".format(d, dt))
            for d, dt, t in re.findall(
                r'href="/detalhe-ordem-do-dia/\?docid=(\d+)&(?:amp;)?data=([\d/]+)"[^>]*>(.*?)</a>',
                page or "", re.S)]


_PE_HEAD = re.compile(r"^((?:\d+[ªº]\s*)?(?:Discuss[ãa]o|Vota[çc][ãa]o|Aprecia[çc][ãa]o|"
                      r"Leitura|Primeira|Segunda|Turno|Reda[çc][ãa]o Final)\b.*?\bn[º°o]\s*[\d.]+/\d{4}.*)$",
                      re.I)
_PE_RESULT = re.compile(r"^(?:[A-ZÁÉÍÓÚÂÊÔÃÕÇ() ]{4,60}|DI[ÁA]RIO OFICIAL.*)$")


def parse_pe_ordem(page):
    """A detalhe-ordem-do-dia page -> [(heading, ementa, authors)]."""
    m = re.search(r'class="proposicao-list"(.*?)(?:<aside|$)', page or "", re.S)
    lines = [l for l in ra.clean(m.group(1) if m else "").split("\n")]
    out, cur = [], None
    for line in lines:
        line = _one(line)
        if not line:
            continue
        h = _PE_HEAD.match(line)
        if h:
            cur = [h.group(1), "", ""]
            out.append(cur)
        elif cur is not None:
            if _AUTHOR.match(line):
                cur[2] = line
            elif not cur[1] and not _PE_RESULT.match(line):
                cur[1] = line
    return [tuple(c) for c in out]


def read_pe(client, ctx):
    events, gaps = [], []
    d = ctx.today_date.replace(day=1)
    while d.isoformat() <= ctx.until:
        page = client.post_form(PE + "/agenda", {
            "operacao": "lerAgendaMensal", "hiddenData": "", "field-filter-data": "",
            "field-filter-mes": str(d.month), "field-filter-ano": str(d.year)},
            FEED, "pe-agenda-{0}".format(d.strftime("%Y-%m")))
        events += parse_pe_month(page)
        d = (d + datetime.timedelta(days=32)).replace(day=1)
    items, ok, meetings = [], True, []
    plenary_days = []
    for n, ev in enumerate(events):
        if not ctx.in_window(ev["dated"]):
            continue
        plenary = "plen" in ev["desc"].lower() or (
            ev["local"].lower().startswith("plenário") and "mesa diretora" in ev["author"].lower())
        if plenary and ev["title"].lower().startswith("reunião"):
            plenary_days.append(ev)
            continue
        body = ev["author"] if ev["author"].lower().startswith("comiss") else "Plenário"
        mid = "pe-{0}-{1}-{2}".format(ev["dated"], (ev["time"] or "").replace(":", ""),
                                      ra.slug(body, 30))
        if ev["desc"] and not re.match(r"^(Distribui[çc][ãa]o e discuss[ãa]o de Projetos|"
                                        r"Reuni[ãa]o Plen[áa]ria)$", ev["desc"], re.I):
            business = "{0}: {1}".format(ev["title"], ev["desc"])
            items.append(ra.item(ev["dated"], business, body, item_time=ev["time"], meeting_id=mid,
                                 detail=ev["local"] or None, url=PE + "/agenda/",
                                 item_type="committee evidence" if "audiência" in
                                 ev["title"].lower() else None))
        else:
            items.append(ra.item(ev["dated"], "", body, item_time=ev["time"], meeting_id=mid,
                                 detail=_one("{0} {1}".format(ev["title"], ev["desc"])),
                                 url=PE + "/agenda/"))
        meetings.append(mid)
    for ev in plenary_days:
        dated = ev["dated"]
        mid = "pe-plenario-{0}".format(dated)
        got = []
        if not ctx.out_of_time() and dated <= (ctx.today_date + datetime.timedelta(days=7)).isoformat():
            try:
                dmy = "{2}/{1}/{0}".format(*dated.split("-"))
                lst = client.post_form(PE + "/ordem-do-dia/", {
                    "operacao": "lerOrdem", "hiddenData": dmy, "field-filter-data": dmy},
                    FEED, "pe-ordem-{0}".format(dated))
                for docid, title, url in parse_pe_ordem_list(lst)[:2]:
                    det = client.get_text(url, FEED, "pe-ordem-{0}".format(docid))
                    for k, (head, ementa, authors) in enumerate(parse_pe_ordem(det), 1):
                        got.append(text_item(dated, head, ementa, "Plenário", k, mid,
                                             detail="; ".join(x for x in (title, authors) if x),
                                             url=url, item_time=ev["time"]))
            except FetchError as exc:
                gaps.append("pe: ordem do dia of {0}: {1}".format(dated, exc))
                ok = False
        items += got or [ra.item(dated, "", "Plenário", item_time=ev["time"], meeting_id=mid,
                                 detail=ev["title"], url=PE + "/ordem-do-dia/")]
        meetings.append(mid)
    return ra.RegionRead(items, _units(ctx, ok, meetings),
                         source="ALEPE agenda (lerAgendaMensal) + Ordem do Dia (lerOrdem)",
                         note="the ordem do dia is asked for plenary days in the next week",
                         gaps=gaps)


# --- Ceará: ALECE's agenda ------------------------------------------------------------

_CE_SKIP = re.compile(r"manuten[çc][ãa]o|aulas?\b|palestra|curso|treinamento|ensaio|reuni[ãa]o "
                      r"administrativa|exposi[çc][ãa]o", re.I)


def parse_ce_agenda(page):
    """ALECE's agenda -> [dict(dated, time, title, local, by)]."""
    out = []
    for block in re.split(r'<div class="page_agenda--item">', page or "")[1:]:
        hora = re.search(r'page_agenda--hora[^>]*>(.*?)</div>', block, re.S)
        when = ra.clean(hora.group(1)) if hora else ""
        title = re.search(r'page_agenda--title[^>]*>(.*?)</h2>', block, re.S)
        local = re.search(r"<b>Local:</b>(.*?)</h3>", block, re.S)
        by = re.search(r"<b>Solicitante:</b>(.*?)</h3>", block, re.S)
        out.append({"dated": ra.find_date(when), "time": _hm(when),
                    "title": _one(ra.clean(title.group(1))) if title else "",
                    "local": _one(ra.clean(local.group(1))) if local else "",
                    "by": _one(ra.clean(by.group(1))) if by else ""})
    return out


def ce_items(events, ctx):
    out = []
    for ev in events:
        if not ctx.in_window(ev["dated"]) or not ev["title"] or _CE_SKIP.search(ev["title"]):
            continue
        plenary = ev["local"].lower().startswith("plenário")
        committee = ev["by"].lower().startswith("comiss")
        if not (plenary or committee or re.search(r"audi[êe]ncia p[úu]blica|sess[ãa]o",
                                                  ev["title"], re.I)):
            continue
        body = ev["by"] if committee else "Plenário"
        title = ev["title"].rstrip(".")
        out.append(ra.item(ev["dated"], title, body, item_time=ev["time"],
                           meeting_id="ce-{0}-{1}-{2}".format(ev["dated"], (ev["time"] or "").replace(
                               ":", ""), ra.slug(body, 30)),
                           detail="; ".join(x for x in ("Local: " + ev["local"] if ev["local"] else "",
                                                        "Solicitante: " + ev["by"] if ev["by"] else "")
                                            if x) or None,
                           url=CE_AGENDA.format(""), key=ra.slug(title)))
    return out


def read_ce(client, ctx):
    rng = "{0} - {1}".format(ctx.today_date.strftime("%d/%m/%y"), ctx.until_date.strftime("%d/%m/%y"))
    page = client.get_text(CE_AGENDA.format(urllib.parse.quote(rng, safe="")), FEED, "ce-agenda")
    return ra.RegionRead(ce_items(parse_ce_agenda(page), ctx), [ra.window(ctx.today, ctx.until)],
                         source="ALECE agenda (www.al.ce.gov.br/agenda)",
                         note="solemn sessions and committee hearings; ordinary sessions' ordem "
                              "do dia is posted on the day and not read")


# --- Pará: ALEPA's Pautas do Plenário ---------------------------------------------------

def parse_pa_list(page):
    """-> [(id, dated, title)] newest first."""
    return [(i, ra.find_date(t), _one(t)) for i, t in re.findall(
        r"href='/Legislativo/DetalhesPauta\?Id=(\d+)'>([^<]+)</a>", page or "")]


_PA_ITEM = re.compile(r"^((?:PROJETO|PROPOSTA|VETO|REQUERIMENTO|MO[ÇC][ÃA]O|INDICA[ÇC][ÃA]O|"
                      r"MENSAGEM|EMENDA)\b.*?N[º°O]\s*[\d.]+/\d{4}.*)$")


def parse_pa_pauta(page):
    """DetalhesPauta -> [(heading, ementa, section)]."""
    i = (page or "").find("Você está em")
    lines = [_one(l) for l in ra.clean((page or "")[i:]).split("\n")]
    out, section, cur = [], None, None
    for line in lines:
        if not line:
            continue
        if line.startswith("Imprimir"):
            break
        m = _PA_ITEM.match(line)
        if m:
            cur = [m.group(1), "", section]
            out.append(cur)
        elif cur is not None and not cur[1]:
            cur[1] = re.sub(r"\s*\((?:Pareceres?|Avulso)[^)]*\)", "", line).strip(" .")
        elif line.isupper() and len(line) < 80:
            section, cur = line, None
    return [tuple(c) for c in out]


def read_pa(client, ctx):
    rows = parse_pa_list(client.get_text(PA_LIST, FEED, "pa-pautas"))
    items, gaps, ok, meetings = [], [], True, []
    for pid, dated, title in rows:
        if not ctx.in_window(dated):
            continue
        mid = "pa-pauta-{0}".format(pid)
        url = PA + "/Legislativo/DetalhesPauta?Id={0}".format(pid)
        got = []
        try:
            for n, (head, ementa, section) in enumerate(parse_pa_pauta(
                    client.get_text(url, FEED, "pa-pauta-{0}".format(pid))), 1):
                head = re.sub(r"\s+-\s+DEP\..*$", "", head)
                got.append(text_item(dated, head, ementa, "Plenário", n, mid, detail=section, url=url))
        except FetchError as exc:
            gaps.append("pa: pauta {0}: {1}".format(pid, exc))
            ok = False
            continue
        items += got or [ra.item(dated, "", "Plenário", meeting_id=mid, detail=title, url=url)]
        meetings.append(mid)
    return ra.RegionRead(items, _units(ctx, ok, meetings),
                         source="ALEPA Pautas do Plenário (DetalhesPauta)", gaps=gaps)


# --- the SAPL houses (Interlegis), asked in parallel ----------------------------------------

def parse_sapl_sessions(data, ctx):
    """sessaoplenaria -> [dict(id, dated, time, title, pauta)] in the window."""
    out = []
    for s in (data or {}).get("results") or []:
        dated = (s.get("data_inicio") or "")[:10]
        if not ctx.in_window(dated):
            continue
        pauta = s.get("upload_pauta") or None
        if pauta and pauta.startswith("http://"):
            pauta = "https://" + pauta[len("http://"):]
        out.append({"id": s.get("id"), "dated": dated, "time": _hm(s.get("hora_inicio")),
                    "title": _one(s.get("__str__")), "pauta": pauta,
                    "published": bool(s.get("publicar_pauta")) or bool(pauta)})
    return out


def parse_sapl_ordem(data):
    """ordemdia -> [(order, ref, ementa)] and whether more pages follow."""
    out = []
    for r in (data or {}).get("results") or []:
        s = _one(r.get("__str__"))
        m = re.search(r":\s*\d+\s*-\s*(.*?)\s+em\s+\d+ª", s)
        ref = m.group(1) if m else s
        out.append((r.get("numero_ordem"), ref, _one(r.get("observacao"))))
    nxt = ((data or {}).get("pagination") or {}).get("next_page")
    return out, bool(nxt)


def sapl_read(client, ctx, uf):
    host = SAPL_HOSTS[uf]
    data = client.get_json("https://{0}/api/sessao/sessaoplenaria/?data_inicio__gte={1}"
                           "&page_size=100".format(host, ctx.today), FEED, "sapl-{0}-sessoes".format(uf))
    items, gaps, ok, meetings, asked = [], [], True, [], 0
    for s in parse_sapl_sessions(data, ctx):
        mid = "sapl-{0}-{1}".format(uf, s["id"])
        got = []
        if s["published"] and asked < SAPL_ORDEM_CAP and not ctx.out_of_time():
            asked += 1
            try:
                od, more = parse_sapl_ordem(client.get_json(
                    "https://{0}/api/sessao/ordemdia/?sessao_plenaria={1}&page_size=100".format(
                        host, s["id"]), FEED, "sapl-{0}-ordem-{1}".format(uf, s["id"])))
                if more:
                    gaps.append("{0}: session {1}: ordem do dia longer than 100 items; the first "
                                "100 were read".format(uf, s["id"]))
                    ok = False
                for order, ref, ementa in od:
                    got.append(ra.item(s["dated"], "{0}: {1}".format(ref, ementa) if ementa else ref,
                                       "Plenário", item_time=s["time"], order=order, meeting_id=mid,
                                       detail=s["title"], reference=ref, url=s["pauta"],
                                       key="od-{0}-{1}".format(order, ra.slug(ref, 40))))
            except FetchError as exc:
                gaps.append("{0}: ordem do dia of session {1}: {2}".format(uf, s["id"], exc))
                ok = False
        elif s["published"]:
            ok = False
        items += got or [ra.item(s["dated"], "", "Plenário", item_time=s["time"], meeting_id=mid,
                                 detail=s["title"] + ("; pauta (PDF) published" if s["pauta"] else ""),
                                 url=s["pauta"])]
        meetings.append(mid)
    return ra.RegionRead(items, _units(ctx, ok, meetings),
                         source="SAPL REST API ({0}: sessaoplenaria + ordemdia)".format(host),
                         note="SAPL Crawl-delay 60 s honoured", gaps=gaps)


_SAPL_LOCK = threading.Lock()
_SAPL_CACHE = {}


def _sapl_all(client, ctx):
    """Every SAPL house read at once (each costs about a minute a request):
    {uf: RegionRead or the exception it raised}. Cached for the run."""
    key = (id(client), ctx.today, ctx.until)
    with _SAPL_LOCK:
        if key in _SAPL_CACHE:
            return _SAPL_CACHE[key]

        def one(uf):
            try:
                return sapl_read(client, ctx, uf)
            except Exception as exc:                    # noqa: BLE001 - handed to that region
                return exc

        with ThreadPoolExecutor(max_workers=len(SAPL_HOSTS)) as pool:
            got = dict(zip(SAPL_HOSTS, pool.map(one, list(SAPL_HOSTS))))
        _SAPL_CACHE.clear()
        _SAPL_CACHE[key] = got
        return got


def sapl_reader(uf):
    def read(client, ctx):
        res = _sapl_all(client, ctx)[uf]
        if isinstance(res, Exception):
            raise res
        return res
    read.__name__ = "read_sapl_" + uf
    return read


# --- the regions ---------------------------------------------------------------------

_UNREACHABLE = ("does not answer from outside Brazil (robots.txt timed out from the laptop on 16 "
                "October 2026, and from GitHub's runners on 13 October): no forward route can be read")

REGIONS = {
    "sp": ra.region("São Paulo", reader=read_sp),
    "mg": ra.region("Minas Gerais", reader=read_mg),
    "rj": ra.region("Rio de Janeiro", reader=read_rj),
    "ba": ra.region("Bahia", status="no-route", note=(
        "ALBA's own ordem do dia, pauta and committee pauta pages stop in July 2025 and point to "
        "albalegis.nopapercloud.com.br (SPL), which answers 403 to robots.txt and every page")),
    "rs": ra.region("Rio Grande do Sul", status="no-route", note="www.al.rs.gov.br " + _UNREACHABLE),
    "pr": ra.region("Paraná", reader=read_pr),
    "pe": ra.region("Pernambuco", reader=read_pe),
    "ce": ra.region("Ceará", reader=read_ce),
    "pa": ra.region("Pará", reader=read_pa),
    "sc": ra.region("Santa Catarina", status="no-route", note=(
        "ALESC's hosts answer GitHub's runners only (13 October 2026); this step runs from the "
        "laptop or the Mini, so no agenda is read")),
    "go": ra.region("Goiás", status="no-route", note=(
        "portal.al.go.leg.br/agenda?data= is one page a day (sessões solenes, palestras, "
        "committee events) with no pauta; not built this pass (56 requests a run for little "
        "business)")),
    "ma": ra.region("Maranhão", status="no-route", note=(
        "sapl.al.ma.leg.br does not answer from outside Brazil (robots.txt times out); not asked, "
        "to keep the SAPL houses inside the step's clock")),
    "am": ra.region("Amazonas", reader=sapl_reader("am")),
    "es": ra.region("Espírito Santo", status="no-route", note="www.al.es.gov.br " + _UNREACHABLE),
    "pb": ra.region("Paraíba", reader=sapl_reader("pb")),
    "rn": ra.region("Rio Grande do Norte", status="no-route", note=(
        "www.al.rn.leg.br shows session photo albums, no pauta; the Transparência Legislativa "
        "API read for bills has no agenda endpoint found (16 October 2026)")),
    "mt": ra.region("Mato Grosso", status="no-route", note=(
        "www.al.mt.gov.br answers GitHub's runners only; its SAPL (sapl.al.mt.leg.br) held "
        "nothing recent on 13 October 2026")),
    "al": ra.region("Alagoas", reader=sapl_reader("al")),
    "pi": ra.region("Piauí", reader=sapl_reader("pi")),
    "df": ra.region("Distrito Federal", status="no-route", note="www.cl.df.gov.br " + _UNREACHABLE),
    "ms": ra.region("Mato Grosso do Sul", status="no-route", note=(
        "the ordem do dia appears only as news items on www.al.ms.gov.br; the bill system "
        "(sgpl.consulta) sits behind a proof-of-work captcha, never bypassed")),
    "se": ra.region("Sergipe", status="no-route", note=(
        "al.se.leg.br (WordPress) publishes atas and audio of past sessions only; its "
        "legislative system host times out")),
    "ro": ra.region("Rondônia", reader=sapl_reader("ro")),
    "to": ra.region("Tocantins", reader=sapl_reader("to")),
    "ac": ra.region("Acre", reader=sapl_reader("ac")),
    "ap": ra.region("Amapá", status="no-route", note="www.al.ap.gov.br " + _UNREACHABLE),
    "rr": ra.region("Roraima", status="blocked", note=(
        "sapl.al.rr.leg.br answers 403 Forbidden to robots.txt and the API (13 October 2026), "
        "read as a refusal")),
}
