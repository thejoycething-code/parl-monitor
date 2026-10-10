"""Croatia: the weekly edition's adapter (src/country_edition.py).

Reads the hr_* tables tools/hr_rollcalls.py fills (src/hr_store.py): the
Sabor's agenda appearances, the recorded vote on each item with every
member's position, and the member list.

TWO RULES SHAPE IT (docs/croatia-scope.md):

  * "ZA" IS NOT ALWAYS "FOR THE BILL". An opposition bill at first reading is
    usually disposed of by a vote on a conclusion NOT to accept it, and the
    majority votes Za to kill it. The collector reads the item page's result
    sentence for every vote on our ground and sets `yes_means_reject`; the
    edition states the question that was put on every such vote, and says
    so when it has not been read.
  * PARTY AT THE VOTE IS NOT KNOWN (X6). The vote service prints no party;
    `hr_votes.party_seen` is the party in the member list the week the vote
    was collected. The split is shown as that, labelled, and no member is
    named against their party until party history is sourced.

The Sabor carries an unheard bill to the next session's agenda under a new
id, so appearances fold by bill key, never by id or title. The current
session's pending items on our ground are the week-ahead section: the
Sabor's agenda is per session, not per week, so each says how long it has
waited.
"""

from __future__ import annotations

import re

from src import country_edition as ce

CC = "hr"
VOTE_URL = "https://www.sabor.hr/hr/rezultati-glasovanja-servis/{tid}/"
STATUS = {6: "not yet debated", 7: "in debate", 8: "voted", 9: "debate closed, vote pending",
          10: "withdrawn"}
PENDING = (6, 7, 9)
FOR, AGAINST, ABSTAINED = ("for",), ("against",), ("abstained",)
X6 = "party as listed when the vote was collected, not party history, X6"


def _fold(text):
    from src.noise import fold
    return fold(text)


def sentence(text):
    """A takeaway ends with a full stop: a group's decisive vote prints it as is."""
    text = (text or "").strip()
    return text if not text or text.endswith((".", "…", "?", "!")) else text + "."


def watchlist(config_dir=None):
    """{key: {'areas', 'why'}}, keyed as src/hr_store.py keys them: a bill
    '11/41', or an agenda appearance 'item:214612'."""
    import os
    from src import hr_store
    path = os.path.join(config_dir or ce.CONFIG, "watchlist-hr.yaml")
    if not os.path.exists(path):
        return {}
    return {k: {"areas": a, "why": w} for k, (a, w) in hr_store.watchlist(path).items()}


def key_of(tid, bill_key):
    return bill_key or "item:{0}".format(tid)


def watched_key(wl, tid, bill_key):
    return any(k in wl for k in ([bill_key] if bill_key else []) + ["item:{0}".format(tid)])


def reading(title):
    t = _fold(title)
    if t.startswith("konacni prijedlog"):
        return "Final reading"
    if "prvo citanje" in t:
        return "First reading"
    if "drugo citanje" in t:
        return "Second reading"
    return None


def conclusion_carried(outcome):
    """True when the result sentence says the conclusion not to accept was
    adopted ("donesen je zakljucak da se ne prihvaca"), False when it says
    it was not, None when the sentence says neither."""
    o = _fold(outcome)
    if re.search(r"nije donesen\w* zakljucak da se ne prihvaca", o):
        return False
    if re.search(r"donesen je zakljucak da se ne prihvaca", o):
        return True
    return None


def question_lines(r):
    """(how, takeaway): the question put, from the item page's result."""
    if r["yes_means_reject"] == 1:
        carried = conclusion_carried(r["outcome"])
        take = ("The question put was a conclusion NOT to accept the bill, so “Za” (for) "
                "was a vote to reject it and “Protiv” (against) a vote to keep it")
        if carried is True:
            take += ". The conclusion was adopted: the bill was not accepted"
        elif carried is False:
            take += ". The conclusion was not adopted"
        return "on a conclusion not to accept the bill: for = to reject", take
    if r["outcome"] is None:
        return None, ("The question put has not been read from the item page yet; on an "
                      "opposition bill at first reading “Za” can mean rejecting it")
    return None, None


def grouped_with(conn, r):
    """Other agenda items put to the same floor vote: the service repeats one
    record (same time and tally) on each."""
    got = ce.rows(conn, "SELECT COUNT(*) FROM hr_divisions WHERE voted_at = ? AND yes IS ? "
                  "AND no IS ? AND abstain IS ? AND division_key != ?",
                  (r["voted_at"], r["yes"], r["no"], r["abstain"], r["division_key"]))
    return got[0][0] if got else 0


def vote_lines(conn, r, how):
    lines = [ce.tally_line(r["yes"], r["no"], r["abstain"],
                           result=ce.clip(r["outcome"], 300) if r["outcome"] else None, how=how)]
    pos = ce.rows(conn, "SELECT party_seen, position FROM hr_votes WHERE division_key = ?",
                  (r["division_key"],))
    if pos:
        lines.append(ce.split_line(
            ce.group_counts([(p["party_seen"] or "no party listed", p["position"]) for p in pos],
                            FOR, AGAINST, ABSTAINED),
            label="By {0}".format(X6)))
        lines.append(ce.members_line(
            len(pos), caveat="No member is named against their party until party history is "
                             "sourced (X6). Absent members are not listed by the Sabor."))
    n = grouped_with(conn, r)
    if n:
        lines.append("Put to one floor vote with {0} other agenda item(s): the Sabor records "
                     "the same time and tally on each.".format(n))
    return lines


def votes(conn, since, until, wl):
    out = []
    for r in ce.rows(conn, "SELECT d.*, i.url, i.title AS item_title FROM hr_divisions d "
                     "LEFT JOIN hr_items i ON i.tid = d.tid WHERE "
                     + ce.window_sql("d.voted_at") + " ORDER BY d.voted_at", (since, until)):
        watched = watched_key(wl, r["tid"], r["bill_key"])
        if not ce.on_ground(r["areas"], watched):
            continue
        how, take = question_lines(r)
        title = r["item_title"] or r["title"]
        stage = reading(title)
        takeaway = ". ".join(x for x in (stage and "{0}, session {1}".format(
            stage, r["session_no"]), take) if x)
        key = key_of(r["tid"], r["bill_key"])
        out.append(ce.vote(
            CC, key, r["voted_at"], title, ce.areas_of(r["areas"]), r["tier"], watched,
            vote_lines(conn, r, how), terms=r["matched_terms"], url=r["url"] or
            VOTE_URL.format(tid=r["tid"]), takeaway=sentence(takeaway) or None,
            group=("hr", key), group_title=title,
            final=_fold(title).startswith("konacni prijedlog"),
            rebels_note="No member is named against their party until party history is "
                        "sourced (X6).", division=r["division_key"]))
    return out


def _baseline(conn):
    got = ce.rows(conn, "SELECT MIN(substr(first_seen,1,10)) FROM hr_items")
    return got[0][0] if got else None


def appearances(conn, bill_key):
    if not bill_key:
        return 1
    got = ce.rows(conn, "SELECT COUNT(DISTINCT session_id) FROM hr_items WHERE bill_key = ?",
                  (bill_key,))
    return got[0][0] if got else 1


def new_items(conn, since, until, wl):
    """Bills and items first put on an agenda in the window. The first run's
    backfill is not news: items first seen on the store's first day are left
    out."""
    base = _baseline(conn)
    out, seen = [], set()
    for r in ce.rows(conn, "SELECT * FROM hr_items WHERE " + ce.window_sql("first_seen")
                     + " ORDER BY tid", (since, until)):
        if base and ce.day(r["first_seen"]) <= base:
            continue
        watched = watched_key(wl, r["tid"], r["bill_key"])
        if not ce.on_ground(r["areas"], watched):
            continue
        key = key_of(r["tid"], r["bill_key"])
        if key in seen:
            continue
        if r["bill_key"]:
            older = ce.rows(conn, "SELECT 1 FROM hr_items WHERE bill_key = ? AND "
                            "substr(first_seen,1,10) <= ? LIMIT 1", (r["bill_key"], since))
            if older:
                continue                      # carried over, not new
        seen.add(key)
        out.append(ce.item(
            CC, "new", key, r["first_seen"], r["title"], ce.areas_of(r["areas"]), r["tier"],
            watched, status=STATUS.get(r["status_id"]), url=r["url"],
            terms=r["matched_terms"],
            takeaway="Put on the agenda of session {0}".format(r["session_no"])))
    return out


def items(conn, since, until, wl):
    return votes(conn, since, until, wl) + new_items(conn, since, until, wl)


def current_session(conn):
    got = ce.rows(conn, "SELECT session_id, session_no FROM hr_items WHERE session_id IS NOT NULL "
                  "ORDER BY tid DESC LIMIT 1")
    return (got[0]["session_id"], got[0]["session_no"]) if got else (None, None)


def week_ahead(conn, today, wl):
    """The current session's items on our ground still waiting for debate or
    a vote. The Sabor votes in a noon block, mostly on Fridays."""
    sid, sno = current_session(conn)
    if sid is None:
        return []
    out = []
    for r in ce.rows(conn, "SELECT * FROM hr_items WHERE session_id = ? AND status_id IN ({0}) "
                     "ORDER BY tid".format(",".join(str(s) for s in PENDING)), (sid,)):
        watched = watched_key(wl, r["tid"], r["bill_key"])
        if not ce.on_ground(r["areas"], watched):
            continue
        n = appearances(conn, r["bill_key"])
        take = "On the agenda of session {0}, {1}".format(sno, STATUS.get(r["status_id"], "pending"))
        if n > 1:
            take += "; on {0} sessions' agendas of this Sabor so far".format(n)
        out.append(ce.item(
            CC, "agenda", key_of(r["tid"], r["bill_key"]), r["last_seen"], r["title"],
            ce.areas_of(r["areas"]), r["tier"], watched, url=r["url"],
            terms=r["matched_terms"], takeaway=sentence(take)))
    return out


COUNTRY = ce.Country(
    cc=CC, name="Croatia", chamber="Hrvatski sabor", language="Croatian",
    taxonomies=(("taxonomy-hr.yaml", "hr"),),
    items=items, week_ahead=week_ahead, watchlist=watchlist,
    members_note=("Every recorded vote states the question put: on a conclusion not to "
                  "accept a bill, “Za” is a vote to reject it. Party splits use the party "
                  "in the member list when the vote was collected, not party at the vote "
                  "(X6), so no member-level claims are made"),
    coverage=(
        "Classification reads agenda titles only: Criminal Code and Health Care Act "
        "amendments are title-blind, and opposition bills are scanned PDFs (OCR is a later "
        "phase, X7).",
        "Amendments are not voted by roll call in the Sabor's service; items voted with no "
        "recorded vote (mostly unanimous) carry no positions.",
        "The week ahead is the current session's agenda: items on our ground not yet voted.",
    ),
)
