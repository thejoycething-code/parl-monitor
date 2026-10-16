"""Slovakia: the legislative processes on Slov-Lex (eLegislatíva), with the
inter-ministerial comment procedure (pripomienkové konanie, MPK) and the
preliminary information (predbežná informácia, PI), both open to the public
with a deadline.

Probed 16 October 2026 (docs/slovakia-scope.md, "Government consultations
and publications").

Slov-Lex was relaunched as a single-page application: www.slov-lex.sk serves
a shell, and the eLegislatíva module (www.slov-lex.sk/elegislativa-fe/)
reads its data from https://api-gateway.slov-lex.sk/internal/elegislativa,
the JSON the public pages load (no robots.txt on api-gateway.slov-lex.sk, a
404; www.slov-lex.sk's robots.txt is "Disallow:" with nothing after it). No
key, no login: the public list and detail views use these calls.

  * POST /legislativne-materialy/filter?page=1&size=1000 with
    {"datumZmenyOd": <window start>}: every legislative material whose record
    changed since the date (585 on 16 October 2026 for 92 days: 276 'LP'
    processes, 309 'LPEU' EU acts), each with its type (typNazov), number
    (LP/2026/541), title, current stage (stadium) and, when it went through
    the comment procedure, the MPK closing date (datumUkonceniaPkMpk). Pages
    start at 1. The same call with {"typKod": "PredbeznaInfo", ...} lists
    the preliminary information notices (PI/2026/245, 116 in the window),
    whose datumUkonceniaPkMpk is the deadline for public statements.
  * GET /legislativne-materialy/{LP|PI}/{year}/{n}: one process, with the
    responsible institution (zodpovednaInstitucia), the subject areas
    (oblastList) and the MPK dates. Read only for the processes still open
    for comment (MPK or VYJADRENIA, deadline today or later; at most 40 a
    run) to name the body; for the rest the ministry is read off the title
    when it names one ("Návrh vyhlášky Ministerstva dopravy ..."), and an MP's
    bill (Poslanecký návrh zákona) is filed under the MPs.

Doc types: a draft act (Zákon, Ústavný zákon, Poslanecký návrh zákona) is a
'bill_draft' until it is published in the Collection (VYHLASENE_V_ZBIERKE,
PRED_VYHLASENIM_V_ZBIERKE), then a 'law'; a government regulation, decree or
measure (Nariadenie vlády, Vyhláška, Výnos, Opatrenie) likewise a
'regulation_draft', then a 'regulation'; a non-legislative material that
went to comment (Nelegislatívny všeobecný materiál, Legislatívny zámer) is a
'consultation', one that did not a 'publication'; an information paper for
the government ('Informatívny materiál') a 'report'; a PI a 'consultation'.
closing_date is the MPK (or PI) deadline whatever the stage, so the
countdown shows only those still to come. EU acts (LPEU), international
treaties and personnel proposals are not filed.

URL: https://www.slov-lex.sk/elegislativa/legislativne-procesy/SK/LP/2026/541
(the process page, as the process's own RSS links it).
"""

from __future__ import annotations

import json
import re

from src import gov_docs as G

CC = "sk"
API = "https://api-gateway.slov-lex.sk/internal/elegislativa"
FILTER = API + "/legislativne-materialy/filter?page={0}&size={1}"
DETAIL = API + "/legislativne-materialy/{0}"
PAGE = "https://www.slov-lex.sk/elegislativa/legislativne-procesy/SK/{0}"
PAGE_SIZE = 1000
MAX_PAGES = 3
MAX_DETAILS = 40

LAW_TYPES = ("zákon", "ústavný zákon", "poslanecký návrh zákona")
RULE_TYPES = ("nariadenie vlády", "vyhláška", "výnos", "opatrenie")
CONSULT_TYPES = ("nelegislatívny všeobecný materiál", "legislatívny zámer")
REPORT_TYPES = ("informatívny materiál",)
PUBLISHED = ("VYHLASENE_V_ZBIERKE", "PRED_VYHLASENIM_V_ZBIERKE")
OPEN_STAGES = ("MPK", "VYJADRENIA")
MPS = "Poslanci Národnej rady Slovenskej republiky"

_BODY = re.compile(
    r"\b((?:Ministerstv|Úrad|Urad|Štatistick|Protimonopoln|Generáln|Kancelári|Najvyšš)"
    r"[^\W\d]*(?:\s+[^\W\d,()]+){0,8}?\s+Slovenskej\s+republiky)")


def doc_kind(typ, stage, prefix, closing):
    """The doc_type of one material, or None when it is not filed."""
    t = (typ or "").strip().lower()
    if prefix == "PI":
        return "consultation"
    if prefix != "LP":
        return None
    if t in LAW_TYPES or t.endswith("zákona"):
        return "law" if stage in PUBLISHED else "bill_draft"
    if any(t.startswith(r) for r in RULE_TYPES):
        return "regulation" if stage in PUBLISHED else "regulation_draft"
    if t in CONSULT_TYPES:
        return "consultation" if closing else "publication"
    if any(t.startswith(r) for r in REPORT_TYPES):
        return "report"
    return None


def body_from_title(title):
    m = _BODY.search(title or "")
    return G.one_line(m.group(1)) if m else None


def parse_filter(reply):
    """(total, [material dict]) from a filter reply."""
    reply = reply or {}
    return reply.get("totalElements") or 0, list(reply.get("legMaterialList") or [])


def material_entry(m, detail=None):
    """One entry from a list row (and its detail, when read); None when not filed."""
    number = m.get("cisloLegislativnehoMaterialu") or ""
    prefix = number.split("/", 1)[0]
    stage = (m.get("stadium") or {}).get("hodnota")
    closing = m.get("datumUkonceniaPkMpk")
    kind = doc_kind(m.get("typNazov"), stage, prefix, closing)
    if not kind or not number:
        return None
    body, summary = None, None
    if detail:
        body = (detail.get("zodpovednaInstitucia") or {}).get("nazov")
        areas = [o.get("nazov") for o in detail.get("oblastList") or [] if o.get("nazov")]
        if areas:
            summary = "Oblasť: " + ", ".join(areas)
        closing = detail.get("datumUkonceniaPkMpk") or closing
    if not body and (m.get("typNazov") or "").lower().startswith("poslanecký"):
        body = MPS
    body = body or body_from_title(m.get("nazov"))
    if kind in ("law", "regulation", "report", "publication"):
        closing_out = None
    else:
        closing_out = closing
    status = (m.get("stadium") or {}).get("nazov") or stage
    return G.entry("lp", number, m.get("nazov"), kind, body=body,
                   published=m.get("zaciatokStadia"), closing_date=closing_out,
                   url=PAGE.format(number), summary=summary,
                   status="{0}: {1}".format(m.get("typNazov"), status), refs=[number])


def _filter_all(client, body, label, gaps):
    out, total, page = [], 0, 1
    while page <= MAX_PAGES:
        reply = client.post_json(FILTER.format(page, PAGE_SIZE), json.dumps(body), "sk-govdocs",
                                 "lp-{0}-{1}".format(label, page))
        total, rows = parse_filter(reply)
        out += rows
        if not rows or len(out) >= total:
            break
        page += 1
    if total and len(out) < total:
        gaps.append("Slov-Lex {0}: read {1} of {2}".format(label, len(out), total))
    return out


def fetch_slovlex(client, today, log):
    start = G.window_start(today)
    gaps = []
    rows = _filter_all(client, {"datumZmenyOd": start}, "lp", gaps)
    try:
        rows += _filter_all(client, {"typKod": "PredbeznaInfo", "datumZmenyOd": start}, "pi", gaps)
    except Exception as exc:                                # noqa: BLE001
        gaps.append("Slov-Lex PI list: {0}".format(str(exc)[:160]))
    seen, entries, details = set(), [], 0
    for m in rows:
        number = m.get("cisloLegislativnehoMaterialu")
        if not number or number in seen:
            continue
        seen.add(number)
        detail = None
        stage = (m.get("stadium") or {}).get("hodnota")
        open_now = stage in OPEN_STAGES and (m.get("datumUkonceniaPkMpk") or "") >= today
        if open_now and number.split("/")[0] in ("LP", "PI") and details < MAX_DETAILS:
            details += 1
            try:
                detail = client.get_json(DETAIL.format(number), "sk-govdocs",
                                         "lp-detail-" + number.replace("/", "-"))
            except Exception as exc:                        # noqa: BLE001
                gaps.append("Slov-Lex {0} detail: {1}".format(number, str(exc)[:120]))
        e = material_entry(m, detail)
        if e:
            entries.append(e)
    note = "{0} materials changed since {1}, {2} filed, {3} details read".format(
        len(seen), start, len(entries), details)
    return G.fetched(entries, note=note, gaps=gaps)


SOURCES = (
    G.Source(code="lp", name="Slov-Lex eLegislatíva (legislative processes, MPK and PI)",
             fetch=fetch_slovlex, url=API + "/legislativne-materialy/filter"),
)
