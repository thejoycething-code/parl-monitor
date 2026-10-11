# Country editions: parity plan and handover (updated 10 October 2026)

Written by the personal-account Claude session that built the 30 new
countries and their parity layers (9-10 October 2026), for Chris's
work-account Claude to take over. Everything it built is merged to main.
Read this with `docs/country-decisions-2026-10-10.md` (Chris's signed-off
decisions, the spec) and each `docs/<country>-scope.md` (sources, quirks,
phase lists, "Waiting on Chris"). The Mini runbook is `docs/mac-mini.md`.

## Start here: where things stand

**Built and merged (PRs on thejoycething-code/parl-monitor):** collectors and
weekly jobs for 30 countries (#14), Brazil areas 14-15 (#17), Latam monitor
and alerts (#19, noise filters #23), Mini install script (#20), the edition
framework and 14 own editions (#47, #49, #50, #52, fixes #55), Hungary gazette
and karzat backfill (#57, #58), free session judge (#60), 5CA with sign-off
(#65, France scope #77), week ahead (#66), member profiles (#67), 5CA tracker
and partner sheet (#68), campaign targets (#69), constitutional courts, UY5,
BO4, OCR stub (#70), debate packs (#71), later phases set A (#72), debates and
questions (#73), campaign briefs (#74, English per rule 6 #75), same-day vote
briefs (#76), debate today and live read (#78), taxonomy noise round (#79),
small fixes (#80). UK-parity round, 11 October: health summary and Drive
publishing (#82), partner vote pages, vote tracker and bill timelines (#83),
petitions and consultations (#84), collector time budgets and the El Salvador
fallback (#85), member intelligence: committees, groups, declared interests,
Brazil's party line (#86), the review window, built but OFF (#88), store
compression (#89), plain-English vote meanings (#90), daily sweep of new
items (#91), speech clips (#92).

**Nothing is published from a 5CA yet.** Every stance is a draft: 975
readings await sign-off across the countries (France limited to final votes
and watched amendments). Briefs, packs, targets, the partner sheet and the
live read all render "awaiting sign-off" until a named person confirms.

**Waiting on Chris (decisions and actions):**

1. Name a signer per country in `config/stance_signers.yaml` (country teams
   are the natural owners), then start confirming readings
   (`docs/5ca-<cc>-readings.md`, `tools/country_5ca.py --cc CC --sign-from-doc --by NAME`).
2. Review the flagged bill directions in the stance files (Belgium's
   religious-symbol bans read as against us while CitizenGO supports
   Portugal's face-covering law; IVF; the euthanasia referendum).
3. Check France's five aide a mourir decrees in `config/watchlist-fr.yaml`
   against the promulgated law (drafted from the first-reading text).
4. Check the Looker list prefix per country before the first petition export
   (`docs/campaign-benchmarks.md`; the prefixes are guesses).
5. Send the parliament emails drafted in his Gmail (three still lack an
   address): Hungary W-API token, Spain Senado, Costa Rica, Paraguay, El
   Salvador missing votes, Guatemala court, meineabgeordneten.at.
6. Update the work account's **debate-day-net** scheduled task from
   `ops/scheduled-tasks/debate-day-net.md` (adds STEP 1B, debate today for
   NL, CH, FR, BE). It lives on the work account, not the personal one.
7. Whether the Dutch edition (votes only, NL3) should show the week ahead.
8. Whether the one watched Dutch motion in dossier 21501-02 (the rainbow-flag
   motion, zaak 2026Z21728) should stay watched (it now alerts in the daily
   sweep).
9. Review the flagged groups in `config/member-intel-groups.yaml` (which
   cross-party groups count as "on our ground").
10. Confirm four petition thresholds read from the law, not the sites: Austria
    500 signatures (Bürgerinitiative), Portugal 1,000 and 7,500, Switzerland's
    18-month collection deadline, Belgium's regional split of 25,000.
11. Campaign openings found on 11 October: an Assemblée nationale petition
    against the aide a mourir law (48% of 100,000); Italy's "PMA per tutte"
    initiative (88% of 50,000, closes 8 December); Austrian Volksbegehren on
    the abortion paragraphs and the abortion pill.
12. Speech clips: France and Belgium need prior agreement for video
    (communication@assemblee-nationale.fr; the Chamber), then set
    `fr.agreement` / `be.agreement` in `config/clip-sources.yaml`.
13. DONE (11 October 2026, #95): the Mini's run slot is first in, first out
    (a ticket queue in `tools/mini_run.sh`). Keep hand backfills out of the
    overnight weekly window.
14. Whether to raise the weekly free-judge cap (`SESSION_JUDGE_MAX`, about
    100 items): 295 vote meanings wait for it.

**Still to run on the Mini (store writers, one at a time):**

- `latam-courts-backfill`: DONE (10 October, 03:22Z).
- `sk-docs-backfill`: DONE (11 October 2026). Run 1 read the whole document
  backlog (then timed out after publishing; the budget now comes from
  `tools/collector_budget.sh`, #94); runs 2 and 3 found nothing left.
  The one-shot launchd job is removed.
- Austria and Portugal weeklies: rerun 11 October 2026 (kickstarted after the
  Slovak runs, queued in order by the FIFO run slot, #95); both published and
  sent their editions.
- Speech clip tools: INSTALLED 11 October 2026 (user site of the Mini's
  /usr/bin/python3 3.9: imageio-ffmpeg with ffmpeg 7.1, yt-dlp 2025.10.14,
  faster-whisper 1.2.1; Whisper "small" pre-fetched, 464 MB in
  ~/.cache/huggingface). Clips can be cut for CH and AT, and NL from a
  hand-downloaded video; FR and BE refuse until agreement is recorded. Test
  clip cut 11 October 2026 (CH 25.455, Jessica Jaccoud, 44.7 s, match 0.86):
  captions and the ParlCH credit checked; the test clips and footage were
  then deleted on both the Mini and the laptop. Clip
  footage under `data/clips/*/windows/` and `final/` is git-ignored (#99);
  a person picks who goes in (the pick ranks by topic, not by side).
- Compressed publish: VERIFIED 11 October 2026. The store (1.77 GB) uploads
  as `parl-monitor.db.gz`, 431 MB, compressed in 16 s; the raw asset is gone
  from the release. The size warning fires because the uncompressed store is
  above 1.6 GB: plan a split before the compressed asset nears 2 GiB.
- Install Tesseract when wanted (X7; steps in docs/mac-mini.md) to switch on
  the OCR steps.
- Check the first `vote-briefs-daily` log: can the Mini reach `dati.senato.it`
  (it refuses the laptop)?
- The store is now published gzipped (`parl-monitor.db.gz`, 11 October 2026; docs/mac-mini.md, "The store is published compressed"): nothing to do on the Mini, but a branch without that change cannot pull once the raw asset is retired, so merge main into any branch before testing it there.
- The first Sunday 16:45 run of `editions-session-judge` (Claude Code on the
  Mini is signed in to the work account; over SSH it reports "Not logged in"
  because the keychain is locked for SSH, which is expected).

**The review window (#88) is built but OFF** (Chris, 11 October 2026: the UK
retired its own review loop on 21 August). Editions are DMed straight after
each weekly as before. To switch a country on, set `review: true` on its line
in `config/edition-review.yaml`: the weekly then writes a draft and
`reviews/<cc>-review-<date>.md` (keep / cut / edit, note, hold or now), and
the Mini's `edition-publish` job (installed; 06:31 and 21:10 London, exits at
once when nothing is due) sends it at 06:30 the next morning and keeps one
combined weekly Asana reading task (needs `asana_pat` in the Mini's
`config/secrets.yaml`).

**The store is published compressed (#89).** It had reached 1.76 GB against
GitHub's 2 GiB per-asset limit; gzip cuts it about 4x and the upload from
about 15 minutes to 4 or 5. Pushes warn above 1.6 GB uncompressed and refuse
above 2 GiB. If it keeps growing, the next step is splitting the new
countries into their own store file (Chris: "further changes in the future
if necessary").

**What could come next (not started):** regions and Länder (IT3, AT6, PE4,
Spain's autonomous communities, Mexico's states); Croatia and Slovakia
debates; Polish transcripts when the Sejm endpoint answers; Brazilian
speeches (cost); Belgian, Portuguese, Slovak, Hungarian and Mexican agendas;
committee agendas; Croatian and Slovak speeches; France's HATVP interest
declarations (members' own items only); daily sweep for BE, PT, HR, SK, HU,
AR, MX and Latam; Africa (Kenya, Nigeria, Uganda: Chris's aim is Q1 2027); a
native read of each language's term list.

## What exists now

| Layer | UK | DE | US / IE / AU | CA | New countries |
|---|---|---|---|---|---|
| Collector (bills, votes, members) | yes | yes | yes | yes | yes, 25 countries (see below) |
| Weekly edition, Slack DM to Chris | yes | yes | yes | yes | 14 own editions + Hungary gazette edition + one monthly Latam edition |
| Weekly review window (edit or cut before the DM, Asana reading task) | yes (Sunday pull review file, Monday publish; the UK editorial loop and its Asana task were retired 21 Aug) | no | no | no | **built** 11 Oct (`src/edition_review.py`, `tools/edition_review.py`, `config/edition-review.yaml`, branch `ukp-review-window`): all 15 own editions and the Latam monthly write `reviews/<cc>-review-<date>.md` (keep / cut / edit, note, hold / now, merge-preserving) and DM at 06:30 London the next morning via the Mini job `edition-publish` (06:31, 21:10); one combined Asana reading task a week; vote briefs and Latam alerts stay immediate |
| Triage | API judge | API judge | API or session judge | session judge (provinces) | free session judge, Sundays 16:45 (`tools/edition_judge.py`) |
| Noise filters, mute lists | yes | partly | yes | yes | yes (`src/noise.py`, `config/edition-noise-<cc>.yaml`) |
| Same-day vote briefs (division watch) | yes | no | yes (`*_division_brief.py`, `src/vote_brief.py`) | no | yes, 20 countries (`src/country_vote_brief.py`): daily for NL, PL, CH, BR, IT; after the weekly for the rest |
| Daily sweep of new items (bills, motions, questions, agenda) | yes (`tools/day_sweep.py`) | no | EU (`tools/eu_day_sweep.py`) | no | **built** 11 Oct (`src/country_day_sweep.py`, readers `src/day_sweep_sources.py`, branch `ukp-day-sweep`): a step of the one daily job (`jobs/vote-briefs-daily.sh`) for NL, PL, CH, BR, IT, AT, FR (agenda only, once a day) and ES (from 23 Dec); tier 1 and watched, the vote briefs' gate; one combined DM with the vote briefs; de-duplicated against the editions, the vote briefs and `data/day-sweep/<cc>.json`; samples `docs/day-sweep-samples/` |
| 5CA (member stance, five columns) | yes | yes | yes | yes | **built** 10 Oct (`tools/country_5ca.py`, branch `parity-5ca`): sheets from confirmed readings only, none confirmed yet; AT/PT/NL rows derived (X5). Tracker and partner sheet built 10 Oct (`tools/make_country_5ca_web.py`, branch `camp-5ca-sheets`): `docs/5ca-countries.html` weekly, "awaiting sign-off: N readings" per country; partner page gated until a country has a confirmed placement |
| Stance sign-off per vote (`config/*_stance.yaml`) | yes | yes | yes | yes | **built** 10 Oct (#65): 975 readings awaiting sign-off after France was limited to final votes and watched amendments (#77), weekly digest DM; signers per country to name (`config/stance_signers.yaml`) |
| Campaign targets and outcomes (`ca_campaign.py`, the 5CA Evaluate) | yes | no | no | no | **built** 10 Oct (`tools/country_campaign.py`, branch `camp-targets`): open, targets, add, find, outcome, score; targets from confirmed readings only, candidates by vote record until then; petition numbers none yet (UK only) |
| Member profiles | yes | yes | US yes | no | yes, 23 countries (`profiles/<cc>/`, weekly step; X5 derived and X6 as-listed labelled; HR and CL party history sourced), branch `parity-profiles` |
| Public vote pages, vote tracker, bill timelines | yes (`mp-votes.html`, devolved, timelines) | yes (`de-votes.html`) | yes (`us-`, `ie-`, `au-votes.html`) | no | **built** 11 Oct (`tools/make_country_votes.py`, src/country_votes.py, branch `ukp-vote-pages`): `partner_site/<cc>-votes.html` for the 22 countries with member or party-group votes, `votes-countries.html` (tracker) and `bill-timelines.html` (watched bills: stages, agenda slots, votes), behind the partner passphrase, weekly in `editions-session-judge`; records only, no for/against before a reading is CONFIRMED; X5 derived and X6 as-listed labelled, non-attached never counted (#80) |
| Member intelligence (interests, cross-party groups, committees, whip lines) | yes (`pull_interests.py`, `load_appgs.py`, `pull_pbc_attendance.py`, `annotate_whips.py`) | part | no | no | **built** 11 Oct (`tools/member_intel.py`, `src/member_intel.py`, branch `ukp-member-intel`), a step of 7 weeklies before the profiles: BR fronts (frentes parlamentares) and organs, NL committee seats and nevenfuncties, CH committees and Interessenbindungen, PL committees, FR committees, délégations and groupes d'études, IT Camera organs, AT committee functions. Groups on our ground flagged by name (`config/member-intel-groups.yaml`) in each profile and a "Groups on our ground" list in each index. Whip: Brazil's orientação de bancada beside each Câmara position (the only published whip). Not built: FR HATVP (open, heavy, later), AT interests, ES (dissolved), AR, CL (stale service), IT Senate (403) |
| Debates / speeches | yes | yes | IE, AU | yes | NL, CH, AT, FR, BE (10 Oct, `tools/<cc>_chamber.py`); not PL (transcripts never answered), BR (per-deputy cost), IT (Senate 403), ES (dissolved), PT (questions only), HR, SK |
| Parliamentary questions | yes | no | IE | no | NL, PL, FR, PT, BR requests (10 Oct, `tools/<cc>_chamber.py`); already in the editions: SK interpellations, AT J/AB, CH Vorstösse, HU, UY pedidos, HN press, BO written questions: BO4, built 10 Oct, `parity-phases-b` |
| Committees, courts, petitions, consultations | yes | yes | US courts | yes | constitutional courts (X8) built for CO, EC, PE, PT (10 Oct, `parity-phases-b`); GT gap; no committees. **Petitions and consultations built** 11 Oct (`src/petitions.py`, `tools/country_petitions.py`, branch `ukp-petitions-consult`), a step of 11 weeklies and an edition section: FR (AN and Sénat e-petitions), AT (Ministerialentwürfe in Begutachtung, Petitionen, Bürgerinitiativen, Volksbegehren), CH (Vernehmlassungen, Petitionen, Volksinitiativen in collection), IT (firmereferendum initiatives and referendums, ParteciPa), PT (petições), PL (Sejm consultations, citizens' bills), BE (Chamber petitions), NL (petitions handed to the Kamer), BR (e-Cidadania ideas and public vote, Brasil Participativo), AR (consultapublica), CO (SUCOP, in the Latam edition); not NL internetconsultatie or PL legislacja (robots.txt), ES (no central list), CL (403), MX |
| Week ahead / agenda | yes | yes | yes | no | yes for NL, PL, CH, BR, IT (Camera), FR, AT, ES (fills from 23 Dec), AR (Senate), HR; not BE, PT, SK, HU, MX or Latam (item 4) |
| Debate packs, campaign briefs, campaign targets | yes | yes | no | yes | debate packs **built** 10 Oct (`tools/country_debate_pack.py`, manual, 26 countries; placements from confirmed readings only, none yet); campaign briefs **built** 10 Oct (`tools/country_briefs.py`, a weekly step): drafts in English per rulebook rule 6 (#75), NOT READY until stances are confirmed; targets **built** (#69) |
| Speech clips for social (`social_cut`, `speech_cut`, `pick_speeches`) | yes | no | no | no | **built** 11 Oct (`tools/country_clips.py`, branch `ukp-speech-clips`, manual, nothing posted): CH and AT open (each speech's own official MP4); NL manual (Debat Direct's archive answers us with a placeholder: a person downloads the speech, `--video`); FR and BE located to the second but the cut refuses until the parliament's written agreement is recorded (`config/clip-sources.yaml`); BR, PL, IT, ES not built (no speeches stored). Not yet run end to end: the Mini lacks the footage bundle |
| Debate today, live read | yes | no | no | no | **built** 10 Oct (`tools/country_debate_today.py`, `tools/country_live_debate.py`, branch `camp-live-debate`) for the four countries whose chamber publishes the same day: NL, CH, FR, BE; not AT (next day or later) or the question-only countries. Before sign-off the live read names no contradiction ("awaiting sign-off"); debate today is a step of the 16:45 net task |
| Debate report (report and social copy after a debate, DM for approval, canvas) | yes (`tools/debate_report.py`, one paid call) | no | no | no | **built** 11 Oct (`tools/country_debate_report.py`, `src/country_debatereport.py`, branch `ukp2-debate-report`, manual) for the five countries whose speeches we store: NL, CH, AT, FR, BE. English report from templates over the record (no paid AI): speakers on our ground with a verbatim source-language passage each, translations by a person or the free session judge (`--queue-out`/`--queue-in` via `tools/session_judge.sh`), the debated bill's votes (found by the reference in the title, `--item` or a debate pack) and the latest on the same ground with tallies, group splits and vote meanings; clip pack linked. AWAITING SIGN-OFF, no verdicts, until the readings shown are confirmed. DM to Chris alone; `--approve --by NAME` records approval against the files; `--publish` makes the canvas with the UK's code, shared with Chris alone (never a channel), rewritten in place on a re-run. Samples `docs/debate-report-samples/` |
| Health summary, Drive | health DM; briefs and debate footage on Drive | health DM | health DM | health DM | **built** 11 Oct (branch `ukp-health-drive`): the 07:30 health DM has one compact section per region (Europe, Latam) plus shared jobs, failed and stale jobs first, step gaps by step, editions behind, the countries' overdue sources (`src/country_health.py`); briefs as Sheets from the UK template and real debate packs on Drive under `Country editions/<Country>/` in the Automated Briefs shared drive, a step of the Sunday `editions-session-judge` (`tools/country_drive.py`, ledger `data/country-drive.json`, at most 30 new sheets a run) |
| Regional / state parliaments | devolved | Länder (part) | US states (in progress) | provinces | **no** (later, per decisions) |
| Vote meanings (what a Yes and a No meant) | yes (`meaning_aye`/`meaning_no`, written by hand) | no | no | no | **built** 11 Oct (`src/vote_meanings.py`, `tools/vote_meanings.py`, branch `ukp-meanings`): every watched and tier-1 vote in the 21 countries with recorded votes, rules first, then the free session judge after the editions' scores within the same ~100 items a week; stored per division (`vote_meanings`); a person overrides in `config/vote-meanings-<cc>.yaml`; shown in editions, the Latam monitor, vote briefs, profiles, debate packs and the 5CA readings guides |
| Later phases, set A (item 6) | | | | | **built 10 Oct** (branch `parity-phases-a`): FR5 Senat votes and dossiers, NL4 Eerste Kamer votes and bills, IT2 dati.camera.it for the Camera, CH6 Swiss Italian texts, SK6 Slovak bill documents |

New-country collectors and what their vote data supports:

- **Member-level votes** (5CA possible): Italy, Switzerland, France
  (Assemblée), Netherlands (mostly party votes, X5 derived), Belgium, Poland
  (Sejm), Croatia, Slovakia, Spain (Congreso), Brazil, Argentina (Senate),
  Mexico (Chamber), Chile, Peru (partial, scans lost), Ecuador, Dominican
  Republic (Chamber), El Salvador, Guatemala (GitHub only), Hungary
  (karzat, 9 May to 28 Aug only).
- **Party-group votes only** (5CA by party, X5 derived and labelled):
  Austria, Portugal, Netherlands.
- **No member votes**: Colombia (current Congress), Bolivia, Panama,
  Honduras, Uruguay, Venezuela, Nicaragua; Costa Rica and Paraguay blocked.

## The parity work, in priority order

### 1. Same-day vote briefs (cheapest win) -- BUILT 10 October 2026

Branch `parity-vote-briefs`: `src/country_vote_brief.py` (shared, from the
editions' and the Latam monitor's own readers), `src/vote_brief_sources.py`
(the daily direct readers), `tools/country_vote_briefs.py`, a step in each
country's weekly job and one daily Mini job (`jobs/vote-briefs-daily.sh`);
see docs/mac-mini.md, "Vote briefs for the new countries", and the samples
in `docs/vote-brief-samples/`. The plan as written:

Generalise `src/vote_brief.py` (IE/AU/US already share it) to the new
countries with member-level votes, reading from each `<cc>_store` after the
weekly collection, or from the source directly where it is cheap (NL OData,
PL Sejm API, CH OData, BR Câmara API publish same-day). Watched and tier-1
votes only, DM to Chris, de-duplicated like `tools/latam_alerts.py`.
No new decisions needed.

### 1b. Daily sweep of new items -- BUILT 11 October 2026

Branch `ukp-day-sweep`: the UK day sweep's same-day alert, for what is NEW on
our ground and not only votes. `src/country_day_sweep.py` (the rules, the
ledger, the rendering), `src/day_sweep_sources.py` (one reader per country
over its own collector's parsers and classifiers, each through the cheapest
query its source answers), a step of the existing daily job: no second daily
job. `tools/country_vote_briefs.py --daily` reads the votes, then the new
items, into the same throwaway store and sends ONE DM to Chris (vote briefs
first, then new items; nothing when nothing). Tier 1 with the noise rules'
minimum evidence, or watched; a judged item only at 2 or 3. Never what Chris
has seen: `data/day-sweep/<cc>.json` (the first pass seeds silently), the
country's editions of the last three weeks, and the run's vote briefs.

Measured 11 October 2026 (about 45 s for the whole daily run, votes and
sweep): NL 2 requests + agenda 1 (its motions are the sweep's own items:
the Dutch edition stays votes, speeches and questions, NL3); PL 3 + 1; CH 2
+ 1-2; BR 1-2 + a pauta per deliberative event; IT 2 SPARQL + 2; AT 2
(the item list restricted by `DATUM_VON`, found that day) + the
Tagesordnungen; FR the agenda zip only, once a day, archived only on a day
it alerts (bills and questions are 10.7 and 55 MB nightly dumps: weekly
only); ES 3 from 23 December. Not swept: BE, PT, HR, SK, HU, AR, MX and the
Latam countries (not measured for a daily read in this pass; Argentina's
Senate agenda is the likeliest next one; the Latam instant alerts cover
the Latam countries after each collection).

### 2. 5CA and stance sign-off (needs people)
5CA (`docs/5ca-notes.md`) needs CitizenGO's position on each vote that counts
(`config/<cc>_stance.yaml`, signed off by Chris or the country team, as with
Canada's C-218). Build per country: stance drafts generated from the watched
and tier-1 votes, a sign-off flow, then `make_5ca`-style output and the
tracker. Without sign-off the 5CA cannot be published. Ask Chris who signs
off per country (country teams are the natural owners). Start with the
countries with the richest member data and live campaigns: Poland, Italy,
Spain (after 23 December), Croatia, Slovakia, Brazil.

**Built 10 October 2026 (branch `parity-5ca`; docs/5ca-notes.md, "The new
country editions").** `tools/country_5ca.py` drafts readings for every
watched and tier-1 vote by rules (area, the bill's direction from a
`bill_directions` line, the kind of vote; `needs_reading` where unclear),
confirms only with `--by NAME` and a date, and writes sheets from confirmed
readings only. `tools/stance_digest.py` DMs Chris the weekly list of what
waits. Still open: Chris to name the signer per country in
`config/stance_signers.yaml`, and to confirm the first readings.

### 3. Member profiles
One profile per member from the stores already collected (party history,
votes on our ground, watched-bill authorship where the source has it).
Reuse the US/DE profile code. X6 applies: party at the vote needs party
history before member-level claims (HR, CL, GT currently show party as
listed).

**Built 10 October 2026 (branch `parity-profiles`).** `src/member_profiles.py`
(one generic generator, a few SQL statements per country) and
`tools/member_profiles.py <cc>`, a step of every new country's weekly job:
`profiles/<cc>/<member>.md` and `index.md` for AR, AT, BE, BR, CH, CL, CO,
DO, EC, ES, FR, GT, HR, HU, IT, MX, NL, PE, PL, PT, SK, SV, UY. Votes come
from each edition adapter with its noise rules and judge scores (the
framework's `item(division=)` field, additive); positions verbatim; party at
the vote with its basis on every line. X6: Croatia's transcripts
(`tools/hr_party_history.py`, `hr_party_seen`) and Chile's senators from the
BCN (`tools/cl_senate_parties.py`); Guatemala, Ecuador, Colombia and Belgium
labelled "not party at the vote". X5: AT, PT, NL positions DERIVED, labelled.
Authorship where the store links it (PT, AT, FR, BE, CH, AR, PE, CL, CO);
questions for SK, UY, AT. Not built: Bolivia, Panama, Honduras (no member
records on our ground), Mexico authorship (presenter is prose).

### 3b. Member intelligence -- BUILT 11 October 2026 (branch `ukp-member-intel`)

Registers of interests, cross-party groups, committee membership and whip
lines for the new countries, generalising the UK's `tools/pull_interests.py`,
`tools/load_appgs.py` and committee rosters. `src/member_intel.py` (parsers,
fetchers, three shared tables `mi_groups`, `mi_interests`, `mi_runs`) and
`tools/member_intel.py <cc>`, a step of each weekly before
`tools/member_profiles.py`. Probed 11 October; every source is the
parliament's own open data:

| Country | Built | Source and size | Rows (11 Oct) |
|---|---|---|---|
| BR | frentes parlamentares and members; every deputy's open organs (committees, CPIs); whip line | Câmara dadosabertos API and bulk `orgaosDeputados-L57` (one 7.7 MB file); the 8 fronts on our ground every week, the other 312 an eighth a week (3 s each) | 3,147 organ seats; 9,640 front memberships from 47 of 320 fronts (the rest fill over 8 weeks; `--full` reads all, about 15 minutes) |
| NL | committee seats (vast and plv.), nevenfuncties | Tweede Kamer OData v4 (CC0), sitting members | 1,465 seats, 1,213 nevenfuncties |
| CH | committee memberships, Interessenbindungen | ws.parlament.ch OData (MemberCommittee, PersonInterest) | 932 memberships, 1,971 interests |
| PL | every committee and its members | Sejm API, one request | 1,050 memberships |
| FR | committees, délégations, commissions d'enquête, missions, groupes d'études | AN open data AMO10 (Licence Ouverte); friendship groups left out | 6,607 memberships |
| IT | Camera organ memberships (committees, giunte, inquiries) | dati.camera.it SPARQL (CC BY), matched by name | 1,162 (29 not matched) |
| AT | committee functions, Nationalrat XXVIII and current Bundesrat | parlament.gv.at Filter API list 250, two requests | 2,838 functions |

In the profiles (`src/member_profiles.py`, additive): a "Committees and
groups" section and a "Declared interests" table per member; a group or
interest whose NAME matches `config/member-intel-groups.yaml` is flagged
"on our ground" (Brazil's Frente Parlamentar Evangélica, em Defesa da Vida e
da Família, contra o Aborto, Católica, Cristã, the LGBTI+ front; France's
Chrétiens d'Orient, Saint-Siège and LGBTQI study groups; the health, family
and justice committees elsewhere; Swiss pro-life and church interests), a
flagged membership earns a profile, and each index lists "Groups on our
ground" with their members. Membership is never read as a stance. Brazil's
profiles show the Câmara's orientação de bancada beside each position and
count followed, differed and free votes: the only whip line any of these
parliaments publishes. Samples: `docs/samples/member-intel/`.

Not built, and why: France's HATVP déclarations d'intérêts (open, Licence
Ouverte, but an 80 MB XML with spouses' activities in it: a later round that
keeps the member's own items only); Austria's interests (HTML per member;
meineabgeordneten.at needs a licence, AT5); Spain (Cortes dissolved,
declarations are scanned PDFs); Argentina (Senate open data lists
committees without members, Diputados unreachable); Chile (the Cámara's
committee service still lists 2022-26 members); Italy's Senate (SPARQL 403
from the laptop); Poland's parliamentary teams (zespoły, not in the API);
attendance (no source publishes it per member beyond the vote records
already held). Not probed: BE, PT, HR, SK, HU and the rest of Latin America.

### 4. Week ahead
The framework already renders a week-ahead section when a store holds
agenda data. Add agenda collection where the source has it: NL (OData
Activiteit), PL (Sejm proceedings), CH (sessions), BR (Câmara pauta), IT, FR,
AT (Sitzungen), ES (from 23 December).

**Built 10 October 2026 (branch `parity-week-ahead`).** One table and one
collector for all of them (`src/agenda.py`, `country_agenda`;
`tools/country_agenda.py <cc>`), a source module per country
(`src/agendas/<cc>.py`), run as a step of each country's weekly job after
its collector. Points are matched to the store's bills by number only
(Kamerstuk/zaak, druk/process, Geschäftsnummer, proposição, Atto Camera,
dossier ref, d.B./A(E), expediente); watched and tier-1 points are flagged,
and the edition's Coverage line says how far each agenda reaches and when
the next sitting is. Measured on the live sources that day: NL 661 points
(12 on our ground), PL sitting 67's 41 points (the abortion bill, druk 223,
watched), BR 47, IT 48 (the Camera's October calendar), FR 216, AT 31, CH
none (between sessions), ES 17 (dissolved: the Diputación Permanente),
AR the Senate's committee meetings (cultural events left out).
Not done: the Italian Senate (refuses us), the Spanish plenary's order of
the day (a PDF), committee convocations in IT and CH, the Argentine
Diputados agenda (www.hcdn.gob.ar, AR4: left to a later decision), Belgium
(no open agenda source probed), Portugal, Slovakia, Hungary, Mexico and
the Latam monitor's countries (monthly, no week-ahead section; their
agendas are HTML per day or PDF: Colombia, Peru, the Dominican Republic;
Panama's orden del día is already collected in pa_agenda but not shown).

### 5. Debates, speeches, questions
Per country where the source is open: NL Handelingen, PL transcripts (the
endpoint timed out on 9 October), AT Stenographische Protokolle, CH, FR, IT
Senate, BR. Written questions where cheap (BR, PL interpellations, FR).


**Done, 10 October 2026 (branch `parity-debates`).** One shared module,
`src/chamber_store.py` (tables `<cc>_speeches`, `<cc>_questions`,
`<cc>_record_reads`; per-speech classification; the run loop; the edition
items), and one collector per country, `tools/<cc>_chamber.py`, run as a
step of each country's weekly through `tools/chamber_step.sh` (time-boxed to
what is left of the hour, at most ten minutes, never fatal, skipped on
GitHub). The edition gains "Said in the chamber" (one entry per debate,
speakers with a short excerpt each) and fills "Questions"; a Coverage line
says how many reports and speeches were read. Guard against long transcripts:
a speech is matched passage by passage in its own words (tier 1 in the
passage, or tier 2 when the debate's title is tier 1); a sitting is never
matched whole; the chair is never stored. Built: Netherlands (Handelingen,
Kamervragen), Switzerland (Bulletin, per-language lists), Austria (speeches
from the provisional protocol), France (comptes rendus, QE and QAG), Belgium
(Integraal Verslag), Poland (interpellations, written questions), Portugal
(perguntas and requerimentos), Brazil (requerimentos de informação). Not
built, with the reason in each scope doc's phase list: Polish transcripts,
Brazilian speeches, Italy (the Senate's SPARQL refuses us, 403), Spain
(dissolved until 23 December), Croatia and Slovakia debates, Belgian written
questions. The first Mini run of each step reads from 1 September 2026.

### 6. Later phases already approved (in each scope doc's phase list)
Set A BUILT 10 October 2026 (branch `parity-phases-a`; each scope doc's
"as built" section): French Senate (FR5), Eerste Kamer via web pages (NL4),
Slovak bill documents (SK6), Swiss Italian texts (CH6), Italy's official
Camera service (IT2). Set B below covers UY5, BO4, X8 and X7. Still to
build: regions and Landtage after national (IT3, AT6, PE4).

**Set B, built 10 October 2026 (branch `parity-phases-b`):** X8
constitutional courts for Colombia (the exhortations file; the Court's
press releases are behind a keyed API and are not read), Ecuador (the
Court's WordPress API), Peru (the Tribunal's press notes, at its 30 s
Crawl-delay) and Portugal (acórdãos, 30 s apart, ten a week), into
`<cc>_rulings` (`src/courts.py`) and the Latam edition and the Portuguese
edition; Guatemala's court is a recorded gap (GT5). UY5 Diario vote totals
(`tools/uy_diario.py`), BO4 written questions (`tools/bo_questions.py`),
X7 OCR designed and guarded (`src/ocr.py`, `tools/pe_ocr.py`; install steps in
`docs/mac-mini.md`, nothing installed). One hand-run backfill after merge:
`jobs/latam-courts-backfill.sh`. Samples: `editions/latam-monitor-2026-06-30.md`,
`editions/latam-monitor-2025-08-31.md`, `editions/pt-monitor-2023-02-05.md`.

### 7. Campaign tools
Debate packs, campaign briefs (`docs/brief-builder`), campaign targets: only
once 5CA exists for a country, and only where CitizenGO runs campaigns there.

**Campaign targets and outcomes built 10 October 2026 (branch `camp-targets`;
docs/5ca-notes.md, "Campaign targets and outcomes for the new countries").**
`tools/country_campaign.py` (src/country_campaign.py) is `ca_campaign.py` for
every country in `src/country5ca.COUNTRIES`: open a campaign on an area in a
chamber (a snapshot of the confirmed-only 5CA), suggest targets (`+`, `-`,
mixed confirmed records), add targets by name (`--by`), find and record the
outcome vote with our side, score it. Before sign-off it suggests nobody and
lists candidates by vote record, each "not a target until the stance is
confirmed". Petition performance joins from `data/looker/<cc>_campaigns.tsv`
(the UK export's shape); no country has one yet, and the command says so.
Manual only, no job. Still open: Chris to pull the first country export from
Looker (the list prefix per country is a guess: `PL`, `IT`, ...).

**Debate packs built 10 October 2026 (branch `camp-debate-packs`).**
`tools/country_debate_pack.py --country cc --date D --find WORDS | --item KEY`
(src/country_debatepack.py) assembles one upcoming or recent debate on our
ground for the 15 own-edition and 11 collected Latam countries: the item and
bill, the agenda slot, the votes on the bill and topic, likely speakers
(`--speakers`), members to watch, every member's record and profile link, and
the campaigner checklist, in the country's language (src/debatepack_i18n.py).
Manual, no job. Placements only from confirmed readings: until a signer
confirms, every pack renders "awaiting sign-off". Usage in each scope doc and
docs/debate-pack-social.md, "New countries".

**Debate today and the live read built 10 October 2026 (branch
`camp-live-debate`).** `tools/country_debate_today.py` and
`tools/country_live_debate.py` (src/country_live.py), the UK pair generalised,
for the countries whose chamber source publishes the day's speeches the same
day, measured on the live sources: the Netherlands (Handelingen, 2.5 to 3
hours behind, re-issued all day), Switzerland (the Bulletin, during the
sitting by the Parliament's account; to confirm in the Wintersession),
France (each sitting's compte rendu the same night) and Belgium (the
Thursday record the same evening). Not Austria (speech files the next day or
later), nor Poland, Brazil, Portugal (questions only) or any country without
a speech collector. The day is read by each country's own collector into an
in-memory store; the real store is only read. The live read sets each
speaker's words beside their votes on the area and names a contradiction
only when the vote's reading is CONFIRMED and the words have been read by a
person or the session judge (`--queue-out` / `--reads`); until then
"awaiting sign-off". Debate today is STEP 1B of the existing 16:45 net task
(`ops/scheduled-tasks/debate-day-net.md`): the task lives on Chris's work
account; update it from the file.
Table and usage: docs/debate-pack-social.md, "New countries".

**Campaign briefs built 10 October 2026 (branch `camp-briefs`).**
`tools/country_briefs.py` (`src/country_briefs.py`, phrases in
`src/brief_phrases.py`, lists and languages in `config/country-briefs.yaml`)
drafts an RF4 brief per watched or tier-1 bill that moved in the last 90 days,
in every new country with a collector (the fourteen own editions and eleven
Latam countries), as a step of its weekly job. Facts from the store only, no
AI call; every cell the record cannot fill is a `[CAMPAIGNER: ...]` line. The
ask, the 5CA, the targets and the segment split come from CONFIRMED stances
only, so every brief is NOT READY until its bill's direction
(`--confirm-direction`, new in `tools/country_5ca.py`) and every reading of
its votes are confirmed. Unedited briefs refresh weekly; edited ones are left
alone. Language: English, per rulebook rule 6 (Chris, 10 October 2026; #75).
Open: the framing glossary, the allies and opponents registers and Bluebook
access.

### 8. Vote meanings (what a Yes and a No meant)

**Built 11 October 2026 (branch `ukp-meanings`).** `src/vote_meanings.py`
and `tools/vote_meanings.py` give each watched and tier-1 vote in the 21
countries of `src/country5ca.COUNTRIES` one plain-English line for each
lobby, stored per division in the store's `vote_meanings` table with its
source. Rules first (the kind of vote from its wording, named forms such as
Poland's re-passage over a veto, Spain's toma en consideración, the Latin
American "en lo general", Switzerland's own Bedeutung lines through a fixed
table, and the bill's English description from the watchlist or
`bill_directions`); then the free session judge, in the Sunday
editions-session-judge job AFTER the editions' scores and only with what is
left of the week's ~100 items, for votes the rules cannot read and lines
that can only quote a source title. A person overrides any line in
`config/vote-meanings-<cc>.yaml` (file-based, like the UK). A meaning says
what a lobby voted for, never whose side it was on: the stance stays a
signed reading. Not covered: Colombia, Bolivia, Panama, Honduras, Uruguay,
Venezuela and Nicaragua (no recorded votes per division to attach a line
to; Uruguay's Diario totals are not divisions of a bill).

### 8. Public vote pages, vote tracker and bill timelines (UK feature parity)

**Built 11 October 2026 (branch `ukp-vote-pages`).** `src/country_votes.py` and
`tools/make_country_votes.py`, one generator for every new country with
member-level or party-group votes (IT, CH, FR, NL, BE, AT, PT, PL, SK, HR,
ES, HU, BR, AR, MX, CL, PE, EC, DO, SV, GT, CO), generalising
`make_au_votes.py`, `make_us_votes.py`, `make_ie_votes.py` and the UK
tracker. Three outputs in `partner_site/`, behind the partner passphrase like
every UK vote page: `<cc>-votes.html` (the votes on our ground as the edition
classifies them, latest 300, with the store's tally and result, the split by
party or group, who voted against their group's majority and every member's
position verbatim, plus a member search; template
`templates/country-votes.html`), `votes-countries.html` (one row per country
and the latest votes across all of them) and `bill-timelines.html` (each
watched bill the store holds: introduced, the stages the store keeps, Spain's
whole procedural history, every `country_agenda` slot, every recorded vote,
its end). Members, parties and party bases come from
`src/member_profiles.py` (X5 DERIVED and X6 as-listed labelled on every
line); tallies and readings from `src/country5ca.py`. "Against their group"
counts recorded positions whose party is the party at the vote only: never
the non-attached (#80), never derived or as-listed parties. A division whose
reading is not CONFIRMED ships with no direction at all ("awaiting
sign-off"); no page places anyone in a 5CA column. The partner nav links the
tracker and the timelines (src/partner.py `VOTE_PAGES`) once they exist.
Weekly: a step of `jobs/editions-session-judge.sh` after the judge (and on a
judge gap), committed with `partner_site`, shipped by Monday's deploy.
Watchlist `why:` lines are never shown (they hold internal reasoning).

## Blocked, waiting on replies (letters drafted in Chris's Gmail)

| Country | Blocker | Route |
|---|---|---|
| Hungary bills and votes | parlament.hu CAPTCHA | W-API token (email drafted to api-reg2@parlament.hu); karzat covers 9 May to 28 Aug |
| Spain Senate | 403 everywhere | email to Senado open data (address to find) |
| Costa Rica | refuses all foreign connections | email to the Asamblea |
| Paraguay | SILpy robots.txt disallows | email to the Senate (addresses from 2016) |
| El Salvador missing votes | unpublished sessions 41-64, 98 | information request (address to find) |
| Guatemala court | bot challenge | email (address to find) |
| Uruguay main site | 403 from laptop, GitHub and the Mini (10 Oct) | write to the open-data team |
| Argentina Diputados votes | no connection from anywhere (Mini 10 Oct) | write to HCDN or ask an Argentine contact |
| meineabgeordneten.at | licence | email drafted |

## Rules to keep (learned the hard way)

- Never solve or bypass CAPTCHAs or bot checks; respect robots.txt; never use
  credentials found in a site's code (Ecuador portal, DR Senate, Peru's
  encrypted endpoint: PE2 left out).
- Never hand-edit generated taxonomy YAML; edit `docs/keyword-taxonomy-*.md`
  and regenerate. `taxonomy-qc` stays unchanged for Belgium and Switzerland.
- AI judge: the paid API judge stays off (X16); the free session judge runs
  on the Mini under the work account's plan, capped at about 100 items a week.
- Never dispatch store-writing GitHub workflows from the laptop (they lose the
  publish race to Mini jobs). One store-writing Mini job at a time.
- Guatemala and Mexico run on GitHub, fortnightly (alternate ISO weeks), as
  their sites refuse UK connections (the Mini included).
- Member-level claims: non-attached members are never counted as breaking
  from a group (#80); party at the vote needs history (X6) or a label.
- New Mini jobs: add them to `ops/install_country_jobs.sh` and rerun it on the
  Mini (`cd ~/runner/parl-monitor && git pull --ff-only && bash ops/install_country_jobs.sh`).
- Ownership: the 30 new countries and Latam were this session's; US, IE, AU,
  Canada, devolved, EU, DE and UN belong to the Ireland/Australia session.

## Reaching the Mini

The Mini's Claude sessions run on the work account, so a personal-account
session cannot message them. From the laptop the Mini is reachable by SSH
with the `parl_mini` key (Chris approved, 10 October):
`ssh -i ~/.ssh/parl_mini -o IdentitiesOnly=yes christopherjoyce@christophers-mac-mini.local`.

- **Do not start `mini_run.sh` over plain SSH:** `gh` reads its login from
  the keychain, which SSH cannot open, so the job fails at "mark running"
  (HTTP 401). Run hand jobs as a one-shot launchd job instead: write a plist
  to /tmp with `RunAtLoad` true and `KeepAlive` false, `launchctl bootstrap
  gui/$(id -u) <plist>`, then `launchctl bootout` it when done.
- Over SSH, `claude` and `gh` live in `~/.local/bin`.
- Installing a new plist: `ops/install_country_jobs.sh` (idempotent), or copy
  one plist from `git show origin/main:ops/launchd/<label>.plist` and
  bootstrap it, without pulling the runner clone while jobs are running.
- A work-account session on the Mini can run Mini steps directly.
