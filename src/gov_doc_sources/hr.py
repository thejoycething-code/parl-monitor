"""Croatia: public consultations (e-Savjetovanja, through the national
open-data portal) and the regulations, decrees and Acts published in the
official gazette (Narodne novine, službeni dio).

Probed 16 October 2026 (docs/croatia-scope.md, "Government consultations and
publications").

E-SAVJETOVANJA ('esav'). The consultation portal esavjetovanja.gov.hr was
rebuilt in 2026 as a Blazor Server application: every page is an empty shell
whose content arrives over a SignalR websocket, no listing is in the HTML,
and the old ECon/MainScreen and RSS routes answer 404 (no robots.txt; nothing
is refused, there is simply nothing to read without running the app). The
Government Legislation Office (Ured za zakonodavstvo) publishes the portal's
register as open data on data.gov.hr instead: dataset 'eSavjetovanja'
(3df5d8d8-e2b2-4608-8a3e-f27c95b2f643, Otvorena dozvola), JSON, CSV and XML,
one row per consultation with the body, the kind of instrument, the title,
the status and the opening and closing dates (869 rows on 16 October 2026).
It is read through the portal's CKAN API (package_show, then the JSON
resource), so a renamed resource is followed. The dataset is a snapshot
refreshed about monthly ("data_refresh_frequency": "monthly"; last modified
10 October 2026, newest consultation opened 10 September), so a consultation
opened since the last refresh is not seen until the next one: the note says
how old the snapshot is and a snapshot over 45 days old is a gap. The row
carries no link to its page on the new portal (its routes are not public
URLs), so the URL is the portal's home and the id is kept in the doc id.

Kinds (vrstaPropisa): Zakon -> 'bill_draft'; Pravilnik, Uredba, Odluka ->
'regulation_draft'; Strateški dokument -> 'consultation'; Ostalo is read by
its title (a draft law, a draft rule, else a 'consultation'). The impact
assessment forms (Obrazac iskaza o procjeni učinaka propisa) and the annual
legislative-plan forms (Obrazac zakonodavnih aktivnosti) duplicate the
drafts they accompany and are not filed; neither are tender documents.

NARODNE NOVINE ('nn'). The gazette's own index of every act of the year
(get_index_file.aspx?year=YYYY&type=csv, the "Popis svih propisa" download of
the search page, data_access_hr.aspx): tab-separated, one row per act with
the issue, the act number, the title, the type (vrsta), whether it is whole,
an amendment or a repeal, the issuing body (donositelj) and the ELI link.
It has no dates, so each issue's publication date is read once from the
gazette's documented API (POST /api/act with the issue's first act,
nn_api_hr.aspx; JSON-LD, eli:date_publication), newest issue first, stopping
at the first issue older than the window: about 30 calls for 92 days.
Scoped to the government's instruments: zakon (an Act) -> 'law'; uredba,
pravilnik, naredba -> 'regulation'; odluka only from the Government or a
ministry -> 'regulation'; uputa and naputak from a ministry -> 'guidance'.
Court judgments, rješenja, statutes, collective agreements, the Sabor's own
decisions and the advertisements part (oglasni dio, disallowed by
robots.txt) are not read.

robots.txt: data.gov.hr serves its application page for /robots.txt (no
rules); narodne-novine.nn.hr disallows the advertisements part
(/clanci/oglasi/, kategorija=3) and a list of individual articles, and
allows /get_index_file.aspx and /api/.
"""

from __future__ import annotations

import csv
import datetime
import io
import json
import re

from src import gov_docs as G

CC = "hr"

CKAN = "https://data.gov.hr/ckan/api/3/action/package_show?id="
ESAV_DATASET = "3df5d8d8-e2b2-4608-8a3e-f27c95b2f643"
ESAV_PORTAL = "https://esavjetovanja.gov.hr/"
ESAV_STALE_DAYS = 45

NN = "https://narodne-novine.nn.hr"
NN_INDEX = NN + "/get_index_file.aspx?year={0}&type=csv"
NN_API_ACT = NN + "/api/act"
NN_MAX_ISSUES = 45          # date look-ups per year read (one per issue)

ESAV_KINDS = {"zakon": "bill_draft", "pravilnik": "regulation_draft",
              "uredba": "regulation_draft", "odluka": "regulation_draft",
              "strateški dokument": "consultation", "strateski dokument": "consultation",
              "ostalo": None}
ESAV_SKIP_TITLE = re.compile(
    r"obraz\w+\s+(iskaza|prethodne\s+procjene)|procjen\w+\s+u[čc]inaka|"
    r"obraz\w+\s+zakonodavnih\s+aktivnosti|plan\w*\s+zakonodavnih\s+aktivnosti", re.I)


def _sentence(name):
    """'MINISTARSTVO FINANCIJA' -> 'Ministarstvo financija'; mixed case kept."""
    name = G.one_line(name)
    if name and name.upper() == name:
        return name[:1] + name[1:].lower()
    return name


def esav_kind(vrsta, title):
    """The doc_type of one e-Savjetovanja row, or None when it is not filed."""
    if ESAV_SKIP_TITLE.search(title or ""):
        return None
    v = (vrsta or "").strip().lower()
    if v in ESAV_KINDS and ESAV_KINDS[v]:
        return ESAV_KINDS[v]
    if v not in ("ostalo", ""):
        return None
    t = (title or "").lower()
    if re.search(r"\bzakon", t):
        return "bill_draft"
    if re.search(r"pravilnik|uredb|odluk|naredb|naputk", t):
        return "regulation_draft"
    return "consultation"


def parse_ckan_package(reply):
    """(json resource url, metadata_modified date) from a CKAN package_show reply."""
    result = (reply or {}).get("result") or {}
    url = None
    for res in result.get("resources") or []:
        if (res.get("format") or "").upper() == "JSON" and res.get("url"):
            url = res["url"]
            break
    return url, G.iso(result.get("metadata_modified"))


def parse_esavjetovanja(rows):
    """[entry] from the dataset's JSON (a list of consultation rows)."""
    out = []
    for r in rows or []:
        if not isinstance(r, dict) or r.get("id") is None:
            continue
        title = G.one_line(r.get("nazivSavjetovanja"))
        kind = esav_kind(r.get("vrstaPropisa"), title)
        if not kind or not title:
            continue
        out.append(G.entry(
            "esav", r["id"], title, kind, body=_sentence(r.get("nazivTijela")),
            published=r.get("pocetakSavjetovanja"), closing_date=r.get("zavrsetakSavjetovanja"),
            url=ESAV_PORTAL, status=r.get("statusSavjetovanja"),
            summary="e-Savjetovanja, {0}".format(r.get("vrstaPropisa") or "savjetovanje"),
            refs=["esav-{0}".format(r["id"])]))
    return out


def fetch_esavjetovanja(client, today, log):
    pkg = client.get_json(CKAN + ESAV_DATASET, "hr-govdocs", "esav-package")
    url, modified = parse_ckan_package(pkg)
    if not url:
        return G.fetched([], gaps=["data.gov.hr eSavjetovanja: no JSON resource in the dataset"])
    rows = client.get_json(url, "hr-govdocs", "esav-data")
    entries = parse_esavjetovanja(rows)
    gaps = []
    age = None
    if modified:
        age = (datetime.date.fromisoformat(today) - datetime.date.fromisoformat(modified)).days
        if age > ESAV_STALE_DAYS:
            gaps.append("eSavjetovanja open data last refreshed {0} ({1} days ago)".format(modified, age))
    newest = max((e["published"] or "" for e in entries), default="") or None
    note = "data.gov.hr snapshot of {0} ({1} rows; newest consultation opened {2})".format(
        modified or "unknown date", len(rows or []), newest)
    return G.fetched(entries, note=note, gaps=gaps)


# --- Narodne novine -----------------------------------------------------------

NN_KINDS = {"zakon": "law", "uredba": "regulation", "pravilnik": "regulation",
            "naredba": "regulation", "odluka": "regulation", "uputa": "guidance",
            "naputak": "guidance"}


def _government(body):
    b = (body or "").lower()
    return b.startswith("vlada republike hrvatske") or b.startswith("ministarstv")


def nn_kind(vrsta, body):
    """The doc_type of one gazette row, or None when it is out of scope."""
    v = (vrsta or "").strip().lower()
    kind = NN_KINDS.get(v)
    if kind is None:
        return None
    if v == "odluka" and not _government(body):
        return None
    if v in ("uputa", "naputak") and not (body or "").lower().startswith("ministarstv"):
        return None
    return kind


def parse_nn_index(raw):
    """[row dict] from the year's index CSV: issue, year, act, title, vrsta,
    change, body, url. Rows out of scope are kept here; nn_kind() decides."""
    raw = raw.lstrip("﻿")
    out = []
    reader = csv.reader(io.StringIO(raw), delimiter="\t")
    head = next(reader, None)
    if not head or "Izdanje" not in head[0]:
        return out
    for cols in reader:
        if len(cols) < 8:
            continue
        m = re.match(r"NN\s+(\d+)/(\d{4})", cols[0].strip())
        if not m:
            continue
        out.append({"issue": int(m.group(1)), "year": int(m.group(2)), "act": cols[1].strip(),
                    "title": G.one_line(cols[2]), "vrsta": cols[3].strip(),
                    "change": cols[5].strip(), "body": G.one_line(cols[6]),
                    "url": cols[7].strip()})
    return out


def parse_nn_act_date(reply):
    """eli:date_publication from the API's JSON-LD reply, else None."""
    stack = [reply]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            for k, v in node.items():
                if k.endswith("date_publication"):
                    vals = v if isinstance(v, list) else [v]
                    for x in vals:
                        got = G.iso(x.get("@value") if isinstance(x, dict) else x)
                        if got:
                            return got
                stack.append(v)
        elif isinstance(node, list):
            stack.extend(node)
    return None


def nn_entries(rows, dates):
    """[entry] for the rows in scope whose issue has a known date."""
    out = []
    for r in rows:
        kind = nn_kind(r["vrsta"], r["body"])
        date = dates.get((r["year"], r["issue"]))
        if not kind or not date:
            continue
        out.append(G.entry(
            "nn", "{0}/{1}/{2}".format(r["year"], r["issue"], r["act"]), r["title"], kind,
            body=r["body"], published=date, url=r["url"],
            status="NN {0}/{1}, {2}".format(r["issue"], r["year"], r["change"] or r["vrsta"]),
            refs=["NN {0}/{1}".format(r["issue"], r["year"])]))
    return out


def fetch_narodne_novine(client, today, log):
    start = G.window_start(today)
    years = sorted({int(start[:4]), int(today[:4])}, reverse=True)
    rows, dates, gaps = [], {}, []
    for year in years:
        try:
            raw = client.get_text(NN_INDEX.format(year), "hr-govdocs", "nn-index-{0}".format(year))
        except Exception as exc:                            # noqa: BLE001
            gaps.append("NN index {0}: {1}".format(year, str(exc)[:160]))
            continue
        got = parse_nn_index(raw)
        if not got:
            gaps.append("NN index {0}: nothing parsed".format(year))
            continue
        rows += got
        firsts = {}
        for r in got:
            if r["issue"] not in firsts:
                firsts[r["issue"]] = r["act"]
        asked = 0
        for issue in sorted(firsts, reverse=True):
            if asked >= NN_MAX_ISSUES:
                gaps.append("NN {0}: stopped after {1} issue dates".format(year, asked))
                break
            asked += 1
            body = json.dumps({"part": "SL", "year": year, "number": issue,
                               "act_num": firsts[issue], "format": "JSON-LD"})
            try:
                reply = client.post_json(NN_API_ACT, body, "hr-govdocs",
                                         "nn-act-{0}-{1}".format(year, issue))
            except Exception as exc:                        # noqa: BLE001
                gaps.append("NN {0}/{1} date: {2}".format(issue, year, str(exc)[:120]))
                continue
            date = parse_nn_act_date(reply)
            if not date:
                continue
            dates[(year, issue)] = date
            if date < start:
                break
    entries = nn_entries(rows, dates)
    note = "{0} acts indexed, {1} issue dates read, {2} in scope".format(
        len(rows), len(dates), len(entries))
    return G.fetched(entries, note=note, gaps=gaps)


SOURCES = (
    G.Source(code="esav", name="e-Savjetovanja (open data, Ured za zakonodavstvo)",
             fetch=fetch_esavjetovanja, url=CKAN + ESAV_DATASET),
    G.Source(code="nn", name="Narodne novine (Acts, decrees, ministerial rules)",
             fetch=fetch_narodne_novine, url=NN + "/get_index_file.aspx"),
)
