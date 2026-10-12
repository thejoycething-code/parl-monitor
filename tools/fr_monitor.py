#!/usr/bin/env python3
"""The weekly French edition (src/country_edition.py, adapter src/editions/fr.py).

    python3 tools/fr_monitor.py --edition --dm     # editions/fr-monitor-<date>.md, DM to Chris
    python3 tools/fr_monitor.py --print            # render to stdout, write nothing
    python3 tools/fr_monitor.py --edition --sample --db <store> --date <iso> --since <iso>
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import country_edition  # noqa: E402

if __name__ == "__main__":
    sys.exit(country_edition.main("fr"))
