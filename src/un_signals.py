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


@dataclass
class Signal:
    kind: str                       # DRAFT | PLENARY | LETTER
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


def _merge(*area_lists):
    out = set()
    for a in area_lists:
        out.update(a or [])
    return sorted(out)


def build_signals(letters, plenaries, drafts, tax, wl, as_of=None):
    """Every item on our ground, plus every flagged PGA letter, linked.

    letters: pga_letters.Letter; plenaries: un_calendar.Meeting (with
    agenda); drafts: DraftInfo. `as_of` drops anything dated after it, which
    is what a backtest needs (a letter of 7 October did not exist on 6
    October). Returns Signals; a letter is kept when flagged even if not on
    our ground, so the forward look can list it unmarked.
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

    out = []
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
