# 5CA (Five Column Analysis) — what the generator must produce

Source: CitizenGO Campaigns Brief Cheat Sheet + Campaigners Training Course
handbook (FACL / Kirk Shelley methodology), read 2026-08-04. Internal only.

## The framework

5CA applies **only when a campaign targets a concrete decision-making body**
(a Parliament, a board). If there is no defined body, there is no 5CA.

**Plan phase** — one row per decision-maker (an individual MP/peer, or a
whole party when members vote the whip):

| Field | Meaning |
|---|---|
| Decision-Maker | The MP/peer (or party) |
| `++` `+` `0` `-` `--` | Five-tier stance gradient. Individuals: a 1 in exactly one column. Parties: member counts distributed across columns. |
| Target (Y/N) | Whether the campaign actively targets this decision-maker |
| Comments | Rationale for the placement and targeting choice |

**Evaluate phase** — after the vote: `Y` (voted for the bill), `N` (against),
`0` (abstained), plus tactical conclusions.

## What the parl-monitor generator does

For a given bill/campaign and its issue area(s), emit a pre-filled Plan-phase
5CA sheet: every relevant parliamentarian as a row, a **suggested** gradient
placement derived from ledger evidence, and the evidence lines themselves as
the Comments rationale. The campaigner reviews and adjusts; the tool's job is
to replace a blank sheet with a defensible draft.

Evidence quality hierarchy (strongest first):
1. **Division votes** on tagged divisions — ground truth (September, Hansard/divisions work)
2. **Speeches** — stance-rich text (September, Hansard ingester)
3. **EDM sponsorship/co-signature** — unambiguous endorsement of the motion's text (live now)
4. **PQ framing** — weakest; needs a stance-classification pass (Claude, triage-style)

Key design fact: the ledger measures **activity**, not **stance** — an
asker pressing the Home Office on small boats and a peer pressing from the
opposite direction ledger identically. Gradient placement therefore needs the
stance layer (votes when available; Claude text-scoring otherwise), never raw
activity counts alone. `intel.area_activity()` gives the per-member per-area
activity input; stance scoring is the remaining build step.

## Ledger foundations in place (2026-08-04)

- `mp_events.areas` — json list of issue-area numbers per event, stamped by
  both capture paths and retro-stamped by backfill re-runs (record_event is
  an upsert; mp_events carries no editorial state so refresh is always safe).
- `edm-signed` events — every live co-signatory of a matched EDM (order > 1,
  not withdrawn), captured weekly and in backfill via one detail call per
  motion; member details are embedded so the members cache seeds for free.
- Bulk-kind rule: `vote` and `edm-signed` never render in the weekly
  section (Christopher: truncate or link, never a big list); they exist for
  profiles, timelines and 5CA.
- `intel.area_activity(conn)` / `intel.area_names(taxonomy_path)` — the
  aggregation and display primitives the generator will consume.

## Remaining build steps

1. September: divisions member-breakdowns + Hansard speeches into the ledger.
2. Stance-classification pass over text-bearing events (per area, five-tier
   scale matching the 5CA gradient; batched Claude calls, triage-style).
3. `tools/make_5ca.py <bill-or-area>`: rows = members active on the area(s),
   suggested column from stance evidence (votes outrank speeches outrank
   signatures outrank PQs), Comments = dated evidence lines, output CSV
   matching the Campaigns Brief 5CA sheet columns for direct paste-in.
