# Switzerland: scoping the Federal Assembly monitor

Probed live on 9 October 2026, from the laptop, through `src/http.py` (the
honest CitizenGO UA, 0.2 s throttle, retry with backoff). Every number below
was measured, not estimated; raw responses are archived under
`data/raw/2026-10-09/` (`ch-probe_*` and `ch-rollcalls_*`). Federal Assembly
only; the 26 cantonal parliaments are a later decision (listed at the end).

## Decisions already taken (Christopher)

- **Own edition**, delivered to Christopher alone (Slack DM), like the US.
- **Shared taxonomy, no edits to any existing taxonomy file.** German text is
  matched with `config/taxonomy-de.yaml`, French text with
  `config/taxonomy-qc.yaml`; Swiss-specific additions are PROPOSED below,
  not made.
- **Federal Assembly first**, cantons later. Federal popular initiatives and
  referendums are noted as a channel.
- **Mac Mini first, GitHub Actions as backup.** No new paid services. Never
  post publicly anywhere.

## Phase 1: built, 9 October 2026

`tools/ch_rollcalls.py` into `ch_members`, `ch_sessions`, `ch_businesses`,
`ch_divisions` and `ch_votes` (schema in `src/ch_store.py`, declared in
`db.TABLES`), with `config/watchlist-ch.yaml` applied by Geschaeftsnummer.
Weekly job: `jobs/ch-weekly.sh`, the launchd plist
`ops/launchd/net.citizengo.parlmonitor.ch-weekly.plist` (Saturday 08:00
London) and `.github/workflows/ch-weekly.yml` (Saturday 09:00 and 11:00 UTC,
gated by `mini-check` with job `CH_WEEKLY`). Tests:
`tests/test_ch_rollcalls.py` on real files under `tests/fixtures/ch/`.

First live run into a scratch database (not the store), 52nd legislature
(Wintersession 2023 to Herbstsession 2026):

| | Read | On our ground |
|---|---|---|
| Businesses submitted in the 52nd legislature (DE and FR) | 10,178 | 453 |
| Older businesses a vote named, fetched by ID | 773 | 39 |
| Nationalrat votes (15 sessions, 3 of them special) | 4,201 | 151, on 71 businesses |
| Staenderat votes (12 sessions, spreadsheets) | 2,101 | 80, on 20 businesses |
| Members sitting since 4 December 2023 | 277 | |
| Positions stored (divisions on our ground only) | 33,862 | NR 30,189, SR 3,673 |

**Four minutes (236 seconds) from an empty database**, about 245 requests (22 business pages, 15 vote lists, 12 sheets, 40 batched business reads, 151 position reads);
the second run, a day's changes plus the open session, took **19 seconds**.
Zero gaps, once the procedural-vote quirk below was handled. Every
Staenderat name in all 12 sheets resolved to a member. The 453 businesses on
our ground split taxonomy-de 340, taxonomy-qc 256, both 147, plus the
watchlist; on title plus submitted text, the two lists again agree on well
under half of what either finds.

What the divisions on our ground are: area 9 dominates (90 NR, 68 SR
votes), because three long bills were voted article by article: the
childcare-funding initiative 21.403 (59 votes in both councils, matched on
"Vereinbarkeit von Familie und Beruf"), the individual-taxation initiative
and counter-proposal BRG 24.026 (28, from the provisional watchlist entry),
and double surnames on marriage 17.523 (25). Then abortion 22 and 2,
sex-based rights 21 and 10, freedom of religion 12 and 1. Single votes
include the cantonal initiative to ban conversion therapies (22.310), the
evaluation of the Fristenregelung (23.3762), the Sarco suicide pod
(24.4093), protection of unborn children late in pregnancy (24.4492), the
child-marriage bill (23.057, 6 votes) and the assisted-suicide framework
motions (25.3944 and 25.3945).

Noise worth knowing before triage sees it, all from a vote's own text being
matched in both languages: the Quebec list's tier-1 "IVG" (interruption
volontaire de grossesse) also spells the German abbreviation of the
Invalidity Insurance Act, and tagged 5 votes on autism early intervention
(BRG 24.066) as abortion; "euthanasie" caught a motion on killing healthy
pets; "Sterbehilfe" caught a motion that uses it figuratively ("aktive
Sterbehilfe für Hausbrennereien", home distilleries). The fix for the first
is a Swiss veto on "IVG" ("Invalidenversicherung"), proposed below.

- **Divisions inherit their business's areas**; `own_areas` keeps the vote's
  own match apart, as in the US.
- **Positions are stored only for divisions on our ground** (the Canada
  rule). The Nationalrat alone cast 4,201 votes this legislature, 840,200
  positions. A division that gains an area later has its positions fetched
  on the next run.
- **The Nationalrat publishes no totals and no result** in the OData
  service. A stored division's counts are tallied from its positions
  (`counts_from = 'tallied'`); `result` stays NULL rather than being
  derived. The Staenderat's spreadsheets publish both (`'published'`).
- **Not yet merged, so not yet scheduled.** GitHub schedules only from the
  default branch; the Mini needs the plist installed (see Waiting on Chris).

## The finding that shapes everything

**Switzerland needs both languages at once, and still misses Swiss
vocabulary.** Every business is published in German and French (and
Italian); the 10,178 businesses submitted in the 52nd legislature are all
translated (3 of 10,178 titles are identical in DE and FR, all proper
names; no submitted text is). Matched on titles, with the unchanged
taxonomies:

| Text matched | taxonomy-de on DE | taxonomy-qc on FR | Both agree | DE only | FR only | Union | English list on DE |
|---|---|---|---|---|---|---|---|
| Titles | 163 | 109 | 57 | 106 | 52 | **215** | 41 |
| Titles + full texts (incl. reasons) | 472 | 352 | 212 | 260 | 140 | 612 | 164 |

Areas 11 (migration, collated not campaigned) excluded throughout. The two
lists agree on barely a third of what either finds. Neither language alone
is enough: German misses the Swiss legal term "medizinisch unterstützte
Fortpflanzung" (French "procréation médicalement assistée" catches it, 8
titles), French misses "traite des êtres humains" and "féminicide" (German
catches "Menschenhandel", 20 titles, and "Femizid", 11). So phase 1 matches
both and takes the union.

Title precision is good: of 25 title hits sampled at random, about 22 are
plainly ours (abortion statistics, assisted suicide for healthy people,
surrogacy, persecuted Christians, confidential birth). Matching the long
reasoning texts as well triples the count but only about half the extra
hits are ours (Desinformation in defence motions, "mariage" in tax
administration). **The collector matches title plus submitted text** (the
motion's wording, the question asked) and leaves the reasons and the
Federal Council's background out.

On our ground by area (titles, union of DE and FR): freedom of religion 38,
free speech 34, sex-based rights 30, prostitution and trafficking 30, marriage
and family 23, abortion 20, assisted dying 16, surrogacy and embryology 14,
organ donation 6, parental rights 3, gender medicine 2, conversion 1.

By business type (titles): interpellations 67, Fragestunde questions 54,
motions 47, postulates 20, parliamentary initiatives 10, petitions 6,
cantonal initiatives 4, Anfragen 4, Federal Council businesses 3. Most of
the ground is **Vorstoesse** (members' motions and questions), not bills.

### What both lists missed (measured)

Counts are titles in the 52nd legislature containing the word, and how many
of those neither list put on our ground:

| German | titles | missed | French | titles | missed |
|---|---|---|---|---|---|
| Individualbesteuerung | 12 | 12 | imposition individuelle | 13 | 12 |
| Familienzulage | 11 | 11 | congé parental | 7 | 7 |
| Jugendschutz | 10 | 9 | protection de la jeunesse | 2 | 2 |
| häusliche Gewalt | 9 | 9 | violence domestique | 14 | 14 |
| Moschee | 8 | 8 | mosquée | 8 | 6 |
| LGBT / LGBTIQ | 7 | 6 | LGBT | 7 | 7 |
| Christen | 7 | 6 | chrétien | 7 | 5 |
| Smartphone | 6 | 6 | réseaux sociaux | 14 | 13 |
| Palliativ (Palliative Care) | 5 | 5 | assistance au suicide | 5 | 5 |
| Pornografie | 5 | 5 | pornographie | 3 | 3 |
| Pädokriminalität | 4 | 3 | pédocriminalité | 4 | 3 |
| Verhüllungsverbot | 3 | 3 | voile | 10 | 10 |
| E-ID | 22 | 21 | identité électronique / e-ID | 8 / 15 | 8 / 14 |
| Sarco (suicide pod) | 2 | 2 | antisémitisme | 10 | 10 |
| Konversion | 1 | 1 | féminicide | 11 | 9 |
| nonbinär | 1 | 1 | traite des êtres humains | 6 | 5 |

Two grammatical misses are worth singling out: "Rahmenregulierung im Bereich
des assistierten Suizids" (Mo. 25.3944) is missed because the German term is
the nominative "assistierter Suizid", and its French title says "assistance
au suicide" where the list has "suicide assisté" and "aide au suicide". And
"Stopp der Gender-Ideologie ... Geschlechtsumwandlung" (Mo. 23.4408) has no
term in either list. Both are in `config/watchlist-ch.yaml`.

**Swiss orthography has no ß.** Swiss Standard German writes "ss"
("geschäftsmässig", "Massnahme"), so the two taxonomy-de terms spelled with
ß ("geschäftsmäßige Förderung der Selbsttötung", "Konversionsmaßnahme*")
can never match a Swiss text. 55 of the 10,178 German records contain a ß
at all, nearly all quoting German or EU law.

### Proposed Swiss additions (for Christopher; nothing has been edited)

Kept out of the shared files as instructed. The cleanest home is either a
Swiss section in each source markdown (`docs/keyword-taxonomy-de.md`,
`docs/keyword-taxonomy-qc.md`) or a small Swiss addendum file the collector
loads beside them. Proposed terms, by area:

- **1 abortion**: DE "Fristenlösung" (the Swiss name, 1 title, already hit by
  "Abtreibung"), "Art. 118 StGB", "Art. 119 StGB" (the Swiss sections);
  FR "interruption de grossesse" is already tier 2.
- **2 assisted dying**: DE stems "assistiert* Suizid*" (replacing the
  nominative), "Sarco", "Suizidkapsel*", "Sterbekapsel*", "Suizidhilfeorganisation*",
  "Palliative Care" (tier 2), "geschäftsmässig*" spelling; FR "assistance au
  suicide", "organisation* d'aide au suicide", "capsule* de suicide".
- **3 gender medicine**: DE "Geschlechtsumwandlung*", "Gender-Ideologie",
  "Transgender" (tier 2); FR "changement de sexe".
- **4 conversion**: DE "Konversionsmassnahme*" (Swiss spelling),
  "Konversionstherapien" is caught already.
- **5 sex-based rights**: DE "LGBTIQ*", "LGBT*" (Swiss acronym; the file has
  LSBTIQ), "nonbinär*", "non-binär*", "häusliche Gewalt" (tier 2);
  FR "féminicide*", "non binaire*", "LGBT*", "violence* domestique*" (tier 2).
- **6 parental rights and education**: DE "Pornografie" with a minors guard,
  "Altersverifikation", "Jugendschutz in den Bereichen Film und Videospiele",
  "Smartphone" and "Social Media" guarded to Kinder/Jugendliche/Schule,
  "Lehrplan 21" guarded to Sexual/Gender; FR "pornographie", "réseaux
  sociaux" guarded the same way, "protection de la jeunesse".
- **7 free speech**: DE "Art. 261bis", "Diskriminierungsstrafnorm",
  "Rassismusstrafnorm"; FR "norme pénale antiraciste", "261bis". Whether the
  **E-ID** (electronic identity, approved by referendum on 28 September 2025
  and the subject of 22 titles) is our ground is a scope question, not a
  vocabulary one: the French list already carries "identité numérique" in
  area 7.
- **8 freedom of religion**: DE "verfolgte* Christen", "Christen in
  Nigeria", "Verhüllungsverbot", "Moschee*" (tier 2), "Imam*" (tier 2),
  "Landeskirche*" (tier 2); FR "antisémitisme", "islamisme", "voile"
  guarded to école/enfant, "mosquée*" (tier 2), "chrétien* persécuté*".
- **9 marriage and family**: DE "Individualbesteuerung", "Heiratsstrafe",
  "Ehepaarbesteuerung", "Elternurlaub", "Familienzulage*" (tier 2),
  "Kinderbetreuung" (tier 2); FR "imposition individuelle", "pénalisation du
  mariage", "congé parental". **Christopher to decide** whether individual
  taxation (the marriage-penalty fight, 12 titles and a popular initiative)
  is our ground; the watchlist carries BRG 24.026 provisionally.
- **10 surrogacy and embryology**: DE "medizinisch unterstützte Fortpflanzung"
  (the Swiss legal term, Fortpflanzungsmedizingesetz), "Embryonenforschung".
- **Across lists**: a Swiss veto on the Quebec tier-1 "IVG", without
  "Invalidenversicherung" (see the noise above); "euthanasie" guarded to
  people, not animals.
- **12 trafficking**: FR "traite des êtres humains" (the Swiss and French form;
  the Quebec list has "traite des personnes"), DE "Pädokriminalität",
  FR "pédocriminalité".

An Italian list does not exist; Italy is being scoped in parallel. Italian
texts are published for every business (10,178 in the 52nd legislature),
so a future taxonomy-it would apply here unchanged.

## What Switzerland publishes

### Parliament Webservices (OData): works today, open, no key

`https://ws.parlament.ch/odata.svc/`, OData v2 (DataServiceVersion 1.0),
JSON with `$format=json`. 48 entity types in `$metadata` (130 KB). No key,
no login, CORS open. Akamai in front; no rate limit is documented and none
was hit at our throttle (several hundred requests on 9 October). No
robots.txt on this host (404).

| Entity | Rows (DE) | What it is |
|---|---|---|
| `Business` | 68,813 | Geschaefte / objets: every business since 1995 or so; 10,178 submitted in the 52nd legislature |
| `Vote` | 24,515 | **Nationalrat** recorded votes since the Wintersession 2003; 4,201 in the 52nd legislature, 328 in the Herbstsession 2026 |
| `Voting` | 4,900,834 | one row per member per vote: 200 for each Nationalrat vote |
| `MemberCouncil` | 3,705 | members since 1848; 254 active (200 NR, 46 SR, 7 Federal Council, 1 other) |
| `Session` | 185 | 15 in the 52nd legislature (12 ordinary, 3 Nationalrat special sessions) |
| `Transcript` | 47,005 in LP52 | the Amtliches Bulletin, speech by speech (4,336 in the Herbstsession 2026) |

Every entity is keyed `(ID, Language)` and exists in DE, FR, IT, EN and RM:
the same 24,515 votes in each.

Quirks, all measured:

- **The Staenderat is not in Vote or Voting.** Every vote has 200 positions;
  Pierre-Yves Maillard (Staenderat since December 2023) has his last Voting
  row in September 2023, when he left the Nationalrat; Hannes Germann
  (Staenderat throughout) has none at all. The Parliament's own page says
  so: individual votes via web services "ab Wintersession 2003" for the
  Nationalrat, nothing for the Staenderat.
- **Two JSON shapes.** A short answer is `{"d": [...]}`; a paged one is
  `{"d": {"results": [...], "__next": ...}}`. Business pages at 1,000 rows
  with a `$skiptoken`; the `__next` link drops `$format`, which must be put
  back. Voting is NOT paged: one session (`IdSession eq 5215`) returns all
  65,600 rows in one 19.7 MB answer in 9 seconds. The collector asks for
  positions vote by vote instead (200 rows, `$select`ed), and only for
  divisions on our ground.
- **Vote texts are not translated.** `Subject`, `MeaningYes` and
  `MeaningNo` read the same in every language; for the Herbstsession 2026
  they are French in all five ("Proposition de la majorité (ne pas donner
  suite)"). Business titles ARE translated. So a vote's own text is matched
  with both lists.
- **Decision codes** (`Voting.Decision`, against `DecisionText`): 1 Ja,
  2 Nein, 3 Enthaltung, 4 Anwesend (older sessions only), 5 Hat nicht
  teilgenommen, 6 Entschuldigt gemäss Art. 57 Abs. 4, 7 Die Präsidentin/der
  Präsident stimmt nicht.
- **Dates** are `/Date(ms)/` or `/Date(ms+0120)/`, the offset in MINUTES.
- **A procedural vote has business number 1**: an Ordnungsantrag carries
  `BusinessNumber` 1 and `BusinessShortNumber` "00.000" (23 of 4,201). The
  first run looked up "business 1" and recorded a gap; the collector now
  stores such votes with no business.
- **`$count`** answers plain text, not JSON; **errors** come back as JSON
  with a full .NET stack trace.
- **Vote has no totals and no result.** Only positions.
- `BusinessNumber` on Vote is the Business `ID` (20250059 for 25.059), the
  Geschaeftsnummer every source shares; the watchlist keys on it.

### Staenderat votes: works today, open, no key, one spreadsheet per session

`https://www.parlament.ch/centers/documents/de/Abstimmungen_SR_<session>_DE.xlsx`,
listed (incompletely) on `parlament.ch/de/ratsbetrieb/abstimmungen/abstimmung-nr-xls`.
The Staenderat has voted electronically since spring 2014 (protocols in the
Amtliches Bulletin) and publishes spreadsheets **from the Fruehjahrssession
2022**. All 12 ordinary sessions of the 52nd legislature were found: 2,101
votes, 135 to 226 a session, every member's position, the council's own
result and published totals.

Quirks, all measured:

- **File names are not regular.** `2026HS`, `2025WS`, but `2024Frühjahr`
  (2024FS is a 404), and on the Nationalrat side `2023Sommer`,
  `2025SonderMai`, `2026SonderApril`. The listing page links only six of
  the Staenderat files and carries one malformed link. The collector tries
  each spelling in turn and records a gap only when none answers 21 days
  after the session ends (the Herbstsession 2026 file was up seven days
  after the session closed).
- **Two layouts.** To the Sommersession 2024 the member block carries a
  "Ratsmitglied (Nr)" row of PersonNumbers, cantons as "AG" and a header
  starting "Abstimmungsdatum"; from the Herbstsession 2024 the number row is
  gone, cantons are German names ("Appenzell A.-Rh.") and the header starts
  "Geschäftsnummer". Columns shift between sessions of one layout. The
  parser finds everything by its label.
- **No PersonNumber in the newer files**, so a position is matched to a
  member by surname, first name and then canton; an unmatched name is
  dropped and recorded as a gap, never guessed. All 46 names of every
  newer sheet matched the 277 members sitting since December 2023.
- **Spellings vary**: "Ja"/"ja", "Hat nicht teilgenommen"/"hat nicht
  teilgenommen", "Entschuldigt gem. Art. 57 Abs. 4"/"entschuldigt", one
  "anwesend".
- **A vote with no business**: sr-7875 (8 December 2025) has no
  Geschaeftsnummer and 0 yes, 0 no, 45 absent; the older sheets pad each
  meaning with " | * | *".

### Curia Vista (web): works, HTML

`parlament.ch/de/ratsbetrieb/suche-curia-vista/geschaeft?AffairId=<ID>`
answers 200 (240 KB, a SharePoint page that loads its data by script). It
is the human view of the same Business records; the OData service is the
machine one, so the collector never scrapes Curia Vista. Links in an
edition should point here.

### Federal popular votes: works today, open, no key

opendata.swiss, dataset "Echtzeitdaten am Abstimmungstag zu eidgenössischen
Abstimmungsvorlagen" (Federal Statistical Office):
`ogd-static.voteinfo-app.ch/v1/ogd/sd-t-17-02-<yyyymmdd>-eidgAbstimmung.json`,
one file per voting day with every proposal's title in four languages and
national, cantonal and communal results. 27 September 2026: the Neutrality
initiative (29.8% yes) and the food-security initiative (27.5%); 14 June
2026: the "Keine 10-Millionen-Schweiz" initiative (45.2%) and the civilian
service act (52.5%, accepted).

Popular initiatives also reach Parliament as Federal Council businesses:
25 of the 241 BRG businesses of the 52nd legislature are "Volksinitiative"
messages, so the collector already sees each initiative when Parliament
debates it (BRG 24.026 individual taxation, 25.018 and 25.035 the
marriage-penalty initiatives). The **Federal Chancellery's chronologies**
of initiatives in signature collection and of referendums
(`bk.admin.ch/ch/d/pore/vi/vis_2_2_5_1.html`, `.../rf/ref_2_2_3_1.html`)
answer 200 but are a script-rendered shell with no data in the HTML; their
data source was not found on 9 October and needs a second probe. That is
where an initiative appears months before Parliament sees it, which is the
channel that matters most to CitizenGO.

### Not available

- **Staenderat positions before spring 2022** in machine-readable form (only
  the Amtliches Bulletin protocols, from 2014, as PDF).
- **Petitions to Parliament** exist only as businesses (153 in the 52nd
  legislature, type "Pet."); there is no e-petition site with signature
  counts.

## Phase plan

1. **Phase 1 (built):** members, sessions, businesses in DE and FR, both
   councils' votes, positions on our ground, the watchlist by number.
2. **Phase 1b: the Swiss terms.** Christopher's decision on the proposals
   above, then a re-run with `--reclassify`.
3. **Phase 2: the edition.** A Swiss monitor and triage on the US pattern
   (`tools/us_monitor.py`, `tools/us_triage.py`), to Christopher by Slack DM.
   Session-driven: four three-week sessions a year plus a special session,
   so most weeks are quiet and four are full. **Week ahead built 10 October 2026** (branch `parity-week-ahead`, `src/agendas/ch.py`, a step of the weekly job): the councils' `Meeting` and `Subject` records by business number; none ahead until the Wintersession programme is in the open data.
4. **Phase 3: initiatives and referendums.** The voteinfo results, and the
   Chancellery's signature-collection chronology once its data source is
   found. Consultations (Vernehmlassungen, fedlex.admin.ch, answers 200) and
   the Amtliches Bulletin (`Transcript`) for debate packs.
5. **Phase 4: cantonal parliaments**, later and by block (below).

## Cantonal parliaments (later; listed, not probed)

26 cantons, each with its own parliament (Grosser Rat, Kantonsrat, Landrat,
Grand Conseil, Gran Consiglio), most with their own business databases, and
no aggregator comparable to Open States. Zürich (Kantonsrat), Bern (Grosser
Rat), Luzern, Uri, Schwyz, Obwalden, Nidwalden, Glarus (Landrat; the
Landsgemeinde legislates), Zug, Fribourg/Freiburg (bilingual), Solothurn,
Basel-Stadt, Basel-Landschaft, Schaffhausen, Appenzell Ausserrhoden,
Appenzell Innerrhoden (Landsgemeinde), St. Gallen, Graubünden (trilingual),
Aargau, Thurgau, Ticino (Italian), Vaud, Valais/Wallis (bilingual),
Neuchâtel, Genève, Jura. Much of our ground is cantonal (schools and sex
education, cantonal assisted-suicide rules in Vaud, Neuchâtel and Valais,
the burqa bans of Ticino and St. Gallen before the federal one), so a block
by salience (Genève, Vaud, Zürich, Bern, Ticino) is the likely start.

## Shared files touched (13 branches will merge)

- `src/db.py`: five `ch_*` names in `TABLES`; `ch_store.ensure_schema` in
  `init_db`. 9 lines.
- `tools/coverage.py`: "Switzerland weekly" in `PIPELINES`,
  `PIPELINE_FEEDS` and `AWAITING_FIRST_RUN`; four `ch_*` rows in `FEEDS`.
  18 lines.
- `.github/workflows/alert.yml`: "Switzerland weekly" in the watched list.
  1 line.

Nothing else outside the Swiss files: no taxonomy, no `src/http.py`
change, no change to `tools/mini_run.sh` (it runs `jobs/ch-weekly.sh` by
name).

### Chamber layer: debates, speeches and questions (parity layer 5, 10 October 2026)

Built: the Amtliches Bulletin speech by speech (OData `Transcript`, Language DE, Type 1; business titles from `SubjectBusiness`), `tools/ch_chamber.py`, a step of the Swiss weekly. Each speech is read with the list of its own language (function words decide; `LanguageOfText` is empty for a third of speeches), and 'IVG' outside an abortion paragraph is masked as the disability-insurance law (measured: ten false abortion hits on the 26.029 inclusion bill). Questions are not collected here: the edition already carries the Vorstösse. Herbstsession 2026 (7 September to 2 October): 2,399 speeches read, 70 on our ground.

## Waiting on Chris

1. **The Swiss terms** above: which go into the shared lists, and where (a
   Swiss section in each source markdown, or a Swiss addendum file).
2. **Scope calls**: individual taxation and the marriage penalty (area 9?);
   the E-ID; the burqa ban (Verhüllungsverbot); antisemitism (as in the US
   question); domestic violence and femicide (area 5 tier 2, or out).
3. **Review `config/watchlist-ch.yaml`** (ten businesses, drafted by Claude).
4. **Merge the `switzerland` branch** when ready: GitHub schedules only from
   main, and the shared-file edits above need merging with the other
   country branches.
5. **On the Mac Mini**: copy the plist to `~/Library/LaunchAgents` and
   `launchctl bootstrap` it (the line is in the plist), after the merge.
   Optionally an `HC_CH_WEEKLY` heartbeat URL in `~/runner/env`.
6. **Italian**: whether the Italy scoping's list should also run on the
   Italian texts here (every business has one).
7. **A Swiss reader**: none of the German or French proposals has been read
   by someone who campaigns in Switzerland.

## Decisions of 10 October 2026 (applied at the countries merge)

Recorded in `docs/country-decisions-2026-10-10.md`. Shared: accents fold and non-ASCII letters are word characters in the filter (X3); member positions are stored for every vote (X15); the AI judge stays off (X16).

Applied on the `countries` branch:

- German additions (CH2 individual taxation area 9, CH3 E-ID, CH4 burqa ban) in `config/taxonomy-atch.yaml`, French in `config/taxonomy-fr.yaml`; both loaded for `ch`.
- X15: positions now read for every division, our ground first.

Later phases and items for Chris (not built at the merge):

- Phase: the Italian texts (CH6). BUILT 10 October 2026 (branch `parity-phases-a`): see "CH6, as built" below.
- The scope's veto on the Quebec IVG term and guard on euthanasie change base terms, so they are not in the addendum.
- Member profiles (handover item 3, built 10 October 2026, branch `parity-profiles`): `profiles/ch/` from the store each weekly run (`tools/member_profiles.py ch`, src/member_profiles.py): party, chamber, constituency, every recorded position on a vote on our ground as the edition classifies it, verbatim, with the basis of the party at the vote; no verdicts, no DM.

## CH6, as built (10 October 2026, branch `parity-phases-a`)

`tools/ch_rollcalls.py` reads a third language: every business's Italian
record (`Language eq 'IT'`) alongside the German and French, and matches
`config/taxonomy-it.yaml` for `ch` (its `[only: it]` terms dropped) on the
Italian title and submitted text. New columns on `ch_businesses`:
`title_it`, `areas_it`, `terms_it`, `tier_it`; `areas` is now the union of
all three languages and the watchlist. A business refreshed in German and
French only keeps its stored Italian result; one with no Italian record is
marked (`title_it = ''`) and not asked again. The Italian list is never run
on a vote's own text (written in German or French, where Italian terms are
false friends: "IVG").

Measured over the 52nd legislature (10,178 businesses, 10 October 2026):
6,739 have an Italian record (3,416 of the 3,564 Fragestunde questions do
not); the Italian list matches 431; **56 businesses are on our ground by
the Italian text alone**, mostly WHO and International Health Regulations
motions (area 7: "OMS", "Regolamento sanitario internazionale", 25), then
sexual violence, smartphones in schools, international adoption,
deepfakes. Noise to watch in the next term-list round: tier-1 "vita umana"
caught three biodiversity and health-insurance titles, "accanimento
terapeutico" one used figuratively (the Energy Charter Treaty). The Swiss
edition's coverage note says the Italian texts are read.

## 5CA and stance sign-off (built 10 October 2026, branch `parity-5ca`)

Phase list: **done** (docs/5ca-notes.md, "The new country editions"). `config/ch_stance.yaml` holds 3 bill direction(s) (Claude's drafts from the watchlist) and 82 vote reading(s): 1 with proposed values, 0 procedural, 81 need reading, 0 confirmed. Guide: `docs/5ca-ch-readings.md`; confirm with `python3 tools/country_5ca.py --cc ch --sign-from-doc --by NAME`. Sheets (`data/5ca/ch-5ca-*.csv`) appear only once a reading is confirmed. Waiting on Chris: who signs for Switzerland (`config/stance_signers.yaml`). 24.026 (individual taxation) has no direction until Chris confirms it is our ground (the watchlist's own note).


## Debate packs (built 10 October 2026, branch `camp-debate-packs`)

A manual command, like the UK and German packs; no scheduled job:

    python3 tools/country_debate_pack.py --country ch --date YYYY-MM-DD --list
    python3 tools/country_debate_pack.py --country ch --date YYYY-MM-DD --item 25.3944 [--speakers "Name; Name"]
    python3 tools/country_debate_pack.py --country ch --date YYYY-MM-DD --find "<words of the title>"
    python3 tools/country_debate_pack.py --pack data/packs/ch-<date>-<slug> --onside

It writes `data/packs/ch-<date>-<slug>/`: `pack.md` and `checklist.md` in German (the frame is
translated in `src/debatepack_i18n.py`; titles, names and positions stay the source's own words),
`members.csv`, `pack.json`, and an English `README.md`. It reads the store only (the item through
this country's edition classification, votes by ID), fetches nothing and calls no AI. Members: every member's recorded position on the bill's decisive votes (final, rejection) and on the latest watched or tier-1 votes on the same areas, the split by group, and the members who broke with their group's majority (arithmetic on the record, never a stance).
Agenda slot: read by bill key from the `country_agenda` table (the week-ahead layer, src/agenda.py) once the country's weekly step has read the agenda; until then the pack says the agenda is not collected. Likely speakers: no source here publishes a speakers' list ahead, so they are named by
hand with `--speakers` (matched to the member list) once known. Placements come only from
readings confirmed in `config/ch_stance.yaml`; none is confirmed yet, so every pack shows
"Freigabe ausstehend" (awaiting sign-off) and places nobody. See docs/debate-pack-social.md, "New
countries".
