"""Probe helper: fetch URLs through src/http.py (archives to data/raw/<date>/do_probe_*)."""
import os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.http import HttpClient, FetchError
c = HttpClient(os.path.join(os.path.dirname(__file__), "..", "data", "raw"), throttle=3.0,
               default_timeout=60, max_retries=2, backoff=(5.0, 15.0))
out = os.path.join(os.path.dirname(__file__), "out")
args = sys.argv[1:]
for i in range(0, len(args), 2):
    url, slug = args[i], args[i + 1]
    t = time.time()
    try:
        raw = c.get_bytes(url, "do_probe", slug)
        open(os.path.join(out, slug), "wb").write(raw)
        print("OK", slug, len(raw), "%.1fs" % (time.time() - t), url)
    except FetchError as e:
        print("FAIL", slug, e, url)
    time.sleep(2)
