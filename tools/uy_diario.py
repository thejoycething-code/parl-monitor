#!/usr/bin/env python3
"""Uruguay: vote totals from the Cámara's Diario de Sesiones PDFs (UY5).

    python3 tools/uy_diario.py                  # the weekly read: up to 4 new Diarios
    python3 tools/uy_diario.py --max 100        # the L legislature's backlog (Mini)
    python3 tools/uy_diario.py --file d4578.pdf --diario 4578   # one PDF, offline
    python3 tools/uy_diario.py --reclassify
    python3 tools/uy_diario.py --db /tmp/uy.db

Chris, 10 October 2026: "Uruguay: build vote totals from the Diario PDFs
now (UY5)". docs/uruguay-scope.md, finding 2: Uruguay records no names.
Both chambers vote by show of hands or an anonymous electronic register,
and the Diario prints only the count. So a row here is ONE VOTE'S TOTAL,
never a member's position, and nothing here can feed a 5CA.

THE SOURCE. The Cámara's own JSON index of Diarios (DAdiarioSesiones.json on
documentos.diputados.gub.uy, read weekly by tools/uy_rollcalls.py into
uy_sittings) links each Diario's PDF on www.diputados.gub.uy (http only:
its https certificate does not name it). The PDFs carry a text layer that
pypdf reads (Diario 4578, the euthanasia sitting: 272 pages, 6.2 MB).
parlamento.gub.uy is NOT read: it refuses us (403) and is not tried.

WHAT IS READ. The Diario is a run of numbered sections ("43.- Muerte digna
(Regulación)"); each vote ends in a line of number WORDS:

    ——Setenta y cuatro en setenta y cinco: AFIRMATIVA.              (hands)
    ——Sesenta y cuatro votos afirmativos y veintinueve votos negativos
      en noventa y tres presentes: AFIRMATIVA.                      (register)

Each result is stored with the section it closes, the sentence that put the
question ("se abre el registro para proceder a la votación n.º 7,
correspondiente al aditivo contenido en la Hoja n.º 3"), the counts, and the
result word verbatim. A show of hands prints the ayes and those present
only; `no` stays NULL rather than being inferred (present minus ayes counts
abstainers, who do not exist in this Chamber, and the Presidency, which
does not always vote). The section TITLE is classified (taxonomy-es for
`uy`): it is the bill's own name, while the speeches in the section cite
everything.

TIMING. The index lags the sittings by months (the newest Diario listed on
8 October 2026 was of 14 July). These totals are for the record, not for
alerts; the Latam edition shows a Diario's votes when it is first read and
the sitting was in the last 200 days.

COST. Up to MAX_READ (4) Diarios a week, newest first, the L legislature
only unless --all: one PDF each, 2 to 7 MB, two seconds apart. Pages are
not archived (the URL is the provenance; the table keeps what was read).
ONE WRITER AT A TIME on data/parl-monitor.db. Exit 3: stored what it could
and recorded gaps.
"""

from __future__ import annotations

import argparse
import datetime
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import courts, db  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402

FEED = "uy-diario"
CC = "uy"
CHAMBER = "representantes"
MAX_READ = 4
QUESTION_CHARS = 300

# --- Spanish number words ------------------------------------------------------------

UNITS = {"cero": 0, "un": 1, "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cuarto": 4, "cinco": 5,
         "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10, "once": 11, "doce": 12,
         "trece": 13, "catorce": 14, "quince": 15, "dieciseis": 16, "diecisiete": 17,
         "dieciocho": 18, "diecinueve": 19, "veinte": 20, "veintiun": 21, "veintiuno": 21,
         "veintiuna": 21, "veintidos": 22, "veintitres": 23, "veinticuatro": 24,
         "veinticinco": 25, "veintiseis": 26, "veintisiete": 27, "veintiocho": 28,
         "veintinueve": 29}
TENS = {"treinta": 30, "cuarenta": 40, "cincuenta": 50, "sesenta": 60, "setenta": 70,
        "ochenta": 80, "noventa": 90}
HUNDREDS = {"cien": 100, "ciento": 100}


def _fold(text):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", text or "")
                   if unicodedata.category(c) != "Mn").lower()


def words_to_int(text):
    """'noventa y tres' -> 93, 'veintiún' -> 21, 'cien' -> 100. None when the
    words are not a number. pypdf splits words now and then ('cincu enta'),
    so an unknown token is joined to the next before giving up."""
    toks = [t for t in re.split(r"[\s\-]+", _fold(text)) if t and t != "y"]
    if not toks:
        return None
    total, i = 0, 0
    while i < len(toks):
        t = toks[i]
        joined = t + toks[i + 1] if i + 1 < len(toks) else None
        for cand, step in ((t, 1), (joined, 2)):
            if cand and (cand in UNITS or cand in TENS or cand in HUNDREDS):
                total += UNITS.get(cand, TENS.get(cand, HUNDREDS.get(cand, 0)))
                i += step
                break
        else:
            return None
    return total


# --- the Diario's text -----------------------------------------------------------------

NUM = r"[A-Za-zÁÉÍÓÚáéíóúÑñü ]+?"


def _fz(word):
    """A keyword with pypdf's stray spaces allowed between its letters
    ('neg ativos', 'presen tes')."""
    return r"\s?".join(re.escape(c) for c in word)


RES = r"(?P<res>AFIRMATIVA|NEGATIVA)"
REGISTER = re.compile(
    r"(?P<yes>{n})\s+{v}\s+{a}\s+y\s+(?P<no>{n})\s+(?:{v}\s+)?{neg}\s+en\s+"
    r"(?P<present>{n})\s+{p}\s*:\s*{r}".format(
        n=NUM, v=_fz("votos") + "?", a=_fz("afirmativos") + "?", neg=_fz("negativos") + "?",
        p=_fz("presentes") + "?", r=RES))
AYES_PRESENT = re.compile(
    r"(?P<yes>{n})\s+{v}\s+{a}\s+en\s+(?P<present>{n})\s+{p}\s*:\s*{r}".format(
        n=NUM, v=_fz("votos") + "?", a=_fz("afirmativos") + "?", p=_fz("presentes") + "?",
        r=RES))
HANDS = re.compile(r"(?P<yes>{0})\s+en\s+(?P<present>{0})\s*:\s*{1}".format(NUM, RES))
AYES_ONLY = re.compile(r"(?P<yes>{0})\s+por\s+la\s+afirmativa\s*:\s*{1}".format(NUM, RES))
RESULT = re.compile(r"(?:——|—)\s*([^—]{3,200}?:\s*(?:AFIRMATIVA|NEGATIVA))")
HEADING = re.compile(r"^\s*(\d{1,3})\s*\.-\s+(.+?)\s*$")
LEADER = re.compile(r"\.{5,}|…{2,}")
CARPETA = re.compile(r"Carp(?:eta)?\.?\s*n?\.?\s*[°º]?\s*(\d{1,5})\s*(?:/|de)\s*(\d{4})", re.I)
SENTENCE = re.compile(r"(?:[^.]|\.(?=\s*[°ºo]\s*\d))+(?:\.|$)")


def pdf_text(raw):
    """(pages, text) of a PDF; text is '' for a scan."""
    import pypdf
    reader = pypdf.PdfReader(io.BytesIO(raw))
    return len(reader.pages), "\n".join((p.extract_text() or "") for p in reader.pages)


def sections(text):
    """[(number, title, body)] in order. The Sumario at the front lists the
    same headings with dot leaders and page numbers; those are skipped."""
    out, cur = [], None
    for line in text.splitlines():
        m = HEADING.match(line)
        if m and not LEADER.search(line):
            if cur:
                out.append(cur)
            cur = [int(m.group(1)), re.sub(r"\s+", " ", m.group(2)).strip(), []]
            continue
        if cur:
            cur[2].append(line)
    if cur:
        out.append(cur)
    return [(n, t, "\n".join(b)) for n, t, b in out]


def parse_result(line):
    """{yes, no, present, result, electronic} from one result line, or the
    result word alone with NULL counts when the numbers do not parse
    ('El resultado es: AFIRMATIVA')."""
    one = re.sub(r"\s+", " ", line)
    m = REGISTER.search(one)
    if m:
        return {"yes": words_to_int(m.group("yes")), "no": words_to_int(m.group("no")),
                "present": words_to_int(m.group("present")), "result": m.group("res"),
                "electronic": 1}
    for pattern in (AYES_PRESENT, HANDS):
        m = pattern.search(one)
        if m:
            return {"yes": words_to_int(m.group("yes")), "no": None,
                    "present": words_to_int(m.group("present")), "result": m.group("res"),
                    "electronic": 1 if pattern is AYES_PRESENT else 0}
    m = AYES_ONLY.search(one)
    if m:
        return {"yes": words_to_int(m.group("yes")), "no": None, "present": None,
                "result": m.group("res"), "electronic": 0}
    res = re.search(r"(AFIRMATIVA|NEGATIVA)", one)
    return {"yes": None, "no": None, "present": None, "result": res.group(1) if res else None,
            "electronic": 0}


def _tidy(text):
    text = re.sub(r"\bn\.\s*[oº°]\s*(\d)", r"n.º \1", text)
    return re.sub(r"\s+", " ", text).strip()


def question_before(body, pos, floor=0):
    """What was put to the vote, in the Diario's words: the last "se va a
    votar ..." that names its object, else the last "En discusión ...", else
    the electronic register's "votación n.º N[, correspondiente a ...]",
    else the bare "Se va a votar"."""
    window = _tidy(body[max(floor, pos - 1200):pos].replace("(Se vota)", " "))
    sentences = [x.strip() for x in SENTENCE.findall(window) if x.strip()]
    for test in (lambda x: re.search(r"se va a votar\s+\S{2,}", x, re.I)
                 and not re.search(r"se va a votar\.?$", x, re.I),
                 lambda x: x.lower().startswith("en discusi"),
                 lambda x: re.search(r"votaci[oó]n n\.º \d", x, re.I),
                 lambda x: re.search(r"\bvotar\b", x, re.I)):
        for x in reversed(sentences[-8:]):
            if test(x):
                return courts.clip(x.lstrip("-—– "), QUESTION_CHARS)
    return None


SUMARIO_ENTRY = re.compile(r"^\s*((?:\d{1,3}\s*(?:,|y)\s*)*\d{1,3})\s*\.-\s+\S")


def sumario_carpetas(text, lines_after=4):
    """{section number: '133/2025'} from the Sumario at the front, where each
    agenda item lists its section numbers ("9, 12, 14, ... 43.- Muerte
    digna") and, a line or two below, its "Carp. n.º 133 de 2025"."""
    out = {}
    lines = text.splitlines()[:600]
    for i, line in enumerate(lines):
        m = SUMARIO_ENTRY.match(line)
        if not m:
            continue
        tail = " ".join(lines[i:i + 1 + lines_after])
        nxt = [j for j in range(i + 1, min(len(lines), i + 1 + lines_after))
               if SUMARIO_ENTRY.match(lines[j])]
        if nxt:
            tail = " ".join(lines[i:nxt[0]])
        c = CARPETA.search(tail)
        if c:
            for n in re.findall(r"\d{1,3}", m.group(1)):
                out.setdefault(int(n), "{0}/{1}".format(c.group(1), c.group(2)))
    return out


def parse_diario(text):
    """[{seq, section_no, section_title, carpeta, question, yes, no,
    present, result, electronic, raw}] for every vote result."""
    out, seq = [], 0
    from_sumario = sumario_carpetas(text)
    for number, title, body in sections(text):
        carp = CARPETA.search(body[:3000])
        flatbody = body.replace("\n", " ")
        prev = 0
        for m in RESULT.finditer(flatbody):
            seq += 1
            row = parse_result(m.group(1))
            row.update(seq=seq, section_no=number, section_title=title,
                       carpeta="{0}/{1}".format(carp.group(1), carp.group(2)) if carp
                       else from_sumario.get(number),
                       question=question_before(flatbody, m.start(), prev),
                       raw=courts.clip(re.sub(r"\s+", " ", m.group(1)), 300))
            out.append(row)
            prev = m.end()
    return out


# --- store ------------------------------------------------------------------------------

def store(conn, diario, date, pages, text, votes, tax, today):
    sect = {}
    for v in votes:
        if v["section_title"] not in sect:
            sect[v["section_title"]] = courts.classify(tax, v["section_title"])
    conn.execute("DELETE FROM uy_diario_votes WHERE chamber=? AND diario=?", (CHAMBER, diario))
    for v in votes:
        areas, terms, tier = sect[v["section_title"]]
        conn.execute(
            "INSERT INTO uy_diario_votes (chamber, diario, seq, date, section_no, section_title, "
            "carpeta, question, yes, no, present, result, electronic, raw, areas, matched_terms, "
            "tier, first_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (CHAMBER, diario, v["seq"], date, v["section_no"], v["section_title"], v["carpeta"],
             v["question"], v["yes"], v["no"], v["present"], v["result"], v["electronic"],
             v["raw"], json.dumps(areas), json.dumps(terms, ensure_ascii=False), tier, today))
    unparsed = sum(1 for v in votes if v["yes"] is None)
    conn.execute(
        "INSERT INTO uy_diario_reads (chamber, diario, date, pages, chars, votes, unparsed, read_at) "
        "VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(chamber, diario) DO UPDATE SET date=excluded.date, "
        "pages=excluded.pages, chars=excluded.chars, votes=excluded.votes, "
        "unparsed=excluded.unparsed, read_at=excluded.read_at",
        (CHAMBER, diario, date, pages, len(text or ""), len(votes), unparsed, today))
    conn.commit()
    return sum(1 for a, _, _ in sect.values() if courts.on_ground(a))


def pending(conn, limit, every_legislature=False):
    sql = ("SELECT s.diario, s.date, s.url FROM uy_sittings s LEFT JOIN uy_diario_reads r "
           "ON r.chamber = s.chamber AND r.diario = s.diario WHERE s.chamber = ? AND "
           "r.diario IS NULL AND s.url IS NOT NULL")
    if not every_legislature:
        sql += " AND s.legislature = 'L'"
    return conn.execute(sql + " ORDER BY s.date DESC, s.diario DESC LIMIT ?",
                        (CHAMBER, limit)).fetchall()


def pull(conn, client, today, tax, limit=MAX_READ, every_legislature=False, log=print):
    """Returns (diarios read, votes, sections on our ground, gaps)."""
    read = votes = ours = gaps = 0
    for diario, date, url in pending(conn, limit, every_legislature):
        try:
            raw = client.get_bytes(url, FEED, "d{0}".format(diario), archive=False)
            pages, text = pdf_text(raw)
        except FetchError as exc:
            gaps += 1
            db.record_gap(conn, FEED, "Diario {0} unreadable: {1}".format(diario, str(exc)[:100]),
                          today)
            continue
        except Exception as exc:          # a broken PDF: say so, carry on
            gaps += 1
            db.record_gap(conn, FEED, "Diario {0}: PDF unreadable ({1})".format(
                diario, type(exc).__name__), today)
            continue
        got = parse_diario(text) if text.strip() else []
        n = store(conn, diario, date, pages, text, got, tax, today)
        read += 1
        votes += len(got)
        ours += n
        log("  Diario {0} ({1}): {2} page(s), {3} vote(s), {4} section(s) on our ground{5}".format(
            diario, date, pages, len(got), n, "; NO TEXT LAYER" if not text.strip() else ""))
    conn.commit()
    return read, votes, ours, gaps


def reclassify(conn, tax):
    n = 0
    for (title,) in conn.execute("SELECT DISTINCT section_title FROM uy_diario_votes").fetchall():
        areas, terms, tier = courts.classify(tax, title)
        conn.execute("UPDATE uy_diario_votes SET areas=?, matched_terms=?, tier=? "
                     "WHERE section_title=?",
                     (json.dumps(areas), json.dumps(terms, ensure_ascii=False), tier, title))
        n += 1
    conn.commit()
    return n


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--raw-dir", default=os.path.join(ROOT, "data", "raw"))
    ap.add_argument("--max", type=int, default=MAX_READ, help="Diarios to read this run")
    ap.add_argument("--all", action="store_true", help="older legislatures too")
    ap.add_argument("--file", help="read one local PDF (with --diario and --date)")
    ap.add_argument("--diario", type=int)
    ap.add_argument("--date")
    ap.add_argument("--reclassify", action="store_true")
    args = ap.parse_args(argv)
    today = datetime.date.today().isoformat()
    tax = courts.load_taxonomy(CC)
    conn = db.init_db(db.connect(args.db))
    if args.reclassify:
        print("uy-diario: {0} section title(s) reclassified".format(reclassify(conn, tax)))
        return 0
    if args.file:
        with open(args.file, "rb") as fh:
            pages, text = pdf_text(fh.read())
        got = parse_diario(text)
        n = store(conn, args.diario, args.date, pages, text, got, tax, today)
        print("uy-diario: Diario {0}: {1} vote(s), {2} section(s) on our ground".format(
            args.diario, len(got), n))
        return 0
    client = HttpClient(raw_dir=args.raw_dir, throttle=2.0)
    read, votes, ours, gaps = pull(conn, client, today, tax, args.max, args.all)
    left = len(pending(conn, 100000, args.all))
    print("uy-diario: {0} Diario(s) read, {1} vote total(s), {2} section(s) on our ground; "
          "{3} Diario(s) still to read.".format(read, votes, ours, left))
    conn.close()
    return 3 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
