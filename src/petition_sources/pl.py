"""Poland: the Sejm's public consultations on bills, and citizens'
legislative initiatives.

Probed 11 October 2026. The Sejm API (api.sejm.gov.pl, the host
tools/pl_rollcalls.py reads; no robots.txt) lists every bill received in the
term at /sejm/term10/bills, with the applicant (applicantType CITIZENS is a
citizens' initiative, which needed 100,000 signatures to be filed; 17 in
the term) and, for a bill put to public consultation, its start and end
dates (publicConsultationStartDate/EndDate; 11 open on 11 October). Both are
deadline-bearing: anyone may send an opinion while a consultation is open.
The API ignores sort_by, so the whole term is read (one request) and
filtered here.

Not covered: the Sejm's and Senate's petition pages and the government's
legislative portal (legislacja.gov.pl, legislacja.rcl.gov.pl) disallow
every crawler in robots.txt; senat.gov.pl answers 403.
"""

from __future__ import annotations

import datetime

from src import petitions as P

CC = "pl"
BILLS = "https://api.sejm.gov.pl/sejm/term10/bills?limit=5000"
PRINT = "https://www.sejm.gov.pl/Sejm10.nsf/druk.xsp?nr={0}"
RECORD = "https://api.sejm.gov.pl/sejm/term10/bills/{0}"
GRACE_DAYS = 30
INITIATIVE_DAYS = 365


def item_url(r):
    """The print's page when the bill has one, else the API record (a link
    for the reader, never fetched)."""
    if r.get("print"):
        return PRINT.format(r["print"])
    from urllib.parse import quote
    return RECORD.format(quote(r.get("number") or "", safe=""))


def parse_bills(rows, today):
    cut = (datetime.date.fromisoformat(today) - datetime.timedelta(days=GRACE_DAYS)).isoformat()
    since = (datetime.date.fromisoformat(today)
             - datetime.timedelta(days=INITIATIVE_DAYS)).isoformat()
    out = []
    for r in rows or []:
        number = r.get("number")
        if not number:
            continue
        end = r.get("publicConsultationEndDate")
        citizens = r.get("applicantType") == "CITIZENS"
        if r.get("publicConsultation") and end and end >= cut:
            out.append(P.entry("konsultacje", number, r.get("title"), kind="consultation",
                               summary=r.get("description"),
                               status="konsultacje publiczne ({0})".format(r.get("status") or "?"),
                               opened=r.get("publicConsultationStartDate"), closes=end,
                               body="Sejm", author=r.get("applicantType"),
                               refs=[r["print"]] if r.get("print") else (), url=item_url(r)))
        if citizens and (r.get("dateOfReceipt") or "") >= since:
            out.append(P.entry("obywatelski", number, r.get("title"), kind="initiative",
                               summary=r.get("description"), status=r.get("status"),
                               opened=r.get("dateOfReceipt"), body="Sejm",
                               author="obywatele (100 000 podpisów)",
                               refs=[r["print"]] if r.get("print") else (), url=item_url(r)))
    return out


def fetch(client, today, log=print):
    try:
        rows = client.get_json(BILLS, "pl-petitions", "bills")
    except Exception as exc:                        # noqa: BLE001
        return P.fetched([], gaps=["Sejm bills unreadable: {0}".format(str(exc)[:140])])
    got = parse_bills(rows, today)
    return got, len(rows or [])


def _split(code):
    def f(client, today, log=print):
        got = fetch(client, today, log)
        if isinstance(got, P.Fetched):
            return got
        entries, n = got
        mine = [e for e in entries if e["source"] == code]
        return P.fetched(mine, note="from {0} bills in the term".format(n))
    return f


SOURCES = (
    P.Source(code="konsultacje", name="Sejm public consultations on bills", kind="consultation",
             fetch=_split("konsultacje")),
    P.Source(code="obywatelski", name="citizens' bills (Sejm)", kind="initiative",
             fetch=_split("obywatelski")),
)
