#!/usr/bin/env python3
"""Argentina's weekly edition (src/editions/ar.py on src/country_edition.py),
with the Ley 13.640 "Nearing lapse" section (src/editions/render_hooks.py).

    python3 tools/ar_monitor.py --edition --dm     # write editions/ar-monitor-<date>.md, DM Chris
    python3 tools/ar_monitor.py --print --date 2026-10-09 --db /tmp/ar.db
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import country_edition  # noqa: E402
from src.editions import ar, render_hooks  # noqa: E402

if __name__ == "__main__":
    render_hooks.install(post_render=ar.post_render)
    sys.exit(country_edition.main("ar"))
