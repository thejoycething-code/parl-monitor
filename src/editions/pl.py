"""Poland: the Sejm, from the pl_* tables (src/pl_store.py,
tools/pl_rollcalls.py).

Every deputy's position on every vote is stored (X15), with the club the
vote record itself names, so each vote carries its club split and the
deputies who voted against their club's majority; nothing is derived.

A sitting often votes a bill's amendments one by one and then the whole:
those votes are one group, keyed on the legislative process the vote cites,
with the vote on the whole ("głosowanie nad całością") as the decisive one.
New items are legislative processes opened in the week; stage moves are
processes whose latest stage (read from the process detail) fell in it.
The Senate is not collected (PL2: the gap is accepted).

Regional assemblies (13 October 2026): the sixteen voivodeship assemblies
(sejmiki województw) read by tools/pl_regions.py (plr_acts) get a section of
their own, "Regional assemblies", before the Watchlist (`post_render`), so
the Sejm's counts, lead and quiet-week test stay the Sejm's alone. Same rules
as the national items: on our ground by taxonomy-pl or watchlist-pl's
`regional` section by key, through the edition's noise filters. A
resolution from a sejmik's own register is shown when it was adopted in the
window (or, listed late, first seen in it); a journal position when it was
published in the window, unless the same resolution is already shown from
its register. docs/poland-regions-scope.md says what is read.
"""

from __future__ import annotations

import datetime
import json
import re

from src import agenda
from src import country_edition as ce

SEJM = "https://www.sejm.gov.pl/Sejm{0}.nsf"
FINAL = ("nad caloscia",)          # folded: "głosowanie nad całością"
POS_YES, POS_NO, POS_ABST = ("yes",), ("no",), ("abstain",)


def process_url(key):
    term, _, number = (key or "").partition("/")
    return "{0}/PrzebiegProc.xsp?nr={1}".format(SEJM.format(term), number) if number else None


def vote_url(term, sitting, number):
    return ("{0}/agent.xsp?symbol=glosowania&NrKadencji={1}&NrPosiedzenia={2}&NrGlosowania={3}"
            .format(SEJM.format(term), term, sitting, number))


def _processes(conn, since, until, wl):
    out = []
    for r in ce.rows(conn, "SELECT * FROM pl_processes WHERE ({0}) OR ({1})".format(
            ce.window_sql("start_date"), ce.window_sql("last_stage_date")),
            (since, until, since, until)):
        w = r["process_key"] in wl
        if not ce.on_ground(r["areas"], w):
            continue
        new = since < ce.day(r["start_date"]) <= until
        take = "Legislative process {0}{1}".format(
            r["process_key"], ", " + r["document_type"] if r["document_type"] else "")
        if r["passed"]:
            take += "; passed{0}".format(", published as " + r["eli"] if r["eli"] else "")
        status = r["last_stage"]
        if not new and r["last_stage_date"]:
            take += "; latest stage on {0}".format(ce.long_date(ce.day(r["last_stage_date"])))
        out.append(ce.item("pl", "new" if new else "moved", r["process_key"],
                           r["start_date"] if new else r["last_stage_date"], r["title"],
                           ce.areas_of(r["areas"]), r["tier"], w, status=status,
                           url=process_url(r["process_key"]), terms=r["matched_terms"],
                           takeaway=take))
    return out


def _votes(conn, since, until, wl):
    out = []
    for r in ce.rows(conn, "SELECT * FROM pl_divisions WHERE " + ce.window_sql("voted_at"),
                     (since, until)):
        procs = json.loads(r["process_keys"] or "[]")
        hit = next((k for k in procs if k in wl), None)
        w = hit is not None
        if not ce.on_ground(r["areas"], w):
            continue
        lines = [ce.tally_line(r["yes"], r["no"], r["abstain"], None,
                               "electronic vote" if r["kind"] == "ELECTRONIC" else r["kind"])]
        got = ce.rows(conn, "SELECT m.name, v.club, v.position FROM pl_votes v LEFT JOIN "
                            "pl_members m USING (mp_key) WHERE v.division_key=?",
                            (r["division_key"],))
        pairs = [(v["name"] or "?", v["club"], v["position"]) for v in got]
        reb = ce.rebels(pairs, POS_YES, POS_NO, skip=("niez.",)) if pairs else None
        if pairs:
            lines.append(ce.split_line(ce.group_counts([(c, p) for _, c, p in pairs],
                                                       POS_YES, POS_NO, POS_ABST), "By club"))
            lines.append(ce.members_line(len(pairs), reb,
                                         "Clubs as the vote record names them."))
        else:
            lines.append("Deputies' positions not read yet; the collector reads them next run.")
        topic = ce.clean(r["topic"]) or ce.clean(r["title"])
        group = procs[0] if procs else "{0}/{1}".format(r["sitting"], ce.clean(r["title"])[:60])
        out.append(ce.vote("pl", r["division_key"], r["voted_at"], topic,
                           ce.areas_of(r["areas"]), r["tier"], w, lines,
                           url=vote_url(r["term"], r["sitting"], r["number"]),
                           terms=r["matched_terms"],
                           takeaway="Sejm vote {0} at sitting {1}{2}".format(
                               r["number"], r["sitting"],
                               ", on process " + ", ".join(procs) if procs else ""),
                           group=group, group_title=r["title"], refs=[r["title"]],
                           final=any(f in ce.noise_mod.fold(topic) for f in FINAL),
                           own=bool(ce.areas_of(r["own_areas"])), watch_key=hit,
                           positions=pairs or None, rebels=reb))
    return out


def items(conn, since, until, wl):
    return _processes(conn, since, until, wl) + _votes(conn, since, until, wl)


# --- regional assemblies (tools/pl_regions.py, src/pl_regions_store.py) ---------

REGIONS_DOC = ce.REPO + "docs/poland-regions-scope.md"
MAX_REGIONAL = 12
LATE_DAYS = 28          # a register lists a resolution late: shown if adopted within this
# The registers tools/pl_regions.py reads (its REGISTERS), and why the rest
# are not read (docs/poland-regions-scope.md).
REGISTERS = ("mz", "sl", "ld", "pk", "ma", "lu", "sk", "wp", "pm", "ds", "wn", "lb", "kp")
NOT_READ = {"zp": "a staff application since 2021, no public list found",
            "pd": "its BIP domain no longer resolves", "op": "its BIP does not answer"}


def _plr():
    from src import pl_regions_store
    return pl_regions_store


KINDS = {"uchwała": "Resolution", "stanowisko": "Position (stanowisko)", "apel": "Appeal (apel)",
         "rezolucja": "Resolution (rezolucja)", "deklaracja": "Declaration",
         "obwieszczenie": "Notice (obwieszczenie)", "oświadczenie": "Statement (oświadczenie)",
         "projekt uchwały": "Draft resolution"}


def _reg_takeaway(r):
    plr = _plr()
    region = plr.REGIONS.get(r["region"], r["region"])
    kind = KINDS.get(r["kind"] or "uchwała", (r["kind"] or "Act").capitalize())
    if r["source"] == "journal":
        bits = ["{0} of the Sejmik Województwa {1}".format(kind, plr.SEJMIK.get(
            r["region"], region).split("Województwa ", 1)[-1])
                if "nadzorcze" not in (r["kind"] or "") else
                "The voivode's supervisory ruling on an act of the Sejmik Województwa {0}".format(
                    plr.SEJMIK.get(r["region"], region).split("Województwa ", 1)[-1])]
        if r["published"]:
            bits.append("published in the {0} on {1}".format(
                r["journal_ref"] or "voivodeship journal", ce.long_date(ce.day(r["published"]))))
    elif r["kind"] == "projekt uchwały":
        # Kujawsko-Pomorskie publishes agendas, not a list of what was adopted.
        bits = ["{0} ({1}) on the agenda of the Sejmik Województwa {2}".format(
            kind, r["number"], plr.SEJMIK.get(r["region"], region).split("Województwa ", 1)[-1])]
        if r["adopted"]:
            bits.append("for its sitting of {0}; the outcome is not published as a list".format(
                ce.long_date(ce.day(r["adopted"]))))
        return "; ".join(bits)
    else:
        bits = ["{0}{1} of the Sejmik Województwa {2}".format(
            kind, " " + r["number"] if r["number"] else "",
            plr.SEJMIK.get(r["region"], region).split("Województwa ", 1)[-1])]
        if r["adopted"]:
            bits.append("adopted on {0}".format(ce.long_date(ce.day(r["adopted"]))))
        if r["session"]:
            bits.append("at its {0}".format(r["session"]))
    return "; ".join(bits)


def regional_items(conn, since, until, wl):
    """The sejmiki's acts on our ground in the window (see the docstring)."""
    late = (datetime.date.fromisoformat(since) - datetime.timedelta(days=LATE_DAYS)).isoformat()
    out, shown = [], set()
    for r in ce.rows(conn, "SELECT * FROM plr_acts WHERE source = 'bip' AND areas IS NOT NULL AND (("
                     + ce.window_sql("adopted") + ") OR (COALESCE(seed, 0) = 0 AND "
                     + ce.window_sql("first_seen") + " AND substr(adopted,1,10) > ?)) "
                     "ORDER BY region, adopted, act_key", (since, until, since, until, late)):
        w = r["act_key"] in wl
        if not ce.on_ground(r["areas"], w):
            continue
        shown.add((r["region"], r["number"]))
        it = ce.item("pl", "new", r["act_key"], r["adopted"], r["title"], ce.areas_of(r["areas"]),
                     r["tier"], w, url=r["url"], terms=r["matched_terms"], takeaway=_reg_takeaway(r))
        it["region"], it["layer"] = r["region"], "agenda" if r["kind"] == "projekt uchwały" else "bip"
        out.append(it)
    for r in ce.rows(conn, "SELECT * FROM plr_acts WHERE source = 'journal' AND areas IS NOT NULL AND "
                     + ce.window_sql("published") + " ORDER BY region, published, act_key", (since, until)):
        w = r["act_key"] in wl
        if not ce.on_ground(r["areas"], w) or (r["region"], r["number"]) in shown:
            continue
        it = ce.item("pl", "law", r["act_key"], r["published"], r["title"], ce.areas_of(r["areas"]),
                     r["tier"], w, url=r["url"], terms=r["matched_terms"], takeaway=_reg_takeaway(r))
        it["region"], it["layer"] = r["region"], "journal"
        out.append(it)
    return out


def regional_coverage(conn):
    plr = _plr()
    reads = {r["source"]: r for r in ce.rows(conn, "SELECT * FROM plr_reads")}
    if not reads:
        return ["The regional layer has not run yet (tools/pl_regions.py, Poland weekly)."]
    def state(src):
        r = reads.get(src)
        if r is None:
            return None
        return ("read {0}".format(ce.short_date(r["last_seen"])) if (r["status"] or "") == "ok"
                else "failed: " + ce.clean(r["status"] or "unknown"))
    journals = [(k, state("journal:" + k)) for k in plr.REGIONS if state("journal:" + k)]
    failed = [plr.REGIONS[k] for k, st in journals if not st.startswith("read")]
    lines = ["The voivodeship journals (each sejmik's published acts and the voivode's rulings on them): "
             "{0} of 16 read{1}. Non-binding resolutions (stanowiska, apele, declarations) are never "
             "published there.".format(len(journals) - len(failed),
                                       "; failed: " + ", ".join(failed) if failed else "")]
    regs = [(k, state("bip:" + k)) for k in REGISTERS if state("bip:" + k)]
    if regs:
        lines.append("The sejmiki's own registers of resolutions, every resolution binding or not: {0}.".format(
            "; ".join("{0} ({1})".format(plr.REGIONS[k], st) for k, st in regs)))
    lines.append("Not read: the registers of {0}, and every councillor's recorded vote (published as "
                 "PDFs or on eSesja, which answers us with a bot check) ([scope]({1})).".format(
                     "; ".join("{0} ({1})".format(plr.REGIONS[k], why) for k, why in NOT_READ.items()),
                     REGIONS_DOC))
    return lines


def regional_section(conn, country, since, until, wl):
    got = regional_items(conn, since, until, wl)
    kept, dropped = ce.noise_for(country).split(got)
    kept = ce.score(kept)
    out = ["## Regional assemblies", ""]
    if not kept:
        first = (datetime.date.fromisoformat(since) + datetime.timedelta(days=1)).isoformat()
        out += ["Nothing on our ground from the sixteen voivodeship assemblies between {0} and {1}.".format(
            ce.long_date(first), ce.long_date(until)), ""]
    for layer, head in (("bip", "### Adopted by the sejmiki"), ("agenda", "### On a sejmik's agenda"),
                        ("journal", "### In the voivodeship journals")):
        these = [it for it in kept if it.get("layer") == layer]
        if not these:
            continue
        out += [head, ""]
        for it in these[:MAX_REGIONAL]:
            out += ce.item_lines(it, wl)
        if len(these) > MAX_REGIONAL:
            out.append("- _And {0} more, lower in the order; in the store._".format(len(these) - MAX_REGIONAL))
        out.append("")
    out += ["Regional coverage:", ""]
    out += ["- " + ce.clean(c) for c in regional_coverage(conn)]
    if dropped:
        out.append("- Left out by the noise filters: {0}.".format(ce.dropped_text(dropped)))
    out.append("")
    return out


_LONG = re.compile(r"covering (\d{1,2} [A-Z][a-z]+ \d{4}) to (\d{1,2} [A-Z][a-z]+ \d{4})")


def _iso_long(text):
    d, m, y = text.split()
    return datetime.date(int(y), ce.MONTHS.index(m) + 1, int(d)).isoformat()


def _rendered_window(text, today):
    """(since, until) as the rendered edition states them, so --since and the
    edition directory are honoured; the framework's default otherwise."""
    m = _LONG.search(text or "")
    if not m:
        return ce.window("pl", today)
    first = datetime.date.fromisoformat(_iso_long(m.group(1)))
    return (first - datetime.timedelta(days=1)).isoformat(), _iso_long(m.group(2))


def post_render(conn, country, today, text, wl):
    """The regional section, before the Watchlist (or at the end of a quiet
    week). Nothing is added when the store has never read a sejmik."""
    try:
        if not conn.execute("SELECT 1 FROM plr_reads LIMIT 1").fetchone():
            return text
    except Exception:   # a store from before the regional layer
        return text
    since, until = _rendered_window(text, today)
    section = "\n".join(regional_section(conn, country, since, until, wl))
    marker = "\n## Watchlist\n"
    if marker in text:
        return text.replace(marker, "\n" + section + marker, 1)
    return text.rstrip("\n") + "\n\n" + section


COUNTRY = ce.Country(
    cc="pl", name="Poland", chamber="Sejm", language="Polish",
    taxonomies=(("taxonomy-pl.yaml", "pl"),),
    items=items, flag=":flag-pl:", post_render=post_render,
    week_ahead=agenda.week_ahead_fn("pl"), ahead_note=agenda.ahead_note_fn("pl"),
    members_note="Every deputy's position on every vote is stored, with the club at the vote",
    coverage=("The Senate is not collected (PL2: the gap is accepted).",
              "The week ahead is the Sejm's agenda for its next sittings: a point is dated "
              "to its sitting's first day, and points the Marshal may add are marked.",
              "The sixteen voivodeship assemblies (sejmiki) have their own section above, with its "
              "own coverage lines (docs/poland-regions-scope.md)."),
)
