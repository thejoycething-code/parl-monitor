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

## The US, Ireland and Australia (9 October 2026)

Christopher asked for 5CA parity for the US Congress, the Oireachtas and the
Federal Parliament of Australia. Built on the provinces and Canada pattern:

* `tools/us_5ca.py`, `tools/ie_5ca.py`, `tools/au_5ca.py`, sharing
  `src/readings5ca.py` (readings, placement, the sheet, the sign-off guide).
  Output `data/5ca/<cc>-5ca-<chamber>-<area>.csv`, stable names, every
  5CA area (migration and organ donation excluded, as everywhere).
* `config/us_stance.yaml`, `config/ie_stance.yaml`, `config/au_stance.yaml`:
  the readings. **Every entry is a Claude draft (`draft: true`) and places
  nobody.** With nothing signed, each sheet's last row says "NO SIGNED
  READINGS ... every row sits at 0": an evidence list, never an inference.
* `docs/5ca-us-readings.md`, `docs/5ca-ie-readings.md`,
  `docs/5ca-au-readings.md`: one checkbox per reading (motion, what an Aye
  means, lobbies, proposed direction, a flag where the call is doubtful).
  Tick, then `python3 tools/<cc>_5ca.py --sign-from-doc` deletes the ticked
  entries' `draft: true` and stamps `signed:`. `--signoff-doc` rewrites the
  guide from the stance file.
* Evidence and weights: a vote 5 everywhere; sponsoring a bill 3 (US, and an
  Irish Private Member's bill); US cosponsoring 2, drafted at +/-1 so it alone
  never reaches ++. Never placing: Present / Not Voting, Staon, an Australian
  PAIR (Hansard does not publish which side), a withdrawn cosponsorship, US
  floor speeches (counted per member, activity not direction).
* Here, unlike `ca_5ca.py`, `draft` outranks `placeable: false`: a drafted
  "evidence only" call is still Claude's call, so it counts as unsigned.
* Run weekly, offline, after the collectors in `jobs/us-weekly.sh`,
  `jobs/ie-weekly.sh` and `jobs/au-weekly.sh` (as `prov_5ca.py` runs in the
  provinces weekly); a failure is a `[gap]` line, never a lost week.
* Ireland: the store holds the 34th Dail and 27th Seanad only, so the safe
  access zones and hate offences votes (33rd Dail) cannot be read until
  `ie_rollcalls.py` backfills it.

## Devolved member records and same-day briefs (9 October 2026)

* `src/devolved_intel.py` reads each MSP's, MS's and MLA's record on our ground
  from the store and the 5CA placement per area from the SAME `build_rows` the
  sheets use (`sp_5ca`, `sd_5ca`, `ni_5ca`; the first two now carry the
  member's id on each row), so a profile and a sheet cannot disagree.
* A vote shows its lobby and, only where a human signed the reading in
  `config/{sp,sd,ni}_stance.yaml`, that lobby's signed direction. Otherwise
  "awaiting sign-off" (no entry, or a draft), or "read and settled: places
  nobody" (an entry with no lobby values, the Senedd LCM family). An
  abstention is a position without a direction; Holyrood's "Not Voted" is
  counted as an absence and never listed.
* Holyrood motions and questions show at tier 1 (the sp_items.tier rule) and
  Holyrood divisions at tier 1 or where a reading exists. Area 11 (migration)
  is collated and never shown as a member's record.
* The same-day briefs (`tools/devolved_brief.py`) report the reading status in
  the same three words and attach no verdict: the next step they name is
  signing the reading in the stance file, after which the weekly places members.

## The European Parliament (9 October 2026)

`tools/make_eu_5ca.py` keeps its own file shape: `config/eu_divisions.yaml` is
a mapping keyed by decision-event id (`our_side`, `meaning_favor`,
`meaning_against`, `signed_off`), read by the tracker and the edition too.
393 DRAFT readings were added for the divisions on our ground; none is signed
and none places anyone. `src/eureadings.py` writes the guide
(`docs/5ca-eu-readings.md`, `--signoff-doc`) and signs from it
(`--sign-from-doc`), reusing `readings5ca`'s checkbox format; a tick cannot
sign a draft that proposes no side. The absence rule now caps ++ for an MEP in
the chamber that day who did not vote on the latest signed division
(docs/eu-monitor-spec.md, 9 October 2026).

## The new country editions (10 October 2026, branch `parity-5ca`)

Parity item 2 of docs/country-parity-handover.md, for every new country whose
store holds member-level votes (IT, CH, FR, BE, PL, HR, SK, ES, BR, AR, MX,
HU, CL, PE, EC, DO, SV, GT) or party-group votes (AT, PT, NL: X5). One
module, `src/country5ca.py`, one tool, `tools/country_5ca.py`, and one spec
per store (the SQL for its divisions, positions and roster); placement, the
sheet and the checkbox format are `src/readings5ca.py`'s, unchanged.

* **The drafter** (`--draft`) appends to `config/<cc>_stance.yaml` one entry
  per watched or tier-1 vote not yet there, and never rewrites an entry. No
  model is called (X16): values are proposed only for a vote on the whole
  text (or the motion itself) or a motion to reject it, on a bill whose
  direction is on file in the same file's `bill_directions` (written by
  Claude from each watchlist's own description, 10 October, drafts too).
  An amendment, an article, a motion tabled in a bill's dossier, a bill
  with no direction and wording the rules do not recognise are all
  `status: needs_reading`, with a `read_first:` line; procedure is a draft
  with `placeable: false`. The kind of vote is read from its own wording in
  its own language (`vote_kind`), the store's own flags winning (Italy's
  `is_final`, Croatia's `yes_means_reject`, Guatemala's `procedural`).
* **The sign-off** is Canada's C-218 path made explicit: `status: draft` ->
  `status: confirmed` with `confirmed_by:` and `confirmed_on:`, by
  `--confirm KEY --by NAME` or by ticking `docs/5ca-<cc>-readings.md` and
  `--sign-from-doc --by NAME`. A `needs_reading` entry cannot be confirmed
  until a person writes its values; a confirmation without a name is
  refused; the name must be Chris or listed for the country in
  `config/stance_signers.yaml` (all lists empty: Chris to name the country
  owners). `readings5ca.status` now reads this `status:` field (additive:
  files without it read as before), so a `confirmed` entry with no name or
  date is still a draft everywhere, the vote briefs included.
* **The sheets** (`--sheets`, `data/5ca/<cc>-5ca-<chamber>-<area>.csv`) are
  written only for a chamber and area with a confirmed reading that places
  someone, and removed when that stops being true, so no unconfirmed stance
  reaches a published 5CA. An unconfirmed vote shows on a row only as
  "awaiting sign-off -- not placed", with no direction. AT, PT and NL rows
  come from the stores' own X5 derivations: labelled `[DERIVED]`, weight 4
  against a recorded vote's 5, confidence "derived (group vote ...)". The
  absence cap applies to member-level rows only, and only where the store
  records the member as present but not voting on the latest confirmed
  decisive vote.
* **The digest** (`tools/stance_digest.py --dm`): one DM to Chris a week,
  by country, of what waits (proposed, procedural, needs reading, ticks not
  yet applied), the newest proposed readings by key. Both steps run at the
  head of `jobs/editions-session-judge.sh` (Sundays 16:45, Mini only).

Initial drafts (10 October 2026), from the 9-10 October scoping and edition
stores (the published store held no rows for these countries yet): 2,012
entries in 18 countries, 71 with proposed values, 43 procedural, 1,898 need
reading, none confirmed. France alone is 1,050, nearly all amendments to the
aide a mourir law: each needs its text read. Peru, El Salvador and Guatemala
have bill directions but no qualifying votes in any store yet.


## Campaign targets and outcomes for the new countries (10 October 2026, branch `camp-targets`)

`tools/country_campaign.py` (src/country_campaign.py) is the UK's
`tools/ca_campaign.py` (the Evaluate phase, src/evaluate.py) and
`tools/campaign_targets.py` for every country in `src/country5ca.COUNTRIES`.
A campaign is one area in one chamber; its state is one JSON file,
`data/campaigns/<cc>/<slug>.json`, committed by whoever runs the command. The
store is read-only; nothing is fetched, posted or scheduled (manual only).

* **open** snapshots every sitting member's placement from
  `country5ca.build_rows`, so from CONFIRMED readings only. Before sign-off
  every member is at 0 and the campaign is stored as "awaiting sign-off":
  it holds no prediction. Re-opening the slug after sign-off retakes the
  snapshot and keeps targets and outcomes.
* **targets** suggests targets from confirmed placements only: `+` (secure),
  `-` (move) and a mixed confirmed record. `++` are allies, `--` are not
  expected to move, `0` has no confirmed evidence. Members who voted on the
  area's unconfirmed votes are listed as candidates by vote record (how they
  voted, in the chamber's words, by group), each "not a target until the
  stance is confirmed", never ordered by an implied direction.
* **add** records a person's choice (`--by NAME`). A member with no confirmed
  placement needs `--reason` and is stored as "chosen by NAME, no confirmed
  stance", never as a suggestion.
* **find** searches the store's divisions and shows each one's reading
  status; **outcome** records the vote and OUR side (`yes`/`no` as the
  chamber records it). A side that contradicts a confirmed reading is
  refused; with no confirmed reading the side is recorded as stated by the
  person, and the score says so.
* **score** reports with us, against, abstained (a recorded abstention only)
  and did not vote (absent, on mission, present only), by placement group
  and for the targets, with the UK's circularity warning; a snapshot taken
  before sign-off gives counts only. `--csv` writes
  `data/5ca/<cc>-5ca-evaluate-<slug>-<date>.csv`. DERIVED positions (AT,
  PT, NL show of hands, X5) are counted and labelled.
* **performance** joins petition numbers from `data/looker/<cc>_campaigns.tsv`,
  the same Looker export as the UK's `en_gb_campaigns.tsv`
  (docs/campaign-benchmarks.md) filtered on the country's list prefix: by a
  campaign's `--petition` ids, then by area (the English keyword table of
  `log_campaign_performance.py`, so foreign slugs may stay unmapped and are
  counted), then members named in a petition. No country has an export yet,
  and the command says so and prints the query and the file it expects.

Sample (scratch config only, never committed): Italy, Camera, area 10, with
the 2023 questione pregiudiziale on surrogacy as a universal crime confirmed
at -1/+1 in a scratch copy. Open: 187 at +, 124 at -, 103 at 0; 311
suggested targets. Outcome the final vote of 26 July 2023, our side
Favorevole: 166 with us, 109 against, 4 abstained, 121 did not vote; the
placement held for 251 of 252 members it tested (flagged circular: the vote
predates the snapshot). Before sign-off the same campaign suggests nobody
and lists 350 candidates by vote record over 42 unconfirmed votes.
