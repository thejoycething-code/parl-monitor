# France: scoping the Parlement monitor

Probed live on 9 October 2026, from the laptop, through `src/http.py`
(CitizenGO UA, one request a second per host). Every number below was
measured, not estimated. Raw probe responses are archived under
`data/raw/2026-10-09/fr-probe_*` (local only; data/raw is published by
`tools/raw_state.py`, never committed). National parliament first; the
regions are listed at the end and not scoped.

## Decisions already taken (Christopher, applied here)

- **Own edition**, delivered to Christopher alone (Slack DM), as for the US.
- **Shared taxonomy concept, no edits to any existing taxonomy file.**
  France-specific terms are PROPOSED below and wait for his approval before
  any `taxonomy-fr` file is generated. Belgium and Switzerland are being
  scoped in parallel and also use French; each proposed term says whether
  it is France-only.
- **National parliament first**; regions later.
- **Mac Mini first, GitHub Actions as the backup**, as in the Australia
  branch. No new paid services. Nothing is ever posted publicly.

## The finding that shapes everything

**France publishes everything we need, keyless, in bulk, refreshed every
night.** The Assemblee nationale's open data gives every scrutin public of
the 17th legislature with every deputy's position and group, every dossier
legislatif with its documents, every deputy, the agenda, written and oral
questions and every amendment. Phase 1 is built on it and runs in under a
minute.

**The English taxonomy is blind to French, as it was to German.** Over the
same 3,248 dossiers and 8,621 scrutins:

| Classifier (no watchlist) | Dossiers on our ground | Scrutins on our ground | of which on the scrutin's own title |
|---|---|---|---|
| English (`taxonomy.yaml`) | 13 | 0 | 0 |
| Quebec French (`taxonomy-qc.yaml`) | 78 | 1,170 | 236 |
| Quebec + `watchlist-fr.yaml` (what phase 1 runs) | 83 | 1,208 | 236 |
| Draft France list (proposed below) | 115 | 1,226 | 1,223 |

"On our ground" means any area except 11 (migration, collated not
campaigned). The Quebec list gets most of the volume because one law
dominates it (below), but it misses the French legal vocabulary: **"aide a
mourir" is not a Quebec term** ("aide medicale a mourir" is), nor are
"assistance medicale a la procreation", "instruction en famille",
"questionnement de genre" or "reconnaissance du genre a l'etat civil". The
draft France list closes those, and lets a scrutin classify on its own
title (1,223 of 1,226) instead of leaning on the join to its dossier.

Written questions tell the same story. Of the 6,745 questions ecrites dated
2026, matched on their AN index heading (rubrique and analyse): English 12,
Quebec 58, draft France 93. On heading and full text: English 53, Quebec
317, draft France 404.

### The aide a mourir law: the ground has moved to implementation

The end-of-life bill is the single largest item on our ground, and the
AN's own dossier (`DLR5L17N51670`, "Fin de vie", Senat `ppl24-661`) shows
it is now law:

| Stage | Date | Outcome |
|---|---|---|
| AN first reading | 27 May 2025 | adopted (305 for, 199 against, 57 abstentions) |
| Senat first reading | 28 January 2026 | rejected |
| AN second reading | 25 February 2026 | adopted (299, 226, 37) |
| Senat second reading | 12 May 2026 | rejected |
| Commission mixte paritaire | 3 June 2026 | no agreement |
| AN nouvelle lecture | 30 June 2026 | adopted (295, 232, 35) |
| Senat nouvelle lecture | 7 July 2026 | rejected |
| AN lecture definitive | 15 July 2026 | adopted (291, 241, 29) |
| Conseil constitutionnel | 14 August 2026 | conforme |
| Promulgation | 18 August 2026 | |

931 scrutin titles say "aide a mourir"; 380 name the dossier directly. On
the final vote the groups split: EPR 64 for, 18 against; RN 12 for, 106
against; DR 5 for, 41 against; DEM 20 for, 16 against; HOR 16 for, 18
against; the left groups almost wholly for. Every position is in the store
with the group at the vote, so a France 5CA on this law needs no new data.
The companion bill on soins palliatifs (`DLR5L17N51672`) was promulgated on
26 May 2026. **What happens next is regulatory** (the decrees applying the
law, published in the Journal officiel) and in the courts, neither of which
is in phase 1. See "Waiting on Chris".

Other live items on our ground found by the probe: a bill to remove the
specific conscience clause on IVG (`DLR5L17N54992`, sent to committee 6
October 2026); the under-15 social media bill (`DLR5L17N53187`, Senat vote
21 July 2026); the Senate-adopted bill on medical practice for minors "en
questionnement de genre" (`DLR5L16N49654`, pending at the AN since the 16th
legislature); bills to restore instruction en famille (five dossiers); a
string of bills and resolutions on laicite, religious neutrality and
"entrisme islamiste"; and resolutions on prostitution and the sexual
exploitation of minors.

## What France publishes

### Assemblee nationale: data.assemblee-nationale.fr (works today, open, no key)

All under `https://data.assemblee-nationale.fr/static/openData/repository/17/`.
Licence Ouverte. No key, no account, no rate limit published, no robots.txt
(404). Every zip below answered HEAD with `Last-Modified` between 22:27 on
8 October and 02:06 UTC on 9 October 2026, `ETag`, `Accept-Ranges` and
`Cache-Control: max-age=14400`: they are rebuilt nightly and replaced in
place. Each is offered as JSON and XML; the JSON is the XML converted, which
is the source of most quirks.

| Dataset | Path | Zip | Records (9 Oct 2026) | Notes |
|---|---|---|---|---|
| Scrutins | `loi/scrutins/Scrutins.json.zip` | 26.9 MB (176 MB unzipped) | 8,621 (8 Oct 2024 to 8 Oct 2026) | every position, by group |
| Dossiers legislatifs | `loi/dossiers_legislatifs/Dossiers_Legislatifs.json.zip` | 10.7 MB | 3,248 dossiers, 7,304 documents | full timeline of acts |
| Amendements | `loi/amendements_div_legis/Amendements.json.zip` | 315 MB | not downloaded | exposes sommaires; phase 1b |
| Sitting deputies (AMO10) | `amo/deputes_actifs_mandats_actifs_organes/...json.zip` | 4.9 MB | 574 deputies, 7,116 organs | groups are organs of type GP (12) |
| All deputies since 2002 (AMO30) | `amo/tous_acteurs_mandats_organes_xi_legislature/...json.zip` | 13.7 MB | named 78 departed voters | read only when needed |
| Agenda (reunions) | `vp/reunions/Agenda.json.zip` | 8.4 MB | 8,024 meetings | points carry dossier refs |
| Questions ecrites | `questions/questions_ecrites/Questions_ecrites.json.zip` | 49.3 MB | 18,853 (6,745 dated 2026) | indexed: rubrique + analyse |
| Questions au gouvernement | `questions/questions_gouvernement/Questions_gouvernement.json.zip` | 5.4 MB | 1,800 | |
| Debates (Syceron) | `vp/syceronbrut/syseron.xml.zip` | 57.0 MB | not unpacked | the compte rendu, XML only |

Downloads from the laptop: scrutins 11.7 s, dossiers 6.3 s, AMO10 1.3 s,
agenda 3.4 s, questions ecrites 13.3 s, QAG 1.1 s.

**Scrutins.** One file per scrutin (`VTANR5L17V<n>.json`): date, type
(8,526 SPO ordinaire, 72 SPS solennel, 23 MOC motion de censure), result
(`sort.code`: adopte / rejete), title, the counts, and every deputy under
their group as `pours` / `contres` / `abstentions` / `nonVotants`, with
`acteurRef` (the AN's stable deputy ID, `PA1008`), `parDelegation` (15.4%
of all positions cast were by proxy) and, for non-votes, a cause (`PAN`
President of the Assembly, `PSE` presiding, `MG` member of the government).
By year: 525 in late 2024, 4,422 in 2025, 3,674 in 2026 so far.

Quirks, all handled in `tools/fr_rollcalls.py` and tested:

- **Two scrutins in three do not name their dossier.** Only 2,795 of 8,621
  carry `objet.dossierLegislatif.dossierRef`. The rest are amendment and
  article votes whose title names the text in full. Matching that name
  against every document title joins 3,940 more; 1,331 are ambiguous (the
  2025 and 2026 budget bills carry their titles in several dossiers) and
  are left unjoined, which costs nothing because a budget lends no area;
  522 match nothing, mostly because the text was renamed in committee (the
  soins palliatifs bill was debated as "relative a l'accompagnement et aux
  soins palliatifs" and filed under three other titles). 151 scrutins on
  our ground are unjoined; every one is classified on its own title.
- **XML-to-JSON shapes.** A single voter is an object, several are a
  list; an empty position is `null`; the `miseAuPoint` blocks are lists
  with nulls in them; some uids are `{"#text": "PA1008"}`.
- **Mises au point.** 1,267 scrutins carry at least one deputy saying
  afterwards that they meant to vote otherwise. The official result never
  changes; the store keeps both (`position` and `intended`).
- **Scrutin numbers run across the whole legislature** (1 to 8,621), not
  per session, so `an-17-<n>` is a stable key.
- **Recess.** The AN voted 695 times in June 2026, 531 in July (to 22
  July), none in August or September, and 187 times from 1 to 8 October.

**Dossiers.** Each dossier (`DLR5L17N<n>`) has a short title ("Fin de
vie"), the procedure (2,207 propositions de loi ordinaires, 75 projets de
loi, 253 resolutions, 204 article 34-1 resolutions, 92 constitutional, 66
organic, and others), the initiator, the Senat's dossier URL when the text
has been there, and a nested timeline of acts with codes (`AN1-DEPOT`,
`SN1-DEBATS-DEC`, `CMP-DEC`, `CC-CONCLUSION`, `PROM-PUB`). The documents
(bills, reports, adopted texts, including the Senat's) carry the long
titles. Dossiers from the 16th legislature that are still live (texts the
Senat adopted before the 2024 dissolution) keep their `DLR5L16` key.

### Senat: data.senat.fr (works today, open, no key, harder to use)

Licence Ouverte; `robots.txt` allows everything. Refreshed nightly
(`Last-Modified` 01:47 to 03:24 UTC on 9 October 2026).

| Dataset | URL | Size | Notes |
|---|---|---|---|
| Dosleg (dossiers, texts, **scrutins**) | `/data/dosleg/dosleg.zip` | 16.0 MB zip, 126.5 MB SQL | PostgreSQL 8.4 dump |
| Dossiers list | `/data/dosleg/dossiers-legislatifs.csv` | 3.6 MB | |
| Amendments (Ameli) | `/data/ameli/ameli.zip` | 154 MB | PostgreSQL dump |
| Senators | `/data/senateurs/ODSEN_GENERAL.json` | 1.1 MB | 2,012 records, 348 current |
| Questions | `/data/questions/questions.zip` | 283 MB | also a one-year CSV, 1.7 MB |
| Debates | `/data/debats/cri.zip` | 545 MB | |

**Senat votes are in the Dosleg dump**, not a dataset of their own: table
`scr` (4,764 scrutins; 359 in the 2024-25 session, 337 in 2025-26 to 21
July 2026) and `votsen` (1,657,344 positions, keyed by the senator's
`senmat` matricule, with a position code and a status such as "Excuse" or
"President de seance"). 29 Senat scrutins of the last two sessions name
the aide a mourir text, 10 soins palliatifs.

Quirks that make the Senat phase 2, not phase 1:

- It is a SQL dump: parseable with the stdlib (the `COPY ... FROM stdin`
  blocks are tab-separated), but it is 126 MB to read for a few hundred
  rows.
- **The vote-to-dossier link is sparse.** `scr.code` joins
  `date_seance.code`, then `lecture`, then `loi`; only 16 of the 696
  scrutins of the last two sessions reach a dossier that way. Like the AN,
  the scrutin's own text (`scrint`) names the text, so title matching is
  the route.
- **Broken encoding.** 343 of those 696 `scrint` values carry a Windows-1252
  apostrophe or have lost it ("lordre", "lensemble"), which breaks exact
  title matching until it is repaired.
- `loi.signet` (`ppl24-661`) and `loi.url_an` give a clean crosswalk to the
  AN's dossiers (the AN side carries `senatChemin`).
- Senate elections took place in late September 2026 (data.senat.fr has an
  `elections-senatoriales-2026` page); the senators' file must be re-read
  after them.
- `www.senat.fr/scrutin-public/<year>/scr<year>-<n>.html` answers 200 (215
  KB per page) if the dump ever proves unusable.

### Other sources, probed or noted

- **NosDeputes.fr / NosSenateurs.fr** (Regards Citoyens, volunteer):
  `nosdeputes.fr/deputes/json` answered 200 (814 KB). Not needed: the AN's
  own data is complete, and the AN is the primary source.
- **Legifrance / Journal officiel** (decrees applying the aide a mourir law,
  laws as promulgated): not probed. DILA publishes the JO in bulk
  (echanges.dila.gouv.fr) and the PISTE API needs an account. Phase 3.
- **Conseil constitutionnel decisions**: not probed. The AN dossier already
  records the referral and the conclusion (`CC-SAISIE-*`, `CC-CONCLUSION`).
- **Petitions**: the AN and the Senat both run petition platforms; not
  probed.

## Proposed taxonomy (for Christopher's approval; nothing generated)

The areas and keys stay CitizenGO's. The proposal is a France file,
`docs/keyword-taxonomy-fr.md` generating `config/taxonomy-fr.yaml`, built
on the Quebec list (which is good French and caught 78 dossiers on its own)
with the additions and guards below. `tools/generate_taxonomy.py` already
says "a France or EU French layer would be a different file"; adding `fr`
to its `MASTERS` is a one-line change. The collector switches to it with
no code change. Every term was measured on the AN's 2024-2026 data; the
counts are scrutin titles / dossiers / written questions (all 18,853).

"FR only" marks terms specific to French law or debate; "shared" terms are
likely useful in Belgium and Switzerland too (worth comparing with their
scope docs).

| Area | Proposed term | Tier | Measured | Scope |
|---|---|---|---|---|
| 1 Abortion | `liberte garantie a la femme` (art. 34 of the Constitution, 2024) | 1 | 0 / 0 / 1 | FR only |
| 1 | `clause de conscience` with IVG / interruption volontaire / avortement | 1 | caught `DLR5L17N54992` | shared |
| 1 | `delit d'entrave` with IVG / interruption volontaire / avortement | 1 | 0 / 0 / 5 | FR only |
| 1 | `Planning familial` | 2 | | FR only |
| 2 Assisted dying | `aide a mourir` | 1 | 931 / 1 / 7 | FR only (Quebec: "aide medicale a mourir"; Belgium: "euthanasie") |
| 2 | `assistance au suicide` | 1 | 0 / 0 / 0 | shared (Swiss usage) |
| 2 | `Claeys-Leonetti`, `sedation profonde et continue` | 1 | 0 / 0 / 4, 0 / 0 / 1 | FR only |
| 2 | `soins d'accompagnement`, `directives anticipees` | 2 | 0 / 0 / 3, 0 / 0 / 4 | FR only |
| 2 | guard: `euthanasie` without animaux / animal | | removes 1 false dossier | shared |
| 3 Gender medicine | `questionnement de genre` | 1 | caught `DLR5L16N49654` | FR only |
| 3 | `transidentite*` with mineur* / enfant* / jeune* / eleve*; bare at tier 2 | 1 / 2 | 0 / 0 / 5 | shared |
| 5 Sex-based rights | `reconnaissance du genre`, `changement de sexe a l'etat civil` | 1 | 2 dossiers | FR only |
| 5 | `LGBT*` | 2 | | shared |
| 6 Parental rights, education | `instruction en famille` | 1 | 0 / 7 / 33 | FR only |
| 6 | `education a la vie affective` (EVARS), `EVARS` | 1 | 0 / 0 / 33, 0 / 0 / 24 | FR only |
| 6 | `etablissement* hors contrat`, `ecole* hors contrat` | 1 | 0 / 2 / 14 | FR only |
| 6 | `autorite parentale`, `controle parental` | 2 | 0 / 0 / 37 | shared |
| 7 Free speech, online safety | `majorite numerique`, `haine en ligne`, `contenus haineux` | 1 | 0 / 0 / 1-4 | FR only |
| 7 | `reseaux sociaux` with mineur* / moins de quinze ans / moins de 15 ans / age | 1 | 39 / 12 / 216 (bare) | shared |
| 7 | `pornograph*` with mineur* / enfant* / age (Quebec has it only as a guard) | 1 | 0 / 0 / 18 (bare) | shared |
| 7 | `Arcom` | 2 | 0 / 0 / 24 | FR only |
| 7 | guard: `censure` without "motion(s) de censure" | | removes 23 MOC scrutins and about 20 dossiers | FR only |
| 8 Freedom of religion | `separatisme`, `loi de 1905`, `christianophobie`, `antichretien*` | 1 | 0 / 1 / 29, ..., 0 / 0 / 9 | FR only |
| 8 | `principes de la Republique` with culte* / religi* / association* / laicite | 1 | 0 / 6 / 35 | FR only |
| 8 | `entrisme` with islamis* / religi* / communautari* | 1 | 0 / 5 / 31 | FR only |
| 8 | `profanation*` with eglise* / lieu de culte / cimetiere* / tombe* | 1 | 0 / 1 / 8 | shared |
| 8 | `islamisme`, `islamiste*`, `proselytisme`, `port du voile`, `abaya*`, `Freres musulmans` | 2 | Freres musulmans 17 / 1 / 21 | FR only (needs a scope call: is political Islam area 8?) |
| 9 Marriage, family | `mariage pour tous` | 1 | 0 / 0 / 0 | FR only |
| 9 | `conge de naissance` | 2 | 0 / 0 / 11 | FR only |
| 10 Surrogacy, embryology | `assistance medicale a la procreation`, `PMA`, `GPA`, `bioethique`, `autoconservation des ovocytes` | 1 | AMP 0 / 1 / 10; PMA 0 / 0 / 17; bioethique 0 / 1 / 19 | PMA, GPA shared; AMP and bioethique law FR only |
| 12 Prostitution, trafficking | `systeme prostitutionnel`, `achat d'actes sexuels`, `achat d'un acte sexuel` | 1 | 0 / 0 / 3 | FR only (the 2016 law) |
| 12 | `traite des etres humains` (Quebec says "traite des personnes") | 1 | 0 / 4 / 11 | shared |
| 12 | `pedocriminalite`, `pedopornograph*` | 1 | 1 / 3 / 11 | shared |
| 13 Organ donation | `prelevement* d'organes` | 1 | | shared |

(Accents are dropped in this table for search; the terms themselves keep
them: "aide à mourir", "laïcité", "séparatisme".)

Known noise the proposal does not yet fix, for Christopher's call:

- Area 9 carries 42 scrutins on a bill against "mariages simules ou
  arranges" (sham marriages), which is immigration fraud rather than our
  ground. A guard (`mariage` without "simule*" / "arrange*") would drop it.
- "inceste" (17 written questions, 5 dossiers) is child protection and
  criminal law; left out.
- Political Islam ("entrisme islamiste", "Freres musulmans") is a large
  French theme (5 dossiers, 17 scrutins, 50 questions). Whether it sits in
  area 8 is a scope decision, like antisemitism in the US.

## Phase 1: built, 9 October 2026

`tools/fr_rollcalls.py` into `fr_members`, `fr_groups`, `fr_dossiers`,
`fr_divisions` and `fr_votes` (schema in `src/fr_store.py`, declared in
`db.TABLES`). Live run into a scratch database, not the store, on 9
October 2026:

| | Read | On our ground |
|---|---|---|
| Dossiers legislatifs | 3,248 | 83 |
| Scrutins | 8,621 | 1,208 (718 in 2026) |
| Positions | 1,294,136 | |
| Deputies (574 sitting + 78 departed, from AMO30) | 652 | |

24 seconds end to end from cached zips; the downloads add about 30
seconds. No gaps.

- **Keys.** Deputies on the AN's `acteurRef`; dossiers on their uid
  (`DLR5L17N51670`); divisions on `an-17-<numero>`. Never titles.
- **Every position is stored**, with the group at the vote, the proxy flag,
  the non-vote cause and the mise au point.
- **Votes classify on their own title, then inherit their dossier's
  areas** (`own_areas` keeps the first apart), joined by `dossierRef` or a
  unique title match (`dossier_via` says which).
- **Classifier**: `config/taxonomy-qc.yaml`, read-only, until a France
  list is approved; `config/taxonomy-fr.yaml` is picked up automatically
  when it exists. Plus `config/watchlist-fr.yaml` (seven dossiers, by key)
  for the Quebec list's measured misses, and two masked false friends
  ("motion de censure", "euthanasie des animaux") documented in the tool.
- **Resume.** A later run stores new scrutins and re-reads the last 30
  days' (mises au point arrive after the vote); dossiers and deputies are
  re-read whole every run. `--reclassify` re-derives areas offline.
- **Raw archive.** The bulk zips are not archived (`archive=False`), as
  with the US BILLSTATUS zips. See "Waiting on Chris".
- **Tests.** `tests/test_fr_rollcalls.py` (25 tests) on real AN files
  trimmed into `tests/fixtures/fr/` (176 KB): the aide a mourir final and
  first-reading votes, an amendment joined by title, a budget amendment left
  unjoined, a motion de censure, a scrutin with mises au point, a defence
  article, the dossiers and documents behind them, three deputies, all
  groups and one departed deputy.

### The weekly job

- `jobs/fr-weekly.sh`: the collector, then `tools/raw_state.py --push` and
  `tools/db_state.py --push`; exit 3 from the collector (gaps) still
  publishes.
- Mac Mini first: `ops/launchd/net.citizengo.parlmonitor.fr-weekly.plist`,
  Saturdays 13:00 London, through `tools/mini_run.sh fr-weekly` (which
  records `MINI_LAST_FR_WEEKLY`).
- GitHub backup: `.github/workflows/fr-weekly.yml`, Saturdays 13:00 and
  15:00 UTC (moved from 03:00 and 05:00 at the countries merge, where
  Austria and Belgium hold the early slots), behind `mini-check` with job `FR_WEEKLY` and a 200-minute
  grace, then the same-day retry gate copied from the US and Australia.
  The slots are clear of every cron on main and on the country branches
  seen on 9 October (Saturday holds 06:00, 08:00, 10:00, 11:00, 14:00,
  18:00).
- It runs only once merged to main: GitHub schedules from the default
  branch, and the Mini runs from its runner clone of main.

### Shared files touched (for the merge of the country branches)

| File | Change |
|---|---|
| `src/db.py` | five `fr_*` names added to `TABLES` after the US block; `fr_store.ensure_schema(conn)` added to `init_db` after `us_store` |
| `tools/coverage.py` | `"France weekly"` in `PIPELINES`; `fr_dossiers`, `fr_members`, `fr_divisions` in `FEEDS`; `"France weekly"` in `PIPELINE_FEEDS` and `AWAITING_FIRST_RUN` |
| `.github/workflows/alert.yml` | `"France weekly"` added to the watched workflow names |

All three are insertions next to the US entries, the same places the
Australia branch inserts its own, so the merges are textual neighbours,
not conflicts of meaning. Everything else is new and France-only:
`src/fr_store.py`, `tools/fr_rollcalls.py`, `config/watchlist-fr.yaml`,
`tests/test_fr_rollcalls.py`, `tests/fixtures/fr/`, `jobs/fr-weekly.sh`,
the plist, `.github/workflows/fr-weekly.yml` and this document.

One wiring lesson for the other branches: `tests/test_raw_state.py` and
`tests/test_vote_tracker_display.py` search workflow and job text for the
literal strings `db_state.py --push` and `raw_state.py --push`, comments
included. A comment that names `db_state.py --push` before the script
publishes the archive fails the suite. The Australia branch's
`au-weekly.yml` and `jobs/au-weekly.sh` carry both comments as of 9
October.

## Phase plan

1. **Phase 1 (built): AN scrutins, dossiers, deputies.** Above.
2. **Phase 1b: the France taxonomy.** On approval: `docs/keyword-taxonomy-fr.md`,
   `fr` in `tools/generate_taxonomy.py`, generate, `FR_RECLASSIFY=true`
   once. The watchlist then shrinks to what no term can carry.
3. **Phase 2: the Senat.** Scrutins and positions from the Dosleg dump,
   senators from `ODSEN_GENERAL.json`, joined to AN dossiers through
   `loi.signet` / `senatChemin` and by repaired title. Then AN amendments
   (315 MB; the exposes sommaires say what an amendment does, which the
   scrutin title does not).
4. **Phase 3: the agenda and the regulatory side.** The AN agenda (dossier
   refs on every point) as the week ahead (**Week ahead built 10 October 2026** (branch `parity-week-ahead`, `src/agendas/fr.py`, a step of the weekly job): Agenda.json.zip, archived as FR3; 216 points on 10 October); written questions on our ground
   (the measure above: 93 a year on headings alone); the Journal officiel
   for the decrees applying the aide a mourir law.
5. **Phase 4: edition and 5CA.** A France edition to Christopher by Slack
   DM; a 5CA from positions, groups and authorship.
6. **Later: regions** (below).

## Regions (listed, not scoped)

France's regions have no legislative power over our areas (criminal law,
health, civil status, education content and religion are national). Their
councils vote budgets and subsidies (family planning centres, school
buildings, associations), so they matter for campaigns rather than law.

- 13 metropolitan regions: Auvergne-Rhone-Alpes, Bourgogne-Franche-Comte,
  Bretagne, Centre-Val de Loire, Corse (Collectivite de Corse, its own
  Assembly), Grand Est, Hauts-de-France, Ile-de-France, Normandie,
  Nouvelle-Aquitaine, Occitanie, Pays de la Loire, Provence-Alpes-Cote
  d'Azur.
- 5 overseas regions or single authorities: Guadeloupe, Martinique, Guyane,
  La Reunion, Mayotte.
- Overseas collectivities with their own law-making (lois du pays): the
  Congress of New Caledonia and the Assembly of French Polynesia.

### Chamber layer: debates, speeches and questions (parity layer 5, 10 October 2026)

Built: the compte rendu intégral of every sitting (`/dyn/opendata/CRSANR5L17S2027O1N012.xml`, walked by number from the last read, a session never read entered by a binary search on the date) and the questions écrites and questions au gouvernement (the nightly dumps, classified on the Assemblée's own index, never the full text), `tools/fr_chamber.py`, a step of the French weekly. The two question dumps (55 MB) are not archived (rebuilt nightly, re-fetchable). Measured 20 September to 9 October 2026: 17 sittings, 4,448 speeches, 118 on our ground (99 in the bill on sexual and sexist violence); 643 written questions, 15 on our ground.

## Waiting on Chris

1. **Approve, amend or reject the proposed France term list** (the table
   above), including the two scope calls inside it: political Islam
   ("entrisme islamiste", "Freres musulmans") in area 8 or not, and a guard
   for "mariages simules". Nothing is generated until he says so.
2. **The raw archive for France.** The AN overwrites its zips nightly, so a
   week-old copy cannot be re-fetched. Archiving the three weekly zips
   costs about 43 MB a week in the raw-archive release; not archiving keeps
   only the parsed store. Phase 1 does not archive. His call.
3. **The aide a mourir law is promulgated.** Is the France edition's first
   job to follow its application decrees and any repeal attempts (which
   means the Journal officiel, phase 3, sooner), or the remaining
   parliamentary ground?
4. **Merge and schedule.** The weekly runs only once the `france` branch is
   merged to main, and the Mini needs the plist installed
   (`launchctl bootstrap`) and, if heartbeats are wanted, an
   `HC_FR_WEEKLY` check created. No `FR_WEEKLY` repository variable needs
   creating by hand: `mini_run.sh` sets `MINI_LAST_FR_WEEKLY` itself.
5. **A French reader.** As with Quebec and Germany, the terms are measured
   but not read by someone who campaigns in France. Worth one pass before
   the edition goes beyond Christopher.
6. **Senat phase 2** (answered: FR5, go ahead; built 10 October 2026): confirm it is wanted before the 126 MB dump is read
   weekly (about 16 MB to download).

## Decisions of 10 October 2026 (applied at the countries merge)

Recorded in `docs/country-decisions-2026-10-10.md`. Shared: accents fold and non-ASCII letters are word characters in the filter (X3); member positions are stored for every vote (X15); the AI judge stays off (X16).

Applied on the `countries` branch:

- French additions approved (FR1, FR2 political Islam in area 8) and generated as the addendum `config/taxonomy-fr.yaml` (taxonomy-qc plus France, Belgium, Switzerland); the collector loads it for `fr`.
- FR3: the AN weekly zips are now archived to data/raw.
- Weekly moved to Saturday 13:00/15:00 UTC (Austria and Belgium hold the early slots).

Later phases and items for Chris (not built at the merge):

- Phase: follow the aide a mourir decrees first (FR4): a watch on the Journal officiel's implementing decrees once the law passes.
- Phase: the Senat (FR5, go ahead): votes and dossiers from senat.fr open data. BUILT 10 October 2026 (branch `parity-phases-a`): see "FR5, as built" below.
- Member profiles (handover item 3, built 10 October 2026, branch `parity-profiles`): `profiles/fr/` from the store each weekly run (`tools/member_profiles.py fr`, src/member_profiles.py): party, chamber, constituency, every recorded position on a vote on our ground as the edition classifies it, verbatim, with the basis of the party at the vote; no verdicts, no DM.

## FR5, as built (10 October 2026, branch `parity-phases-a`)

`tools/fr_senat.py`, a step of `jobs/fr-weekly.sh` after the Assemblee's
collector. It reads data.senat.fr's Dosleg dump at most weekly and only when
it changed (a one-byte request reads Last-Modified, ETag and size first;
`fr_senat_dump` remembers them), plus `ODSEN_GENERAL.json` and
`ODSEN_HISTOGROUPES.json` for senators and their dated group spells.

- **Same tables as the Assemblee**, `chamber = 'senat'`: senators keyed by
  matricule, groups `senat:<code>` shown by the name the senators' file
  prints ("Les Républicains" for the internal code UMP), scrutins
  `senat-<session>-<number>` with every position and the group at the vote,
  and `fr_senat_dossiers` for the Senate's dossiers since 2024-25. Schema in
  `src/fr_store.py`.
- **The encoding**: every C1 character is read back as Windows-1252. The
  apostrophes the scope thought lost ("lensemble") were U+0092 all along
  (docs/api-notes.md).
- **Joined to the Assemblee**: 593 of the 696 scrutins since the 2024-25
  session reach a dossier (16 by the Senate's own chain, 577 by a unique
  title); 756 of 865 Senate dossiers are linked to the Assemblee's (the
  Senate's `url_an`, by uid or path slug, or the Assemblee's `senat_url`),
  so the aide a mourir law's 28 Senate scrutins sit in the Assemblee's
  dossier `DLR5L17N51670`, watched.
- **No result word**: the dump has none, so `result` is NULL and the
  edition prints the counts and the absolute majority of votes cast.
- **Measured** (scratch store, 10 October 2026): 865 dossiers, 696
  scrutins, 64 on our ground, 2,012 senators, 242,058 positions, about 15
  seconds to load.
- **Sample**: `docs/parity-samples/fr-senat-2026-01-28.md` (SAMPLE, never
  sent), 19 to 28 January 2026: the Senate's first-reading votes on the
  aide a mourir law (rejected 122 to 181 on 28 January, as the Senate
  recorded it) and on the palliative care bill, group by group.
- **Not built**: AN amendments (315 MB), Senate amendments (Ameli), Senate
  questions and debates.

## 5CA and stance sign-off (built 10 October 2026, branch `parity-5ca`)

Phase list: **done** (docs/5ca-notes.md, "The new country editions"). `config/fr_stance.yaml` holds 7 bill direction(s) (Claude's drafts from the watchlist) and 13 vote reading(s): 10 with proposed values, 0 procedural, 3 need reading, 0 confirmed. Guide: `docs/5ca-fr-readings.md`; confirm with `python3 tools/country_5ca.py --cc fr --sign-from-doc --by NAME`. Sheets (`data/5ca/fr-5ca-*.csv`) appear only once a reading is confirmed. Waiting on Chris: who signs for France (`config/stance_signers.yaml`).

**Sign-off scope (Chris, 10 October 2026): final votes and watched amendments only.** France's sign-off covers votes on the whole text and motions to reject it (and procedure about the whole text); an amendment or article vote is drafted only when listed under its dossier's `amendments:` in `config/watchlist-fr.yaml`, by division key (`an-17-1773`) or amendment number (`"n° 3"`, any vote in that dossier on that number). The first drafts had held 1,050 readings, 1,037 of them amendments and articles of the aide a mourir law; `tools/country_5ca.py --cc fr --prune-out-of-scope` removed those 1,037 (all unsigned and untouched; a confirmed or hand-edited entry is never removed). No amendment is watched yet. Branch `fr-signoff-scope`.


## Debate packs (built 10 October 2026, branch `camp-debate-packs`)

A manual command, like the UK and German packs; no scheduled job:

    python3 tools/country_debate_pack.py --country fr --date YYYY-MM-DD --list
    python3 tools/country_debate_pack.py --country fr --date YYYY-MM-DD --item DLR5L17N51670 [--speakers "Name; Name"]
    python3 tools/country_debate_pack.py --country fr --date YYYY-MM-DD --find "<words of the title>"
    python3 tools/country_debate_pack.py --pack data/packs/fr-<date>-<slug> --onside

It writes `data/packs/fr-<date>-<slug>/`: `pack.md` and `checklist.md` in French (the frame is
translated in `src/debatepack_i18n.py`; titles, names and positions stay the source's own words),
`members.csv`, `pack.json`, and an English `README.md`. It reads the store only (the item through
this country's edition classification, votes by ID), fetches nothing and calls no AI. Members: every member's recorded position on the bill's decisive votes (final, rejection) and on the latest watched or tier-1 votes on the same areas, the split by group, and the members who broke with their group's majority (arithmetic on the record, never a stance).
Agenda slot: read by bill key from the `country_agenda` table (the week-ahead layer, src/agenda.py) once the weekly step has read the agenda; until then, the edition's own week ahead (scheduled acts on the dossier). Likely speakers: no source here publishes a speakers' list ahead, so they are named by
hand with `--speakers` (matched to the member list) once known. Placements come only from
readings confirmed in `config/fr_stance.yaml`; none is confirmed yet, so every pack shows
"en attente de validation" (awaiting sign-off) and places nobody. See docs/debate-pack-social.md, "New
countries".

## Same-day vote briefs (built 10 October 2026, branch `parity-vote-briefs`)

Handover item 1: a brief for each watched or tier-1 vote, naming the members who voted against their group's majority, one DM to Chris per run, de-duplicated in `data/vote-briefs/fr.json` (`src/country_vote_brief.py`, step in `jobs/fr-weekly.sh`). Briefed after each weekly collection. Not daily: the Assemblée publishes its scrutins only as one 27 MB nightly zip, and reading only its newest members by HTTP range is unsafe (on 10 October its CDN served two builds of the file, 26,987,736 and 26,960,828 bytes, to successive range requests). See docs/mac-mini.md, "Vote briefs for the new countries".
