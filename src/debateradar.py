"""Which debates on our issues happened on a given day, and which are worth a pack.

Why this asks Hansard directly rather than reading the ledger: the ledger's spoken
sweep runs weekly over the week just ENDED, so on the day of a debate the ledger
holds almost nothing about it. Measured on 2026-09-07, the day of the surrogacy
debate: Hansard's search returned 25 contributions from 14 members, the ledger held
2. A radar built on the ledger would have ranked that debate below a protest debate
and missed the pack entirely.

The gate on each contribution is the SAME taxonomy precision gate the ledger uses,
so a debate cannot reach the radar on a passing word alone. Two further rules:

* a debate whose only areas are hidden ones (migration, area 11) never earns a pack.
  Area 11 is collated and never campaigned, on Christopher's standing instruction, so
  a busy small-boats debate must not produce reels and a canvas.
* a debate qualifies on MEMBERS, not contributions. One member intervening eight
  times in someone else's debate is not our debate; the "EU Membership Referendum"
  false positive of 2026-09-02 looked busy for exactly that reason.
"""

import datetime

from src import filter as filt
from src.ingest import hansard

HIDDEN_AREAS = (11,)     # migration: collated, never campaigned (partner.HIDDEN_AREAS)
FLOOR_MEMBERS = 3        # below this it is a passing mention, not a debate on our ground
STRONG_MEMBERS = 5       # at or above this, worth the footage and the reels


class Candidate(object):
    def __init__(self, debate_ext_id, title, house, date):
        self.debate_ext_id = debate_ext_id
        self.title = " ".join((title or "").split())
        self.house = house
        self.date = date
        self.members = set()
        self.contributions = set()
        self.areas = set()
        self.terms = set()

    @property
    def displayable_areas(self):
        return sorted(a for a in self.areas if a not in HIDDEN_AREAS)

    @property
    def hidden_only(self):
        return bool(self.areas) and not self.displayable_areas

    @property
    def title_matches(self):
        return bool(self._title_areas)

    def worth_a_pack(self, floor=FLOOR_MEMBERS):
        """Enough members, on ground we actually campaign on."""
        if self.hidden_only:
            return False
        return len(self.members) >= floor

    @property
    def strength(self):
        """'strong' earns footage and reels; 'watch' is report-only; 'thin' is neither."""
        if not self.worth_a_pack():
            return "thin"
        return "strong" if len(self.members) >= STRONG_MEMBERS or self.title_matches else "watch"

    def url(self):
        return "https://hansard.parliament.uk/{0}/{1}/debates/{2}/".format(
            self.house or "Commons", self.date.isoformat(), self.debate_ext_id)

    def __repr__(self):
        return "<Candidate %s %d members areas=%s %s>" % (
            self.title[:40], len(self.members), self.displayable_areas, self.strength)


def candidates(client, date, terms, tax, wl, log=None):
    """Ranked debates on our issues for one sitting day.

    `terms` is hansard.sweep_terms(settings) -- the same list the ledger sweeps, so
    the radar sees a debate exactly when the ledger later will.
    """
    from src.http import FetchError
    found = {}
    gaps = []
    iso = date.isoformat()
    for term in terms:
        try:
            rows, term_gaps = hansard.search_contributions_split(
                client, hansard.spoken_form(term), iso, iso, log=log)
            gaps.extend(term_gaps)
        except FetchError as exc:
            gaps.append((term, str(exc.cause)))
            if log:
                log("[gap] radar '{0}' {1}: {2}".format(term, iso, exc.cause))
            continue
        for c in rows:
            if not c.debate_ext_id or not c.member_id:
                continue
            matched = filt.match_passages(tax, wl, c.text or "", title=c.debate_title or "")
            if not matched:
                continue
            areas, hit_terms, _excerpt = filt.aggregate_passages(matched)
            cand = found.get(c.debate_ext_id)
            if cand is None:
                cand = found[c.debate_ext_id] = Candidate(c.debate_ext_id, c.debate_title, c.house, date)
                title_only = filt.match_passages(tax, wl, c.debate_title or "", title=c.debate_title or "")
                cand._title_areas = filt.aggregate_passages(title_only)[0] if title_only else []
            cand.members.add(c.member_id)
            cand.contributions.add(c.ext_id)
            cand.areas.update(areas)
            cand.terms.update(hit_terms)
    out = sorted(found.values(), key=lambda c: (len(c.members), len(c.contributions)), reverse=True)
    return out, gaps


def report(cands, gaps=(), date=None, floor=FLOOR_MEMBERS):
    """A plain-text radar reading: what qualified, what did not, and why."""
    lines = ["# Debate radar%s" % (": " + date.isoformat() if date else ""), ""]
    keep = [c for c in cands if c.worth_a_pack(floor)]
    drop = [c for c in cands if not c.worth_a_pack(floor)]
    if keep:
        lines.append("## Worth a pack")
        for c in keep:
            lines.append("* **%s** (%s) -- %d members, %d contributions, areas %s, %s"
                         % (c.title, c.house, len(c.members), len(c.contributions),
                            c.displayable_areas, c.strength))
            lines.append("  %s" % c.url())
        lines.append("")
    else:
        lines += ["## Worth a pack", "", "Nothing cleared %d members on ground we campaign on." % floor, ""]
    if drop:
        lines.append("## Seen and not proposed")
        for c in drop:
            why = "migration only (collated, never campaigned)" if c.hidden_only \
                else "%d member%s, below the floor of %d" % (len(c.members), "" if len(c.members) == 1 else "s", floor)
            lines.append("* %s -- %s" % (c.title, why))
        lines.append("")
    if gaps:
        lines += ["## Gaps", ""] + ["* %s" % (g if isinstance(g, str) else " ".join(str(x) for x in g)) for g in gaps] + [""]
    return "\n".join(lines)
