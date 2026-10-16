"""Colombia: draft decrees and resolutions open for comment on SUCOP,
mirrored.

The Sistema Único de Consulta Pública (www.sucop.gov.co, SharePoint REST)
is read every week by the petitions step (src/petition_sources/co.py,
source 'sucop'): each row is a ministry's or agency's draft decree or
resolution with its comment window. They are re-filed here as
'regulation_draft' rows, the window's end as the closing date (Bogotá
date), the ministry from the draft's own path, so the countdown has one
place to look.

Probed 16 October 2026, not used:
  * the Diario Oficial (www.diariooficial.gov.co does not resolve; the
    Imprenta Nacional's svrpubindc.imprenta.gov.co has no robots.txt, but no
    listing of the day's acts was found that answers without a script);
  * the Presidency's decree pages (dapre.presidencia.gov.co/normativa/...):
    robots.txt and the listing both came back empty (0 bytes);
  * Función Pública's Gestor Normativo (robots.txt allows everything): its
    search (dafpIndexerBGN/norma/index) answers a 4 KB shell filled by
    script.

No edition of its own: Colombia is in the monthly Latam edition, classified
with taxonomy-es for Colombia, as its petitions are.
"""

from __future__ import annotations

from src import gov_docs as G
from src.gov_doc_sources._petitions_mirror import mirror_for

CC = "co"
TAXONOMIES = (("taxonomy-es.yaml", "co"),)

SOURCES = (
    G.Source(code="sucop", name="SUCOP draft regulations (mirrored)",
             url="https://www.sucop.gov.co/", mirror=mirror_for("sucop", "regulation_draft")),
)
