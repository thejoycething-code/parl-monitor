#!/usr/bin/env python3
"""The Spain weekly edition (src/country_edition.py, adapter src/editions/es.py).

    python3 tools/es_monitor.py --edition --dm    # write editions/es-monitor-<date>.md, DM Chris
    python3 tools/es_monitor.py --print           # render to stdout, write nothing

Runs as the last step of jobs/es-weekly.sh. While the Cortes are dissolved
the edition opens with a notice naming the next sitting (ES6); see the
adapter's docstring.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.editions import es  # noqa: E402

sys.exit(es.main())
