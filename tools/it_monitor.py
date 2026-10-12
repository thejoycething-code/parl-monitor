#!/usr/bin/env python3
"""The weekly Italian edition (src/country_edition.py, adapter src/editions/it.py).

    python3 tools/it_monitor.py --edition --dm     # editions/it-monitor-<date>.md, DM to Chris
    python3 tools/it_monitor.py --print            # render to stdout, write nothing
    python3 tools/it_monitor.py --edition --sample --db <store> --date <iso> --since <iso>
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import country_edition  # noqa: E402

if __name__ == "__main__":
    sys.exit(country_edition.main("it"))
