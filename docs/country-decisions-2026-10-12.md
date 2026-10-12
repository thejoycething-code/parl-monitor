# Country editions: Chris's bill positions, 12 October 2026

Chris: "Draft the 248 bill positions, flag the unclear ones." Claude drafted
a direction for every bill the 5CA readings were waiting on; Chris settled
the themes below, accepted the medium and low drafts, and left six mixed
bills for a person. His decisions on the 126 bills that had no
`bill_directions` line are in `/Users/chrisjoyce/parl-judge/positions/decisions-2026-10-12.json`
(outside the repo), applied on branch `bill-positions-1012`. Read with
`docs/country-decisions-2026-10-11.md`.

## The themes

- **No stake, out of play.** A bill with no CitizenGO stake (misfiled by the
  keyword tagger, procedural, omnibus, incidental) places nobody.
- **Religious-symbol bans are all with us, veils included.** This reverses
  his 11 October call on Belgium.
- **Children online: same as France, against.** Croatia's under-15 social
  media bill and its DSA act, and Spain's minors-online bill, follow France's
  DLR5L17N53187.
- **Smacking bans: against** (parental rights): Slovakia 9/673 and 9/1218.
- **The Dutch motions on Islam and the persecution of Christians: with**
  (2026Z06865, 2026Z06863).
- **Spain, SUMAR's free-expression reform of the Penal Code (15/122/000006):
  with, the HazteOir team to confirm.**
- **Swiss individual taxation (24.026) and Polish divorce without a court
  (10/2121): against** (they weaken marriage in law).
- **Hungary, abolishing the Sovereignty Protection Office (T/123): with.**
- **Medium and low drafts: accepted.**
- **Six mixed bills: left for a person.**

## What was applied

**91 directions** (`bill_directions` in `config/<cc>_stance.yaml`, each with
`why`, `decided` and `drafted: "Claude, 12 October 2026"`, areas from the
votes that name the bill): NL 43, ES 12, AT 8, SK 8, FR 5, CH 3, HR 3,
PL 2, PT 2, and one each for AR, CL, DO, HU and MX. 90 are confirmed in
Chris's name (`confirmed_by: "Christopher Joyce"`, 12 October), as his 11
October decisions were, so the campaign briefs can take their ask from
them. Spain's 15/122/000006 is `status: draft` with a `flag:` (HazteOir to
confirm), so no reading on it confirms until the flag is cleared.

Three votes named no bill ("this item"): Argentina's sen-acta-2486 and
France's an-17-4839 and senat-2025-185. Their directions are keyed by the
division key; the drafter and the fill step now look a vote's own key up
last (`_direction_for`, `fill_directions`), and the automatic checks find
it from the why lines as for any bill.

Corrections made while applying, so a direction says what passing the
named item does:

- Spain 15/121/000052 is the Government's minors-online bill. The decision
  sheet put `with` on VOX's motion to return it, keyed by the bill; recorded
  as the bill **against** us, so a vote for the return is with us (Chris's
  France call).
- The why lines of the three headscarf bans (FR DLR5L16N49619, AT
  XXVIII/UEA/117 and XXVIII/UEA/158) still cited the old Belgium call, and
  the two Dutch Islam motions called our side uncertain; each now cites the
  12 October ruling.

**29 bills not scored**: every vote naming them (52 entries) is
`placeable: false` with `reason: "No CitizenGO stake (Chris, 12 Oct 2026):
..."`, confirmed in his name, so it places nobody and never waits for a
person. Two Swiss family-reunification motions (24.4444, 25.4039) are among
them as migration.

**6 left for a person**: no direction; their 7 entries carry
`flag: "Left for a person (Chris, 12 Oct 2026): ..."`, and the shortlist
lifts such an entry (+40) with the flag shown: NL 2026Z08649 (Israel-Gaza
context), 2025Z00250 (Embryo Act, mixed), 2026Z12645 (DSA and LGBTIQ
content); FR DLR5L17N53936 (Islamist entryism); PL 10/529 (audit of the
media regulator); HR 11/228 (EU Media Freedom Act).

## Religious-symbol bans: what changed

- Belgium 56/149, 56/428, 56/429: `against` to `with`, confirmed 12 October,
  `decided:` citing this file. The one drafted reading (56/95/21, the motion
  to reject 56/149) followed by `--resync-directions`.
- Austria XXVIII/A/1054 and XXVIII/A/1059 (face-veil law and forced
  veiling) and Portugal XVII/J/47 (the face-covering law) were already
  `with`; now confirmed with a `decided:` line. Portugal's PT4 note moved
  from `flag:` into `decided:`, so its two drafts can confirm.
- New: FR DLR5L16N49619, AT XXVIII/UEA/117 and XXVIII/UEA/158, all `with`.
- Quebec (`config/prov_stance.yaml`), read until now as against us and
  flagged for Chris: the signs of ten confirmed laicity readings are
  flipped (Bill 21 principle and adoption, Bill 52, Bill 62 principle and
  adoption, Bill 94 of 2011, Bill 94 of 2025 principle and adoption, the
  2017 Roy motion and the 2019 David motion), each with a comment citing
  this file. Chris confirmed the Quebec flips the same day ("Keep the flips,
  Bill 9 against"): Bill 9 (43-2) goes beyond dress to ban religious
  practice on public premises, so its Yea stays against us.
- No other stance file has a symbol, headscarf, face-veil or burqa ban.

## The fill step and the migration filter

**The gap.** A final, reject or inverted vote drafted before its bill had a
direction is `needs_reading` ("no bill direction is on file"). The drafter
never rewrites an entry and `--resync-directions` only touches drafts, so
adding the direction later changed nothing. `tools/country_5ca.py
--fill-directions` (src/country5ca.py, `fill_directions`) turns such an
entry into the rules' draft once its bill is `with` or `against`, but only
when it is untouched: `read_first` and `reasoning` exactly the drafter's,
no values, flag, strike, amendment or comment added. It needs no store. It
runs weekly in `jobs/editions-session-judge.sh` after `--resync-directions`
and before `--auto-confirm`. Run now on every country: 112 entries drafted.

**Migration.** Area 11 is excluded from the 5CA
(`config/stance_overrides.yaml` `excluded_from_5ca`). A reading whose areas
are all excluded (`collated_only`) now never counts as waiting: it is left
out of the counts, the automatic checks, the guide's lists (shown once as
"collated only", no box), the shortlist and the digest. Nothing is deleted.
217 unconfirmed entries are collated only today (NL 120, ES 36, PT 19, IT 9,
CH 9, PL 8, EC 6, HR 4, AT 3, HU 2, CL 1). A reading taken out of play with
`draft: true` is no longer shortlisted either.

## Dry run of the automatic sign-off

`--auto-confirm --dry-run` against the laptop store of 9 October, read-only,
after the fill: 164 would be confirmed, 568 left for a person (from 71 and
930 on 11 October). Would confirm / left: Italy 7 / 121, Switzerland 12 / 49,
France 12 / 8, the Netherlands 40 / 43, Belgium 2 / 2, Poland 33 / 147,
Croatia 0 / 7, Slovakia 12 / 26, Spain 14 / 35, Brazil 2 / 11, Argentina
0 / 2, Mexico 0 / 3, Hungary 4 / 10, Austria 11 / 7, Portugal 13 / 2, Chile
0 / 4, Ecuador 0 / 1, the Dominican Republic 2 / 90; Peru, El Salvador and
Guatemala none. Several filled votes stay for a person because they were
unanimous (they tell nobody apart) or inverted (Croatia). Nothing from the
dry run was committed; the Sunday job applies it to the live store.

## Every amendment read and scored; France's limit lifted

Chris, 12 October 2026: **"score all amendments and reverse France's
decision"**.

- **Every amendment and article vote on our ground is read and scored, in
  every country.** A reader records whether ADOPTING it is with or against
  CitizenGO (`amendment_direction`, with `amendment_why` and the URL of the
  text read in `amendment_source`), and the rules derive the vote's values
  as for a bill direction; a reading with no flag confirms on the
  automatic checks like a final vote. Readers' decisions are applied with
  `tools/country_5ca.py --apply-amendments FILE` (docs/5ca-notes.md, "Every
  amendment read and scored").
- **France's 10 October limit is reversed.** Sign-off is no longer limited
  to final votes, motions to reject and watched amendments: France has no
  sign-off scope, the drafter drafts every watched and tier-1 vote, and no
  prune ever removes an amendment entry. Drafted the same day from the
  store of 12 October: 1,083 new French entries (1,078 amendment and
  article votes), all needing a reading.
- **The worklist.** 1,555 amendment and article votes across 14 countries
  wait for a reading (France 1,079, Poland 141, Italy 119, the Dominican
  Republic 76, Switzerland 49, the Netherlands 31, Spain 30, Slovakia 13,
  Hungary 7, Brazil 4, Chile 3, Argentina, Austria and Belgium 1 each):
  `/Users/chrisjoyce/parl-judge/amendments/worklist.json` (outside the
  repo), made by `tools/amendment_worklist.py`.
