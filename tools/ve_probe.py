"""Polite one-off probe of Venezuelan parliamentary sources (scope doc only).

Same User-Agent as src/http.py, 2s between requests, every raw response
archived under data/raw/ve-probe/ before anything is read from it.
Usage: python3 tools/ve_probe.py URL [URL ...]
"""
from __future__ import annotations

import gzip
import re
import ssl
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

UA = "CitizenGO-ParlMonitor/1.0 (contact: cjoyce@citizengo.net)"
OUT = Path(__file__).resolve().parent.parent / "data" / "raw" / "ve-probe"


def probe(url: str, verify: bool = True) -> None:
    ctx = ssl.create_default_context()
    if not verify:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    t0 = time.monotonic()
    slug = re.sub(r"[^A-Za-z0-9]+", "_", url)[:120]
    try:
        with urllib.request.urlopen(req, timeout=30, context=ctx) as r:
            body = r.read()
            status, ctype, final = r.status, r.headers.get("Content-Type"), r.geturl()
    except urllib.error.HTTPError as e:
        body = e.read() or b""
        status, ctype, final = e.code, e.headers.get("Content-Type"), url
    except Exception as e:  # noqa: BLE001 - probe records any failure
        print(f"FAIL {url} {type(e).__name__}: {e} ({time.monotonic()-t0:.1f}s)")
        return
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{slug}.gz").write_bytes(gzip.compress(body))
    print(f"{status} {url} -> {final} {ctype} {len(body)}B ({time.monotonic()-t0:.1f}s)")


if __name__ == "__main__":
    verify = "--insecure" not in sys.argv
    for u in [a for a in sys.argv[1:] if not a.startswith("--")]:
        probe(u, verify)
        time.sleep(2)
