"""Devolved petitions: the Senedd's and Holyrood's (Christopher, 2026-09-07).

Westminster's e-petitions are collated (never in the report); these join
them on the same companion page. The Senedd runs the same petitions
platform as Westminster -- petitions.senedd.wales/petitions.json, 50 a
page, thresholds 250 (referral to the Petitions Committee) and 10,000 (a
Plenary debate). Holyrood publishes every petition ever lodged as one
JSON dataset at data.parliament.scot/api/petitions (2,267 rows, 2.4MB;
status 11 = Under Consideration is the live set, 49 on 2026-09-07), with
a public page per petition number.
"""

from __future__ import annotations

from dataclasses import dataclass

SENEDD_API = "https://petitions.senedd.wales/petitions.json?state={state}"
SENEDD_PAGE = "https://petitions.senedd.wales/petitions/{id}"
SENEDD_STATES = ("open", "referred")
SCOT_API = "https://data.parliament.scot/api/petitions"
SCOT_PAGE = "https://petitions.parliament.scot/petitions/{number}"
# Holyrood status ids that mean the petition is live (statuses endpoint):
# 3 Under Review - PPC, 4 Open, 6 Referred, 10 Collecting Signatures, 11 Under Consideration
SCOT_LIVE = {3, 4, 6, 10, 11}
SCOT_STATUS = {0: "Proposed", 1: "Submitted", 2: "Action required", 3: "Under review", 4: "Open", 5: "Lodged",
               6: "Referred", 7: "Closed", 8: "Inadmissible", 9: "No further action", 10: "Collecting signatures",
               11: "Under consideration"}


@dataclass
class DvPetition:
    nation: str          # 'wales' | 'scotland'
    id: str
    action: str
    text: str
    signatures: int
    state: str
    url: str
    opened: str = None
    closes: str = None
    threshold_referral: int = None
    threshold_debate: int = None

    @property
    def key(self):
        return "{0}:{1}".format(self.nation, self.id)

    def milestone(self):
        if self.nation == "wales":
            if self.threshold_debate and self.signatures >= self.threshold_debate:
                return "Passed {0:,}: eligible for a Plenary debate".format(self.threshold_debate)
            if self.threshold_referral and self.signatures >= self.threshold_referral:
                return "Passed {0:,}: referred to the Petitions Committee".format(self.threshold_referral)
            if self.threshold_referral:
                return "{0:,} to referral{1}".format(max(self.threshold_referral - self.signatures, 0),
                                                    "; closes " + self.closes if self.closes else "")
        return self.state or ""


def parse_senedd(payload):
    out, nxt = [], (payload.get("links") or {}).get("next")
    for row in payload.get("data") or []:
        a = row.get("attributes") or {}
        out.append(DvPetition(
            nation="wales", id=str(row.get("id")), action=(a.get("action") or "").strip(),
            text=" ".join(x for x in (a.get("action"), a.get("background"), a.get("additional_details")) if x),
            signatures=a.get("signature_count") or 0, state=a.get("state"),
            url=SENEDD_PAGE.format(id=row.get("id")),
            opened=(a.get("opened_at") or "")[:10] or None, closes=(a.get("closed_at") or "")[:10] or None,
            threshold_referral=a.get("threshold_for_referral"), threshold_debate=a.get("threshold_for_debate")))
    return out, nxt


def fetch_senedd(client, states=SENEDD_STATES, max_pages=20):
    seen = {}
    for state in states:
        url, pages = SENEDD_API.format(state=state), 0
        while url and pages < max_pages:
            rows, url = parse_senedd(client.get_json(url, "petitions", "senedd-{0}-p{1}".format(state, pages + 1),
                                                     archive=False))
            for p in rows:
                seen[p.id] = p
            pages += 1
    return list(seen.values())


def parse_scotland(rows, live=SCOT_LIVE):
    out = []
    for r in rows or []:
        try:
            status = int(r.get("PetitionStatusID"))
        except (TypeError, ValueError):
            continue
        if status not in live:
            continue
        number = r.get("PetitionNumber") or str(r.get("ID"))
        out.append(DvPetition(
            nation="scotland", id=number, action=(r.get("PetitionTitle") or "").strip(),
            text=" ".join(x for x in (r.get("PetitionTitle"), r.get("PetitionSummary")) if x),
            signatures=int(r.get("SignaturesCollected") or 0), state=SCOT_STATUS.get(status, str(status)),
            url=SCOT_PAGE.format(number=number),
            opened=(r.get("DatePetitionFirstPublished") or "")[:10] or None))
    return out


def fetch_scotland(client):
    return parse_scotland(client.get_json(SCOT_API, "petitions", "scotland-all", archive=False))
