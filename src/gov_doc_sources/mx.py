"""Mexico: the Diario Oficial de la Federación (DOF), through SIDOF's
documented web service.

Probed 16 October 2026. www.dof.gob.mx answers the laptop with a certificate
for another host (hostname mismatch), so it is not read; the DOF's own
information system, sidof.segob.gob.mx, answers from the UK and documents a
keyless JSON web service on its "Datos abiertos" page
(https://sidof.segob.gob.mx/datos_abiertos, "Consumo de WebServices",
service "Notas", manual at /datos_abiertos/getPDF/57):

  * GET /dof/sidof/notas/{dd-mm-yyyy}: every note of every edition of that
    day (matutina, vespertina, extraordinaria): codNota, titulo, the issuing
    branch (codOrgaUno: PE executive, OD decentralised bodies, OA
    autonomous bodies, PL legislature, PJ judiciary, CV/AV tenders and
    notices) and the issuing secretariat (codOrgaDos). 60 to 175 notes a
    weekday, none at weekends.
  * GET /dof/sidof/notas/nota/{codNota}: one note with its full HTML text
    (cadenaContenido).

robots.txt (sidof.segob.gob.mx) disallows /CopiasCert? and about a hundred
single /notas/<id> pages (court-ordered withdrawals, presumably); neither
path above is disallowed. Each run reads the last DAYS (62) days, one
request a day (about 90 s), so every draft still open for comment is listed
in every run.

What is kept: notes of the executive, decentralised and autonomous bodies,
the legislature and the judiciary that carry a title (tenders, court and
general notices, CV/AV, are left out). doc_type from the title: a decree
that issues or amends a law is a 'law'; "Aviso de consulta pública del
Proyecto de Norma Oficial Mexicana" (and any other "Proyecto de ...") is a
'regulation_draft'; agreements, regulations, guidelines and NOMs are
'regulation'; everything else (notices, agreements with states, codes of
conduct) a 'publication'.

DEADLINES. A draft NOM is open for comment "dentro de los 60 días naturales
contados a partir del día de su publicación" (Ley de Infraestructura de la
Calidad, art. 35 V and 38). The listing has no date, so each draft's own
note is read (at most DETAIL_CAP a run) and the closing date computed from
the period it states: N natural days counted from the day of publication
(day one) closes on publication + N - 1; counted from the following day,
publication + N. A period in working days (días hábiles) is not computed:
the row is kept without a closing date and the status says so.

Not covered: CONAMER's consultation of draft regulations. Its portal
(cofemersimir.gob.mx) does not resolve from the UK, and since February 2026
it is an archive; the platform that replaced it was not found on gob.mx.
"""

from __future__ import annotations

import datetime
import re

from src import gov_docs as G

CC = "mx"
HOST = "https://sidof.segob.gob.mx"
DAY = HOST + "/dof/sidof/notas/{0}"
NOTE = HOST + "/dof/sidof/notas/nota/{0}"
PAGE = HOST + "/notas/{0}"
DAYS = 62            # a draft NOM is open 60 natural days: every open one is listed each run
DETAIL_CAP = 40
EDITIONS = (("NotasMatutinas", "matutina"), ("NotasVespertinas", "vespertina"),
            ("NotasExtraordinarias", "extraordinaria"))
KEEP_BRANCHES = {"PE", "OD", "OA", "PL", "PJ"}
BRANCH_NAMES = {"PL": "Poder Legislativo", "PJ": "Poder Judicial"}

DRAFT = re.compile(r"(?i)^(aviso de consulta p[uú]blica del )?proyecto\b")
LAW = re.compile(r"(?i)^decreto\b.*\b(ley|c[oó]digo|constituci[oó]n)\b")
REG = re.compile(r"(?i)^(acuerdo|reglamento|lineamientos?|norma oficial|nom-|reglas|decreto|"
                 r"resoluci[oó]n|disposiciones|circular|manual|criterios|modificaci[oó]n)")


SMALL = {"de", "la", "del", "los", "las", "y", "e", "en", "para", "por", "el", "a"}


def nice(name):
    """'SECRETARIA DE SALUD' -> 'Secretaria de Salud'."""
    words = (name or "").lower().split()
    return " ".join(w if (i and w in SMALL) else w[:1].upper() + w[1:] for i, w in enumerate(words))


def doc_type(title):
    t = (title or "").strip()
    if DRAFT.search(t):
        return "regulation_draft"
    if LAW.search(t):
        return "law"
    if REG.search(t):
        return "regulation"
    return "publication"


def parse_day(reply, day=None):
    """Entries from one /notas/{fecha} reply."""
    out = []
    if not isinstance(reply, dict):
        return out
    for key, edition in EDITIONS:
        for n in reply.get(key) or []:
            title = G.one_line(n.get("titulo"))
            branch = n.get("codOrgaUno")
            if not title or branch not in KEEP_BRANCHES or n.get("codNota") is None:
                continue
            body = G.one_line(n.get("codOrgaDos")) or BRANCH_NAMES.get(branch) \
                or G.one_line(n.get("nombreCodOrgaUno"))
            out.append(G.entry("dof", n["codNota"], title, doc_type(title),
                               body=nice(body) if body and body.isupper() else body,
                               published=n.get("fecha") or day,
                               url=PAGE.format(n["codNota"]),
                               status="DOF, edición {0}".format(edition)))
    return out


def note_text(reply):
    """The plain text of one /notas/nota/{codNota} reply."""
    nota = (reply or {}).get("Nota") or {} if isinstance(reply, dict) else {}
    raw = nota.get("cadenaContenido") or ""
    raw = re.sub(r"(?is)<(script|style|title)[^>]*>.*?</\1>", " ", raw)
    return G.text(raw)


PERIOD = re.compile(r"(?i)(?:dentro de|plazo de)\s+(?:los\s+)?(?:[a-záéíóú]+\s+)?\(?(\d{1,3})\)?\s+"
                    r"d[ií]as\s+(naturales|h[aá]biles)(.{0,160})")


def closing_from_text(text, published):
    """(closing ISO date or None, status note) from a draft's own words."""
    m = PERIOD.search(text or "")
    if not m or not published:
        return None, None
    days, kind, rest = int(m.group(1)), m.group(2).lower(), m.group(3).lower()
    if not kind.startswith("natural"):
        return None, "{0} días hábiles para comentarios (no fecha calculada)".format(days)
    pub = datetime.date.fromisoformat(published)
    following = "siguiente" in rest.split("public")[0]
    close = pub + datetime.timedelta(days=days if following else days - 1)
    return close.isoformat(), "{0} días naturales para comentarios".format(days)


def summary_from_text(text, title):
    """The note's text after the title it repeats at its head, capped."""
    t = G.one_line(text)
    core = (title or "").strip().rstrip(".").strip()
    for _ in range(4):
        t = t.lstrip(" .-")
        if core and t.lower().startswith(core.lower()):
            t = t[len(core):]
        else:
            break
    return G.one_line(t.lstrip(" .-"))[:G.SUMMARY_CAP] or None


def fetch(client, today, log=print):
    end = datetime.date.fromisoformat(today)
    entries, gaps, days_read = [], [], 0
    for i in range(DAYS):
        d = end - datetime.timedelta(days=i)
        stamp = d.strftime("%d-%m-%Y")
        try:
            reply = client.get_json(DAY.format(stamp), "mx-govdocs", "dof-" + d.isoformat())
        except Exception as exc:                        # noqa: BLE001
            gaps.append("DOF notes for {0} unreadable: {1}".format(d.isoformat(), str(exc)[:120]))
            continue
        days_read += 1
        entries += parse_day(reply, stamp)
    read = 0
    for e in entries:
        if e["doc_type"] not in G.DEADLINE_TYPES or e.get("closing_date"):
            continue
        if read >= DETAIL_CAP:
            log("  {0}-govdocs: more than {1} drafts; the rest kept without a closing "
                "date".format(CC, DETAIL_CAP))
            break
        read += 1
        code = e["doc_id"].split(":", 1)[1]
        try:
            reply = client.get_json(NOTE.format(code), "mx-govdocs", "dof-nota-" + code)
        except Exception as exc:                        # noqa: BLE001
            log("  mx-govdocs: note {0} unreadable: {1}".format(code, str(exc)[:100]))
            continue
        text = note_text(reply)
        close, status = closing_from_text(text, e["published"])
        e["closing_date"] = close
        if status:
            e["status"] = "{0}; {1}".format(e["status"], status)
        e["summary"] = e["summary"] or summary_from_text(text, e["title"])
    if not days_read:
        return G.fetched([], gaps=gaps or ["no DOF day readable"])
    return G.fetched(entries, gaps=gaps, note="DOF notes of the last {0} days ({1} read), {2} draft "
                     "note(s) read for their comment period".format(DAYS, days_read, read))


SOURCES = (
    G.Source(code="dof", name="Diario Oficial de la Federación (SIDOF web service)",
             url="https://sidof.segob.gob.mx/datos_abiertos", fetch=fetch),
)
