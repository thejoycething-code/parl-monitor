"""Read the text of a European Parliament document, not just its title.

The gap this closes. `eu_texts` matched adopted texts on their TITLE alone, and
Parliament titles are generic by convention. On 17 September 2026 the House
adopted "Impact of social media and the online environment on young people" --
a hundred operative paragraphs on a minimum age for social media, age
assurance, kidfluencers, sharenting, parental controls and smartphones in
schools -- and it matched nothing at all. Guarding a generic phrase catches that
one title; reading the body catches the next one too.

The spec recorded these texts as unreachable: "TA pages sit behind
europarl.eu's bot-wall (202), so rows ship linkless". True of the doceo page,
false of the document. The adopted-texts metadata carries an ELI distribution
path and `data.europarl.europa.eu/distribution/doc/<id>_en.docx` answers 200
with the whole resolution. There is a .pdf and an .xml beside it; the .docx is
the smallest to parse without a dependency.

No python-docx: a .docx is a zip whose word/document.xml holds the text, and
paragraphs are </w:p>. That is the whole parser, and it keeps this offline-
testable with nothing installed.
"""

import io
import re
import zipfile

HOST = "https://data.europarl.europa.eu/"
DISTRIBUTION = HOST + "distribution/doc/{0}_en.{1}"      # kept for callers by name
DOCUMENT = HOST + "api/v2/documents/{0}?format=application%2Fld%2Bjson"

# EACH DOCUMENT TYPE HAS ITS OWN SHELF (18 September 2026). Adopted texts
# answer at distribution/doc/; the reports they were adopted from (A-) sit
# under reds_iPlRp/<id>/ and the motions for resolutions (B-) under
# reds_iPlRe/<id>/. Asking for the report on social media and young people
# at the adopted-texts path returned 404, and the right shelf was only in the
# document's own record (is_realized_by -> is_embodied_by -> is_exemplified_by).
# The record is the truth; the table is the shortcut that saves a call.
SHELVES = {
    "TA": "distribution/doc/{id}_en.{fmt}",
    "A": "distribution/reds_iPlRp/{id}/{id}_en.{fmt}",
    "B": "distribution/reds_iPlRe/{id}/{id}_en.{fmt}",
}

# A paragraph shorter than this is a heading, a reference number or a stray
# field code, not a passage worth filtering.
MIN_PARAGRAPH = 40

# THE PREAMBLE CITATIONS ARE NOT THE SUBJECT (17 September 2026). Every EP
# resolution opens with a block of "having regard to ..." references: the
# treaties, the Charter, earlier resolutions, Commission communications. The
# Charter recital alone names human dignity, the right to life, freedom of
# expression and the protection of personal data, so matching the body
# verbatim filed a resolution on narco-trafficking in Europe's waters under
# free speech on the strength of a citation. Measured on the first ten texts
# read: this was the ONLY term two of the five gains rested on. A citation is
# what a text cites, not what it says, so the whole block is dropped before
# filtering -- the same judgement the UK ledger makes when it filters passages
# rather than whole speeches.
CITATION = re.compile("^[–—‒-]?[ \t]*having regard to\\b", re.I)


def kind(identifier):
    """'TA' for TA-10-2026-0313, 'A' for A-10-2026-0220, 'B' for B-10-2026-0406."""
    return (identifier or "").split("-", 1)[0].upper()


def url_for(identifier, fmt="docx"):
    """The distribution URL for a document whose shelf is known; None when the
    type is not in SHELVES (a joint motion, a committee opinion), in which
    case url_from_record() reads the shelf off the document's record."""
    shelf = SHELVES.get(kind(identifier))
    if not shelf:
        return None
    return HOST + shelf.format(id=identifier, fmt=fmt)


def url_from_record(record, fmt="docx", lang="en"):
    """The distribution URL named in a documents/<id> API record: the
    manifestation whose path ends _<lang>.<fmt>. None when there is none."""
    data = record.get("data") if isinstance(record, dict) and "data" in record else record
    if isinstance(data, list):
        data = data[0] if data else {}
    suffix = "_{0}.{1}".format(lang, fmt)
    for expression in (data or {}).get("is_realized_by") or []:
        for manifestation in expression.get("is_embodied_by") or []:
            path = manifestation.get("is_exemplified_by")
            if isinstance(path, str) and path.endswith(suffix):
                return HOST + path.lstrip("/")
    return None


def resolve_url(identifier, get_json, fmt="docx"):
    """url_for() when the shelf is known, else one call to the document record.
    get_json(url) -> dict."""
    return url_for(identifier, fmt) or url_from_record(get_json(DOCUMENT.format(identifier)), fmt)


def paragraphs(blob):
    """The document's paragraphs, in order. Raises for anything that is not a
    readable .docx, so a bot-wall HTML page cannot be mistaken for a text."""
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        xml = z.read("word/document.xml").decode("utf-8", "replace")
    xml = re.sub(r"</w:p>", "\n", xml)
    # A tab is how Word separates "78." from "Calls on the Commission"; strip
    # the tag alone and the number fuses to the first word, which is why the
    # first attempt to find paragraph 78 in a report found nothing numbered.
    xml = re.sub(r"<w:tab\s*/>", " ", xml)
    text = re.sub(r"<[^>]+>", "", xml)
    text = re.sub(r"[ \t]+", " ", text)
    out = []
    for p in text.split("\n"):
        p = p.strip()
        # Word leaves field codes in the run text ('TC"(A10-0199/2026 ...)"\l3
        # \n> \* MERGEFORMAT'); they are not prose and they match nothing good.
        if p and "MERGEFORMAT" not in p and not p.startswith("TC\""):
            out.append(p)
    return out


def body_text(blob, min_paragraph=MIN_PARAGRAPH, drop_citations=True):
    """The document's prose as one string: short structural lines dropped, and
    the preamble's "having regard to" citations with them."""
    out = []
    for p in paragraphs(blob):
        if len(p) < min_paragraph:
            continue
        if drop_citations and CITATION.match(p):
            continue
        out.append(p)
    return "\n".join(out)


OPERATIVE = re.compile(r"^(\d{1,3})\.\s+(.*)$", re.S)
RECITAL = re.compile(r"^([A-Z]{1,2})\.\s+(whereas.*)$", re.S | re.I)
MOTION = "MOTION FOR A EUROPEAN PARLIAMENT RESOLUTION"
AFTER_MOTION = ("EXPLANATORY STATEMENT", "INFORMATION ON ADOPTION", "ANNEX",
                "OPINION OF THE COMMITTEE", "FINAL VOTE BY ROLL CALL")


def numbered(paras):
    """{'78': '78. Calls on ...', 'AD': 'AD. whereas ...'} for the motion in a
    report or adopted text, keyed the way the roll calls name them.

    Reports carry a table of contents, the motion, then the explanatory
    statement and committee opinions with their own numbering; the motion
    is the stretch from its heading to the first of those, or the whole
    document when there is no heading (an adopted text)."""
    starts = [i for i, p in enumerate(paras) if MOTION in p.upper()]
    start = starts[-1] if starts else 0
    end = len(paras)
    for i in range(start + 1, len(paras)):
        if paras[i].upper().startswith(AFTER_MOTION):
            end = i
            break
    out = {}
    for p in paras[start:end]:
        m = OPERATIVE.match(p) or RECITAL.match(p)
        if m and m.group(1) not in out:
            out[m.group(1)] = p
    return out
