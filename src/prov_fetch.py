"""The fetch context every provincial collector runs inside.

One object carries what each src/ingest/prov_<code>.py needs, so the
modules stay parsers plus a short `collect()`:

  * the shared HttpClient (honest CitizenGO User-Agent with contact, retries,
    a per-host throttle of at least 1.1 s -- docs/canada-provinces-scope.md);
  * robots.txt, read once per host and HONOURED: a disallowed URL is never
    requested and is recorded as a gap; a Crawl-delay larger than the
    throttle raises that HOST's interval (HttpClient.set_host_throttle; New
    Brunswick asks for 10 s, and the run waits 10 s between its requests). A robots.txt
    that answers 404 -- or, as lims.leg.bc.ca does, an HTML error page with
    status 404 -- means no rules;
  * the run's budget (src/drain), its record --limit and --dry-run;
  * the gaps collected on the way, written once at the end through
    db.record_gaps so a run log is never the only record.

The vote collectors archive nothing to data/raw: provincial PDFs run to a
megabyte each and the URL stored on every row is the provenance (as for the
Canada Gazette). The Hansard readers (src/prov_speeches.py) DO archive each
day's transcript, by passing archive=True: a speech is stored only when it
is on our ground, so the raw day is the only record of everything else said.
"""

from __future__ import annotations

import html as _html
import io
import re
from urllib.parse import urlsplit

from src.http import FetchError

MIN_THROTTLE = 1.1


class Context:
    def __init__(self, conn, client, prov, feed=None, since=None, until=None,
                 limit=None, budget=None, dry_run=False, refresh=False, log=print,
                 robots=True):
        self.conn = conn
        self.client = client
        self.prov = prov
        self.feed = feed or "prov-" + prov
        self.since = since
        self.until = until
        self.limit = limit
        self.budget = budget
        self.dry_run = dry_run
        self.refresh = refresh
        self.log = log
        self.robots = robots
        self.gaps = []
        self.records_read = 0
        self._robots = {}
        self._stopped = False
        if getattr(client, "throttle", None) is not None and client.throttle < MIN_THROTTLE:
            client.throttle = MIN_THROTTLE

    # -- bookkeeping ----------------------------------------------------------

    def gap(self, detail):
        self.gaps.append(detail)
        self.log("  [gap] {0}".format(str(detail)[:160]))

    def in_window(self, date):
        if not date:
            return True
        if self.since and date < self.since:
            return False
        if self.until and date > self.until:
            return False
        return True

    def stop(self):
        """True once the record limit or the clock is spent; says so once."""
        if self._stopped:
            return True
        if self.limit is not None and self.records_read >= self.limit:
            self.log("  record cap ({0}) reached; the rest lands on the next run "
                     "-- disclosed, not silent".format(self.limit))
            self._stopped = True
        elif self.budget is not None and self.budget.exhausted():
            self.log(self.budget.disclose("records", self.records_read))
            self._stopped = True
        return self._stopped

    # -- robots ---------------------------------------------------------------

    def _parser(self, url):
        parts = urlsplit(url)
        host = parts.netloc
        if host not in self._robots:
            try:
                text = self.client.get_text("{0}://{1}/robots.txt".format(parts.scheme, host),
                                            self.feed, "robots-" + host, archive=False)
            except FetchError:
                text = ""             # no robots.txt: no rules
            rp = Robots(text)
            # Two independent readers, and a URL is fetched only if BOTH allow
            # it: the Robots class (built for Ontario's '/*?' wildcard) and
            # star_rules (built for Quebec's rules split across many '*'
            # groups and its literal query paths). They were written the same
            # day by two builds; neither is allowed to be the weaker one.
            rp.star_rules = star_rules(text, self.client.user_agent)
            delay = rp.crawl_delay(self.client.user_agent)
            if delay and float(delay) > (self.client.throttle or 0):
                self.log("  {0}: robots.txt Crawl-delay {1}s honoured".format(host, delay))
                if hasattr(self.client, "set_host_throttle"):
                    # Per host: legnb.ca's 10 s must not slow every other host.
                    self.client.set_host_throttle(host, float(delay))
                else:
                    self.client.throttle = float(delay)
            self._robots[host] = rp
        return self._robots[host]

    def allowed(self, url):
        if not self.robots:
            return True
        rp = self._parser(url)
        if not (rp.can_fetch(self.client.user_agent, url) and rp.can_fetch("*", url)):
            return False
        return rule_allows(getattr(rp, "star_rules", []), url)

    # -- fetches: None on failure, with the gap recorded ------------------------

    def _guard(self, url):
        if not self.allowed(url):
            self.gap("robots.txt disallows {0}; not fetched".format(url))
            return False
        return True

    def text(self, url, slug, encoding=None, archive=False):
        if not self._guard(url):
            return None
        try:
            return self.client.get_text(url, self.feed, slug, archive=archive,
                                        fallback_encoding=encoding)
        except FetchError as exc:
            self.gap("{0}: {1}".format(url, exc.cause))
            return None

    def bytes(self, url, slug, archive=False):
        if not self._guard(url):
            return None
        try:
            return self.client.get_bytes(url, self.feed, slug, archive=archive)
        except FetchError as exc:
            self.gap("{0}: {1}".format(url, exc.cause))
            return None

    def post_form(self, url, fields, slug):
        """An HTML form POST (Quebec's month-by-month sitting index)."""
        if not self._guard(url):
            return None
        try:
            return self.client.post_form(url, fields, self.feed, slug)
        except FetchError as exc:
            self.gap("{0} (form post): {1}".format(url, exc.cause))
            return None

    def post_json(self, url, body, slug):
        if not self._guard(url):
            return None
        try:
            return self.client.post_json(url, body, self.feed, slug)
        except (FetchError, ValueError) as exc:
            self.gap("{0}: {1}".format(url, getattr(exc, "cause", exc)))
            return None


# -- robots.txt -------------------------------------------------------------

class Robots:
    """robots.txt as the major crawlers read it (RFC 9309).

    Written because urllib.robotparser cannot honour Ontario's: ola.org
    ends its file with a SECOND `User-agent: *` group holding `Disallow: /*?`
    (no query strings), and the standard library both ignores every `*`
    group after the first and treats `*` and `$` in a path literally -- so
    it would have let us fetch every query-string URL ola.org forbids.

      * groups naming the same agent are merged;
      * our agent uses the groups whose name is a token of its product name
        ('citizengo-parlmonitor'), else the `*` groups. Manitoba's groups for
        GPTBot, ClaudeBot and the rest do not name us; if Manitoba ever names
        us, this obeys it (docs/canada-provinces-scope.md, "Decisions");
      * `*` matches any run of characters, a trailing `$` anchors the end;
      * the longest matching rule wins, and Allow wins a tie.
    """

    def __init__(self, text):
        self.groups = []           # [(agents, [(allow, pattern)], crawl_delay)]
        agents, rules, delay, in_rules = [], [], None, False
        for raw in (text or "").splitlines():
            line = raw.split("#", 1)[0].strip()
            if ":" not in line:
                continue
            field, _, value = line.partition(":")
            field, value = field.strip().lower(), value.strip()
            if field == "user-agent":
                if in_rules:
                    self.groups.append((agents, rules, delay))
                    agents, rules, delay, in_rules = [], [], None, False
                agents.append(value.lower())
            elif field in ("allow", "disallow"):
                in_rules = True
                if agents and value:
                    rules.append((field == "allow", value))
            elif field == "crawl-delay":
                in_rules = True
                try:
                    delay = float(value)
                except ValueError:
                    pass
        if agents:
            self.groups.append((agents, rules, delay))

    def _groups_for(self, user_agent):
        product = (user_agent or "*").split("/")[0].strip().lower()
        named = [g for g in self.groups
                 if any(a != "*" and a and a in product for a in g[0])] if product != "*" else []
        return named or [g for g in self.groups if "*" in g[0]]

    @staticmethod
    def _matches(pattern, path):
        anchored = pattern.endswith("$")
        body = pattern[:-1] if anchored else pattern
        rx = "^" + ".*".join(re.escape(p) for p in body.split("*")) + ("$" if anchored else "")
        return re.match(rx, path) is not None

    def can_fetch(self, user_agent, url):
        parts = urlsplit(url)
        path = (parts.path or "/") + ("?" + parts.query if parts.query else "")
        best = None                  # (length, allow)
        for _agents, rules, _delay in self._groups_for(user_agent):
            for allow, pattern in rules:
                if self._matches(pattern, path):
                    key = (len(pattern), allow)
                    if best is None or key > best:
                        best = key
        return True if best is None else best[1]

    def crawl_delay(self, user_agent):
        delays = [g[2] for g in self._groups_for(user_agent) if g[2]]
        if not delays and (user_agent or "*") != "*":
            delays = [g[2] for g in self._groups_for("*") if g[2]]
        return max(delays) if delays else None

# -- robots.txt: every group that names us or '*' -----------------------------

def star_rules(text, user_agent):
    """[(allow, path)] from EVERY group of robots.txt that names '*' or us.

    urllib.robotparser keeps only the FIRST 'User-agent: *' group and drops
    the rest. assnat.qc.ca writes one group per rule (2 October 2026): its
    'Disallow: /json/' -- the vote register's data feed -- sits in the
    seventh '*' group, so the standard parser reported the feed ALLOWED. It
    also failed to match the six disallowed /Media/Process.aspx?MediaId=...
    documents literally, because it re-quotes the query. This reads every
    matching group and compares paths literally (and unquoted), longest rule
    first, as the robots standard says."""
    rules, agents, in_rules = [], [], False
    ua = (user_agent or "").lower()
    for raw in (text or "").splitlines():
        line = raw.split("#", 1)[0].strip().lstrip("\ufeff")
        if not line or ":" not in line:
            continue
        field, _, value = line.partition(":")
        field, value = field.strip().lower(), value.strip()
        if field == "user-agent":
            if in_rules:
                agents, in_rules = [], False
            agents.append(value.lower())
            continue
        if field not in ("allow", "disallow"):
            continue
        in_rules = True
        ours = any(a == "*" or (a and a in ua) for a in agents)
        if ours and value:
            rules.append((field == "allow", value))
    return rules


def rule_allows(rules, url):
    from urllib.parse import unquote
    parts = urlsplit(url)
    target = parts.path + ("?" + parts.query if parts.query else "")
    forms = {target, unquote(target)}
    best = None

    def matches(pattern, target):
        # RFC 9309: '*' is any run of characters, a trailing '$' anchors the
        # end; everything else is literal and matches from the start.
        anchored = pattern.endswith("$")
        body = pattern[:-1] if anchored else pattern
        rx = ".*".join(re.escape(part) for part in body.split("*"))
        return re.match(rx + ("$" if anchored else ""), target) is not None

    for allow, path in rules:
        if any(matches(path, f) or matches(unquote(path), f) for f in forms):
            if best is None or len(path) > len(best[1]) or (len(path) == len(best[1]) and allow):
                best = (allow, path)
    return True if best is None else best[0]


# -- document helpers -------------------------------------------------------

class Unreadable(Exception):
    """A record that is truncated or not the document it claims to be. It is
    a GAP, never an empty sitting (the NB Hansard of 20 November 2025)."""


def pdf_text(raw, pages=None, joiner="\n=====PAGE\n"):
    """Text of a PDF's pages (all, or the given indexes)."""
    if not raw or not raw[:5] == b"%PDF-":
        raise Unreadable("not a PDF ({0} bytes)".format(len(raw or b"")))
    if b"%%EOF" not in raw[-2048:]:
        raise Unreadable("truncated PDF: no %%EOF marker in {0} bytes".format(len(raw)))
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(raw))
        idx = range(len(reader.pages)) if pages is None else [
            i for i in pages if i < len(reader.pages)]
        return joiner.join(reader.pages[i].extract_text() or "" for i in idx)
    except Exception as exc:  # pypdf raises a zoo of errors on a damaged file
        raise Unreadable("PDF could not be read: {0}".format(exc))


def glyph_width(text, font_dict, font_size):
    """Advance width of `text` in text-space units, from the font's own
    /Widths (500/1000 em for a glyph it does not list); a font we cannot
    measure falls back to a mean advance of 0.43 em."""
    try:
        widths, first = font_dict.get("/Widths"), int(font_dict.get("/FirstChar", 0))
        if widths is not None:
            ws = [float(w) for w in widths]
            total = 0.0
            for c in text:
                k = ord(c) - first
                total += ws[k] if 0 <= k < len(ws) and ws[k] else 500.0
            return total / 1000.0 * float(font_size or 10.0)
    except Exception:  # noqa: BLE001
        pass
    return len(text) * 0.43 * float(font_size or 10.0)


def pdf_fragments(raw, pages=None, want=None, extents=False):
    """Positioned text of a PDF: [(page, x, y, text)] in drawing order, for
    pages laid out in columns (Ontario's Hansard member list), where plain
    extraction runs the columns together. `pages` may index from the end
    (-1 is the last page); `want`, if given, keeps only pages whose plain
    text contains it. With `extents`, each fragment also carries where it
    ENDS, from its font's glyph widths: (page, x, y, text, x_end), so a
    reader can tell two words drawn apart from one word drawn in pieces."""
    if not raw or not raw[:5] == b"%PDF-":
        raise Unreadable("not a PDF ({0} bytes)".format(len(raw or b"")))
    if b"%%EOF" not in raw[-2048:]:
        raise Unreadable("truncated PDF: no %%EOF marker in {0} bytes".format(len(raw)))
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(raw))
        n = len(reader.pages)
        idx = range(n) if pages is None else sorted({i % n for i in pages if -n <= i < n})
        out = []
        for i in idx:
            got = []

            def visit(text, cm, tm, fd, fs, got=got):
                if text and text.strip():
                    x = round(tm[4] * cm[0] + cm[4], 1)
                    end = x + glyph_width(text, fd or {}, fs) * (tm[0] or 1.0) * (cm[0] or 1.0)
                    got.append((x, round(tm[5] * cm[3] + cm[5], 1), text, round(end, 1)))
            plain = reader.pages[i].extract_text(visitor_text=visit) or ""
            if want and want not in plain:
                continue
            if extents:
                out.extend((i, x, y, t, e) for x, y, t, e in got)
            else:
                out.extend((i, x, y, t) for x, y, t, _e in got)
        return out
    except Exception as exc:
        raise Unreadable("PDF could not be read: {0}".format(exc))


def pdf_rows(raw, pages=None):
    """The text fragments of a PDF's pages WITH their x positions: for the
    tables whose columns plain extraction runs together (New Brunswick's
    members list, Newfoundland's attendance summary, where a name column
    and a district column are both free text).

    [[(y, [(x0, x1, text), ...]), ...] per page], lines top to bottom,
    fragments left to right. Built on pypdf's layout engine, the private
    interface src/ca_gazette_pdf.py already uses; if it moves, the parse
    comes back empty and the caller records a gap."""
    if not raw or not raw[:5] == b"%PDF-":
        raise Unreadable("not a PDF ({0} bytes)".format(len(raw or b"")))
    if b"%%EOF" not in raw[-2048:]:
        raise Unreadable("truncated PDF: no %%EOF marker in {0} bytes".format(len(raw)))
    import logging

    try:
        import pypdf
        from pypdf._text_extraction._layout_mode import _fixed_width_page as fw
        logging.getLogger("pypdf").setLevel(logging.ERROR)
        reader = pypdf.PdfReader(io.BytesIO(raw))
        idx = range(len(reader.pages)) if pages is None else [
            i for i in pages if i < len(reader.pages)]
        out = []
        for i in idx:
            page = reader.pages[i]
            contents = page.get_contents()
            if contents is None:
                out.append([])
                continue
            ops = iter(pypdf.generic.ContentStream(contents, reader, "bytes").operations)
            frags = fw.text_show_operations(ops, page._layout_mode_fonts(), True, None)
            lines = {}
            for f in frags or []:
                if f["text"].strip():
                    lines.setdefault(round(f["ty"]), []).append(
                        (float(f["tx"]), float(f["displaced_tx"]), f["text"]))
            # Fragments of one printed row can sit a point apart (the 2025
            # NL attendance summary set 'Parsons, Jim' 1 pt above his
            # district): rows within 2 pt are one line.
            merged = []
            for y in sorted(lines, reverse=True):
                if merged and merged[-1][0] - y <= 2:
                    merged[-1][1].extend(lines[y])
                else:
                    merged.append((y, list(lines[y])))
            out.append([(y, sorted(fr)) for y, fr in merged])
        return out
    except Unreadable:
        raise
    except Exception as exc:  # pypdf raises a zoo of errors on a damaged file
        raise Unreadable("PDF could not be read: {0}".format(exc))


def join_fragments(frags):
    """One string from left-to-right fragments: a fragment that starts where
    the last one ended (within 1 pt) is the same word."""
    out, end = "", None
    for x0, x1, text in frags:
        if end is not None and x0 - end < 1.0:
            out += text
        else:
            out += (" " if out else "") + text.lstrip()
        end = x1
    return re.sub(r"\s+", " ", out).strip()


def split_columns(frags, edges):
    """Cut one line's fragments into columns at the given left edges (the x
    of each column heading). A fragment belongs to the last column whose
    edge is at or left of its start (2 pt of slack)."""
    cols = [[] for _ in edges]
    for f in frags:
        k = 0
        for j, e in enumerate(edges):
            if f[0] >= e - 2:
                k = j
        cols[k].append(f)
    return [join_fragments(c) for c in cols]


_TAG = re.compile(r"<[^>]+>")
_COMMENT = re.compile(r"<!--.*?-->|<!\[if[^>]*>|<!\[endif\]>|<script.*?</script>|<style.*?</style>",
                      re.S | re.I)


def html_text(fragment):
    """Visible text of an HTML fragment, whitespace collapsed. Tags are
    removed WITHOUT a space, so Word's '<span>Nippi</span>-Albright' stays
    one word; line breaks inside the source become spaces."""
    s = _COMMENT.sub("", fragment or "")
    s = re.sub(r"<br[^>]*>", " ", s, flags=re.I)
    s = _TAG.sub("", s)
    return re.sub(r"\s+", " ", _html.unescape(s)).strip()


def slug(text, max_length=60):
    from src.prov_names import fold
    s = re.sub(r"[^a-z0-9]+", "-", fold(text)).strip("-")
    return s[:max_length].rstrip("-") or "x"


# -- sessions, as each legislature's own index lists them ----------------------
#
# The backfill (tools/prov_collect.py --all-sessions) and the weekly's
# new-session check take the list of sessions from the legislature's OWN
# index page -- a page each collector already reads -- never from a list typed
# into the repo: a session left off a typed list would be skipped in silence,
# while a session the index lists and the parser cannot read is a gap. Each
# module's list_sessions(ctx) returns
#     [{"code": "31-2", "start": "2025-01-01", "end": "2026-12-31" or None}]
# oldest first. Where the index prints years only, a span runs from 1 January
# of the first year to 31 December of the last; an open session ends None.

def session_order(code):
    """(31, 2) for '31-2': sessions compare by legislature, then session."""
    leg, _, sess = str(code).partition("-")
    return int(leg), int(sess or 0)


def year_span(code, first, last=None, open_ended=False):
    """A session spanning whole years ('2010-2011', '2019', '2025-')."""
    first = int(first)
    last = int(last) if last else (None if open_ended else first)
    return {"code": code, "start": "{0}-01-01".format(first),
            "end": "{0}-12-31".format(last) if last else None}


def sessions_sorted(items):
    """De-duplicated by code (the first listing wins), oldest first."""
    seen = {}
    for s in items:
        seen.setdefault(s["code"], s)
    return sorted(seen.values(), key=lambda s: session_order(s["code"]))


def overlaps(session, since=None, until=None):
    """True when the session's span touches [since, until]. A session with
    no known end is open, and overlaps any window that starts after it."""
    if since and session.get("end") and session["end"] < since:
        return False
    if until and session.get("start") and session["start"] > until:
        return False
    return True
