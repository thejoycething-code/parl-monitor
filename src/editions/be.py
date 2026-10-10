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
"""

from __future__ import annotations

import json

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


COUNTRY = ce.Country(
    cc="be", name="Belgium", chamber="Chamber of Representatives", language="Dutch (with the French)",
    taxonomies=(("taxonomy-nl.yaml", "be"), ("taxonomy-fr.yaml", "be")),
    items=items, flag=":flag-be:",
    members_note=("Every plenary vote records every member by name; the group shown is the "
                  "member's group when the vote was stored, since the record prints none"),
    coverage=("Dossier pages carry no history, so there are no stage moves; new dossiers are "
              "those deposited in the week.",
              "The Senate, committee agendas and written questions are not collected yet."),
)
