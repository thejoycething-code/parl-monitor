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

QUESTIONS_PAGE = """# Written questions in full - w/c {week}

Every question that matched our campaign areas this week, with the text as
asked. The weekly edition groups these by area and links here for detail.

{tables}
"""


def build_questions_page(site_dir, week, pq_rows, area_labels=None):
    """The companion page the edition's question tables link to.

    Holds every matched question with the text as asked -- the detail that
    would swamp the edition. Same passphrase gate as the rest of the site;
    no owner names, since the rows carry none.
    """
    if not pq_rows:
        return None
    grouped = {}
    for row in pq_rows:
        grouped.setdefault(row.get("area_label") or "Other", []).append(row)

    header = ("| Member | Question | Asked of | House | Answered | The question as asked |",
              "|---|---|---|---|---|---|")
    blocks = []
    for label in sorted(grouped, key=lambda k: (-len(grouped[k]), k)):
        rows = grouped[label]
        blocks.append("## {0} ({1})\n".format(label, len(rows)))
        blocks.extend(header)       # every table repeats its header
        for r in rows:
            who = r.get("member") or "A member"
            detail = ", ".join(x for x in (r.get("party"), r.get("seat")) if x)
            if detail:
                who = "{0} ({1})".format(who, detail)
            heading = r.get("heading") or "Question"
            link = "[{0}]({1})".format(heading, r["url"]) if r.get("url") else heading
            asked = " ".join((r.get("question_text") or "").split()) or "-"
            blocks.append("| {0} | {1} | {2} | {3} | {4} | {5} |".format(
                who, link, r.get("department") or "-", r.get("house") or "-",
                r.get("date") or "-", asked))
        blocks.append("")
    markdown = QUESTIONS_PAGE.format(week=week, tables="\n".join(blocks))
    page = to_html(markdown, "Written questions in full - w/c {0}".format(week))
    path = os.path.join(site_dir, "questions.html")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(page)
    return path


def build_site(site_dir, week, partner_markdown, archive_weeks, pq_rows=None):
    """Write index.html (latest) + archive/<week>.html + auth middleware."""
    os.makedirs(os.path.join(site_dir, "archive"), exist_ok=True)
    build_questions_page(site_dir, week, pq_rows or [])
    title = "Parliamentary Monitor (partner edition) - w/c {0}".format(week)
    page = to_html(partner_markdown, title)

    nav = "<nav>Archive: " + " | ".join(
        '<a href="/archive/{0}.html">{0}</a>'.format(w) for w in sorted(archive_weeks, reverse=True)
    ) + "</nav>"
    index = page.replace("</h1>", "</h1>\n" + nav, 1)

    with open(os.path.join(site_dir, "index.html"), "w", encoding="utf-8") as handle:
        handle.write(index)
    with open(os.path.join(site_dir, "archive", "{0}.html".format(week)), "w", encoding="utf-8") as handle:
        handle.write(page)
    _write_scaffold(site_dir)
    return os.path.join(site_dir, "index.html")


def _write_scaffold(site_dir):
    with open(os.path.join(site_dir, "middleware.js"), "w", encoding="utf-8") as handle:
        handle.write('''// Shared-passphrase gate (fail closed: no env var, no access).
export const config = { matcher: ["/((?!favicon.ico).*)"] };

export default function middleware(request) {
  const phrase = process.env.PARTNER_PASSPHRASE;
  const auth = request.headers.get("authorization") || "";
  if (phrase && auth === "Basic " + btoa("partners:" + phrase)) {
    return; // authenticated: serve the static page
  }
  return new Response("Authentication required.", {
    status: 401,
    headers: { "WWW-Authenticate": 'Basic realm="Parliamentary Monitor"' },
  });
}
''')
    with open(os.path.join(site_dir, "vercel.json"), "w", encoding="utf-8") as handle:
        handle.write('{ "version": 2, "public": false, "github": { "enabled": false } }\n')
