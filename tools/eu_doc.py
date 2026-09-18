#!/usr/bin/env python3
"""Print a European Parliament document, or the paragraphs a roll call names.

    python3 tools/eu_doc.py A-10-2026-0220 --para 78 --para 85 --para AD
    python3 tools/eu_doc.py TA-10-2026-0313            # the whole body
    python3 tools/eu_doc.py B-10-2026-0406 --list      # every numbered paragraph, first 90 chars

Roll calls name paragraphs of the REPORT as tabled ("A10-0220/2026 - § 78"),
and a rejected paragraph is not in the adopted text at all, so the report is
what to read. Reports, motions and adopted texts sit on different shelves
(src/eudoc.SHELVES); a type not in the table is looked up in its record.
Read-only: nothing is written to the store.
"""

import argparse
import json
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import eudoc  # noqa: E402

UA = {"User-Agent": "parl-monitor (cjoyce@citizengo.net)"}


def fetch(url, accept=None):
    headers = dict(UA)
    if accept:
        headers["Accept"] = accept
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=120) as h:
        return h.read()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("identifier", help="A-10-2026-0220, B-10-2026-0406, TA-10-2026-0313 ...")
    ap.add_argument("--para", action="append", default=[], help="78, AD ... (repeatable)")
    ap.add_argument("--list", action="store_true", help="list every numbered paragraph")
    args = ap.parse_args()
    url = eudoc.resolve_url(args.identifier, lambda u: json.loads(fetch(u, "application/ld+json")))
    if not url:
        print("no English .docx listed for {0}".format(args.identifier))
        return 1
    print("source: {0}".format(url))
    paras = eudoc.paragraphs(fetch(url))
    if args.para or args.list:
        nums = eudoc.numbered(paras)
        if args.list:
            for k, v in nums.items():
                print("  {0:>4}  {1}".format(k, v[len(k) + 2:92]))
        for key in args.para:
            key = key.strip().rstrip(".").upper() if not key.strip().isdigit() else key.strip()
            print("\n=== \u00a7 {0}\n{1}".format(key, nums.get(key, "(no paragraph {0} in the motion)".format(key))))
        return 0
    print("\n\n".join(p for p in paras if len(p) >= eudoc.MIN_PARAGRAPH))
    return 0


if __name__ == "__main__":
    sys.exit(main())
