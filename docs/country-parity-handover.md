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
items (#91), speech clips (#92). UK-parity round 2, 11 October: a
'sign these first' 5CA shortlist per country, leading the weekly digest
(#102); words since the last vote for NL, CH, AT, FR, BE (#103); the Swiss
"IVG" false friend fixed and Switzerland reclassified on the Mini (#104,
14 votes lost a wrong abortion tag); the debate report with approval and a
canvas for Chris alone (#105); attendance: BR and FR committees, CL plenary
roll, NL committee debates, CO, and vote participation where absences are
recorded (#106); members' length of service, with derived positions now only for days a member sat (#107). Round 3: 5CA posting and Slack canvases
(#111): `tools/country_5ca_post.py --cc CC --area N --to canvas|dm|both`
(or `--all-countries`; `--dry-run` shows what would go), from confirmed
readings only, to Chris alone (a canvas shared with his ID, never a channel);
reruns rewrite the same canvas, and a Sunday step refreshes canvases whose
confirmed readings changed. Silent until the first reading is confirmed.
Also the publish-collision fix (#109). Portugal's plenary attendance (#113:
every XVII sitting's roll, absence reasons verbatim) and France's HATVP
declared interests (#114: members' own items only; spouses' and other
third parties' sections are dropped at parse time and never stored). Coverage-gap round, 11
October: week ahead for Belgium, Portugal, Slovakia, Polish committees and
the Spanish plenary PDF (#116); daily sweep for 13 more countries and
France's new dossiers, about 2 minutes a day in all (#117); speeches for
Croatia, Slovakia, Poland (transcripts now answer) and Brazil within a
small budget (#118).

**Nothing is published from a 5CA yet.** Every stance is a draft: 975
readings await sign-off across the countries (France limited to final votes
and watched amendments). Briefs, packs, targets, the partner sheet and the
live read all render "awaiting sign-off" until a reading is confirmed. From
the Sunday run after 11 October 2026 the drafts that pass every automatic
check are confirmed on Chris's delegation (a dry run on 11 October: 71 of
1,001), the rest wait for a person, and country signers amend
(docs/country-decisions-2026-10-11.md, docs/5ca-notes.md).

**Waiting on Chris (decisions and actions):**

1. DONE (11 October 2026): Chris signs for every country, "for now"
   (`config/stance_signers.yaml`); team members are added as they take over.
2. DONE (11 October 2026): the flagged bill directions are decided and
   confirmed (religious-symbol bans, IVF, the euthanasia referendum, minors
   online, puberty blockers, conversion-practices ban, sex-work licensing,
   GT and HU against us; France's palliative care bill on hold until read).
3. DONE (11 October 2026, #121): checked against Loi n° 2026-794 du 18 août 2026
   (JORF 19 August). None of its implementing texts is published yet; the
   watchlist now lists nine (the HAS list and pharmacy rules are not decrees;
   conscience register, prices arrêté due about 18 November, register-check
   start and overseas ordonnance added).
4. HANDED OVER (11 October 2026): the Looker list prefixes per country
   (`docs/campaign-benchmarks.md`) go to the work-account Claude, which has
   Looker access.
5. DONE: sent on 9 October from cjoyce@citizengo.net (Hungary W-API, Spain
   Senado, meineabgeordneten.at, Paraguay, Open States, Australia aph.gov.au)
   and on 12 October (Guatemala's court via comunicacion@cc.gob.gt, asking it
   to forward to the information unit; El Salvador's missing votes, a LAIP
   request to transparencia@asamblea.gob.sv). Costa Rica PARKED: the address
   bounced and no external one is published. Watch for replies.
6. Update the work account's **debate-day-net** scheduled task from
   `ops/scheduled-tasks/debate-day-net.md` (adds STEP 1B, debate today for
   NL, CH, FR, BE). It lives on the work account, not the personal one.
7. DONE (11 October 2026): the Dutch edition shows the week ahead, now in
   its votes-only DM too (`dm_ahead` in `src/editions/nl.py`).
8. DONE (11 October 2026): the rainbow-flag motion (dossier 21501-02, zaak
   2026Z21728) stays watched.
9. DONE (11 October 2026): `config/member-intel-groups.yaml` approved as
   drafted.
10. DONE (11 October 2026, #121): all four checked against the law. Portugal
    gained the >2,500 committee-debate tier (art. 24-A); Belgium's 25,000 and
    regional split cite the Law of 2 May 2019 art. 4.
11. DECIDED (12 October 2026): no outreach to the country teams; the
    openings stay in the editions' Petitions section.
12. ASKED (12 October 2026): prior-agreement requests sent to
    communication@assemblee-nationale.fr and pri@dekamer.be (short credited
    clips on CitizenGO's channels). When either agrees, set `fr.agreement` /
    `be.agreement` in `config/clip-sources.yaml`.
13. DONE (11 October 2026, #95): the Mini's run slot is first in, first out
    (a ticket queue in `tools/mini_run.sh`). Keep hand backfills out of the
    overnight weekly window.
15. DONE (11 October 2026): sign-off is now automatic with team amendments
    (`--auto-confirm` weekly; a signer amends with `--amend`). What fails a
    check is listed, with the check, in each shortlist and guide for a
    person to sign.
16. DECIDED (11 October 2026): debate reports keep English summaries with
    verbatim source-language quotes. Translations still come from a person
    in `translations.yaml` or the free judge run by hand on the Mini
    (command in `docs/mac-mini.md`); "publish" means a canvas for Chris alone.
14. DONE (12 October 2026): 400 items scored once on Chris's personal Claude
    account (jobs/judge-queue-out.sh / judge-queue-in.sh, #120): 27 edition
    scores and 373 vote meanings, none refused; 13 editions rewritten. About
    111 meanings remain for the Sunday judge (cap unchanged at 100).
17. DONE (12 October 2026, `docs/country-decisions-2026-10-12.md`): the 126
    bills with no direction are decided (91 directions, 29 with no CitizenGO
    stake taken out of play, 6 left for a person); religious-symbol bans are
    all with us, veils included (Belgium reversed, Quebec's laicity readings
    flipped); `--fill-directions` drafts the votes that waited on them, and
    migration-only readings no longer count as needing a person.
18. OPEN: HazteOir to confirm Spain's SUMAR free-expression reform
    (15/122/000006). Drafted `with`, flagged, so nothing confirms on it
    until the flag is cleared.
19. DONE (12 October 2026, `docs/country-decisions-2026-10-12.md`, "The seven
    read for a person"): FR palliative law and entryism bill with us, NL
    Embryowet and motie Podt against, NL 2026Z08649, PL 10/529 and HR 11/228
    not scored. (Quebec's Bill 9 decided 12 October 2026: against us; the
    other Quebec laicity flips kept.)

20. DONE (12 October 2026): every amendment read (Chris: "Score every
    amendment"; France's limit lifted, #127). 1,555 applied: 818 with, 272
    against, 256 not scored, 209 unclear; 313 flagged for a person. About
    936 readings confirm on Sunday's automatic sign-off. Unclear ones are
    mostly the Italian Senate and Hungary (bot checks), the Dominican
    Chamber (no readable text) and some French Sénat votes.

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
- First runs: the Netherlands, Chile and Colombia ran on the Mini on 11
  October 2026 (kickstarted; all published, editions sent; the Dutch run
  needed a rerun, see below). Still to come: Mexico and Guatemala (GitHub,
  fortnightly) and El Salvador (failed 11 October, fixed in #85; next run
  Sunday 18 October). The Dominican Republic's 11 October Mini run timed out
  before the #85 budget fix; check its next run. To run a weekly sooner,
  kickstart its installed job on the Mini
  (`launchctl kickstart gui/$(id -u)/net.citizengo.parlmonitor.<cc>-weekly`),
  outside the overnight window.
- Compressed publish: VERIFIED 11 October 2026. The store (1.77 GB) uploads
  as `parl-monitor.db.gz`, 431 MB, compressed in 16 s; the raw asset is gone
  from the release. Since 12 October 2026 the size warnings are on the
  compressed asset (0.75 GB: plan the split; 1.0 GiB: split now), so they no
  longer fire; docs/store-split-plan.md.
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
about 15 minutes to 4 or 5. Pushes warn when the compressed asset passes
0.75 GB ("plan the split") and 1.0 GiB ("split now"), and refuse above 2 GiB
(12 October 2026, docs/store-split-plan.md). If it keeps growing, the next step is splitting the new
countries into their own store file (Chris: "further changes in the future
if necessary"). On 11 October it was 1.82 GB uncompressed, 446 MB compressed.

**Publish collisions fixed (#109).** Three runs lost their store with "gh
upload failed: HTTP 404 ... ANOTHER PUBLISH LANDED" (prov-backfill 9 October,
Portugal 10 October, the Netherlands 11 October). The cause: a GitHub run's
`db_state --pull` found only the keep-aside `.prev` / `.gz.prev` mid-upload and
renamed it back. Pull now leaves a keep-aside younger than 30 minutes
read-only; push retries a failed upload three times when no other publish is
seen, and still refuses a genuine race. Unverified: the 30-minute age comes
from GitHub's `updated_at` on the asset; if a rename does not update it, the
guard can miss an old keep-aside. Watch the logs for "upload failed, no other
publish seen".

**What could come next (not started):**
- Still blocked by the source: Hungary's bills and votes (CAPTCHA; API token
  requested), Italy's Senate (refuses us), Mexico's Senate (robots.txt) and
  its same-day agendas (UK connections refused), Swiss committees
  (confidential), the Dutch and Polish consultation portals (robots.txt),
  committee attendance in PL, CH, AT and IT (not published), Austrian
  interests (licence), Colombia's and El Salvador's daily sweep (no cheap
  dated source), clips for France and Belgium (agreement needed).
- Waiting for time: Spain's agendas, speeches and sweep fill from 23
  December when the XVI sits.
- Regions built 12 October 2026 (Spain, Peru, Mexico, Austria, Italy; sections
  below). Not yet built: Africa (Kenya, Nigeria, Uganda: Chris's aim is Q1
  2027); a native read of each language's term list.

## What exists now

| Layer | UK | DE | US / IE / AU | CA | New countries |
|---|---|---|---|---|---|
| Collector (bills, votes, members) | yes | yes | yes | yes | yes, 25 countries (see below) |
| Weekly edition, Slack DM to Chris | yes | yes | yes | yes | 14 own editions + Hungary gazette edition + one monthly Latam edition |
| Weekly review window (edit or cut before the DM, Asana reading task) | yes (Sunday pull review file, Monday publish; the UK editorial loop and its Asana task were retired 21 Aug) | no | no | no | **built** 11 Oct (`src/edition_review.py`, `tools/edition_review.py`, `config/edition-review.yaml`, branch `ukp-review-window`): all 15 own editions and the Latam monthly write `reviews/<cc>-review-<date>.md` (keep / cut / edit, note, hold / now, merge-preserving) and DM at 06:30 London the next morning via the Mini job `edition-publish` (06:31, 21:10); one combined Asana reading task a week; vote briefs and Latam alerts stay immediate |
| Triage | API judge | API judge | API or session judge | session judge (provinces) | free session judge, Sundays 16:45 (`tools/edition_judge.py`) |
| Noise filters, mute lists | yes | partly | yes | yes | yes (`src/noise.py`, `config/edition-noise-<cc>.yaml`) |
| Same-day vote briefs (division watch) | yes | no | yes (`*_division_brief.py`, `src/vote_brief.py`) | no | yes, 20 countries (`src/country_vote_brief.py`): daily for NL, PL, CH, BR, IT; after the weekly for the rest |
| Daily sweep of new items (bills, motions, questions, agenda) | yes (`tools/day_sweep.py`) | no | EU (`tools/eu_day_sweep.py`) | no | **built** 11 Oct (`src/country_day_sweep.py`, readers `src/day_sweep_sources.py`, branch `ukp-day-sweep`): a step of the one daily job (`jobs/vote-briefs-daily.sh`) for NL, PL, CH, BR, IT, AT, FR (agenda only, once a day) and ES (from 23 Dec); tier 1 and watched, the vote briefs' gate; one combined DM with the vote briefs; de-duplicated against the editions, the vote briefs and `data/day-sweep/<cc>.json`; samples `docs/day-sweep-samples/`. **Extended** 11 Oct (branch `gaps-day-sweep`): BE, PT, HR, SK, AR, France's new dossiers, and CL, PE, EC, BO, DO, PA, HN, UY through the Latam alerts' rule and ledger (no double send); MX, CO, SV measured and left out; the daily run about 2 min (55 s before) |
| 5CA (member stance, five columns) | yes | yes | yes | yes | **built** 10 Oct (`tools/country_5ca.py`, branch `parity-5ca`): sheets from confirmed readings only, none confirmed yet; AT/PT/NL rows derived (X5). Tracker and partner sheet built 10 Oct (`tools/make_country_5ca_web.py`, branch `camp-5ca-sheets`): `docs/5ca-countries.html` weekly, "awaiting sign-off: N readings" per country; partner page gated until a country has a confirmed placement. Posting to Chris built 11 Oct (`tools/country_5ca_post.py`, src/country5ca_post.py, branch `ukp3-5ca-post`; the UK `post_5ca.py` and `republish_canvas.py`): per country and area, from confirmed readings only, a canvas shared with Chris alone and/or a DM, never a channel; rewritten in place on a rerun; refreshed in the Sunday judge job only when confirmed readings change; X5 rows labelled DERIVED, non-attached never placed from a group vote (#80); nothing sent while none is confirmed |
| Stance sign-off per vote (`config/*_stance.yaml`) | yes | yes | yes | yes | **built** 10 Oct (#65): 975 readings awaiting sign-off after France was limited to final votes and watched amendments (#77), weekly digest DM; signers per country to name (`config/stance_signers.yaml`) |
| Picking past votes for 5CA (which to sign first) | yes (`find_division_candidates.py`, `review_divisions.py`, `research_shortlist.py`: a review queue, a person adds each vote by hand) | no | no | no | **built** 11 Oct (`src/shortlist5ca.py`, `tools/country_5ca.py --shortlist`, branch `ukp2-5ca-candidates`): every waiting reading ranked by rules (decisive votes on watched bills, close margins, split groups, a meaning line ready, campaigns and briefs, recent first; procedural, near-unanimous and amendment votes sink; collated-only areas last); `docs/5ca-<cc>-shortlist.md` per country (top 20 with why, meaning line, proposed values and the exact `--confirm` command, then the best per area), rewritten in the Sunday judge job; the stance digest DM now leads with each country's top 5. Confirms nothing |
| Campaign targets and outcomes (`ca_campaign.py`, the 5CA Evaluate) | yes | no | no | no | **built** 10 Oct (`tools/country_campaign.py`, branch `camp-targets`): open, targets, add, find, outcome, score; targets from confirmed readings only, candidates by vote record until then; petition numbers none yet (UK only) |
| Member profiles | yes | yes | US yes | no | yes, 23 countries (`profiles/<cc>/`, weekly step; X5 derived and X6 as-listed labelled; HR and CL party history sourced), branch `parity-profiles` |
| Public vote pages, vote tracker, bill timelines | yes (`mp-votes.html`, devolved, timelines) | yes (`de-votes.html`) | yes (`us-`, `ie-`, `au-votes.html`) | no | **built** 11 Oct (`tools/make_country_votes.py`, src/country_votes.py, branch `ukp-vote-pages`): `partner_site/<cc>-votes.html` for the 22 countries with member or party-group votes, `votes-countries.html` (tracker) and `bill-timelines.html` (watched bills: stages, agenda slots, votes), behind the partner passphrase, weekly in `editions-session-judge`; records only, no for/against before a reading is CONFIRMED; X5 derived and X6 as-listed labelled, non-attached never counted (#80) |
| Member portraits and party logos | yes (Members API thumbnail on `mp-votes.html`, CC BY 3.0, credit line still to add); logo slot empty by choice | no | no | review cards only | **built** 12 Oct (`src/portraits.py`, `tools/fetch_portraits.py`, `docs/portraits-logos-licences.md`, branch `portraits-logos`): licences checked for every monitored legislature (9 OK with attribution, 12 internal-only, 8 not allowed, 21 unclear); portraits on the vote pages' member cards for **BR and HR** only (cached 96 px thumbnails under `partner_site/portraits/<cc>/`, credit line, never hotlinked), a step in `editions-session-judge`; **no party logos** (trademarks): Wikidata colour chips (`config/party-colours.yaml`) |
| Member intelligence (interests, cross-party groups, committees, whip lines) | yes (`pull_interests.py`, `load_appgs.py`, `pull_pbc_attendance.py`, `annotate_whips.py`) | part | no | no | **built** 11 Oct (`tools/member_intel.py`, `src/member_intel.py`, branch `ukp-member-intel`), a step of 7 weeklies before the profiles: BR fronts (frentes parlamentares) and organs, NL committee seats and nevenfuncties, CH committees and Interessenbindungen, PL committees, FR committees, délégations and groupes d'études, IT Camera organs, AT committee functions. Groups on our ground flagged by name (`config/member-intel-groups.yaml`) in each profile and a "Groups on our ground" list in each index. Whip: Brazil's orientação de bancada beside each Câmara position (the only published whip). FR HATVP declared interests **built** 11 Oct (branch `fr-hatvp`, `tools/fr_hatvp.py`, monthly, members' own items only). Not built: AT interests, ES (dissolved), AR, CL (stale service), IT Senate (403) |
| Committee and plenary attendance | yes (`pull_pbc_attendance.py`, bill committees) | no | no | no | **built** 11 Oct (`src/attendance.py`, `tools/country_attendance.py`, branch `ukp2-attendance`), a step of 5 weeklies before the profiles: BR committee and plenary presence register, FR commission présences, CL plenary and committee rolls, NL committee-debate participants ("took part", not a roll), CO plenary (co_attendance), PT plenary roll (added 11 Oct, branch `pt-attendance`: an HTML roll per sitting, not a PDF; 119 XVII sittings, 27,370 marks, every deputy matched to `pt_members` and the member service; motive of each justified absence verbatim; also beside speakers in PT packs); committee-to-bill referrals for BR, FR, NL; plenary vote participation DERIVED from the votes for IT, CH, PL, ES, AR, PE, DO, HU. Shown in profiles and debate packs. Not built: PL, CH, AT, IT committees (none published), PT committees, ES, PE, PA (PDFs) |

| Length of service (every period each member sat; `tools/pull_service.py`) | yes | no | no | no | **built** 11 Oct (`src/member_service.py`, `tools/member_service.py`, branch `ukp2-service`), a step of 18 weeklies before the profiles (weekly or every four weeks by source): shared tables `ms_periods`, `ms_party`, `ms_runs`. Seat dates for CH (since 1848), NL, FR (from 2002), AT, PT (since 1976), IT Camera (since 1948), ES (since 1977), PL (from 1997), BR (sitting members), CL (militancias), HU (current term); terms only for SK, HR, BE, AR, PE, DO, MX; nothing for EC, SV, GT, CO, UY. Profiles and vote pages say "serving since" and earlier periods with what the source covers, never more; DERIVED positions (AT, PT, NL) only for days the member sat, by their group on the day (also in the 5CA and campaign positions) |
| Debates / speeches | yes | yes | IE, AU | yes | NL, CH, AT, FR, BE (10 Oct, `tools/<cc>_chamber.py`); **HR, SK, PL, BR (11 Oct, branch `gaps-speeches`)**: Sabor transcripts (chair told by the record's shape), NR SR debate record, Sejm per-statement transcripts (answered on the retry), Câmara speeches pre-filtered on its own summaries; in the editions, profiles' since-vote and the debate report, no live read (none same-day); samples `docs/speech-samples/`; not IT (Senate 403), ES (dissolved), PT (questions only) |
| Parliamentary questions | yes | no | IE | no | NL, PL, FR, PT, BR requests (10 Oct, `tools/<cc>_chamber.py`); already in the editions: SK interpellations, AT J/AB, CH Vorstösse, HU, UY pedidos, HN press, BO written questions: BO4, built 10 Oct, `parity-phases-b` |
| Committees, courts, petitions, consultations | yes | yes | US courts | yes | constitutional courts (X8) built for CO, EC, PE, PT (10 Oct, `parity-phases-b`); GT gap; no committees. **Petitions and consultations built** 11 Oct (`src/petitions.py`, `tools/country_petitions.py`, branch `ukp-petitions-consult`), a step of 11 weeklies and an edition section: FR (AN and Sénat e-petitions), AT (Ministerialentwürfe in Begutachtung, Petitionen, Bürgerinitiativen, Volksbegehren), CH (Vernehmlassungen, Petitionen, Volksinitiativen in collection), IT (firmereferendum initiatives and referendums, ParteciPa), PT (petições), PL (Sejm consultations, citizens' bills), BE (Chamber petitions), NL (petitions handed to the Kamer), BR (e-Cidadania ideas and public vote, Brasil Participativo), AR (consultapublica), CO (SUCOP, in the Latam edition); not NL internetconsultatie or PL legislacja (robots.txt), ES (no central list), CL (403), MX |
| Week ahead / agenda | yes | yes | yes | no | yes for NL, PL, CH, BR, IT (Camera), FR, AT, ES (fills from 23 Dec), AR (Senate), HR; **11 Oct (branch `gaps-week-ahead`)**: BE (Chamber eMeeting XML, plenary and committees), PT (Agenda Parlamentar, plenary and committees), SK (programme of a convened sitting), PL committee sittings, ES plenary order of the day read from its PDF; committees were already in for NL, FR, AT, BR; samples `docs/week-ahead-samples/`. Not HU (CAPTCHA), MX (hosts refuse UK; orden del día only on the day), CH committees (confidential), Latam (item 4) |
| Debate packs, campaign briefs, campaign targets | yes | yes | no | yes | debate packs **built** 10 Oct (`tools/country_debate_pack.py`, manual, 26 countries; placements from confirmed readings only, none yet); campaign briefs **built** 10 Oct (`tools/country_briefs.py`, a weekly step): drafts in English per rulebook rule 6 (#75), NOT READY until stances are confirmed; targets **built** (#69) |
| Speech clips for social (`social_cut`, `speech_cut`, `pick_speeches`) | yes | no | no | no | **built** 11 Oct (`tools/country_clips.py`, branch `ukp-speech-clips`, manual, nothing posted): CH and AT open (each speech's own official MP4); NL manual (Debat Direct's archive answers us with a placeholder: a person downloads the speech, `--video`); FR and BE located to the second but the cut refuses until the parliament's written agreement is recorded (`config/clip-sources.yaml`); BR, PL, IT, ES not built (no speeches stored). Not yet run end to end: the Mini lacks the footage bundle |
| Debate today, live read | yes | no | no | no | **built** 10 Oct (`tools/country_debate_today.py`, `tools/country_live_debate.py`, branch `camp-live-debate`) for the four countries whose chamber publishes the same day: NL, CH, FR, BE; not AT (next day or later) or the question-only countries. Before sign-off the live read names no contradiction ("awaiting sign-off"); debate today is a step of the 16:45 net task |
| Debate report (report and social copy after a debate, DM for approval, canvas) | yes (`tools/debate_report.py`, one paid call) | no | no | no | **built** 11 Oct (`tools/country_debate_report.py`, `src/country_debatereport.py`, branch `ukp2-debate-report`, manual) for the five countries whose speeches we store: NL, CH, AT, FR, BE. English report from templates over the record (no paid AI): speakers on our ground with a verbatim source-language passage each, translations by a person or the free session judge (`--queue-out`/`--queue-in` via `tools/session_judge.sh`), the debated bill's votes (found by the reference in the title, `--item` or a debate pack) and the latest on the same ground with tallies, group splits and vote meanings; clip pack linked. AWAITING SIGN-OFF, no verdicts, until the readings shown are confirmed. DM to Chris alone; `--approve --by NAME` records approval against the files; `--publish` makes the canvas with the UK's code, shared with Chris alone (never a channel), rewritten in place on a re-run. Samples `docs/debate-report-samples/` |
| Words since the last vote (`since_last_vote.py`) | yes | no | no | no | **built** 11 Oct (`tools/country_since_vote.py`, `src/country_since_vote.py`, branch `ukp2-since-last-vote`, manual) for the countries with speeches and votes: NL, CH, AT, FR, BE. Per area, each member's last recorded vote on it (watched or tier 1, procedure never) and their speeches since, with excerpts. Drift is named only once the vote's reading is CONFIRMED and a person or the free session judge has read the words (`--queue-out` / `--reads`, `read_by` required, a read goes stale when new words arrive); before that "awaiting sign-off", ranked by recency and volume. Group votes (NL shows of hands, AT) never name drift. Optional profile section: `tools/member_profiles.py <cc> --since-vote` (off in the weeklies). Samples `docs/since-vote-samples/` (CH, FR, BE; the published store holds no NL votes or speeches and no AT speeches yet) |
| Health summary, Drive | health DM; briefs and debate footage on Drive | health DM | health DM | health DM | **built** 11 Oct (branch `ukp-health-drive`): the 07:30 health DM has one compact section per region (Europe, Latam) plus shared jobs, failed and stale jobs first, step gaps by step, editions behind, the countries' overdue sources (`src/country_health.py`); briefs as Sheets from the UK template and real debate packs on Drive under `Country editions/<Country>/` in the Automated Briefs shared drive, a step of the Sunday `editions-session-judge` (`tools/country_drive.py`, ledger `data/country-drive.json`, at most 30 new sheets a run) |
| Regional / state parliaments | devolved | Länder (part) | US states (in progress) | provinces | Built 12 Oct 2026: Italy four councils (IT3), Austria seven Landtage (AT6), Spain all 17 via the BOE plus four bill lists, Peru 25 regions + Lima (PE4), Mexico 13 state congresses; others later, per decisions |
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

**Extended 11 October 2026 (branch `gaps-day-sweep`).** Measured and added
to the same daily run: Belgium (the Chamber's recent-documents listing),
Portugal (the latest-initiatives page), Croatia ("Novi akti", the sweep's
own items), Slovakia (the term's prints and interpellations), Argentina
(the Diputados register on datos.hcdn.gob.ar once a day with no retry,
never www.hcdn.gob.ar per AR4, and the Senate's agenda), France's new
dossiers (the AN's own list, one page, once a day with the agenda; its
written questions stay weekly: the Journal officiel prints them on
Tuesdays), and, through the Latam alerts' reader, rule and ledger
(`data/latam-alerts/<cc>.json`, both ways, so nothing is sent twice with
`tools/latam_alerts.py`), Chile, Peru, Ecuador (votes, tallies only),
Bolivia, the Dominican Republic, Panama, Honduras and Uruguay (pedidos, once
a day, only when the file changed). Left out: Mexico (refuses UK
connections, and no dated list), Colombia (no cheap dated list; CO3 rules
out votes), El Salvador (a vote's subject is filed days late, 40 s a day).
Each sweep request is retried at most once. The whole daily run took 55 s
before and about 2 minutes after (laptop). Sample:
`docs/day-sweep-samples/day-sweep-2026-10-11-more-countries.md`.

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

France's HATVP declarations of interests and activities: **built** 11
October 2026 (branch `fr-hatvp`; `tools/fr_hatvp.py`, `src/fr_hatvp.py`, a
monthly step of `jobs/fr-weekly.sh` before the profiles). The HATVP's open
data (Licence Ouverte; robots.txt allows it): `declarations.xml` (79.5 MB)
downloaded only when it changed (If-Modified-Since, at most every four
weeks; validators in `mi_downloads`) and stream-parsed with the stdlib;
`liste.csv` supplies the parliament ids. Kept: each sitting député's and
sénateur's latest declaration, their OWN items in six sections (activities
of the last five years, consultancy, management roles, shareholdings,
voluntary roles, mandates), into `mi_interests` (source `fr-hatvp`) with the
deposit date and the HATVP page (two new columns, `declared` and `url`).
Spouses', collaborators', free-text and asset sections are cleared at parse
time and never stored, logged or archived; the XML itself is never archived
(a test proves the spouse data never reaches the store or the log). 699
sitting members matched (532 AN, 167 Sénat; 694 by the HATVP's id, 5 by name
and mandate, all hand-checked), 7,337 items; the other 223 sitting members
have no declaration in the open data yet (the HATVP lists 179 senators'
as "En cours" and 38 as lodged, publication to come; 6 with no row): they
fill in as the HATVP publishes. 36 organisations flagged on our ground by
name (OGEC Catholic school bodies, dioceses and parishes, secularist
bodies, women's rights associations, private schools). Profiles show
"From the declaration lodged with the HATVP on <date>" and the HATVP page.
Sample: `docs/samples/member-intel/fr-hatvp.md`.

Not built, and why: Austria's interests (HTML per member;
meineabgeordneten.at needs a licence, AT5); Spain (Cortes dissolved,
declarations are scanned PDFs); Argentina (Senate open data lists
committees without members, Diputados unreachable); Chile (the Cámara's
committee service still lists 2022-26 members); Italy's Senate (SPARQL 403
from the laptop); Poland's parliamentary teams (zespoły, not in the API);
attendance (built separately, 3c below). Not probed: BE, PT, HR, SK, HU and
the rest of Latin America.

### 3c. Attendance -- BUILT 11 October 2026 (branch `ukp2-attendance`)

The UK's `tools/pull_pbc_attendance.py` (who attended each bill committee
sitting) generalised: `src/attendance.py`, `tools/country_attendance.py`, a
step of the BR, FR, CL, NL and CO weeklies after member intelligence and
before the profiles. Four tables: `att_sittings` (one per sitting: body,
date, the kind of roll, the bills its own agenda names), `att_marks` (one per
member per sitting, status verbatim), `att_referrals` (which committee
handled which bill) and `att_runs`.

What each country reads (probed 11 October 2026, all open, no key):

- **BR** Câmara: the year's bulk presence register
  (`eventosPresencaDeputados`, who was present at each committee meeting and
  plenary session; deliberative plenary sessions only), with each event's
  organ and type. The register lists only who was present, so a member's
  sittings count from the day they joined the committee (member
  intelligence's `br-orgaos` start dates); a non-member's attendance is shown
  as attended only. Referrals: each bill on our ground's tramitações. 1,189
  sittings (70 plenary), 58,764 marks in 2026.
- **FR** Assemblée: the Agenda open data's commission présences ("présent",
  "absent", "excusé", per member, as at the foot of each compte rendu) and
  the dossiers on each meeting's agenda (the referrals). 3,403 meetings of
  the 17th legislature (433 of them friendship groups, stored but not
  counted), 181,230 marks, 541 bill-committee links. The séances
  carry no presence list.
- **CL** Cámara: every plenary session's roll ("Asiste" / "No Asiste" with
  the justification verbatim), 98 sessions in 2026, 15,186 marks; the
  committee service knows only two current committees (Salud, which is on
  our ground, and Ética), the same stale service member intelligence hit.
  No referral link.
- **NL** Tweede Kamer: committee debates, wetgevingsoverleggen and
  notaoverleggen this term with their participants ("Deelnemer") and zaken.
  NOT a roll call: usually one spokesperson per fractie takes part, so the
  count says "took part in", labelled on every line. 284 debates, 2,463
  participations, 99 referrals.
- **CO** Cámara plenary: `co_attendance` (datos.gov.co 48i3-vuny), copied
  across so every country renders alike.

Plenary vote participation, DERIVED from the stored votes where the record
lists who did not vote: IT (assente, in missione, presente non votante), CH
(Nicht teilgenommen, Entschuldigt), PL (ABSENT, PRESENT), ES (No vota), AR
(AUSENTE), PE (AUS, the licences), DO (AU, SV), HU (four non-voting codes);
the 365 days to the newest stored vote; excused absences counted apart;
basis stated with every figure. Not for FR, BE, HR, EC or the Câmara's votes:
their records list only those who voted, and an absence is never inferred.

Shown in each member profile ("Attendance": per committee and the plenary,
"attended N of M sittings", with its basis) and in each debate pack (a new
section in the pack's language: the committee(s) handling the bill, each
member's sittings attended and sittings on this bill attended, least
attended first; participation beside the named speakers and the members to
watch). Samples: `docs/samples/attendance/`.

Not built, and why: Poland (committee sittings carry no attendance, scanned
lists); Switzerland and Austria (committee meetings closed; AT votes by
group); Italy (the Camera publishes no committee presence; participation
from votes); Spain (dissolved,
no attendance file); Peru, Panama and the Dominican Senate (PDFs only);
Argentina, Ecuador, Mexico, Belgium, Croatia, Slovakia (no attendance file
found).

### 3c (Portugal). Plenary attendance -- BUILT 11 October 2026 (branch `pt-attendance`)

The attendance round left Portugal out believing the presence was a PDF per
sitting. It is not: the PDF beside each sitting on "Presenças às Reuniões
Plenárias" is the agenda; the roll is an HTML page per sitting
(`DetalheReuniaoPlenaria.aspx?BID=...`), every seated deputy with group and
status, and the motive of a justified absence ("Falta Justificada (FJ):
Doença", "Trabalho Político", "Casamento", ...), stored verbatim. Statuses
seen over the XVII's 119 sittings: Presença (P) 25,049; FJ 1,341; AMP
(missão parlamentar) 759; PNO (presença noutro órgão) 172; Falta 17; Falta
ao Quórum de Votação 19; Falta Injustificada (FI) 9. P counts as present;
FJ, AMP and PNO as excused; the rest as absent. Each deputy links by
DepCadId, so all 27,370 marks matched `pt_members`, and an Efetivo period
and the printed group in the member service on the day (`pt_verify`, logged
each run). Hand-check: 10 random sittings re-read from the raw pages by an
independent text parse agreed on 2,300 of 2,300 rows.

`fetch_pt` in `src/attendance.py`, a step of `jobs/pt-weekly.sh` before the
profiles: at most 40 rolls a run (the first three runs backfill the XVII),
then the new sittings and the last three weeks again. Profiles: "Plenary:
present at N of M sitting(s)". PT debate packs: the plenary roll beside each
named speaker and member to watch (`PLENARY_ROLL_PACKS`, Portugal only; CL
and CO packs unchanged). Sample: `docs/samples/attendance/pt-plenary.md`.
Not built: committee attendance (not published); earlier legislatures (the
index filters by legislature by postback; a later backfill if wanted).

### 3c. Length of service -- BUILT 11 October 2026 (branch `ukp2-service`)

The UK's `tools/pull_service.py` was built after a member's page said "MP
since 13 Aug 2026" beside votes from years before: a roster's start date is
the start of the current period, not of a member's service. The new
countries had the same trap and a worse one: AT, PT and NL member positions
were DERIVED from the group by the group a member sits in today, so a member
who took their seat last month was given positions on votes taken before it,
and a member who changed group was given the new group's votes for the old
days.

`src/member_service.py` and `tools/member_service.py <cc>` (a step of each
weekly before the profiles; the tool skips a source read within its cadence,
`STALE_DAYS`: a week for one-request sources, four weeks for the rest; AT and BR, a request a member, read the longest-unread first within a time budget and are due again the next week when cut short) store
every period each member sat in `ms_periods` (chamber, term, start, end,
precision `day` or `term`, the party or list and the group for the period,
the seat), every dated party or group spell in `ms_party`, and what each
source covers in `ms_runs`. Sources, all the parliament's own open data:

| Country | Source | Precision | Covers |
|---|---|---|---|
| CH | ws.parlament.ch MemberCouncilHistory | day | every NR and SR period since 1848, party and group |
| NL | gegevensmagazijn FractieZetelPersoon | day | every fractie seat recorded; fractie spells matched by Fractie_Id |
| FR | AMO30 (all acteurs, all mandates) | day (prise de fonction) | ASSEMBLEE mandates from the 12th legislature (2002); GP spells |
| AT | parlament.gv.at biographies (`/person/<PAD>?json=TRUE`) | day | every NR and BR mandate, Klub and Wahlpartei |
| PT | InformacaoBase I to XVII | day | each deputy's Efetivo situations and DepGP spells since 1976 |
| IT | dati.camera.it SPARQL | day | every Camera mandate of the Republic, dated group adhesions; Senate not read (403) |
| ES | Congreso odsDiputados00-14, DiputadosActivos/DeBaja | day | every seat since 1977, dated group |
| PL | Sejm API `/term<N>/MP` | day (oath to expiry) | terms 3 to 10 (from 1997), linked by name and date of birth (never stored) |
| BR | Câmara `historico`, Senado `mandatos` | day | each sitting member's entries and exits (each chamber separately), Senate party filiations |
| CL | the Cámara's militancias in the store | day | deputies only; senators not read |
| HU | karzat (in the store) | day | the current term only; Wikidata's SPARQL is disallowed by robots.txt |
| SK | NRSR MP lists per term | term | terms 1 to 9 |
| HR | sabor.hr member lists | term | the 10th and 11th sazivi |
| BE | lachambre.be member list per legislature | term | from the 48th legislature |
| AR, PE, DO, MX | the store's current term | term | the current term only |
| EC, SV, GT, CO, UY | none | | nothing is said |

What a profile or page says: "Serving since" (the start of the current
unbroken run of day-precision periods in the member's chamber; "at least"
when it starts on the source's first day), the earlier periods with their
dates, or the terms where the source names terms only, and always what the
source covers ("nothing here says whether this is a first term"). The index
gains a Service column; the vote pages a service line on each member card
and a note. DERIVED positions are corrected in the profiles, the vote pages
and `src/country5ca.positions` (so the 5CA candidates and campaign targets
too): a member who did not sit on the vote's day is left out, and a member is
given the vote of the group they belonged to that day ("group's vote on the
day, X5"); a member without dated rows keeps the latest-group derivation and
its label. X6: an as-listed party yields to a dated group spell covering the
day (none of BE, HR, EC, GT, CO has dated spells yet). Samples:
`docs/service-samples/`.

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

**Built 11 October 2026 (branch `gaps-week-ahead`).** Belgium
(`src/agendas/be.py`): the Chamber's eMeeting service, plain XML behind
the viewer (`/agenda/api/meetings/week/<y>/<w>/calendar.xml`, then each
meeting's agenda.xml), plenary and committees, one point per item in Dutch
with the French, dossier keys from the links ('56/1338'); 5-second crawl
delay per robots.txt; `bill_rows` now accepts a table with no tier column
(additive). Portugal (`src/agendas/pt.py`): the Agenda Parlamentar's
calendar JSON (Plenário, Comissão Permanente, committees), one point per
numbered or listed item, keys from the printed numbers ('XVII/J/623') and
the linked IniIds through pt_initiatives. Slovakia (`src/agendas/sk.py`):
the open data's Meetings and MeetingProgram, print keys ('9/1324'); empty
until a sitting is convened. Poland: committee and subcommittee sittings
(`/committees/sittings/<date>`), prints as refs. Spain: the plenary row's
order of the day PDF has a text layer; it is split into its numbered items
with their expedientes (fills from 23 December). Steps added to
`jobs/{be,pt,sk}-weekly.sh`. Live reads of 11 October: BE 54 points (the
government's declaration week, nothing on our ground), PT 291 (the PMA
initiatives on 15 October, watched; the gender-procedure hearing in the
Constitutional Affairs committee, watched XVII/J/479), SK none convened, PL
46 with committees. Not built: Mexico (hosts refuse UK addresses; the
orden del día appears on the morning of the sitting), Swiss committee
agendas (confidential; dates only, in a planning PDF), Hungary (CAPTCHA).
NL, FR, AT and BR already read committee meetings.

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

**Remaining speeches built 11 October 2026 (branch `gaps-speeches`):**
Croatia (`tools/hr_chamber.py`), Slovakia (`tools/sk_chamber.py`), Polish
speeches and Brazilian speeches (second feeds of `tools/pl_chamber.py`,
`tools/br_chamber.py`). Details and measured runs in each scope doc.

### 6. Later phases already approved (in each scope doc's phase list)
Set A BUILT 10 October 2026 (branch `parity-phases-a`; each scope doc's
"as built" section): French Senate (FR5), Eerste Kamer via web pages (NL4),
Slovak bill documents (SK6), Swiss Italian texts (CH6), Italy's official
Camera service (IT2). Set B below covers UY5, BO4, X8 and X7. Still to
build: regions and Landtage after national: built 12 October 2026 (Spain,
Peru, Mexico, Austria, Italy; below).

**IT3, Italy's regional councils, BUILT 12 October 2026 (branch
`regions-it`, docs/italy-regions-scope.md).** Covered: Lombardia (the
council's open data on dati.lombardia.it, with stage dates), Campania and
Marche (HTML bill lists) and the Provincia autonoma di Trento (open-data XML
of bills, motions, orders of the day, petitions): 958 acts, 22 on our ground
on the first run, five of them regional assisted-dying bills.
`tools/it_regions.py` into `it_reg_acts`; a "Regional councils" section in
the Italian edition; a step in `jobs/it-weekly.sh` (nothing to install).
Blocked: Veneto (Akamai 403), Puglia, Basilicata and Sicilia's ARS
(robots.txt), Molise (self-signed certificate); unreachable from the UK:
Abruzzo, Piemonte, Sardegna, Umbria, Valle d'Aosta. Not built yet (forms or
no list found): Lazio, Emilia-Romagna, Toscana, Calabria, Liguria, FVG,
Bolzano, the Trentino-Alto Adige regional council. No council publishes
member votes we can read (Lombardia's vote PDFs are a possible later phase).
Taxonomy-it v0.3 (12 October 2026, Chris: "Add the Mexico and Italy keyword
terms too"; gambling "tier 2 under marriage and family"): the proposed
regional terms are applied (`educazione relazionale`, `consultorio`,
`gioco d'azzardo` and its variants); 13 new Italian matches (9 bills, 4
regional acts) and 2 Swiss Italian, no false positives; regional rows
reclassify on the next weekly, the national bills on one Italy weekly run
with `IT_RECLASSIFY=true`.

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

**AT6, Austria's Landtage, built 12 October 2026 (branch `regions-at`;
`docs/austria-regions-scope.md`).** Seven of nine Landtage (Wien,
Niederösterreich, Oberösterreich, Steiermark, Salzburg, Vorarlberg,
Burgenland; about 85 per cent of the population), each from its own system
(no two share a platform): `tools/at_landtage.py` into `atl_items` /
`atl_reads` (`src/atl_store.py`), titles classified with taxonomy-atch, a
`landtage` watchlist section by key, and a **Landtage** section in the
Austrian edition after the Watchlist (new additive hook
`Country.extra_sections`; other editions unchanged), with Steiermark's and
Oberösterreich's recorded decisions and their Klubs verbatim. A step of
`jobs/at-weekly.sh` (five minutes at most; a week's read is under one); no
new Mini job. Blocked: **Kärnten** (www.ktn.gv.at disallows every robot but
Google and Bing) and **Tirol** (lte.tirol.gv.at disallows every robot);
**RIS Landesrecht**, the only common source for adopted Land laws, is barred
by data.bka.gv.at's robots.txt and www.ris.bka.gv.at's bot check (parser
ready and tested, not read). Waiting on Chris: RIS permission, Wien's
Gemeinderat, Salzburg's unreadable robots.txt (treated as no rules).

### 6b. Regions -- Peru BUILT 12 October 2026 (branch `regions-pe`, PE4)

Peru's 25 regional governments and Lima Metropolitana, all at once
(`docs/peru-regions-scope.md`): `tools/pe_regions.py` reads El Peruano's
Normas Legales (one form POST a week; the gazette where every ordenanza
regional must be published) and each institution's council-act pages on
gob.pe (61 pages, 3 s apart), into `pe_regional_norms` (keyed
`<region>/<kind>/<n>-<year>`, the two sources merged on one row). Taxonomy-es
over heading and sumilla; 19 of 1,352 norms on our ground in the first read
(child marriage, the Arequipa ESI ordinance, gender-equality plans, violence
against women). Shown in the monthly Latam monitor as a "Regional governments
and Lima Metropolitana" sub-heading under Peru; tier-1 and watched norms also
alert. A step in `jobs/pe-weekly.sh` (budget 300 s); no new Mini job. Blocked
or not built: votes (regional councils publish no roll calls), sittings and
agendas (26 different sites, PDF or video), consejeros, El Peruano's full-text
search (client-side behind a bot-manager script; the Filtro form serves the
same listing in HTML). Cajamarca, Puno, San Martín, Huánuco and Lima
Metropolitana keep stale gob.pe pages and are covered by the gazette alone.

**Spain's regional parliaments, built 12 October 2026 (branch `regions-es`,
`docs/spain-regions-scope.md`):** all seventeen communities' laws and
decree-laws from the BOE's open-data summaries (Spanish for every community;
153 acts from January to 9 October 2026), plus bills in passage from the
lists of Andalucía (RSS), Canarias, La Rioja (government bills) and
Cantabria, classified with `taxonomy-es`; the Corts Valencianes' bills are
stored but unclassified (Valencian only) and counted as a gap. A "Regional
parliaments" section in the Spanish edition and one DM line; a step in
`jobs/es-weekly.sh` (no new job, nothing to install). Blocked: Madrid,
Navarra and Galicia (Sucuri, Cloudflare and Akamai bot checks, never
bypassed), Murcia and Extremadura (robots.txt disallows all), País Vasco,
Illes Balears and Aragón's tramitación base (no answer from the laptop),
Cataluña (Catalan only, open-data page 500), Castilla y León, Castilla-La
Mancha and Asturias (no machine-readable bill list). Canarias' open-data API
sits under a robots-disallowed `/api/`. Waiting on Chris: the proposed terms
(`concebido`, `apoyo a la familia`: Madrid's Ley 5/2026 on the conceived child
is missed today) and a Catalan/Valencian list.

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

## Blocked, waiting on replies

All from cjoyce@citizengo.net.

| Item | Asked of | Status |
|---|---|---|
| Hungary bills and votes (CAPTCHA): W-API token | api-reg2@parlament.hu | sent 9 Oct; karzat covers 9 May to 28 Aug meanwhile |
| Spain Senate (403 everywhere): open data | informacion@senado.es | sent 9 Oct |
| Paraguay (SILpy robots.txt disallows) | parlamentoabierto@senado.gov.py, cc silpy@diputados.gov.py | sent 9 Oct |
| meineabgeordneten.at licence | office@meineabgeordneten.at | sent 9 Oct |
| Open States (US) | contact@openstates.org | sent 9 Oct; replied with paid tier pricing |
| Australia | webmanager@aph.gov.au | sent 9 Oct |
| Guatemala court (bot challenge) | comunicacion@cc.gob.gt, asked to forward to the Unidad de Información Pública | sent 12 Oct |
| El Salvador missing votes (sessions 41-64, 98): LAIP request | transparencia@asamblea.gob.sv | sent 12 Oct |
| France clip agreement | communication@assemblee-nationale.fr | sent 12 Oct |
| Belgium clip agreement | pri@dekamer.be | sent 12 Oct |
| Uruguay main site (403 everywhere): open-data team | address being found | being sent 12 October |
| Argentina Diputados votes (no connection from anywhere) | address being found | being sent 12 October |
| Costa Rica (refuses foreign connections) | participacion-consultas@asamblea.go.cr takes internal senders only; no external address published | bounced, parked |

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

## Regional layer: Mexico's 32 state congresses (12 October 2026)

Scope and build: `docs/mexico-regions-scope.md`. Code: `tools/mxs_collect.py`,
`src/ingest/mxs_<state>.py` (13 readers), `src/mxs_store.py` (`mxs_items`,
`mxs_reads`), `src/mxs_edition.py`, `config/watchlist-mx-states.yaml`,
`tests/test_mxs.py`. A step of `jobs/mx-collect.sh` (the Mexican edition's
fortnightly GitHub job; no new Mini job), on a 15-minute clock.

- **Covered (13):** Estado de México, Ciudad de México, Chiapas, Oaxaca,
  Chihuahua, Tamaulipas, Baja California, Sinaloa, Yucatán,
  Quintana Roo, Tabasco, Aguascalientes, Nayarit: every iniciativa (and
  punto de acuerdo where listed) with date, author, committee and status
  where the source gives them, classified with taxonomy-es (mx). The
  edition has a "State congresses" section and the DM a line.
- **Unreachable from the UK (5):** Veracruz, Guanajuato, Nuevo León,
  Michoacán (https), Zacatecas; the step asks each from the runner every
  run and the edition says if one answers.
- **Blocked (4):** Puebla (Cloudflare challenge), San Luis Potosí (Sucuri
  challenge), Campeche (robots.txt disallows all), Durango (Wordfence geo
  block). Never bypassed.
- **Not built (10):** Jalisco (77 s a page), Querétaro (plain HTTP only),
  Guerrero, Coahuila (JSF),
  Sonora (thin), Hidalgo, Morelos (late PDFs), Tlaxcala, Colima (undated),
  Baja California Sur.
- **No member votes yet:** Baja California and Estado de México publish
  them in HTML, Tamaulipas, Coahuila and Tabasco in PDFs (phase 2), with
  the SCJN list of recent state reforms for enacted laws across all 32.
