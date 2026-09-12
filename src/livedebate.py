"""Read a debate while it is still going (Christopher, 12 Sept 2026).

On 11 September Marie Goldman intervened at 09:56 and the stance pass read her
"neutral or unclear" -- the only supporter it read that way -- four hours before
she voted against the Bill. Nobody saw it, because the pack was built after the
vote. This compares the pass's reading of each speaker so far with what the
ledger already holds on them for the area, and names the contradictions:

  WOBBLE  read With us / unclear today, but their last vote on the area was
          against us (a supporter sounding like an opponent);
  SLIP    read Against us today, but their last vote was with us.

The pack tool does the reading (cached per speaker, so a re-run mid-debate costs
only the new speakers); this reads the pack and the ledger. Hansard publishes a
long debate in parts, so run it at lunchtime and again before the division.
"""

import json
import os
import re

from src import socialcut as sc

VOTE_KINDS = ("vote",)


def last_vote_on_area(conn, member_id, area, before=None):
    """(date, ref, stance) of the member's latest scored vote on the area, or None."""
    where = "AND e.date < ?" if before else ""
    args = [member_id] + ([before] if before else [])
    row = conn.execute(
        "SELECT e.date, e.ref, s.stance FROM mp_events e JOIN stance s ON s.ref = e.ref "
        "WHERE e.member_id = ? AND e.kind = 'vote' AND e.areas LIKE '%%' || ? || '%%' %s "
        "ORDER BY e.date DESC LIMIT 1" % where, [args[0], str(area)] + args[1:]).fetchone()
    return (row[0], row[1], row[2]) if row else None


def reading_of(pass_read):
    p = (pass_read or "").lower()
    return "with" if p.startswith("with us") else "against" if p.startswith("against") else "unclear"


def wobbles(conn, state, speeches, area, before=None):
    """[{name, party, read, last_vote, kind}] for every contradiction between today's
    reading and the member's last vote on the area. `state['speakers']` carries the
    member ids (keys); speeches carry the pass reads."""
    keys = {(sp.get("name") or "").strip().lower(): sp.get("key") for sp in state.get("speakers") or []}
    out = []
    for s in speeches:
        key = keys.get(re.sub(r"\s*MP$", "", s["name"]).strip().lower())
        if not key or not str(key).isdigit():
            continue
        read = reading_of(s.get("pass_read"))
        last = last_vote_on_area(conn, int(key), area, before)
        if not last or last[2] is None or last[2] == 0:
            continue
        with_us_last = last[2] > 0
        if read in ("with", "unclear") and not with_us_last:
            kind = "WOBBLE"
        elif read == "against" and with_us_last:
            kind = "SLIP"
        else:
            continue
        out.append({"name": s["name"], "party": s.get("party") or "", "seat": s.get("seat") or "",
                    "read": s.get("pass_read") or "", "kind": kind,
                    "last_vote": {"date": last[0], "ref": last[1], "stance": last[2]},
                    "words": max((c.get("words") or 0) for c in s.get("contributions") or [{}])})
    order = {"WOBBLE": 0, "SLIP": 1}
    out.sort(key=lambda r: (order[r["kind"]], r["read"].startswith("With") and 0 or 1, -r["words"]))
    return out


def dm_text(meta, speeches, found, as_of=None):
    n_with = sum(1 for s in speeches if reading_of(s.get("pass_read")) == "with")
    n_against = sum(1 for s in speeches if reading_of(s.get("pass_read")) == "against")
    lines = ["*Live read — %s%s*" % (meta.get("title", "debate"), (" as of %s" % as_of) if as_of else ""),
             "%d speakers so far: %d read with us, %d against, %d unclear." % (len(speeches), n_with, n_against, len(speeches) - n_with - n_against), ""]
    wob = [f for f in found if f["kind"] == "WOBBLE"]; slip = [f for f in found if f["kind"] == "SLIP"]
    if wob:
        lines.append("*Supporters sounding like opponents (last vote against us):*")
        lines += ["• %s (%s) — read %s; voted %s on %s" % (f["name"], f["party"], f["read"].split(" — ")[0].lower(), "against us" if f["last_vote"]["stance"] < 0 else "with us", f["last_vote"]["date"]) for f in wob]
        lines.append("")
    if slip:
        lines.append("*Our side sounding like the other (last vote with us):*")
        lines += ["• %s (%s) — read %s; voted with us on %s" % (f["name"], f["party"], f["read"].split(" — ")[0].lower(), f["last_vote"]["date"]) for f in slip]
        lines.append("")
    if not found:
        lines.append("No contradictions between today's readings and the vote record.")
    lines.append("_A reading is the pass's first cut of the words; the vote is the record. Re-run before the division._")
    return "\n".join(lines)
