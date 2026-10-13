"""Letters from the President of the General Assembly: where plenary dates
are announced first.

Added 13 October 2026. On 12 October the General Assembly voted on the
political declaration on pandemic prevention, preparedness and response
(draft A/81/L.6). The date had been public since 7 October, in a PGA letter
to all permanent representatives titled "Submission of the political
declaration on pandemic prevention, preparedness and response to the General
Assembly for adoption, 12 October 2026". Nothing read these letters, so the
monitor missed the vote. The Journal lists a plenary only a few days ahead
and its programme notes then say "Letters from the President of the General
Assembly, dated 7 October 2026 ... were sent": the letter is the first sign.

WHERE, probed 13 October 2026 (not assumed):

  * www.un.org/pga/ and www.un.org/pga/81/ are the 81st President's site
    (WordPress). Its menu links "Letters to Member States" at
    www.un.org/pga/81/documents/letters/ ; www.un.org/pga/81/letters/ serves
    the same listing. www.un.org/pga/81/letters-from-the-pga/ is a 404.
  * The listing is plain HTML, one block per letter: a day ("7"), a
    "MON YYYY" line ("Oct 2026"), the title as a link to the letter's own
    page, the addressees ("To all Permanent Representatives and Permanent
    Observers") and a PDF link. 16 letters, 16 September to 9 October 2026,
    on one page (no pagination yet).
  * Each letter's page carries a short summary of the letter in plain HTML
    ("He has now submitted the political declaration, to be annexed to draft
    resolution A/81/L.6, for consideration by the General Assembly at its
    plenary meeting on 12 October 2026"), so the PDF does not need reading.
  * robots.txt (www.un.org) allows /pga/ and asks Crawl-delay: 10, which is
    honoured (CRAWL_DELAY below; fetch through robots_guard.guard so the
    rule is re-read on every run). Not bot-challenged and no 403, from the
    laptop, on 13 October 2026.
  * IF IT IS EVER BLOCKED (a challenge page, a 403): do not defeat it.
    Routes to try, all legitimate: the letter PDFs under
    /pga/wp-content/uploads/ (linked from the listing, same host); the
    site's WordPress feed or REST API (/pga/81/feed/, /pga/81/wp-json/,
    both allowed by robots.txt); and the Journal's own meeting programme
    notes, which name the PGA letters behind each plenary by date (src/ingest
    /un_calendar.fetch_meeting_detail). A challenge is reported as "could
    not read" with its reason (BlockedError), never as an empty listing.

The session number moves every September: the session opening in September
of year Y is Y - 1945, so a date before September belongs to Y - 1946.
"""

from __future__ import annotations

import datetime
import html as _html
import re
from dataclasses import dataclass, field

LETTERS_URL = "https://www.un.org/pga/{0}/documents/letters/"
PGA_HOST = "www.un.org"
CRAWL_DELAY = 10            # robots.txt, www.un.org, read 13 October 2026
BODY_DAYS = 21              # letters this recent have their page read too

MONTHS = ("January February March April May June July August September "
          "October November December").split()
_MON3 = [m[:3].lower() for m in MONTHS]

_TAGS = re.compile(r"<[^>]+>")
_LETTER_LINK = re.compile(
    r'<a\s+href="(https://www\.un\.org/pga/\d+/documents/letters/[^"#?]+/)"[^>]*>(.*?)</a>',
    re.S | re.I)
_BLOCK_DATE = re.compile(
    r">\s*(\d{1,2})\s*</div>\s*<div[^>]*>\s*([A-Za-z]{3,9})\.?\s+(20\d\d)\s*</div>", re.S)
_SLUG_DATE = re.compile(r"-(\d{1,2})-(" + "|".join(m.lower() for m in MONTHS) + r")-(20\d\d)/?$")
_PDF = re.compile(r'href="([^"]+\.pdf)"', re.I)
_ADDRESSEE = re.compile(r">\s*(To all [^<]{5,120}?)\s*<", re.I)
# A date in UN prose: "12 October 2026", or "12 October" with the year implied.
_DATE = re.compile(r"\b(\d{1,2})\s+(" + "|".join(MONTHS) + r")(?:\s+(20\d\d))?\b")
_SYMBOL = re.compile(r"\bA/(?:C\.\d/)?\d{2}/(?:L\.\d+|\d+)(?:/(?:Rev|Add|Corr)\.\d+)*")
# The words that make a letter a scheduling signal. "adoption" and "political
# declaration" are Chris's (13 October 2026); a plenary or a high-level
# meeting is where the Assembly decides.
SIGNALS = (
    ("plenary", re.compile(r"\bplenary\b", re.I)),
    ("high-level meeting", re.compile(r"\bhigh[- ]level (?:meeting|plenary)", re.I)),
    ("adoption", re.compile(r"\badopt(?:ion|ed)?\b", re.I)),
    ("political declaration", re.compile(r"\bpolitical declaration\b", re.I)),
    ("draft resolution", re.compile(r"\bdraft (?:resolution|decision)\b", re.I)),
)


class BlockedError(Exception):
    """The listing answered with a bot challenge instead of letters."""


@dataclass
class Letter:
    dated: datetime.date
    title: str
    url: str
    pdf: str = ""
    addressee: str = ""
    body: str = ""
    announced: tuple = ()        # meeting dates the letter names (after its own date)
    symbols: tuple = ()          # document symbols it names (A/81/L.6)
    signals: tuple = ()          # which SIGNALS words it carries
    areas: list = field(default_factory=list)   # our issue areas (caller fills)

    @property
    def match_text(self):
        return " ".join(p for p in (self.title, self.body) if p)

    @property
    def flagged(self):
        """A scheduling signal or our ground. Either is worth a line."""
        return bool(self.signals or self.areas or self.announced)

    @property
    def next_date(self):
        """The first meeting date the letter announces, or None."""
        return min(self.announced) if self.announced else None


def session_for(day):
    """The GA session sitting on `day` (81 from September 2026)."""
    return day.year - 1945 if day.month >= 9 else day.year - 1946


def _plain(text):
    text = re.sub(r"(?s)<(script|style)[^>]*>.*?</\1>", " ", text or "")
    return re.sub(r"\s+", " ", _html.unescape(_TAGS.sub(" ", text))).strip()


def _month(name):
    key = name[:3].lower()
    return _MON3.index(key) + 1 if key in _MON3 else None


def is_challenge(html_text):
    """A bot-challenge page rather than the site (Cloudflare and kin)."""
    head = (html_text or "")[:4000]
    return ("Just a moment" in head or "cf-chl" in head
            or "challenge-platform" in head or "Attention Required" in head)


def parse_letters(html_text):
    """Letters on the listing page, newest first.

    Each title link is taken once (the "Read the letter" button repeats it).
    The date comes from the block's own day and month lines; when those are
    missing, from the slug ("...-7-october-2026/"), which every letter so far
    carries. A letter with neither is skipped rather than dated by guesswork.
    """
    if is_challenge(html_text):
        raise BlockedError("bot challenge page served instead of the letters listing")
    out, seen = [], set()
    links = list(_LETTER_LINK.finditer(html_text or ""))
    for i, m in enumerate(links):
        url, label = m.group(1), _plain(m.group(2))
        if url in seen or not label or label.lower().startswith("read the letter"):
            continue
        label = label.rstrip(" →").strip()
        seen.add(url)
        before = html_text[max(0, m.start() - 1500):m.start()]
        dated = None
        found = list(_BLOCK_DATE.finditer(before))
        if found:
            d, mon, y = found[-1].groups()
            if _month(mon):
                try:
                    dated = datetime.date(int(y), _month(mon), int(d))
                except ValueError:
                    dated = None
        if dated is None:
            s = _SLUG_DATE.search(url)
            if s:
                try:
                    dated = datetime.date(int(s.group(3)), _month(s.group(2)), int(s.group(1)))
                except ValueError:
                    dated = None
        if dated is None:
            continue
        nxt = next((l.start() for l in links[i + 1:] if l.group(1) != url), len(html_text))
        after = html_text[m.end():nxt]
        pdf = _PDF.search(after)
        to = _ADDRESSEE.search(after)
        letter = Letter(dated=dated, title=label, url=url,
                        pdf=pdf.group(1) if pdf else "",
                        addressee=_plain(to.group(1)) if to else "")
        annotate(letter)
        out.append(letter)
    return sorted(out, key=lambda l: l.dated, reverse=True)


def parse_letter_body(html_text):
    """The letter's summary text from its own page.

    The page gives a meta description and, below the addressee and date, a
    paragraph summarising the letter, ending at "Download the letter". Both
    are kept: the description is short and reliable, the paragraph carries
    the detail (the draft symbol, the meeting date).
    """
    if is_challenge(html_text):
        raise BlockedError("bot challenge page served instead of the letter")
    desc = re.search(r'<meta name="description" content="([^"]*)"', html_text or "")
    text = _plain(html_text)
    body = ""
    m = re.search(r"(?:Permanent Observers|Member States|Representatives)\s*(?:·|&middot;)?\s*"
                  r"\d{1,2} \w+ 20\d\d (.*?) Download the letter", text)
    if m:
        body = m.group(1).strip()
    parts = [_html.unescape(desc.group(1)).strip()] if desc else []
    if body and body not in parts:
        parts.append(body)
    return " ".join(parts)


def announced_dates(text, letter_date):
    """Meeting dates a letter names: dates AFTER the letter's own date.

    "held on 25 September 2026" is history and "dated 6 October" is the
    letter itself; "at its plenary meeting on 12 October 2026" is the
    signal. A date with no year takes whichever year puts it nearest the
    letter (a December letter naming "15 January" means next January).
    """
    out = []
    for d, mon, y in _DATE.findall(text or ""):
        years = [int(y)] if y else [letter_date.year - 1, letter_date.year, letter_date.year + 1]
        candidates = []
        for year in years:
            try:
                candidates.append(datetime.date(year, _month(mon), int(d)))
            except ValueError:
                continue
        if not candidates:
            continue
        day = min(candidates, key=lambda c: abs((c - letter_date).days))
        if day > letter_date and day not in out:
            out.append(day)
    return tuple(sorted(out))


def annotate(letter):
    """Fill signals, symbols and announced dates from title and body."""
    text = letter.match_text
    letter.signals = tuple(name for name, rx in SIGNALS if rx.search(text))
    symbols = []
    for s in _SYMBOL.findall(text):
        if s not in symbols:
            symbols.append(s)
    letter.symbols = tuple(symbols)
    letter.announced = announced_dates(text, letter.dated)
    return letter


def fetch_letters(client, today=None, session=None, body_days=BODY_DAYS):
    """The session's letters, the recent ones with their page read.

    Returns (letters, failures). `client` should be robots_guard.guard(...)
    around an HttpClient, so robots.txt is asked on every run; the host's
    Crawl-delay is applied here as well. A letter page that will not load is
    kept with its listing title and named in `failures`. A listing that will
    not load raises (FetchError, or BlockedError for a challenge), so the
    caller can report "could not read" rather than "no letters".
    """
    today = today or datetime.date.today()
    session = session or session_for(today)
    if hasattr(client, "set_host_throttle"):
        client.set_host_throttle(PGA_HOST, CRAWL_DELAY)
    listing = client.get_text(LETTERS_URL.format(session), "pga",
                              "letters-{0}".format(session))
    letters = parse_letters(listing)
    failures = []
    cutoff = today - datetime.timedelta(days=body_days)
    for letter in letters:
        if not (cutoff <= letter.dated <= today):
            continue
        slug = letter.url.rstrip("/").rsplit("/", 1)[-1]
        try:
            letter.body = parse_letter_body(client.get_text(letter.url, "pga", "letter-" + slug))
        except Exception as exc:
            failures.append("{0} ({1}): page not read ({2})".format(
                letter.title[:60], letter.dated, str(exc)[:80]))
            continue
        annotate(letter)
    return letters, failures
