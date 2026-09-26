#!/usr/bin/env python3
"""Every Bundestag member since 1949, from the Bundestag's own register.

    python3 tools/de_stammdaten.py              # fetch, parse, store
    python3 tools/de_stammdaten.py --dry-run    # parse and count, store nothing
    python3 tools/de_stammdaten.py --file /tmp/mdb.zip   # a copy already on disk

Christopher, 26 September 2026: "get the MdB-Stammdaten." MdB-Stammdaten.zip
on www.bundestag.de/services/opendata -- 952 KB zipped, 15 MB of XML, 4,614
members, NO KEY.

WHY IT IS WORTH HOLDING when de_members already exists. Two reasons, and
neither is "more data":

  * It reaches back to 1949. abgeordnetenwatch covers the parliaments it
    covers; this is the register. A German 5CA that needs a member who left
    before the current Wahlperiode has nowhere else to look.
  * It carries ORTSZUSATZ -- the constituency the Stenografischer Bericht
    prints to tell two members of the same name apart, as in "Michael Brand
    (Fulda)". That heading form silently defeated the speech parser until
    25 September, and this is the authoritative list of who has one.

TWO ID SPACES, JOINED BY NAME. de_members keys on an abgeordnetenwatch
candidacy_mandate; this keys on the Bundestag's own member id. They are not
interchangeable and nothing here pretends otherwise.

A MEMBER CAN HAVE SEVERAL NAMES. The file records name changes with
HISTORIE_VON / HISTORIE_BIS -- 434 NAME elements across 400 members in the
sample. The CURRENT name is the one with no HISTORIE_BIS, and taking the
first would give some members the name they were elected under decades ago.

RELIGION IS NOT STORED. The file carries it; see the note in src/db.py.
"""

from __future__ import annotations

import argparse
import datetime
import io
import os
import sys
import xml.etree.ElementTree as ET
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db  # noqa: E402
from src.http import HttpClient  # noqa: E402

URL = "https://www.bundestag.de/resource/blob/472878/MdB-Stammdaten.zip"
MEMBER_XML = "MDB_STAMMDATEN.XML"
# Present in the file, deliberately not read. Kept as a NAME so the omission
# is visible to the next reader rather than looking like an oversight.
NOT_COLLECTED = ("RELIGION",)


def _text(el, path):
    found = el.find(path) if el is not None else None
    return (found.text or "").strip() if found is not None and found.text else ""


def _bare(value):
    """ORTSZUSATZ arrives as "(Fulda)", brackets and all. Stored bare, so it
    can be compared with what a parser pulled out of a heading without one
    side carrying punctuation the other does not."""
    return (value or "").strip().strip("()").strip()


def current_name(mdb):
    """The name the member goes by NOW.

    The one with no HISTORIE_BIS. Falling back to the last listed rather
    than the first: the file is chronological, so if every name is closed
    the most recent is still the best answer.
    """
    names = mdb.findall("NAMEN/NAME")
    if not names:
        return None
    open_ended = [n for n in names if not _text(n, "HISTORIE_BIS")]
    return (open_ended or names)[-1]


def parse(xml_bytes):
    """-> [(member dict, [term dicts])] for every MDB in the register."""
    root = ET.fromstring(xml_bytes)
    out = []
    for mdb in root.findall("MDB"):
        mdb_id = _text(mdb, "ID")
        name = current_name(mdb)
        if not mdb_id or name is None:
            continue
        bio = mdb.find("BIOGRAFISCHE_ANGABEN")
        terms = []
        for wp in mdb.findall("WAHLPERIODEN/WAHLPERIODE"):
            number = _text(wp, "WP")
            if not number.isdigit():
                continue
            terms.append({
                "mdb_id": mdb_id, "wp": int(number),
                "von": _text(wp, "MDBWP_VON"), "bis": _text(wp, "MDBWP_BIS"),
                "mandatsart": _text(wp, "MANDATSART"),
                "wkr_nummer": _text(wp, "WKR_NUMMER"),
                "wkr_name": _text(wp, "WKR_NAME"),
                "wkr_land": _text(wp, "WKR_LAND"),
                "liste": _text(wp, "LISTE"),
            })
        wps = [t["wp"] for t in terms]
        out.append(({
            "mdb_id": mdb_id,
            "nachname": _text(name, "NACHNAME"),
            "vorname": _text(name, "VORNAME"),
            "ortszusatz": _bare(_text(name, "ORTSZUSATZ")),
            "titel": _text(name, "AKAD_TITEL"),
            "praefix": _text(name, "PRAEFIX"),
            "adel": _text(name, "ADEL"),
            "partei": _text(bio, "PARTEI_KURZ"),
            "geschlecht": _text(bio, "GESCHLECHT"),
            "beruf": _text(bio, "BERUF"),
            "geburtsdatum": _text(bio, "GEBURTSDATUM"),
            "sterbedatum": _text(bio, "STERBEDATUM"),
            "vita_kurz": _text(bio, "VITA_KURZ"),
            "first_wp": min(wps) if wps else None,
            "last_wp": max(wps) if wps else None,
        }, terms))
    return out


def store(conn, records, today=None, dry_run=False):
    today = today or datetime.date.today().isoformat()
    if dry_run:
        return len(records), sum(len(t) for _m, t in records)
    members = terms = 0
    for member, member_terms in records:
        conn.execute(
            "INSERT INTO de_mdb (mdb_id, nachname, vorname, ortszusatz, titel,"
            " praefix, adel, partei, geschlecht, beruf, geburtsdatum,"
            " sterbedatum, vita_kurz, first_wp, last_wp, captured_at)"
            " VALUES (:mdb_id,:nachname,:vorname,:ortszusatz,:titel,:praefix,"
            ":adel,:partei,:geschlecht,:beruf,:geburtsdatum,:sterbedatum,"
            ":vita_kurz,:first_wp,:last_wp,:captured_at)"
            " ON CONFLICT(mdb_id) DO UPDATE SET nachname=excluded.nachname,"
            " vorname=excluded.vorname, ortszusatz=excluded.ortszusatz,"
            " titel=excluded.titel, praefix=excluded.praefix,"
            " adel=excluded.adel, partei=excluded.partei,"
            " beruf=excluded.beruf, sterbedatum=excluded.sterbedatum,"
            " vita_kurz=excluded.vita_kurz, last_wp=excluded.last_wp,"
            " captured_at=excluded.captured_at",
            dict(member, captured_at=today))
        members += 1
        for term in member_terms:
            conn.execute(
                "INSERT INTO de_mdb_terms (mdb_id, wp, von, bis, mandatsart,"
                " wkr_nummer, wkr_name, wkr_land, liste)"
                " VALUES (:mdb_id,:wp,:von,:bis,:mandatsart,:wkr_nummer,"
                ":wkr_name,:wkr_land,:liste)"
                " ON CONFLICT(mdb_id, wp) DO UPDATE SET bis=excluded.bis,"
                " mandatsart=excluded.mandatsart, wkr_name=excluded.wkr_name,"
                " wkr_land=excluded.wkr_land, liste=excluded.liste",
                term)
            terms += 1
    conn.commit()
    return members, terms


def fetch(client, path=None, log=print):
    """The register's XML bytes, from disk or from the Bundestag."""
    if path:
        with open(path, "rb") as handle:
            data = handle.read()
    else:
        data = client.get_bytes(URL, "de-stammdaten", "mdb-stammdaten")
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = [n for n in archive.namelist()
                 if n.upper().endswith("MDB_STAMMDATEN.XML")
                 and not n.startswith("__MACOSX")]
        if not names:
            log("  [gap] de-stammdaten: no {0} in the archive".format(MEMBER_XML))
            return b""
        return archive.read(names[0])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--file", help="a copy of the zip already on disk")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    xml_bytes = fetch(client, args.file)
    if not xml_bytes:
        return 1
    records = parse(xml_bytes)
    with_seat = sum(1 for m, _t in records if m["ortszusatz"])
    wps = [m["first_wp"] for m, _t in records if m["first_wp"]]
    print("de-stammdaten: {0} member(s), {1} with a constituency suffix, "
          "Wahlperioden {2}-{3}".format(
              len(records), with_seat, min(wps) if wps else "?",
              max(m["last_wp"] or 0 for m, _t in records)))
    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    members, terms = store(conn, records, dry_run=args.dry_run)
    print("de-stammdaten: {0} member(s), {1} term(s){2}".format(
        members, terms, " (dry run, nothing stored)" if args.dry_run else ""))
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
