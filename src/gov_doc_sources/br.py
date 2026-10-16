"""Brazil: federal laws, provisional measures and decrees (the Senate's
documented legislation API) and the Brasil Participativo consultations,
mirrored.

Probed 16 October 2026.

THE DIÁRIO OFICIAL DA UNIÃO IS NOT READ. www.in.gov.br's robots.txt is
"User-agent: * / Disallow: /" (it disallows even its own robots.txt), and
INLABS (inlabs.in.gov.br, the Imprensa Nacional's XML dumps of the DOU)
answers "Request Rejected" from a WAF and needs an account besides. Neither
is touched. A GitHub runner would not change a robots.txt refusal.

THE LEGITIMATE ROUTE for the acts themselves: the Senate's Dados Abertos
legislation service (legis.senado.leg.br/dadosabertos/legislacao/lista.json,
documented at legis.senado.leg.br/dadosabertos/docs/, in
src/robots_guard.DOCUMENTED_APIS), which lists every federal norm with its
ementa (the official one-sentence summary) and its signature date, by year
and type: LEI (ordinary laws, about 200 so far in 2026), LCP
(complementary laws), MPV (medidas provisórias, in force on signature and
the government's main instrument between bills), EMC (constitutional
amendments) and DEC (numbered decrees). Signature and DOU publication fall
on the same day or the next. One request per type and year; the previous
year is read too in the first months of a year so the window holds. Not
covered: ministries' portarias and resoluções, which only the DOU carries.

doc_type: LEI, LCP and EMC are 'law'; MPV (law-force from signature,
needing Congress within 120 days) is 'law' too, its status saying
"Medida Provisória"; DEC is 'regulation'.

CONSULTATIONS. Brasil Participativo (brasilparticipativo.presidencia.gov.br,
Decidim GraphQL) is read every week by the petitions step
(src/petition_sources/br.py, source 'bp', kind 'consultation'); its rows are
mirrored here. Participa + Brasil is closed (see docs/brazil-scope.md).
"""

from __future__ import annotations

import datetime

from src import gov_docs as G
from src.gov_doc_sources._petitions_mirror import mirror_for

CC = "br"
API = "https://legis.senado.leg.br/dadosabertos/legislacao/lista.json?ano={0}&tipo={1}"
PAGE = "https://legis.senado.leg.br/norma/{0}"
TYPES = (("LEI", "law", "Lei"), ("LCP", "law", "Lei Complementar"),
         ("MPV", "law", "Medida Provisória"), ("EMC", "law", "Emenda Constitucional"),
         ("DEC", "regulation", "Decreto"))
BODIES = {"LEI": "Presidência da República (lei sancionada)",
          "LCP": "Presidência da República (lei complementar sancionada)",
          "MPV": "Presidência da República", "EMC": "Congresso Nacional",
          "DEC": "Presidência da República"}


def parse_list(reply, code):
    """Entries from one legislacao/lista.json reply."""
    kind, label = next(((k, l) for c, k, l in TYPES if c == code), ("law", code))
    docs = (((reply or {}).get("ListaDocumento") or {}).get("documentos") or {}).get("documento") or []
    if isinstance(docs, dict):
        docs = [docs]
    out = []
    for d in docs:
        if not d.get("id") or not d.get("normaNome"):
            continue
        out.append(G.entry("legis", d.get("norma") or d["id"], d["normaNome"], kind,
                           body=BODIES.get(code), published=d.get("dataassinatura"),
                           url=PAGE.format(d["id"]), summary=d.get("ementa"),
                           status=d.get("descricao") or label,
                           refs=[d.get("norma")] if d.get("norma") else ()))
    return out


def years(today):
    d = datetime.date.fromisoformat(today)
    start = datetime.date.fromisoformat(G.window_start(today))
    return sorted({d.year, start.year}, reverse=True)


def fetch(client, today, log=print):
    entries, gaps = [], []
    for year in years(today):
        for code, _, _ in TYPES:
            try:
                reply = client.get_json(API.format(year, code), "br-govdocs",
                                        "legis-{0}-{1}".format(code, year))
            except Exception as exc:                    # noqa: BLE001
                gaps.append("legislation list {0} {1} unreadable: {2}".format(code, year,
                                                                              str(exc)[:110]))
                continue
            entries += parse_list(reply, code)
    return G.fetched(entries, gaps=gaps, note="federal laws, MPs, amendments and decrees of {0}".format(
        "/".join(str(y) for y in years(today))))


SOURCES = (
    G.Source(code="legis", name="Federal legislation (Senado Dados Abertos: laws, MPs, decrees)",
             url="https://legis.senado.leg.br/dadosabertos/legislacao/lista", fetch=fetch),
    G.Source(code="bp", name="Brasil Participativo consultations (mirrored)",
             url="https://brasilparticipativo.presidencia.gov.br/",
             mirror=mirror_for("bp", "consultation", body="Governo federal (Brasil Participativo)")),
)
