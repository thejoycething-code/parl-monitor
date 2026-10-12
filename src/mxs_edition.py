"""The "State congresses" section of the Mexican edition (12 October 2026).

Mexico's 32 state congresses are where most of our ground moves (abortion
is state criminal law, decriminalised state by state; gender-identity
recognition, conversion-practice bans and civil unions are state laws):
docs/mexico-regions-scope.md. tools/mxs_collect.py stores what the readable
states list in mxs_items; this module turns the fortnight's items on our
ground into one section of the Mexican edition (src/editions/mx.py), placed
before its Watchlist through the framework's Country.post_render hook, so
the shared edition framework is not touched.

WHAT IT SHOWS, per state, items on our ground (taxonomy-es areas, or
watched in config/watchlist-mx-states.yaml by key):
  * new: presented (or first published) in the window;
  * moved: an older item whose status date falls in the window, with the
    source's own status words; routine handling ("Turnada", "Se toma en
    consideración", a first listing) is not a stage and is not shown;
  * a decree: an item the state lists as approved/published, by its own
    kind ('decreto').
The same noise rules as the federal items (config/edition-noise-mx.yaml)
apply. A line under the section says which states were read, when, and
which were not and why (from mxs_reads), so a quiet section is never read
as "nothing happened in 32 states".

Read-only on the store.
"""

from __future__ import annotations

import datetime
import re

from src import country_edition as ce
from src import mxs_store

HEADING = "## State congresses"
MAX_ITEMS = 20
# Status words that record routine handling, not a stage: an older item
# whose only news is one of these is not shown as moved.
NOT_A_STAGE = re.compile(r"^(turnad|se toma en consideraci|primera vez listada|recibid|"
                         r"pr[oó]rroga)", re.I)
COVERING = re.compile(r"covering (\d{1,2} \w+ \d{4}) to (\d{1,2} \w+ \d{4})")


def _iso(long_text):
    day, month, year = long_text.split()
    return datetime.date(int(year), ce.MONTHS.index(month) + 1, int(day)).isoformat()


def window_of(text, cc, today, days):
    """(since, until) of the edition being rendered: read off its own
    "covering A to B" line (so --since is honoured), else the framework's."""
    hit = COVERING.search(text or "")
    if hit:
        try:
            first = datetime.date.fromisoformat(_iso(hit.group(1)))
            return (first - datetime.timedelta(days=1)).isoformat(), _iso(hit.group(2))
        except (ValueError, IndexError):
            pass
    return ce.window(cc, today, days=days)


def watchlist(path=None):
    return mxs_store.watchlist(path)


def from_gazette(source_id):
    """True for an item read from the state's official gazette rather than
    the congress itself (tools/mxs_collect.py GAZETTE readers key them 'po/')."""
    return str(source_id or "").startswith(mxs_store.GAZETTE_PREFIX)


def takeaway(r):
    state = mxs_store.STATES.get(r["state"], r["state"])
    bits = ["{0} state congress{1}{2}".format(
        state, " ({0} Legislature)".format(r["legislature"]) if r["legislature"] else "",
        " (from the official gazette)" if from_gazette(r["source_id"]) else "")]
    if from_gazette(r["source_id"]):
        bits.append("Adopted and published in the state's Periódico Oficial; the congress's own "
                    "site is not read (docs/mexico-regions-scope.md)")
        if r["turno"]:
            bits.append("Committee: {0}".format(ce.clip(r["turno"], 160)))
        return ". ".join(bits)
    kind = mxs_store.KINDS.get(r["kind"] or "", None)
    who = r["presenter"]
    if kind:
        party = r["party"] if r["party"] and r["party"] not in (who or "") else None
        bits.append("{0}{1}{2}".format(kind, " from " + ce.clip(who, 120) if who else "",
                                       " ({0})".format(party) if party else ""))
    elif who:
        bits.append("Presented by {0}".format(ce.clip(who, 120)))
    if r["turno"]:
        bits.append("Committee: {0}".format(ce.clip(r["turno"], 160)))
    return ". ".join(bits)


def items(conn, since, until, wl=None, cc="mx"):
    """The window's state items on our ground, as edition items."""
    wl = watchlist() if wl is None else wl
    out = []
    for r in ce.rows(conn, "SELECT * FROM mxs_items WHERE (" + ce.window_sql("presented")
                     + ") OR (" + ce.window_sql("status_date") + ")",
                     (since, until, since, until)):
        watched = r["item_key"] in wl
        if not ce.on_ground(r["areas"], watched):
            continue
        presented = (r["presented"] or "")[:10]
        status_date = (r["status_date"] or "")[:10]
        if since < presented <= until:
            kind, date = ("law" if r["kind"] == "decreto" else "new"), presented
        elif since < status_date <= until and not NOT_A_STAGE.search(
                (r["status"] or "").strip()):
            kind, date = ("law" if r["kind"] == "decreto" else "moved"), status_date
        else:
            continue
        out.append(ce.item(cc, kind, r["item_key"], date, ce.clean(r["title"]),
                           ce.areas_of(r["areas"]), r["tier"], watched,
                           status=r["status"], url=r["url"], terms=r["matched_terms"],
                           takeaway=takeaway(r)))
    return out


def reads_line(conn):
    """Which states were read, and which not, from mxs_reads."""
    got = ce.rows(conn, "SELECT * FROM mxs_reads ORDER BY state")
    if not got:
        return "The state congresses have not been read yet (tools/mxs_collect.py)."
    ok = [r for r in got if r["status"] == "ok"]
    gap = [r for r in got if r["status"] == "gap"]
    off = [r for r in got if r["status"] not in ("ok", "gap")]
    def name(r):
        label = mxs_store.STATES.get(r["state"], r["state"])
        if (r["reader"] or "").endswith("_gazette"):
            label += " (from the official gazette)"
        return label
    bits = []
    if ok:
        when = max((r["read_at"] or "")[:10] for r in ok)
        bits.append("Read cleanly ({0} of 32, last {1}): {2}.".format(
            len(ok), ce.long_date(when) if when else "?", ", ".join(name(r) for r in ok)))
    if gap:
        bits.append("Read with gaps: {0}.".format(", ".join(
            "{0} ({1})".format(name(r), ce.clip(r["detail"] or "gap", 80)) for r in gap)))
    if off:
        bits.append("Not read ({0}): see docs/mexico-regions-scope.md.".format(
            ", ".join(name(r) for r in off)))
    return " ".join(bits)


def section(conn, country, since, until, config_dir=None):
    wl = watchlist()
    got = items(conn, since, until, wl, country.cc)
    kept, dropped = ce.noise_for(country).split(got, config_dir)
    kept = ce.score(ce.collapse_titles(kept))
    out = [HEADING, ""]
    if kept:
        states = sorted({it["key"].split("/", 1)[0] for it in kept})
        out.append("**{0} item(s) on our ground** in {1} state congress(es): {2}.".format(
            len(kept), len(states), ce.count_text(kept) or "none"))
        out.append("")
        for it in kept[:MAX_ITEMS]:
            out += ce.item_lines(it, wl)
        if len(kept) > MAX_ITEMS:
            out.append("- _And {0} more, lower in the order; in the store._".format(
                len(kept) - MAX_ITEMS))
    else:
        out.append("Nothing on our ground in the state congresses read this {0}.".format(
            country.period))
    out += ["", "_" + reads_line(conn) + (" Left out by the noise filters: {0}.".format(
        ce.dropped_text(dropped)) if dropped else "") + "_", ""]
    return out


def post_render(conn, country, today, text, wl=None):
    """The section, before the Watchlist (or at the end of a quiet edition)."""
    since, until = window_of(text, country.cc, today, country.cadence_days)
    block = "\n".join(section(conn, country, since, until))
    marker = "\n## Watchlist\n"
    if marker in text:
        return text.replace(marker, "\n" + block + marker, 1)
    return text.rstrip("\n") + "\n\n" + block


def notice(conn, today, dm=False, cc="mx", days=14):
    """The DM's second line: the fortnight's state items on our ground, if any
    (the edition itself carries the section, so it gets no notice)."""
    if not dm:
        return None
    since, until = ce.window(cc, today, days=days)
    try:
        n = len(items(conn, since, until))
    except Exception:  # noqa: BLE001 -- a DM line is never worth a failed DM
        return None
    if not n:
        return None
    return "State congresses: {0} item(s) on our ground this fortnight (see the edition).".format(n)
