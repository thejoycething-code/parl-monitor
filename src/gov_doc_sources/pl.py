"""Poland: the government's list of legislative work, the Dziennik Ustaw and
Monitor Polski, and the Sejm's public consultations on bills (16 October
2026).

WYKAZ PRAC ('wplip'). The government's legislative portal
(legislacja.gov.pl, legislacja.rcl.gov.pl), where drafts go out for public
consultation with their deadlines, answers `User-agent: * Disallow: /`, so
consultation closing dates are not read. The list of work behind it is
published by the Chancellery of the Prime Minister on www.gov.pl
(robots.txt: `User-agent: * Allow: /`): "Wykaz prac legislacyjnych i
programowych Rady Ministrów" (www.gov.pl/web/premier/wplip-rm), a register
whose page offers its whole content as one CSV file (/register-file/
Rejestr_<page id>.csv, 10.5 MB, 1,493 entries since December 2023; dane.gov.pl
dataset 301 points to the same page). Each entry: the project number (UD478,
RD343, ID...), title, kind (Projekty ustaw, Projekty rozporządzeń, Projekty
innych dokumentów rządowych), the ministry responsible, the purpose and
substance, the planned adoption date, status and the date it was entered
("Data publikacji", the window's date). A draft law is a 'bill_draft', a
draft regulation a 'regulation_draft', a programme or strategy a
'publication'. No closing date: the consultation stage lives on the
refused portal. The CSV link is read from the register page each run, and the
CSV is not archived (re-fetchable, and 10 MB a week in the raw tree).

DZIENNIK USTAW ('du') and MONITOR POLSKI ('mp'): the Sejm's ELI API
(api.sejm.gov.pl/eli, documented, src/robots_guard.DOCUMENTED_APIS),
/eli/acts/search?publisher=DU&dateFrom=<window start>: every act promulgated
in the window (327 on 16 October 2026) with its type, title, issuing body
(releasedBy) and keywords. Kept: Ustawa ('law'), Rozporządzenie
('regulation'); the consolidated texts (Obwieszczenie) and treaties are not.
From Monitor Polski, only the Council of Ministers' resolutions and the
Prime Minister's orders ('publication').

SEJM CONSULTATIONS ('sejm'): a mirror of country_petitions (source
'konsultacje', src/petition_sources/pl.py, the step before this one in
jobs/pl-weekly.sh): bills before the Sejm put to public consultation, with
their end date. Anyone may send an opinion while one is open: 'bill_draft'
with its closing date, a deadline row.
"""

from __future__ import annotations

import csv
import io
import re

from src import gov_docs as G

CC = "pl"
WPLIP_PAGE = "https://www.gov.pl/web/premier/wplip-rm"
GOV = "https://www.gov.pl"
ELI_SEARCH = "https://api.sejm.gov.pl/eli/acts/search?publisher={0}&dateFrom={1}&limit=2000"
DU_LINK = "https://dziennikustaw.gov.pl/DU/{0}/{1}"
MP_LINK = "https://monitorpolski.gov.pl/MP/{0}/{1}"

KINDS = {"Projekty ustaw": "bill_draft", "Projekty rozporządzeń": "regulation_draft",
         "Projekty innych dokumentów rządowych": "publication"}
DU_TYPES = {"Ustawa": "law", "Rozporządzenie": "regulation"}
MP_KEEP = (("Uchwała", "RADA MINISTRÓW"), ("Zarządzenie", "PREZ. RADY MINISTRÓW"))

# The register names the ministry by its short form. "ME" is both the
# Ministry of Education and the Ministry of Energy in the 2026 register, so it
# is not expanded: the person responsible is named beside it instead.
MINISTRIES = {
    "MS": "Ministerstwo Sprawiedliwości", "MZ": "Ministerstwo Zdrowia",
    "MEN": "Ministerstwo Edukacji Narodowej", "MRPiPS": "Ministerstwo Rodziny, Pracy i Polityki Społecznej",
    "MSWiA": "Ministerstwo Spraw Wewnętrznych i Administracji", "MF": "Ministerstwo Finansów",
    "MFiG": "Ministerstwo Finansów i Gospodarki", "MON": "Ministerstwo Obrony Narodowej",
    "MSZ": "Ministerstwo Spraw Zagranicznych", "MKiDN": "Ministerstwo Kultury i Dziedzictwa Narodowego",
    "MNiSW": "Ministerstwo Nauki i Szkolnictwa Wyższego", "MC": "Ministerstwo Cyfryzacji",
    "MI": "Ministerstwo Infrastruktury", "MRiRW": "Ministerstwo Rolnictwa i Rozwoju Wsi",
    "MKiŚ": "Ministerstwo Klimatu i Środowiska", "MSiT": "Ministerstwo Sportu i Turystyki",
    "MAP": "Ministerstwo Aktywów Państwowych", "MRiT": "Ministerstwo Rozwoju i Technologii",
    "MFiPR": "Ministerstwo Funduszy i Polityki Regionalnej",
    "KPRM": "Kancelaria Prezesa Rady Ministrów", "MRPiT": "Ministerstwo Rozwoju, Pracy i Technologii",
    "MPiT": "Ministerstwo Przemysłu", "MGMiŻŚ": "Ministerstwo Gospodarki Morskiej i Żeglugi Śródlądowej",
}


def _cell(row, *names):
    for n in names:
        v = row.get(n)
        if v and v.strip():
            return v.strip()
    return None


# --- Wykaz prac legislacyjnych i programowych Rady Ministrów -------------------------

def register_csv_url(page):
    """The register's CSV link from its page, absolute; None when absent."""
    m = re.search(r'href="(/register-file/[^"]+\.csv)"', page or "")
    return GOV + m.group(1) if m else None


def parse_wplip(text):
    out = []
    for r in csv.DictReader(io.StringIO(text.lstrip("﻿")), delimiter=";"):
        number, title = _cell(r, "Numer projektu"), _cell(r, "Tytuł")
        kind = KINDS.get(_cell(r, "Rodzaj dokumentu") or "")
        if not number or not title or not kind:
            continue
        organ = _cell(r, "Organ odpowiedzialny za opracowanie projektu", "Organ odpowiedzialny")
        body = MINISTRIES.get(organ or "")
        if not body and organ:
            person = _cell(r, "Osoba odpowiedzialna", "Osoba odpowiedzialna za opracowanie projektu")
            body = "{0} ({1})".format(organ, person) if person and len(organ) <= 8 else organ
        purpose = _cell(r, "Cele projektu oraz informacja o przyczynach i potrzebie rozwiązań "
                           "planowanych w projekcie") or ""
        substance = _cell(r, "Istota rozwiązań planowanych w projekcie, w tym proponowane środki "
                             "realizacji") or ""
        status = _cell(r, "Status realizacji") or "w przygotowaniu"
        if _cell(r, "Informacja o rezygnacji z prac nad projektem"):
            status = "rezygnacja z prac"
        planned = _cell(r, "Planowane przyjęcie przez RM", "Planowany termin przyjęcia projektu przez RM")
        if planned:
            status += "; planowane przyjęcie przez RM: " + planned
        out.append(G.entry("wplip", number, title, kind, body=body,
                           published=(_cell(r, "Data publikacji") or "")[:10],
                           url=_cell(r, "Podgląd") or WPLIP_PAGE,
                           summary=(purpose + " " + substance).strip() or None, status=status,
                           refs=[number]))
    return out


def fetch_wplip(client, today, log=print):
    try:
        page = client.get_text(WPLIP_PAGE, "pl-govdocs", "wplip-page")
    except Exception as exc:                            # noqa: BLE001
        return G.fetched([], gaps=["Wykaz prac page unreadable: {0}".format(str(exc)[:160])])
    url = register_csv_url(page)
    if not url:
        return G.fetched([], gaps=["Wykaz prac page carries no CSV link (layout changed?)"])
    try:
        text = client.get_text(url, "pl-govdocs", "wplip-csv", archive=False)
    except Exception as exc:                            # noqa: BLE001
        return G.fetched([], gaps=["Wykaz prac CSV unreadable: {0}".format(str(exc)[:160])])
    got = parse_wplip(text)
    return G.fetched(got, note="{0} entries in the register ({1})".format(len(got), url.rsplit("/", 1)[-1]),
                     gaps=[] if got else ["Wykaz prac CSV parsed to nothing (columns changed?)"])


# --- Dziennik Ustaw and Monitor Polski (ELI API) --------------------------------------

def _released(item):
    return "; ".join(item.get("releasedBy") or []) or None


def parse_du(reply):
    out = []
    for a in reply.get("items") or []:
        kind = DU_TYPES.get(a.get("type"))
        if not kind or not a.get("title"):
            continue
        out.append(G.entry("du", a.get("ELI") or a.get("address"), a["title"], kind,
                           body=_released(a), published=a.get("promulgation") or a.get("announcementDate"),
                           url=DU_LINK.format(a.get("year"), a.get("pos")),
                           summary=", ".join(a.get("keywords") or []) or None,
                           status="{0}; {1}".format(a.get("displayAddress") or "", a.get("status") or "").strip("; "),
                           refs=[a.get("ELI")] if a.get("ELI") else ()))
    return out


def parse_mp(reply):
    out = []
    for a in reply.get("items") or []:
        released = a.get("releasedBy") or []
        if not any(a.get("type") == t and b in released for t, b in MP_KEEP) or not a.get("title"):
            continue
        out.append(G.entry("mp", a.get("ELI") or a.get("address"), a["title"], "publication",
                           body=_released(a), published=a.get("promulgation") or a.get("announcementDate"),
                           url=MP_LINK.format(a.get("year"), a.get("pos")),
                           summary=", ".join(a.get("keywords") or []) or None,
                           status=a.get("displayAddress"), refs=[a.get("ELI")] if a.get("ELI") else ()))
    return out


def _eli(client, publisher, today, parse):
    url = ELI_SEARCH.format(publisher, G.window_start(today))
    try:
        reply = client.get_json(url, "pl-govdocs", "eli-{0}".format(publisher.lower()))
    except Exception as exc:                            # noqa: BLE001
        return G.fetched([], gaps=["ELI {0} search unreadable: {1}".format(publisher, str(exc)[:160])])
    got = parse(reply)
    gaps = []
    if (reply.get("totalCount") or 0) > len(reply.get("items") or []):
        gaps.append("ELI {0}: {1} acts in the window, {2} returned".format(
            publisher, reply.get("totalCount"), len(reply.get("items") or [])))
    return G.fetched(got, note="{0} acts promulgated in the window, {1} kept by type".format(
        reply.get("totalCount"), len(got)), gaps=gaps)


def fetch_du(client, today, log=print):
    return _eli(client, "DU", today, parse_du)


def fetch_mp(client, today, log=print):
    return _eli(client, "MP", today, parse_mp)


# --- the Sejm's consultations, mirrored --------------------------------------------------

def mirror_sejm(conn, cc, today):
    start = G.window_start(today)
    try:
        rows = conn.execute(
            "SELECT item_id, title, summary, status, opened, closes, author, url, refs, last_seen "
            "FROM country_petitions WHERE cc = ? AND kind = 'consultation' AND "
            "(closes >= ? OR opened >= ?)", (cc, start, start)).fetchall()
        ever = conn.execute("SELECT COUNT(*), MAX(last_seen) FROM country_petitions WHERE cc = ? "
                            "AND kind = 'consultation'", (cc,)).fetchone()
    except Exception as exc:                            # noqa: BLE001
        return G.fetched([], gaps=["country_petitions unreadable: {0}".format(str(exc)[:160])])
    out = []
    for r in rows:
        key = r[0].split(":", 1)[-1]
        applicant = {"GOVERNMENT": "government bill", "DEPUTIES": "deputies' bill",
                     "COMMITTEE": "committee bill", "CITIZENS": "citizens' bill",
                     "SENATE": "Senate bill", "PRESIDENT": "President's bill"}.get(r[6] or "", r[6])
        status = r[3] or "konsultacje publiczne"
        if applicant:
            status += "; " + applicant
        out.append(G.entry("sejm", key, r[1], "bill_draft", body="Sejm", published=r[4],
                           closing_date=r[5], url=r[7], summary=r[2], status=status,
                           refs=G.loads(r[8])))
    # A quiet window is not a gap; a table never filled is.
    gaps = [] if ever and ever[0] else [
        "country_petitions holds no Sejm consultation (has the petitions step run?)"]
    return G.fetched(out, note="mirrored from country_petitions ({0} in the window, last read {1})".format(
        len(out), ever[1] if ever else None), gaps=gaps)


SOURCES = (
    G.Source(code="wplip", name="Wykaz prac legislacyjnych i programowych Rady Ministrów",
             url=WPLIP_PAGE, fetch=fetch_wplip),
    G.Source(code="du", name="Dziennik Ustaw (acts and regulations, ELI API)",
             url="https://api.sejm.gov.pl/eli/acts/search?publisher=DU", fetch=fetch_du),
    G.Source(code="mp", name="Monitor Polski (Council of Ministers resolutions, ELI API)",
             url="https://api.sejm.gov.pl/eli/acts/search?publisher=MP", fetch=fetch_mp),
    G.Source(code="sejm", name="Sejm public consultations on bills (from the petitions step)",
             url="https://api.sejm.gov.pl/sejm/term10/bills", mirror=mirror_sejm),
)
