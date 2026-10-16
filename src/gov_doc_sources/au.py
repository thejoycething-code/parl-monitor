"""Australia: the Department of Health's consultation hub and the Federal
Register of Legislation's made legislative instruments.

Probed 16 October 2026. Two sources, both keyless:

HEALTH CONSULTATION HUB (code 'health'). consultations.health.gov.au is a
Citizen Space instance (Delib) for the Department of Health, Disability and
Ageing, including the NDIS and disability consultations of its Disability
and Carers Group. Citizen Space's JSON search API
(/api/2.4/json_search_results?fields=extended&st=open|closed) lists every
activity with its start and end date (the closing date), its workspace
(the team that runs it), an HTML overview and its page: 33 open and 536
closed on 16 October 2026. robots.txt disallows only respondents' pages
(Disallow: /*view_respondent) and asks Crawl-delay: 5, which the guarded
client honours. Everything is a 'consultation'; the administrative forms
that live there as permanently open "surveys" (hearing-services
accreditation and the like) do not match the taxonomy and are not kept.

FEDERAL REGISTER OF LEGISLATION (code 'frl'). api.prod.legislation.gov.au
(documented OData API, src/robots_guard.DOCUMENTED_APIS; tools/au_schedule.py
and tools/au_rollcalls.py already read it). The search
titles/search(criteria='and(collection(LegislativeInstrument),
registrationdate(<start>,<today>))') lists every legislative instrument
registered in the window, compilations included, with
$expand=administeringDepartments for the body. $top is capped at 500, so it
is paged with $skip, ordered by id: without $orderby the pages overlap.
The search answers one row per matching registration, so a title can come
twice (the count, 760, counts rows); titles are de-duplicated. A title whose AS-MADE registration falls in the window
is a made instrument, a 'regulation'; a compilation of an older title is
left out. Plain $filter on makingDate or asMadeRegisteredAt answers 400.
(tools/au_schedule.py's au_instruments holds only the instruments still open
for disallowance, so it is not mirrored: the window needs every one made.)

NOT READ, and why (details in docs/australia-scope.md):
  * www.ag.gov.au (Attorney-General's consultations): robots.txt did not
    answer in three attempts (read timed out), so the guard treats the host
    as Disallow: / (RFC 9309 2.3.1 unreachable);
  * consult.industry.gov.au, consult.dcceew.gov.au,
    consultations.education.gov.au: Converlens "Open Point", a JavaScript
    application with no server-rendered listing and no documented API;
  * consult.dss.gov.au and consultation.infrastructure.gov.au do not resolve;
    engage.dss.gov.au has no Citizen Space API (404);
  * www.australia.gov.au now redirects to myGov's services page.

CLASSIFICATION. The English shared taxonomy (config/taxonomy.yaml), as
tools/au_monitor.py classifies.
"""

from __future__ import annotations

import urllib.parse

from src import gov_docs as G

CC = "au"
TAXONOMIES = (("taxonomy.yaml", None),)

HEALTH = ("https://consultations.health.gov.au/api/2.4/json_search_results?fields=extended"
          "&st={0}")
HEALTH_BODY = "Department of Health, Disability and Ageing"
FRL = "https://api.prod.legislation.gov.au/v1"
FRL_SEARCH = (FRL + "/titles/search(criteria={0})?$select=id,name,makingDate,asMadeRegisteredAt,"
              "status&$expand=administeringDepartments&$count=true&$orderby=id&$top={1}&$skip={2}")
FRL_PAGE = 500
FRL_PAGES = 6
FRL_TEXT = "https://www.legislation.gov.au/{0}/asmade/text"


# --- the Health consultation hub ------------------------------------------------------

def cs_date(value):
    """'2026/10/15' -> '2026-10-15'."""
    return G.iso((value or "").replace("/", "-"))


def parse_citizen_space(reply, body=HEALTH_BODY, source="health"):
    out = []
    for r in reply if isinstance(reply, list) else []:
        if (r.get("visibility") or "public") != "public" or not r.get("title"):
            continue
        key = "{0}/{1}".format(r.get("workspace_id") or r.get("dept") or "", r.get("id") or "")
        team = r.get("department") or r.get("workspace_title")
        out.append(G.entry(
            source, key.strip("/"), r["title"], "consultation",
            body="{0} ({1})".format(body, team) if team else body,
            published=cs_date(r.get("startdate")), closing_date=cs_date(r.get("enddate")),
            url=r.get("url"), summary=G.text(r.get("overview")),
            status=(r.get("status") or "").capitalize() or None))
    return out


def fetch_health(client, today, log):
    out, seen, gaps = [], set(), []
    for state in ("open", "closed"):
        try:
            reply = client.get_json(HEALTH.format(state), "au-govdocs",
                                    "health-{0}-{1}".format(state, today))
        except Exception as exc:                            # noqa: BLE001
            gaps.append("Citizen Space {0} list: {1}".format(state, str(exc)[:160]))
            continue
        for e in parse_citizen_space(reply):
            if e["doc_id"] not in seen:
                seen.add(e["doc_id"])
                out.append(e)
    return G.fetched(out, note="{0} activities listed (open and closed)".format(len(out)), gaps=gaps)


# --- the Federal Register of Legislation ------------------------------------------------

def frl_url(start, today, skip=0, top=FRL_PAGE):
    criteria = "'and(collection(LegislativeInstrument),registrationdate({0},{1}))'".format(start, today)
    return FRL_SEARCH.format(urllib.parse.quote(criteria), top, skip)


def parse_frl(reply, start):
    """[entry] for instruments MADE (first registered) on or after start."""
    out = []
    for r in (reply or {}).get("value") or []:
        made_reg = G.iso(r.get("asMadeRegisteredAt"))
        if not r.get("id") or not made_reg or made_reg < start:
            continue
        depts = "; ".join(d.get("name") for d in r.get("administeringDepartments") or []
                          if d.get("name")) or None
        out.append(G.entry("frl", r["id"], r.get("name"), "regulation", body=depts,
                           published=made_reg, url=FRL_TEXT.format(r["id"]),
                           status="Made {0}; {1}".format(G.iso(r.get("makingDate")) or "?",
                                                         r.get("status") or ""),
                           refs=[r["id"]]))
    return out


def fetch_frl(client, today, log):
    start = G.window_start(today)
    out, gaps, total, seen = [], [], None, set()
    for page in range(FRL_PAGES):
        reply = client.get_json(frl_url(start, today, page * FRL_PAGE), "au-govdocs",
                                "frl-{0}-{1}".format(today, page))
        total = reply.get("@odata.count", total)
        for e in parse_frl(reply, start):
            if e["doc_id"] not in seen:
                seen.add(e["doc_id"])
                out.append(e)
        if len(reply.get("value") or []) < FRL_PAGE:
            break
    else:
        gaps.append("FRL: {0} registered in the window, only {1} pages read".format(total, FRL_PAGES))
    return G.fetched(out, note="{0} registered in the window, {1} made in it".format(total, len(out)),
                     gaps=gaps)


SOURCES = (
    G.Source(code="health", name="Department of Health consultation hub (Citizen Space)",
             url="https://consultations.health.gov.au/", fetch=fetch_health),
    G.Source(code="frl", name="Federal Register of Legislation (made legislative instruments)",
             url=FRL, fetch=fetch_frl),
)
