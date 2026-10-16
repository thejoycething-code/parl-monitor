"""The UN check log: what each source said this run, in one of three words.

Added 13 October 2026. UN output had been paused since 17 August, and the
forward look had one failure mode that hid everything else: a source that
could not be read and a source with nothing new both ended as silence, so
"nothing new" could mean "nothing was looked at". Every UN source now
reports exactly one of three statuses:

  * READ_OK     ("read OK")        -- fetched and parsed, items found;
  * READ_EMPTY  ("read but empty") -- fetched and parsed, nothing in it;
  * NOT_READ    ("could not read") -- fetch failed, refused, challenged, or
                                      the page parsed to nothing where
                                      something is always expected.

Each line also names the NEWEST item the source gave and that item's date,
so a source that is read but stale (the same session list for six months)
is visible as stale. `nothing_new()` is the only sentence a run may print
when nothing changed, and it refuses to say "nothing new" while any source
could not be read.

No em dashes anywhere in what this renders: it goes into the forward look
footer and the UN DM.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

READ_OK = "read OK"
READ_EMPTY = "read but empty"
NOT_READ = "could not read"


NEWEST_CHARS = 90
DETAIL_CHARS = 260


def shorten(text, limit):
    """`text` cut to at most `limit` characters AT A WORD BOUNDARY, with
    "..." when cut (16 October 2026: the check log printed "Fellowship
    Programme durin"). A single word longer than the limit is cut hard."""
    text = " ".join(str(text or "").split())
    if len(text) <= limit:
        return text
    cut = text[:max(1, limit - 3)]
    if " " in cut and not text[len(cut)].isspace():
        cut = cut[:cut.rindex(" ")]
    return cut.rstrip(" ,;:(") + "..."


@dataclass
class Check:
    source: str
    status: str
    count: int = 0
    newest: str = ""              # the newest item's title
    newest_date: str = ""         # ISO date of that item
    detail: str = ""              # why it could not be read, or a caveat


def _iso(value):
    if value is None:
        return ""
    if isinstance(value, datetime.datetime):
        return value.date().isoformat()
    if isinstance(value, datetime.date):
        return value.isoformat()
    return str(value)


class CheckLog:
    def __init__(self):
        self.checks = []

    def read(self, source, items, newest=None, detail="", key=None, title=None):
        """Record a source that was fetched and parsed.

        `items` is what it gave; `key` (item -> date) and `title` (item ->
        text) pick the newest one when `newest` (a (title, date) pair) is not
        passed. An empty list is READ_EMPTY, never READ_OK.
        """
        items = list(items or [])
        if newest is None and items and key is not None:
            best = max(items, key=key)
            newest = ((title(best) if title else str(best)), key(best))
        status = READ_OK if items else READ_EMPTY
        name, when = newest if newest else ("", None)
        self.checks.append(Check(source=source, status=status, count=len(items),
                                 newest=shorten(name, NEWEST_CHARS), newest_date=_iso(when),
                                 detail=detail))
        return self.checks[-1]

    def failed(self, source, reason):
        self.checks.append(Check(source=source, status=NOT_READ,
                                 detail=shorten(reason, DETAIL_CHARS)))
        return self.checks[-1]

    def unread(self):
        return [c for c in self.checks if c.status == NOT_READ]

    def lines(self):
        """One line per source, aligned, plain text."""
        width = max([len(c.source) for c in self.checks] + [10])
        out = []
        for c in self.checks:
            line = "{0:<{w}}  {1:<15}".format(c.source, c.status.upper(), w=width)
            if c.status == NOT_READ:
                line += "  " + c.detail
            else:
                line += "  {0} item(s)".format(c.count)
                if c.newest:
                    line += "; newest {0}: {1}".format(c.newest_date or "undated", c.newest)
                if c.detail:
                    line += " ({0})".format(c.detail)
            out.append(line.rstrip())
        return out

    def nothing_new(self):
        """The sentence for a run with no changes. Never 'nothing new' while
        a source could not be read: that would be a guess, not a finding."""
        bad = self.unread()
        if not bad:
            return "No changes since the last run (all {0} sources read).".format(len(self.checks))
        return ("NOT 'nothing new': {0} of {1} sources could not be read ({2}), "
                "so changes there are unknown.".format(
                    len(bad), len(self.checks), ", ".join(c.source for c in bad)))
