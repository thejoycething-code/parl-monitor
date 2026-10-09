#!/usr/bin/env python3
"""Brazil's weekly edition (src/editions/br.py on src/country_edition.py).

    python3 tools/br_monitor.py --edition --dm     # write editions/br-monitor-<date>.md, DM Chris
    python3 tools/br_monitor.py --print --date 2026-05-29 --since 2026-05-22 --db /tmp/br.db
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import country_edition  # noqa: E402

if __name__ == "__main__":
    sys.exit(country_edition.main("br"))
