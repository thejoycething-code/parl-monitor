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
            try:
                text = self.client.get_text("{0}://{1}/robots.txt".format(parts.scheme, host),
                                            self.feed, "robots-" + host, archive=False)
                rp.parse(text.splitlines())
            except FetchError:
                rp.parse([])          # no robots.txt: no rules
            delay = rp.crawl_delay(self.client.user_agent) or rp.crawl_delay("*")
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
        return rp.can_fetch(self.client.user_agent, url) and rp.can_fetch("*", url)

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

    def post_json(self, url, body, slug):
        if not self._guard(url):
            return None
        try:
            return self.client.post_json(url, body, self.feed, slug)
        except (FetchError, ValueError) as exc:
            self.gap("{0}: {1}".format(url, getattr(exc, "cause", exc)))
            return None


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
