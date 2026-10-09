"""Nicaragua scoping probe (not a collector): crawl the Asamblea Nacional's
plenary vote lists on verifica.asamblea.gob.ni for the given years and write
one JSON row per recorded vote (date, number, title, Si/No/Abs/Pres counts,
detail id). Used to measure docs/nicaragua-scope.md.

Polite: fixed CitizenGO User-Agent, 2s between calls, retries with backoff.
Raw HTML is archived (gzipped) under data/raw/nic/lists/ before parsing, and
re-runs read the archive instead of the network.

    python3 tools/nic_probe.py 2026 2025      # -> data/raw/nic/votes_2026_2025.json
"""
import gzip, json, os, re, sys, time, html, urllib.request
UA = "CitizenGO-ParlMonitor/1.0 (contact: cjoyce@citizengo.net)"
BASE = "https://verifica.asamblea.gob.ni/vtn/Votaciones_/"
OUT = "data/raw/nic/lists"; os.makedirs(OUT, exist_ok=True)
def get(q):
    p = os.path.join(OUT, re.sub(r"[^\w-]", "_", q) + ".html.gz")
    if os.path.exists(p):
        return gzip.open(p, "rt", encoding="utf-8").read()
    req = urllib.request.Request(BASE + "Votaciones.aspx?" + q, headers={"User-Agent": UA})
    for wait in (2, 8, 20, None):
        try:
            s = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace"); break
        except OSError as e:
            if wait is None: raise
            print("retry", q, e, flush=True); time.sleep(wait)
    with gzip.open(p, "wt", encoding="utf-8") as f: f.write(s)
    time.sleep(2); return s
CARD = re.compile(r'<span class="badge">(\d+)</span>\s*<span class="fw-bold">(.*?)</span>.*?Si:\s*(\d+)\s*\|\s*No:\s*(\d+)\s*\|\s*Abs:\s*(\d+)\s*\|\s*Pres:\s*(\d+).*?href=\'(VotacionDetalle\.aspx\?id=([0-9a-f-]+)[^\']*)\'', re.S)
rows = []
for y in sys.argv[1:]:
    ys = get(f"anio={y}")
    for m in sorted(set(re.findall(rf"anio={y}&(?:amp;)?mes=(\d+)", ys)), key=int):
        ms = get(f"anio={y}&mes={m}")
        for d in sorted(set(re.findall(r"fecha=(\d{4}-\d\d-\d\d)", ms))):
            ds = get(f"anio={y}&mes={m}&fecha={d}")
            for c in CARD.findall(ds):
                rows.append(dict(date=d, num=int(c[0]), title=re.sub(r"\s+"," ",html.unescape(c[1])).strip(), si=int(c[2]), no=int(c[3]), abs=int(c[4]), pres=int(c[5]), id=c[7]))
        print(y, m, len(rows), flush=True)
json.dump(rows, open("data/raw/nic/votes_%s.json" % "_".join(sys.argv[1:]), "w"), ensure_ascii=False, indent=0)
