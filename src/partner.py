"""Partner edition: redacted render + static site for coalition allies.

Content decision (Christopher, 2026-08-03): partners see the full edition
including priority tags and why-lines, with the internal layer removed:

  * owner names stripped -- both the "Owner: X" fields and occurrences of
    those names inside prose ("Campaign live under Zuzana" -> "the team");
  * section 11 (MP intelligence notes) dropped entirely: it references the
    internal profiling machinery and is not partner material;
  * a partner banner replaces nothing else -- gaps footer stays (honesty
    travels well).

The site is static HTML behind a shared passphrase (Vercel edge middleware,
PARTNER_PASSPHRASE env var, fail-closed).
"""

from __future__ import annotations

import html as html_lib
import os
import re

OWNER_FIELD = re.compile(r";?\s*Owner: [^);\n]+")
MP_SECTION = re.compile(r"\n## (?:\d+\. )?(?:MP intelligence notes|Parliamentarians on our issues)\n"
                        r".*?(?=\n## |\n---)", re.S)
EMPTY_PARENS = re.compile(r" \(\s*\)")

BANNER = ("> **Coalition partner edition**, prepared by CitizenGO UK from Parliament's "
          "open data feeds. Priority tags reflect CitizenGO's own campaign assessment. "
          "Please do not circulate beyond your organisation.\n")


def owner_names(markdown):
    """Names appearing in Owner fields.

    NOT sufficient on its own: sections that no longer print Owner fields
    (the deadline table) can still carry names in prose, so callers must also
    pass extra_names from the store (items.owner) -- see owners_from_store."""
    return sorted(set(re.findall(r"Owner: ([^);\n]+)", markdown)))


def owners_from_store(conn):
    """Every owner name ever recorded: the authoritative scrub list."""
    rows = conn.execute("SELECT DISTINCT owner FROM items WHERE owner IS NOT NULL "
                        "AND owner != ''").fetchall()
    return [r[0] for r in rows]


def redact(markdown, extra_names=()):
    """Strip internal ownership, keep the parliamentary substance.

    The MP intelligence section IS included (Christopher, 2026-08-05,
    reversing the 3 August scoping): it reports public-record activity by
    named parliamentarians, which allies can see. What never leaves the
    building is who internally owns a campaign, so owner fields and owner
    names in prose are still removed. Stance placements and 5CA sheets are
    a separate matter and are not part of any edition.
    """
    names = set(owner_names(markdown)) | set(extra_names)
    out = OWNER_FIELD.sub("", markdown)
    out = EMPTY_PARENS.sub("", out)
    for name in sorted(names, key=len, reverse=True):
        for token in {name} | set(name.split()):
            if len(token) < 3:
                continue
            out = re.sub(r"\bunder %s\b" % re.escape(token), "under the team", out)
            out = re.sub(r"\b%s\b" % re.escape(token), "the team", out)
    # Banner goes after the H1 + subtitle.
    lines = out.splitlines()
    lines.insert(2, "")
    lines.insert(3, BANNER.rstrip())
    return "\n".join(lines) + ("\n" if not out.endswith("\n") else "")


# -- minimal markdown -> HTML for the edition subset --------------------------

# Absolute or same-site relative targets: the companion page is linked as
# questions.html, which an http-only pattern left as literal markdown.
_INLINE_LINK = re.compile(
    r"\[((?:[^\[\]]|\[[^\]]*\])+)\]\(((?:https?://|/|[\w.-]+\.html)[^)\s]*)\)")
_BOLD = re.compile(r"\*\*([^*]+)\*\*")


def _inline(text):
    text = html_lib.escape(text, quote=False)
    text = _BOLD.sub(r"<strong>\1</strong>", text)
    text = _INLINE_LINK.sub(r'<a href="\2">\1</a>', text)
    for tag, cls in (("ACT", "act"), ("WATCH", "watch"), ("NOTE", "note")):
        text = text.replace("<strong>[%s]</strong>" % tag,
                            '<span class="tag %s">%s</span>' % (cls, tag))
    for k in ("PQ", "DEBATE", "VOTE", "EDM"):
        text = text.replace("<strong>%s</strong>" % k,
                            '<span class="kindchip">%s</span>' % k)
    for kind, cls in (("Consultation", "consult"), ("Evidence", "evidence")):
        text = text.replace("<strong>%s</strong>" % kind,
                            '<span class="kind %s">%s</span>' % (cls, kind.upper()))
    return text


_DAYS = re.compile(r"(\d+) days")

# Hover explanations for parliamentary procedure terms (title attribute:
# native browser tooltip, works without JavaScript).
PROCEDURES = {
    "Draft affirmative": "Laid as a draft: it cannot become law until both Houses have voted to approve it.",
    "Made affirmative": "Already law when laid, but it lapses unless both Houses approve it within the statutory period (usually 28 or 40 days).",
    "Draft negative": "Laid as a draft: it becomes law unless either House objects within 40 days.",
    "Made negative": "Already law when laid: it stays law unless either House annuls it within the praying period (usually 40 days).",
}


def _proc_chip(cell_html):
    for name, blurb in PROCEDURES.items():
        if cell_html.strip() == name:
            return ('<span class="proc" title="{0}">{1}</span>'.format(
                html_lib.escape(blurb, quote=True), name))
    return cell_html


def _due_chip(cell_html):
    """Urgency-tinted deadline chip: red <=8 days, amber <=21, grey beyond."""
    m = _DAYS.search(cell_html)
    if m:
        days = int(m.group(1))
        cls = "soon" if days <= 8 else ("mid" if days <= 21 else "far")
    else:
        cls = "far"  # rolling / no countdown
    return '<span class="due %s">%s</span>' % (cls, cell_html)


def to_html(markdown, title):
    body, table, in_list = [], [], False

    def close_list():
        nonlocal in_list
        if in_list:
            body.append("</ul>")
            in_list = False

    def flush_table():
        if not table:
            return
        body.append('<div class="tablewrap"><table>')
        headers = table[0]
        is_deadline_table = headers and headers[-1].strip().lower() == "closes"
        is_si_table = headers and headers[0].strip().lower() == "instrument"
        body.append("<tr>" + "".join("<th>%s</th>" % _inline(c) for c in headers) + "</tr>")
        for row in table[2:]:  # skip separator row
            cells = [_inline(c) for c in row]
            if is_deadline_table and cells:
                cells[-1] = _due_chip(cells[-1])
            if is_si_table and len(cells) >= 2:
                cells[1] = _proc_chip(cells[1])
            body.append("<tr>" + "".join("<td>%s</td>" % c for c in cells) + "</tr>")
        body.append("</table></div>")
        table.clear()

    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("|"):
            close_list()
            table.append([c.strip() for c in stripped.strip("|").split("|")])
            continue
        flush_table()
        if not stripped:
            close_list()
            continue
        if stripped.startswith("### "):
            close_list(); body.append("<h3>%s</h3>" % _inline(stripped[4:]))
        elif stripped.startswith("## "):
            close_list(); body.append("<h2>%s</h2>" % _inline(stripped[3:]))
        elif stripped.startswith("# "):
            close_list(); body.append("<h1>%s</h1>" % _inline(stripped[2:]))
        elif stripped.startswith("> "):
            close_list(); body.append('<p class="banner">%s</p>' % _inline(stripped[2:]))
        elif stripped.startswith("- "):
            if not in_list:
                body.append("<ul>"); in_list = True
            body.append("<li>%s</li>" % _inline(stripped[2:]))
        elif stripped == "---":
            close_list(); body.append("<hr>")
        elif stripped.startswith("*") and stripped.endswith("*") and not stripped.startswith("**"):
            close_list(); body.append('<p class="key">%s</p>' % _inline(stripped.strip("*")))
        else:
            close_list(); body.append("<p>%s</p>" % _inline(stripped))
    flush_table()
    close_list()

    return _PAGE.format(title=html_lib.escape(title), body="\n".join(body))


_PAGE = """<!doctype html>
<html lang="en-GB"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>{title}</title>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700;900&display=swap" rel="stylesheet">
<style>
/* CitizenGO brand: Roboto; principal palette #4285f4 / #FFFFFF / #EEEEEE / #52575C;
   secondary palette (#DB544F, #55B159, #FFEBAD) reserved for UX elements (tags). */
body {{ font: 16px/1.6 Roboto, -apple-system, "Segoe UI", sans-serif; color: #52575C;
       background: #FFFFFF; max-width: 62rem; margin: 0 auto; padding: 0 1.5rem 2rem; }}
.masthead {{ display: flex; align-items: center; gap: .6rem; padding: 1.1rem 0;
             border-bottom: 4px solid #4285f4; margin-bottom: 1.2rem; }}
.masthead .logo {{ height: 2.6rem; width: auto; }}
.masthead .product {{ font-size: 1.05rem; font-weight: 500; color: #52575C; }}
h1 {{ font-weight: 700; color: #52575C; font-size: 1.55rem; margin: .2rem 0 .4rem; }}
h2 {{ font-weight: 700; color: #4285f4; margin-top: 2rem; font-size: 1.2rem; }}
h3 {{ font-weight: 500; color: #52575C; }}
.banner {{ background: #EEEEEE; border-left: 4px solid #4285f4; padding: .7rem 1rem;
           border-radius: 0 4px 4px 0; }}
.key {{ font-style: italic; color: #52575C; opacity: .75; font-size: .88em; }}
.tag {{ display: inline-block; font-size: .72em; font-weight: 700; letter-spacing: .04em;
        padding: .1em .55em; border-radius: 3px; vertical-align: .08em; }}
.tag.act {{ background: #DB544F; color: #FFFFFF; }}
.tag.watch {{ background: #FFEBAD; color: #52575C; }}
.tag.note {{ background: #EEEEEE; color: #52575C; }}
.kind {{ display: inline-block; font-size: .68em; font-weight: 700; letter-spacing: .05em;
        border-radius: 3px; padding: .14em .5em; white-space: nowrap; }}
.kind.consult {{ background: #4285f4; color: #FFFFFF; }}
.kind.evidence {{ background: #FFFFFF; color: #4285f4; border: 1px solid #4285f4; }}
.due {{ display: inline-block; font-weight: 700; font-size: .85em; padding: .2em .65em;
       border-radius: 4px; white-space: nowrap; }}
.due.far {{ background: #EEEEEE; color: #52575C; }}
.due.mid {{ background: #FFEBAD; color: #52575C; }}
.due.soon {{ background: #DB544F; color: #FFFFFF; }}
.kindchip {{ display: inline-block; font-size: .68em; font-weight: 700; letter-spacing: .04em;
            border-radius: 999px; padding: .1em .6em; background: #4285f4; color: #FFFFFF;
            white-space: nowrap; vertical-align: .09em; }}
.proc {{ display: inline-block; font-size: .78em; font-weight: 700; color: #4285f4;
        border: 1px solid #4285f4; border-radius: 3px; padding: .08em .45em;
        white-space: nowrap; cursor: help; border-bottom-style: dotted; }}
.tablewrap {{ overflow-x: auto; }}
table {{ border-collapse: collapse; width: 100%; font-size: .92em; }}
th, td {{ border: 1px solid #EEEEEE; padding: .5rem .65rem; text-align: left;
          vertical-align: top; }}
th {{ background: #4285f4; color: #FFFFFF; font-weight: 500; }}
tr:nth-child(even) {{ background: #EEEEEE44; }}
a {{ color: #4285f4; }}
hr {{ border: 0; border-top: 1px solid #EEEEEE; margin: 2rem 0; }}
nav {{ margin: .8rem 0 1.6rem; font-size: .9em; }}
ul {{ padding-left: 1.3rem; }}
li {{ margin: .45rem 0; }}
</style></head><body>
<div class="masthead"><svg class="logo" viewBox="0 0 350 120" role="img" aria-label="CitizenGO"><g transform="rotate(-8 175 60)"><text x="6" y="80" font-family="Roboto, sans-serif" font-weight="900" font-size="54" letter-spacing="1.5" fill="#4285f4">CITIZEN</text><circle cx="292" cy="56" r="45" fill="#4285f4"/><text x="292" y="74" text-anchor="middle" font-family="Roboto, sans-serif" font-weight="900" font-size="46" fill="#FFFFFF">GO</text></g></svg><span class="product">Parliamentary Monitor</span></div>
{body}
</body></html>
"""

QUESTIONS_PAGE = """# Written questions and answers in full - w/c {week}

Every question that matched our campaign areas this week, with the text as
asked and the minister's answer in full. The weekly edition groups these by
area and trims both; this page is where the untrimmed text lives.

{tables}
"""


PETITIONS_PAGE = """# E-petitions on our ground

Every open petition to Westminster, the Senedd and Holyrood matching our campaign
areas, refreshed weekly. At Westminster 10,000 signatures earn a Government
response and 100,000 a Commons debate; at the Senedd 250 earn referral to the
Petitions Committee and 10,000 a Plenary debate. The movement column is
the early warning: a petition gaining thousands a week is on its way to a
debate months before the diary shows one. Signatures as of {seen}.

{tables}
"""

HIDDEN_AREAS = (11,)   # migration: collated, never campaigned, shown nowhere


def petition_rows(conn, hidden=HIDDEN_AREAS, excluded=None):
    """The latest sweep's petitions, each with its movement since the sweep
    before. Migration-only petitions are left out, as everywhere else, and
    so are ids named in settings.petition_exclusions (already-collated rows
    included, so an exclusion takes effect on the next build, not the next
    sweep)."""
    import json
    if excluded is None:
        try:
            import yaml
            from src.ingest import petitions as _pet
            with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                   "config", "settings.yaml"), encoding="utf-8") as fh:
                excluded = _pet.exclusions(yaml.safe_load(fh) or {})
        except Exception:                                   # noqa: BLE001
            excluded = set()
    try:
        latest = conn.execute("SELECT MAX(last_seen) FROM petitions").fetchone()[0]
    except Exception:                                       # noqa: BLE001
        return None, []
    if not latest:
        return None, []
    rows = []
    for r in conn.execute(
            "SELECT id, action, url, signatures, areas, milestone, first_seen, last_seen, "
            "scheduled_debate_date, debate_reached, response_reached "
            "FROM petitions WHERE last_seen = ? ORDER BY signatures DESC", (latest,)):
        if r["id"] in excluded:
            continue
        areas = [a for a in json.loads(r["areas"] or "[]") if a not in hidden]
        if not areas:
            continue
        prev = conn.execute(
            "SELECT signatures FROM petition_snapshots WHERE petition_id = ? AND captured_at < ? "
            "ORDER BY captured_at DESC LIMIT 1", (r["id"], latest)).fetchone()
        rows.append({"id": r["id"], "action": r["action"], "url": r["url"],
                     "signatures": r["signatures"], "areas": areas, "milestone": r["milestone"],
                     "first_seen": r["first_seen"], "new": r["first_seen"] == latest,
                     "delta": (r["signatures"] - prev[0]) if prev else None,
                     "scheduled_debate_date": r["scheduled_debate_date"]})
    return latest, rows


def dv_petition_rows(conn, nation, hidden=HIDDEN_AREAS):
    """The latest sweep's devolved petitions for one nation, with movement."""
    import json
    try:
        latest = conn.execute("SELECT MAX(last_seen) FROM dv_petitions WHERE nation = ?", (nation,)).fetchone()[0]
    except Exception:                                       # noqa: BLE001
        return None, []
    if not latest:
        return None, []
    rows = []
    for r in conn.execute("SELECT key, id, action, url, signatures, areas, milestone, state, first_seen "
                          "FROM dv_petitions WHERE nation = ? AND last_seen = ? ORDER BY signatures DESC", (nation, latest)):
        areas = [a for a in json.loads(r["areas"] or "[]") if a not in hidden]
        if not areas:
            continue
        prev = conn.execute("SELECT signatures FROM dv_petition_snapshots WHERE key = ? AND captured_at < ? "
                            "ORDER BY captured_at DESC LIMIT 1", (r["key"], latest)).fetchone()
        rows.append({"id": r["id"], "action": r["action"], "url": r["url"], "signatures": r["signatures"],
                     "areas": areas, "milestone": r["milestone"] or r["state"] or "", "first_seen": r["first_seen"],
                     "new": r["first_seen"] == latest, "delta": (r["signatures"] - prev[0]) if prev else None})
    return latest, rows


def _movement(row):
    if row["delta"] is None:
        return "new to the monitor"
    d = row["delta"]
    return "{0}{1:,}".format("+" if d >= 0 else "\u2212", abs(d))


def build_petitions_page(site_dir, conn, area_labels=None):
    """The petitions companion page (Christopher, 2026-09-07). Petitions are
    kept OUT of the weekly report by his decision the same day; this page is
    where the collated record surfaces. Public record only, no judgement:
    every figure on it is petition.parliament.uk's own."""
    latest, rows = petition_rows(conn)
    devolved = [(label, dv_petition_rows(conn, nation)) for label, nation in
                (("Senedd", "wales"), ("Holyrood", "scotland"))]
    if not rows and not any(dv[1] for _, dv in devolved):
        return None
    labels = area_labels or {}

    def cell(row):
        link = "[{0}]({1})".format(row["action"].replace("|", "/"), row["url"])
        return link + (" *(new)*" if row["new"] else "")

    def areas(row):
        return ", ".join(str(labels.get(a, a)) for a in row["areas"])

    blocks = []
    movers = sorted([r for r in rows if r["delta"] is not None and r["delta"] > 0],
                    key=lambda r: -r["delta"])[:8]
    if movers:
        blocks.append("## Moving fastest this week\n")
        blocks.append("| Petition | Signatures | This week | Where it stands |")
        blocks.append("|---|---|---|---|")
        for r in movers:
            blocks.append("| {0} | {1:,} | {2} | {3} |".format(cell(r), r["signatures"], _movement(r), r["milestone"] or ""))
        blocks.append("")
    def table(rows_):
        blocks.append("| Petition | Signatures | This week | Where it stands | Areas | First seen |")
        blocks.append("|---|---|---|---|---|---|")
        for r in rows_:
            blocks.append("| {0} | {1:,} | {2} | {3} | {4} | {5} |".format(
                cell(r), r["signatures"], _movement(r), (r["milestone"] or "").replace("|", "/"),
                areas(r), r["first_seen"] or ""))
        blocks.append("")

    if rows:
        blocks.append("## Westminster ({0})\n".format(len(rows)))
        table(rows)
    # The Senedd's and Holyrood's (Christopher, 2026-09-07): the Senedd
    # refers a petition to its committee at 250 signatures and debates it
    # at 10,000; Holyrood has no signature thresholds, so its column reads
    # the petition's status instead.
    for label, (seen, dv_rows) in devolved:
        if dv_rows:
            blocks.append("## {0} ({1})\n".format(label, len(dv_rows)))
            table(dv_rows)
    markdown = PETITIONS_PAGE.format(seen=latest or max(s for s, _ in (dv for _, dv in devolved) if s),
                                     tables="\n".join(blocks))
    page = to_html(markdown, "E-petitions on our ground - {0}".format(latest))
    path = os.path.join(site_dir, "petitions.html")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(page)
    return path


def _question_row(r):
    """One row of the questions table. Shared by the digest rows and the
    background rows, which built it twice identically and could drift.

    The answer is carried here in FULL. The edition trims it to about
    fifty words and tells the reader the rest is on this page, so if this
    column were also a summary the promise would be empty (2026-09-24).
    Pipes are escaped: an answer quoting a table would otherwise split the
    row and silently shift every later cell one column left.
    """
    who = r.get("member") or "A member"
    detail = ", ".join(x for x in (r.get("party"), r.get("seat")) if x)
    if detail:
        who = "{0} ({1})".format(who, detail)
    heading = r.get("heading") or "Question"
    link = "[{0}]({1})".format(heading, r["url"]) if r.get("url") else heading
    cell = lambda t: " ".join((t or "").split()).replace("|", "\\|") or "-"
    answer = cell(r.get("answer_text"))
    if r.get("holding"):
        answer = "Holding answer - no substantive reply yet."
    return "| {0} | {1} | {2} | {3} | {4} | {5} | {6} |".format(
        who, link, r.get("department") or "-", r.get("house") or "-",
        r.get("date") or "-", cell(r.get("question_text")), answer)


def build_questions_page(site_dir, week, pq_rows, area_labels=None, background=None):
    """The companion page the edition's question tables link to.

    Holds every matched question with the text as asked AND the minister's
    answer in full -- the detail that would swamp the edition, which trims
    both. Same passphrase gate as the rest of the site; no owner names,
    since the rows carry none.
    """
    # Same precondition as the edition: no issue area, no appearance. An
    # "Other" heading would only advertise our false positives to allies.
    rows = [r for r in (pq_rows or []) if r.get("area")]
    if not rows:
        return None
    grouped = {}
    for row in rows:
        grouped.setdefault(row.get("area_label") or "Other", []).append(row)

    header = ("| Member | Question | Asked of | House | Answered | "
              "The question as asked | The answer given |",
              "|---|---|---|---|---|---|---|")
    blocks = []
    for label in sorted(grouped, key=lambda k: (-len(grouped[k]), k)):
        rows = grouped[label]
        blocks.append("## {0} ({1})\n".format(label, len(rows)))
        blocks.extend(header)       # every table repeats its header
        blocks.extend(_question_row(r) for r in rows)
        blocks.append("")
    bg = [r for r in (background or []) if r.get("area")]
    if bg:
        blocks.append("## Also captured, scored as background ({0})\n".format(len(bg)))
        blocks.append("These matched our areas but were judged background rather "
                      "than digest material, so they do not appear in the edition.\n")
        blocks.extend(header)
        blocks.extend(_question_row(r) for r in bg)
        blocks.append("")

    markdown = QUESTIONS_PAGE.format(week=week, tables="\n".join(blocks))
    page = to_html(markdown, "Written questions and answers in full - w/c {0}".format(week))
    path = os.path.join(site_dir, "questions.html")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(page)
    return path


def build_site(site_dir, week, partner_markdown, archive_weeks, pq_rows=None, pq_background=None):
    """Write index.html (latest) + archive/<week>.html + auth middleware."""
    os.makedirs(os.path.join(site_dir, "archive"), exist_ok=True)
    build_questions_page(site_dir, week, pq_rows or [], background=pq_background)
    title = "Parliamentary Monitor (partner edition) - w/c {0}".format(week)
    page = to_html(partner_markdown, title)

    nav = ('<nav><a href="/mp-votes.html">How did my MP vote?</a> | '
           '<a href="/5ca-sheets.html">5CA sheets</a> | '
           '<a href="/5ca-peers.html">5CA peers</a> | '
           '<a href="/5ca-matrix.html">Cross-issue matrix</a> | '
           '<a href="/5ca-peers-matrix.html">Peers matrix</a> | '
           '<a href="/5ca.html">Five Column Analysis tracker</a> | '
           '<a href="/questions.html">Questions and answers</a> | '
           '<a href="/petitions.html">E-petitions on our ground</a> | '
           '<a href="/issues.html">Issue pages</a><br>Archive: ' +
           " | ".join('<a href="/archive/{0}.html">{0}</a>'.format(w)
                      for w in sorted(archive_weeks, reverse=True)) + "</nav>")
    index = page.replace("</h1>", "</h1>\n" + nav, 1)

    with open(os.path.join(site_dir, "index.html"), "w", encoding="utf-8") as handle:
        handle.write(index)
    with open(os.path.join(site_dir, "archive", "{0}.html".format(week)), "w", encoding="utf-8") as handle:
        handle.write(page)
    _write_scaffold(site_dir)
    return os.path.join(site_dir, "index.html")


def _write_scaffold(site_dir):
    with open(os.path.join(site_dir, "middleware.js"), "w", encoding="utf-8") as handle:
        handle.write('''// Password-only gate: one box, no username (Christopher, 2026-08-05).
// Fails closed -- no PARTNER_PASSPHRASE env var, no access.
export const config = { matcher: ["/((?!favicon.ico).*)"] };

const FORM = (retry) => `<!doctype html>
<html lang="en-GB"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Parliamentary Monitor</title>
<link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&display=swap" rel="stylesheet">
<style>
body { font: 15px/1.6 Roboto, sans-serif; color:#52575C; display:flex; min-height:90vh;
       align-items:center; justify-content:center; margin:0; padding:1rem; }
.card { border:1px solid #EEEEEE; border-radius:8px; padding:2rem; max-width:24rem; width:100%; }
h1 { font-size:1.15rem; color:#52575C; border-bottom:4px solid #4285f4;
     padding-bottom:.4rem; margin:0 0 .3rem; }
p { font-size:.9em; }
input { width:100%; padding:.6rem; font:inherit; border:1px solid #C8D0DC;
        border-radius:4px; box-sizing:border-box; }
button { margin-top:.7rem; width:100%; padding:.6rem; font:inherit; font-weight:700;
         background:#4285f4; color:#FFF; border:0; border-radius:4px; cursor:pointer; }
.err { color:#DB544F; font-size:.86em; font-weight:700; }
</style></head><body>
<div class="card">
<h1>Parliamentary Monitor</h1>
<p>Coalition partner edition, prepared by CitizenGO UK. Please enter the password you were given.</p>
${retry ? '<p class="err">That password was not recognised.</p>' : ''}
<form method="POST">
<input type="password" name="password" placeholder="Password" autofocus autocomplete="current-password">
<button type="submit">Open the briefing</button>
</form>
</div></body></html>`;

export default async function middleware(request) {
  const phrase = process.env.PARTNER_PASSPHRASE;
  if (!phrase) {
    return new Response("Access is not configured.", { status: 503 });
  }
  const cookie = request.headers.get("cookie") || "";
  if (cookie.split(/;\\s*/).includes("pm_access=" + encodeURIComponent(phrase))) {
    return; // already unlocked: serve the static page
  }
  if (request.method === "POST") {
    const body = await request.formData().catch(() => null);
    if (body && body.get("password") === phrase) {
      return new Response(null, {
        status: 303,
        headers: {
          location: new URL(request.url).pathname,
          "set-cookie": "pm_access=" + encodeURIComponent(phrase) +
            "; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=7776000",
        },
      });
    }
    return new Response(FORM(true), {
      status: 401, headers: { "content-type": "text/html; charset=utf-8" },
    });
  }
  return new Response(FORM(false), {
    status: 401, headers: { "content-type": "text/html; charset=utf-8" },
  });
}
''')
    with open(os.path.join(site_dir, "vercel.json"), "w", encoding="utf-8") as handle:
        handle.write('{ "version": 2, "public": false, "github": { "enabled": false } }\n')
