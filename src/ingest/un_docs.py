"""UN documents by symbol: which draft resolutions exist, and where.

Found 2026-08-17, and it reopens a gap that had been written off the same day.
The Journal's own config file names the pattern:

    "undocsUrl": "https://docs.un.org/{lang}/{symbol}?direct=true"

That `direct=true` is the whole thing. Without it, docs.un.org serves a ~4KB
redirect shell, which is why the source was dismissed as useless. With it, it
serves the document: A/C.3/80/L.1 is a 256KB PDF of a real Third Committee
draft resolution.

Draft resolutions are numbered sequentially within a session, so the set for a
session can be discovered by walking L.1, L.2, ... until the misses run on.
Existence is decided by CONTENT TYPE, not status: a missing symbol still
answers 200, with a 1.3KB text/html not-found page instead of a PDF.

WHAT THIS DOES NOT DO: read the documents. The titles are in the PDF body,
using subset fonts whose bytes need the embedded ToUnicode map to decode, so
stdlib-only extraction produces markup artefacts rather than text (tried, and
it returned a page of "en-GB"). Getting subjects out needs a PDF library,
which is a dependency decision for the repo owner -- this module deliberately
stops at "this draft exists, here it is".
"""

from __future__ import annotations

import re
from dataclasses import dataclass

DOC_URL = "https://docs.un.org/{lang}/{symbol}?direct=true"

# The two bodies whose drafts matter to us. Third Committee takes the family,
# SRHR and religious-freedom resolutions; the HRC takes the thematic mandates.
THIRD_COMMITTEE_DRAFTS = "A/C.3/{session}/L.{n}"
HRC_DRAFTS = "A/HRC/{session}/L.{n}"


@dataclass
class Document:
    symbol: str
    url: str
    size: int
    content_type: str

    @property
    def is_document(self):
        return "pdf" in (self.content_type or "").lower()


def doc_url(symbol, lang="en"):
    return DOC_URL.format(lang=lang, symbol=symbol)


def head(client, symbol, lang="en"):
    """Fetch a symbol and report what came back.

    A GET rather than a HEAD: docs.un.org answers 200 for a missing symbol, so
    the only reliable signal is the response itself, and a HEAD would not
    give the content type consistently.
    """
    url = doc_url(symbol, lang)
    # 64 bytes is enough: %PDF- means the document exists, <!doct means the
    # not-found page. Downloading the whole PDF to learn that cost 11s per
    # symbol and ~300KB (measured before adding the Range request).
    raw = client.get_bytes(url, "undocs", symbol.replace("/", "-"), first_bytes=64)
    kind = "application/pdf" if raw[:5] == b"%PDF-" else "text/html"
    return Document(symbol=symbol, url=url, size=len(raw), content_type=kind)


def enumerate_drafts(client, pattern, session, max_n=120, stop_after_misses=5):
    """Draft symbols that exist for a session, walking L.1 upward.

    Stops after `stop_after_misses` consecutive misses rather than at the
    first one: numbering has gaps in practice (a withdrawn or renumbered
    draft), and stopping at the first hole would silently truncate the set.
    Returns (documents, checked) so the caller can report the cost.
    """
    found, misses, checked = [], 0, 0
    for n in range(1, max_n + 1):
        symbol = pattern.format(session=session, n=n)
        checked += 1
        try:
            doc = head(client, symbol)
        except Exception:
            misses += 1
            if misses >= stop_after_misses:
                break
            continue
        if doc.is_document:
            found.append(doc)
            misses = 0
        else:
            misses += 1
            if misses >= stop_after_misses:
                break
    return found, checked
