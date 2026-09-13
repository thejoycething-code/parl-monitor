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

## The Evaluate phase (2026-08-24)

The framework has two halves and only Plan was ever built: the sheets were a
standing prediction nobody marked, so nothing measured whether the evidence
hierarchy works.

**Recovering the prediction fairly.** `stance.suggest_rows(..., as_at=DATE)`
rebuilds the sheet from evidence dated STRICTLY BEFORE the division. After a
vote the vote itself is evidence, and a sheet including it would be marking
its own homework. No snapshot is needed and none should be built -- the
ledger carries dates, so any past placement is reconstructable. (An earlier
plan called for snapshotting sheets before each vote; the as-at rebuild
supersedes it and removes the need for forethought.)

**Which lobby is ours** comes from the stance already scored on the
division's own refs (`div:cN:aye` / `:no`) -- the same human-reviewable
judgement the 5CA places on. An unscored or procedural division (both
lobbies at 0) is REFUSED rather than guessed.

**What counts as a miss** is most of the design, because a hit rate is a
number people quote and a generous denominator flatters it:

  * placed at 0 is NOT a miss -- zero means "no evidence", an honest absence
    of prediction. Counting it would punish the sheet for admitting what it
    does not know, and would sink the rate on a 650-seat roster where most
    members never speak on a given issue;
  * an ABSENCE is not a miss -- paired, ill or abroad contradicts nothing;
  * only members with BOTH a directional placement and a recorded vote can
    be right or wrong, and the rate is computed over exactly those.

**First result** (`div:c1877`, Terminally Ill Adults second reading,
2024-11-29): 52 hit, 4 miss, 592 no-prediction, 2 no-vote -- a **93% hit
rate** over the 56 members who had both. By what the placement rested on:
debate 92% (34/37), edm-signed 94% (17/18), pq 100% (1/1). That is the first
measured evidence of whether the hierarchy is right, rather than the
reasonable-sounding assumption it was built on.

The sheet gains two columns, `Actual vote` and `Evaluate`. The outcome is
written as "hit (was ++)" because it refers to the placement AS AT the vote,
not the column on the row -- today's column includes the vote itself, so a
bare "hit" beside a ++ that was 0 beforehand reads as a contradiction.

Next: the Terminally Ill Adults second reading on 2026-09-11 is a free vote
on our core issue with a full roll call -- the best evaluation set of the
year, and now it will be scored automatically.

## Flags on the sheet (2026-09-12)

After the Terminally Ill Adults Second Reading (270–286) every 5CA row carries
`wavering`, `wavering_why`, `targeted` alongside `conflict`, rendered as W / T / ±
chips on the internal web sheet with a Wavering filter. The rules, the evidence
behind the threshold, the cap on former Aye voters, and the presence/absence
events are written up in docs/debate-pack-social.md under "What the vote feeds".
The partner build drops flags and tiers alike.

## The Evaluate phase, measured (2026-09-13)

`python3 tools/evaluate_5ca.py div:cID --area N [--apply]` (built 24 Aug, never run
until 13 Sept) rebuilds the Plan sheet from evidence dated before the division
(`suggest_rows(..., as_at=)`), scores the hit rate over members with both a
placement and a vote, and breaks it down by the evidence each placement rested
on. It now also reports the flags (WAVERING, CONFLICT, TARGETED) against the
base, the gains (placed against us, voted our way) beside the misses, and
staying away as movement; that sheet is banked in data/5ca-eval/<ref>.md and
.json, and --apply writes the per-member rows to the `evaluations` table. First
readings:

* 2428 (Second Reading, 11 Sept 2026): every ++ and + who voted went our way;
  no misses; the seven gains were all at --. The flags did NOT beat the base:
  among members placed against us, flagged WAVERING or CONFLICTING moved,
  abstained or stayed away 13 of 76 (17%) against 49 of 252 (19%) unflagged.
  The 24% figure worked by hand on 12 Sept counted the safeguards-two-plus
  list alone; the wider flag as coded is not that list. The flag is a watch
  list, not a prediction, until it is narrowed.
* 2071 (Third Reading, 20 June 2025): the + column was soft, 13 of 56 voters our
  way (23%); ++ held at 99%. The cap that now keeps former Aye voters at + is
  the right column for them: + means "might", not "will".
* 2421 (puberty blockers, 8 Sept 2026): a whipped vote; no movement either way.
