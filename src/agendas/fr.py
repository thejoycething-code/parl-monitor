"""France: the Assemblée nationale's agenda (ordre du jour) from its open
data.

`vp/reunions/Agenda.json.zip` (8.4 MB, one JSON per meeting) holds every
séance publique and committee meeting of the legislature, planned ones
included. Each point of the ordre du jour (`pointODJ`) carries the dossier
législatif it takes (`dossierRef`, 'DLR5L17N54445'), the key of
fr_dossiers and config/watchlist-fr.yaml. Measured 10 October 2026: 201
meetings from that day on (67 séances, 128 committee meetings, 5 study
groups), 67 of the committee meetings 'Eventuel'. A meeting with no point
(a hearing) is one point from its convocation text. Cancelled and deleted
meetings are left out.

The zip is archived (FR3: the AN overwrites it nightly). Committee names
come from the AN's organe file (AMO10) when tools/fr_rollcalls.py has
archived it the same day; otherwise the committee's organe reference is
shown.
"""

from __future__ import annotations

import datetime
import gzip
import io
import json
import os
import zipfile

from src import agenda
from src.http import FetchError

CC = "fr"
SOURCE = "the Assemblée nationale's open data, Agenda.json.zip"
BILLS = ("fr_dossiers", "dossier_ref", "title")
FEED = "fr-agenda"
LEG = 17
AGENDA = ("https://data.assemblee-nationale.fr/static/openData/repository/{0}/"
          "vp/reunions/Agenda.json.zip".format(LEG))
AMO10_ARCHIVE = "fr-rollcalls_amo10.json.gz"     # tools/fr_rollcalls.py's same-day copy
SKIP = ("Annulé", "Supprimé")
KIND = {"seance_type": "plenary", "reunionCommission_type": "committee"}
WEB = "https://www.assemblee-nationale.fr/dyn/17/agendas/{0}"


def as_list(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def texts(value):
    """Strings from an ODJ 'item' that may be a string, a list or None."""
    return [" ".join(str(x).split()) for x in as_list((value or {}).get("item")) if x]


def organes_from_amo10(blob):
    """{organe_ref: label} from the AMO10 zip's organe files."""
    out = {}
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        for name in zf.namelist():
            if "/organe/" in name and name.endswith(".json"):
                o = json.loads(zf.read(name)).get("organe") or {}
                if o.get("uid"):
                    out[o["uid"]] = o.get("libelle") or o.get("libelleAbrev")
    return out


def parse_reunion(r, organes=None):
    organes = organes or {}
    if (r.get("cycleDeVie") or {}).get("etat") in SKIP:
        return []
    stamp = r.get("timeStampDebut") or ""
    date, time = stamp[:10] or None, stamp[11:16] or None
    rtype = r.get("@xsi:type") or ""
    kind = KIND.get(rtype, "other")
    ref = r.get("organeReuniRef")
    if kind == "plenary":
        body = "Séance publique"
    else:
        body = organes.get(ref) or ("Committee meeting ({0})".format(ref) if ref else "Meeting")
    status = (r.get("cycleDeVie") or {}).get("etat")
    odj = r.get("ODJ") or {}
    url = WEB.format(r.get("uid"))
    out = []
    for p in as_list((odj.get("pointsODJ") or {}).get("pointODJ")):
        refs = as_list((p.get("dossiersLegislatifsRefs") or {}).get("dossierRef"))
        title = p.get("objet") or " ".join(texts(odj.get("resumeODJ")))
        out.append(agenda.point(p.get("uid"), date, title, body, kind, time,
                                p.get("procedure"), refs=refs, url=url,
                                status=status))
    if not out:
        words = texts(odj.get("resumeODJ")) or texts(odj.get("convocationODJ"))
        if words:
            out.append(agenda.point(r.get("uid"), date, words[0], body, kind, time,
                                    " ".join(words[1:]) or None, url=url, status=status))
    return out


def parse_zip(zf, today, end, organes=None):
    out = []
    for name in zf.namelist():
        if not name.endswith(".json"):
            continue
        r = json.loads(zf.read(name)).get("reunion") or {}
        day = (r.get("timeStampDebut") or "")[:10]
        if day and today <= day <= end:
            out += parse_reunion(r, organes)
    return out


def same_day_organes(client, today):
    path = os.path.join(client.raw_dir, client.archive_date or today, AMO10_ARCHIVE)
    if not os.path.exists(path):
        return {}
    try:
        with gzip.open(path, "rb") as fh:
            return organes_from_amo10(fh.read())
    except Exception:                               # noqa: BLE001 - a bad copy names nothing
        return {}


def fetch(client, today, days, log=print):
    end = (datetime.date.fromisoformat(today) + datetime.timedelta(days=days)).isoformat()
    try:
        blob = client.get_bytes(AGENDA, FEED, "agenda-{0}".format(LEG), timeout=180)
        zf = zipfile.ZipFile(io.BytesIO(blob))
    except (FetchError, zipfile.BadZipFile, ValueError) as exc:
        return agenda.fetched([], gaps=["Agenda.json.zip unreadable: {0}".format(str(exc)[:120])])
    organes = same_day_organes(client, today)
    points = parse_zip(zf, today, end, organes)
    plenary = sorted(p["date"] for p in points if p["kind"] == "plenary" and p["date"])
    note = None if organes else "Committee names were not available (AMO10 not archived today)"
    return agenda.fetched(points, next_sitting=plenary[0] if plenary else None, note=note)
