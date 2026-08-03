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
MP_SECTION = re.compile(r"\n## 11\. MP intelligence notes\n.*?(?=\n## |\n---)", re.S)
EMPTY_PARENS = re.compile(r" \(\s*\)")

BANNER = ("> **Coalition partner edition**, prepared by CitizenGO UK from Parliament's "
          "open data feeds. Priority tags reflect CitizenGO's own campaign assessment. "
          "Please do not circulate beyond your organisation.\n")


def owner_names(markdown):
    """Names appearing in Owner fields (to scrub from prose as well)."""
    return sorted(set(re.findall(r"Owner: ([^);\n]+)", markdown)))


def redact(markdown, extra_names=()):
    names = set(owner_names(markdown)) | set(extra_names)
    out = MP_SECTION.sub("", markdown)
    out = OWNER_FIELD.sub("", out)
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

_INLINE_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_BOLD = re.compile(r"\*\*([^*]+)\*\*")


def _inline(text):
    text = html_lib.escape(text, quote=False)
    text = _BOLD.sub(r"<strong>\1</strong>", text)
    text = _INLINE_LINK.sub(r'<a href="\2">\1</a>', text)
    return text


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
        body.append("<tr>" + "".join("<th>%s</th>" % _inline(c) for c in table[0]) + "</tr>")
        for row in table[2:]:  # skip separator row
            body.append("<tr>" + "".join("<td>%s</td>" % _inline(c) for c in row) + "</tr>")
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
<style>
body {{ font: 16px/1.55 -apple-system, "Segoe UI", Roboto, sans-serif; color: #1a2333;
       max-width: 62rem; margin: 0 auto; padding: 1.5rem; }}
h1 {{ color: #1a2b4a; border-bottom: 3px solid #1a2b4a; padding-bottom: .3rem; }}
h2 {{ color: #1a2b4a; margin-top: 2rem; }}
.banner {{ background: #f4f1e8; border-left: 4px solid #b58900; padding: .7rem 1rem; }}
.key {{ font-style: italic; color: #555; font-size: .9em; }}
.tablewrap {{ overflow-x: auto; }}
table {{ border-collapse: collapse; width: 100%; font-size: .92em; }}
th, td {{ border: 1px solid #cbd2dd; padding: .45rem .6rem; text-align: left;
          vertical-align: top; }}
th {{ background: #1a2b4a; color: #fff; }}
tr:nth-child(even) {{ background: #f5f7fa; }}
a {{ color: #1a5ba6; }}
hr {{ border: 0; border-top: 1px solid #cbd2dd; margin: 2rem 0; }}
nav {{ margin: 1rem 0 2rem; font-size: .9em; }}
</style></head><body>
{body}
</body></html>
"""


def build_site(site_dir, week, partner_markdown, archive_weeks):
    """Write index.html (latest) + archive/<week>.html + auth middleware."""
    os.makedirs(os.path.join(site_dir, "archive"), exist_ok=True)
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
