"""One-off measurement pull of the Chamber SIL (titles, sessions, vote headers)."""
import json, os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.http import HttpClient, FetchError
ROOT = os.path.join(os.path.dirname(__file__), "..")
c = HttpClient(os.path.join(ROOT, "data", "raw"), throttle=1.0, max_retries=3, backoff=(5.0, 15.0, 40.0))
OUT = os.path.join(os.path.dirname(__file__), "out", "pull")
B = "https://www.diputadosrd.gob.do/sil/api/"
def get(path, slug):
    p = os.path.join(OUT, slug + ".json")
    if os.path.exists(p):
        return json.load(open(p))
    try:
        d = c.get_json(B + path, "do_probe_pull", slug)
    except FetchError as e:
        print("FAIL", slug, e, flush=True); return None
    json.dump(d, open(p, "w"))
    return d
MODE = sys.argv[1] if len(sys.argv) > 1 else "all"
t0 = time.time()
for per in ((2761,) if MODE in ("all", "votes") else ()):
    first = get("sesion/sesiones?page=1&keyword=&periodoId=%d" % per, "ses_%d_1" % per)
    pages = -(-first["total"] // 10)
    sessions = list(first["results"])
    for pg in range(2, pages + 1):
        d = get("sesion/sesiones?page=%d&keyword=&periodoId=%d" % (pg, per), "ses_%d_%d" % (per, pg))
        if d: sessions += d["results"]
    print(per, "sessions", len(sessions), "%.0fs" % (time.time() - t0), flush=True)
    nv = 0
    for s in sessions:
        sid = s["sesionId"]; pg = 1
        while True:
            d = get("sesion/votaciones?page=%d&id=%d&periodoId=%d" % (pg, sid, per), "vot_%d_%d" % (sid, pg))
            if not d or not d["results"]: break
            nv += len(d["results"])
            if pg * 10 >= d["total"]: break
            pg += 1
    print(per, "votes", nv, "%.0fs" % (time.time() - t0), flush=True)
for per in ((2761, 2760) if MODE in ("all", "bills") else ()):
    first = get("iniciativa/getIniciativas?page=1&keyword=&periodoId=%d" % per, "ini_%d_1" % per)
    pages = -(-first["total"] // 10)
    print(per, "iniciativas", first["total"], flush=True)
    for pg in range(2, pages + 1):
        get("iniciativa/getIniciativas?page=%d&keyword=&periodoId=%d" % (pg, per), "ini_%d_%d" % (per, pg))
        if pg % 100 == 0: print(per, pg, "%.0fs" % (time.time() - t0), flush=True)
print("done %.0fs" % (time.time() - t0))
