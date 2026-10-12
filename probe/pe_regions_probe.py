"""Probe gob.pe normas-legales for Peru's 25 regional governments and Lima
Metropolitana (scope of PE4, 12 October 2026). Writes a JSON summary."""
import json, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from src.http import HttpClient, FetchError

SLUGS = sys.argv[1].split(",")
TYPES = sys.argv[2].split(",") if len(sys.argv) > 2 else ["40-ordenanza-regional"]
c = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"), throttle=3.0, max_retries=1)
out = {}
for s in SLUGS:
    for t in TYPES:
        url = "https://www.gob.pe/institucion/{0}/normas-legales/tipos/{1}".format(s, t)
        try:
            h = c.get_text(url, "pe-regions-probe", "{0}-{1}".format(s, t))
        except FetchError as e:
            out["{0} {1}".format(s, t)] = "ERR " + str(e)[:80]
            print(s, t, "ERR", str(e)[:80]); continue
        items = re.findall(r'aria-labelledby="p-filter-item-\d+" href="([^"]+)">([^<]*)</a>', h)
        dates = re.findall(r'<time[^>]*datetime="(\d{4}-\d\d-\d\d)', h)
        name = re.search(r'<title>([^<]*)</title>', h)
        out["{0} {1}".format(s, t)] = {"n": len(items), "newest": max(dates) if dates else None,
              "oldest": min(dates) if dates else None, "first": items[0][1] if items else None,
              "title": name.group(1).strip() if name else None}
        print(s, t, out["{0} {1}".format(s, t)])
print(json.dumps(out, ensure_ascii=False, indent=1))
