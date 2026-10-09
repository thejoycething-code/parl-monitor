#!/usr/bin/env python3
"""Official portraits for a review round's cards.

    python3 tools/review_photos.py --round R1        # data/review/R1/photos.json

Christopher, 9 October 2026: "each of the 50 cards to show up perhaps with a
profile picture - an official one if possible". Every portrait comes from
the member's OWN legislature (House of Commons, Senate, and the provincial
assemblies' member pages or APIs); nothing from a search engine, social
network or news site. A member whose official portrait is not found gets
none, and the card shows initials.

The review page runs under a content policy that blocks outside images, so
each portrait is shrunk (sips, 160 px) and stored as a data: URI on the
card's item, with the page it came from. Probed live 9 October 2026:

  Commons   ourcommons.ca/members/en/<id>        img.ce-mip-mp-picture
  Senate    sencanada.ca SenatorBioAjax/GetBio   sen_pho_<name>_bio.jpg
  Ontario   ola.org/en/members/all/<slug>        member/profile-photo/...
  Alberta   assembly.ab.ca .../mla-photos/ph-mla<mid>.jpg
  Sask.     legassembly.sk.ca/mlas/member-details?first=&last=
  Quebec    the assnat member page (prov_members.page_url)  img.photoDepute
  BC        LIMS GraphQL imageByMediumImageId.path under /public
  Manitoba  legislature/members/info/<x>.html -> img/mla/<x>.jpg
  N.B.      legnb.ca/en/members/current           portraits/<leg>/<x>_sm.jpg
"""

from __future__ import annotations

import argparse
import base64
import html as _html
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import unicodedata
from urllib.parse import quote, urljoin

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, intel  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402

OUT_DIR = os.path.join(ROOT, "data", "review")
SIZE = 160


def fold(s):
    s = unicodedata.normalize("NFKD", s or "")
    return re.sub(r"[^a-z]", "", "".join(c for c in s if not unicodedata.combining(c)).lower())


def shrink(raw):
    """JPEG bytes -> a SIZE-px JPEG data: URI (macOS sips), or None."""
    with tempfile.TemporaryDirectory() as d:
        src, dst = os.path.join(d, "in"), os.path.join(d, "out.jpg")
        with open(src, "wb") as h:
            h.write(raw)
        r = subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "70", "-Z", str(SIZE), src,
                            "--out", dst], capture_output=True)
        if r.returncode or not os.path.exists(dst):
            return None
        with open(dst, "rb") as h:
            return "data:image/jpeg;base64," + base64.b64encode(h.read()).decode()


class Finder:
    def __init__(self, client, conn):
        self.c, self.conn, self.cache = client, conn, {}

    def text(self, url, slug):
        if url not in self.cache:
            self.cache[url] = self.c.get_text(url, "review-photos", slug, archive=False)
        return self.cache[url]

    def member(self, prov, key):
        return self.conn.execute("SELECT name, given, surname, page_url FROM prov_members WHERE prov=? AND member_key=?",
                                 (prov, key)).fetchone()

    def url_for(self, pid):
        kind, _, key = pid.partition(":")
        if kind == "commons":
            page = "https://www.ourcommons.ca/members/en/{0}".format(key)
            m = re.search(r'class="ce-mip-mp-picture[^"]*"\s+src="([^"]+)"', self.text(page, "commons-" + key))
            return (urljoin(page, _html.unescape(m.group(1))), page) if m else (None, page)
        if kind == "senate":
            sid = key.rsplit("-", 1)[-1]
            page = ("https://sencanada.ca/umbraco/surface/SenatorBioAjax/GetBio?displayFor=senatorheader"
                    "&senatorId={0}&columns=0".format(sid))
            m = re.search(r'(/media/[^"\'\s?]*sen_pho_[^"\'\s?]+\.jpg)', self.text(page, "senate-" + sid))
            return ("https://sencanada.ca" + m.group(1) + "?width=300", page) if m else (None, page)
        if kind == "on":
            page = "https://www.ola.org/en/members/all/{0}".format(key)
            m = re.search(r'src="(/sites/default/files/member/profile-photo/[^"]+)"', self.text(page, "on-" + key))
            return (urljoin(page, m.group(1)), page) if m else (None, page)
        if kind == "ab":
            page = "https://www.assembly.ab.ca/members/members-of-the-legislative-assembly/member-information?mid={0}".format(key)
            return ("https://www.assembly.ab.ca/images/default-source/members/mla-photos/ph-mla{0}.jpg".format(key), page)
        if kind == "sk":
            row = self.member("sk", key)
            if not row:
                return None, None
            page = "https://www.legassembly.sk.ca/mlas/member-details?first={0}&last={1}".format(row[1], row[2])
            m = re.search(r'<img src="(/media/[^"]+\.(?:jpg|jpeg|png))"', self.text(page, "sk-" + key), re.I)
            return (urljoin(page, m.group(1)), page) if m else (None, page)
        if kind == "qc":
            row = self.member("qc", key)
            if not row or not row[3]:
                return None, None
            m = re.search(r'src="([^"]+)"\s+class="photoDepute"', self.text(row[3], "qc-" + key))
            return (_html.unescape(m.group(1)), row[3]) if m else (None, row[3])
        if kind == "bc":
            # The member's own image, else the newest parliament's (members
            # first elected in the 43rd carry theirs only there).
            q = json.dumps({"query": "{ memberById(id: %d) { imageByMediumImageId { path } "
                                     "memberParliamentsByMemberId { nodes { parliamentId "
                                     "imageByMediumImageId { path } } } } }" % int(key)})
            reply = self.c.post_json("https://api.lims.leg.bc.ca/graphql", q, "review-photos", "bc-" + key)
            node = ((reply or {}).get("data") or {}).get("memberById") or {}
            paths = [(n.get("parliamentId") or 0, (n.get("imageByMediumImageId") or {}).get("path"))
                     for n in (node.get("memberParliamentsByMemberId") or {}).get("nodes") or []]
            paths = [p for _, p in sorted(paths, reverse=True) if p]
            path = paths[0] if paths else (node.get("imageByMediumImageId") or {}).get("path")
            return ("https://lims.leg.bc.ca/public" + path, "https://www.leg.bc.ca/members") if path else (None, None)
        if kind == "mb":
            row = self.member("mb", key)
            lst = "https://www.gov.mb.ca/legislature/members/mla_list_alphabetical.html"
            page_html = self.text(lst, "mb-list")
            sur = fold(row[2] if row else key.rsplit("-", 1)[-1])
            for href in re.findall(r'href="(info/[^"]+\.html)"', page_html):
                if sur and sur in fold(href):
                    page = urljoin(lst, href)
                    m = re.search(r'src="([^"]*img/mla/[^"]+\.(?:jpg|jpeg|png))"', self.text(page, "mb-" + key), re.I)
                    return (urljoin(page, m.group(1)), page) if m else (None, page)
            return None, lst
        if kind == "nb":
            row = self.member("nb", key)
            lst = "https://www.legnb.ca/en/members/current"
            page_html = self.text(lst, "nb-list").replace("\\", "/")
            sur = fold(row[2] if row else key.rsplit("-", 1)[-1])
            for src in re.findall(r'(/content/members/portraits/[^"\'\s]+\.(?:jpg|jpeg|png))', page_html, re.I):
                if sur and sur in fold(os.path.basename(src)):
                    return urljoin(lst, src), lst
            return None, lst
        return None, None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--round", required=True)
    args = ap.parse_args(argv)
    spec = importlib.util.spec_from_file_location("rs", os.path.join(ROOT, "tools", "review_sample.py"))
    rs = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rs)
    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    pop = rs.population(conn, intel.area_names(os.path.join(ROOT, "config", "taxonomy.yaml")), rs._excluded())
    pid_of = {(c["jurisdiction"], c["member"]): pid for v in pop.values() for pid, cs in v.items() for c in cs}
    with open(os.path.join(OUT_DIR, args.round, "items.json"), encoding="utf-8") as h:
        items = json.load(h)
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    client.set_host_throttle("www.legnb.ca", 10)
    finder = Finder(client, conn)
    out, missing = {}, []
    for it in items:
        pid = pid_of.get((it["jurisdiction"], it["member"]))
        try:
            url, page = finder.url_for(pid) if pid else (None, None)
            if url:   # "Deschênes" in a Commons file name: percent-encode anything non-ASCII
                url = quote(url, safe=":/?=&%+,;@")
            raw = client.get_bytes(url, "review-photos", "img-" + it["id"], archive=False) if url else None
        except (FetchError, ValueError, KeyError) as exc:
            url, raw = None, None
            print("  {0}: {1}".format(it["id"], exc))
        data = shrink(raw) if raw and raw[:3] in (b"\xff\xd8\xff", b"\x89PN", b"RIF", b"GIF") else None
        if data:
            out[it["id"]] = {"photo": data, "photo_source": page or url}
        else:
            missing.append("{0} {1}".format(it["id"], it["member"]))
    with open(os.path.join(OUT_DIR, args.round, "photos.json"), "w", encoding="utf-8") as h:
        json.dump(out, h)
    print("review photos {0}: {1} of {2} official portrait(s)".format(args.round, len(out), len(items)))
    for m in missing:
        print("  none: " + m)
    return 0


if __name__ == "__main__":
    sys.exit(main())
