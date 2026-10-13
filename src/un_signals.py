"""First signs on our ground at the UN: a draft tabled, a plenary listed, a
PGA letter naming a date. Alert on those, not only on the vote.

Added 13 October 2026. The General Assembly adopted the political
declaration on pandemic prevention, preparedness and response on 12 October
2026. Three things had said so in advance, each enough on its own:

  * the draft, A/81/L.6, dated 5 October 2026 (docs.un.org);
  * the PGA's letter of 7 October 2026 submitting it "for adoption, 12
    October 2026" (www.un.org/pga/81/documents/letters/);
  * the Journal listing of the 18th plenary, 12 October 2026, whose agenda
    reads "Global health and foreign policy - Item 129: Draft resolution
    (A/81/L.6) / Action on the draft resolution".

This module ties those together and decides what goes to the top of the
forward look and the UN DM. It is pure: no fetching, so the backtest
(tests/test_un_backtest.py) runs it on the archived fixtures as of a date
before the vote.

LINKING. The plenary's agenda item ("Global health and foreign policy") is
not our ground and must not be made so; the draft it acts on is. So a
plenary or a letter is on our ground when its own text matches the UN
taxonomy OR it names a draft symbol that does. A draft's due date is the
earliest plenary that lists it, or failing that the earliest meeting date a
letter naming it announces.

WHAT IS A FIRST SIGN. With a store, an item whose id this run recorded for
the first time (un_store.record's new ids). Without one (a stateless DM
run), an item tabled or announced within FIRST_SIGN_DAYS, or a plenary on
our ground listed within DUE_SOON_DAYS, since a listing has no date of its
own. Everything on our ground due within DUE_SOON_DAYS goes to the top
whether or not it is new: a reminder five days out is the point.
"""

from __future__ import annotations

import datetime
import re
from dataclasses import dataclass, field

from src import filter as filt

DUE_SOON_DAYS = 14
FIRST_SIGN_DAYS = 7
RECENT_DRAFT_DAYS = 30     # an undated-vote draft on our ground stays listed this long

MONTHS = ("January February March April May June July August September "
          "October November December").split()
_DRAFT_SYMBOL = re.compile(r"/L\.\d+")


@dataclass
class DraftInfo:
    symbol: str
    title: str = ""
    dated: datetime.date = None
    areas: list = field(default_factory=list)
    url: str = ""
    agenda_item: int = None
    # Set when the draft's own text could not be read and it is known only
    # because something named it (13 October 2026: docs.un.org's redirect to
    # documents.un.org/api/..., which robots.txt disallows): "PGA letter" or
    # "Journal agenda". `dated` is then the date it was named, not tabled.
    named_by: str = ""


@dataclass
class Signal:
    kind: str                       # DRAFT | PLENARY | LETTER | CONSULT
    id: str
    title: str
    sign_date: datetime.date = None  # when it was tabled or announced
    due: datetime.date = None        # the meeting it points at
    areas: list = field(default_factory=list)
    url: str = ""
    detail: str = ""
    obj: object = None

    @property
    def when(self):
        return self.due or self.sign_date

    @property
    def ours(self):
        return bool(self.areas)


def parse_un_date(text):
    """'5 October 2026' -> date, else None."""
    m = re.search(r"(\d{1,2})\s+(" + "|".join(MONTHS) + r")\s+(20\d\d)", text or "")
    if not m:
        return None
    try:
        return datetime.date(int(m.group(3)), MONTHS.index(m.group(2)) + 1, int(m.group(1)))
    except ValueError:
        return None


def draft_symbols(symbols):
    """Only draft symbols (A/81/L.6, A/C.3/81/L.12/Rev.1), not reports."""
    return [s for s in symbols if _DRAFT_SYMBOL.search(s)]


_LETTER_SUBJECT = re.compile(r"^(?:submission|transmission|circulation) of (?:the )?", re.I)
_LETTER_TAIL = re.compile(r"\s+to the General Assembly\b.*$|,\s*\d{1,2} \w+ 20\d\d$", re.I)
_AGENDA_SEGMENT = re.compile(r"^(?P<subject>.+?) - Item (?P<item>\d+)")


def _letter_subject(title):
    """'Submission of the political declaration on X to the General Assembly
    for adoption, 12 October 2026' -> 'political declaration on X'."""
    text = _LETTER_TAIL.sub("", _LETTER_SUBJECT.sub("", title or "").strip())
    return text.strip(" ,.") or (title or "")


def _agenda_subject(agenda, symbol):
    """(subject, item) of the agenda segment that names `symbol`:
    'Global health and foreign policy - Item 129: Draft resolution
    ( A/81/L.6 )' -> ('Global health and foreign policy', 129)."""
    for seg in (agenda or "").split(" ; "):
        if re.search(re.escape(symbol) + r"(?![\d/])", seg.replace(" ", "")):
            m = _AGENDA_SEGMENT.match(seg.strip())
            if m:
                return m.group("subject").strip(), int(m.group("item"))
    return "", None


def drafts_named(letters, meetings, tax, wl, meeting_date=None, doc_url=None):
    """DraftInfo for every draft symbol a PGA letter or a Journal agenda
    names, built from what names it (13 October 2026).

    The draft's own PDF is behind docs.un.org's redirect to
    documents.un.org/api/..., which documents.un.org/robots.txt disallows,
    so its title and date cannot be read. What names it still says what it
    is: a PGA letter's title ("Submission of the political declaration on
    pandemic prevention, preparedness and response ...", classified on the
    letter's whole text) and a Journal agenda's item ("Global health and
    foreign policy - Item 129"). `dated` is when it was NAMED (the letter's
    date; for a meeting, meeting_date(m) when given, else None), and
    named_by says by what, so nothing claims a tabling date it never read.
    """
    out = {}
    for l in letters or []:
        for s in draft_symbols(getattr(l, "symbols", ()) or ()):
            areas = filt.filter_item(tax, wl, l.match_text).issue_areas
            d = out.get(s)
            if d is None:
                out[s] = DraftInfo(symbol=s, title=_letter_subject(l.title), dated=l.dated,
                                   areas=list(areas), url=doc_url(s) if doc_url else "",
                                   named_by="PGA letter")
                continue
            d.areas = _merge(d.areas, areas)
            if l.dated and (d.dated is None or l.dated < d.dated):
                d.dated, d.named_by, d.title = l.dated, "PGA letter", _letter_subject(l.title)
    for m in meetings or []:
        when = meeting_date(m) if meeting_date else None
        for s in draft_symbols(getattr(m, "symbols", ()) or ()):
            subject, item = _agenda_subject(m.agenda, s)
            areas = filt.filter_item(tax, wl, subject).issue_areas if subject else []
            d = out.get(s)
            if d is None:
                out[s] = DraftInfo(symbol=s, title=subject, dated=when, areas=list(areas),
                                   url=doc_url(s) if doc_url else "", agenda_item=item,
                                   named_by="Journal agenda")
                continue
            d.areas = _merge(d.areas, areas)
            d.agenda_item = d.agenda_item or item
            if when and (d.dated is None or when < d.dated):
                d.dated, d.named_by = when, "Journal agenda"
    return list(out.values())


def _merge(*area_lists):
    out = set()
    for a in area_lists:
        out.update(a or [])
    return sorted(out)


def build_signals(letters, plenaries, drafts, tax, wl, as_of=None, consultations=(),
                  committee_meetings=()):
    """Every item on our ground, plus every flagged PGA letter, linked.

    letters: pga_letters.Letter; plenaries: un_calendar.Meeting (with
    agenda); drafts: DraftInfo. `as_of` drops anything dated after it, which
    is what a backtest needs (a letter of 7 October did not exist on 6
    October). Returns Signals; a letter is kept when flagged even if not on
    our ground, so the forward look can list it unmarked.

    consultations (13 October 2026): un_calendar.Consultation, informal
    consultations on a draft, a CONSULT signal when the draft's title is on
    our ground. committee_meetings: Third Committee meetings with their
    agendas read; only used to date the drafts they act on.
    """
    by_symbol = {d.symbol: d for d in drafts
                 if not (as_of and d.dated and d.dated > as_of)}
    letters = [l for l in letters if not (as_of and l.dated > as_of)]

    def symbol_areas(symbols):
        return _merge(*[by_symbol[s].areas for s in symbols if s in by_symbol])

    due = {}

    def note_due(symbol, day):
        if day and (symbol not in due or day < due[symbol]):
            due[symbol] = day

    for m in committee_meetings or ():
        for s in draft_symbols(m.symbols):
            note_due(s, m.starts.date())

    out = []
    for c in consultations or ():
        areas = filt.filter_item(tax, wl, c.match_text).issue_areas
        if not areas:
            continue
        bits = [c.starts.strftime("%H:%M") + " informal consultations"]
        if c.agenda_item:
            bits.append("agenda item {0}".format(c.agenda_item))
        if c.convened_by:
            bits.append("convened by " + c.convened_by)
        out.append(Signal(kind="CONSULT", id="consult:" + (c.id or c.title[:60]),
                          title="Draft in negotiation: " + (c.draft_title or c.title),
                          sign_date=None, due=c.starts.date(), areas=areas,
                          url=c.url, detail="; ".join(bits), obj=c))

    for m in plenaries:
        own = filt.filter_item(tax, wl, m.title, m.agenda).issue_areas
        named = draft_symbols(m.symbols)
        areas = _merge(own, symbol_areas(named))
        for s in named:
            note_due(s, m.starts.date())
        if not areas:
            continue
        acts_on = [s for s in named if s in by_symbol and by_symbol[s].areas]
        detail = m.starts.strftime("%H:%M") + " " + (
            "acts on " + ", ".join("{0} ({1})".format(s, by_symbol[s].title[:100]) for s in acts_on)
            if acts_on else m.agenda[:140])
        out.append(Signal(kind="PLENARY", id="plenary:" + (m.id or m.title),
                          title="General Assembly: " + m.title,
                          sign_date=None, due=m.starts.date(), areas=areas,
                          url=m.url, detail=detail, obj=m))

    for l in letters:
        own = filt.filter_item(tax, wl, l.match_text).issue_areas
        named = draft_symbols(l.symbols)
        l.areas = _merge(own, symbol_areas(named))
        for s in named:
            note_due(s, l.next_date)
        if not (l.flagged or l.areas):
            continue
        bits = ["PGA letter of {0}".format(l.dated.strftime("%d %B %Y").lstrip("0"))]
        if l.announced:
            bits.append("names " + ", ".join(d.strftime("%d %B %Y").lstrip("0") for d in l.announced))
        if named:
            bits.append("on " + ", ".join(named))
        slug = l.url.rstrip("/").rsplit("/", 1)[-1]
        out.append(Signal(kind="LETTER", id="letter:" + slug, title=l.title,
                          sign_date=l.dated, due=l.next_date, areas=l.areas,
                          url=l.url, detail="; ".join(bits), obj=l))

    for d in by_symbol.values():
        if not d.areas:
            continue
        if d.named_by:
            detail = "named by {0}{1} (text not read)".format(
                d.named_by, " of " + d.dated.strftime("%d %B %Y").lstrip("0") if d.dated else "")
        else:
            detail = "tabled {0}".format(d.dated.strftime("%d %B %Y").lstrip("0") if d.dated else "(date unread)")
        if d.agenda_item:
            detail += ", agenda item {0}".format(d.agenda_item)
        if d.symbol in due:
            detail += "; taken {0}".format(due[d.symbol].strftime("%d %B %Y").lstrip("0"))
        out.append(Signal(kind="DRAFT", id="draft:" + d.symbol,
                          title="{0}: {1}".format(d.symbol, d.title or "(title unread)"),
                          sign_date=d.dated, due=due.get(d.symbol), areas=d.areas,
                          url=d.url, detail=detail, obj=d))
    return sorted(out, key=lambda s: (s.when or datetime.date.max, s.kind))


def in_forward_look(signal, today, days):
    """Whether a signal belongs in the chronological list at all."""
    if signal.due and signal.due >= today:
        return (signal.due - today).days <= days
    if signal.kind == "DRAFT" and signal.ours and signal.sign_date:
        return (today - signal.sign_date).days <= RECENT_DRAFT_DAYS
    if signal.sign_date:
        return 0 <= (today - signal.sign_date).days <= FIRST_SIGN_DAYS
    return False


def due_soon(signals, today, days=DUE_SOON_DAYS):
    return [s for s in signals if s.ours and s.due and 0 <= (s.due - today).days <= days]


def first_signs(signals, today, new_ids=None, days=FIRST_SIGN_DAYS):
    """Our ground, first seen. See the module docstring for the two modes."""
    out = []
    for s in signals:
        if not s.ours:
            continue
        if new_ids is not None:
            if s.id in new_ids:
                out.append(s)
            continue
        if s.sign_date and 0 <= (today - s.sign_date).days <= days:
            out.append(s)
        elif s.kind == "PLENARY" and s.due and 0 <= (s.due - today).days <= DUE_SOON_DAYS:
            out.append(s)
        elif (s.kind == "CONSULT" and s.due
              and -days <= (s.due - today).days <= DUE_SOON_DAYS):
            # A consultation has no date of its own but its meeting's; one
            # held in the last week is still a first sign of the draft.
            out.append(s)
    return out


def _day(d):
    return d.strftime("%a %d %b %Y") if d else "undated"


def render_top(due, first, today):
    """The lines that go first in the forward look and the DM. Plain text,
    British spelling, no em dashes."""
    lines = []
    lines.append("ON OUR GROUND, DUE WITHIN {0} DAYS ({1}):".format(DUE_SOON_DAYS, len(due)))
    if not due:
        lines.append("  none listed")
    for s in due:
        lines.append("  {0}  in {1}d  {2:<7}  {3}".format(
            _day(s.due), (s.due - today).days, s.kind, s.title[:90]))
        lines.append("      areas {0}; {1}".format(",".join(str(a) for a in s.areas), s.detail[:160]))
        lines.append("      {0}".format(s.url))
    lines.append("FIRST SIGNS ON OUR GROUND ({0}):".format(len(first)))
    if not first:
        lines.append("  none")
    for s in first:
        when = "tabled/announced {0}".format(_day(s.sign_date)) if s.sign_date else "listed"
        lines.append("  {0:<7}  {1}  {2}".format(s.kind, when, s.title[:90]))
        lines.append("      areas {0}; {1}".format(",".join(str(a) for a in s.areas), s.detail[:160]))
        lines.append("      {0}".format(s.url))
    return lines
