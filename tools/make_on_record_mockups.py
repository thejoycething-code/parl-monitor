"""Build docs/on-record-mockups.html: four options for "Also on the record".

Every row, count, quote and link is read from the BUILT page, so the mockups
cannot drift from what the site actually ships.

THE TRAP, if you write another mockup page. This file embeds the template's
whole stylesheet so the options look like the real thing -- which means any
class name it invents is sharing a namespace with 250-odd page rules. The
first version used `.opt`, the page already had
`.opt{display:flex;align-items:center}` for its filter rows, and every
option rendered as a column of single words. Everything this file defines is
prefixed `mk-`, and a check at the end asserts no collisions.
"""
import json, os, re, sys, html

ROOT = "/Users/chrisjoyce/parl-monitor"
src = open(os.path.join(ROOT, "partner_site", "mp-votes.html"), encoding="utf-8").read()
DATA = json.loads(re.search(r"const DATA\s*=\s*(\{.*?\});\n", src, re.S).group(1))
CSS = re.search(r"<style>([\s\S]*?)</style>", src).group(1)

def member(sub):
    return [m for m in DATA["members"] if sub.lower() in m["name"].lower()][0]

E = html.escape
KIND = {"debate": "SPOKE", "pq": "ASKED", "edm": "PROPOSED EDM", "edm-signed": "SIGNED EDM"}
MONTH = ["", "January","February","March","April","May","June","July","August",
         "September","October","November","December"]

def fmtD(d):
    y, m, dd = d.split("-")
    return "{0} {1} {2}".format(int(dd), MONTH[int(m)], y)

def link(it):
    if it.get("u"):
        what = "Written question" if it["k"] == "pq" else "Hansard"
        return ' &middot; <a class="official" href="{0}" target="_blank">{1}</a>'.format(it["u"], what)
    if it.get("e"):
        return (' &middot; <a class="official" target="_blank" '
                'href="https://edm.parliament.uk/early-day-motion/{0}">EDM register</a>'.format(it["e"]))
    return ""

def counts(n):
    p = []
    if n.get("debate"): p.append("<b>spoke in {0} debate{1}</b>".format(n["debate"], "s" if n["debate"] > 1 else ""))
    if n.get("pq"): p.append("<b>asked {0} written question{1}</b>".format(n["pq"], "s" if n["pq"] > 1 else ""))
    if n.get("edm"): p.append("<b>proposed {0} early day motion{1}</b>".format(n["edm"], "s" if n["edm"] > 1 else ""))
    if n.get("edm-signed"): p.append("<b>signed {0} early day motion{1}</b>".format(n["edm-signed"], "s" if n["edm-signed"] > 1 else ""))
    return " &middot; ".join(p)

def total(n): return sum(n.values())

# ---------------------------------------------------------------- CURRENT ---
def row_now(it):
    q = '<blockquote class="recquote">{0}</blockquote>'.format(E(it["q"])) if it.get("q") else ""
    return ('<div class="recrow"><span class="reckind">{0}</span><div class="recbody">'
            '<div class="rectitle">{1}</div>{2}'
            '<div class="recmeta">{3}{4}</div></div></div>').format(
        KIND.get(it["k"], it["k"]), E(it["t"]), q, fmtD(it["d"]), link(it))

def render_now(m):
    out = []
    for a, b in m["record"].items():
        c = counts(b["n"]); t = total(b["n"]); shown = len(b["items"])
        out.append('<div class="recarea"><div class="recareahead"><h3>{0}</h3></div>'.format(
            E(DATA["areas"].get(a, a))))
        if c: out.append('<p class="reccounts">{0}</p>'.format(c))
        out.extend(row_now(it) for it in b["items"])
        if t > shown and shown:
            out.append('<p class="recmore">Showing the {0} most recent of {1}.</p>'.format(shown, t))
        out.append("</div>")
    return "".join(out)

# ------------------------------------------------- A: strongest receipt first
STRENGTH = {"debate": 4, "pq": 2, "edm": 3, "edm-signed": 1}
def render_a(m):
    out = []
    for a, b in m["record"].items():
        its = sorted(b["items"],
                     key=lambda x: (1 if x.get("q") else 0, STRENGTH.get(x["k"], 0), x["d"]),
                     reverse=True)
        c = counts(b["n"]); t = total(b["n"])
        out.append('<div class="recarea"><div class="recareahead"><h3>{0}</h3></div>'.format(
            E(DATA["areas"].get(a, a))))
        if c: out.append('<p class="reccounts">{0}</p>'.format(c))
        out.extend(row_now(it) for it in its)
        if t > len(its) and its:
            out.append('<p class="recmore">Showing the {0} strongest of {1}.</p>'.format(len(its), t))
        out.append("</div>")
    return "".join(out)

# ------------------------------------------------------- B: one line per row
def row_b(it):
    q = ('<details class="mk-mq"><summary>quote</summary><blockquote class="recquote">{0}</blockquote></details>'
         ).format(E(it["q"])) if it.get("q") else ""
    return ('<div class="mk-brow"><span class="mk-bkind mk-k-{0}">{1}</span>'
            '<span class="mk-btitle">{2}</span>'
            '<span class="mk-bmeta">{3}{4}</span>{5}</div>').format(
        it["k"], KIND.get(it["k"], it["k"]), E(it["t"]), fmtD(it["d"]), link(it), q)

def render_b(m):
    out = []
    for a, b in m["record"].items():
        c = counts(b["n"]); t = total(b["n"])
        out.append('<div class="recarea"><div class="recareahead"><h3>{0}</h3></div>'.format(
            E(DATA["areas"].get(a, a))))
        if c: out.append('<p class="reccounts">{0}</p>'.format(c))
        out.extend(row_b(it) for it in b["items"])
        if t > len(b["items"]) and b["items"]:
            out.append('<p class="recmore">Showing the {0} most recent of {1}.</p>'.format(len(b["items"]), t))
        out.append("</div>")
    return "".join(out)

# ---------------------------------------------------- C: split by Parliament
GE = "2024-07-04"
def render_c(m):
    out = []
    for a, b in m["record"].items():
        c = counts(b["n"]); t = total(b["n"])
        now = [x for x in b["items"] if x["d"] >= GE]
        old = [x for x in b["items"] if x["d"] < GE]
        out.append('<div class="recarea"><div class="recareahead"><h3>{0}</h3></div>'.format(
            E(DATA["areas"].get(a, a))))
        if c: out.append('<p class="reccounts">{0}</p>'.format(c))
        # Only label when the block ACTUALLY splits. Stamping "In this
        # Parliament" on a block whose rows are all recent is a header that
        # tells the reader nothing, on most blocks.
        split = bool(now) and bool(old)
        if now:
            if split: out.append('<p class="mk-epoch">In this Parliament</p>')
            out.extend(row_now(it) for it in now)
        if old:
            if split: out.append('<p class="mk-epoch">Before the 2024 election</p>')
            else: out.append('<p class="mk-epoch">Before the 2024 election</p>')
            out.extend(row_now(it) for it in old)
        if t > len(b["items"]) and b["items"]:
            out.append('<p class="recmore">Showing the {0} most recent of {1}.</p>'.format(len(b["items"]), t))
        out.append("</div>")
    return "".join(out)

# ------------------------------------ D: mk-tally is the spine, quotes the proof
def tally(n):
    """Nouns, not verb fragments: "13 spoke in" reads as a broken sentence."""
    cells = []
    for key, one, many in (("debate", "debate", "debates"),
                           ("pq", "written question", "written questions"),
                           ("edm", "motion proposed", "motions proposed"),
                           ("edm-signed", "motion signed", "motions signed")):
        v = n.get(key)
        if v:
            cells.append('<span class="mk-tcell"><b>{0}</b> {1}</span>'.format(
                v, one if v == 1 else many))
    return '<div class="mk-tally">{0}</div>'.format("".join(cells))

def render_d(m):
    out = []
    for a, b in m["record"].items():
        quoted = [x for x in b["items"] if x.get("q")]
        out.append('<div class="recarea"><div class="recareahead"><h3>{0}</h3></div>'.format(
            E(DATA["areas"].get(a, a))))
        out.append(tally(b["n"]))
        if quoted:
            out.extend(row_now(it) for it in quoted)
        else:
            best = b["items"][0] if b["items"] else None
            if best:
                # An early day motion has no text in the ledger at all --
                # 0 of 1,457 -- so "no passage long enough" would be wrong.
                why = ("Early day motions carry no text here"
                       if best["k"].startswith("edm")
                       else "No passage long enough to quote")
                out.append('<p class="mk-nowords">{0}. Most recent: '
                           '<b>{1}</b>{2}</p>'.format(why, E(best["t"]), link(best)))
        out.append("</div>")
    return "".join(out)

EXTRA = """
.mk-mockwrap{max-width:760px;margin:0 auto;padding:28px 20px 60px}
.mk-opt{border:1px solid var(--line);border-radius:10px;padding:18px 20px;margin:0 0 26px;background:#fff}
.mk-optlabel{font-size:11px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;
  color:var(--blue-deep);margin:0 0 2px}
.mk-opth{font-size:17px;font-weight:600;color:#23282f;margin:0 0 6px}
.mk-optnote{font-size:13px;margin:0 0 14px;color:var(--ink);max-width:70ch}
.mk-optnote b{color:#23282f;font-weight:600}
.mk-who{font-size:11px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;
  color:#9aa1a9;margin:16px 0 2px;padding-top:10px;border-top:1px dashed var(--line)}
.mk-brow{display:flex;flex-wrap:wrap;align-items:baseline;gap:8px;padding:7px 0;
  border-top:1px solid var(--line);font-size:13.5px}
.mk-bkind{flex:0 0 auto;font-size:9px;font-weight:700;letter-spacing:.05em;padding:2px 6px;
  border-radius:3px;background:var(--grey-100);color:#4a5058}
.mk-btitle{flex:1 1 320px;min-width:0;font-weight:500;color:#23282f}
.mk-bmeta{font-size:11.5px;color:#9aa1a9}
.mk-mq{flex:0 0 100%;margin:2px 0 0}
.mk-mq summary{font-size:11.5px;color:var(--blue-deep);cursor:pointer}
.mk-mq .recquote{margin-top:4px}
.mk-epoch{font-size:10.5px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;
  color:#9aa1a9;margin:12px 0 0}
.mk-tally{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 8px}
.mk-tcell{font-size:12px;padding:3px 9px;border-radius:20px;background:var(--grey-100);color:#4a5058}
.mk-tcell b{color:#23282f;font-weight:600}
.mk-nowords{font-size:13px;color:#9aa1a9;margin:6px 0 0;padding:9px 0;border-top:1px solid var(--line)}
"""

OPTS = [
    ("Option A", "Strongest receipt first",
     "Rows are ordered by <b>evidence strength</b> &mdash; a quoted speech, then a written "
     "question, a proposed motion, a signed one, a bare debate title &mdash; and only then by "
     "date. Fixes the <b>88 blocks whose first row is bare while a quote sits below it</b>. "
     "The cap line changes from &ldquo;most recent&rdquo; to &ldquo;strongest&rdquo;, which is "
     "the honest description once the order is no longer chronological.", render_a),
    ("Option B", "One line per receipt, quote on demand",
     "Each receipt is a single line: kind, title, date, link. The quote moves behind a "
     "<b>quote</b> disclosure. On Jim Shannon&rsquo;s page that is <b>8 rows in roughly half "
     "the height</b>. Costs the at-a-glance quote &mdash; the words are the point of the "
     "section, and this hides 40% of rows that have one.", render_b),
    ("Option C", "Split by Parliament",
     "<b>28% of rows predate the 2024 election</b>, and a 2006 motion currently sits level "
     "with a 2026 speech. This groups each block into &ldquo;In this Parliament&rdquo; and "
     "&ldquo;Before the 2024 election&rdquo;. Adds a line per group but answers "
     "&ldquo;is this still what they think?&rdquo; without the reader doing date arithmetic.",
     render_c),
    ("Option D", "The tally is the spine, quotes are the proof",
     "The counts become a compact tally strip, and <b>only rows that carry a quote</b> are "
     "listed beneath. Bare rows &mdash; <b>60% of all rows, 394 of them bare debate titles</b> "
     "&mdash; fold into the tally they already belong to. Where a block has no quote at all it "
     "says so and names its most recent receipt, so nothing is hidden.", render_d),
]

people = [member("Jim Shannon"), member("Danny Kruger")]

body = ['<div class="mk-mockwrap">',
        '<h1 style="font-size:22px;font-weight:600;color:#23282f;margin:0 0 4px">',
        '&ldquo;Also on the record&rdquo; &mdash; four improvements</h1>',
        '<p style="font-size:13.5px;margin:0 0 8px;max-width:74ch">Rendered from the live payload, ',
        'not mocked up: every row, count, quote and link below is what the page ships today ',
        '(878 blocks, 1,385 rows, 466 members). Two members are shown for each option &mdash; ',
        'Jim Shannon, who has the fullest record on the page, and Danny Kruger.</p>',
        '<p style="font-size:12.5px;color:#9aa1a9;margin:0 0 22px">These four are independent. ',
        'A and C can both ship; B and D are alternative answers to the same problem.</p>']

body.append('<div class="mk-opt"><p class="mk-optlabel">As it is now</p>'
            '<h2 class="mk-opth">Current</h2>'
            '<p class="mk-optnote">Newest first, every row full-height, the quote always inline.</p>')
for p in people:
    body.append('<p class="mk-who">{0}</p>'.format(E(p["name"])) + render_now(p))
body.append('</div>')

for label, head, note, fn in OPTS:
    body.append('<div class="mk-opt"><p class="mk-optlabel">{0}</p><h2 class="mk-opth">{1}</h2>'
                '<p class="mk-optnote">{2}</p>'.format(label, head, note))
    for p in people:
        body.append('<p class="mk-who">{0}</p>'.format(E(p["name"])) + fn(p))
    body.append('</div>')
body.append('</div>')

out = ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
       "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
       "<title>Also on the record - four improvements</title>"
       "<style>{0}{1}</style></head><body>{2}</body></html>").format(CSS, EXTRA, "".join(body))
dest = os.path.join(ROOT, "docs", "on-record-mockups.html")
open(dest, "w", encoding="utf-8").write(out)
print("-> {0}  ({1:,} bytes)".format(dest, len(out)))

# The collision guard, run every build: see the module docstring.
_page = set(re.findall(r"\.([A-Za-z][\w-]*)", CSS))
_mine = set()
for _c in re.findall(r'class="([^"]+)"', out):
    _mine |= {x for x in _c.split() if x.startswith("mk-")}
_clash = sorted(_mine & _page)
assert not _clash, "mockup classes collide with the page stylesheet: {0}".format(_clash)
print("   {0} mk- classes, no collisions with the page stylesheet".format(len(_mine)))
