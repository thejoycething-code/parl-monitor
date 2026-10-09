"""Free, deterministic noise filters for the Latam monitor.

The AI judge stays off (X16), and Chris on 10 October 2026: "no judge yet,
we need free alternatives". So between the collectors' taxonomy pass and
what Chris reads, three cheap checks run, every one of them configured by
hand in config/latam-noise.yaml and config/latam-mute.yaml:

  * EDITION FILTERS (drop_reason): a recorded vote whose own words are
    procedural (order of the day, minutes, quorum, a recess, the Dominican
    Cámara's "liberado del trámite de lectura"); a title on a country's
    exclusion list (Dominican honours resolutions), or a vote naming only
    such bills; an item missing a country's required context (Nicaragua's
    gazette notices without a cancellation or a church); and Chris's mutes.
    These leave the edition and therefore the alerts too.
  * ALERT EVIDENCE (alert_reason): a tier-1 item that is not watched alerts
    only with a tier-1 term in its own title, or enough distinct terms in
    shown areas, or (Honduras's press releases) a decree or expediente
    number. Anything else still appears in the monthly edition.
  * A WATCHED ITEM IS NEVER FILTERED, except by its own key on the mute list.

Without config/latam-noise.yaml nothing is filtered and every tier-1 item
alerts, as before these filters existed. Patterns match text folded the way
src/filter.py folds it (lower case, accents stripped).

Measured on the October 2026 sample: docs/country-decisions-2026-10-10.md,
"Latam noise filters".

Since 10 October 2026 the implementation is src/noise.py, shared with the
weekly country editions (src/country_edition.py); this module is the Latam
instance of it, with the same functions and the same behaviour.
"""

from __future__ import annotations

import os

from src import noise as _noise

ROOT = _noise.ROOT
CONFIG = _noise.CONFIG
TAXONOMY_ES = os.path.join(CONFIG, "taxonomy-es.yaml")
NOISE_FILE = "latam-noise.yaml"
MUTE_FILE = "latam-mute.yaml"
HIDDEN_AREAS = (11,)            # migration: matched, never shown (src/latam.py)

fold = _noise.fold

NOISE = _noise.Noise(NOISE_FILE, MUTE_FILE, lambda cc: [(TAXONOMY_ES, cc)],
                     hidden_areas=HIDDEN_AREAS)


def clear():
    """Forget loaded files (tests, or a long-running caller after an edit)."""
    NOISE.clear()


def rules_for(cc, config_dir=None):
    """The default rules with the country's added: lists concatenated, alert
    keys overriding one by one. None when there is no noise file."""
    return NOISE.rules_for(cc, config_dir)


def muted(it, config_dir=None, edition=False):
    """True when Chris's mute list names this item (by key, or by a title
    pattern for an unwatched item)."""
    return NOISE.muted(it, config_dir, edition)


def drop_reason(it, config_dir=None):
    """Why an item leaves the edition (and so the alerts), or None to keep it."""
    return NOISE.drop_reason(it, config_dir)


def split(items, config_dir=None):
    """(kept, dropped); each dropped item carries its `dropped` reason."""
    return NOISE.split(items, config_dir)


def taxonomy(cc):
    """The compiled taxonomy-es for one country, or None."""
    got = NOISE.taxonomy(cc)
    return got[0] if got else None


def title_tier1(it):
    """True when the title alone carries a tier-1 term in a shown area."""
    return NOISE.title_tier1(it)


def distinct_terms(it):
    """How many distinct matched terms the item has in shown areas."""
    return NOISE.distinct_terms(it)


def alert_reason(it, config_dir=None):
    """Why an item alerts ("watched", "tier-1 term in the title", ...), or None."""
    return NOISE.alert_reason(it, config_dir)
