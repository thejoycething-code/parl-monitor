"""Spain (Congreso): the enmiendas a plenary vote names (16 October 2026).

src/amendtext.py is the design; this is the Congreso's source and identifiers.
The XV legislature has been dissolved, so this reads the votes already stored;
the weekly finds nothing new until a new Congreso sits.

THE GAP. A vote on a bill's amendments is recorded as "Enmiendas presentadas
por el Grupo Parlamentario Popular en el Congreso. Enmiendas 25, 26 y 30."
under the bill's title: 445 such votes on 32 initiatives (store sha
12dfcd342515). The bill lends its areas; what the amendments say does not.

THE SOURCE. The Boletín Oficial de las Cortes Generales, Congreso series, as
the Congreso publishes it (www.congreso.es/public_oficiales/L15/CONG/BOCG/,
robots.txt allows these paths): every publication of an initiative is
numbered from its first, BOCG-15-B-84-1, -2, -3 ..., and one or more of them
is "ENMIENDAS E ÍNDICE DE ENMIENDAS AL ARTICULADO", where each amendment is
printed under "ENMIENDA NÚM. 25" with its group, the precept, the text
proposed and its JUSTIFICACIÓN. The PDFs carry a text layer.

THE LINK, by the Congreso's own identifiers: the initiative the vote was
recorded under (es_divisions.initiative_key) -> its first BOCG publication
(es_initiatives.bocg, read by tools/es_rollcalls.py) -> the same series and
number's later publications, read in turn until one is missing (at most
MAX_PUBLICATIONS) -> the amendments publications among them -> the amendment
numbers the vote names. Each number must be printed exactly once, by the group
the vote names; otherwise the vote is a gap.

Known unreadable shapes, said so up front: "Resto de las enmiendas" (the
group's amendments not voted separately: the vote names no numbers), a
"Votación en bloque", the Senate's amendments ("Enmienda al Preámbulo, parte
IV": numbered by precept in the Senate's message, not here), and amendments to
the whole bill (enmiendas a la totalidad, whose text is a whole alternative
bill). They are not candidates.

THE PURPOSE for the ledger gate: the text proposed (its opening) and the
JUSTIFICACIÓN's opening, the group's own statement of what the amendment is
for. The rest of a long replacement text is body.
"""

from __future__ import annotations

import os
import re

from src import amendtext, filter as filt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FEED = "es-amendment-text"
MAX_PUBLICATIONS = 40
PURPOSE_TEXT = 350
PURPOSE_JUSTIFICATION = 300

_VOTE = re.compile(r"^Enmiendas?\s+(?:presentadas?|al articulado)\s+(?:por\s+)?(?:(?:el|del?)\s+)?"
                   r"(?P<group>Grupo Parlamentario.+?)\.?\s+Enmiendas?\s+(?:números?\s+|núms?\.\s*)?"
                   r"(?P<nums>\d+(?:\s*(?:,|y)\s*\d+)*)\s*\.?\s*$", re.I)
_BOCG = re.compile(r"/public_oficiales/L(?P<leg>\d+)/CONG/BOCG/(?P<ser>[A-Z])/BOCG-(?P=leg)-(?P=ser)-(?P<num>\d+)-\d+\.PDF",
                   re.I)
_ENMIENDA = re.compile(r"ENMIENDA\s+N[ÚU]M\.\s*(?P<n>\d+)\b")
_HEADER = re.compile(r"BOLETÍN OFICIAL DE LAS CORTES GENERALES\s*\n?CONGRESO DE LOS DIPUTADOS\s*\n?Serie [A-Z] "
                     r"Núm\. [\d-]+ [^\n]*\n?cve: BOCG-[\w-]+\s*|=====PAGE\s*", re.I)


def refs_of(row):
    """[initiative key, group, '25', '26', ...] for a vote naming amendment numbers, else []."""
    sub = " ".join((row.get("subgroup") or "").split())
    m = _VOTE.match(sub)
    if not m or not row.get("initiative_key"):
        return []
    nums = [str(int(x)) for x in re.split(r"\s*(?:,|y)\s*", m.group("nums")) if x.strip().isdigit()]
    return [row["initiative_key"], m.group("group").strip()] + nums


def split_amendments(text):
    """{number: block} of an amendments publication, page furniture removed."""
    text = _HEADER.sub("\n", text or "")
    marks = list(_ENMIENDA.finditer(text))
    out = {}
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        out.setdefault(m.group("n"), []).append(text[m.start():end].strip())
    return out


def _fold(s):
    import unicodedata
    t = unicodedata.normalize("NFKD", s or "")
    return " ".join("".join(c for c in t if not unicodedata.combining(c)).lower().split())


def purpose_of(block):
    t = " ".join((block or "").split())
    prop = re.search(r"Texto que se propone\s*:?\s*(.*?)(?:JUSTIFICACI[ÓO]N|$)", t, re.I)
    just = re.search(r"JUSTIFICACI[ÓO]N\s*:?\s*(.*)$", t, re.I)
    return " ".join(x for x in ((prop.group(1)[:PURPOSE_TEXT] if prop else ""),
                                (just.group(1)[:PURPOSE_JUSTIFICATION] if just else "")) if x)


class SpainReader(amendtext.Reader):
    cc, table, key_col = "es", "es_divisions", "division_key"

    def __init__(self, client):
        self.client = client
        self._tax = None
        self._pubs = {}

    def taxonomy(self):
        if self._tax is None:
            import importlib.util
            spec = importlib.util.spec_from_file_location("es_rollcalls_for_amendtext",
                                                          os.path.join(ROOT, "tools", "es_rollcalls.py"))
            es = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(es)
            tax = es.load_taxonomy() or filt.Taxonomy(version="none", terms={}, exclusions=set())
            self._tax = (tax, es.empty_watchlist(), None)
        return self._tax

    def candidates(self, conn):
        rows = conn.execute(
            "SELECT d.division_key, d.date, d.title, d.subgroup, d.areas, d.initiative_key, i.bocg "
            "FROM es_divisions d LEFT JOIN es_initiatives i USING (initiative_key) "
            "WHERE d.subgroup LIKE 'Enmienda%' ORDER BY d.date, d.division_key")
        out = []
        for r in rows:
            d = dict(zip(("key", "date", "bill", "subgroup", "areas", "initiative_key", "bocg"), r))
            d["title"] = "{0} {1}".format(d["bill"] or "", d["subgroup"] or "").strip()
            out.append(d)
        return out

    def refs(self, row):
        return refs_of(row)

    def _amendment_pubs(self, bocg):
        """[(url, {number: [block]})] for the amendments publications of the
        initiative whose first publication is `bocg`."""
        m = _BOCG.search(bocg or "")
        if not m:
            raise ValueError("no BOCG publication recorded for the initiative")
        base = "https://www.congreso.es/public_oficiales/L{0}/CONG/BOCG/{1}/BOCG-{0}-{1}-{2}-{{0}}.PDF".format(
            m.group("leg"), m.group("ser").upper(), m.group("num"))
        if base in self._pubs:
            return self._pubs[base]
        from src.prov_fetch import pdf_text
        out = []
        for k in range(1, MAX_PUBLICATIONS + 1):
            url = base.format(k)
            try:
                raw = self.client.get_bytes(url, FEED, "bocg-{0}".format(url.rsplit("/", 1)[-1]), archive=False)
            except Exception as exc:                    # noqa: BLE001
                if "404" in str(exc):
                    break
                raise
            if raw[:5] != b"%PDF-":
                break                                   # past the last publication: an HTML not-found page
            text = pdf_text(raw)
            if re.search(r"ENMIENDAS\s+E\s+[ÍI]NDICE\s+DE\s+ENMIENDAS|ENMIENDA\s+N[ÚU]M\.", text[:3000], re.I):
                out.append((url, split_amendments(text)))
        self._pubs[base] = out
        return out

    def fetch(self, row, refs):
        key, group, nums = refs[0], refs[1], refs[2:]
        try:
            pubs = self._amendment_pubs(row.get("bocg"))
        except Exception as exc:                        # noqa: BLE001 - fail loud
            return amendtext.unreadable(refs, "BOCG of {0}: {1}".format(key, str(exc)[:140]))
        if not pubs:
            return amendtext.unreadable(refs, "no amendments publication among the BOCG of {0}".format(key))
        texts, missing = [], []
        # the group's first word ("popular", "vox", "mixto", "junts"): the
        # BOCG prints "Grupo Parlamentario Mixto" or the member's name with it
        gkey = (_fold(group).replace("grupo parlamentario", "").split() or [""])[0].strip("().,")
        for n in nums:
            hits = [(url, b) for url, blocks in pubs for b in blocks.get(n, [])]
            mine = [(url, b) for url, b in hits if gkey and gkey in _fold(b[:200])]
            if len(mine) != 1:
                missing.append("{0} ({1} printed, {2} by the {3})".format(n, len(hits), len(mine), group))
                continue
            url, block = mine[0]
            texts.append(amendtext.entry("enmienda {0}".format(n), "enmienda", "{0} enmienda {1}".format(key, n),
                                         url, purpose_of(block), block))
        if not texts:
            return amendtext.unreadable(refs, "amendment(s) {0} of {1} not found once in its BOCG".format(
                "; ".join(missing), key))
        lk = amendtext.Lookup("ok", refs=refs, texts=texts)
        if missing:
            lk.reason = "partly read; missing {0}".format("; ".join(missing))
        return lk


def make_reader(client):
    return SpainReader(client)
