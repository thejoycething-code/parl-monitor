"""The fetch context every provincial collector runs inside.

One object carries what each src/ingest/prov_<code>.py needs, so the
modules stay parsers plus a short `collect()`:

  * the shared HttpClient (honest CitizenGO User-Agent with contact, retries,
    a per-host throttle of at least 1.1 s -- docs/canada-provinces-scope.md);
  * robots.txt, read once per host and HONOURED: a disallowed URL is never
    requested and is recorded as a gap; a Crawl-delay larger than the
    throttle raises the throttle (New Brunswick asks for 10 s). A robots.txt
    that answers 404 -- or, as lims.leg.bc.ca does, an HTML error page with
    status 404 -- means no rules;
  * the run's budget (src/drain), its record --limit and --dry-run;
  * the gaps collected on the way, written once at the end through
    db.record_gaps so a run log is never the only record.

Nothing is archived to data/raw: provincial PDFs run to a megabyte each and
the URL stored on every row is the provenance (as for the Canada Gazette).
"""

from __future__ import annotations

import html as _html
import io
import re
import urllib.robotparser
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
            rp = urllib.robotparser.RobotFileParser()
            text = ""
            try:
                text = self.client.get_text("{0}://{1}/robots.txt".format(parts.scheme, host),
                                            self.feed, "robots-" + host, archive=False)
                rp.parse(text.splitlines())
            except FetchError:
                rp.parse([])          # no robots.txt: no rules
            rp.star_rules = star_rules(text, self.client.user_agent)
            delay = rp.crawl_delay(self.client.user_agent) or rp.crawl_delay("*")
            if delay and float(delay) > (self.client.throttle or 0):
                self.log("  {0}: robots.txt Crawl-delay {1}s honoured".format(host, delay))
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

    def text(self, url, slug, encoding=None):
        if not self._guard(url):
            return None
        try:
            return self.client.get_text(url, self.feed, slug, archive=False,
                                        fallback_encoding=encoding)
        except FetchError as exc:
            self.gap("{0}: {1}".format(url, exc.cause))
            return None

    def bytes(self, url, slug):
        if not self._guard(url):
            return None
        try:
            return self.client.get_bytes(url, self.feed, slug, archive=False)
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
    for allow, path in rules:
        if any(f.startswith(path) or f.startswith(unquote(path)) for f in forms):
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
