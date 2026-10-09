"""Small, additive hooks around src/country_edition.py for the Argentine and
Mexican editions, kept here so the shared framework is not edited.

  * post_render: a country function (conn, country, today, text, wl) -> text,
    run on every edition the framework renders. Argentina inserts its
    "Nearing lapse (Ley 13.640)" section with it.
  * cadence_days: an edition that is not weekly (Mexico runs fortnightly on
    GitHub, X9): the first edition's default window becomes that many days,
    and the edition and the DM say "fortnight" where the framework says
    "week".

install() wraps country_edition.render and country_edition.dm_summary in the
calling process only (tools/<cc>_monitor.py); nothing else is changed.
`render()` below is the same pipeline for tests and callers that want it
without installing anything.
"""

from __future__ import annotations

import sqlite3

from src import country_edition as ce

# The framework's weekly wording that a fortnightly edition changes. A
# phrase the framework no longer prints is simply not found.
FORTNIGHT = (("Weekly, to Chris by DM.", "Fortnightly (X9), to Chris by DM."),
             (" Monitor - week to ", " Monitor - fortnight to "),
             ("**A quiet week.**", "**A quiet fortnight.**"),
             ("*A quiet week*", "*A quiet fortnight*"))


def fortnightly(text):
    for old, new in FORTNIGHT:
        text = text.replace(old, new)
    return text


def apply(conn, country, today, text, post_render=None, cadence_days=None, config_dir=None):
    if post_render:
        conn.row_factory = sqlite3.Row
        text = post_render(conn, country, today, text, ce.watchlist_of(country, config_dir))
    if cadence_days == 14:
        text = fortnightly(text)
    return text


def first_window(country, today, since, cadence_days, directory=None):
    """The framework's window, but `cadence_days` long when there is no prior edition."""
    if since or not cadence_days:
        return since
    if [d for d in ce.editions(country.cc, directory) if d < today]:
        return None
    import datetime
    return (datetime.date.fromisoformat(today) - datetime.timedelta(days=cadence_days)).isoformat()


def render(conn, country, today, since=None, sample=False, config_dir=None, directory=None,
           post_render=None, cadence_days=None, _render=None):
    since = first_window(country, today, since, cadence_days, directory)
    text = (_render or ce.render)(conn, country, today, since, sample, config_dir, directory)
    return apply(conn, country, today, text, post_render, cadence_days, config_dir)


def install(post_render=None, cadence_days=None):
    """Wrap the framework's render and dm_summary for this process."""
    base_render, base_dm = ce.render, ce.dm_summary

    def wrapped_render(conn, country, today, since=None, sample=False, config_dir=None,
                       directory=None):
        return render(conn, country, today, since, sample, config_dir, directory,
                      post_render, cadence_days, _render=base_render)

    def wrapped_dm(conn, country, today, since=None, path=None, config_dir=None,
                   directory=None):
        since = first_window(country, today, since, cadence_days, directory)
        text = base_dm(conn, country, today, since, path, config_dir, directory)
        return fortnightly(text) if cadence_days == 14 else text

    ce.render, ce.dm_summary = wrapped_render, wrapped_dm
    return base_render, base_dm
