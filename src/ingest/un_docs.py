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

Reading them needs pypdf (Christopher approved the dependency 2026-08-17).
A stdlib attempt returned a page of "en-GB": the body text uses subset fonts
whose bytes need the embedded ToUnicode map, which is a PDF library's job.

Two things the text gives that the symbol alone cannot:

  * every draft names its AGENDA ITEM and subject on the first page, in a
    fixed order, so the taxonomy can finally decide whether a draft is ours.
    A/C.3/80/L.20 is "Agenda item 67 / Promotion and protection of the
    rights of children" -- area 6.
  * L.1 of a session is not a draft at all: it is the Organization of Work
    note, and its annex is the committee's dated PROGRAMME OF WORK. That is
    the agenda, which had been written off as unavailable an hour earlier.
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


def document_text(client, symbol, lang="en", pages=None):
    """Full text of a document, via pypdf.

    Fetches the whole PDF, so it is not the existence check -- use head() for
    that. `pages` limits extraction to the first N, which is all a draft's
    metadata needs.
    """
    import io
    import pypdf
    raw = client.get_bytes(doc_url(symbol, lang), "undocs",
                           "text-" + symbol.replace("/", "-"))
    if raw[:5] != b"%PDF-":
        return ""
    reader = pypdf.PdfReader(io.BytesIO(raw))
    wanted = reader.pages if pages is None else reader.pages[:pages]
    return "\n".join((p.extract_text() or "") for p in wanted)


_ITEM = re.compile(r"Agenda item[s]?\s+(\d+)", re.I)
_SUBMITTED = re.compile(r"^Draft (resolution|decision)\s+submitted by", re.I)
_DATE = re.compile(r"^(\d{1,2}\s+\w+\s+20\d\d)$")
# HRC drafts end their sponsor list with ": draft resolution" and then give
# the draft's own title, prefixed with the session number.
# A sponsor list ends in one of three ways, and the third is the interesting
# one: an AMENDMENT names the draft it attacks. Amendments are how language
# gets inserted or stripped, so they are usually the contested moment, and
# seven of session 58's thirty-seven "drafts" were amendments -- all of them
# unclassifiable until this was handled.
# The colon and the phrase are often on SEPARATE lines, because the sponsor
# list wraps: "... and Zimbabwe* :" then "amendment to draft resolution
# A/HRC/58/L.7". So the leading colon is optional.
# ":*" occurs where a single sponsor carries the not-a-member footnote:
# "Ghana:* draft resolution". The asterisk sits between colon and phrase.
# "REVISED" appears in both branches: a text that has already been revised is
# by definition the fought-over one, and "amendment to revised draft
# resolution A/C.3/80/L.20/Rev.1" was missed entirely by a pattern that
# expected only "amendment to draft resolution" -- which silently dropped the
# four amendments to session 80's children's rights resolution.
_SPONSOR_FLAT = re.compile(
    r":\**\s*(?:(?P<amend>amendment)\s+to\s+(?:revised\s+)?draft\s+"
    r"(?:resolution|decision)\s*(?P<target>A/[A-Z0-9./]+?)(?=\s+\d+/|\s*$|\s+[A-Z])"
    r"|(?:revised\s+)?draft\s+(?P<kind>resolution|decision))\s+",
    re.I)
_BODY_FLAT = re.compile(
    r"The (?:Human Rights Council|General Assembly|Third Committee)\s*,|After paragraph",
    re.I)
_SPONSOR_END = re.compile(
    r"(?::\s*|^)(?:(?P<amend>amendment)\s+to\s+draft\s+(?:resolution|decision)"
    r"\s*(?P<target>A/[A-Z0-9./]+)?|draft\s+(?P<kind>resolution|decision))\s*$", re.I)
_TITLE_PREFIX = re.compile(r"^\d+/[\u2026.]+\s*")
_BODY_START = re.compile(r"^The (Human Rights Council|General Assembly|Third Committee)\s*,", re.I)


@dataclass
class Draft:
    symbol: str
    agenda_item: int = None
    subject: str = None          # the AGENDA ITEM title
    title: str = None            # the draft's OWN title, where it has one
    kind: str = None             # resolution | decision | amendment
    amends: str = None           # the draft an amendment attacks
    instruction: str = None      # an amendment's operative text
    dated: str = None
    sponsors: str = None

    @property
    def classify_on(self):
        """Title AND an amendment's operative text.

        The title alone is not enough for an amendment. A/C.3/80/L.64 is
        titled "Rights of the child" and its instruction reads: delete
        "sexual and reproductive health" from operative paragraphs 13, 27, 43
        and 46. Classified on the title it is area 6; on the instruction too
        it is areas 1 and 6, which is the truth and the reason to read it.
        Contested language lives in the instruction, not the heading.
        """
        return " ".join(p for p in (self.topic, self.instruction) if p)

    @property
    def topic(self):
        """What to classify on.

        The two bodies differ, and getting this wrong made every HRC draft
        unclassifiable. In a Third Committee draft the agenda item title IS
        the topic ("Agenda item 67 / Promotion and protection of the rights of
        children"). In an HRC draft, item 3 is an omnibus covering most
        thematic resolutions -- "Promotion and protection of all human rights,
        civil, political, economic, social and cultural rights, including the
        right to development" -- and the draft's real title comes AFTER the
        sponsor list, prefixed "58/...". Prefer the specific one.
        """
        return self.title or self.subject

    @property
    def is_programme_of_work(self):
        """L.1 is the Organization of Work note, not a draft."""
        return bool(self.subject and "organization of the work" in self.subject.lower())


def parse_draft(symbol, text):
    """Agenda item, subject and type from a draft's first page.

    The first page has a fixed shape: masthead, distribution, date, session,
    committee, "Agenda item N", then THE SUBJECT, then either a sponsor list
    or "Draft resolution submitted by ...". The subject is taken as the lines
    between the agenda item and whichever of those comes first, because it is
    sometimes wrapped over two lines.
    """
    lines = [re.sub(r"\s+", " ", l).strip() for l in (text or "").split("\n")]
    lines = [l for l in lines if l]
    draft = Draft(symbol=symbol)
    for i, line in enumerate(lines):
        if draft.dated is None and _DATE.match(line):
            draft.dated = line
        found = _ITEM.search(line)
        if found and draft.agenda_item is None:
            draft.agenda_item = int(found.group(1))
            subject = []
            for nxt in lines[i + 1:i + 5]:
                if _SUBMITTED.match(nxt):
                    draft.kind = draft.kind or _SUBMITTED.match(nxt).group(1).lower()
                    draft.sponsors = nxt
                    break
                # A sponsor list is a run of comma-separated country names;
                # the subject is not, so a comma-heavy line ends the subject.
                if nxt.count(",") >= 3:
                    draft.sponsors = nxt
                    break
                subject.append(nxt)
            if subject:
                draft.subject = " ".join(subject).strip(" :")
            break
    if draft.subject is None:
        # Organization-of-work notes carry no agenda item; use the heading.
        for line in lines[:12]:
            if "organization of the work" in line.lower():
                draft.subject = line
                break

    # The draft's OWN title, from the whole text rather than line by line.
    # The sponsor list wraps unpredictably: ": draft" can end one line with
    # "resolution" beginning the next, and ":" can end a line with "amendment
    # to draft resolution A/HRC/58/L.7" on the next. Matching per line missed
    # five of session 58's thirty-seven drafts, each silently falling back to
    # the omnibus agenda-item title.
    flat = re.sub(r"\s+", " ", text or "")
    marker = _SPONSOR_FLAT.search(flat)
    if marker:
        if marker.group("amend"):
            draft.kind = "amendment"
            draft.amends = (marker.group("target") or "").rstrip(".") or None
        else:
            draft.kind = draft.kind or (marker.group("kind") or "").lower()
        tail = flat[marker.end():]
        stop = _BODY_FLAT.search(tail)
        candidate = tail[:stop.start()] if stop else tail[:220]
        candidate = _TITLE_PREFIX.sub("", candidate.strip())
        # Footnote markers and the running header get glued on at page breaks.
        candidate = re.split(r"\s*\*\s|United Nations A/", candidate)[0]
        # An amendment's title is followed by its operative instruction
        # ("1. In the fourteenth preambular paragraph..."). Keep the title.
        parts = re.split(
            r"(\s+\d+\.\s|\s+(?:In|After|Before|Replace|Delete)\s+(?:the|operative|paragraph)\b)",
            candidate, maxsplit=1)
        candidate = parts[0]
        if len(parts) > 2:
            draft.instruction = ("".join(parts[1:])).strip()[:400]
        if 8 < len(candidate) < 260:
            draft.title = candidate.strip(" :,.")
    return draft


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
