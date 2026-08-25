"""What the paid passes actually cost, recorded rather than remembered.

Christopher's standing instruction is to be told when API funds are used.
Until 2026-08-24 nothing recorded it: spend was reported by hand, from
memory of historic rates, which is exactly the kind of number that drifts.
The passes already receive a `usage` block on every reply and were throwing
it away.

This records the FACT (tokens, per pass, per model, per day) and computes
the ESTIMATE separately, because rates change and a stored pound figure
would silently become wrong. RATES below carries its source date; if a
model is missing the report says so instead of guessing.
"""

from __future__ import annotations

import datetime

# USD per million tokens, from the Anthropic pricing table, 2026-08-24.
# Sonnet 5 is on an INTRODUCTORY rate that ends 2026-08-31: from 1 September
# the same work costs 50% more, which is worth knowing before it lands.
RATES = {
    "claude-sonnet-5": {"input": 3.00, "output": 15.00,
                        "intro": {"until": "2026-08-31",
                                  "input": 2.00, "output": 10.00}},
    "claude-opus-5": {"input": 5.00, "output": 25.00},
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00},
}
USD_PER_GBP = None      # unset on purpose: report dollars, not a stale FX rate


def record(conn, pass_name, model, usage, dated=None):
    """Store one reply's usage. Unknown shapes are stored as zeros, never
    dropped -- a call that happened must leave a trace even if the response
    surprised us."""
    usage = usage or {}
    conn.execute(
        "INSERT INTO api_spend (dated, pass_name, model, calls, "
        "input_tokens, output_tokens, cache_read_tokens, cache_write_tokens) "
        "VALUES (?,?,?,1,?,?,?,?)",
        (dated or datetime.date.today().isoformat(), pass_name, model or "?",
         int(usage.get("input_tokens") or 0),
         int(usage.get("output_tokens") or 0),
         int(usage.get("cache_read_input_tokens") or 0),
         int(usage.get("cache_creation_input_tokens") or 0)))


def _rate(model, dated):
    spec = RATES.get(model)
    if not spec:
        return None
    intro = spec.get("intro")
    if intro and dated and dated <= intro["until"]:
        return intro["input"], intro["output"], True
    return spec["input"], spec["output"], False


def summary(conn, since=None):
    """Totals per pass since a date, with a dollar estimate where the rate
    is known. Returns (rows, notes) -- notes carry anything the caller
    should say out loud rather than bury."""
    args, where = [], ""
    if since:
        where, args = "WHERE dated >= ?", [since]
    rows = conn.execute(
        "SELECT pass_name, model, SUM(calls) calls, SUM(input_tokens) inp, "
        "SUM(output_tokens) outp, SUM(cache_read_tokens) cread, "
        "MIN(dated) first, MAX(dated) last FROM api_spend {0} "
        "GROUP BY pass_name, model ORDER BY 1, 2".format(where), args
    ).fetchall()
    out, notes, total = [], [], 0.0
    for r in rows:
        rate = _rate(r["model"], r["last"])
        cost = None
        if rate:
            cost = (r["inp"] / 1e6) * rate[0] + (r["outp"] / 1e6) * rate[1]
            total += cost
            if rate[2]:
                notes.append(
                    "{0} is on an INTRODUCTORY rate that ends {1}; after that "
                    "the same work costs about {2:.0f}% more.".format(
                        r["model"], RATES[r["model"]]["intro"]["until"],
                        100 * (RATES[r["model"]]["input"]
                               / RATES[r["model"]]["intro"]["input"] - 1)))
        else:
            notes.append("no rate held for {0}: tokens are recorded, cost is "
                         "not estimated.".format(r["model"]))
        out.append({"pass": r["pass_name"], "model": r["model"],
                    "calls": r["calls"], "input": r["inp"],
                    "output": r["outp"], "cache_read": r["cread"],
                    "usd": cost, "first": r["first"], "last": r["last"]})
    return out, sorted(set(notes)), total


def line(conn, since=None):
    """One human line for the Monday log."""
    rows, notes, total = summary(conn, since)
    if not rows:
        return "api spend: nothing recorded{0}.".format(
            " since " + since if since else "")
    calls = sum(r["calls"] for r in rows)
    toks = sum(r["input"] + r["output"] for r in rows)
    head = "api spend{0}: {1} call(s), {2:,} tokens, about ${3:.2f}".format(
        " since " + since if since else "", calls, toks, total)
    return "\n".join([head] + ["  " + n for n in notes])
