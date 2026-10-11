"""Portugal: petitions to the Assembleia da República.

Probed 11 October 2026. The Assembleia's open data (the same site and
folder pattern tools/pt_rollcalls.py reads): DAPeticoes.aspx links a folder
per legislature, the folder links PeticoesXVII_json.txt behind an opaque
path token, so both pages are read each run to find it. One JSON array (237
petitions in the XVII legislature) with the number, subject (PetAssunto),
date received, signature count (PetNrAssinaturas), status (PetSituacao) and
the committee handling it. No closing date: a petition is open until the
committee concludes it. Petitions already 'Concluída' or 'Retirada' are not
stored. No robots.txt on either host.

THRESHOLDS (Lei 43/90 as amended by Lei 63/2020; checked against the
Assembleia's consolidated text on 11 October 2026): over 1,000 signatures,
the petitioners must be heard by the committee (art. 21(1)) and the petition
is published in the Diário (art. 26(1)(a)); over 2,500, it is debated in the
committee (art. 24-A); over 7,500, in plenary (art. 24(1)(a)). The petition
itself is never voted on.

Not covered: ConsultaLEX (the government's consultations) is driven by
postbacks with no item addresses and listed none open on 11 October;
citizens' legislative initiatives (20,000 signatures) arrive as bills in
the Portuguese store (pt_rollcalls), three in this legislature.
"""

from __future__ import annotations

import html
import json
import re

from src import petitions as P

CC = "pt"
SITE = "https://www.parlamento.pt"
PAGE = SITE + "/Cidadania/Paginas/DAPeticoes.aspx"
LEG = "XVII"
ITEM = SITE + "/ActividadeParlamentar/Paginas/DetalhePeticao.aspx?BID={0}"
CLOSED = ("Concluída", "Concluida", "Retirada", "Arquivada")
THRESHOLDS = (
    (1000, "petitioners heard by the committee, published in the Diário"),
    (2500, "debated in the committee"),
    (7500, "debated in plenary"),
)

_ANCHOR = re.compile(r'<a [^>]*href="([^"]+)"[^>]*>([^<]{0,160})', re.I)


def anchors(page):
    return [(html.unescape(h), html.unescape(t).strip()) for h, t in _ANCHOR.findall(page or "")]


def folder_link(page, leg=LEG):
    for href, text in anchors(page):
        if text == "{0} Legislatura".format(leg) and "Path=" in href:
            return href if href.startswith("http") else SITE + href
    return None


def json_link(page, leg=LEG):
    want = "Peticoes{0}_json.txt".format(leg)
    for href, text in anchors(page):
        if "webutils/docs/" in href and text == want:
            return href
    return None


def parse_petitions(rows):
    out = []
    for r in rows or []:
        status = (r.get("PetSituacao") or "").strip()
        if status.startswith(CLOSED):
            continue
        committee = None
        for c in r.get("DadosComissao") or []:
            committee = (c.get("Nome") or "").strip() or committee
        out.append(P.entry("ar", "{0}/{1}".format(r.get("PetLeg") or LEG, r.get("PetNr")),
                           r.get("PetAssunto"), kind="petition", status=status,
                           opened=r.get("PetDataEntrada"), signatures=r.get("PetNrAssinaturas"),
                           body=committee, url=ITEM.format(r.get("PetId"))))
    return out


def fetch(client, today, log=print):
    try:
        page = client.get_text(PAGE, "pt-petitions", "page", archive=False)
        folder = folder_link(page)
        if not folder:
            raise ValueError("no '{0} Legislatura' folder on DAPeticoes".format(LEG))
        listing = client.get_text(folder, "pt-petitions", "folder", archive=False)
        url = json_link(listing)
        if not url:
            raise ValueError("the folder lists no Peticoes{0}_json.txt".format(LEG))
        raw = client.get_bytes(url, "pt-petitions", "peticoes-" + LEG, timeout=300)
        rows = json.loads(raw.decode("utf-8-sig"))
    except Exception as exc:                        # noqa: BLE001
        return P.fetched([], gaps=["petitions dataset unreadable: {0}".format(str(exc)[:140])])
    got = parse_petitions(rows)
    return P.fetched(got, note="{0} petitions in the legislature, {1} not concluded".format(
        len(rows), len(got)))


SOURCES = (
    P.Source(code="ar", name="Assembleia da República petitions", kind="petition",
             fetch=fetch, thresholds=THRESHOLDS),
)
