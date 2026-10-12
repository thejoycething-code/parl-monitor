"""Spain: the weekly edition's adapter (src/country_edition.py).

Reads the es_* tables tools/es_rollcalls.py fills (src/es_store.py): the
Congreso de los Diputados' plenary votes with every deputy's position and
the group printed at the vote, and its legislative initiatives. The Senado
refuses us (docs/spain-scope.md), so the edition is the Congreso's.

ES6 (docs/country-decisions-2026-10-10.md): build the edition now, although
the Cortes were dissolved on 6 October 2026 (Real Decreto 806/2026; election
29 November; the XVI legislature convenes on 23 December). While the store
holds nothing newer than a dissolved legislature, every edition opens with a
short notice saying so and naming the next sitting; a week with nothing on
our ground is then the short "quiet week" form under that notice. The
notice goes by itself the day the store holds a row of the next
legislature, which the collector reads off the Congreso's own selector, so
the XVI's first items appear with no edit here.

THE NOTICE is the framework's `Country.notice` hook (`edition_notice()`
below): the framework puts it under the edition's subtitle and on the DM's
second line.

Votes on one initiative in one week (points voted separately, amendments,
the vote of the whole) render as one entry; the vote's sub-heading leads
its title so that each line of the group says which vote it was.
"""

from __future__ import annotations

import datetime
import re
import sys

from src import agenda
from src import country_edition as ce

CC = "es"
BASE = "https://www.congreso.es"
DAY_PAGE = (BASE + "/es/opendata/votaciones?p_p_id=votaciones&p_p_lifecycle=0"
            "&p_p_state=normal&p_p_mode=view&targetLegislatura={leg}&targetDate={date}")
ROMAN = {14: "XIV", 15: "XV", 16: "XVI", 17: "XVII", 18: "XVIII"}

# A dissolved legislature, from the decree in the BOE. Add a row at the next
# dissolution; nothing else changes.
DISSOLUTIONS = {
    15: {"dissolved": "2026-10-06",
         "decree": "Real Decreto 806/2026 (BOE-A-2026-20742)",
         "election": "2026-11-29",
         "convenes": "2026-12-23"},
}

# The Congreso's agenda sections, in English, by the folded start of the
# section heading ("NUEVO PUNTO." and "PUNTO UNICO." are stripped first).
SECTIONS = (
    ("toma en consideracion", "Taking into consideration: whether the Congreso takes the bill up"),
    ("proposiciones no de ley", "Non-binding motion (proposición no de ley)"),
    ("votacion de las proposiciones no de ley", "Non-binding motion (proposición no de ley)"),
    ("mociones consecuencia", "Motion following an urgent interpellation"),
    ("convalidacion o derogacion", "Validation of a royal decree-law"),
    ("debates de totalidad", "Totality debate: amendments seeking the bill's return or a whole new text"),
    ("dictamenes de comisiones sobre iniciativas", "Committee report on a bill, with amendments kept alive for the plenary"),
    ("dictamenes de la comision de asuntos exteriores", "International treaty"),
    ("enmiendas del senado", "The Senado's amendments, back in the Congreso"),
    ("veto del senado", "The Senado's veto, back in the Congreso"),
    ("acuerdos de comisiones relativos a informes", "Report of a subcommittee"),
    ("propuestas de creacion", "Proposal to create a committee or subcommittee"),
    ("solicitud", "Request about a committee's work"),
    ("tramitacion directa", "Direct passage in a single reading"),
    ("acuerdo de tramitacion directa", "Direct passage in a single reading"),
    ("avocacion", "The plenary takes the final say on a bill from its committee"),
)

INITIATIVE_TYPES = (
    ("proyecto de ley", "Government bill"),
    ("proposicion de ley de grupos", "Bill from parliamentary groups"),
    ("proposicion de ley de diputados", "Bill from deputies"),
    ("proposicion de ley del senado", "Bill from the Senado"),
    ("proposicion de ley de comunidades", "Bill from a regional parliament"),
)


def _fold(text):
    from src.noise import fold
    return fold(text)


def _lookup(table, text):
    t = re.sub(r"^\s*(nuevo punto|punto unico)\.\s*", "", _fold(text))
    return next((en for start, en in table if t.startswith(start)), None)


def sentence(text):
    """A takeaway ends with a full stop: a group's decisive vote prints it as is."""
    text = (text or "").strip()
    return text if not text or text.endswith((".", "…", "?", "!")) else text + "."


def roman(n):
    return ROMAN.get(int(n)) if n else None


# --- the state of the legislature -------------------------------------------------

def latest_legislature(conn):
    best = None
    for table in ("es_divisions", "es_initiatives", "es_members"):
        got = ce.rows(conn, "SELECT MAX(legislature) FROM {0}".format(table))
        v = got[0][0] if got else None
        if v and (best is None or v > best):
            best = int(v)
    return best


def state(conn, today):
    """{'legislature', 'dissolved', ...} while the store's newest legislature
    is one dissolved by `today`; None otherwise (a sitting legislature, or a
    store that already holds the next one)."""
    leg = latest_legislature(conn)
    d = DISSOLUTIONS.get(leg) if leg else None
    if not d or today < d["dissolved"]:
        return None
    return dict(d, legislature=leg, next=leg + 1)


def notice(conn, today):
    """The edition's opening lines while the Cortes are dissolved; [] otherwise."""
    s = state(conn, today)
    if not s:
        return []
    nxt = roman(s["next"]) or str(s["next"])
    old = roman(s["legislature"]) or str(s["legislature"])
    if today < s["convenes"]:
        if today < s["election"]:
            when = "The general election is on {0}, and the {1} legislature convenes on {2}.".format(
                ce.long_date(s["election"]), nxt, ce.long_date(s["convenes"]))
        else:
            when = "The general election was held on {0}; the {1} legislature convenes on {2}.".format(
                ce.long_date(s["election"]), nxt, ce.long_date(s["convenes"]))
        head = "**The Cortes Generales are dissolved; next sitting {0}.**".format(
            ce.long_date(s["convenes"]))
        rest = ("Until then only the Diputación Permanente can meet (chiefly to validate "
                "decree-laws); a vote it holds appears here when the Congreso publishes it.")
    else:
        when = ("The {0} legislature convened on {1}, but the Congreso has not yet published "
                "its open data; this edition picks it up on the first run that finds it.".format(
                    nxt, ce.long_date(s["convenes"])))
        head = "**The {0} legislature has convened; its data is not out yet.**".format(nxt)
        rest = ""
    lines = ["> {0} The Congreso and the Senado were dissolved on {1} by {2}. {3} Every "
             "initiative of the {4} still pending lapsed with the dissolution, whatever its "
             "status line says. {5}".format(head, ce.long_date(s["dissolved"]), s["decree"],
                                             when, old, rest).rstrip(), ""]
    return lines


def dm_notice(conn, today):
    s = state(conn, today)
    if not s:
        return None
    nxt = roman(s["next"]) or str(s["next"])
    if today < s["convenes"]:
        return "_Cortes dissolved on {0}; next sitting {1} ({2} legislature)._".format(
            ce.short_date(s["dissolved"]), ce.long_date(s["convenes"]), nxt)
    return "_The {0} legislature convened on {1}; its data is not out yet._".format(
        nxt, ce.long_date(s["convenes"]))


def edition_notice(conn, today, dm=False):
    """Country.notice: notice() for the edition, dm_notice() for the DM.
    The DM's adds the regional layer's one line (12 October 2026)."""
    if dm:
        lines = [x for x in (dm_notice(conn, today), regional_dm_line(conn, today)) if x]
        return "\n".join(lines) or None
    return "\n".join(notice(conn, today))


# --- items ----------------------------------------------------------------------

def _terms(*raws):
    out = []
    for raw in raws:
        for t in ce.terms_of(raw):
            if t not in out:
                out.append(t)
    return out


def vote_title(title, subgroup):
    """The sub-heading first ('Votación separada por puntos. Punto 3.'), then
    the item, both verbatim: a group's lines then say which vote each was."""
    title, subgroup = ce.clean(title), ce.clean(subgroup)
    if not subgroup:
        return title
    return "{0}{1} {2}".format(subgroup, "" if subgroup.endswith(".") else ".", title)


def is_final(subgroup, title):
    s = _fold(subgroup or "") + " " + _fold(title or "")
    return "votacion de conjunto" in s


def _positions(conn, key):
    return [(r["name"], r["grupo"], r["position"]) for r in ce.rows(
        conn, "SELECT name, grupo, position FROM es_votes WHERE division_key = ?", (key,))]


YES, NO, ABSTAIN = ("sí", "si"), ("no",), ("abstención", "abstencion")


def _brief_positions(conn, r):
    """The same-day vote brief's fields (src/country_vote_brief.py)."""
    pos = [] if r["assent"] else _positions(conn, r["division_key"])
    return {"positions": pos or None, "rebels": ce.rebels(pos, YES, NO) if pos else None}


def vote_lines(conn, r):
    if r["assent"]:
        return ["Tally: agreed by assent, with no recorded vote."]
    how = "{0} not voting".format(r["not_voting"]) if r["not_voting"] else None
    lines = [ce.tally_line(r["yes"], r["no"], r["abstain"], how=how)]
    pos = _positions(conn, r["division_key"])
    if pos:
        lines.append(ce.split_line(ce.group_counts([(g, p) for _, g, p in pos], YES, NO, ABSTAIN),
                                   label="By group at the vote"))
        lines.append(ce.members_line(len(pos), ce.rebels(pos, YES, NO)))
    elif not r["json_url"]:
        lines.append("Published as a chart only (a public roll call or an image-only vote): "
                     "no member positions in the open data.")
    elif r["positions"] == 0:
        lines.append("A secret ballot: the vote file names no one.")
    else:
        lines.append("Member positions not read yet; the next run fetches them.")
    return lines


def divisions(conn, since, until, wl):
    out = []
    for r in ce.rows(conn, "SELECT * FROM es_divisions WHERE " + ce.window_sql("date")
                     + " ORDER BY date, session, vote_number", (since, until)):
        key = r["initiative_key"] or r["division_key"]
        watched = key in wl
        if not ce.on_ground(r["areas"], watched):
            continue
        init = None
        if r["initiative_key"]:
            got = ce.rows(conn, "SELECT matched_terms FROM es_initiatives WHERE initiative_key = ?",
                          (r["initiative_key"],))
            init = got[0]["matched_terms"] if got else None
        own = bool(ce.areas_of(r["own_areas"])) if r["own_areas"] is not None else None
        section = _lookup(SECTIONS, r["section"])
        takeaway = "{0}{1}".format(section or ce.clean(r["section"]).rstrip("."),
                                   ", {0} legislature".format(roman(r["legislature"]))
                                   if roman(r["legislature"]) else "")
        out.append(ce.vote(
            CC, key, r["date"], vote_title(r["title"], r["subgroup"]),
            ce.areas_of(r["areas"]), r["tier"], watched, vote_lines(conn, r),
            terms=_terms(r["matched_terms"], init), body=ce.clean(r["section"]),
            url=DAY_PAGE.format(leg=roman(r["legislature"]) or r["legislature"],
                                date=_ddmmyyyy(r["date"])),
            takeaway=sentence(takeaway), group=("es", key), group_title=r["title"],
            final=is_final(r["subgroup"], r["title"]),
            own=False if own is False else None, division=r["division_key"],
            **_brief_positions(conn, r)))
    return out


def _ddmmyyyy(iso):
    try:
        d = datetime.date.fromisoformat(ce.day(iso))
    except ValueError:
        return ""
    return "{0:02d}/{1:02d}/{2}".format(d.day, d.month, d.year)


def initiatives(conn, since, until, wl, today=None):
    out = []
    s = state(conn, today or until)
    for r in ce.rows(conn, "SELECT * FROM es_initiatives WHERE " + ce.window_sql("presentada")
                     + " ORDER BY presentada", (since, until)):
        watched = r["initiative_key"] in wl
        if not ce.on_ground(r["areas"], watched):
            continue
        kind = _lookup(INITIATIVE_TYPES, r["tipo"]) or ce.clean(r["tipo"])
        bits = [kind]
        if r["autor"]:
            bits.append("from {0}".format(ce.clean(r["autor"])))
        takeaway = ", ".join(bits)
        if s and r["legislature"] == s["legislature"] and "caducad" not in _fold(r["situacion"]):
            takeaway += ". Lapsed with the dissolution of {0}, whatever its status says".format(
                ce.long_date(s["dissolved"]))
        out.append(ce.item(
            CC, "new", r["initiative_key"], r["presentada"], r["objeto"],
            ce.areas_of(r["areas"]), r["tier"], watched, status=r["situacion"],
            url=r["bocg"] or None, terms=r["matched_terms"], takeaway=takeaway))
    return out


def items(conn, since, until, wl):
    return divisions(conn, since, until, wl) + initiatives(conn, since, until, wl)


# --- the regional layer (tools/es_regions.py, src/es_regions_store.py) -----------
#
# 12 October 2026 (docs/spain-regions-scope.md): the seventeen communities'
# laws as the BOE publishes them (in Spanish for all seventeen), and the bills
# new in the regional parliaments whose sites list them. A section of its own,
# "Regional parliaments", added by post_render() after the Congreso's
# sections (before the Watchlist, or at the end of a quiet week's form), so
# the Congreso's counts, lead and quiet-week test are the Congreso's alone.
# The items go through the same noise filters (config/edition-noise-es.yaml,
# config/edition-mute-es.yaml) and stub ordering; the session judge and the
# review window do not read them yet. The DM gets one line saying how many.

REGIONAL_RANKS = ("ley", "decreto-ley", "decreto legislativo")
RANK_NAMES = {"ley": "Law", "decreto-ley": "Decree-law", "decreto legislativo": "Legislative decree",
              "decreto": "Decree", "correction": "Correction", "other": "Act"}
BILL_KINDS = {"proyecto de ley": "Government bill", "proposición de ley": "Members' bill",
              "decreto-ley": "Decree-law for validation", "ilp": "Popular legislative initiative"}
MAX_REGIONAL = 12


def _esr():
    from src import es_regions_store
    return es_regions_store


def regional_laws(conn, since, until, wl):
    esr = _esr()
    out = []
    for r in ce.rows(conn, "SELECT * FROM esr_laws WHERE " + ce.window_sql("published")
                     + " ORDER BY published, boe_id", (since, until)):
        watched = r["boe_id"] in wl
        if r["rank"] not in REGIONAL_RANKS and not watched:
            continue
        if not ce.on_ground(r["areas"], watched):
            continue
        region = esr.REGIONS.get(r["region"], r["region"])
        takeaway = "{0} of {1}, published in the BOE on {2}{3}".format(
            RANK_NAMES.get(r["rank"], "Act"), region, ce.long_date(r["published"]),
            "; a decree-law the regional parliament must validate or reject"
            if r["rank"] == "decreto-ley" else "")
        out.append(ce.item(CC, "law", r["boe_id"], r["published"], r["title"],
                           ce.areas_of(r["areas"]), r["tier"], watched,
                           url=r["url_html"] or r["url_pdf"], terms=r["matched_terms"],
                           body=r["heading"] or "", takeaway=takeaway))
    return out


def _bill_date(r):
    """The date a bill counts as new: its own presentation date when the
    list gives one, else the day first listed (never a seed row's)."""
    if r["presented"]:
        return r["presented"]
    return None if r["seed"] else r["first_seen"]


def regional_bills(conn, since, until, wl):
    esr = _esr()
    out = []
    # Every classified title, Spanish or Catalan/Valencian (12 October 2026:
    # the Corts Valencianes' bills are classified with taxonomy-ca); a title
    # in a language with no list has areas NULL and is counted, never shown.
    for r in ce.rows(conn, "SELECT * FROM esr_bills WHERE areas IS NOT NULL AND ("
                     + ce.window_sql("presented") + " OR (presented IS NULL AND COALESCE(seed, 0) = 0 AND "
                     + ce.window_sql("first_seen") + ")) ORDER BY region, bill_key",
                     (since, until, since, until)):
        watched = r["bill_key"] in wl
        if not ce.on_ground(r["areas"], watched):
            continue
        bits = [BILL_KINDS.get(r["kind"] or "", "Bill"), "in the {0}".format(
            esr.PARLIAMENTS.get(r["region"], r["region"]))]
        if r["proponent"]:
            bits.append("from {0}".format(ce.clean(r["proponent"])))
        out.append(ce.item(CC, "new", r["bill_key"], _bill_date(r), r["title"],
                           ce.areas_of(r["areas"]), r["tier"], watched, status=r["status"],
                           url=r["url"], terms=r["matched_terms"], takeaway=" ".join(bits)))
    return out


def regional_items(conn, since, until, wl, config_dir=None):
    """(kept, dropped): the regional items in the window after the noise filters."""
    got = regional_laws(conn, since, until, wl) + regional_bills(conn, since, until, wl)
    kept, dropped = ce.noise_for(COUNTRY).split(got, config_dir)
    return ce.score(kept), dropped


def regional_coverage(conn, since, until):
    """The section's own coverage lines: what was read, and the gaps."""
    esr = _esr()
    reads = {r["source"]: r for r in ce.rows(conn, "SELECT * FROM esr_reads")}
    if not reads:
        return ["The regional layer has not run yet (tools/es_regions.py, Spain weekly)."]
    lines = []
    boe = reads.get("boe")
    n_acts = ce.rows(conn, "SELECT COUNT(*) FROM esr_laws WHERE " + ce.window_sql("published"),
                     (since, until))
    if boe:
        lines.append("The BOE, every community's laws in Spanish: read to {0}; {1} regional act(s) "
                     "published in this period. A law reaches the BOE weeks after the regional "
                     "bulletin.".format(ce.long_date(boe["last_day"]) if boe["last_day"] else "never",
                                        n_acts[0][0] if n_acts else 0))
    listed = [k for k in ("an", "cn", "ri", "cb") if k in reads]
    if listed:
        lines.append("Bills in passage, from the parliaments' own lists: {0}.".format("; ".join(
            "{0} ({1})".format(esr.REGIONS[k], "read {0}".format(ce.short_date(reads[k]["last_seen"]))
                               if (reads[k]["status"] or "") == "ok" else "failed: "
                               + ce.clean(reads[k]["status"] or "unknown"))
            for k in listed)))
    new_sql = (" AND (" + ce.window_sql("presented") + " OR (presented IS NULL AND COALESCE(seed, 0) = 0 "
               "AND " + ce.window_sql("first_seen") + "))")
    window = (since, until, since, until)
    # Catalan/Valencian titles (12 October 2026): classified with the
    # Catalan/Valencian list, an unmeasured draft, so the line says so.
    catalan = {}
    for r in ce.rows(conn, "SELECT region, areas FROM esr_bills WHERE lang = 'ca' AND areas IS NOT NULL"
                     + new_sql + " ORDER BY region", window):
        n, ours = catalan.get(r["region"], (0, 0))
        catalan[r["region"]] = (n + 1, ours + bool(ce.on_ground(r["areas"], False)))
    if "vc" in reads or catalan:
        lines.append("Classified with the Catalan/Valencian term list (an unmeasured draft): {0} new "
                     "bill(s) in this period ({1}).".format(
                         sum(n for n, _ in catalan.values()),
                         ", ".join("{0} {1}, {2} on our ground".format(n, esr.PARLIAMENTS.get(k, k), ours)
                                   for k, (n, ours) in catalan.items())
                         or "Corts Valencianes, in Valencian"))
    other = ce.rows(conn, "SELECT region, COUNT(*) FROM esr_bills WHERE areas IS NULL" + new_sql
                    + " GROUP BY region", window)
    if other:
        lines.append("Not classified, published in a language with no term list: {0} new bill(s) in "
                     "this period ({1}).".format(
                         sum(r[1] for r in other),
                         ", ".join("{0} {1}".format(r[1], esr.PARLIAMENTS.get(r[0], r[0])) for r in other)))
    lines.append("No list of bills is read for Madrid, Navarra and Galicia (bot checks), Murcia and "
                 "Extremadura (robots.txt), País Vasco, Illes Balears and Aragón (no answer), "
                 "Cataluña (its open-data page fails) or Castilla y León, Castilla-La Mancha and Asturias (no "
                 "list to read): their laws arrive through the BOE "
                 "([scope]({0}docs/spain-regions-scope.md)).".format(ce.REPO))
    return lines


def regional_section(conn, since, until, wl, config_dir=None):
    kept, dropped = regional_items(conn, since, until, wl, config_dir)
    out = ["## Regional parliaments", ""]
    laws = [it for it in kept if it["kind"] == "law"]
    bills = [it for it in kept if it["kind"] == "new"]
    if not kept:
        out += ["Nothing on our ground from the seventeen autonomous communities in this period.", ""]
    if laws:
        out += ["### Regional laws in the BOE", ""]
        for it in laws[:MAX_REGIONAL]:
            out += ce.item_lines(it, wl)
        if len(laws) > MAX_REGIONAL:
            out.append("- _And {0} more, lower in the order; in the store._".format(len(laws) - MAX_REGIONAL))
        out.append("")
    if bills:
        out += ["### New regional bills", ""]
        for it in bills[:MAX_REGIONAL]:
            out += ce.item_lines(it, wl)
        if len(bills) > MAX_REGIONAL:
            out.append("- _And {0} more, lower in the order; in the store._".format(len(bills) - MAX_REGIONAL))
        out.append("")
    out += ["Regional coverage:", ""]
    out += ["- " + ce.clean(c) for c in regional_coverage(conn, since, until)]
    if dropped:
        out.append("- Left out by the noise filters: {0}.".format(ce.dropped_text(dropped)))
    out.append("")
    return out


def post_render(conn, country, today, text, wl):
    """Country.post_render: the regional section, before the Watchlist (or
    at the end of a quiet week's form)."""
    since, until = _window(today, text)
    section = "\n".join(regional_section(conn, since, until, wl))
    marker = "\n## Watchlist\n"
    if marker in text:
        return text.replace(marker, "\n" + section + marker, 1)
    return text.rstrip("\n") + "\n\n" + section


def _window(today, text=None, directory=None):
    """The edition's window, read back off its subtitle ('covering 3 October
    2026 to 9 October 2026') so the section matches the Congreso's exactly;
    the framework's own default when the subtitle is not there."""
    m = re.search(r"covering (\d{1,2} \w+ \d{4}) to (\d{1,2} \w+ \d{4})", text or "")
    if m:
        try:
            first = datetime.datetime.strptime(m.group(1), "%d %B %Y").date()
            last = datetime.datetime.strptime(m.group(2), "%d %B %Y").date()
            return (first - datetime.timedelta(days=1)).isoformat(), last.isoformat()
        except ValueError:
            pass
    return ce.window(CC, today, None, directory, COUNTRY.cadence_days)


def regional_dm_line(conn, today, directory=None):
    """The DM's line: the edition's window, as the framework sets it."""
    since, until = _window(today, directory=directory)
    kept, _ = regional_items(conn, since, until, ce.watchlist_of(COUNTRY, None))
    if not ce.rows(conn, "SELECT 1 FROM esr_reads LIMIT 1"):
        return None
    if not kept:
        return "_Regional parliaments: nothing on our ground this {0}._".format(COUNTRY.period)
    laws = sum(it["kind"] == "law" for it in kept)
    return "_Regional parliaments: {0} regional law(s) in the BOE and {1} new regional bill(s) on our ground; in the edition._".format(
        laws, len(kept) - laws)


COUNTRY = ce.Country(
    cc=CC, name="Spain", chamber="Congreso de los Diputados", language="Spanish",
    taxonomies=(("taxonomy-es.yaml", "es"),),
    items=items, notice=edition_notice, post_render=post_render,
    week_ahead=agenda.week_ahead_fn(CC), ahead_note=agenda.ahead_note_fn(CC),
    members_note=("Member positions are the Congreso's own, by name, with the parliamentary "
                  "group printed in each vote file, so a member against their group's majority "
                  "is named"),
    coverage=(
        "The Congreso only: www.senado.es refuses our requests (Akamai 403, ES5 pending); "
        "the Senado's amendments and vetoes show when the Congreso votes on them.",
        "Non-binding motions and motions appear when the plenary votes on them; written "
        "questions are not collected yet (phase 2), and no stage-move history is stored, so "
        "there is no stage-moves section.",
        "The week ahead is the Congreso's weekly agenda page, classified on its own words; "
        "the plenary's order of the day (a PDF) is not read.",
        "The seventeen regional parliaments have their own section above, with its own "
        "coverage lines (docs/spain-regions-scope.md).",
    ),
)


# --- the entry point --------------------------------------------------------------

def render(conn, today, since=None, sample=False, config_dir=None, directory=None):
    """The edition, notice included (for tests and callers)."""
    return ce.render(conn, COUNTRY, today, since, sample, config_dir, directory)


def dm_summary(conn, today, since=None, path=None, config_dir=None, directory=None):
    return ce.dm_summary(conn, COUNTRY, today, since, path, config_dir, directory)


def main(argv=None):
    return ce.main(CC, argv)


if __name__ == "__main__":
    sys.exit(main())
