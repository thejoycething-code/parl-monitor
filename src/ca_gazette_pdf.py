"""Canada Gazette issues that exist only as PDFs: all of 2010, Part II of 2011.

Built 28 September 2026 for the backfill to 2010. The yearly archive links
these issues as one PDF each (g1-14423.pdf, g2-14412.pdf) with no HTML
edition, so the collector cannot read an index; it reads the PDF.

THE LAYOUT. Every page is bilingual in two columns, English left and French
right (612 pt wide; English runs start at x=48-57, French at x=312-321). A
plain text extraction interleaves the two paragraph by paragraph. Keeping only
the text fragments that start left of the midline gives the English column
(english_pages, about 7 s for a 105-page issue). english_only() still cuts a
French half off any heading or title line that arrives merged, as a guard.

THE ITEMS.
  * Part I: every notice and proposed regulation ends with its insertion code,
    "[23-1-o]" (issue-week-occurrence). The text between codes is one item.
    The cover and table of contents come before the first body page (the
    first page the table of contents points at) and are dropped; the index
    after the last code is dropped. The section is the table-of-contents
    entry whose page the item starts on.
  * Part II: every instrument opens with "Registration / SOR/2010-110 May 19,
    2010", which is the item boundary and its registration number. The
    English table of contents at the back is where the last item stops.
  * An issue with neither (an extra edition of one order) is one item, read
    whole.
Each item's URL is the PDF's with the page it starts on (#page=12), which is
also its key; two items starting on one page get #page=12.2.

The text stored is the English column. It is rougher than an HTML page:
hyphenation is kept ("En-vironment") and the odd heading keeps a French word.
Matching runs per passage, like every other Gazette item.
"""

from __future__ import annotations

import io
import re
from collections import Counter

# "[23-1-o]"; the odd one is printed without its "-o" (5 June 2010, p. 1491).
FRENCH_EDGE = 264          # the French column's left edge on a 612 pt page
MARKER = re.compile(r"(?:\[\d{1,2}-\d{1,2}(?:-o)?\]\s*)+")
# The French registration line that follows the English one in Part II.
FRENCH_REGISTRATION = re.compile(r"^\s*(?:DORS|TR)/\d{4}-\d+\s+Le\s+\S+\s+\S+\s+\d{4}\s*")
FRENCH_WORD = re.compile(r"[àâçéèêëîïôûùœÀÂÇÉÈÊËÎÏÔÛÙŒ]|^(?:de|du|des|la|le|les|et|pour|sur|aux?|"
                         r"d[’']\S*|l[’']\S*|DE|DU|DES|LA|LE|LES|ET|POUR|SUR|AUX?|D[’']\S*|L[’']\S*|"
                         r"Avis|AVIS|Nominations|NOMINATIONS|Liste|Demandes?|Autorisation|n)$")
REGISTRATION = re.compile(
    r"Registration\s+(?:Enregistrement\s+)?((?:SOR|SI)/\d{4}-\d+)\s+([A-Z][a-z]+\.? \d{1,2}, \d{4})")
P2_END = re.compile(r"\n\s*(?:TABLE OF CONTENTS|INDEX SOR)\b")
# Running heads, which would otherwise split sentences at every page turn:
# "1402 Canada Gazette Part I June 5, 2010", "Le 5 juin 2010 Gazette du Canada
# Partie I 1407", "2010-06-09 Canada Gazette Part II, Vol. 144, No. 12 ...".
RUNNING_HEAD = re.compile(
    r"^\s*(?:\d{1,5}\s+Canada Gazette Part I\b.*|.*Gazette du Canada Partie I.*"
    r"|\d{4}-\d{2}-\d{2}\s+Canada Gazette Part II.*|\d{1,5})\s*$", re.M)
PRINTED_PAGE = re.compile(r"^\s*(\d{1,5})\s+Canada Gazette Part I\b", re.M)
TOC_ENTRY = re.compile(r"^\s*([A-Z][A-Za-z ,()'’-]{2,60}?)\s*\.{4,}\s*(\d{1,5})\b", re.M)
FRENCH_HEADING = re.compile(
    r"\s+(?=(?:MINISTÈRE|LOI|BUREAU|AGENCE|CONSEIL|RÈGLEMENT|DÉCRET|AVIS|TARIF|"
    r"SECRÉTARIAT|DIRECTEUR|DIRECTION|CHAMBRE|SÉNAT|GOUVERNEMENT|SOCIÉTÉ|RÉGIE|"
    r"COMMISSARIAT|ENREGISTREMENT|ÉNONCÉ|NOMINATIONS|PARLEMENT|COMMISSIONS DE)\b)")
BODY_START = re.compile(r"^(?:Notice is|Name and position|The |His |Her |Whereas|Pursuant|"
                        r"P\.C\.|Take notice|Public Notice|Under |In this |"
                        r"(?:January|February|March|April|May|June|July|August|September|"
                        r"October|November|December) \d)")


def english_pages(data):
    """The English column of each page of a Gazette PDF, as text.

    Built on pypdf's layout engine, which knows where every text-show
    operation lands (text_show_operations: tx is the fragment's left edge,
    measured from the leftmost text on the page). A fragment starting left of
    the page's text midline is English. The first version kept pypdf
    visitor_text runs by position, but a visitor call reports the position of
    the run BEFORE its text -- it held on the real pages only by the order
    their content streams happen to be written in, and let whole French
    halves of headings through. This is a private pypdf interface, so the
    workflow pins pypdf; if it moves, the issue is a gap, not bad text.
    """
    import logging

    import pypdf                         # only the PDF-only backfill needs it
    from pypdf._text_extraction._layout_mode import _fixed_width_page as fw

    # "Rotated text discovered. Output will be incomplete." once per page with
    # a sideways table heading: the rotated text is dropped, which is right.
    logging.getLogger("pypdf").setLevel(logging.ERROR)

    reader = pypdf.PdfReader(io.BytesIO(data))
    pages = []
    for page in reader.pages:
        contents = page.get_contents()
        if contents is None:
            pages.append("")
            continue
        ops = iter(pypdf.generic.ContentStream(contents, reader, "bytes").operations)
        frags = fw.text_show_operations(ops, page._layout_mode_fonts(), True, None)
        if not frags:
            pages.append("")
            continue
        # Where the French column starts: the commonest left edge in the
        # middle band (264 on every page seen, measured from the leftmost
        # text). The page's widest line is no guide: Part II pads its
        # registration lines ("SOR/2010-110 ... DORS/2010-110") to far past
        # the page edge, which put an earlier midline to the right of the
        # whole French column.
        edges = Counter(round(f["tx"]) for f in frags
                        if 150 < f["tx"] < 400 and f["text"].strip())
        top = edges.most_common(1)
        midline = top[0][0] - 3 if top and top[0][1] >= 3 else FRENCH_EDGE - 3
        lines = {}
        for f in frags:
            if f["tx"] < midline and f["text"].strip():
                lines.setdefault(round(f["ty"]), []).append((f["tx"], f["displaced_tx"], f["text"]))
        out, last = [], None
        for ty in sorted(lines, reverse=True):
            # From July 2011 Part II sets nearly every glyph as its own
            # fragment ("C", "ana", "da G", "a", "z"...). Joined with spaces
            # that read "S O R / 2011- 246", no registration line matched and
            # twelve issues became one blob each. A fragment that starts
            # where the last one ended (within 1 pt; a word space is ~7 pt)
            # is the same word.
            line, end = "", None
            for tx, dtx, text in sorted(lines[ty]):
                line += text if end is not None and tx - end < 1.0 else (" " if line else "") + text.lstrip()
                end = dtx
            line = " ".join(line.split())
            if line != last:             # a centred name set once per column
                out.append(line)
            last = line
        pages.append("\n".join(out))
    return pages


def contents_pages(data, n=5):
    """The first pages in plain extraction, for the table of contents: its
    layout (a French word at the far left, page numbers as separate
    fragments) defeats the column cut, and plain text reads it whole:
    "Government notices ......... 1400 Avis du gouvernement ..... 1400"."""
    import pypdf

    reader = pypdf.PdfReader(io.BytesIO(data))
    return [(page.extract_text() or "") for page in list(reader.pages)[:n]]


def english_only(line):
    """One heading or title line with its French half cut off.

    A full-width line can come out of the PDF as one run holding both
    columns: "PARIS RE PARIS RE", "Notice  Avis", "RELEASE OF ASSETS
    LIBÉRATION D’ACTIF", "Greenhouse bell peppers Poivrons de serre". A line
    that repeats itself is halved; a wide gap is the column break; otherwise
    the line is cut before the first capitalised word from which on it reads
    as French (accents, de/la/des...) while everything before it reads as
    English. A line that is all one language is returned whole."""
    line = re.split(r"\s{2,}", line.strip())[0]
    words = line.split()
    half = len(words) // 2
    if len(words) % 2 == 0 and half and words[:half] == words[half:]:
        return " ".join(words[:half])
    line = FRENCH_HEADING.split(line, 1)[0].strip()
    words = line.split()

    def french(ws):
        return sum(1 for w in ws if FRENCH_WORD.search(w)) / max(1, len(ws))

    # Of the places the line could be cut, the one nearest the middle: the
    # French half runs about as long as the English ("RELEASE OF ASSETS
    # LIBÉRATION D’ACTIF" is cut after ASSETS, not after RELEASE).
    cuts = [k for k in range(1, len(words))
            if words[k][:1].isupper() and french(words[:k]) == 0 and french(words[k:]) >= 0.25]
    if cuts:
        k = min(cuts, key=lambda c: (abs(c - (len(words) - c)),
                                     0 if FRENCH_WORD.search(words[c]) else 1))
        return " ".join(words[:k])
    return line


def _heading(line):
    return english_only(line)


ENGLISH_WORD = re.compile(r"^(?:the|of|and|to|for|in|on|or|by|with|under|respecting|"
                          r"amending|regulations?|order|act|schedule|canada|canadian)$", re.I)


def _reads_english(line):
    """A title's wrap line, not the French title's: no French word, and a
    line that opens in lower case must open with an English word."""
    words = line.split()
    if not words or any(FRENCH_WORD.search(w) for w in words):
        return False
    return words[0][:1].isupper() or words[0][:1] == "(" or bool(ENGLISH_WORD.match(words[0]))


def _is_heading(line):
    letters = [c for c in line if c.isalpha()]
    return len(letters) >= 3 and all(c.isupper() for c in letters)


def title_of(chunk, sections=()):
    """(department, title) from an item's opening lines. A heading that is a
    section's name ("GOVERNMENT NOTICES", "COMMISSIONS") is not the
    department: it only opens the section."""
    names = {n.upper() for n in sections}
    lines = [l.strip() for l in chunk.strip().splitlines()
             if l.strip() and english_only(l).upper() not in names]
    # A proposed regulation opens with its section's table of contents; its
    # title is the English line(s) just before "Statutory authority".
    auth = next((i for i, l in enumerate(lines) if l.startswith("Statutory authority")), None)
    if auth is not None and auth < 40:
        block = []
        for l in reversed(lines[:auth]):
            if "..." in l or FRENCH_WORD.search(l.split()[0] if l.split() else ""):
                break
            block.insert(0, english_only(l))
        if block:
            return None, " ".join(block)
    heads = []
    while lines and _is_heading(lines[0]):
        heads.append(_heading(lines.pop(0)))
    first = english_only(lines[0]) if lines else ""
    if not first or BODY_START.match(first) or len(first) > 160:
        title = " — ".join(heads[1:] or heads) or first[:120]
    elif len(first) < 25 and heads:
        # "Notice", "Appointments": say what it is a notice OF.
        title = "{0} — {1}".format(heads[-1], first)
    else:
        # A title may wrap over two or three lines before the body starts.
        # A French title's centred wrap line can sit left of the midline
        # ("ferroviaire —", "et drogues (1595 — annexe F)"), so a wrap line
        # is followed only while it reads as English.
        for nxt in lines[1:4]:
            if (BODY_START.match(nxt) or _is_heading(nxt) or len(first) < 30
                    or first.endswith((".", ":")) or len(first) + len(nxt) > 220
                    or not _reads_english(nxt)):
                break
            first = "{0} {1}".format(first, english_only(nxt))
        title = first
    return (heads[0] if heads else None), title


def _sections(pages):
    """[(printed page, section)] from the Part I table of contents."""
    out = []
    for text in pages[:5]:
        if "TABLE OF CONTENTS" not in text:
            continue
        for name, page in TOC_ENTRY.findall(text):
            out.append((int(page), name.strip()))
    return sorted(set(out))


def _offset(pages):
    """printed page number - PDF page index, from the first even-page head."""
    for i, text in enumerate(pages):
        m = PRINTED_PAGE.search(text)
        if m:
            return int(m.group(1)) - i
    return None


def _joined(pages, first=0):
    """The pages' text, running heads removed, with each page's start offset."""
    parts, starts, pos = [], [], 0
    for i, text in enumerate(pages):
        if i < first:
            starts.append(None)
            continue
        text = RUNNING_HEAD.sub("", text)
        starts.append(pos)
        parts.append(text + "\n")
        pos += len(text) + 1
    return "".join(parts), starts


def _page_at(starts, offset):
    page = 0
    for i, s in enumerate(starts):
        if s is not None and s <= offset:
            page = i
    return page


def items(pages, part, pdf_url, title=None, contents=None):
    """[{url, title, section, department, kind, registration, text}] for one
    PDF issue, in page order."""
    out, used = [], {}

    def add(page, dept, head, section, kind, registration, text):
        n = used[page] = used.get(page, 0) + 1
        url = "{0}#page={1}{2}".format(pdf_url, page + 1, "" if n == 1 else ".{0}".format(n))
        out.append({"url": url, "title": head, "section": section, "department": dept,
                    "kind": kind, "registration": registration, "text": text})

    if part == 2:
        text, starts = _joined(pages)
        end = P2_END.search(text, REGISTRATION.search(text).end() if REGISTRATION.search(text) else 0)
        text = text[:end.start()] if end else text
        found = list(REGISTRATION.finditer(text))
        for m, nxt in zip(found, found[1:] + [None]):
            body = FRENCH_REGISTRATION.sub("", text[m.end():nxt.start() if nxt else len(text)])
            dept, head = title_of(body)
            add(_page_at(starts, m.start()), dept, head, None, "regulation", m.group(1),
                " ".join(body.split()))
    else:
        sections, offset = _sections(contents or pages), _offset(pages)
        first = (sections[0][0] - offset) if sections and offset is not None else 0
        text, starts = _joined(pages, first=max(0, first))
        found = list(MARKER.finditer(text))
        begin = 0
        for m in found:
            body = text[begin:m.start()]
            page = _page_at(starts, begin + len(body) - len(body.lstrip()))
            begin = m.end()
            if len(body.split()) < 5:
                continue
            section = None
            if offset is not None:
                printed = page + offset
                for start, name in sections:
                    if start <= printed:
                        section = name
            dept, head = title_of(body, [name for _, name in sections] + ["PARLIAMENT"])
            flat = " ".join(body.split())
            kind = ("regulation" if (section or "").lower().startswith("proposed regulations")
                    or "REGULATORY IMPACT ANALYSIS STATEMENT" in body.upper() else "notice")
            add(page, dept, head, section, kind, None, flat)
    if not out:
        text, _ = _joined(pages)
        add(0, None, title or "Extra edition", "Extra edition", "extra", None, " ".join(text.split()))
    return out
