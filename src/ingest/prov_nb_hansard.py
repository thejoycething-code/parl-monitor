"""New Brunswick Hansard speeches (tools/prov_speeches.py --prov nb).

THE SOURCE: the session's Hansard listing the vote collector reads for its
member lists (/en/house-business/hansard/61/2, prov_nb.list_hansards), one
bilingual "b" PDF per sitting ("47 2026-06-04b.pdf", 1.3 MB and 118 pages,
measured 2 October 2026). robots.txt asks for 10 seconds between requests
and gets them (prov_fetch raises the host's interval).

THE BILINGUAL EDITION, measured on 4 June 2026: two columns, the LEFT one as
spoken (French or English, switching mid-speech) and the RIGHT one its
translation, paragraph by paragraph, each pair starting on the same line.
Plain extraction interleaves them, so the page is read with positions
(prov_fetch.pdf_fragments), each column cut into paragraphs by the gaps
between lines, the pairs matched by their first line, and the ENGLISH
paragraph of each pair kept, by its function words. French is never
classified here: the English taxonomy cannot read it, and its English
counterpart is right beside it.

  Introduction of Guests / Présentation d’invités    a rubric (both languages)
  Mr. Savoie: Thank you very much, Madam Speaker. ...  a turn
  13:05                                                a clock line, dropped

WHO SPOKE: "Hon. Mr. Herron", "Ms. M. Wilson", "Mr. Coon", with the vote
collector's resolver (prov_nb.make_resolver: the reviewed aliases over the
session roster -- the compiled Journal's members page, or the current
members page for a session not yet compiled). A session with no roster
stored is read once here through prov_nb.fetch_roster, as the vote
collector reads it.
"""

from __future__ import annotations

import collections
import re

from src import prov_speeches as sp
from src.ingest import prov_nb as base
from src.prov_fetch import Unreadable, rebuild_cut_xref

PROV = "nb"
LANGUAGE = "en"
CURRENT_SESSION = base.CURRENT_SESSION

COLUMN_CUT = 300.0          # the left column starts at x 72, the right at x 321
TOP, BOTTOM = 702.0, 50.0   # the running head (y 711) and the '^' mark (y 40)
PARA_GAP = 16.0             # lines are 11.5 pt apart; a paragraph break leaves about 23
CHAR_W = 4.3                # mean advance of a character at 10 pt, for re-spacing words

_EN = {"the", "and", "of", "to", "is", "that", "in", "for", "i", "we", "this", "it", "on", "with",
       "have", "be", "are", "will", "our", "speaker", "madam", "thank", "you", "they", "was", "what",
       "not", "has", "from", "who", "would", "their", "an", "as", "at", "by", "all", "my", "can"}
_FR = {"le", "la", "les", "des", "de", "du", "et", "est", "que", "qui", "pour", "dans", "une", "un",
       "nous", "je", "vous", "à", "au", "aux", "sur", "pas", "présidente", "président", "merci", "madame",
       "ce", "cette", "ils", "elle", "il", "sont", "mais", "avec", "plus", "leur", "ont", "été", "très"}
_CLOCK = re.compile(r"^\d{1,2}:\d{2}$")
_LABEL = re.compile(r"^(?P<l>(?:Hon\.\s*|The\s+)?(?:Mr\.|Ms\.|Mrs\.|Miss|Dr\.|Madam|Mister|Mr|Ms|Speaker|"
                    r"Deputy\s+Speaker|Chair|Clerk|Hon\.\s+Members|Some\s+Hon\.\s+Members|An\s+Hon\.\s+Member)"
                    r"[^:]{0,60}?)\s*:\s*(?P<r>.*)$", re.S)
# A long set-piece speech opens in narration, not "Name:" (Throne Speech and
# Budget replies): "Mr. McKee, resuming the adjourned debate on the motion on
# the address in reply to the speech from the throne, spoke as follows: Mr.
# Speaker, ..." (27 October 2022; three opening-week days read as "no
# speaker turns parsed" until this, 9 October 2026).
_NARRATED = re.compile(r"^(?P<l>(?:Hon\.\s*)?(?:Mr\.|Ms\.|Mrs\.|Miss|Dr\.)\s*[^,:]{1,50}),\s"
                       r"[^:]{0,300}?\bspoke as follows\s*:\s*(?P<r>.*)$", re.S)


def english_score(text):
    """Function words, English less French; a tie (a two-word heading) goes
    to the text with fewer French accents ('Tax Reform', not 'Réforme fiscale')."""
    low = (text or "").lower()
    words = re.findall(r"[a-zàâçéèêëîïôûùüÿœ’']+", low)
    en = sum(1 for w in words if w in _EN)
    fr = sum(1 for w in words if w in _FR or w.startswith(("l’", "d’", "qu’", "n’", "s’", "j’", "c’")))
    accents = len(re.findall(r"[àâçéèêëîïôûùüÿœ]", low))
    return (en - fr, -accents)


# The close of a sitting as the bilingual Hansard prints it: "(The House
# adjourned at 6 p.m.)" / "(La séance est levée à 18 h.)".
ADJOURNED = re.compile(r"House\s+(?:is\s+now\s+)?adjourned|s[ée]ance\s+est\s+lev[ée]e", re.I)


def fragments(raw):
    """[(page, x, y, text, x_end)]: prov_fetch.pdf_fragments with each
    fragment's END, from its font's own glyph widths, so the space between
    two separately drawn words can be put back ('Policy' '713') without
    splitting a word drawn in pieces ('Nor' 'd')."""
    import io

    import pypdf
    if not raw or raw[:5] != b"%PDF-":
        raise Unreadable("not a PDF ({0} bytes)".format(len(raw or b"")))
    rebuilt = False
    if b"%%EOF" not in raw[-2048:]:
        # legnb.ca serves many Hansards cut off inside their closing
        # cross-reference table (9 October 2026; prov_fetch.rebuild_cut_xref).
        # The rebuilt file is taken only when its last page reaches the
        # adjournment, so a record cut short in its TEXT stays a gap.
        fixed = rebuild_cut_xref(raw)
        if fixed is None:
            raise Unreadable("truncated PDF: no %%EOF marker in {0} bytes".format(len(raw)))
        raw, rebuilt = fixed, True
    try:
        reader = pypdf.PdfReader(io.BytesIO(raw))
        # The close may sit a page or two before the end: the bilingual files
        # end on a page carrying only the running header ("2772 2021 June 1
        # juin", 1 June 2021), so the last THREE pages are read.
        tail = " ".join(reader.pages[i].extract_text() or "" for i in range(max(0, len(reader.pages) - 3), len(reader.pages)))
        if rebuilt and not ADJOURNED.search(tail):
            raise Unreadable("truncated PDF: cross-reference rebuilt, but the last pages do not "
                             "reach the adjournment")
        out = []
        for i, page in enumerate(reader.pages):
            got = []

            def visit(text, cm, tm, fd, fs, got=got, i=i):
                if not text or not text.strip():
                    return
                scale = (tm[0] or 1.0) * (cm[0] or 1.0)
                x = round(tm[4] * cm[0] + cm[4], 1)
                y = round(tm[5] * cm[3] + cm[5], 1)
                got.append((i, x, y, text, x + _width(text, fd, fs) * scale))
            page.extract_text(visitor_text=visit)
            out.extend(got)
        return out
    except Unreadable:
        raise
    except Exception as exc:
        raise Unreadable("PDF could not be read: {0}".format(exc))


def _width(text, fd, fs):
    try:
        widths, first = fd.get("/Widths"), int(fd.get("/FirstChar", 0))
        if widths is not None:
            ws = [float(w) for w in widths]
            total = 0.0
            for c in text:
                k = ord(c) - first
                total += ws[k] if 0 <= k < len(ws) and ws[k] else 500.0
            return total / 1000.0 * float(fs or 10.0)
    except Exception:  # noqa: BLE001 -- a font we cannot measure falls back to the mean
        pass
    return len(text) * CHAR_W * float(fs or 10.0) / 10.0


def _join(frags):
    """One line's fragments, left to right, with the space put back where a
    fragment starts clearly after the last one ended."""
    out, prev_end, prev_t = "", None, ""
    for x, t, x_end in sorted(frags):
        if out and not prev_t.endswith(" ") and not t.startswith(" ") and prev_end is not None \
                and x - prev_end > 1.2:
            out += " "
        out += t
        prev_end, prev_t = x_end, t
    return re.sub(r"\s+", " ", out).strip()


def column_paragraphs(frags):
    """{(page, col): [(start_y, text)]} from positioned fragments."""
    lines = collections.defaultdict(list)
    for page, x, y, t, x_end in frags:
        if (x <= 1 and y <= 1) or y > TOP or y < BOTTOM:
            continue
        lines[(page, 0 if x < COLUMN_CUT else 1, round(y))].append((x, t, x_end))
    out = collections.defaultdict(list)
    last = {}
    for (page, col, y) in sorted(lines, key=lambda k: (k[0], k[1], -k[2])):
        text = _join(lines[(page, col, y)])
        if not text or len(text) <= 3 and text.isalpha() and text.islower():
            continue                     # a superscript ('me', 'e') printed above the line
        key = (page, col)
        if _CLOCK.match(text):
            last.pop(key, None)
            continue
        prev = last.get(key)
        if prev is None or prev - y > PARA_GAP:
            out[key].append([y, text])
        else:
            out[key][-1][1] += " " + text
        last[key] = y
    return out


def english_stream(frags):
    """The English paragraph of every pair, in reading order."""
    paras = column_paragraphs(frags)
    pages = sorted({p for p, _c in paras})
    stream = []
    for page in pages:
        left, right = paras.get((page, 0), []), paras.get((page, 1), [])
        used = set()
        for ly, lt in left:
            match = None
            for j, (ry, rt) in enumerate(right):
                if j not in used and abs(ry - ly) <= 4:
                    match = j
                    break
            if match is None:
                stream.append((page, -ly, lt))
                continue
            used.add(match)
            rt = right[match][1]
            stream.append((page, -ly, lt if english_score(lt) >= english_score(rt) else rt))
        for j, (ry, rt) in enumerate(right):
            if j not in used:
                stream.append((page, -ry, rt))
    return [t for _p, _y, t in sorted(stream, key=lambda s: (s[0], s[1]))]


def parse_paragraphs(paras):
    start = next((i for i, p in enumerate(paras) if re.match(r"^\(The House met", p)), None)
    if start is None:
        start = next((i for i, p in enumerate(paras) if "House met" in p or "séance est ouverte" in p), 0)
    paras = paras[start:]
    blocks = []
    for i, p in enumerate(paras):
        nxt = paras[i + 1] if i + 1 < len(paras) else ""
        if is_heading(p, nxt):
            # One language a column (2023): 'Oral Questions', then 'Schools'.
            if blocks and blocks[-1][0] == "subject":
                blocks[-1] = ("rubric", blocks[-1][1])
            blocks.append(("subject", p, sp.bill_number(p)))
            continue
        if " / " in p and len(p) <= 160 and not re.search(r"[.?!]$", p) and not _LABEL.match(p):
            # A heading, printed in both languages. Two in a row are the
            # rubric and the subject under it (Oral Questions, then Tax Reform).
            halves = [h.strip() for h in p.split(" / ") if h.strip()]
            best = max(halves, key=english_score) if halves else p
            if blocks and blocks[-1][0] == "subject":
                blocks[-1] = ("rubric", blocks[-1][1])
            blocks.append(("subject", best, sp.bill_number(best)))
            continue
        m = _NARRATED.match(p) or _LABEL.match(p)
        if m and len(m.group("l").split()) <= 7:
            blocks.append(("label", m.group("l").strip(), m.group("r").strip()))
        elif p.startswith("(") and p.endswith(")") or p.startswith("[") and p.endswith("]"):
            blocks.append(("proc", p))
        else:
            blocks.append(("para", p))
    return sp.turns_from_blocks(blocks)


def is_heading(p, nxt):
    """A short title line with no closing punctuation, followed by a label
    or by another such line -- never a line inside a speech."""
    if not p or len(p) > 90 or len(p.split()) > 12 or " / " in p or _LABEL.match(p):
        return False
    if not p[:1].isupper() or re.search(r"[.?!:;,”\"’)\]—–-]$", p) or re.match(r"^\d", p):
        return False
    return bool(_LABEL.match(nxt)) or (len(nxt) <= 90 and nxt[:1].isupper()
                                        and not re.search(r"[.?!:;,”\"’)\]]$", nxt) and not _LABEL.match(nxt)
                                        and len(nxt.split()) <= 12)


def parse_pdf(raw):
    return parse_paragraphs(english_stream(fragments(raw)))


def list_days(ctx, session):
    leg, sess = base.parse_session(session)
    html = ctx.text(base.HANSARD.format(leg, sess), "hansards-{0}-{1}".format(leg, sess))
    listed = base.list_hansards(html) if html else {}
    if html and not listed:
        menu = [(int(a), int(b)) for a, b in re.findall(r'href="/en/house-business/hansard/(\d+)/(\d+)"', html)]
        if menu and (leg, sess) < min(menu):
            # Measured 2 October 2026: the Hansard page offers sessions from
            # 58-3 (2017) on; earlier transcripts are "available upon request
            # through the Legislative Library". Not published is not a gap.
            ctx.log("  nb Hansard {0}: not published online (the Hansard page lists sessions from 58-3; "
                    "earlier ones are on request from the Legislative Library)".format(session))
        else:
            ctx.gap("nb Hansard {0}: no sittings parsed from the listing".format(session))
    days = [{"key": "nb-{0}-{1}-{2}".format(leg, sess, date), "date": date, "legislature": leg,
             "session": sess, "url": url, "document": url} for date, url in sorted(listed.items())]
    have = ctx.conn.execute("SELECT COUNT(*) FROM prov_member_terms WHERE prov=? AND legislature=? "
                            "AND source NOT LIKE 'party%'", (PROV, leg)).fetchone()[0]
    if days and not have and not ctx.dry_run:
        journals = ctx.text(base.JOURNALS.format(leg, sess), "journals-{0}-{1}".format(leg, sess))
        base.fetch_roster(ctx, leg, sess, base.list_records(journals or ""))
    return days


def read_day(ctx, day):
    raw = ctx.bytes(day["url"], "hansard-{0}".format(day["key"]), archive=True)
    if raw is None:
        return None, ["the Hansard PDF was not fetched"]
    try:
        return parse_pdf(raw), []
    except Unreadable:
        raise


def resolver(ctx):
    return base.make_resolver(ctx.conn)
