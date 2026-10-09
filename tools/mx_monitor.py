#!/usr/bin/env python3
"""Mexico's FORTNIGHTLY edition (src/editions/mx.py on src/country_edition.py).

Rendered at the end of the GitHub job (jobs/mx-collect.sh, odd ISO weeks,
X9): the Chamber's hosts refuse UK addresses, so the work and the edition
happen on a GitHub runner, and the Mini only keeps the clock. The window is
a fortnight (src/editions/render_hooks.py).

    python3 tools/mx_monitor.py --edition --dm     # write editions/mx-monitor-<date>.md, DM Chris
    python3 tools/mx_monitor.py --print --date 2026-10-01 --db /tmp/mx.db
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import country_edition  # noqa: E402
from src.editions import mx, render_hooks  # noqa: E402

if __name__ == "__main__":
    render_hooks.install(cadence_days=mx.CADENCE_DAYS)
    sys.exit(country_edition.main("mx"))
