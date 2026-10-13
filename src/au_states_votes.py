"""Divisions beyond New South Wales: parsers for the official records that
list each division with every member's vote, on hosts that answer our
honest user agent (13 October 2026, branch au-divisions-alt;
docs/australia-states-scope.md, "Divisions: the alternative routes").

Pure functions, no network, no store: tools/au_states.py fetches and stores.

  * Victoria: the Legislative Assembly's Votes and Proceedings and the
    Legislative Council's Minutes of the Proceedings, as Word files from
    www.parliament.vic.gov.au (the House documents database's own listing,
    /api/search/house-papers/<id>, the JSON the page itself loads). Each
    division names every member: "Ayes 31" then "Brad Battin; Jade
    Benham; ...".
  * South Australia: the House of Assembly's Votes and Proceedings and the
    Legislative Council's Minutes, PDFs in the Parliament's document library
    (dynamic-content-api.parliament.sa.gov.au, the backend of the library
    the Parliament's own pages embed). The Assembly prints Ayes and Noes in
    two columns side by side; the Council one name per line.
  * Tasmania: the daily Hansard of each House as a Word file, from the
    Parliament's own search engine (search.parliament.tas.gov.au); each
    division is a table, Ayes in the left column and Noes in the right.
  * The ACT: the daily Hansard PDF from www.hansard.act.gov.au (the
    Assembly's Hansard site, which answers us although
    www.parliament.act.gov.au challenges). Names are laid out in columns,
    so the pages with a division are read with their x positions.

Every parser returns a list of divisions:

    {"heading", "question", "result", "ayes", "noes", "pairs",
     "votes": [(name, 'aye' | 'no' | 'pair', teller)]}

Names are kept as printed (the records carry no member IDs); the store
keys a member '<state>:name:<the name folded>'.
"""

from __future__ import annotations

import html
import io
import re
import zipfile

# --- shared helpers ---------------------------------------------------------

TELLER = re.compile(r"\s*\(\s*Teller\s*\)\s*", re.I)
MONTHS = {m: i + 1 for i, m in enumerate(
    ("january", "february", "march", "april", "may", "june", "july", "august", "september",
     "october", "november", "december"))}


def clean_name(name):
    """('Mr Telfer', True) from 'Mr Telfer (Teller)'; None for a non-name."""
    name = (name or "").replace("\xa0", " ").replace("‑", "-")
    teller = bool(TELLER.search(name))
    name = TELLER.sub(" ", name)
    name = re.sub(r"\s+", " ", name).strip(" .;,*")
    name = re.sub(r"^The\s+(?=Hon\b)", "", name)
    if not name or len(name) > 60 or not re.search(r"[A-Za-z]{2}", name):
        return None
    return name, teller


def name_key(name):
    """The folded name a member is keyed by: lower case, initials' dots and
    honorific dots dropped ('Hon. D.G.E. Hood' -> 'hon-d-g-e-hood')."""
    return re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")[:80]


def iso_dmy_words(text):
    """'Thursday 17 September 2026' or '27.11.2025' -> ISO date, else None."""
    m = re.search(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", text or "")
    if m and m.group(2).lower() in MONTHS:
        return "{0}-{1:02d}-{2:02d}".format(int(m.group(3)), MONTHS[m.group(2).lower()],
                                            int(m.group(1)))
    m = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", text or "")
    if m:
        return "{0}-{1:02d}-{2:02d}".format(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    return None


def tidy_caps(text):
    """A heading printed in capitals, in title case ('HEALTH (ABORTION) BILL
    2026' -> 'Health (Abortion) Bill 2026'); anything else as it is."""
    text = re.sub(r"\s+", " ", (text or "")).strip(" —–-")
    letters = re.findall(r"[A-Za-z]", text)
    if letters and sum(c.isupper() for c in letters) >= 0.8 * len(letters) and re.search(r"[A-Z]{3}", text):
        small = {"and", "of", "the", "for", "in", "on", "to", "or", "a", "an", "by", "with"}
        words = []
        for i, w in enumerate(text.lower().split(" ")):
            words.append(w if (i and w in small) else w[:1].upper() + w[1:])
        text = " ".join(words)
        text = re.sub(r"(\(|-|’|')([a-z])", lambda m: m.group(1) + (
            m.group(2) if m.group(1) in "’'" else m.group(2).upper()), text)
        text = re.sub(r"\bNo\.", "No.", text)
    return text


def outcome_from_result(result):
    low = (result or "").lower()
    if "negatived" in low or "defeated" in low or "negative" in low:
        return "negatived"
    if "agreed" in low or "affirmative" in low or "passed" in low:
        return "agreed"
    return None


# --- Word files -------------------------------------------------------------

_RUN_TOKEN = re.compile(r"<w:t(?:\s[^>]*)?>([^<]*)</w:t>|<w:(tab|br|cr|noBreakHyphen|softHyphen)\b[^>]*/>")
# A self-closing '<w:p .../>' must not open a match that runs to the next
# paragraph's end (it would swallow a table between them).
_PARA = r"<w:p(?:\s[^>]*)?/>|<w:p(?:\s[^>]*)?>.*?</w:p>"
_BODY_ITEM = re.compile(r"<w:tbl>.*?</w:tbl>|" + _PARA, re.S)


def _para_text(xml):
    out = []
    for m in _RUN_TOKEN.finditer(xml):
        if m.group(1) is not None:
            out.append(m.group(1))
        elif m.group(2) == "noBreakHyphen":
            out.append("-")
        elif m.group(2) in ("tab", "br", "cr"):
            out.append(" ")
    return re.sub(r"[ \t]+", " ", html.unescape("".join(out))).strip()


def docx_body(raw):
    """The document's body in order: [('p', text) | ('tbl', [[cell text]])]."""
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        xml = z.read("word/document.xml").decode("utf-8", "replace")
    out = []
    for m in _BODY_ITEM.finditer(xml):
        chunk = m.group(0)
        if chunk.startswith("<w:tbl>"):
            rows = []
            for tr in re.findall(r"<w:tr[ >].*?</w:tr>", chunk, re.S):
                rows.append([" ".join(_para_text(p) for p in re.findall(_PARA, tc, re.S)).strip()
                             for tc in re.findall(r"<w:tc>.*?</w:tc>", tr, re.S)])
            out.append(("tbl", rows))
        else:
            out.append(("p", _para_text(chunk)))
    return out


def docx_paragraphs(raw):
    """Every paragraph's text, tables flattened cell by cell."""
    out = []
    for kind, val in docx_body(raw):
        if kind == "p":
            out.append(val)
        else:
            for row in val:
                out.extend(row)
    return out


# --- Victoria: Votes and Proceedings, Minutes of the Proceedings ------------

VIC_DIVIDED = re.compile(r"^The (House|Council|Committee|Assembly) divided\b")
VIC_TALLY = re.compile(r"^(AYES|Ayes|NOES|Noes|PAIRS|Pairs),?\s*(\d+)?\s*$")
VIC_ITEM = re.compile(r"^(\d{1,3})\s*([A-Z0-9‘’'(][A-Z0-9 ,’'‘()\-–&:/.]{3,250}?)\s+[—–]\s")
VIC_RESULT = re.compile(r"^(Question|Motion|Amendments?|Bill|Clause|Original question)\b[^.]{0,80}?"
                        r"\b(agreed to|defeated|negatived|resolved in the (?:affirmative|negative))", re.I)
VIC_QUESTION = re.compile(r"[Qq]uestion\s*[—–-]?\s*(That\b.+?)\s*[—–]\s*(?:after debate,\s*)?put\b")
VIC_MOVED = re.compile(r"\bmoved,?\s*(?:by leave,\s*)?(That\b.+)")
VIC_RESUMED = re.compile(r"\bon (?:the )?question,?\s*(?:—\s*)?(That\b.+?)(?:;|$)")


def _vic_names(text):
    out = []
    # '(Recorded by Clerks-at-the-Table, ...)' trails the Council's lists.
    text = re.sub(r"\((?!\s*Teller)[^)]*\)", " ", text or "")
    # A free vote names its tellers after the list: '... Jess Wilson.
    # Tellers: Bronwyn Halfpenny; Michaela Settle.'
    parts = re.split(r"\.?\s*Tellers?\s*:\s*", text, maxsplit=1)
    for k, chunk in enumerate(parts):
        for part in re.split(r"[;,]", chunk):
            got = clean_name(part)
            if got:
                out.append((got[0], got[1] or k == 1))
    return out


def parse_vic(paragraphs):
    """Divisions from a Victorian Votes and Proceedings or Minutes."""
    paras = [p for p in paragraphs]
    out = []
    last_end = 0
    for i, p in enumerate(paras):
        if not VIC_DIVIDED.match(p):
            continue
        d = {"heading": None, "question": None, "result": None, "ayes": None, "noes": None,
             "pairs": 0, "votes": []}
        side, j = None, i + 1
        while j < len(paras) and j < i + 40:
            q = paras[j].strip()
            j += 1
            if not q or (q.startswith("(") and q.endswith(")") and "Teller" not in q):
                continue
            t = VIC_TALLY.match(q)
            if t:
                side = {"a": "aye", "n": "no", "p": "pair"}[t.group(1)[0].lower()]
                if t.group(2) and side in ("aye", "no"):
                    d["ayes" if side == "aye" else "noes"] = int(t.group(2))
                continue
            if VIC_RESULT.match(q) or VIC_ITEM.match(q) or VIC_DIVIDED.match(q):
                if VIC_RESULT.match(q):
                    d["result"] = q
                break
            if side:
                for name, teller in _vic_names(q):
                    d["votes"].append((name, side, teller))
        n_pair = sum(1 for v in d["votes"] if v[1] == "pair")
        d["pairs"] = n_pair // 2
        if d["ayes"] is None:
            d["ayes"] = sum(1 for v in d["votes"] if v[1] == "aye")
        if d["noes"] is None:
            d["noes"] = sum(1 for v in d["votes"] if v[1] == "no")
        # The question and the item heading, looking back.
        back = paras[last_end:i]
        for b in reversed(back):
            m = VIC_QUESTION.search(b)
            if m:
                d["question"] = m.group(1).strip()
                break
            if VIC_ITEM.match(b):
                break
        if not d["question"]:
            for b in reversed(back):
                m = VIC_MOVED.search(b) or VIC_RESUMED.search(b)
                if m:
                    d["question"] = m.group(1).strip()[:400]
                    break
                if VIC_ITEM.match(b):
                    break
        for b in reversed(paras[:i]):
            m = VIC_ITEM.match(b)
            if m:
                d["heading"] = tidy_caps(m.group(2))
                break
        last_end = j
        out.append(d)
    return out


# --- South Australia: Votes and Proceedings, Minutes (PDF text) ------------

SA_DIVIDED = re.compile(r"\b(House|Council|Committee) divided\b")
SA_BOTH = re.compile(r"Ayes,?\s*(\d+)\s+Noes,?\s*(\d+)")
SA_AYES = re.compile(r"^Ayes,?\s*(\d+)\s*$")
SA_NOES = re.compile(r"^Noes,?\s*(\d+)\s*$")
SA_PAIRS = re.compile(r"^Pairs?,?\s*(\d+)?\s*$")
SA_RESULT = re.compile(r"So it (?:was resolved in the (?:affirmative|negative)|passed in the "
                       r"(?:affirmative|negative))|resolved in the (?:affirmative|negative)", re.I)
SA_HONORIFIC = r"(?:The Hon\.|Hon\.|Mr|Mrs|Ms|Dr|Miss|Mx|Prof\.?)"
SA_NAME_START = re.compile(r"^" + SA_HONORIFIC + r"\s|^[A-Z]\s[A-Z][a-z’']")
# Two names on one line: split before an honorific, or before 'S Andrews'
# (a member printed with an initial and no title) after a surname.
SA_SPLIT = re.compile(r"\s+(?=(?:The Hon\.|Hon\.|Mr|Mrs|Ms|Dr|Miss|Mx|Prof\.?)\s)"
                      r"|(?<=[a-z’'\)])\s+(?=[A-Z]\s[A-Z][a-z’'])")
SA_ITEM = re.compile(r"^(\d{1,3})\s+([A-Z][^\n]{3,170})$")      # the Assembly's '3 Births ... Bill'
SA_LC_ITEM = re.compile(r"^(\d{1,3})\.\s")                       # the Council's ' 27.  On the Order ...'
# A bill's name in running text: capitalised words, small words and
# parentheses, ending in 'Bill' ('the Termination of Pregnancy (Restrictions
# on Terminations after 24 Weeks and 6 Days) Amendment Bill being ...').
SA_BILL = re.compile(r"([A-Z][A-Za-z’'\-]+,?(?:\s+(?:[A-Z][A-Za-z’'\-]*,?|of|and|the|for|on|to|in|after|"
                     r"with|\d+|\([^)]{1,120}\)))*\s+Bill)\b")
SA_BILL_LEAD = re.compile(r"^(?:(?:That|The|This|Order|Resolved)\s+(?:the\s+)?)+")
SA_BILL_NOT = re.compile(r"^(?:Private Members|Government|Members|Message|Bill\b)")


def sa_bill_names(text):
    """The bill names in running text, leading 'That the' dropped, 'Private
    Members' Bill' and the like left out."""
    out = []
    for b in SA_BILL.findall(text or ""):
        b = SA_BILL_LEAD.sub("", b).strip()
        if len(b.split()) >= 3 and not SA_BILL_NOT.match(b):
            out.append(b)
    return out
SA_QUESTION = re.compile(r"Question\s*[–-]\s*(That\b(?:(?!\bQuestion\b).){0,400}?)\s*[–-]\s*put\b", re.S)
SA_MOVED = re.compile(r"moved\s*[–-]\s*(That\b[^.]*\.)", re.S)
# The Council's 'the adjourned debate on the question - That the ... Bill be
# now read a second time - be now resumed'.
SA_RESUMED = re.compile(r"on the question\s*[–-]\s*(That\b(?:(?!\bThat\b).){0,300}?)\s*[–-]\s*be now resumed",
                        re.S)


def _sa_lines(text):
    out = []
    for line in (text or "").split("\n"):
        s = re.sub(r"\s+", " ", line.replace("\xa0", " ")).strip()
        if not s or s == "=====PAGE" or re.fullmatch(r"\d{1,4}", s):
            continue
        out.append(s)
    return out


def _sa_split(line):
    return [p for p in SA_SPLIT.split(line) if p and p.strip()]


def parse_sa(text):
    """Divisions from a South Australian Votes and Proceedings (two columns)
    or Legislative Council Minutes (one name a line), as pdf_text gives it."""
    lines = _sa_lines(text)
    out = []
    last_end = 0
    for i, line in enumerate(lines):
        if not SA_DIVIDED.search(line):
            continue
        d = {"heading": None, "question": None, "result": None, "ayes": 0, "noes": 0,
             "pairs": 0, "votes": []}
        j = i + 1
        both = SA_BOTH.search(lines[j]) if j < len(lines) else None
        if both:
            d["ayes"], d["noes"] = int(both.group(1)), int(both.group(2))
            j += 1
            ayes, noes = [], []
            while j < len(lines):
                s = lines[j]
                if SA_RESULT.search(s) or SA_PAIRS.match(s) or not SA_NAME_START.search(s):
                    break
                parts = [clean_name(p) for p in _sa_split(s)]
                parts = [p for p in parts if p]
                if len(parts) >= 2:
                    ayes.append(parts[0])
                    noes.extend(parts[1:])
                elif parts:
                    (ayes if len(ayes) < d["ayes"] else noes).append(parts[0])
                j += 1
            d["votes"] = [(n, "aye", t) for n, t in ayes] + [(n, "no", t) for n, t in noes]
        else:
            side = None
            while j < len(lines) and j < i + 200:
                s = lines[j]
                a, n = SA_AYES.match(s), SA_NOES.match(s)
                if a:
                    side, d["ayes"] = "aye", int(a.group(1))
                elif n:
                    side, d["noes"] = "no", int(n.group(1))
                elif SA_PAIRS.match(s):
                    side = "pair"
                elif SA_RESULT.search(s):
                    d["result"] = d["result"] or s
                    if side == "no" or side == "pair":
                        j += 1
                        break
                elif side and SA_NAME_START.search(s):
                    got = clean_name(s)
                    if got:
                        d["votes"].append((got[0], side, got[1]))
                elif side == "no" or side == "pair":
                    break
                elif side is None and j > i + 3:
                    break
                j += 1
            d["pairs"] = sum(1 for v in d["votes"] if v[1] == "pair") // 2
        if not d["result"]:
            for s in lines[j:j + 4]:
                if SA_RESULT.search(s):
                    d["result"] = SA_RESULT.search(s).group(0)
                    break
        else:
            d["result"] = SA_RESULT.search(d["result"]).group(0)
        block = " ".join(lines[max(last_end, i - 40):i])
        for pattern in (SA_QUESTION, SA_RESUMED, SA_MOVED):
            found = pattern.findall(block)
            if found:
                d["question"] = re.sub(r"\s+", " ", found[-1]).replace("Bill. be", "Bill be").strip()
                break
        start, title = 0, None
        for k in range(i - 1, -1, -1):
            m = SA_ITEM.match(lines[k])
            if m or SA_LC_ITEM.match(lines[k]):
                start, title = k, (m.group(2).strip() if m else None)
                break
        names = sa_bill_names(" ".join(lines[start:i]))
        d["heading"] = names[-1] if names else title
        last_end = j
        out.append(d)
    return out


# --- Tasmania: the daily Hansard (Word) --------------------------------------

TAS_TALLY = re.compile(r"AYES\s*(\d+)", re.I)
TAS_NOES = re.compile(r"NOES\s*(\d+)", re.I)
TAS_RESULT = re.compile(r"^(?:Question|Motion|Amendment|Amendments|Bill|Clause|Clauses|New clause|"
                        r"Third reading|Second reading)[^.]{0,80}?\b(agreed to|negatived)\b", re.I)
TAS_QUESTION = re.compile(r"((?:The )?question is (?:that|whether)\b.*)", re.I)
TAS_HEADING = re.compile(r"\bBill\s+\d{4}\b", re.I)


def parse_tas(body):
    """Divisions from a Tasmanian Hansard's body (docx_body)."""
    out = []
    for k, (kind, val) in enumerate(body):
        if kind != "tbl":
            continue
        head = None
        for r, row in enumerate(val[:4]):
            joined = " ".join(row)
            if TAS_TALLY.search(joined) and TAS_NOES.search(joined):
                head = r
                break
        if head is None:
            continue
        joined = " ".join(val[head])
        d = {"heading": None, "question": None, "result": None,
             "ayes": int(TAS_TALLY.search(joined).group(1)),
             "noes": int(TAS_NOES.search(joined).group(1)), "pairs": 0, "votes": []}
        pairs = False
        for row in val[head + 1:]:
            if any(c.strip().upper().startswith("PAIRS") for c in row):
                pairs = True
                continue
            for c, cell in enumerate(row[:2]):
                got = clean_name(cell)
                if got:
                    side = "pair" if pairs else ("aye" if c == 0 else "no")
                    d["votes"].append((got[0], side, got[1]))
        # After the table: PAIRS given as paragraphs, then the result.
        in_pairs = False
        for kind2, val2 in body[k + 1:k + 16]:
            if kind2 != "p":
                if kind2 == "tbl" and any("PAIRS" in " ".join(r).upper() for r in val2[:2]):
                    for row in val2:
                        for cell in row[:2]:
                            got = clean_name(cell)
                            if got and "PAIRS" not in cell.upper():
                                d["votes"].append((got[0], "pair", got[1]))
                continue
            s = val2.strip()
            if not s:
                continue
            if s.upper() == "PAIRS":
                in_pairs = True
                continue
            if TAS_RESULT.match(s):
                d["result"] = s
                break
            if in_pairs and len(s) < 40 and re.match(r"^(Mr|Mrs|Ms|Dr|Miss|Prof)\b", s):
                got = clean_name(s)
                if got:
                    d["votes"].append((got[0], "pair", got[1]))
                continue
            break
        d["pairs"] = sum(1 for v in d["votes"] if v[1] == "pair") // 2
        for kind2, val2 in reversed(body[max(0, k - 30):k]):
            if kind2 == "p" and TAS_QUESTION.search(val2):
                d["question"] = TAS_QUESTION.search(val2).group(1).strip()[:400]
                break
        for kind2, val2 in reversed(body[:k]):
            if kind2 == "p" and TAS_HEADING.search(val2) and len(val2) < 160 and not re.search(
                    r"\s[-–]\s|^(Mr|Mrs|Ms|Dr|Miss|Prof)\b", val2):
                d["heading"] = tidy_caps(val2.strip())
                break
        out.append(d)
    return out


# --- The ACT: the daily Hansard PDF -------------------------------------------

ACT_SKIP = re.compile(r"^PROOF\b|Legislative Assembly for the ACT|^P?\d{1,5}$")
ACT_RESULT = re.compile(r"^Question resolved in the (affirmative|negative)", re.I)


def _act_names(frags):
    """[(x0, name)] from one printed row's fragments: fragments drawn within
    3 pt of each other are one name."""
    names = []
    for x0, x1, text in sorted(frags):
        if names and x0 - names[-1][2] < 3:
            sep = "" if (x0 - names[-1][2] < 1 or text.strip() == "-" or names[-1][1].endswith("-")) else " "
            names[-1] = (names[-1][0], names[-1][1] + sep + text.strip(), x1)
        else:
            names.append((x0, text.strip(), x1))
    return [(x0, re.sub(r"\s*-\s*", "-", t).strip()) for x0, t, _x1 in names if t.strip()]


def act_vote_pages(page_texts):
    """The pages (by index) worth reading with positions: each page with a
    division, and its neighbours (the question and heading may be on the
    page before, the names may run onto the page after)."""
    hits = [i for i, t in enumerate(page_texts) if "Assembly voted" in t]
    return sorted({j for i in hits for j in (i - 1, i, i + 1) if 0 <= j < len(page_texts)})


def parse_act(rows, pages=None):
    """Divisions from the ACT Hansard pages read with positions
    (src/prov_fetch.pdf_rows on act_vote_pages; `pages` their numbers, so a
    heading is looked for on the division's page and the one before only)."""
    lines, page_of = [], []
    for n, page in enumerate(rows):
        number = pages[n] if pages and n < len(pages) else n
        for _y, frags in page:
            text = re.sub(r"\s+", " ", " ".join(t for _a, _b, t in frags)).strip()
            if not text or ACT_SKIP.search(text):
                continue
            lines.append((text, frags))
            page_of.append(number)
    out = []
    for i, (text, _f) in enumerate(lines):
        if "Assembly voted" not in text:
            continue
        d = {"heading": None, "question": None, "result": None, "ayes": None, "noes": None,
             "pairs": 0, "votes": []}
        j = i + 1
        threshold = None
        while j < len(lines) and j < i + 4:
            t, frags = lines[j]
            a = re.search(r"Ayes[,:]\s*(\d+)", t)
            n = re.search(r"Noes[,:]\s*(\d+)", t)
            if a:
                d["ayes"] = int(a.group(1))
            if n:
                d["noes"] = int(n.group(1))
            if a and n:
                xa = next((x0 for x0, _x1, s in frags if "Ayes" in s), None)
                xn = next((x0 for x0, _x1, s in frags if "Noes" in s), None)
                if xa is not None and xn is not None and xn > xa:
                    threshold = (xa + xn) / 2.0
                j += 1
                break
            j += 1
            if d["ayes"] is not None and d["noes"] is not None:
                break
        if threshold is not None:
            while j < len(lines) and j < i + 60:
                t, frags = lines[j]
                if ACT_RESULT.match(t) or t.startswith("Question") or "Assembly voted" in t:
                    break
                for x0, name in _act_names(frags):
                    got = clean_name(name)
                    if got:
                        d["votes"].append((got[0], "aye" if x0 < threshold else "no", got[1]))
                j += 1
        for t, _f in lines[j:j + 4]:
            if ACT_RESULT.match(t):
                d["result"] = t.strip()
                break
        # The question: what follows the last 'Question put' before the vote.
        q = []
        for k in range(i - 1, max(-1, i - 12), -1):
            t = lines[k][0]
            if page_of[k] < page_of[i] - 1:
                break
            if t.startswith("Question put"):
                rest = t.split(":", 1)[1].strip() if ":" in t else ""
                if rest:
                    q.insert(0, rest)
                break
            q.insert(0, t)
        if q and q[0].startswith("That"):
            d["question"] = " ".join(q)[:400]
        for k in range(i - 1, max(-1, i - 400), -1):
            if page_of[k] < page_of[i] - 1:
                break
            t = lines[k][0]
            if re.search(r"\bBill\b", t) and len(t) < 120 and not t.endswith((".", ":", ",")) \
                    and t[:1].isupper() and not re.match(r"^(MR|MS|MRS|DR|MISS)\s", t) \
                    and not t.startswith(("That", "Question", "Debate")):
                nxt = lines[k + 1][0] if k + 1 < len(lines) else ""
                d["heading"] = t + (" " + nxt if re.fullmatch(r"\d{4}(?:-\d{4})?", nxt) else "")
                break
        if d["ayes"] is None and d["noes"] is None:
            continue
        d["ayes"] = d["ayes"] if d["ayes"] is not None else sum(v[1] == "aye" for v in d["votes"])
        d["noes"] = d["noes"] if d["noes"] is not None else sum(v[1] == "no" for v in d["votes"])
        out.append(d)
    return out
