"""Attendance for the new country editions: who attended the committee and
plenary sittings, from each parliament's own open data, and how often each
member cast a vote in the recorded plenary votes.

    from src import attendance as att
    att.ensure(conn)
    att.collect(conn, client, "fr", today)            # fetch, parse, upsert
    att.summaries(conn, "fr")                         # what the profiles read
    att.participation(conn, "pl", today)              # derived from stored votes

    python3 tools/country_attendance.py br fr cl nl co pt   # the weekly step

The parity layer "attendance" (docs/country-parity-handover.md), generalising
the UK's tools/pull_pbc_attendance.py (who attended each Public Bill
Committee sitting, from the dagger in the Hansard roster) to the countries
built on 9-10 October 2026. The UK table (committee_attendance) is keyed on
Westminster member ids and is left as it is; the new countries share four
tables of their own:

  att_sittings   one row per sitting: its body (a committee, or the
                 plenary), date, the source's kind of roll, and the bills
                 the sitting's own agenda names (where the source links them);
  att_marks      one row per member per sitting, the status VERBATIM;
  att_referrals  which committee handled which bill, from the source's own
                 links (France's meeting agendas, the Tweede Kamer's
                 activities, the Câmara's tramitações);
  att_runs       when each source was last read, and what it gave.

WHAT EACH COUNTRY READS (probed 11 October 2026; every source is the
parliament's own open data, no key, no login, nothing behind a bot check):

  br  Câmara dos Deputados, dadosabertos.camara.leg.br: the year's bulk
      files eventosPresencaDeputados (who registered presence at each event,
      9 MB of CSV), eventosOrgaos (which organ held the event) and eventos
      (type and date). Committee meetings, and the plenary's deliberative
      sessions (solemn and non-deliberative sessions left out). The file
      lists only who was PRESENT: a member's sittings are those their
      committee held while they sat on it (src/member_intel.py's br-orgaos
      rows, with their start dates). Referrals: the tramitações of each bill
      on our ground (one request a bill).
  fr  Assemblée nationale, the Agenda open data (Licence Ouverte,
      Agenda.json.zip, 8 MB, the 17th legislature): each committee meeting's
      présences ("présent", "absent", "excusé" per member, as printed at the
      foot of the compte rendu) and the dossiers on its agenda (which give
      the referrals). The plenary (séances) carries no presence list.
  cl  Cámara de Diputados, opendata.camara.cl: the plenary sessions of the
      year and each one's attendance (WSSala retornarSesionAsistencia, one
      request per new session), and every current committee's sessions with
      their attendance (WSComision retornarSesionesXComisionYAnno, one
      request per committee). "Asiste" / "No Asiste" with the justification
      verbatim. No referral link (the sessions name no bill).
  nl  Tweede Kamer, gegevensmagazijn OData v4 (CC0): every committee debate,
      legislative and nota consultation held this term (Activiteit) with its
      participants (ActiviteitActor "Deelnemer") and its zaken (the
      referral). NOT A ROLL CALL: the Kamer lists who took part, and usually
      one spokesperson per party takes part, so the count is "took part in",
      never "attended", and is labelled so.
  pt  Assembleia da República, parlamento.pt "Presenças às Reuniões
      Plenárias" (added 11 October 2026): the XVII legislature's index of
      plenary sittings (reunioesplenarias.aspx, twenty a page, further pages
      by the page's own ASP.NET postback) and each sitting's roll
      (DetalheReuniaoPlenaria.aspx?BID=..., HTML, not the PDF the first
      round expected: the PDF beside each sitting is its agenda). Every
      seated deputy, with their group and "Presença (P)", "Falta", "Falta
      Justificada (FJ)" with its motive verbatim, "Ausência em Missão
      Parlamentar (AMP)", "Presença Noutro Órgão (PNO)", "Falta Injustificada
      (FI)" or "Falta ao Quórum de Votação". Deputies by their Biografia id,
      which is pt_members.cad_id (27,370 marks of 119 sittings, every one
      matched to pt_members and to an Efetivo period and group in the member
      service on the day). At most PT_MAX_SITTINGS rolls a run: the first
      runs backfill the legislature, then the new sittings and those of the
      last three weeks (re-read: a Falta is justified later).
  co  Colombia: nothing fetched here; the Cámara's plenary attendance is
      already in the store (co_attendance, tools/co_rollcalls.py, datos.gov.co
      48i3-vuny) and is copied across so that every country renders alike.

PLENARY VOTE PARTICIPATION (derived, no fetch): where a country's stored vote
records list the members who did not vote (IT absent / in missione / present,
CH "Nicht teilgenommen" / "Entschuldigt", PL ABSENT / PRESENT, ES "No vota",
AR AUSENTE, PE AUS and the licences, DO AU / SV, HU the four non-voting
codes), `participation` counts per member the votes cast against the votes
recorded for them, over the twelve months to the newest stored vote. Its
basis is stated with every figure: "from the vote records, which list
absences". Countries whose records list only those who voted (FR, BE, HR,
EC, BR's Câmara) get no participation figure: an absence there is not
recorded, and is never inferred.

NOT BUILT, and why (docs/country-parity-handover.md has the table):
  * Poland: the Sejm API's committee sittings carry no attendance (the lists
    are scanned PDFs); plenary participation is derived from the votes.
  * Switzerland, Austria, Italy: committee meetings are closed (CH, AT) or
    publish no presence (the Camera); plenary participation from the votes
    for CH and IT; Austria votes by group only.
  * Portugal: committees publish no attendance; the plenary roll is read
    (above, from 11 October 2026). Its votes are by group.
  * Spain: Cortes dissolved; the Congreso publishes no attendance file.
    Participation from the stored votes ("No vota").
  * Peru, Panama, the Dominican Senate: attendance as PDFs only.
  * Argentina, Ecuador, Mexico, Belgium, Croatia, Slovakia, Hungary: no
    attendance file found; participation from the votes where they list
    absences (AR, HU, DO, PE).

NO VERDICTS. Attendance is a count of what the parliament recorded. A member
can be absent on leave, on mission, or paired; the status is shown verbatim
and excused absences are counted apart. Nothing here posts or DMs.
"""

from __future__ import annotations

import csv
import datetime
import io
import json
import re
import sqlite3
import xml.etree.ElementTree as ET
import zipfile
from urllib.parse import quote

FEED = "attendance"

SCHEMA = (
    """CREATE TABLE IF NOT EXISTS att_sittings (
        cc          TEXT NOT NULL,
        sitting_key TEXT NOT NULL,      -- the source's own id: 'br-83009-2007', 'RUANR5L17S2025IDC453462'
        source      TEXT NOT NULL,      -- 'br-presenca', 'fr-agenda', 'cl-sala', ...
        body_kind   TEXT NOT NULL,      -- committee | plenary
        body_key    TEXT NOT NULL,      -- the source's id of the committee ('2007', 'PO420120', ...)
        body_name   TEXT,               -- verbatim
        date        TEXT,
        kind        TEXT,               -- the source's word for the sitting ('Reunião Deliberativa')
        roll        TEXT NOT NULL,      -- roll | present | participants (what the list is)
        bill_keys   TEXT,               -- JSON: the bills the sitting's own agenda names
        last_seen   TEXT NOT NULL,
        PRIMARY KEY (cc, sitting_key)
    )""",
    "CREATE INDEX IF NOT EXISTS att_sittings_body ON att_sittings (cc, body_key, date)",
    """CREATE TABLE IF NOT EXISTS att_marks (
        cc          TEXT NOT NULL,
        sitting_key TEXT NOT NULL,
        member_key  TEXT,               -- the store's member key, where the source gives its id
        member_ref  TEXT NOT NULL,      -- the source's own person id
        name        TEXT,
        status      TEXT,               -- verbatim: 'présent', 'Asiste', 'EXCUSA', ...
        present     INTEGER,            -- 1 present / took part, 0 absent
        excused     INTEGER,            -- 1 when the record gives a reason or says excused
        substitute  INTEGER,            -- 1 when sitting in for a full member
        PRIMARY KEY (cc, sitting_key, member_ref)
    )""",
    "CREATE INDEX IF NOT EXISTS att_marks_member ON att_marks (cc, member_key)",
    """CREATE TABLE IF NOT EXISTS att_referrals (
        cc          TEXT NOT NULL,
        bill_key    TEXT NOT NULL,      -- the store's own bill key (dossier, zaak, proposição)
        body_key    TEXT NOT NULL,
        body_name   TEXT,
        source      TEXT NOT NULL,
        first_date  TEXT,
        last_date   TEXT,
        sittings    INTEGER,            -- sittings of the body whose agenda named the bill
        PRIMARY KEY (cc, bill_key, body_key, source)
    )""",
    """CREATE TABLE IF NOT EXISTS att_runs (
        cc          TEXT NOT NULL,
        source      TEXT NOT NULL,
        last_seen   TEXT NOT NULL,
        sittings    INTEGER,
        marks       INTEGER,
        note        TEXT,
        PRIMARY KEY (cc, source)
    )""",
)

TABLES = ("att_sittings", "att_marks", "att_referrals", "att_runs")

ROLL_WORDS = {
    "roll": "the parliament's roll for each sitting (present, absent, excused)",
    "present": "the parliament's register of who was present; a sitting counts from the "
               "day the member joined the body",
    "participants": "the parliament's list of who took part; not a roll call (usually one "
                    "member per party takes part in a committee debate)",
}


def ensure(conn):
    for stmt in SCHEMA:
        conn.execute(stmt)
    conn.commit()
    return conn


def has_tables(conn):
    try:
        got = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND "
                           "name='att_sittings'").fetchone()
    except sqlite3.Error:
        return False
    return bool(got)


def clean(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()


def sitting(sitting_key, body_kind, body_key, body_name=None, date=None, kind=None,
            roll="roll", bill_keys=()):
    return {"sitting_key": str(sitting_key), "body_kind": body_kind, "body_key": str(body_key),
            "body_name": clean(body_name) or None, "date": (date or "")[:10] or None,
            "kind": clean(kind) or None, "roll": roll,
            "bill_keys": sorted({str(b) for b in bill_keys if b})}


def mark(sitting_key, member_ref, member_key=None, name=None, status=None, present=1,
         excused=0, substitute=0):
    return {"sitting_key": str(sitting_key), "member_ref": str(member_ref),
            "member_key": None if member_key is None else str(member_key),
            "name": clean(name) or None, "status": clean(status) or None,
            "present": None if present is None else int(bool(present)),
            "excused": int(bool(excused)), "substitute": int(bool(substitute))}


def referral(bill_key, body_key, body_name=None, first_date=None, last_date=None, sittings=None):
    return {"bill_key": str(bill_key), "body_key": str(body_key),
            "body_name": clean(body_name) or None, "first_date": first_date,
            "last_date": last_date, "sittings": sittings}


# --- the store -------------------------------------------------------------------------

def store(conn, cc, source, today, sittings=(), marks=(), referrals=None, note=None):
    """Upsert sittings; each sitting read this run has its marks replaced.
    `referrals`, when given, replaces this source's referral rows (a run that
    did not read them passes None and leaves them standing)."""
    sittings = list(sittings)
    marks = [m for m in marks if m["member_ref"]]
    with conn:
        for s in sittings:
            conn.execute(
                "INSERT INTO att_sittings (cc, sitting_key, source, body_kind, body_key, body_name, "
                "date, kind, roll, bill_keys, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT (cc, sitting_key) DO UPDATE SET source=excluded.source, "
                "body_kind=excluded.body_kind, body_key=excluded.body_key, "
                "body_name=COALESCE(excluded.body_name, att_sittings.body_name), "
                "date=excluded.date, kind=excluded.kind, roll=excluded.roll, "
                "bill_keys=excluded.bill_keys, last_seen=excluded.last_seen",
                (cc, s["sitting_key"], source, s["body_kind"], s["body_key"], s["body_name"],
                 s["date"], s["kind"], s["roll"], json.dumps(s["bill_keys"]), today))
            conn.execute("DELETE FROM att_marks WHERE cc=? AND sitting_key=?",
                         (cc, s["sitting_key"]))
        conn.executemany(
            "INSERT OR REPLACE INTO att_marks (cc, sitting_key, member_key, member_ref, name, "
            "status, present, excused, substitute) VALUES (?,?,?,?,?,?,?,?,?)",
            [(cc, m["sitting_key"], m["member_key"], m["member_ref"], m["name"], m["status"],
              m["present"], m["excused"], m["substitute"]) for m in marks])
        if referrals is not None:
            conn.execute("DELETE FROM att_referrals WHERE cc=? AND source=?", (cc, source))
            conn.executemany(
                "INSERT OR REPLACE INTO att_referrals (cc, bill_key, body_key, body_name, source, "
                "first_date, last_date, sittings) VALUES (?,?,?,?,?,?,?,?)",
                [(cc, r["bill_key"], r["body_key"], r["body_name"], source, r["first_date"],
                  r["last_date"], r["sittings"]) for r in referrals])
        conn.execute(
            "INSERT OR REPLACE INTO att_runs (cc, source, last_seen, sittings, marks, note) "
            "VALUES (?,?,?,?,?,?)", (cc, source, today, len(sittings), len(marks), note))
    return len(sittings), len(marks)


def referrals_from_sittings(sittings):
    """[referral] from the bills named on sittings' agendas, per (bill, body)."""
    acc = {}
    for s in sittings:
        if s["body_kind"] != "committee":
            continue
        for b in s["bill_keys"]:
            r = acc.setdefault((b, s["body_key"]), referral(b, s["body_key"], s["body_name"],
                                                            s["date"], s["date"], 0))
            r["sittings"] += 1
            if s["date"]:
                r["first_date"] = min(x for x in (r["first_date"], s["date"]) if x)
                r["last_date"] = max(x for x in (r["last_date"], s["date"]) if x)
    return list(acc.values())


def stored_keys(conn, cc, source):
    return {r[0] for r in conn.execute("SELECT sitting_key FROM att_sittings WHERE cc=? AND "
                                       "source=?", (cc, source))}


def member_keys(conn, sql):
    try:
        got = {str(r[0]) for r in conn.execute(sql)}
    except sqlite3.Error:
        return None
    return got or None


def body_names(conn, cc):
    """{group_key: group_name} from member intelligence (committee names the
    attendance sources do not print)."""
    try:
        return {str(k): n for k, n in conn.execute(
            "SELECT group_key, group_name FROM mi_groups WHERE cc=?", (cc,))}
    except sqlite3.Error:
        return {}


# --- the parsers (pure; fixtures in tests/fixtures/attendance/) --------------------------

# Brazil ------------------------------------------------------------------------------------

def parse_br_presence(text):
    """{event id: set(deputy id)} from eventosPresencaDeputados-<year>.csv."""
    out = {}
    rows = csv.DictReader(io.StringIO(text.lstrip("﻿")), delimiter=";")
    for r in rows:
        ev, dep = (r.get("idEvento") or "").strip(), (r.get("idDeputado") or "").strip()
        if ev and dep:
            out.setdefault(ev, set()).add(dep)
    return out


def parse_br_organ_names(reply):
    """{organ id: published name} from the bulk file orgaos.json."""
    out = {}
    for d in (reply or {}).get("dados") or []:
        m = re.search(r"/orgaos/(\d+)", d.get("uri") or "")
        if m:
            out[m.group(1)] = clean(d.get("nomePublicacao") or d.get("nome") or d.get("sigla"))
    return out


def parse_br_event_organs(reply):
    out = {}
    for d in (reply or {}).get("dados") or []:
        if d.get("idEvento") and d.get("idOrgao"):
            out.setdefault(str(d["idEvento"]), []).append((str(d["idOrgao"]),
                                                           d.get("siglaOrgao") or ""))
    return out


def parse_br_events(reply):
    return {str(d["id"]): {"date": (d.get("dataHoraInicio") or "")[:10],
                           "kind": clean(d.get("descricaoTipo")), "state": d.get("situacao")}
            for d in (reply or {}).get("dados") or [] if d.get("id")}


def br_plenary_kind(kind):
    """The plenary's deliberative sessions only: a solemn or non-deliberative
    session is not one a member is expected at."""
    k = (kind or "").lower()
    return "deliberativa" in k and "não deliberativa" not in k and "nao deliberativa" not in k


def build_br(presence, organs, events, names=None):
    """(sittings, marks) for the events with presence registered."""
    names = names or {}
    sittings, marks = [], []
    for ev, deps in sorted(presence.items()):
        info = events.get(ev) or {}
        for organ, sigla in organs.get(ev) or []:
            plenary = sigla == "PLEN"
            if plenary and not br_plenary_kind(info.get("kind")):
                continue
            key = "br-{0}-{1}".format(ev, organ)
            sittings.append(sitting(key, "plenary" if plenary else "committee", organ,
                                    "Plenário da Câmara" if plenary else
                                    names.get(organ) or sigla, info.get("date"),
                                    info.get("kind"), roll="present"))
            marks += [mark(key, d, member_key="camara-{0}".format(d), status="presente")
                      for d in sorted(deps)]
    return sittings, marks


BR_SKIP_ORGANS = {"PLEN", "MESA", "CCP", "SGM", "SECAP", "COPER", "GAB", "CORREG"}


def parse_br_tramitacoes(bill_key, reply):
    """[referral] for the organs a bill passed through (the plenary and the
    clerk's desks left out)."""
    acc = {}
    for t in (reply or {}).get("dados") or []:
        m = re.search(r"/orgaos/(\d+)", t.get("uriOrgao") or "")
        sigla = (t.get("siglaOrgao") or "").strip()
        if not m or sigla.upper() in BR_SKIP_ORGANS:
            continue
        date = (t.get("dataHora") or "")[:10] or None
        r = acc.setdefault(m.group(1), referral(bill_key, m.group(1), sigla, date, date, None))
        if date:
            r["first_date"] = min(x for x in (r["first_date"], date) if x)
            r["last_date"] = max(x for x in (r["last_date"], date) if x)
    return list(acc.values())


# France ------------------------------------------------------------------------------------

FR_PRESENT = {"présent": (1, 0), "absent": (0, 0), "excusé": (0, 1)}


def _as_list(x):
    return x if isinstance(x, list) else ([] if x is None else [x])


def parse_fr_agenda(raw, today, names=None):
    """(sittings, marks) from Agenda.json.zip's bytes: the committee meetings
    held by `today` with a presence list."""
    names = names or {}
    z = zipfile.ZipFile(io.BytesIO(raw))
    sittings, marks = [], []
    for n in sorted(z.namelist()):
        if not n.endswith(".json"):
            continue
        r = json.loads(z.read(n)).get("reunion") or {}
        pi = ((r.get("participants") or {}).get("participantsInternes") or {}) \
            if isinstance(r.get("participants"), dict) else {}
        people = _as_list(pi.get("participantInterne"))
        date = (r.get("timeStampDebut") or "")[:10]
        if not people or not r.get("organeReuniRef") or not date or date > today:
            continue
        if ((r.get("cycleDeVie") or {}).get("etat") or "") in ("Annulé", "Supprimé"):
            continue
        dossiers = []
        for p in _as_list(((r.get("ODJ") or {}).get("pointsODJ") or {}).get("pointODJ")):
            refs = (p or {}).get("dossiersLegislatifsRefs") or {}
            dossiers += [x for x in _as_list(refs.get("dossierRef")) if isinstance(x, str)]
        organ = r["organeReuniRef"]
        key = r.get("uid")
        sittings.append(sitting(key, "committee", organ, names.get(organ), date,
                                (r.get("@xsi:type") or "").replace("_type", ""), "roll", dossiers))
        for p in people:
            ref = p.get("acteurRef")
            status = p.get("presence") or ""
            present, excused = FR_PRESENT.get(status, (None, 0))
            if ref:
                marks.append(mark(key, ref, member_key=ref, status=status, present=present,
                                  excused=excused))
    return sittings, marks


# Chile -------------------------------------------------------------------------------------

CL_NS = "{http://opendata.camara.cl/camaradiputados/v1}"


def _t(el, path):
    got = el.find("/".join(CL_NS + p for p in path.split("/")))
    return clean(got.text) if got is not None and got.text else None


def _cl_name(dip):
    return " ".join(x for x in (_t(dip, "Nombre"), _t(dip, "ApellidoPaterno"),
                                _t(dip, "ApellidoMaterno")) if x)


def _cl_marks(key, parent):
    out = []
    for a in parent.iter(CL_NS + "Asistencia"):
        dip = a.find(CL_NS + "Diputado")
        tipo = a.find(CL_NS + "TipoAsistencia")
        if dip is None or tipo is None:
            continue
        ref = _t(dip, "Id")
        just = a.find(CL_NS + "Justificacion")
        why = _t(just, "Nombre") if just is not None else None
        titular = a.find(CL_NS + "TipoTitularAsistencia")
        status = clean(tipo.text) + (" ({0})".format(why) if why else "")
        out.append(mark(key, ref, member_key="D-{0}".format(ref), name=_cl_name(dip),
                        status=status, present=tipo.get("Valor") == "1", excused=bool(why),
                        substitute=titular is not None and titular.get("Valor") not in (None, "1")))
    return out


def parse_cl_sessions(text):
    """[(id, date, held)] from WSSala retornarSesionesXAnno."""
    root = ET.fromstring(text.encode("utf-8"))
    out = []
    for s in root.iter(CL_NS + "Sesion"):
        estado = s.find(CL_NS + "Estado")
        out.append((_t(s, "Id"), (_t(s, "FechaInicio") or "")[:10],
                    estado is not None and estado.get("Valor") == "1"))
    return out


def parse_cl_session(text):
    """(sitting, marks) from WSSala retornarSesionAsistencia."""
    root = ET.fromstring(text.encode("utf-8"))
    sid = _t(root, "Id")
    key = "cl-sala-{0}".format(sid)
    tipo = root.find(CL_NS + "Tipo")
    s = sitting(key, "plenary", "sala", "Sala de la Cámara", _t(root, "FechaInicio"),
                "Sesión {0} {1}".format(_t(root, "Numero") or "", clean(tipo.text) if tipo is not None
                                        else ""), "roll")
    return s, _cl_marks(key, root)


def parse_cl_committees(text):
    """[(id, name)] from WSComision retornarComisionesVigentes."""
    root = ET.fromstring(text.encode("utf-8"))
    return [(_t(c, "Id"), _t(c, "Nombre")) for c in root.iter(CL_NS + "Comision")
            if _t(c, "Id")]


def parse_cl_committee_sessions(text, today):
    """(sittings, marks) from WSComision retornarSesionesXComisionYAnno: the
    sessions held (Estado 'Celebrada') by `today`."""
    root = ET.fromstring(text.encode("utf-8"))
    cid, cname = _t(root, "Id"), _t(root, "Nombre")
    sittings, marks = [], []
    for s in root.iter(CL_NS + "SesionComision"):
        date = (_t(s, "FechaInicio") or "")[:10]
        estado = s.find(CL_NS + "Estado")
        if not date or date > today or (estado is not None and "Celebrada" not in (estado.text or "")):
            continue
        key = "cl-com-{0}".format(_t(s, "Id"))
        tipo = s.find(CL_NS + "Tipo")
        sittings.append(sitting(key, "committee", cid, cname, date,
                                "Sesión {0} {1}".format(_t(s, "Numero") or "",
                                                         clean(tipo.text) if tipo is not None else ""),
                                "roll"))
        holder = s.find(CL_NS + "Asistencia")
        if holder is not None:
            marks += _cl_marks(key, holder)
    return sittings, marks


# Netherlands -------------------------------------------------------------------------------

NL_KINDS = ("Commissiedebat", "Wetgevingsoverleg", "Notaoverleg")


def parse_nl_activities(rows):
    """(sittings, marks) from Activiteit rows with ActiviteitActor and Zaak
    expanded: the lead committee (Voortouwcommissie_Id, Voortouwnaam) is the
    body; the members marked 'Deelnemer' took part ('Afgemeld', withdrawn,
    is not counted)."""
    sittings, marks = [], []
    for a in rows:
        actors = a.get("ActiviteitActor") or []
        if not a.get("Voortouwcommissie_Id"):
            continue
        zaken = []
        for z in a.get("Zaak") or []:
            if z.get("Nummer"):
                zaken.append(z["Nummer"])
            for d in _as_list(z.get("Kamerstukdossier")):
                if d and d.get("Nummer"):
                    zaken.append(str(d["Nummer"]))
        key = a.get("Id")
        sittings.append(sitting(key, "committee", a["Voortouwcommissie_Id"], a.get("Voortouwnaam"),
                                a.get("Datum"), "{0}: {1}".format(a.get("Soort") or "",
                                                                  clean(a.get("Onderwerp"))[:120]),
                                "participants", zaken))
        for x in actors:
            if x.get("Relatie") == "Deelnemer" and x.get("Persoon_Id") and \
                    "bewindspersoon" not in (x.get("Functie") or "").lower():
                marks.append(mark(key, x["Persoon_Id"], member_key=x["Persoon_Id"],
                                  name=x.get("ActorNaam"), status="Deelnemer"))
    return sittings, marks


# Colombia (from the store) -------------------------------------------------------------------

def co_rows(conn):
    """(sittings, marks) from co_attendance (Cámara plenary, datos.gov.co)."""
    try:
        got = conn.execute("SELECT member_key, session, date, joint, status FROM co_attendance "
                           "ORDER BY date, session").fetchall()
    except sqlite3.Error:
        return [], []
    sittings, marks, seen = [], [], set()
    for member, session, date, joint, status in got:
        key = "co-{0}".format(session)
        if key not in seen:
            seen.add(key)
            sittings.append(sitting(key, "plenary", "congreso-pleno" if joint else "camara-plenaria",
                                    "Congreso pleno" if joint else "Plenaria de la Cámara", date,
                                    session, "roll"))
        s = fold_status(status)
        marks.append(mark(key, member, member_key=member, status=status,
                          present=s.startswith("asist"), excused=s.startswith("excus")))
    return sittings, marks


# Portugal -----------------------------------------------------------------------------------
#
# The Assembleia's "Presenças às Reuniões Plenárias" (parlamento.pt, probed 11
# October 2026; no robots.txt on www.parlamento.pt, a 404). The handover said
# a PDF per sitting: the PDF beside each sitting is its AGENDA; the roll itself
# is an HTML page per sitting (DetalheReuniaoPlenaria.aspx?BID=<id>), every
# seated deputy with their group and one of "Presença (P)", "Falta",
# "Falta Justificada (FJ)" (with its "Motivo": "Casamento", "Trabalho
# Político", "Trabalho Parlamentar", "Dificuldades de transportes", ...) or
# "Ausência em Missão Parlamentar (AMP)". Each deputy links to their
# Biografia.aspx?BID=<DepCadId>, the same person id as pt_members.cad_id.
# The index (reunioesplenarias.aspx) lists the XVII legislature's sittings,
# newest first, twenty a page; further pages only by the page's own ASP.NET
# postback (client.post_form, as the Québec sittings index).

def _pt_attrs(tag):
    import html as _html
    return {k.lower(): _html.unescape(v) for k, v in re.findall(r'([\w:$.-]+)="([^"]*)"', tag)}


def _pt_text(fragment):
    import html as _html
    return clean(_html.unescape(re.sub(r"<[^>]+>", " ", fragment or "")))


_PT_ROW = re.compile(r'lvResults_ctrl(\d+)_hplData"[^>]*?href="[^"]*?DetalheReuniaoPlenaria\.aspx\?BID=(\d+)"'
                     r'[^>]*>([^<]*)</a>', re.S)
_PT_PAGER = re.compile(r"__doPostBack\(&#39;([^&]*dpgResults[^&]*)&#39;,&#39;&#39;\)\">(\d+)</a>")
_PT_CELL = re.compile(r'rptDetalhe_(ctl\d+)_(hplDeputado|lblGP|lblPresenca|lblMotivo)"([^>]*)>([^<]*)<')


def parse_pt_index(page):
    """([{bid, date, number, kind, session}], {page number: postback target},
    the listed total) from one page of reunioesplenarias.aspx."""
    rows = []
    marks_ = list(_PT_ROW.finditer(page or ""))
    for i, m in enumerate(marks_):
        block = page[m.end():marks_[i + 1].start() if i + 1 < len(marks_) else len(page)]
        block = block.split('class="pager"')[0]
        num = re.search(r'_hplNumero"[^>]*>([^<]*)</a>', block)
        fich = re.search(r"Fich=([A-Z]+)_(\d+)_(\d+)_", block)
        kind = re.search(r'Tipo</div>\s*<div class="TextoRegular">([^<]*)<', block)
        rows.append({"bid": m.group(2), "date": clean(m.group(3))[:10],
                     "number": clean(num.group(1)) if num else None,
                     "kind": clean(kind.group(1)) if kind else None,
                     "legislature": fich.group(1) if fich else None,
                     "session": fich.group(2) if fich else None})
    pages = {int(n): t for t, n in _PT_PAGER.findall(page or "")}
    total = re.search(r"(\d+)\s+registos", page or "")
    return rows, pages, int(total.group(1)) if total else None


def pt_form(page, target):
    """The index page's own form, as the browser posts it to change page."""
    fields = [("__EVENTTARGET", target), ("__EVENTARGUMENT", "")]
    for tag in re.findall(r"<input\b[^>]*>", page or "", re.I):
        a = _pt_attrs(tag)
        if a.get("name") and a.get("type", "text").lower() == "hidden" and \
                a["name"] not in ("__EVENTTARGET", "__EVENTARGUMENT"):
            fields.append((a["name"], a.get("value", "")))
    return fields


def pt_status(word):
    """(present, excused) for the roll's word: "Presença (P)" present; a
    justified absence (FJ), an absence on parliamentary mission (AMP) and a
    presence at another organ of the Assembleia (PNO, not in the plenary)
    excused; "Falta", "Falta Injustificada (FI)" and "Falta ao Quórum de
    Votação" absent; anything else (None, 0), kept verbatim and never counted
    as present. Measured over the 119 sittings of the XVII to 7 October 2026."""
    f = fold_status(word)
    if f.startswith("presenca noutro orgao"):
        return 0, 1                       # PNO: present at another organ, not the plenary
    if f.startswith("presenc"):
        return 1, 0
    if f.startswith("falta justificada") or f.startswith("ausencia"):
        return 0, 1
    if f.startswith("falta"):
        return 0, 0
    return None, 0


def parse_pt_sitting(text, bid, row=None):
    """(sitting, marks) from one DetalheReuniaoPlenaria page. The status is
    verbatim; a justified absence carries its motive after a colon
    ("Falta Justificada (FJ): Casamento"). `row` is the index's line for the
    sitting (number, kind, session), when read from it."""
    row = row or {}
    head = re.search(r'_lblHeader"[^>]*>([^<]*)<', text or "")
    header = _pt_text(head.group(1)) if head else ""
    d = re.search(r"(\d{4}-\d{2}-\d{2})", header)
    date = row.get("date") or (d.group(1) if d else None)
    k = re.search(r"Plenária (\S+) de", header)
    kind = row.get("kind") or (k.group(1) if k else None)
    bits = ["Reunião Plenária"]
    if row.get("number"):
        bits[0] += " n.º {0}".format(row["number"])
    if kind:
        bits.append(kind)
    if row.get("session"):
        bits.append("{0}.ª sessão legislativa".format(row["session"]))
    key = "pt-rp-{0}".format(bid)
    s = sitting(key, "plenary", "plenario", "Plenário da Assembleia da República", date,
                ", ".join(bits), "roll")
    cells = {}
    for ctl, what, attrs, val in _PT_CELL.findall(text or ""):
        c = cells.setdefault(ctl, {})
        c[what] = _pt_text(val)
        if what == "hplDeputado":
            ref = re.search(r"Biografia\.aspx\?BID=(\d+)", attrs)
            c["ref"] = ref.group(1) if ref else None
    marks = []
    for ctl in sorted(cells, key=lambda k: int(k[3:])):
        c = cells[ctl]
        name, word = c.get("hplDeputado"), c.get("lblPresenca")
        if not name or not word:
            continue
        present, excused = pt_status(word)
        why = c.get("lblMotivo")
        status = word + (": " + why if why else "")
        ref = c.get("ref")
        m = mark(key, ref or "name:" + name, member_key=ref, name=name, status=status,
                 present=present, excused=excused or bool(why))
        m["group"] = c.get("lblGP") or None
        marks.append(m)
    return s, marks


def pt_verify(conn, sittings, marks):
    """How the roll's deputies match the store: {marks, in_roster (the id is a
    pt_members cad_id), name_match (and the printed name is that member's),
    seated (member service: an Efetivo period covers the day), not_seated,
    group_match (member service: the group on the day is the one printed),
    group_differs, no_service}. Read only."""
    out = dict.fromkeys(("marks", "in_roster", "name_match", "seated", "not_seated",
                         "group_match", "group_differs", "no_service"), 0)
    out["examples"] = []
    roster = {}
    if _has(conn, "pt_members"):
        roster = {str(k): n for k, n in conn.execute("SELECT cad_id, name FROM pt_members")}
    periods, groups = {}, {}
    if _has(conn, "ms_periods"):
        for k, start, end in conn.execute("SELECT member_key, start, end FROM ms_periods WHERE "
                                          "cc='pt' AND precision='day'"):
            periods.setdefault(str(k), []).append((start or "", end))
        for k, party, start, end in conn.execute("SELECT member_key, party, start, end FROM "
                                                 "ms_party WHERE cc='pt' AND kind='group'"):
            groups.setdefault(str(k), []).append((start or "", end, party))
    dates = {s["sitting_key"]: s["date"] for s in sittings}
    for m in marks:
        out["marks"] += 1
        k, d = m["member_key"], dates.get(m["sitting_key"]) or ""
        if k and k in roster:
            out["in_roster"] += 1
            if fold_status(roster[k]) == fold_status(m["name"]):
                out["name_match"] += 1
        if not k or k not in periods:
            out["no_service"] += 1
            continue
        if any(a <= d and (not b or d <= b) for a, b in periods[k]):
            out["seated"] += 1
        else:
            out["not_seated"] += 1
            if len(out["examples"]) < 5:
                out["examples"].append("{0} not seated on {1}".format(m["name"], d))
        on = sorted((a, p) for a, b, p in groups.get(k, []) if a <= d and (not b or d <= b))
        if on and m.get("group"):
            if fold_status(on[-1][1]) == fold_status(m["group"]):
                out["group_match"] += 1
            else:
                out["group_differs"] += 1
                if len(out["examples"]) < 5:
                    out["examples"].append("{0} printed {1}, member service {2} on {3}".format(
                        m["name"], m["group"], on[-1][1], d))
    return out


def fold_status(text):
    import unicodedata
    t = unicodedata.normalize("NFD", text or "")
    return "".join(c for c in t if not unicodedata.combining(c)).lower().strip()


# --- the fetchers ---------------------------------------------------------------------------

BR_FILES = "https://dadosabertos.camara.leg.br/arquivos/{0}/{1}/{0}-{2}.{1}"
BR_API = "https://dadosabertos.camara.leg.br/api/v2"
BR_ORGANS = "https://dadosabertos.camara.leg.br/arquivos/orgaos/json/orgaos.json"
FR_AGENDA = ("https://data.assemblee-nationale.fr/static/openData/repository/{0}/vp/reunions/"
             "Agenda.json.zip")
FR_LEGISLATURE = 17
FR_AMO30 = ("https://data.assemblee-nationale.fr/static/openData/repository/{0}/amo/"
            "tous_acteurs_mandats_organes_xi_legislature/"
            "AMO30_tous_acteurs_tous_mandats_tous_organes_historique.json.zip")
CL_WS = "https://opendata.camara.cl/camaradiputados/WServices/"
NL_API = "https://gegevensmagazijn.tweedekamer.nl/OData/v4/2.0/"
NL_TERM_START = "2025-11-12"      # the Tweede Kamer elected 29 October 2025 was sworn in
MAX_REFERRAL_FETCHES = 60         # BR bills on our ground read per run (one request each)


def fetch_br(conn, client, today, log=print, years=None, **_):
    years = years or [today[:4]]
    names = body_names(conn, "br")
    names.update(parse_br_organ_names(client.get_json(BR_ORGANS, FEED, "br-orgaos")))
    sittings, marks = [], []
    for y in years:
        # The presence file is 9 MB of CSV, re-published whole each night: not
        # archived (its URL, by year, is the provenance, as for Holyrood's dumps).
        text = client.get_bytes(BR_FILES.format("eventosPresencaDeputados", "csv", y), FEED,
                                "br-presenca-{0}".format(y), archive=False).decode("utf-8-sig")
        organs = parse_br_event_organs(client.get_json(
            BR_FILES.format("eventosOrgaos", "json", y), FEED, "br-eventos-orgaos-{0}".format(y)))
        events = parse_br_events(client.get_json(
            BR_FILES.format("eventos", "json", y), FEED, "br-eventos-{0}".format(y)))
        s, m = build_br(parse_br_presence(text), organs, events, names)
        sittings += s
        marks += m
    log("  br: {0} sitting(s) with presence registered ({1} plenary), {2} mark(s)".format(
        len(sittings), sum(1 for s in sittings if s["body_kind"] == "plenary"), len(marks)))
    # Referrals: the tramitações of the bills on our ground.
    bills = conn.execute(
        "SELECT bill_key, camara_id FROM br_bills WHERE camara_id IS NOT NULL AND "
        "(tier IS NOT NULL OR (areas IS NOT NULL AND areas NOT IN ('', '[]'))) "
        "ORDER BY bill_key").fetchall() if _has(conn, "br_bills") else []
    refs = []
    for bill_key, cid in bills[:MAX_REFERRAL_FETCHES]:
        refs += parse_br_tramitacoes(bill_key, client.get_json(
            "{0}/proposicoes/{1}/tramitacoes".format(BR_API, cid), FEED,
            "br-tramitacoes-{0}".format(cid)))
    log("  br: {0} referral(s) from {1} bill(s) on our ground".format(
        len(refs), min(len(bills), MAX_REFERRAL_FETCHES)))
    return {"br-presenca": (sittings, marks, refs, "years {0}".format(", ".join(years)))}


def _has(conn, table):
    return bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                             (table,)).fetchone())


def parse_fr_organ_names(raw):
    """({organe uid: libelle}, {organe uid: codeType}) from an AMO zip's
    organe files."""
    z = zipfile.ZipFile(io.BytesIO(raw))
    names, types = {}, {}
    for n in z.namelist():
        if "/organe/" in n and n.endswith(".json"):
            o = json.loads(z.read(n)).get("organe") or {}
            uid = o.get("uid")
            uid = uid.get("#text") if isinstance(uid, dict) else uid
            if uid and o.get("libelle"):
                names[uid] = clean(o["libelle"])
            if uid and o.get("codeType"):
                types[uid] = o["codeType"]
    return names, types


# Sittings stored but never counted: France's friendship groups (GA), whose
# meetings carry a presence list like any committee's but are not committee
# work (member intelligence leaves them out too).
UNCOUNTED_KINDS = ("GA",)


def stored_names(conn, cc):
    return {k: n for k, n in conn.execute("SELECT DISTINCT body_key, body_name FROM att_sittings "
                                          "WHERE cc=? AND body_name IS NOT NULL", (cc,))}


def fetch_fr(conn, client, today, log=print, **_):
    raw = client.get_bytes(FR_AGENDA.format(FR_LEGISLATURE), FEED, "fr-agenda")
    names = stored_names(conn, "fr")
    names.update(body_names(conn, "fr"))
    known = {r[0]: r[1] for r in conn.execute("SELECT body_key, MAX(kind) FROM att_sittings "
                                              "WHERE cc='fr' GROUP BY body_key")}
    types = {k: "GA" for k, kind in known.items() if kind in UNCOUNTED_KINDS}
    sittings, marks = parse_fr_agenda(raw, today, names)
    unnamed = {s["body_key"] for s in sittings if not s["body_name"]} - set(known)
    if unnamed:
        # Organs no sitting deputy belongs to any more (special committees,
        # missions that have ended, friendship groups) are named only in the
        # historical AMO30 file (13.7 MB): read once, and again only when a
        # new one appears.
        more, kinds = parse_fr_organ_names(client.get_bytes(
            FR_AMO30.format(FR_LEGISLATURE), FEED, "fr-amo30", archive=False))
        names.update(more)
        types.update({k: v for k, v in kinds.items() if v in UNCOUNTED_KINDS})
        for s in sittings:
            s["body_name"] = s["body_name"] or names.get(s["body_key"])
        log("  fr: {0} organ(s) named from AMO30".format(len(unnamed)))
    for s in sittings:
        if s["body_key"] in types:
            s["kind"] = types[s["body_key"]]
    refs = referrals_from_sittings(sittings)
    log("  fr: {0} committee meeting(s) with présences, {1} mark(s), {2} referral(s)".format(
        len(sittings), len(marks), len(refs)))
    return {"fr-agenda": (sittings, marks, refs, "Agenda.json.zip, legislature {0}".format(
        FR_LEGISLATURE))}


def fetch_cl(conn, client, today, log=print, years=None, **_):
    years = years or [today[:4]]
    have = stored_keys(conn, "cl", "cl-sala")
    sala_s, sala_m = [], []
    for y in years:
        listed = parse_cl_sessions(client.get_text(
            "{0}WSSala.asmx/retornarSesionesXAnno?prmAnno={1}".format(CL_WS, y), FEED,
            "cl-sesiones-{0}".format(y)))
        for sid, date, held in listed:
            if not held or not date or date > today or "cl-sala-{0}".format(sid) in have:
                continue
            s, m = parse_cl_session(client.get_text(
                "{0}WSSala.asmx/retornarSesionAsistencia?prmSesionId={1}".format(CL_WS, sid), FEED,
                "cl-asistencia-{0}".format(sid)))
            sala_s.append(s)
            sala_m += m
    com_s, com_m = [], []
    committees = parse_cl_committees(client.get_text(
        "{0}WSComision.asmx/retornarComisionesVigentes".format(CL_WS), FEED, "cl-comisiones"))
    for cid, _name in committees:
        for y in years:
            s, m = parse_cl_committee_sessions(client.get_text(
                "{0}WSComision.asmx/retornarSesionesXComisionYAnno?prmComisionId={1}&prmAnno={2}"
                .format(CL_WS, cid, y), FEED, "cl-comision-{0}-{1}".format(cid, y)), today)
            com_s += s
            com_m += m
    log("  cl: {0} new plenary session(s), {1} committee session(s) of {2} committee(s)".format(
        len(sala_s), len(com_s), len(committees)))
    return {"cl-sala": (sala_s, sala_m, None, None),
            "cl-comisiones": (com_s, com_m, None, "{0} committee(s)".format(len(committees)))}


def fetch_nl(conn, client, today, log=print, **_):
    keep = member_keys(conn, "SELECT persoon_id FROM nl_members")
    soorts = " or ".join("Soort eq '{0}'".format(k) for k in NL_KINDS)
    flt = ("Verwijderd eq false and Status eq 'Uitgevoerd' and Datum ge {0}T00:00:00Z and "
           "({1})".format(NL_TERM_START, soorts))
    expand = ("ActiviteitActor($filter=Verwijderd eq false;$select=ActorNaam,Relatie,Functie,"
              "Persoon_Id),Zaak($select=Nummer;$expand=Kamerstukdossier("
              "$select=Nummer))")
    url = "{0}Activiteit?$filter={1}&$select=Id,Soort,Onderwerp,Datum,Voortouwcommissie_Id,Voortouwnaam&$expand={2}".format(
        NL_API, quote(flt, safe="'()"), quote(expand, safe="(),;=$"))
    rows, n = [], 0
    while url:
        got = client.get_json(url, FEED, "nl-activiteiten-{0}".format(n))
        rows += got.get("value") or []
        url = got.get("@odata.nextLink")
        n += 1
    sittings, marks = parse_nl_activities(rows)
    if keep is not None:
        marks = [m for m in marks if m["member_ref"] in keep]
    refs = referrals_from_sittings(sittings)
    log("  nl: {0} committee debate(s) this term, {1} participation(s), {2} referral(s)".format(
        len(sittings), len(marks), len(refs)))
    return {"nl-activiteiten": (sittings, marks, refs, "since {0}".format(NL_TERM_START))}


def fetch_co(conn, client, today, log=print, **_):
    sittings, marks = co_rows(conn)
    log("  co: {0} plenary sitting(s), {1} mark(s) from co_attendance".format(len(sittings),
                                                                              len(marks)))
    return {"co-asistencia": (sittings, marks, None, "from co_attendance (datos.gov.co 48i3-vuny)")}


PT_SITE = "https://www.parlamento.pt"
PT_INDEX = PT_SITE + "/DeputadoGP/Paginas/reunioesplenarias.aspx"
PT_DETAIL = PT_SITE + "/DeputadoGP/Paginas/DetalheReuniaoPlenaria.aspx?BID={0}"
PT_MAX_SITTINGS = 40      # roll pages read per run (about 800 KB of HTML each, 1-3 s)
PT_REREAD_DAYS = 21       # a sitting this recent is read again: a Falta is justified later
PT_MAX_PAGES = 12         # index pages walked (20 sittings each; the XVII had 6 on 11 October)


def fetch_pt(conn, client, today, log=print, budget=None, max_sittings=None, **_):
    """The XVII legislature's plenary rolls: the index's newest page every run,
    further pages (by postback) while sittings listed there are not stored,
    then each unstored sitting's roll, newest first, and the sittings of the
    last three weeks again; at most `max_sittings` rolls (PT_MAX_SITTINGS) and
    `budget` seconds. The first run backfills part of the legislature; each
    run after takes the next block until every listed sitting is stored."""
    import time
    deadline = time.monotonic() + budget if budget else None
    cap = PT_MAX_SITTINGS if max_sittings is None else int(max_sittings)
    have = dict(conn.execute("SELECT sitting_key, date FROM att_sittings WHERE cc='pt' AND "
                             "source='pt-plenario'").fetchall())
    recent = (datetime.date.fromisoformat(today) -
              datetime.timedelta(days=PT_REREAD_DAYS)).isoformat()
    page = client.get_text(PT_INDEX, FEED, "pt-reunioes-1", archive=False)
    rows, pages, total = parse_pt_index(page)
    if not rows:
        raise ValueError("the plenary sittings index lists no sitting")
    n = 1
    while n < PT_MAX_PAGES and (n + 1) in pages:
        new = [r for r in rows if "pt-rp-" + r["bid"] not in have]
        if len(new) >= cap or (deadline and time.monotonic() > deadline):
            break                         # enough for this run
        if total is not None and len(have) + len(new) >= total:
            break                         # every listed sitting is stored or in hand
        page = client.post_form(PT_INDEX, pt_form(page, pages[n + 1]), FEED,
                                "pt-reunioes-{0}".format(n + 1))
        got, pages, _t = parse_pt_index(page)
        if not got:
            break
        rows += [r for r in got if r["bid"] not in {x["bid"] for x in rows}]
        n += 1
    listed = [r for r in rows if r["date"] and r["date"] <= today]
    todo = [r for r in listed if "pt-rp-" + r["bid"] not in have]
    todo += [r for r in listed if "pt-rp-" + r["bid"] in have and r["date"] >= recent]
    sittings, marks, empty, read = [], [], [], 0
    for r in todo:
        if read >= cap or (deadline and time.monotonic() > deadline):
            break
        text = client.get_text(PT_DETAIL.format(r["bid"]), FEED, "pt-reuniao-" + r["bid"])
        read += 1
        s, m = parse_pt_sitting(text, r["bid"], r)
        if not m:
            empty.append(r["bid"])        # no roll published yet: read again next run
            continue
        sittings.append(s)
        marks += m
    stored = len(set(have) | {s["sitting_key"] for s in sittings})
    left = max(0, (total or len(listed)) - stored)
    check = pt_verify(conn, sittings, marks)
    log("  pt: {0} index page(s), {1} sitting(s) listed; {2} roll(s) read, {3} mark(s); "
        "{4} of the legislature's sittings stored, {5} left for later runs{6}".format(
            n, total if total is not None else len(listed), len(sittings), len(marks), stored,
            left, "; no roll yet: " + ", ".join(empty) if empty else ""))
    if check["marks"]:
        log("  pt: deputies matched to pt_members {in_roster}/{marks} (names {name_match}); "
            "member service: seated on the day {seated}, not seated {not_seated}, "
            "group as printed {group_match}, differs {group_differs}, no service rows "
            "{no_service}".format(**check))
        for e in check["examples"]:
            log("    " + e)
    note = "XVII legislature, {0} of {1} listed sittings stored{2}".format(
        stored, total if total is not None else len(listed),
        "; {0} left for later runs".format(left) if left else "")
    return {"pt-plenario": (sittings, marks, None, note)}


FETCHERS = {"br": fetch_br, "fr": fetch_fr, "cl": fetch_cl, "nl": fetch_nl, "co": fetch_co,
            "pt": fetch_pt}
COUNTRIES = tuple(FETCHERS)


def collect(conn, client, cc, today, log=print, years=None, budget=None, max_sittings=None):
    """Fetch one country's sources and store them. Returns {source: (sittings,
    marks)}. A fetch error propagates: nothing of this country is written.
    `budget` (seconds) and `max_sittings` (additive, 11 October 2026) bound a
    source read a page per sitting (PT); the others ignore them."""
    ensure(conn)
    got = FETCHERS[cc](conn, client, today, log=log, years=years, budget=budget,
                       max_sittings=max_sittings)
    done = {}
    for source, (sittings, marks, refs, note) in got.items():
        done[source] = store(conn, cc, source, today, sittings, marks, refs, note)
    return done


# --- what the profiles and packs read ---------------------------------------------------------

def _memberships(conn, cc):
    """{(member_key, body_key): (start, end, role, substitute)} from member
    intelligence."""
    out = {}
    try:
        rows = conn.execute("SELECT member_key, group_key, start, end, role FROM mi_groups WHERE cc=? "
                            "AND kind IN ('committee', 'inquiry') AND member_key IS NOT NULL",
                            (cc,)).fetchall()
    except sqlite3.Error:
        return out
    for mk, gk, start, end, role in rows:
        k = (str(mk), str(gk))
        old = out.get(k)
        sub = is_substitute(role)
        # A full seat wins over a substitute's; then the earliest start.
        if old is None or (old[3] and not sub) or (old[3] == sub and
                                                    (start or "") < (old[0] or "9999")):
            out[k] = (start, end, clean(role) or None, sub)
    return out


def is_substitute(role):
    r = fold_status(role)
    return any(w in r for w in ("suplente", "plv.", "plaatsvervangend", "supplean", "reemplazo"))


def summaries(conn, cc, since=None):
    """{member key: [row]}, one row per body the member has a record in:
    {body_kind, body_key, body_name, roll, attended, of, excused, absent,
    first, last, since, basis, name}. `since` (ISO) limits the sittings."""
    if not has_tables(conn):
        return {}
    sit = {}
    for key, kind, bkey, bname, date, roll in conn.execute(
            "SELECT sitting_key, body_kind, body_key, body_name, date, roll FROM att_sittings "
            "WHERE cc=? AND (? IS NULL OR date >= ?) AND COALESCE(kind, '') NOT IN ({0})".format(
                ",".join("?" * len(UNCOUNTED_KINDS))), (cc, since, since) + UNCOUNTED_KINDS):
        sit[key] = (kind, bkey, bname, date, roll)
    if not sit:
        return {}
    by_body = {}
    for key, (kind, bkey, bname, date, roll) in sit.items():
        by_body.setdefault(bkey, []).append((date or "", key))
    names = {}
    for bkey in by_body:
        by_body[bkey].sort()
    marks = {}
    for key, mk, ref, name, present, excused in conn.execute(
            "SELECT sitting_key, member_key, member_ref, name, present, excused FROM att_marks "
            "WHERE cc=?", (cc,)):
        if key not in sit:
            continue
        who = str(mk or ref)
        names.setdefault(who, name)
        marks.setdefault(who, {})[key] = (present, excused)
    member_of = _memberships(conn, cc)
    first_seen = {who: min((sit[k][3] or "9999") for k in ks) for who, ks in marks.items()}
    out = {}
    bodies = {bkey: (sit[ks[0][1]][0], sit[ks[0][1]][2], sit[ks[0][1]][4])
              for bkey, ks in by_body.items()}
    # Bodies whose roll lists only those present (or who took part): the
    # sittings counted are the body's sittings while the member sat on it.
    # A member has a row for every body they have a mark in; for a register of
    # who was present, also for every body they sit on (member intelligence)
    # and for the plenary once they have any recorded presence.
    open_plenaries = [b for b, (kind, _n, roll) in bodies.items()
                      if kind == "plenary" and roll != "roll"]
    wanted = set()
    for who, ks in marks.items():
        wanted.update((who, sit[k][1]) for k in ks)
        wanted.update((who, b) for b in open_plenaries)
    wanted.update(k for k in member_of if k[1] in bodies and bodies[k[1]][2] != "roll")
    for who, bkey in wanted:
        kind, bname, roll = bodies[bkey]
        mine = marks.get(who) or {}
        start = end = role = None
        sub = False
        basis_since = None
        if roll == "roll":
            counted = [k for _d, k in by_body[bkey] if k in mine]
        else:
            if kind == "plenary":
                start = first_seen.get(who)
                basis_since = "first_presence"
            elif (who, bkey) in member_of:
                start, end, role, sub = member_of[(who, bkey)]
                basis_since = "joined"
            else:
                basis_since = "not_member"
            counted = [k for d, k in by_body[bkey]
                       if (not start or d >= start) and (not end or d <= end)]
            if basis_since == "not_member":
                counted = [k for _d, k in by_body[bkey] if k in mine]
        if not counted:
            continue
        attended = sum(1 for k in counted if (mine.get(k) or (None,))[0] == 1)
        excused = sum(1 for k in counted if k in mine and mine[k][0] == 0 and mine[k][1])
        absent = sum(1 for k in counted if (k not in mine) or (mine[k][0] == 0 and not mine[k][1]))
        dates = [sit[k][3] for k in counted if sit[k][3]]
        out.setdefault(who, []).append({
            "body_kind": kind, "body_key": bkey, "body_name": bname or bkey, "roll": roll,
            "attended": attended, "of": len(counted), "excused": excused, "absent": absent,
            "first": min(dates) if dates else None, "last": max(dates) if dates else None,
            "since": start, "since_basis": basis_since, "name": names.get(who),
            "member": basis_since != "not_member", "role": role, "substitute": sub})
    for rows in out.values():
        rows.sort(key=lambda r: (r["body_kind"] != "plenary", -(r["of"]), r["body_name"]))
    return out


def bill_sittings(conn, cc, bill_keys):
    """{body_key: [sitting_key]} of the sittings whose agenda names one of the
    bill keys."""
    if not has_tables(conn):
        return {}
    keys = {str(k) for k in bill_keys if k}
    out = {}
    for skey, bkey, raw in conn.execute("SELECT sitting_key, body_key, bill_keys FROM att_sittings "
                                        "WHERE cc=? AND bill_keys NOT IN ('', '[]')", (cc,)):
        try:
            got = set(json.loads(raw or "[]"))
        except ValueError:
            continue
        if got & keys:
            out.setdefault(bkey, []).append(skey)
    return out


def referrals_for(conn, cc, bill_keys):
    """[{body_key, body_name, first_date, last_date, sittings}] for the
    committees that handled a bill, only those with attendance stored."""
    if not has_tables(conn):
        return []
    keys = [str(k) for k in bill_keys if k]
    if not keys:
        return []
    rows = conn.execute(
        "SELECT r.body_key, COALESCE(MAX(s.body_name), r.body_name), MIN(r.first_date), "
        "MAX(r.last_date), MAX(r.sittings) FROM att_referrals r JOIN att_sittings s "
        "ON s.cc = r.cc AND s.body_key = r.body_key WHERE r.cc=? AND r.bill_key IN ({0}) "
        "GROUP BY r.body_key ORDER BY MIN(r.first_date)".format(",".join("?" * len(keys))),
        [cc] + keys).fetchall()
    return [{"body_key": r[0], "body_name": r[1] or r[0], "first_date": r[2],
             "last_date": r[3], "sittings": r[4]} for r in rows]


def on_bill(conn, cc, sitting_keys):
    """{member key: (attended, of)} over the given sittings (roll sources:
    the members listed; present / participant sources: those who were)."""
    if not sitting_keys or not has_tables(conn):
        return {}
    out = {}
    q = ",".join("?" * len(sitting_keys))
    for mk, ref, present in conn.execute(
            "SELECT member_key, member_ref, present FROM att_marks WHERE cc=? AND sitting_key IN "
            "({0})".format(q), [cc] + list(sitting_keys)):
        who = str(mk or ref)
        a, n = out.get(who, (0, 0))
        out[who] = (a + (1 if present == 1 else 0), n + 1)
    return out


def sources_line(conn, cc):
    if not has_tables(conn):
        return None
    got = conn.execute("SELECT source, last_seen, sittings, marks, note FROM att_runs WHERE cc=? "
                       "ORDER BY source", (cc,)).fetchall()
    return "; ".join("{0} read {1}".format(s, r) + (" ({0})".format(n) if n else "")
                     for s, r, _si, _m, n in got) or None


def basis(row):
    """The plain words for how a row was counted."""
    words = ROLL_WORDS.get(row["roll"], row["roll"])
    if row.get("since_basis") == "first_presence":
        words += "; counted from their first recorded presence"
    elif row.get("since_basis") == "not_member":
        words += "; not listed as a member, so only the sittings attended are known"
    return words


def row_text(row):
    """'attended 12 of 15 sitting(s) (2 excused or with a reason given), 2026-03-03 to
    2026-10-08'. A reason is the record's own (France's 'excusé', Chile's
    justification, verbatim in att_marks.status)."""
    verb = "took part in" if row["roll"] == "participants" else (
        "present at" if row["body_kind"] == "plenary" else "attended")
    what = "debate(s)" if row["roll"] == "participants" else "sitting(s)"
    if row.get("since_basis") == "not_member":
        text = "{0} {1} {2} (not a member)".format(verb, row["attended"], what)
    else:
        text = "{0} {1} of {2} {3}".format(verb, row["attended"], row["of"], what)
        if row.get("excused"):
            text += " ({0} excused or with a reason given)".format(row["excused"])
        if row.get("substitute"):
            text += " as a substitute ({0})".format(row.get("role") or "substitute")
    if row.get("first"):
        text += ", {0} to {1}".format(row["first"], row["last"])
    return text


# --- plenary vote participation, derived from the stored votes ---------------------------------

# For each country whose vote records list the members who did not vote:
# the SQL (member key, member name, position, date) and what each non-voting
# position is. Anything else recorded is a vote cast; OTHER (presiding) is
# left out of the count.
ABSENT, EXCUSED, PRESENT, OTHER = "absent", "excused", "present", "other"

VOTE_RECORDS = {
    "it": ("SELECT v.member_key, m.name, v.position, d.date FROM it_votes v JOIN it_divisions d "
           "USING (division_key) LEFT JOIN it_members m USING (member_key)",
           {"absent": ABSENT, "mission": EXCUSED, "present": PRESENT},
           "the Camera's and the Senate's records list 'assente', 'in missione' and 'presente "
           "non votante'"),
    "ch": ("SELECT v.person_number, TRIM(COALESCE(m.first_name,'') || ' ' || "
           "COALESCE(m.last_name,'')), v.position, d.date FROM ch_votes v JOIN ch_divisions d "
           "USING (division_key) LEFT JOIN ch_members m USING (person_number)",
           {"nicht teilgenommen": ABSENT, "entschuldigt": EXCUSED, "prasident": OTHER,
            "anwesend": PRESENT},
           "the Federal Assembly's records list 'Nicht teilgenommen' and 'Entschuldigt'"),
    "pl": ("SELECT v.mp_key, m.name, v.position, substr(d.voted_at, 1, 10) FROM pl_votes v "
           "JOIN pl_divisions d USING (division_key) LEFT JOIN pl_members m USING (mp_key)",
           {"absent": ABSENT, "present": PRESENT},
           "the Sejm's records list ABSENT and PRESENT (present, not voting)"),
    "es": ("SELECT v.name, v.name, v.position, d.date FROM es_votes v JOIN es_divisions d "
           "USING (division_key)",
           {"no vota": ABSENT},
           "the Congreso's records list 'No vota' (did not vote, present or not)"),
    "ar": ("SELECT v.member_key, m.name, v.position, d.date FROM ar_votes v JOIN ar_divisions d "
           "USING (division_key) LEFT JOIN ar_members m USING (member_key)",
           {"ausente": ABSENT},
           "the Senate's records list AUSENTE"),
    "pe": ("SELECT COALESCE(v.member_key, v.name_raw), COALESCE(m.name, v.name_raw), v.position, "
           "d.date FROM pe_votes v JOIN pe_divisions d USING (division_key) LEFT JOIN pe_members m "
           "USING (member_key)",
           {"aus": ABSENT, "le": EXCUSED, "lo": EXCUSED, "lp": EXCUSED, "lv": EXCUSED,
            "pres": OTHER, "sr": PRESENT},
           "the Congress's records list AUS (absent), the licences (LE, LO, LP, LV) and SR "
           "(no answer)"),
    "do": ("SELECT COALESCE(v.member_key, v.name), COALESCE(m.name, v.name), v.position, d.date "
           "FROM do_votes v JOIN do_divisions d USING (division_key) LEFT JOIN do_members m "
           "USING (member_key)",
           {"au": ABSENT, "sv": PRESENT},
           "the Chamber's records list AU (absent for this vote) and SV (present, no vote)"),
    "hu": ("SELECT v.member_id, v.name, v.position, d.date FROM hu_votes v JOIN hu_divisions d "
           "USING (vote_ts)",
           {"nem_szavazott": ABSENT, "bejelentett_hianyzo": EXCUSED, "igazoltan_tavol": EXCUSED,
            "jelen_nem_szavazott": PRESENT},
           "the karzat records list 'nem szavazott', announced and excused absences, and "
           "'jelen, nem szavazott'"),
}

PARTICIPATION_DAYS = 365


def participation(conn, cc, today=None, days=PARTICIPATION_DAYS):
    """{member key: {name, cast, absent, excused, present, of, first, last}}
    over the `days` to the newest stored vote, and the basis line; ({}, None)
    for a country whose records do not list absences."""
    spec = VOTE_RECORDS.get(cc)
    if spec is None:
        return {}, None
    sql, codes, words = spec
    table = {"pl": "pl_divisions"}.get(cc, "{0}_divisions".format(cc))
    col = "substr(voted_at, 1, 10)" if cc == "pl" else "date"
    try:
        newest = conn.execute("SELECT MAX({0}) FROM {1}".format(col, table)).fetchone()[0]
        rows = conn.execute(sql)
    except sqlite3.Error:
        return {}, None
    if not newest:
        return {}, None
    newest = str(newest)[:10]
    if today:
        newest = min(newest, today)
    since = (datetime.date.fromisoformat(newest) - datetime.timedelta(days=days)).isoformat()
    out = {}
    folded = {fold_status(k): v for k, v in codes.items()}
    for key, name, position, date in rows:
        d = str(date or "")[:10]
        if not key or not d or d < since or d > newest:
            continue
        what = folded.get(fold_status(position))
        if what == OTHER:
            continue
        r = out.setdefault(str(key), {"name": name, "cast": 0, ABSENT: 0, EXCUSED: 0, PRESENT: 0,
                                      "of": 0, "first": d, "last": d})
        r["of"] += 1
        r[what or "cast"] += 1
        r["first"], r["last"] = min(r["first"], d), max(r["last"], d)
    basis_line = ("from the stored vote records, which list the members who did not vote "
                  "({0}); the {1} days to {2}".format(words, days, newest))
    return out, basis_line


def participation_text(r):
    """'cast a vote in 412 of 450 recorded votes (30 absent, 8 excused)'."""
    bits = []
    for k, w in ((ABSENT, "absent"), (EXCUSED, "excused or on leave"),
                 (PRESENT, "present, not voting")):
        if r.get(k):
            bits.append("{0} {1}".format(r[k], w))
    return "cast a vote in {0} of {1} recorded vote(s){2}".format(
        r["cast"], r["of"], " ({0})".format(", ".join(bits)) if bits else "")
