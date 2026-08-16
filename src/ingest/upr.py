"""Universal Periodic Review recommendations ingester (UN monitor, 4.14).

Every UN member state is reviewed by the others roughly every 4-5 years. Each
review produces recommendations naming who asked, who was asked, and -- the
part nobody else publishes usefully -- whether the state SUPPORTED or NOTED
each one. "Noted" is diplomatic language for refused.

That makes this the UN analogue of the Commons vote tracker: a per-state
record of positions taken on life, family and religious freedom, rather than
a feed of documents to read.

Source: UPR Info's Uwazi instance at upr-info-database.uwazi.io, probed
2026-08-16. It is a real JSON API, not a scrape.

Quirks encoded here, all measured rather than assumed:
  * issue filter values are full UUIDs from /api/thesauris. An abbreviated id
    silently returns totalRows=0 rather than an error, so the thesaurus must
    be fetched, never hardcoded from a screenshot;
  * paging is `from` (offset) + `limit`; pages come back disjoint;
  * `response` has THREE values, not two: Supported, Noted, Not Supported.
    Treating it as a boolean would misfile the third;
  * `issues` is multi-valued, and the UN's "Right to life" is mostly DEATH
    PENALTY recommendations. The issue filter narrows the field; it does not
    decide relevance. Everything here still goes through the taxonomy filter.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from urllib.parse import urlencode

UPR_API = "https://upr-info-database.uwazi.io/api"
ENTITY_URL = "https://upr-info-database.uwazi.io/entity/{0}"

# What a state did with a recommendation. Supported = accepted; Noted is the
# diplomatic form of refusal; Not Supported is explicit refusal.
ACCEPTED = "Supported"
REFUSED = ("Noted", "Not Supported")


@dataclass
class Recommendation:
    id: str                      # uwazi sharedId, stable across edits
    text: str
    state_under_review: str
    recommending_state: str
    response: str                # Supported | Noted | Not Supported
    issues: list = field(default_factory=list)
    cycle: str = None
    session: str = None
    action_category: str = None
    sur_group: str = None        # regional group of the state under review
    rs_group: str = None         # regional group of the recommending state

    @property
    def url(self):
        return ENTITY_URL.format(self.id)

    @property
    def refused(self):
        """True when the state declined. See REFUSED: two of three values."""
        return self.response in REFUSED


def _label(metadata, key):
    """First label of a uwazi multi-value field, or None."""
    values = metadata.get(key) or []
    if not values:
        return None
    first = values[0]
    return first.get("label") if isinstance(first, dict) else str(first)


def _labels(metadata, key):
    return [v.get("label") for v in (metadata.get(key) or [])
            if isinstance(v, dict) and v.get("label")]


def _value(metadata, key):
    """First raw value of a uwazi field (used for free-text like the
    recommendation itself, which carries `value` rather than `label`)."""
    values = metadata.get(key) or []
    if not values:
        return None
    first = values[0]
    return first.get("value") if isinstance(first, dict) else str(first)


def parse_recommendation(row):
    metadata = row.get("metadata") or {}
    return Recommendation(
        id=row.get("sharedId"),
        text=_value(metadata, "recommendation") or "",
        state_under_review=_label(metadata, "state_under_review"),
        recommending_state=_label(metadata, "recommending_state"),
        response=_label(metadata, "response"),
        issues=_labels(metadata, "issues"),
        cycle=_label(metadata, "cycle"),
        session=_label(metadata, "session"),
        action_category=_label(metadata, "action_category"),
        sur_group=_label(metadata, "state_under_review___regional_group"),
        rs_group=_label(metadata, "recommending_state___regional_group"),
    )


def parse_response(payload):
    """Uwazi envelope is {rows: [...], totalRows: n}."""
    return [parse_recommendation(row) for row in (payload.get("rows") or [])]


def fetch_issue_ids(client):
    """{issue label: uuid} from the Issues thesaurus.

    Fetched every run rather than pinned in config: the filter fails SILENTLY
    on a wrong id (totalRows=0, HTTP 200), so a stale hardcoded uuid would
    look like an issue nobody has raised rather than like a bug.
    """
    payload = client.get_json(UPR_API + "/thesauris", "upr", "thesauri")
    for row in (payload.get("rows") or []):
        if row.get("name") == "Issues":
            return {v.get("label"): v.get("id") for v in (row.get("values") or [])
                    if v.get("label") and v.get("id")}
    return {}


def fetch_recommendations(client, issue_id=None, issue_label=None, search_term=None,
                          page_size=100, max_pages=20):
    """Recommendations matching a search term and/or an issue tag, paged.

    Prefer search_term. QUOTE the phrase: unquoted multi-word terms match
    loosely, exactly as Parliament's Written Questions API does.
    Measured 2026-08-16:
        sexuality education     -> 10,000 (i.e. everything)
        "sexuality education"   ->    228
    Harvesting by issue tag alone means fetching thousands to keep dozens --
    "Rights of the Child" is 10,000+ rows of which ~127 are ours -- and hits
    max_pages long before it finishes.

    max_pages caps a runaway harvest; the caller is told when it bites rather
    than silently receiving a truncated set (see the return value).
    """
    if not issue_id and not search_term:
        raise ValueError("need an issue_id or a search_term to harvest")
    out, offset, total = [], 0, None
    slug_base = "search-{0}".format(
        (search_term or issue_label or issue_id).lower()
        .replace('"', "").replace(" ", "-")[:40])
    for page in range(max_pages):
        params = {"limit": str(page_size), "from": str(offset)}
        if issue_id:
            params["filters"] = json.dumps({"issues": {"values": [issue_id]}})
        if search_term:
            params["searchTerm"] = search_term
        query = urlencode(params)
        payload = client.get_json("{0}/search?{1}".format(UPR_API, query),
                                  "upr", "{0}-p{1}".format(slug_base, page))
        if total is None:
            total = payload.get("totalRows")
        batch = parse_response(payload)
        if not batch:
            break
        out.extend(batch)
        offset += len(batch)
        if total is not None and offset >= total:
            break
    truncated = bool(total is not None and len(out) < total)
    return out, total, truncated


def by_state(recommendations):
    """{state under review: {"supported": n, "refused": n}} -- the shape the
    tracker renders. Counted here so the caller cannot disagree about what
    "Noted" means."""
    tally = {}
    for rec in recommendations:
        if not rec.state_under_review:
            continue
        row = tally.setdefault(rec.state_under_review,
                               {"supported": 0, "refused": 0})
        row["refused" if rec.refused else "supported"] += 1
    return tally
