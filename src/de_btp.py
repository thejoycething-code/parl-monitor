"""Plenary protocols WITHOUT a DIP key: the Bundestag's own PDF route.

Christopher, 26 September 2026: "Build it" -- the keyless fallback surveyed
in docs/germany-scope.md, for the day DIP refuses us. We are not on it
today: src/dip.py reads the key the Bundestag publishes in its own spec and
that works. This is the spare.

THE ROUTE. `www.bundestag.de/ajax/filterlist/.../plenarprotokolle/...`
answers plain curl with no key and reports 4,656 protocols, each with a
predictable document URL: `dserver.bundestag.de/btp/<wp>/<wp><nnn>.pdf`,
where <nnn> is the sitting number padded to three digits (21/96 ->
21096.pdf). It serves ten rows a page and carries the total as data-hits,
so the caller pages on offset exactly as the Mediathek listing does.

PDF ONLY. The Bundestag publishes a DTD for plenary protocols on its
open-data page, but no XML is offered on this route -- `btp/21/21096.xml`
is a 404 -- so this reverses the property the German scope doc opens by
celebrating, that DIP returns text and Germany needs no PDF parsing at all.
That is the cost of the fallback and the reason it is a fallback.

IT IS GOOD ENOUGH, MEASURED, not assumed. Protocol 21/96 through pypdf
against the same protocol's DIP text (2026-09-26):

    speeches parsed     474 from the PDF, 474 from DIP
    distinct speakers   137 and 137, of which 136 are shared
    speech bodies       464 of 474 found VERBATIM in the PDF text

The parser in src/de_protocol.py needs no change: it keys on the heading
line, which survives extraction. What does NOT survive is order -- the
front matter interleaves differently -- and line breaking, so the two texts
are not identical character for character even where the words are the
same. Anything comparing the two must normalise first; comparing raw
prefixes suggested 33 of 474 matched, which was an artefact of hyphenation
and nearly sent this route to the bin.

COST. 1.7 MB and about 4 seconds of extraction per sitting, against one
cheap DIP call. Fine for a fallback, wrong as a default.
"""

from __future__ import annotations

import re

LIST = ("https://www.bundestag.de/ajax/filterlist/de/dokumente/protokolle/"
        "plenarprotokolle/442112-442112?limit=10&noFilterSet=true"
        "&offset={offset}")
PDF = "https://dserver.bundestag.de/btp/{wp}/{wp}{sitzung:03d}.pdf"
PAGE_SIZE = 10

_HITS = re.compile(r'data-hits="(\d+)"')
# "96. Sitzung, 21. Wahlperiode, 24.09.2026"
_ROW = re.compile(r"(\d+)\.\s*Sitzung,\s*(\d+)\.\s*Wahlperiode,\s*"
                  r"(\d{2})\.(\d{2})\.(\d{4})")
_TAG = re.compile(r"<[^>]+>")


def pdf_url(wahlperiode, sitzung):
    """The document URL for one sitting. The sitting number pads to THREE
    digits: 21/96 is 21096.pdf, not 2196.pdf."""
    return PDF.format(wp=int(wahlperiode), sitzung=int(sitzung))


def hits(html_text):
    hit = _HITS.search(html_text or "")
    return int(hit.group(1)) if hit else 0


def parse_list(html_text):
    """[{protocol, wahlperiode, sitzung, datum, url}] from one listing page.

    Read from the row's own description line rather than from the PDF href, so a
    change to the document host does not silently yield rows with no
    identity. The href is rebuilt from the numbers.
    """
    import html as _html
    plain = " ".join(_html.unescape(_TAG.sub(" ", html_text or "")).split())
    out, seen = [], set()
    for m in _ROW.finditer(plain):
        sitzung, wp, day, month, year = m.groups()
        key = (wp, sitzung)
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "protocol": "{0}/{1}".format(wp, sitzung),
            "wahlperiode": int(wp), "sitzung": int(sitzung),
            "datum": "{0}-{1}-{2}".format(year, month, day),
            "url": pdf_url(wp, sitzung),
        })
    return out


def extract_text(data):
    """The words out of a protocol PDF, or "" if it cannot be read.

    Returns empty rather than raising: one unreadable Bericht must cost its
    own sitting and no more, the same rule the archive reader follows.
    """
    import io
    try:
        import pypdf
    except ImportError:                                   # pragma: no cover
        return ""
    # pypdf logs "EOF marker not found" and friends at ERROR for files it
    # then raises on anyway. We handle that by returning "", so the warning
    # is noise on a case already covered -- and noise in a test run is how a
    # real message gets skimmed past.
    import logging
    logging.getLogger("pypdf").setLevel(logging.CRITICAL)
    try:
        reader = pypdf.PdfReader(io.BytesIO(data))
        return dehyphenate(
            "\n".join((page.extract_text() or "") for page in reader.pages))
    except Exception:                                     # noqa: BLE001
        return ""


# The Bericht is typeset in justified columns and hyphenates freely:
# protocol 21/96 has 3,467 hyphen-newline splits. DIP's text has none, so a
# term list that works on DIP silently under-matches on the PDF --
# "Bundesregie-\nrung" is not "Bundesregierung", and the first live run
# found 11 speeches on our ground where DIP found 14.
#
# Rejoined ONLY when the next line starts lower case, which is where German
# breaks a word. A capital after the hyphen is a real compound
# ("Mediendienste-\nInvestitionsverpflichtungs-Gesetz") and keeps its
# hyphen, so this cannot weld two words into one that was never written.
_HYPHEN_BREAK = re.compile(r"([a-zäöüß])-\n([a-zäöüß])")


def dehyphenate(text):
    return _HYPHEN_BREAK.sub(r"\1\2", text or "")


def protocols(client, since, limit=20, log=print, max_pages=40):
    """Sitting protocols newest first, in the shape DIP's reader returns.

    `dokumentnummer`, `datum` and `text`, so tools/de_speeches.py can take
    these instead of DIP's documents without knowing which it has.

    Stops at `since` rather than paging the whole 4,656: the listing is
    newest first, so the first row older than the window ends it.
    """
    out = []
    for page in range(max_pages):
        try:
            html_text = client.get_text(
                LIST.format(offset=page * PAGE_SIZE), "de-btp",
                "list-{0}".format(page), archive=False)
        except Exception as exc:                          # noqa: BLE001
            log("  [gap] de-btp: listing page {0} unreadable ({1})".format(
                page, str(exc)[:70]))
            break
        rows = parse_list(html_text)
        if not rows:
            break
        for row in rows:
            if row["datum"] < since:
                return out
            try:
                data = client.get_bytes(row["url"], "de-btp", row["protocol"]
                                        .replace("/", "-"))
            except Exception as exc:                      # noqa: BLE001
                log("  [gap] de-btp: {0} not downloaded ({1})".format(
                    row["protocol"], str(exc)[:70]))
                continue
            text = extract_text(data)
            if not text.strip():
                log("  [gap] de-btp: {0} has no extractable text".format(
                    row["protocol"]))
                continue
            out.append({"dokumentnummer": row["protocol"],
                        "datum": row["datum"], "text": text})
            if len(out) >= limit:
                return out
    return out
