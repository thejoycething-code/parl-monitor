"""The Italian Senate's amendment texts: parsing, the vote-wording numbers,
the link from a vote to its text, and the lookups the readers use
(12 October 2026, Chris: "Yes, build it").

The collector is tools/it_senato_amendments.py; the tables are in
src/it_store.py (`it_senate_amendments`, `it_senate_amendment_votes`,
`it_senate_amend_acts`). Everything here is pure or reads the store: no
network.

THE SOURCE. The Senate publishes every amendment and order of the day as
one Akoma Ntoso XML file in its GitHub repository
SenatoDellaRepubblica/AkomaNtosoBulkData, under Leg<n>/Atto<idFase>/emend
(Assembly) and emendc (committee). In each file:
  * FRBRWork/FRBRnumber is the number the vote wording uses ("1.23",
    "2.0.2", "G1.104", "QP1");
  * FRBRWork/FRBRname is the type ("Emendamento", "Ordine del giorno");
  * FRBRWork/FRBRthis carries the act and the sede:
    http://dati.senato.it/19/Emend/S/1735/A/1.23/main ('A' Assembly,
    'C' committee);
  * preface/docProponent are the proposers, as printed;
  * amendmentBody is the operative text.
Downloaded content is DATA: it is parsed with ElementTree into strings and
stored; nothing in it is ever executed or followed.

THE LINK. A Senate vote's wording names the amendment(s) put: "Em. 1.23,
D'Elia e altri", "Emm. 3.1 e 3.2", "ODG G1.1, ...", "Em. 7.0.100/151, ...",
"Em. 1.5 (testo 2), ...". `vote_numbers` reads the numbers and the split
part ("Em. 1.23 (1a parte)"). `link` matches each number to an ASSEMBLY
text of one of the acts the vote names (it_divisions.bill_key and
bill_keys: a joint examination files its amendments under the base text,
S.824 for the surrogacy bill voted as S.163 and others). A split vote is
linked to the whole text and FLAGGED ('split'): which words the part was
is never guessed.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import re
import sqlite3
import xml.etree.ElementTree as ET

REPO = "SenatoDellaRepubblica/AkomaNtosoBulkData"
BRANCH = "master"
BLOB_URL = "https://github.com/{0}/blob/{1}/{{path}}".format(REPO, BRANCH)
RAW_URL = "https://raw.githubusercontent.com/{0}/{1}/{{path}}".format(REPO, BRANCH)
TREE_URL = "https://api.github.com/repos/{0}/git/trees/{1}:{{folder}}?recursive=1".format(REPO, BRANCH)
FOLDERS = {"emend": "A", "emendc": "C"}
TEXT_CHARS = 20000          # one amendment's stored text, at most

_AKN = "{http://docs.oasis-open.org/legaldocml/ns/akn/3.0/CSD03}"


def act_folder(leg, id_fase):
    """'Leg19/Atto00059761' for legislature 19, idFase 59761."""
    return "Leg{0}/Atto{1:08d}".format(int(leg), int(id_fase))


def git_blob_sha(raw):
    """The git blob sha1 of `raw` bytes: what the tree lists for the file."""
    return hashlib.sha1(b"blob %d\0" % len(raw) + raw).hexdigest()


def norm(number):
    """The join key for an amendment number: spaces and case folded,
    "(testo 2)" -> "t2". '1.5 (testo 2)' and '1.5(Testo 2)' -> '1.5t2'."""
    s = re.sub(r"\s+", "", str(number or "")).lower()
    s = re.sub(r"\(?testo(\d+)\)?", r"t\1", s)
    return s.strip(".,;")


def _local(tag):
    return tag.rsplit("}", 1)[-1]


def _find(root, name):
    for el in root.iter():
        if _local(el.tag) == name:
            return el
    return None


def _text_of(el):
    return " ".join("".join(el.itertext()).split())


def parse_akn(raw):
    """One amendment file (bytes or str) -> dict, or None when it is not an
    Akoma Ntoso amendment. Keys: number, kind, act ('19/S.1735'), legislature,
    sede ('A'/'C'), frbr_uri, presented, proposers [names], text."""
    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return None
    work = _find(root, "FRBRWork")
    if work is None:
        return None
    vals = {}
    for el in work:
        name = _local(el.tag)
        if name in ("FRBRthis", "FRBRuri", "FRBRnumber", "FRBRname", "FRBRsubtype"):
            vals[name] = el.get("value")
        elif name == "FRBRdate" and el.get("name") == "presentazione":
            vals["date"] = el.get("date")
    uri = vals.get("FRBRuri") or re.sub(r"/main$", "", vals.get("FRBRthis") or "")
    m = re.match(r"^https?://dati\.senato\.it/(\d+)/Emend/([SC])/([^/]+)/([AC])/(.+?)/?$", uri or "")
    leg = act = sede = None
    if m:
        leg = int(m.group(1))
        act = "{0}/{1}.{2}".format(leg, m.group(2), m.group(3))
        sede = m.group(4)
    proposers = []
    for el in root.iter():
        if _local(el.tag) == "docProponent":
            name = _text_of(el)
            if name and name not in proposers:
                proposers.append(name)
    body = _find(root, "amendmentBody")
    paras = []
    if body is not None:
        for el in body.iter():
            if _local(el.tag) == "p":
                t = _text_of(el)
                if t:
                    paras.append(t)
        if not paras:
            t = _text_of(body)
            if t:
                paras.append(t)
    number = (vals.get("FRBRnumber") or (m.group(5) if m else "") or "").strip()
    if not number:
        return None
    return {"number": number, "kind": (vals.get("FRBRname") or "").strip() or None,
            "act": act, "legislature": leg, "sede": sede, "frbr_uri": uri or None,
            "presented": vals.get("date"), "proposers": proposers,
            "text": "\n".join(paras)[:TEXT_CHARS] or None}


def is_empty_akn(raw):
    """True for a well-formed Akoma Ntoso document with nothing in it (the
    Senate publishes the odd one: a bare <akomaNtoso/> root)."""
    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return False
    return _local(root.tag) == "akomaNtoso" and len(root) == 0 and not (root.text or "").strip()


# --- the numbers in a vote's wording -------------------------------------------------

_PREFIX = re.compile(r"^\s*(?:emm?\.|emendament[oi]|odg|ordin[ei] del giorno|em)\s*", re.I)
_NUMBER = re.compile(r"(?<![\w.])((?:G|QP)?\d+(?:-[a-z]+)?(?:\.\d+(?:-[a-z]+)?)+(?:/\d+)?|G\d+|QP\d+)"
                     r"(\s*\(\s*testo\s*\d+\s*\))?", re.I)
_PART = re.compile(r"\(\s*(\d+)\s*[a°ª]\s*parte\s*\)", re.I)


def vote_numbers(title):
    """(numbers, part) for a Senate vote's wording: (['3.1', '3.2'], None)
    for "Emm. 3.1 e 3.2", (['1.23'], '1a parte') for "Em. 1.23 (1a parte) ,
    D'Elia e altri", (['1.5 (testo 2)'], None) for "Em. 1.5 (testo 2), ...".
    ([], None) for a wording that names no amendment ("Articolo 3",
    "Votazione finale", "Votazione questione pregiudiziale")."""
    t = " ".join(str(title or "").split())
    if not _PREFIX.match(t):
        return [], None
    rest = _PREFIX.sub("", t, count=1)
    part = None
    pm = _PART.search(rest)
    if pm:
        part = "{0}a parte".format(pm.group(1))
        rest = rest[:pm.start()] + rest[pm.end():]
    # the numbers come before the proposers: cut at the first ", <Name>"
    m = re.search(r",\s*(?=[A-Z][a-z'])|,\s*(?=Il Relatore|La Relatrice|Il Governo)", rest)
    head = rest[:m.start()] if m else rest
    nums = []
    for n in _NUMBER.finditer(head):
        num = n.group(1) + (" (testo {0})".format(re.search(r"\d+", n.group(2)).group(0)) if n.group(2) else "")
        if num not in nums:
            nums.append(num)
    return nums, part


# --- the link ---------------------------------------------------------------------

def _rows(conn, sql, params=()):
    try:
        cur = conn.execute(sql, params)
    except sqlite3.Error:
        return []
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def senate_acts(row):
    """The Senate acts a division names: bill_key first, then bill_keys."""
    keys = []
    try:
        extra = json.loads(row.get("bill_keys") or "[]")
    except (TypeError, ValueError):
        extra = []
    for k in [row.get("bill_key")] + list(extra or []):
        if k and re.match(r"^\d+/S\.", str(k)) and k not in keys:
            keys.append(k)
    return keys


def link_division(conn, row, read_acts, today=None):
    """[(number, part, status, act, file_path)] for one Senate division row
    (division_key, title, bill_key, bill_keys). `read_acts` is the set of
    acts whose folders have been read."""
    nums, part = vote_numbers(row.get("title"))
    acts = senate_acts(row)
    out = []
    for num in nums:
        hits = []
        for act in acts:
            hits += [(act, r["file_path"]) for r in _rows(
                conn, "SELECT file_path FROM it_senate_amendments WHERE act=? AND sede='A' "
                      "AND number_norm=?", (act, norm(num)))]
        if len(hits) == 1:
            status = "split" if part else "linked"
            out.append((num, part, status, hits[0][0], hits[0][1]))
        elif len(hits) > 1:
            out.append((num, part, "ambiguous", None, None))
        elif acts and all(a in read_acts for a in acts):
            out.append((num, part, "not_found", None, None))
        else:
            out.append((num, part, "not_read", None, None))
    return out


def link(conn, divisions, today=None):
    """Link every Senate division in `divisions` (rows with division_key,
    title, bill_key, bill_keys) to its texts, replacing earlier links of
    those divisions. Returns {status: count}."""
    today = today or datetime.date.today().isoformat()
    read_acts = {r["act"] for r in _rows(conn, "SELECT act FROM it_senate_amend_acts WHERE checked IS NOT NULL")}
    counts = {}
    for row in divisions:
        got = link_division(conn, row, read_acts, today)
        conn.execute("DELETE FROM it_senate_amendment_votes WHERE division_key=?", (row["division_key"],))
        for num, part, status, act, path in got:
            conn.execute("INSERT OR REPLACE INTO it_senate_amendment_votes (division_key, number, part, "
                         "status, act, file_path, linked_on) VALUES (?,?,?,?,?,?,?)",
                         (row["division_key"], num, part, status, act, path, today))
            counts[status] = counts.get(status, 0) + 1
    conn.commit()
    return counts


# --- what the readers use ------------------------------------------------------------

def texts_for(conn, division_key):
    """[{number, part, status, act, kind, proposers, text, url, presented}]
    for one Senate division, from the store; [] when nothing is linked or the
    tables are missing (an older store). `status` is linked / split /
    not_found / ambiguous / not_read; text and url only when linked or split."""
    if conn is None or not str(division_key).startswith("senato-"):
        return []
    rows = _rows(conn, "SELECT v.number, v.part, v.status, v.act, a.kind, a.proposers, a.text, a.url, "
                       "a.presented, a.file_path FROM it_senate_amendment_votes v LEFT JOIN "
                       "it_senate_amendments a ON a.file_path = v.file_path WHERE v.division_key=?",
                 (str(division_key),))
    out = []
    for r in rows:
        try:
            r["proposers"] = json.loads(r.get("proposers") or "[]")
        except (TypeError, ValueError):
            r["proposers"] = []
        out.append(r)
    nums, _ = vote_numbers(_title(conn, division_key))
    order = {n: i for i, n in enumerate(nums)}
    out.sort(key=lambda r: order.get(r["number"], 99))
    return out


def _title(conn, division_key):
    got = _rows(conn, "SELECT title FROM it_divisions WHERE division_key=?", (str(division_key),))
    return got[0]["title"] if got else ""


def has_text(texts):
    """True when every number of the vote has its text (linked or split)."""
    return bool(texts) and all(t["status"] in ("linked", "split") and t.get("text") for t in texts)


def is_split(texts):
    return any(t["status"] == "split" for t in texts)


def summary_line(texts, chars=300):
    """One line for a reader: 'Em. 1.23 (D'ELIA, CRISANTI ...): <text...>
    [url]', each number; plus the split warning."""
    bits = []
    for t in texts:
        if t["status"] not in ("linked", "split") or not t.get("text"):
            continue
        who = ", ".join(t["proposers"][:3]) + (" and others" if len(t["proposers"]) > 3 else "")
        text = " ".join(t["text"].split())
        if len(text) > chars:
            text = text[:chars - 3].rstrip() + "..."
        bits.append("{0} {1}{2}: {3} [{4}]".format(
            "ODG" if (t.get("kind") or "").lower().startswith("ordine") else "Em.", t["number"],
            " ({0})".format(who) if who else "", text, t.get("url") or ""))
    line = " | ".join(bits)
    if is_split(texts):
        part = next(t["part"] for t in texts if t["status"] == "split")
        line += (" | SPLIT VOTE: only the {0} was put; the record does not say which words that part "
                 "was, so the whole text is shown and the part is not guessed.".format(part))
    return line
