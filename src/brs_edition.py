"""The "State assemblies" section of the Brazilian edition (13 October 2026).

Much of Brazil's fight on our ground is state law: school policy (Escola sem
Partido, bans on "linguagem neutra", gender in curricula), sex-education
rules, conversion-practice and "ideologia de gênero" bills, and the state
health systems' protocols. tools/br_states.py stores what the readable
Assembleias publish in brs_bills and brs_votes (docs/brazil-regions-scope.md);
this module turns the week's items on our ground into one section of the
Brazilian edition (src/editions/br.py), placed before its Watchlist through
the framework's Country.post_render hook, so the shared edition framework
is not touched.

WHAT IT SHOWS, per assembly, items on our ground (taxonomy-pt areas, or
watched in config/watchlist-br-states.yaml by key):
  * new: a bill presented in the window (or, where the source prints no
    date, first listed in the window and not part of a source's first read);
  * moved: an older bill whose status changed in the window, with the
    source's own status words;
  * a recorded vote in the window on a bill on our ground: ALESP's committee
    votes with each member's vote, the SAPL houses' plenary tallies.
The same noise rules as the federal items (config/edition-noise-br.yaml)
apply. A line under the section says which assemblies were read, when, and
which were not and why, so a quiet section is never read as "nothing
happened in 27 assemblies".

Read-only on the store.
"""

from __future__ import annotations

import datetime
import re

from src import brs_store
from src import country_edition as ce

HEADING = "## State assemblies"
MAX_ITEMS = 20
COVERING = re.compile(r"covering (\d{1,2} \w+ \d{4}) to (\d{1,2} \w+ \d{4})")
YES = ("yes",)
# Status words that record routine handling, not a stage: an older bill
# whose only news is one of these is not shown as moved.
NOT_A_STAGE = re.compile(r"coautoria|arquivado pelo setor de arquivo|^publicad[oa] o despacho", re.I)
# A gap line names its assembly first ('ALPB (Paraíba): ...'); the coverage
# line names it already.
_PREFIX = re.compile(r"^[A-Z][A-Z-]+[^:]{0,30}:\s*")
# The assemblies listed by tools/br_states.NOT_READ, kept here too so the
# edition never imports a tool. Short reasons; the scope doc has the detail.
NOT_READ = {
    "pr": "bill search and votes behind reCAPTCHA",
    "rs": "no answer from outside Brazil",
    "sc": "no answer from outside Brazil",
    "ba": "certificate fails / no answer",
    "pe": "open data has no bills",
    "df": "no answer from outside Brazil",
    "es": "no answer from outside Brazil",
    "mt": "its SAPL holds nothing recent",
    "ms": "no answer; bill search is a JavaScript app",
    "rn": "no answer from outside Brazil",
    "ap": "no answer from outside Brazil",
    "go": "no list of bills found",
    "ce": "no list of bills found",
    "pa": "bill search is a callback form",
    "se": "no list of bills found",
}


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


def _where(r):
    return brs_store.assembly(r["uf"])


def bill_takeaway(r):
    bits = ["{0} in the {1}".format(r["kind_name"] or r["kind"] or "Bill", _where(r))]
    if r["authors"]:
        bits.append("from {0}".format(ce.clip(r["authors"], 160)))
    if r["committees"]:
        bits.append("({0})".format(ce.clip(r["committees"], 160)))
    return " ".join(bits)


def _new_date(r):
    """The date a bill counts as new: its own presentation date when the
    source gives one, else the day first listed (never a seed row's)."""
    if r["presented"]:
        return r["presented"][:10]
    return None if r["seed"] else r["first_seen"]


def positions(conn, vote_key):
    return [(r["member"], r["party"], r["position"]) for r in ce.rows(
        conn, "SELECT member, party, position FROM brs_positions WHERE vote_key=? ORDER BY member",
        (vote_key,))]


def _kind(position):
    t = (position or "").lower()
    if t.startswith("favor"):
        return "yes"
    if t.startswith("contr"):
        return "no"
    if t.startswith("absten"):
        return "abstain"
    return None


def vote_lines(conn, v):
    lines = [ce.tally_line(v["yes"], v["no"], v["abstain"], v["result"])]
    pos = positions(conn, v["vote_key"])
    if pos:
        pairs = [(p or "unknown", _kind(x)) for _m, p, x in pos if _kind(x)]
        lines.append(ce.split_line(ce.group_counts(pairs, ("yes",), ("no",), ("abstain",))))
        named = [m for m, _p, x in pos if _kind(x) == "no"]
        line = "{0} member votes recorded.".format(len(pos))
        if named:
            line += " Against: {0}.".format(", ".join(named[:12]))
        lines.append(line)
    return [ln for ln in lines if ln]


def items(conn, since, until, wl=None, cc="br"):
    """The window's state items on our ground, as edition items."""
    wl = brs_store.watchlist() if wl is None else wl
    out = []
    bills = {}
    for r in ce.rows(conn, "SELECT * FROM brs_bills WHERE areas IS NOT NULL AND (("
                     + ce.window_sql("presented") + ") OR (presented IS NULL AND COALESCE(seed, 0) = 0 AND "
                     + ce.window_sql("first_seen") + ") OR (" + ce.window_sql("status_date") + "))",
                     (since, until, since, until, since, until)):
        bills[r["bill_key"]] = r
        watched = r["bill_key"] in wl
        if not ce.on_ground(r["areas"], watched):
            continue
        new = _new_date(r)
        if new and since < new <= until:
            kind, date = "new", new
        elif (r["status_date"] and since < r["status_date"][:10] <= until and r["status"]
              and not NOT_A_STAGE.search(r["status"])):
            kind, date = "moved", r["status_date"][:10]
        else:
            continue
        out.append(ce.item(cc, kind, r["bill_key"], date, ce.clean(r["title"]),
                           ce.areas_of(r["areas"]), r["tier"], watched, status=r["status"],
                           url=r["url"], terms=r["matched_terms"], takeaway=bill_takeaway(r)))
    for v in ce.rows(conn, "SELECT v.*, b.title, b.areas, b.tier, b.matched_terms, b.url, "
                           "b.kind_name, b.kind, b.status FROM brs_votes v JOIN brs_bills b USING (bill_key) "
                           "WHERE " + ce.window_sql("v.date"), (since, until)):
        watched = v["bill_key"] in wl
        if not ce.on_ground(v["areas"], watched):
            continue
        where = "{0}, {1}".format(brs_store.assembly(v["uf"]),
                                  "plenary" if v["body"] == "plenary" else "committee: " + (v["body"] or "?"))
        out.append(ce.vote(cc, v["vote_key"], v["date"], ce.clean(v["title"]), ce.areas_of(v["areas"]),
                           v["tier"], watched, vote_lines(conn, v), url=v["url"],
                           terms=v["matched_terms"], watch_key=v["bill_key"],
                           takeaway="{0}: {1}, on {2}".format(
                               where, ce.clip(v["description"] or "recorded vote", 160), v["bill_key"]),
                           group=("bill", v["uf"], v["bill_key"]),
                           group_title="{0}: {1}".format(v["bill_key"], ce.clean(v["title"]))))
    return out


def reads_line(conn):
    """Which assemblies were read, and which not, from brs_reads."""
    got = ce.rows(conn, "SELECT * FROM brs_reads ORDER BY uf")
    if not got:
        return "The state assemblies have not been read yet (tools/br_states.py)."
    ok = [r for r in got if r["status"] == "ok"]
    gap = [r for r in got if r["status"] == "gap"]
    off = [r for r in got if r["status"] not in ("ok", "gap")]
    bits = []
    if ok:
        when = max((r["read_at"] or "")[:10] for r in ok)
        bits.append("Read cleanly ({0} of 27, last {1}): {2}.".format(
            len(ok), ce.long_date(when) if when else "?",
            ", ".join(brs_store.ASSEMBLIES.get(r["uf"], r["uf"]) for r in ok)))
    if gap:
        bits.append("Read with gaps: {0}.".format(", ".join(
            "{0} ({1})".format(brs_store.ASSEMBLIES.get(r["uf"], r["uf"]),
                               ce.clip(_PREFIX.sub("", r["detail"] or "gap"), 80))
            for r in gap)))
    if off:
        bits.append("Tried, not read this run: {0}.".format(", ".join(
            "{0} ({1})".format(brs_store.ASSEMBLIES.get(r["uf"], r["uf"]),
                               ce.clip(_PREFIX.sub("", r["detail"] or r["status"]), 60))
            for r in off)))
    seen = {r["uf"] for r in got}
    rest = [uf for uf in NOT_READ if uf not in seen]
    if rest:
        bits.append("Not read: {0} ([scope]({1}docs/brazil-regions-scope.md)).".format(
            "; ".join("{0} ({1})".format(brs_store.ASSEMBLIES[uf], NOT_READ[uf]) for uf in rest),
            ce.REPO))
    return " ".join(bits)


def section(conn, country, since, until, config_dir=None):
    wl = brs_store.watchlist()
    got = items(conn, since, until, wl, country.cc)
    kept, dropped = ce.noise_for(country).split(got, config_dir)
    kept = ce.score(ce.collapse_titles(kept))
    out = [HEADING, ""]
    if kept:
        states = sorted({it["key"].split("/", 1)[0] for it in kept})
        out.append("**{0} item(s) on our ground** in {1} assembly(ies): {2}.".format(
            len(kept), len(states), ce.count_text(kept) or "none"))
        out.append("")
        for it in kept[:MAX_ITEMS]:
            out += ce.item_lines(it, wl)
        if len(kept) > MAX_ITEMS:
            out.append("- _And {0} more, lower in the order; in the store._".format(
                len(kept) - MAX_ITEMS))
    else:
        out.append("Nothing on our ground in the state assemblies read this {0}.".format(
            country.period))
    out += ["", "_" + ce.clean(reads_line(conn)) + (" Left out by the noise filters: {0}.".format(
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


def notice(conn, today, dm=False, cc="br", days=7):
    """The DM's line: the week's state items on our ground, if any (the
    edition itself carries the section, so it gets no notice)."""
    if not dm:
        return None
    since, until = ce.window(cc, today, days=days)
    try:
        n = len(items(conn, since, until))
    except Exception:  # noqa: BLE001 -- a DM line is never worth a failed DM
        return None
    if not n:
        return None
    return "State assemblies: {0} item(s) on our ground this week (see the edition).".format(n)
