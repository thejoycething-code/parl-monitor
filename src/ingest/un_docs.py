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
from urllib.parse import urlsplit

from src.http import RobotsRefused

DOC_URL = "https://docs.un.org/{lang}/{symbol}?direct=true"

# ROBOTS.TXT ON THE REDIRECT (13 October 2026). docs.un.org/<symbol>
# ?direct=true now answers 302 to documents.un.org/api/symbol/access?s=...,
# and documents.un.org/robots.txt reads "User-agent: * / Disallow: /doc,
# /access, /api". The HTTP client used to follow that redirect unasked; it
# now asks robots.txt about every hop (src/http._RedirectHandler), and every
# fetch here goes through the robots guard (_guarded), so the walks below
# are refused before anything reaches documents.un.org. A refusal is NOT "no
# such draft": walk_drafts raises it, and the forward look's check log says
# "could not read: robots.txt disallows (documents.un.org)", so the DM calls
# the number of new drafts unknown, never zero. Resumes by itself if the
# redirect or the robots.txt changes.
#
# Routes tried for the drafts and their titles instead (every request with
# the honest User-Agent, seconds apart; docs/un-sources.md has the table):
#   * UN Journal API (journal-api.un.org, robots.txt 404): GA plenary
#     agendas name the draft symbols they act on ("Item 129: Draft
#     resolution (A/81/L.6)"), already read; the GA calendar also lists
#     informal consultations on drafts with their titles ("Informal
#     consultations on the draft resolution entitled ..."), now read as a
#     first sign (src/ingest/un_calendar.parse_ga_consultations). Third
#     Committee consultations are not listed there: the Journal points to
#     iGov. USED.
#   * PGA letters (www.un.org/pga/81/, robots.txt allows, Crawl-delay 10):
#     name the drafts they submit ("to be annexed to draft resolution
#     A/81/L.6"). Already read; a draft named there or on a plenary agenda
#     is now known by its symbol and that context even when its PDF cannot
#     be read (named_drafts). USED.
#   * www.un.org/en/ga/info/draft/ (allowed): a stale list (A/66/L.n).
#     www.un.org/en/ga/third/81/documentation.shtml (allowed): lists L.1
#     (organisation of work) only. Not used.
#   * igov.un.org (the GA's "iGov" portal; robots.txt answers the app page,
#     so no rules): the proposals feed its own app loads
#     (igov/api/proposals/<session>/<committee>) answers an empty list for
#     sessions 80 and 81. Not used; worth re-checking once action begins.
#   * press.un.org (allowed but /search/): meetings coverage names drafts
#     and votes on the day of action, which is after the first sign. Not
#     wired.
#   * digitallibrary.un.org: robots.txt disallows /search and /rss, and a
#     record can only be found by search. Not used.
#   * research.un.org (allowed for '*', Crawl-delay 10): guides that link to
#     docs.un.org. Not a source of its own.
#   * daccess-ods.un.org, documents-dds-ny.un.org: robots.txt disallows the
#     document paths too. Wayback or any cache: not tried, on purpose.
#
# Tried again 16 October 2026 (the UN DM of that morning could title only
# A/81/L.4); every request with the honest User-Agent, seconds apart:
#   * igov.un.org, the GA's iGov portal: no robots.txt (the path answers the
#     app page, so no rules). The documents-by-agenda-item list its own app
#     loads, /igov/api/meetings/getdocumentsbysession/<session>?body=<body>
#     (body "GA" for the plenary, "Third Committee"), gives every document
#     issued under each agenda item, L-documents included, with the official
#     title and type: A/81/L.2 to L.6 and L.1/Rev.1 on 16 October 2026,
#     e.g. A/81/L.3 "United Nations Declaration on Sea-level Rise", A/81/L.5
#     the Cuba embargo resolution (named nowhere else we read). It lags and
#     is incomplete (29 of session 80's ~70 Third Committee L-documents), so
#     a draft it does not list is still unknown, never absent. Reachable
#     from GitHub's runners too (probe-hosts run 38870091411). USED for
#     symbol + title + agenda item (fetch_igov_drafts); one request a body a
#     run. The proposals feed (igov/api/proposals/...) still answers an
#     empty list for sessions 79 to 81 whatever the committee.
#   * igov.un.org/igov/api/undoc?symbol=... serves the PDF, relayed from
#     documents.un.org. NOT USED, on purpose: it is the very document
#     documents.un.org/robots.txt keeps robots from, fetched through
#     another host (the same reasoning as no Wayback, no cache).
#   * digitallibrary.un.org: robots.txt still disallows /search and /rss,
#     and now (malformed, missing its colon, but the intent is plain and is
#     honoured) "/record/*/export/*", which is the MARCXML export. The
#     record pages (/record/<id>) and the sitemap answer 202 with an empty
#     body and "x-amzn-waf-action: challenge" (an AWS WAF bot challenge):
#     not defeated. OAI-PMH (/oai2d, allowed) answers, but ListSets still
#     exposes only "sanctions", ListIdentifiers from 2026-10-10 returns only
#     sanctions records, and GetRecord on any other id says idDoesNotExist;
#     its Identify adds "Full content ... may not be harvested by robots".
#     Not used.
#   * PGA letter PDFs (/pga/wp-content/uploads/..., allowed): one-page
#     scanned images with no text layer; they do not enclose the draft.
#     The letter PAGES (already read) name the symbol: "to be annexed to
#     draft resolution A/81/L.3". Not used beyond that.
#   * undocs.org: 301 to docs.un.org (and so to documents.un.org). The
#     docs.un.org page without ?direct=true is a 4KB "Document Viewer"
#     shell framing documents.un.org/api/symbol/access: no title. Not used.
#   * www.un.org/en/ga/81/resolutions.shtml: "The list of resolutions will
#     be displayed here" (empty so far, and adopted resolutions only).
#     www.un.org/en/ga/third/81/proposalstatus.shtml: 404; the Third
#     Committee's documentation page links "Status of draft proposals" to
#     iGov. Not used.
#   * press.un.org (allows all but /search/): titles on the day of action,
#     after the first sign. Not wired.
# DRAFT TEXT: no permitted route on 16 October 2026. Titles come from iGov;
# classification is on the title (and the PGA letter or Journal agenda that
# names it). A permission request to the UN's documents team is drafted.
ROBOTS_NOTE = "robots.txt disallows (documents.un.org)"


def refusal_note(exc):
    """'robots.txt disallows (<host>)' for a refused fetch, naming the host
    whose robots.txt refused (the redirect target, not docs.un.org)."""
    reason = str(getattr(exc, "reason", "") or exc)
    m = re.search(r"disallows (\S+)", reason)
    host = urlsplit(m.group(1)).netloc if m else ""
    return "robots.txt disallows ({0})".format(host) if host else reason



def refusal_detail(exc):
    """The check-log line for a refusal: the note, then where the redirect
    went (path only), short enough for the DM. 'robots.txt disallows
    (documents.un.org): docs.un.org redirects to
    https://documents.un.org/api/symbol/access'."""
    reason = str(getattr(exc, "reason", "") or exc)
    m = re.search(r"disallows (\S+)", reason)
    if not m:
        return reason
    hop = urlsplit(m.group(1))
    origin = re.search(r"redirected from (\S+?)\)", reason)
    src = urlsplit(origin.group(1)).netloc if origin else ""
    where = "{0}://{1}{2}".format(hop.scheme, hop.netloc, hop.path)
    if src:
        return "{0}: {1} redirects to {2}".format(refusal_note(exc), src, where)
    return "{0}: {1}".format(refusal_note(exc), where)


def _guarded(client):
    """Every fetch here asks robots.txt (and, through the client, every
    redirect hop). A real HttpClient is wrapped once (kept on the client);
    an already guarded client and the tests' fake clients pass through."""
    from src.http import HttpClient
    from src.robots_guard import GuardedClient, guard
    if isinstance(client, GuardedClient) or not isinstance(client, HttpClient):
        return client
    wrapped = client.__dict__.get("_undocs_guard")
    if wrapped is None:
        wrapped = guard(client, "undocs")
        client.__dict__["_undocs_guard"] = wrapped
    return wrapped

# The two bodies whose drafts matter to us. Third Committee takes the family,
# SRHR and religious-freedom resolutions; the HRC takes the thematic mandates.
THIRD_COMMITTEE_DRAFTS = "A/C.3/{session}/L.{n}"
HRC_DRAFTS = "A/HRC/{session}/L.{n}"
# General Assembly PLENARY drafts (13 October 2026). The political
# declarations of high-level meetings are adopted here, not in a committee:
# A/81/L.6, "Political declaration on pandemic prevention, preparedness and
# response", dated 5 October 2026 and adopted on 12 October, was never seen
# because only the Third Committee and HRC series were walked. Same walk,
# same existence test, same first-page parse.
GA_PLENARY_DRAFTS = "A/{session}/L.{n}"


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
    raw = _guarded(client).get_bytes(url, "undocs", symbol.replace("/", "-"), first_bytes=64)
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
    raw = _guarded(client).get_bytes(doc_url(symbol, lang), "undocs",
                                     "text-" + symbol.replace("/", "-"))
    if raw[:5] != b"%PDF-":
        return ""
    reader = pypdf.PdfReader(io.BytesIO(raw))
    wanted = reader.pages if pages is None else reader.pages[:pages]
    return "\n".join((p.extract_text() or "") for p in wanted)


# A mandate resolution creates, renews or ends a Special Rapporteur, Independent
# Expert or Working Group. These are the most PREDICTABLE campaign moments in
# the system -- mandates run on three-year cycles, so the renewal vote is
# knowable years ahead -- and they were sitting in the store as ordinary
# resolutions until 2026-08-17.
_MANDATE = re.compile(
    r"mandate of (?:the )?(?:special rapporteur|independent expert|"
    r"working group|special representative)"
    r"|renewal of the mandate"
    r"|(?:establish\w*|creation of) (?:a |the )?(?:new )?"
    r"(?:special rapporteur|mandate|independent expert)", re.I)

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
# A plenary draft put forward by the President carries no sponsor list: its
# own title follows "Draft resolution submitted by the President of the
# General Assembly" and runs to "The General Assembly", whose comma pypdf
# sometimes loses (A/81/L.6).
_BODY_LINE = re.compile(r"^The (Human Rights Council|General Assembly|Third Committee)\s*,?$", re.I)


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
    def event(self):
        """The campaign-relevant EVENT type, where the text is one.

        A campaign needs a date, a decider and a decision that can still go
        either way. "mandate" is the clearest of those in the UN system: the
        holder of a mandate writes the reports that shift norms, and the
        renewal vote is a fixed, recurring, winnable moment.
        """
        if _MANDATE.search(self.topic or ""):
            return "mandate"
        return None

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
    if draft.title is None and draft.sponsors and _SUBMITTED.match(draft.sponsors):
        draft.title = _title_after_submitted(lines, draft.sponsors)
    return draft


def _title_after_submitted(lines, sponsors):
    """The lines between "Draft resolution submitted by ..." and the body.

    Added 13 October 2026 for GA plenary drafts. Without it A/81/L.6 was
    classified on its agenda item, "Global health and foreign policy", which
    matches nothing, instead of its title, "Political declaration on pandemic
    prevention, preparedness and response", which is our ground.
    """
    try:
        start = lines.index(sponsors) + 1
    except ValueError:
        return None
    title = []
    for line in lines[start:start + 4]:
        if _BODY_LINE.match(line) or line.lower().startswith("the general assembly"):
            break
        title.append(line)
    text = re.sub(r"\s+", " ", " ".join(title)).strip(" :,.")
    return text if 8 < len(text) < 260 else None


def enumerate_drafts(client, pattern, session, max_n=120, stop_after_misses=5, start=1):
    """Draft symbols that exist for a session, walking L.1 upward.

    Stops after `stop_after_misses` consecutive misses rather than at the
    first one: numbering has gaps in practice (a withdrawn or renumbered
    draft), and stopping at the first hole would silently truncate the set.
    Returns (documents, checked) so the caller can report the cost.

    start (13 October 2026, additive): resume after the highest symbol a
    store already holds, so a weekly run checks only what may be new
    instead of re-walking a session at ~10 s a symbol.
    """
    found, checked, _errors = walk_drafts(client, pattern, session, max_n=max_n,
                                          stop_after_misses=stop_after_misses, start=start)
    return found, checked


def walk_drafts(client, pattern, session, max_n=120, stop_after_misses=5, start=1):
    """enumerate_drafts, plus the symbols whose check FAILED.

    A fetch error counts as a miss for the walk, but it is not the same as
    "no such draft". A robots.txt refusal (RobotsRefused) is raised at the
    first symbol rather than counted: it is a refusal of the source. The UN check log (src/un_checks.py) needs the
    difference: a walk where every check failed could not read docs.un.org,
    and must never be reported as "no new drafts".
    """
    found, misses, checked, errors = [], 0, 0, []
    for n in range(max(1, start), max_n + 1):
        symbol = pattern.format(session=session, n=n)
        checked += 1
        try:
            doc = head(client, symbol)
        except RobotsRefused:
            # robots.txt refused (13 October 2026: the redirect to
            # documents.un.org/api/...). Every symbol goes the same way, so
            # stop at once and let the caller say "could not read".
            raise
        except Exception:
            errors.append(symbol)
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
    return found, checked, errors


# ---------------------------------------------------------------------------
# iGov: the GA's own list of documents per agenda item (16 October 2026).
# See the routes note at the top. The JSON its app loads; no robots.txt on
# igov.un.org, asked anyway through the robots guard; one request a body.

IGOV_DOCS_URL = "https://igov.un.org/igov/api/meetings/getdocumentsbysession/{session}?body={body}"
IGOV_HOST = "igov.un.org"
# (label, iGov body name, the L-series prefix it holds)
IGOV_BODIES = (
    ("GA plenary", "GA", "A/{session}/L."),
    ("Third Committee", "Third Committee", "A/C.3/{session}/L."),
)
_IGOV_DATE = re.compile(r"^(\d{1,2})/(\d{1,2})/(20\d\d)$")
_IGOV_ITEM = re.compile(r"^(\d+)")


@dataclass
class Listed:
    """A draft as iGov lists it: symbol, title, agenda item. No text."""
    symbol: str
    title: str = ""
    kind: str = ""               # "Draft resolution", "Draft decision", "" (iGov leaves it blank)
    agenda_item: int = None
    agenda_label: str = ""       # iGov's own item label: "68(b)"
    agenda_title: str = ""
    body: str = ""               # "General Assembly" | "Third Committee"
    dated: object = None         # datetime.date, only when plausible (see parse)

    @property
    def is_programme_of_work(self):
        return "organization of" in (self.title or "").lower() and "work" in (self.title or "").lower()


def _igov_date(text, session):
    """iGov's 'dd/mm/yyyy', kept only inside the session (it carries
    placeholders: A/C.3/81/L.1 is dated 31/12/2025, before the session)."""
    import datetime
    m = _IGOV_DATE.match((text or "").strip())
    if not m:
        return None
    try:
        day = datetime.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None
    opens = datetime.date(1945 + int(session), 9, 1)
    return day if opens <= day <= opens.replace(year=opens.year + 1) else None


def parse_igov_documents(payload, session, prefix):
    """The L-documents of one body from iGov's documents-by-session JSON.

    payload: a list of agenda items, each {AG_Item, AG_Title, documents:
    [{DD_symbol1, DD_officialTitle, DD_workingTitle, DD_documentType,
    DD_officialDate, ...}]}. A symbol is kept once (a document listed under
    two items keeps the first). The organisation-of-work note (L.1 in the
    Third Committee) is dropped: it is not a draft.
    """
    head = prefix.format(session=session)
    out, seen = [], set()
    for item in payload or []:
        if not isinstance(item, dict):
            continue
        label = str(item.get("AG_Item") or "").strip()
        num = _IGOV_ITEM.match(label)
        for doc in item.get("documents") or []:
            symbol = re.sub(r"\s+", "", str(doc.get("DD_symbol1") or ""))
            if not symbol.startswith(head) or symbol in seen:
                continue
            seen.add(symbol)
            title = re.sub(r"\s+", " ", (doc.get("DD_officialTitle") or doc.get("DD_workingTitle")
                                         or "")).strip()
            listed = Listed(symbol=symbol, title=title, kind=(doc.get("DD_documentType") or "").strip(),
                            agenda_item=int(num.group(1)) if num else None, agenda_label=label,
                            agenda_title=re.sub(r"\s+", " ", item.get("AG_Title") or "").strip(),
                            body="Third Committee" if "/C.3/" in symbol else "General Assembly",
                            dated=_igov_date(doc.get("DD_officialDate") or doc.get("DD_workingDate"),
                                             session))
            if listed.is_programme_of_work:
                continue
            out.append(listed)
    return sorted(out, key=lambda l: _symbol_key(l.symbol))


def _symbol_key(symbol):
    """A/81/L.10 after A/81/L.9; a revision after its original."""
    return [int(p) if p.isdigit() else p for p in re.split(r"(\d+)", symbol)]


def fetch_igov_drafts(client, session, bodies=IGOV_BODIES, log=None):
    """(listed, failures): the L-documents iGov lists for each body.

    `client` should be robots-guarded (robots_guard.guard); a body that will
    not load is named in failures with the reason, never read as empty.
    """
    from urllib.parse import quote
    if hasattr(client, "set_host_throttle"):
        client.set_host_throttle(IGOV_HOST, 3)
    listed, failures = [], []
    for label, body, prefix in bodies:
        url = IGOV_DOCS_URL.format(session=session, body=quote(body))
        try:
            payload = client.get_json(url, "igov", "docs-{0}-{1}".format(
                session, body.lower().replace(" ", "-")))
        except Exception as exc:
            failures.append("{0}: {1}".format(label, str(getattr(exc, "reason", "") or exc)[:120]))
            continue
        if not isinstance(payload, list):
            failures.append("{0}: unexpected payload ({1})".format(label, type(payload).__name__))
            continue
        listed.extend(parse_igov_documents(payload, session, prefix))
    return listed, failures
