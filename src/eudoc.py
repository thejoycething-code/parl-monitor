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

DISTRIBUTION = "https://data.europarl.europa.eu/distribution/doc/{0}_en.{1}"

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


def url_for(identifier, fmt="docx"):
    """The distribution URL for 'TA-10-2026-0313'."""
    return DISTRIBUTION.format(identifier, fmt)


def paragraphs(blob):
    """The document's paragraphs, in order. Raises for anything that is not a
    readable .docx, so a bot-wall HTML page cannot be mistaken for a text."""
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        xml = z.read("word/document.xml").decode("utf-8", "replace")
    xml = re.sub(r"</w:p>", "\n", xml)
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
