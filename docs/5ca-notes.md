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
  `config/stance_signers.yaml` (Chris for every country since 11 October
  2026; since the same day drafts that pass every check are confirmed
  automatically, below). `readings5ca.status` now reads this `status:` field (additive:
  files without it read as before), so a `confirmed` entry with no name or
  date is still a draft everywhere, the vote briefs included.
* **The sign-off scope** (Chris, 10 October 2026; **lifted 12 October 2026**,
  below: no country has a scope now, and no prune removes an amendment
  entry). A spec may limit what is
  drafted for sign-off (`Spec.scope`; none means every qualifying vote, as
  for every country but France until 12 October). France's is `final_or_watched`: votes on
  the whole text, motions to reject it and inverted votes; procedure only
  when its wording is about the whole text; and amendment or article votes
  only when listed under their dossier's `amendments:` in
  `config/watchlist-fr.yaml`, by division key (exact) or by amendment number
  as the Assemblee words it (any vote in that dossier on that number). The
  drafter skips the rest and counts them. `--prune-out-of-scope`
  (`--dry-run` to see first) removes out-of-scope entries that are unsigned
  and untouched: stamped by the drafter, no yea/nay or why lines, no
  `confirmed_by`, no `placeable: false` but the drafter's own procedural
  one, no comment inside the entry. Everything else is kept and reported,
  and the edit is checked to leave every kept entry exactly as it was.
  France, 10 October: 1,050 entries to 13 (10 proposed, 3 need reading);
  1,037 amendment and article drafts removed, none kept.
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
aide a mourir law: each needs its text read. (France was cut to 13 the same day by
the sign-off scope above: 975 entries in all.) Peru, El Salvador and Guatemala
have bill directions but no qualifying votes in any store yet.


### Which readings to sign first (11 October 2026, branch `ukp2-5ca-candidates`)

The UK picks its past votes by hand from a review queue
(`tools/find_division_candidates.py`, `tools/review_divisions.py`,
`docs/division-candidates*.md`). The new countries start from the other end:
every watched and tier-1 vote already has a drafted reading, 975 of them,
and none places anyone until a named person confirms it. In date order that
is not a job anyone finishes. `src/shortlist5ca.py` ranks it, by rules (no
AI call), from the stance file itself (kind, tally, lobbies), the vote
meanings (`src/vote_meanings.py`), the campaign files and the brief ledger:

* up: the whole text (+30) or a motion to reject it (+25), the last such
  vote on its bill (+10), a watched bill (+15), values already proposed
  (+15), a close margin (+8 to +20), split groups and members against their
  group (up to +25), a meaning line ready (+10), a campaign outcome (+25),
  a campaign's ground or a brief's bill (+10), recent (+5 to +15);
* down: amendments (-10), procedure (-30), near-unanimous votes (-15), and
  collated-only areas such as migration last (-100: they place nobody).

`python3 tools/country_5ca.py --cc CC --shortlist [--top 20]` writes
`docs/5ca-<cc>-shortlist.md`: the top N, each with its reasons and points,
the result and lobbies, the meaning line, the proposed values (or what a
person must read first) and the exact `--confirm KEY --by NAME` command
(the country's one named signer, else Christopher), a one-line command for
all the proposed ones in the list, and the best three per area. The Sunday
`editions-session-judge` job rewrites them (`--shortlist` on the 5CA step),
and the stance digest DM now leads with each country's top 5 and keeps the
counts as one line under them. **It confirms nothing**: the commands are
for a person to run after reading each item, and `--confirm` still refuses
a `needs_reading` entry and anyone not named in
`config/stance_signers.yaml`.

On the stance files of 11 October 2026 (laptop, no store tables for these
countries, so lobbies come from the files and meanings from the rules), the
tops are what a signer would pick: Poland's re-passage of the cohabitation
contracts law over the veto (232 to 199), Italy's questione sospensiva on
assisted dying in the Senato, France's final vote on the aide a mourir law,
the Dutch Embryowet initiative bill (CDA and JA21 split), Belgium's final
vote on palliative leave flagged near-unanimous.

### Automatic sign-off and amendments (11 October 2026, branch `stance-decisions-1011`)

Chris, 11 October 2026: "Automate the checks and we'll make it so teams can
amend as and when errors come up. Like we're doing with Canada." In Canada
he delegated ("Score for me and Greg can amend if necessary"); for the new
countries the delegation is to deterministic checks, and any country signer
amends afterwards. Chris is the signer for every country for now ("Me for
all, for now", `config/stance_signers.yaml`).

**What is confirmed automatically.** `tools/country_5ca.py --auto-confirm`
(src/country5ca.py, `auto_check` and `auto_confirm`) runs every Sunday in
`jobs/editions-session-judge.sh`, after `--draft` and before
`--signoff-doc`, `--sheets` and `--shortlist`, so the guides, sheets, pages
and canvases reflect it. It confirms a DRAFT entry only when every check
passes:

* `reading`: the entry has values (`needs_reading` has none);
* `drafted`: it is as the drafter left it: `status: draft`, stamped
  `drafted:` by the drafter, no `confirmed_by`, no `amended_*`, no
  `draft: true`, no comment inside the entry;
* `direction`: a bill direction applies (the one its why lines name, else
  the watched key), says `with` or `against`, is not on hold or
  `needs_reading`, and carries no flag; the entry has no flag of its own
  except a copy of a bill flag since cleared;
* `kind`: a vote on the whole text or a motion to reject it (an inverted
  vote asks a person to check the question), or an amendment or article
  watched for sign-off with a direction of its own, keyed by its division;
* `values`: yea, nay and both why lines are exactly what the rules give that
  direction and kind (`rule_values`, recomputed), so a hand edit fails;
* `placeable`: not struck (`placeable: false`: procedural calls stay for a
  person), with a recorded tally (the result line, else the lobbies, else
  the store's positions) that has members on both sides;
* `scope`: inside the country's sign-off scope (France: final votes,
  motions to reject and watched amendments).

Each confirmed entry gets `status: confirmed`,
`confirmed_by: "auto-check on delegation (Chris Joyce, 11 Oct 2026)"`,
`confirmed_on:` (the run's date) and `auto_checks:` (the checks' version,
`auto-checks v1 (2026-10-11)`). Confirmed, amended and hand-edited entries
are never touched. Everything that fails stays a draft and is listed with
the check it failed on an "Auto-check" line in `docs/5ca-<cc>-readings.md`
and `docs/5ca-<cc>-shortlist.md`; the stance digest says how many were
confirmed automatically that week and counts what still needs a person by
check. `--auto-confirm --dry-run` reports without writing.

**Directions that change.** `--resync-directions` (also weekly, just before)
brings an untouched draft into line when a person changes its bill's
direction: an entry that is exactly the rules' output for one direction gets
the rules' values for the new one, or becomes `needs_reading` (with the
bill's `read_first:`) when the direction is put on hold. Applied on 11
October to France's eight drafts on the palliative care bill (now on hold)
and the minors online bill (now against).

**Amending (any signer for the country).** Edit the reading in
`config/<cc>_stance.yaml` by hand with `amended_by:`, `amended_on:` and
`amended_why:`, or use the command, which stamps them, writes the values and
confirms the reading in the signer's name:

    python3 tools/country_5ca.py --cc CC --amend KEY --yea N --nay N --by NAME --why "..."

To take a reading out of play instead (it places nobody, confirmed or not),
`draft: true`, or the same command with `--take-out` in place of the values.
`--by` must be Chris or a name in `config/stance_signers.yaml` for that
country, and `--why` is required. An amended entry is never touched by the
automation again (the `drafted` check fails on `amended_*` and on
`draft: true`).

**First count** (dry run, 11 October 2026, against the laptop store of 9
October, read-only; the store held no new qualifying votes, so these are the
stance files' own drafts): 71 would be confirmed, 930 left for a person.
Italy 7 / 130, Switzerland 1 / 81, France 10 / 13, the Netherlands 2 / 210,
Belgium 2 / 2, Poland 29 / 163, Croatia 0 / 12, Slovakia 3 / 40, Spain
1 / 85, Brazil 2 / 11, Argentina 0 / 2, Mexico 0 / 3, Hungary 2 / 22,
Austria 3 / 19, Portugal 9 / 31, Chile 0 / 5, Ecuador 0 / 7, the Dominican
Republic 0 / 94; Peru, El Salvador and Guatemala have none. Of the 930, 879
need reading (amendments, articles, bills with no direction), 46 are
procedural, 2 have no tally in the file, 1 is Belgium's near-unanimous
palliative leave vote (its bill still flagged) and 2 sit on Portugal's
face-covering law, whose PT4 note is still written as a flag. Nothing was
confirmed by that run; the Sunday job applies it to the live store.

### Filling directions, and readings that never need a person (12 October 2026, branch `bill-positions-1012`)

**`--fill-directions`** (src/country5ca.py, `fill_directions`; weekly,
after `--resync-directions`, before `--auto-confirm`). A final, reject or
inverted vote drafted while its bill had no direction is `needs_reading`
("no bill direction is on file"), and nothing revisited it once a direction
was added. The step turns it into the rules' draft (values, why lines,
reasoning, the bill's flag copied) when the bill is `with` or `against` and
the entry is untouched: its `read_first` and `reasoning` exactly the
drafter's, stamped by the drafter, no values, flag, strike, amendment or
comment a person added. The direction is looked up from the stance file
alone: the watched key, the refs the `read_first` line names, then the
division's own key, so a vote whose store row names no bill ("this item")
takes a direction keyed by its division. A Dutch motion still takes only
its own zaak's direction, as in the drafter.

**Collated only.** A reading whose areas are all in
`config/stance_overrides.yaml` `excluded_from_5ca` (migration) can place
nobody (`sheet_pairs` writes no sheet for it), so `collated_only` keeps it
out of `counts` (a `collated` count instead), `auto_report` and so
`--auto-confirm`, the guide's lists (one "Collated only" list, no box), the
shortlist and the digest. The entries stay in the file.

**Out of play.** A bill Chris found no CitizenGO stake in has every vote
naming it `placeable: false` with a `reason:` and confirmed in his name: it
places nobody and is listed under Confirmed as "out of play". A reading
with `draft: true` is no longer shortlisted. A `flag:` starting "Left for a
person" lifts a reading in the shortlist (+40), the flag saying why.

### Every amendment read and scored (12 October 2026, branch `amendments-all`)

Chris, 12 October 2026: "score all amendments and reverse France's
decision". Every amendment and article vote on our ground is read and
scored in every country (docs/country-decisions-2026-10-12.md).

* **France's limit is lifted.** `SPECS["fr"]` has no `scope` (it was
  `final_or_watched()`, 10 October), so the drafter drafts every watched
  and tier-1 French vote, as for every other country. The scope machinery
  stays in the module, unused. **No prune removes an amendment entry**:
  `_prune` (behind `--prune-out-of-scope` and `--prune-off-ground`) keeps
  every `vote_kind: amendment` entry and reports it; a reader marks one
  `not_scored` instead. A read entry (any `amendment_*` field) also counts
  as hand-edited.
* **France drafted** against the store of 12 October 2026 (sha256
  07d9d0e89392, read-only): 1,083 new entries, 1,078 amendment and article
  votes (959 on the aide a mourir law DLR5L17N51670, 86 on the palliative
  care law, 40 on the minors online law) and 5 Senat motions the rules do
  not recognise; all `needs_reading`. The rules now read the Senat's
  "sur l'article N ..." and the Dominican "modificaciones propuestas" as
  article and amendment votes.
* **An amendment's own direction.** A reader records on the entry whether
  ADOPTING the amendment (or article) is with CitizenGO or against it:
  `amendment_direction: with|against`, `amendment_why:`,
  `amendment_source:` (the URL of the text read), and, only where a Yes
  does not adopt it (Brazil's "mantido o texto"), `amendment_yes_adopts:
  false`. A motion to delete an article is read as itself: adopting the
  deletion is with or against us. The rules give the values as for a bill
  direction (`amendment_values`: Yes +2 / No -2 when adopting is with us,
  swapped when against or when a Yes rejects). `amendment_flag:` holds
  anything a person must look at.
* **The checks.** `auto_check` treats an entry with an
  `amendment_direction` like a final vote: it must be untouched as the rules
  wrote it, carry a why and a source, have no `amendment_flag` (or `flag`),
  values exactly `amendment_values`, and a tally that splits members; then
  `--auto-confirm` confirms it on the delegation. `--fill-directions` also
  drafts an untouched `needs_reading` amendment entry given an
  `amendment_direction` by hand (`fill_amendments`).
* **Applying readers' decisions.** `python3 tools/country_5ca.py
  --apply-amendments FILE [--dry-run]` reads a JSON list (or
  `{"decisions": [...]}`) of `{cc, key, direction, why, source, flag,
  yes_adopts}`: `with`/`against` (why and source required) record the
  reading and draft the values; `unclear` leaves the entry `needs_reading`
  with `amendment_flag` shown in the guide ("Read, side unclear");
  `not_scored` makes it `placeable: false` with `reason: "Not scored
  (amendment reading, DATE): why"`. Confirmed, amended, hand-valued and
  non-amendment entries are refused with the reason (an entry drafted as
  `other` whose wording the rules now read as an article vote is accepted
  and becomes `amendment`). The tool exits 1 when anything was refused.
* **The reading worklist.** `python3 tools/amendment_worklist.py --db STORE
  --out FILE --summary FILE` lists every unread amendment entry (not
  collated only) with the vote's full wording from the store, the bill and
  its direction, result, tally, areas, identifiers from the store row and
  the wording (number, author, article, reading, prints, dossier) and the
  parliament's URLs (`sure: false` where a part must be filled in). First
  run, 12 October 2026: 1,555 items (FR 1,079, PL 141, IT 119, DO 76, CH 49,
  NL 31, ES 30, SK 13, HU 7, BR 4, CL 3, AR 1, AT 1, BE 1), written to
  `/Users/chrisjoyce/parl-judge/amendments/worklist.json` (outside the
  repo). No for/against judgement is made by the tools: that is the
  readers'.
* **Accepting flagged readings as drafted** (Chris, 12 October 2026: "Accept
  all as drafted"). `python3 tools/country_5ca.py --all-countries
  --accept-flagged-amendments --by NAME [--on DATE] [--dry-run]`
  (`accept_flagged_amendments`) takes the `amendment_flag` off every draft
  with/against reading whose values are the rules' own, unconfirmed, not
  amended, not struck, with no entry `flag` and no flagged bill, and records
  `amendment_accepted: "NAME, 12 Oct 2026: accepted as drafted (was
  flagged: ...)"`. The automatic checks ignore that field, so the reading
  confirms on Sunday. First run: 313 accepted.

## The new countries' tracker and partner sheet (10 October 2026, branch `camp-5ca-sheets`)

`tools/make_country_5ca_web.py`, the new-country counterpart of
`make_5ca_tracker.py`: ONE page with a country switcher (twenty-one
countries do not fit the UK tracker's single scroll), the tracker's look and
per-area block (the gradient bar, the change since last week, the names
behind each decisive column).

* **One gate.** The page reads `country5ca.publishable_sheets`, the same
  generator `run_sheets` now uses for the CSVs, so a page and a sheet cannot
  disagree: an area appears only with a confirmed reading that places
  someone.
* **Before sign-off** each country shows "Awaiting sign-off: N readings"
  (proposed, procedural, need reading) and no placement of any kind; a
  country with no qualifying vote says so. A country awaiting sign-off needs
  no store; one with confirmed readings whose store cannot be read is "not
  shown this week" internally and kept off the partner page (fail closed).
* **Internal** `docs/5ca-countries.html`: every country, plus the signer and
  the sign-off guide for each, and a hover with "based on" and confidence.
* **Partner** `partner_site/5ca-countries.html`: written only while at least
  one country has a confirmed placement, those countries only; removed
  otherwise. `src/partner.py` links it in the partner nav only while the file
  exists. No signers, guides or confidence.
* **AT, PT, NL**: a note above the sheets, and a DERIVED tag on each member
  placed from the group's vote (X5).
* English, as the UK 5CA pages; members and parties as each parliament
  names them. Weekly in `jobs/editions-session-judge.sh` after
  `country_5ca.py`; the Monday deploy ships the partner page.

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