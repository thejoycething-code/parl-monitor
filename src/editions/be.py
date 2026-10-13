"""Belgium: the federal Chamber, from the be_* tables (src/be_store.py,
tools/be_rollcalls.py).

The full edition (BE6, a votes-only DM first, is superseded: the term lists
are approved, BE1). Recorded votes lead: every plenary vote names every
member, so each carries the party split and the members who voted against
their group's majority. The group is the member's group WHEN STORED, not at
the vote (the plenary record prints no party), and the edition says so.
Votes on one dossier (amendments, articles, the whole) are one group, the
vote on the whole being the decisive one.

New dossiers are those deposited in the week (or first seen in it, once
the store is older than the week); the Chamber's dossier pages carry no
history, so there are no stage moves. Titles are the Chamber's Dutch, with
its French beside it.

COMMUNITIES AND REGIONS (13 October 2026): the documents of the Flemish,
Walloon, French Community (FWB), Brussels and COCOM parliaments on our ground
or watched (src/be_regions_store.py, tools/be_regions.py; watchlist-be.yaml,
`regions`), and the Flemish Parliament's recorded votes on them with every
member's position, in their own section after the Watchlist
(Country.extra_sections), never mixed into the Chamber's. Education, youth,
family allowances and health prevention are community matters, so EVRAS,
gender in schools and family policy land here. A document is new in the
week it was deposited; an older one whose status the source dates in the
week (or a run first saw change) is a stage move. The German-speaking
Community's parliament, COCOF and the VGC are not read; the Coverage section
says why every week.
"""

from __future__ import annotations

import json

from src import agenda
from src import be_regions_store as ber
from src import country_edition as ce

HOST = "https://www.lachambre.be"
DOSSIER = (HOST + "/kvvcr/showpage.cfm?section=/flwb&language=fr&cfm=/site/wwwcfm/flwb/flwbn.cfm"
           "?lang=F&legislat={0}&dossierID={1}")
FINAL = ("geheel", "ensemble")
POS = {"yes": "for", "no": "against", "abstain": "abstaining"}


def dossier_url(key):
    leg, _, num = (key or "").partition("/")
    return DOSSIER.format(leg, num.zfill(4)) if num else None


def _store_age(conn):
    got = ce.rows(conn, "SELECT MIN(substr(first_seen,1,10)) FROM be_dossiers")
    return got[0][0] if got else None


def _dossiers(conn, since, until, wl):
    out = []
    oldest = _store_age(conn)
    seen_new = oldest is not None and oldest <= since
    for r in ce.rows(conn, "SELECT * FROM be_dossiers WHERE ({0}) OR (deposited IS NULL AND {1})"
                     .format(ce.window_sql("deposited"), ce.window_sql("first_seen")),
                     (since, until, since, until)):
        if not r["deposited"] and not seen_new:
            continue                    # the store's first run: everything is first seen
        w = r["dossier_key"] in wl
        if not ce.on_ground(r["areas"], w):
            continue
        take = ce.clean(r["doc_type"]).lower() if r["doc_type"] else "Dossier"
        take = "Dossier {0}{1}".format(r["dossier_key"], ", " + take.split(" ", 1)[-1]
                                       if r["doc_type"] else "")
        lines = ["FR: *{0}*".format(ce.clip(r["title_fr"], 300))] if r["title_fr"] else []
        out.append(ce.item("be", "new", r["dossier_key"], r["deposited"] or r["first_seen"],
                           r["title_nl"] or r["title_fr"], ce.areas_of(r["areas"]), None, w,
                           status=r["status"], url=dossier_url(r["dossier_key"]),
                           lines=lines, terms=r["matched_terms"], takeaway=take))
    return out


def _votes(conn, since, until, wl):
    out = []
    for r in ce.rows(conn, "SELECT d.*, s.url AS sitting_url, b.title_nl AS d_title_nl "
                           "FROM be_divisions d LEFT JOIN be_sittings s "
                           "ON s.legislature = d.legislature AND s.number = d.sitting "
                           "LEFT JOIN be_dossiers b ON b.dossier_key = d.dossier_key WHERE "
                           + ce.window_sql("d.date"), (since, until)):
        w = (r["dossier_key"] or "") in wl
        if not ce.on_ground(r["areas"], w):
            continue
        subjects = json.loads(r["subjects"] or "[]")
        subject_nl = "; ".join(s[0] for s in subjects if s and s[0])
        subject_fr = "; ".join(s[1] for s in subjects if len(s) > 1 and s[1])
        title = " ".join(x for x in (r["heading_nl"], subject_nl) if x)
        title_fr = " ".join(x for x in (r["heading_fr"], subject_fr) if x)
        got = ce.rows(conn, "SELECT member_name, group_seen, position FROM be_votes "
                            "WHERE division_key=?", (r["division_key"],))
        pairs = [(v["member_name"], v["group_seen"], v["position"]) for v in got]
        lines = [ce.tally_line(r["yes"], r["no"], r["abstain"], r["result_fr"],
                               "nominal vote" if r["kind"] == "nominal" else "counted"),
                 "FR: *{0}*".format(ce.clip(title_fr, 300)) if title_fr else None]
        reb = ce.rebels(pairs) if pairs else None
        if pairs:
            lines.append(ce.split_line(ce.group_counts([(g, p) for _, g, p in pairs]),
                                       "By group"))
            lines.append(ce.members_line(
                len(pairs), reb,
                "Groups are as the member list stood when stored, not at the vote."))
        heading = (r["heading_nl"] or "").lower() + " " + (r["heading_fr"] or "").lower()
        final = any(heading.strip().startswith(f) or (" " + f + " ") in heading[:40]
                    for f in FINAL)
        out.append(ce.vote("be", r["division_key"], r["date"], title, ce.areas_of(r["areas"]),
                           None, w, lines, url=r["sitting_url"], terms=r["matched_terms"],
                           takeaway="Plenary vote {0}{1}{2}".format(
                               r["division_key"],
                               ", on dossier " + r["dossier_key"] if r["dossier_key"] else "",
                               ", outcome " + r["outcome"] if r["outcome"] else ""),
                           group=r["dossier_key"], group_title=r["d_title_nl"],
                           final=final, watch_key=r["dossier_key"],
                           positions=pairs or None, rebels=reb))
    return out


def items(conn, since, until, wl):
    return _dossiers(conn, since, until, wl) + _votes(conn, since, until, wl)


# Our kinds (tools/be_regions.bill_kind) -> the framework's for a new document.
REGION_KIND = {"bill": "new", "resolution": "new", "motion": "new", "concept": "new",
               "petition": "petition", "question": "question"}
REGION_WORDS = {"bill": "bill", "resolution": "resolution", "motion": "motion",
                "concept": "concept note", "petition": "petition", "question": "question",
                "other": "document"}
HIDDEN = {11}


def _region_ground(areas_raw, watched):
    return watched or bool(set(ce.areas_of(areas_raw)) - HIDDEN)


def region_doc_items(conn, since, until, wl):
    out = []
    got = ce.rows(conn, "SELECT * FROM ber_docs WHERE ({0}) OR ({1})".format(
        ce.window_sql("date"), ce.window_sql("status_date")), (since, until, since, until))
    for r in got:
        w = r["doc_key"] in wl
        if not _region_ground(r["areas"], w):
            continue
        fresh = bool(r["date"]) and since < r["date"] <= until
        if fresh:
            kind = REGION_KIND.get(r["kind"]) or ("new" if w else None)
        else:
            kind = "moved" if r["kind"] not in ("question",) else None
        if not kind:
            continue
        date = r["date"] if fresh else r["status_date"]
        house = ber.HOUSE.get(r["parliament"], r["parliament"])
        what = r["doc_type"] or REGION_WORDS.get(r["kind"], "document")
        take = "{0}: {1}".format(house, what[0].lower() + what[1:] if what else "document")
        if r["number"]:
            take += " {0}{1}".format(r["number"], " ({0})".format(r["session"])
                                     if r["session"] else "")
        if r["date"]:
            take += "; deposited {0}".format(ce.long_date(ce.day(r["date"])))
        if not fresh and r["status_date"]:
            # the status itself is printed by the framework from `status`
            take += "; status {0} {1}".format(
                "first seen by us" if r["status_seen"] else "dated",
                ce.long_date(ce.day(r["status_date"])))
        if r["authors"]:
            take += "; by {0}".format(ce.clip(r["authors"], 160))
        lines = []
        if r["title_alt"]:
            lines.append("NL: *{0}*".format(ce.clip(r["title_alt"], 300)))
        out.append(ce.item("be", kind, r["doc_key"], date, r["title"], ce.areas_of(r["areas"]),
                           r["tier"], w, status=r["status"], url=r["url"], lines=lines,
                           terms=r["matched_terms"], takeaway=take))
    return out


def region_vote_items(conn, since, until, wl):
    out = []
    for r in ce.rows(conn, "SELECT v.*, d.title AS d_title FROM ber_votes v LEFT JOIN ber_docs d "
                           "ON d.doc_key = v.doc_key WHERE " + ce.window_sql("v.date"),
                     (since, until)):
        w = (r["doc_key"] or "") in wl
        if not _region_ground(r["areas"], w):
            continue
        got = ce.rows(conn, "SELECT member_name, group_name, position FROM ber_positions "
                            "WHERE vote_key=?", (r["vote_key"],))
        pairs = [(v["member_name"], v["group_name"], v["position"]) for v in got]
        result = None if r["adopted"] is None else ("aangenomen" if r["adopted"] else "verworpen")
        lines = [ce.tally_line(r["yes"], r["no"], r["abstain"], result, "nominal vote")]
        reb = ce.rebels(pairs) if pairs else None
        if pairs:
            lines.append(ce.split_line(ce.group_counts([(g, p) for _, g, p in pairs]),
                                       "By group"))
            lines.append(ce.members_line(len(pairs), reb,
                                         "Groups are as the vote record prints them."))
        house = ber.HOUSE.get(r["parliament"], r["parliament"])
        out.append(ce.vote("be", r["vote_key"], r["date"], r["title"] or r["d_title"],
                           ce.areas_of(r["areas"]), None, w, lines, url=r["url"],
                           terms=r["matched_terms"],
                           takeaway="{0}: plenary vote on {1}{2}".format(
                               house, r["doc_key"],
                               " ({0} matter)".format(r["matter"].lower()) if r["matter"] else ""),
                           group=r["doc_key"], group_title=r["d_title"], final=True,
                           watch_key=r["doc_key"], positions=pairs or None, rebels=reb))
    return out


def region_coverage(conn):
    seen = ber.reads(conn)
    read, never = [], []
    for code in ber.READ:
        r = seen.get(code)
        if r and r[1]:
            read.append("{0} {1}{2}".format(ber.NAMES[code], ce.short_date(r[1]),
                                            "" if r[2] == r[1] else " (with a gap)"))
        else:
            never.append(ber.NAMES[code])
    lines = ["Communities and regions read (last read): {0}.".format(", ".join(read) or "none yet")]
    if never:
        lines.append("Communities and regions not read yet: {0}.".format(", ".join(never)))
    lines += ["{0}: partial; {1}.".format(ber.HOUSE[c], why) for c, why in sorted(ber.PARTIAL.items())]
    lines += ["{0} not read: {1}.".format(ber.HOUSE[c], why) for c, why in sorted(ber.BLOCKED.items())]
    lines.append("Of the community and regional parliaments only the Flemish Parliament "
                 "publishes its recorded votes as data; the others print them in PDF reports, "
                 "not read. Titles are classified with taxonomy-nl (Dutch) and taxonomy-fr "
                 "(French) for Belgium.")
    return lines


def regions(conn, since, until, wl):
    intro = ["The community and regional parliaments' own documents on our ground: education, "
             "youth, family allowances, health prevention and culture are community matters, "
             "so school sex education (EVRAS), gender in schools and family policy are decided "
             "here. Titles verbatim (Brussels: French, with the Dutch beside it); Flemish "
             "recorded votes with every member's position."]
    got = region_doc_items(conn, since, until, wl) + region_vote_items(conn, since, until, wl)
    return [("Communities and regions", intro, got, region_coverage(conn))]


COUNTRY = ce.Country(
    cc="be", name="Belgium", chamber="Chamber of Representatives", language="Dutch (with the French)",
    taxonomies=(("taxonomy-nl.yaml", "be"), ("taxonomy-fr.yaml", "be")),
    items=items, flag=":flag-be:",
    week_ahead=agenda.week_ahead_fn("be"), ahead_note=agenda.ahead_note_fn("be"),
    members_note=("Every plenary vote records every member by name; the group shown is the "
                  "member's group when the vote was stored, since the record prints none"),
    coverage=("Dossier pages carry no history, so there are no stage moves; new dossiers are "
              "those deposited in the week.",
              "The week ahead is the Chamber's plenary and committee agendas (eMeeting), "
              "published about a week ahead.",
              "The Senate and written questions are not collected yet."),
    extra_sections=regions,
)
