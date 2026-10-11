# Country editions: Chris's decisions, 11 October 2026

Answers to the "Waiting on Chris" list in `docs/country-parity-handover.md`.
Read with `docs/country-decisions-2026-10-10.md` (the spec). Applied on
branch `stance-decisions-1011`.

## 1. Who signs

"Me for all, for now." Chris is the signer for every country in
`config/stance_signers.yaml` (as "Christopher Joyce"). Country team members
are added beside him as they take over.

## 2. The flagged bill directions

Each set in `config/<cc>_stance.yaml` `bill_directions`, its flag cleared, a
`decided:` line citing this file, and confirmed in Chris's name
(`--confirm-direction`, so the campaign briefs take their ask from it):

| Country | Bill | Decision |
|---|---|---|
| Belgium | 56/149, 56/428, 56/429 (the three religious-symbol bans) | against us |
| Poland | 10/31 (state-funded IVF) | against us |
| Portugal | XV/R/62 (the euthanasia referendum, drafted as with us) | against us |
| France | DLR5L17N51672 (palliative care) | HOLD until the text is read |
| France | DLR5L17N53187 (minors online) | against us |
| Guatemala | 5376 | against us |
| Hungary | T/122 | against us |
| Italy | 19/C.2575 (puberty blockers) | with us |
| Italy | 19/C.402 (conversion-practices ban) | against us |
| Netherlands | 35715 (sex-work licensing) | against us |

- Portugal: CitizenGO likes grassroots decisions over an authoritarian
  state, but is against euthanasia, so a referendum on euthanasia is read as
  against us.
- France, palliative care: if the text legitimises assisted dying it is
  against us. Until it is read the direction is `hold` with
  `status: needs_reading` and a `read_first:` line, so nothing is drafted or
  confirmed from it; its four drafted readings became `needs_reading`.
  France's four drafts on the minors online bill were redrafted to the new
  direction (`--resync-directions`).
- Ecuador's flags are explanatory only: left as they are.

## 3. The Dutch week ahead

The Dutch edition (votes only, NL3) shows the week ahead. The edition
already had the section; the votes-only DM now carries it too
(`dm_ahead=True` in `src/editions/nl.py`, `Country.dm_ahead` in
`src/country_edition.py`).

## 4. The rainbow-flag motion

The watched Dutch motion in dossier 21501-02 (zaak 2026Z21728) stays
watched. No change.

## 5. Member intelligence groups

`config/member-intel-groups.yaml` is approved as drafted.

## 6. Sign-off: automatic, with team amendments

"Automate the checks and we'll make it so teams can amend as and when
errors come up. Like we're doing with Canada." As in Canada ("Score for me
and Greg can amend if necessary"), readings are confirmed on Chris's
delegation, here by deterministic checks, and a country signer amends any
reading afterwards. Built as `tools/country_5ca.py --auto-confirm`,
`--resync-directions` and `--amend`, run weekly in
`jobs/editions-session-judge.sh`; the checks and the amendment path are in
`docs/5ca-notes.md`, "Automatic sign-off and amendments".

## 7. Other answers recorded

- Parliament emails: most were sent on 9 October from cjoyce@citizengo.net
  (Hungary W-API, Spain Senado, meineabgeordneten.at, Paraguay, Open States,
  Australia aph.gov.au). Costa Rica bounced (its participation address takes
  internal senders only). Guatemala's court, El Salvador and the France and
  Belgium video-agreement requests are handled separately.
- Looker list prefixes: handed to the work-account Claude, which has Looker
  access.
- Debate reports keep English summaries with verbatim source-language
  quotes.
