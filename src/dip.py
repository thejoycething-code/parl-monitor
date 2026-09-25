"""DIP: the Bundestag's document and proceedings system.

`https://search.dip.bundestag.de/api/v1` holds what the recorded votes do
not. Measured 22 September 2026: five relevant votes across two whole
legislatures, against 11 Vorgänge on Schwangerschaftsabbruch, 17 on
Selbstbestimmungsgesetz and 18 on Meinungsfreiheit by title alone since March
2025. This is where a German monitor finds things.

THE KEY. Every call needs one, and the Bundestag publishes a working key in
its own public OpenAPI specification as the example. Resolution order:

    DIP_API_KEY in the environment
    dip_api_key in config/secrets.yaml
    the example in the published spec

Environment first, so the day a key is issued in CitizenGO's name nothing
changes but a secret. Runtime discovery from the spec means a ROTATION heals
itself rather than failing at 3am with a 401 and no explanation. It does not
survive the Bundestag deciding example keys should not be used this way,
which is why docs/germany-scope.md still says to apply for one.

Discovery failure returns None and the caller discloses it. A quiet
zero-document run is indistinguishable from a quiet week, so this must never
fail silently.

/drucksache-text and /plenarprotokoll-text return the TEXT. There is no PDF
to parse and no src/eudoc.py analogue here; writing one would duplicate an
endpoint that already exists.
"""

from __future__ import annotations

import os
import re

BASE = "https://search.dip.bundestag.de/api/v1"
SPEC = BASE + "/openapi.yaml"
# The spec prints it as: description: "Beispiel: *<key>*"
# The Bundestag writes the example key into its own spec as
#   description: "Beispiel: *ApiKey <the key>*"
# The "ApiKey " prefix is the SCHEME NAME, not part of the key, and it was not
# there when this was written. Without the optional prefix the pattern matched
# nothing from about 25 September 2026 and the document layer ran with no key
# at all -- disclosed as a gap on every run, never silent, but broken.
SPEC_KEY = re.compile(r"Beispiel:\s*\*(?:ApiKey\s+)?([A-Za-z0-9._-]{16,})\*")

_CACHE = {}


def api_key(client=None, secrets=None, env=None, log=print):
    """The key to call DIP with, or None. Cached for the life of the process."""
    if "key" in _CACHE:
        return _CACHE["key"]
    env = env if env is not None else os.environ
    found = (env.get("DIP_API_KEY") or "").strip()
    source = "the environment"
    if not found and secrets:
        found = (secrets.get("dip_api_key") or "").strip()
        source = "config/secrets.yaml"
    if not found and client is not None:
        try:
            spec = client.get_text(SPEC, "de-documents", "openapi", archive=False)
            hit = SPEC_KEY.search(spec or "")
            found, source = (hit.group(1) if hit else ""), "the published spec"
        except Exception as exc:                            # noqa: BLE001
            log("  [gap] DIP key: could not read the published spec ({0})"
                .format(str(exc)[:80]))
            found = ""
    if not found:
        log("  [gap] DIP key: not in the environment, not in secrets, and not "
            "found in the published spec -- the document layer cannot run. "
            "This is disclosed, never a quiet empty run.")
        _CACHE["key"] = None
        return None
    log("  DIP key from {0}".format(source))
    _CACHE["key"] = found
    return found


def forget_key():
    """Drop the cached key. For tests, and for a run that saw a 401."""
    _CACHE.pop("key", None)


def url(path, key, **params):
    """A DIP URL with the key and format applied."""
    import urllib.parse
    params = {k: v for k, v in params.items() if v is not None}
    params["format"] = "json"
    params["apikey"] = key
    return "{0}/{1}?{2}".format(BASE, path.strip("/"),
                                urllib.parse.urlencode(params, doseq=True))


def pages(client, path, key, feed="de-documents", slug=None, limit_pages=20,
          log=print, budget=None, **params):
    """Yield each page's `documents`, following DIP's cursor.

    DIP REPEATS THE CURSOR when a result set is exhausted rather than
    dropping it, so a loop that waits for an empty page never ends. This
    stops when the cursor stops moving, which is the documented behaviour and
    also what a renamed parameter would look like.
    """
    cursor, seen_cursors, page = None, set(), 0
    while page < limit_pages:
        if budget is not None and budget.exhausted():
            log(budget.disclose("DIP pages", page))
            return
        u = url(path, key, cursor=cursor, **params)
        reply = client.get_json(u, feed, "{0}-{1}".format(slug or path, page),
                                archive=False)
        docs = (reply or {}).get("documents") or []
        if docs:
            yield reply
        nxt = (reply or {}).get("cursor")
        if not docs or not nxt or nxt in seen_cursors:
            return
        seen_cursors.add(nxt)
        cursor = nxt
        page += 1
    log("  page cap ({0}) reached for {1}; the rest lands on the next run "
        "-- disclosed, not silent".format(limit_pages, path))
