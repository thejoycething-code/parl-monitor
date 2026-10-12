#!/usr/bin/env python3
"""The weekly Dutch edition (src/country_edition.py, adapter src/editions/nl.py).

    python3 tools/nl_monitor.py --edition --dm     # editions/nl-monitor-<date>.md, DM to Chris
    python3 tools/nl_monitor.py --print            # render to stdout, write nothing
    python3 tools/nl_monitor.py --edition --sample --db <store> --date <iso> --since <iso>
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import country_edition  # noqa: E402

if __name__ == "__main__":
    sys.exit(country_edition.main("nl"))
