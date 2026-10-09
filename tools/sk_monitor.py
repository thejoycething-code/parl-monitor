#!/usr/bin/env python3
"""The Slovakia weekly edition (src/country_edition.py, adapter src/editions/sk.py).

    python3 tools/sk_monitor.py --edition --dm    # write editions/sk-monitor-<date>.md, DM Chris
    python3 tools/sk_monitor.py --print           # render to stdout, write nothing

Runs as the last step of jobs/sk-weekly.sh.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import country_edition  # noqa: E402

sys.exit(country_edition.main("sk"))
