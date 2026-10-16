"""Netherlands: the amendment or motion a Tweede Kamer vote is on (16 October 2026).

src/amendtext.py is the design; this is the Tweede Kamer's source and
identifiers.

THE GAP. A Dutch vote is on a zaak (nl_zaken), and the collector matches its
onderwerp. A motion's onderwerp is a summary ("Motie van het lid X over ..."),
so motions mostly read already. An amendment's onderwerp often says nothing
("Amendement van het lid X over een concretisering van de motiveringsplicht",
"... ter vervanging van nr. 12"), and the change it makes, and why, sit in
the document: 2,317 of the 2,580 amendment zaken carried no area (store sha
12dfcd342515, 16 October 2026).

THE SOURCE. The Tweede Kamer's documented OData API
(gegevensmagazijn.tweedekamer.nl/OData/v4/2.0/, keyless, in
robots_guard.DOCUMENTED_APIS like the collector's own reads; the host's
robots.txt answers 500): the zaak by its Nummer with its Documents expanded,
then the document's own file (Document(<id>)/resource), a Word file for
recent documents and a PDF for some older ones.

THE LINK, by the Kamer's own identifiers: the zaak number the vote was
recorded on (nl_divisions.zaak_nummer) -> that zaak's documents of the
zaak's own kind (Amendement / Gewijzigd amendement / Nader gewijzigd
amendement; Motie / Gewijzigde motie / Motie (gewijzigd)) -> the latest such
document dated on or before the zaak's last vote (a vote is on the text as it
then stood). No document of that kind, or two latest versions on the same
day, is a gap.

The cache and the apply are PER ZAAK, not per besluit: amendment_text's
division_key is the zaak number, because one text can be voted several times
(a besluit to postpone, then the vote). The apply unions the areas, terms and
tier 1 into nl_zaken (where the NL 5CA spec reads tier) and the areas into
every nl_divisions row on that zaak.

THE PURPOSE for the ledger gate:
  * a motion: its operative words, from "verzoekt", "spreekt uit", "draagt ...
    op" or "roept ... op" to the end. The considerans ("constaterende dat",
    "overwegende dat") is context: a motion on housing that notes in passing
    that a law on euthanasia was evaluated is not a euthanasia motion.
  * an amendment: the opening of its Toelichting (the member's own statement
    of what the change is for) and the first lines of the operative change.
"""

from __future__ import annotations

import json
import os
import re
from urllib.parse import quote

from src import amendtext, filter as filt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "https://gegevensmagazijn.tweedekamer.nl/OData/v4/2.0/"
FEED = "nl-amendment-text"
PURPOSE_TOELICHTING = 450
PURPOSE_CHANGE = 250

# A document of the zaak's own kind, original or reworded: the portal writes
# "Amendement", "Amendement (gewijzigd/nader/vervangend)", "Gewijzigd
# amendement", "Motie", "Motie (gewijzigd/nader)", "Gewijzigde motie".
KINDS = {
    "Amendement": re.compile(r"^(?:(?:nader\s+)?gewijzigd\s+)?amendement\b", re.I),
    "Motie": re.compile(r"^(?:(?:nader\s+)?gewijzigde\s+)?motie\b", re.I),
}
_OPERATIVE = re.compile(r"\b(verzoekt|spreekt\s+(?:als\s+haar\s+mening\s+)?uit|draagt\b.{0,60}?\bop|"
                        r"roept\b.{0,60}?\bop|zegt\b.{0,80}?\bop|keurt\b.{0,80}?\baf|besluit|wijst\b.{0,40}?\baf)\b", re.I | re.S)
_TAIL = re.compile(r"\s*en gaat over tot de orde van de dag\.?.*$", re.I | re.S)
_TOELICHTING = re.compile(r"^\s*Toelichting\s*$", re.I | re.M)
_CHANGE = re.compile(r"(?:stelt het volgende amendement voor|stellen het volgende amendement voor)\s*:?\s*",
                     re.I)


def document_text(raw, content_type=""):
    """Plain text of a document file: Word (docx) or PDF."""
    if raw[:2] == b"PK":
        from src.au_states_votes import docx_paragraphs
        return "\n".join(p for p in docx_paragraphs(raw) if p and p.strip())
    if raw[:5] == b"%PDF-":
        from src.prov_fetch import pdf_text
        return pdf_text(raw)
    raise ValueError("not a Word file or a PDF ({0}, {1} bytes)".format(content_type or "?", len(raw)))


def motion_parts(text):
    """(considerans, operative) of a motion's text."""
    body = _TAIL.sub("", text or "")
    m = _OPERATIVE.search(body)
    if not m:
        return body, ""
    return body[:m.start()], body[m.start():].strip()


def amendment_parts(text):
    """(operative change, toelichting) of an amendment's text."""
    t = text or ""
    m = _TOELICHTING.search(t)
    change, expl = (t[:m.start()], t[m.end():]) if m else (t, "")
    c = _CHANGE.search(change)
    if c:
        change = change[c.end():]
    return change.strip(), expl.strip()


def _opening(text, n):
    text = " ".join((text or "").split())
    if len(text) <= n:
        return text
    cut = text.rfind(". ", 0, n)
    return text[:cut + 1] if cut > n // 3 else text[:n]


class NetherlandsReader(amendtext.Reader):
    cc, table, key_col = "nl", "nl_zaken", "zaak_nummer"
    version = "1"

    def __init__(self, client):
        self.client = client
        self._tax = None

    def taxonomy(self):
        if self._tax is None:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "nl_rollcalls_for_amendtext", os.path.join(ROOT, "tools", "nl_rollcalls.py"))
            nl = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(nl)
            self._tax = (nl.load_taxonomy(nl.TAXONOMY, log=lambda *a: None), nl.empty_watchlist(), None)
        return self._tax

    def candidates(self, conn):
        rows = conn.execute(
            "SELECT z.zaak_nummer, MAX(d.date), z.soort, z.onderwerp, z.areas FROM nl_zaken z "
            "JOIN nl_divisions d USING (zaak_nummer) WHERE z.soort IN ('Amendement', 'Motie') "
            "GROUP BY z.zaak_nummer ORDER BY MAX(d.date) DESC, z.zaak_nummer")
        return [{"key": r[0], "date": r[1], "soort": r[2], "title": "{0}: {1}".format(r[2], r[3] or ""),
                 "areas": r[4]} for r in rows]

    def refs(self, row):
        return [row["key"]] if row.get("soort") in KINDS else []

    def fetch(self, row, refs):
        nummer, soort = row["key"], row["soort"]
        url = "{0}Zaak?$filter=Nummer%20eq%20'{1}'&$expand=Document($select=Id,Soort,DocumentNummer," \
              "Volgnummer,Datum,ContentType,Verwijderd)".format(BASE, quote(nummer))
        try:
            zaken = (self.client.get_json(url, FEED, "zaak-{0}".format(nummer), archive=False) or {}).get("value") or []
        except Exception as exc:                        # noqa: BLE001 - fail loud
            return amendtext.unreadable(refs, "OData zaak {0}: {1}".format(nummer, str(exc)[:120]))
        if len(zaken) != 1:
            return amendtext.unreadable(refs, "OData returned {0} zaken numbered {1}".format(len(zaken), nummer))
        date = (row.get("date") or "")[:10]
        docs = [d for d in zaken[0].get("Document") or []
                if not d.get("Verwijderd") and KINDS[soort].match((d.get("Soort") or "").strip())
                and (d.get("Datum") or "")[:10] <= (date or "9999")]
        if not docs:
            return amendtext.unreadable(refs, "zaak {0} has no {1} document dated on or before its vote of "
                                              "{2}".format(nummer, soort.lower(), date or "?"))
        docs.sort(key=lambda d: ((d.get("Datum") or "")[:10], d.get("Volgnummer") or 0))
        doc = docs[-1]
        same = [d for d in docs if (d.get("Datum") or "")[:10] == (doc.get("Datum") or "")[:10]
                and d.get("Soort") != doc.get("Soort")]
        if same:
            return amendtext.unreadable(refs, "zaak {0}: two versions dated {1} ({2}); which was voted is "
                                              "not said".format(nummer, (doc.get("Datum") or "")[:10],
                                                                ", ".join(d.get("Soort") for d in [doc] + same)))
        res = "{0}Document({1})/resource".format(BASE, doc["Id"])
        try:
            raw = self.client.get_bytes(res, FEED, "doc-{0}".format(doc.get("DocumentNummer")), archive=False)
            text = document_text(raw, doc.get("ContentType"))
        except Exception as exc:                        # noqa: BLE001
            return amendtext.unreadable(refs, "document {0} of zaak {1}: {2}".format(
                doc.get("DocumentNummer"), nummer, str(exc)[:120]))
        if soort == "Motie":
            # No operative verb found: the text is read and matched, but
            # with no purpose of its own it can only go to review.
            purpose, limit = motion_parts(text)[1], amendtext.OPERATIVE_CHARS
        else:
            change, expl = amendment_parts(text)
            limit = amendtext.PURPOSE_CHARS
            purpose = " ".join(x for x in (_opening(expl, PURPOSE_TOELICHTING),
                                           _opening(change, PURPOSE_CHANGE)) if x)
        public = "https://www.tweedekamer.nl/kamerstukken/detail?id={0}&did={1}".format(
            zaken[0].get("Nummer"), doc.get("DocumentNummer"))
        return amendtext.Lookup("ok", refs=refs + [doc.get("DocumentNummer")], texts=[amendtext.entry(
            "{0} {1}".format((doc.get("Soort") or soort).lower(), doc.get("DocumentNummer")),
            soort.lower(), doc.get("DocumentNummer"), public, purpose, text, purpose_chars=limit)])

    def apply(self, conn, row, result):
        changed = amendtext.apply_columns(conn, "nl_zaken", "zaak_nummer", row["key"], result)
        for (bid,) in conn.execute("SELECT besluit_id FROM nl_divisions WHERE zaak_nummer=?",
                                   (row["key"],)).fetchall():
            changed = amendtext.apply_columns(conn, "nl_divisions", "besluit_id", bid, result,
                                              terms_col=None, tier_col=None) or changed
        return changed


def make_reader(client):
    return NetherlandsReader(client)
