# Netherlands: scoping the Tweede Kamer monitor

Probed live on 9 October 2026 from the laptop, through `src/http.py`'s
client (honest CitizenGO User-Agent, one request a second, retries with
backoff). Every number below was measured that day, not estimated. The raw
responses are archived under `data/raw/2026-10-09/` (130 files, 6.3 MB:
`nl-probe_*` for the scoping probes, `nl-rollcalls_*` for the collector's
own queries). Like every raw folder they are gitignored; the first scheduled
run publishes its own folder to the release.

## The finding that shapes everything

**The English taxonomy is blind to Dutch**, exactly as it was to German.
Run over the titles of all 12,877 zaken of the current Kamer (motions,
amendments, bills, written and oral questions, government letters and
treaties since 12 November 2025), `config/taxonomy.yaml` found **21 on our
ground** outside migration, and most of those because a Dutch title quotes
an English name: `hospice` (6), `Digital Services Act`, `My Voice, My
Choice`, `transgender`. Over the 4,860 votes of the same Kamer it found
**six**.

A first Dutch term list (proposed below, awaiting Chris) found **393 zaken
and 154 votes** on the same data, with migration excluded. Until that list
is approved, the collector classifies by `config/watchlist-nl.yaml` alone,
which already puts 41 votes on our ground by dossier number.

## Decisions already taken (Chris)

- Own edition per country, delivered to Chris alone (Slack DM), as the US.
- Shared taxonomy concept, but no existing taxonomy file is edited. The
  Dutch terms are proposed here; `config/taxonomy-nl.yaml` is generated only
  after Chris approves them. Belgium (Flanders) is being scoped in parallel
  and also uses Dutch; Netherlands-specific terms are marked (NL) below.
- National parliament first; provinces later.
- Mac Mini first, GitHub Actions as the backup. No new paid services. Never
  post publicly.

## What the Netherlands publishes

### Tweede Kamer Open Data Portaal: WORKS, no key

`https://gegevensmagazijn.tweedekamer.nl/OData/v4/2.0/`, OData v4, JSON.
38 entity sets, among them `Zaak`, `Besluit`, `Stemming`, `Agendapunt`,
`Activiteit`, `Document`, `Kamerstukdossier`, `Persoon`, `Fractie`,
`FractieZetel`, `FractieZetelPersoon`, `ZaakActor`, `Toezegging`. The schema
is at `$metadata` (57,755 bytes of XML).

| Property | Measured |
|---|---|
| Key needed | No. 200 with no credentials of any kind. |
| Rate limit | None advertised: no `RateLimit` or `Retry-After` headers on any response. At one request a second nothing was refused. |
| Page size | 250. `$top=1000` is a 400 ("The limit of '250' for Top query has been exceeded"). |
| Paging | `@odata.nextLink` with a `$skiptoken`. An explicit `$top` suppresses the nextLink. |
| Speed | Counts and small queries 0.1 to 4 s. A page of 250 votes with every position, zaak and dossier expanded: about 13 s. The whole current Kamer (4,860 votes): 20 pages, **69 seconds**. |
| Query features | `$filter` across navigation paths (`Agendapunt/Activiteit/Datum ge ...`), nested `$expand` with its own `$filter` and `$select`, `$count`, `$apply=groupby(...)`, `contains()`. |
| Deletions | Records are soft-deleted: `Verwijderd: true`. A collector must read them, not filter them out, to drop what the Kamer withdrew. |
| Documents | `Document(<id>)/resource` returns the file itself (a written answer: a 29,826-byte PDF). |
| Change feed | `SyncFeed/2.0/Feed?category=<Entity>`: Atom XML with a skiptoken, for full mirrors. Not needed at our volume. |
| Encoding quirk | A bare `+` in a time offset is read as a space; it must be sent as `%2B`. |

**Volumes, whole history and this Kamer:**

| | All time | Since 12 Nov 2025 |
|---|---|---|
| `Stemming` rows (positions) | 1,018,950 (earliest 9 September 2008) | 86,530 |
| of which one per member (roll calls and split groups) | 79,956 | 6,603 |
| Votes by show of hands (`Met handopsteken`) | 63,500 | 4,815 |
| Roll calls (`Hoofdelijk`) | 537 | 45 |
| Zaken | 343,136 | 12,877 of the kinds below |

Zaken started in this Kamer, by kind: Motie 5,002; Brief regering 4,611;
Schriftelijke vragen 2,083; Brief commissie 986; Amendement 955; Position
paper 645; Verzoek bij commissie-regeling van werkzaamheden 637; Brief van
lid/fractie/commissie 353; Overig 269; Brief Eerste Kamer 200; Begroting
134; Wetgeving 115; Nota van wijziging 104; Mondelinge vragen 83;
Initiatiefnota 8; Initiatiefwetgeving 6; Verdrag 14; and smaller kinds.

### How Dutch votes are recorded

**Mostly by party.** A vote by show of hands records one position per
fractie, with the fractie's seats (`FractieGrootte`). This Kamer averages
16.7 rows per vote, and the seats sum to 150 on 4,771 of 4,795 such votes
(to 149 on 23, on days when a seat was changing hands). Positions are
`Voor` (53,627), `Tegen` (32,398) and `Niet deelgenomen` (505).

**Hoofdelijke stemmingen are rare and are the 5CA layer.** 45 in this Kamer,
each with all 150 members by name (`Persoon_Id`, surname, fractie). Nine of
the 45 are on our ground. Eight are on embryo research: on 16 December 2025
the Paternotte and Bevers initiative bill lifting the ban on creating
embryos for research (passed 90-59), after a Bikker motion a week earlier
(adopted 72-70); on 2 June 2026 the government's Embryowet bill (passed
95-48) and five amendments by Bikker and Diederik van Dijk (all rejected,
46 or 48 to 95 or 97). The ninth is the rainbow-flag motion of 8 October
2026 (adopted 90-36). The Dutch roll call is the set-piece, exactly as the German
namentliche Abstimmung is.

Three quirks, each found in the data and handled:

1. **Positions arrive late.** The 21 votes of Thursday 8 October carried a
   result (`BesluitTekst: "Aangenomen (90-36)."`) and no positions at
   05:54 Amsterdam time the next morning, nor at 06:10. The collector re-reads a six-week
   window every week and stores such a vote with `positions_pending = 1`;
   still empty after 14 days is a recorded gap.
2. **A group can split.** On motion 2026Z08607 the Groep Markuszower row
   says Tegen with all seven seats and three of its members carry rows of
   their own saying Voor. Counted naively that is 153 of 150; the collector
   counts each member who votes apart once and takes them off the group's
   seats. One vote in this Kamer.
3. **A group can declare a mistake** (`Vergissing`): 143 position rows in
   this Kamer. The Kamer's result stands; the flag is stored.

The party is stored per vote, as everywhere in this repo: votes from the
spring carry `GroenLinks-PvdA` with 20 seats, while today's fractie list
names a 20-seat group `PRO`.

### Members, fracties, agenda, questions

- **Fracties:** 17 sitting, 150 seats: D66 26, VVD 22, PRO 20, PVV 19, CDA
  18, JA21 9, Groep Markuszower 7, FVD 7, ChristenUnie 3, SP 3, PvdD 3, SGP
  3, BBB 3, DENK 3, 50PLUS 2, Lid Keijzer 1, Volt 1.
- **Members:** `FractieZetelPersoon` with `TotEnMet eq null` gives exactly
  150 current seats; 52 date from the installation of 12 November 2025, the
  rest from later replacements or earlier seating. The Persoon record also
  holds date and place of birth, residence and gender; **none of it is
  requested or stored**.
- **Agenda:** `Activiteit` with a future date: 592 items from 9 October on
  (plenary, committee, procedure, working visits). Phase 2.
- **Kamervragen:** 2,083 written questions this Kamer as zaken, and 2,043
  answer documents (`Antwoord schriftelijke vragen`), served as PDF. Phase 2.

### Eerste Kamer: no API, two workable routes

- **eerstekamer.nl is HTML only.** `/opendata` and `/open_data` are 404,
  `data.eerstekamer.nl` does not resolve, `/wetsvoorstellen` is 404 (the
  list is at `/wetsvoorstellen_2`). `/stemmingen` redirects to
  `/stemmingen_per_vergaderdag`, which lists each sitting's votes with links
  to the bill (`/wetsvoorstel/36791_...`) or motion (`/motiedossier/...`)
  and the method ("Stemming bij zitten en opstaan", or Hamerstuk). The bill
  page states the result in prose, party by party: "De Eerste Kamer heeft
  het voorstel op 29 september 2026 na stemming bij zitten en opstaan
  aangenomen. Voor: PRO, Volt, ... Tegen: FVD en BBB." `robots.txt`
  disallows only search, print layouts and sort parameters. Parseable,
  but a scrape.
- **KOOP's SRU service** (`repository.overheid.nl/sru`, keyless, the
  government publications repository behind officielebekendmakingen.nl)
  holds the Eerste Kamer's Handelingen: 11,058 records with creator
  "Eerste Kamer der Staten-Generaal", and 513 Eerste Kamer publications
  dated since 1 September 2026, each with a URL to its XML. The proceedings
  record the vote outcomes. The same service answers a title search
  (`dt.title any "euthanasie"`: 558 records across both chambers).
- The Tweede Kamer portal does not carry Eerste Kamer votes: `Besluit` and
  `Stemming` are Tweede Kamer only. 1,377 zaken are marked "Eerste Kamer en
  Tweede Kamer" and 200 this Kamer are "Brief Eerste Kamer".

### Provinces (later, listed only)

Twelve Provinciale Staten: Drenthe, Flevoland, Friesland (Fryslân),
Gelderland, Groningen, Limburg, Noord-Brabant, Noord-Holland, Overijssel,
Utrecht, Zeeland, Zuid-Holland. Not probed. They also elect the Eerste Kamer,
which is the main reason they matter to us.

## How much touches CitizenGO ground

Measured on titles only (a zaak's onderwerp, its title and its dossier's
title), the current Kamer, migration (area 11) excluded because it is
collated and never campaigned:

| | English taxonomy | Draft Dutch list | watchlist-nl alone |
|---|---|---|---|
| Zaken (12,877) | 21 | **393** | n/a |
| Votes (4,860) | 6 | **154** | 41 |
| Roll calls (45) | 0 | **9** | 9 |

Draft Dutch list, zaken by area: abortion 41, assisted dying 24, gender
medicine 5, conversion practices 1, sex-based rights 49, parental rights and
education 42, free speech 41, religion 61, marriage and family 31,
surrogacy and embryology 41, prostitution and trafficking 72, organ
donation 3 (migration 526, hidden). By kind: Motie 140, Brief regering 109,
Amendement 68, Schriftelijke vragen 67, Wetgeving 4, Mondelinge vragen 2,
Initiatiefwetgeving 2, Initiatiefnota 1.

The 154 votes: motions adopted 72, motions rejected 40, amendments rejected
23, amendments adopted 15, government bills passed 3, initiative bill passed 1.

**Precision, read by eye on a sample of each area:** mostly right. The
abortion, assisted-dying, gender-medicine and surrogacy hits are on point
(the Gezondheidsraad advice on transgender care for minors, the
Vliegenthart bill taking abortion out of the Criminal Code, the Embryowet
amendments). Noise found, and to be tuned before approval:

- `huwelijk*` catches `huwelijksvermogensrecht` (tax on marital property).
- `leerplicht*` (27) is mostly truancy enforcement; the home-education
  items are the minority.
- `Wet openbare manifestaties` (16) is mostly the policing of
  demonstrations: tier 2 at most, arguably out.
- `prenatale screening` matched a neonatal heel-prick letter through its
  dossier title ("Prenatale screening"), the price of dossier-title lending.
- `hospice*` matches hospice funding as well as end-of-life policy.
- `mensenhandel*` (50) also cross-tags the surrogacy amendments, correctly.

Many proposed terms found nothing in titles (`vrijheid van meningsuiting`,
`voltooid leven`, `conversietherapie`, `seksuele voorlichting`,
`Donorwet`). That is expected on titles: they are the words of debates and
documents, which phase 2 reads.

## Proposed Dutch taxonomy (awaiting Chris)

Same 13 areas and keys as the English taxonomy; only the terms differ.
Conventions as in `config/taxonomy-de.yaml`: a trailing `*` is a stem,
matching is anchored at the start of a word (so a Dutch compound must be
listed whole: `abortus*` cannot reach `laatabortus`), all-caps terms are
case-sensitive, `{term, with: [...]}` needs a guard word in the same text.
**(NL)** marks a term that is Netherlands-specific (a Dutch statute, body
or institution); unmarked terms are ordinary Dutch and should serve Flanders
too. The draft used for the measurements is reproduced exactly here.

1. **Abortion.** Tier 1: `abortus*`, `zwangerschapsafbreking*`, `afbreking
   van de zwangerschap`, `afbreking zwangerschap`, `Wet afbreking
   zwangerschap` (NL), `Wafz` (NL), `abortuspil*`, `overtijdbehandeling*`
   (NL), `abortuskliniek*`, `laatabortus*`, `late zwangerschapsafbreking*`
   (NL), `bedenktijd` (NL), `ongeboren leven`, `ongeboren kind*`,
   `levensbescherming`, `Schreeuw om Leven` (NL), `bufferzone*` with
   abortus/kliniek/zwangerschap. Tier 2: `ongeboren*`, `anticonceptie*`,
   `prenatale screening`, `NIPT` (NL), `20-wekenecho` (NL), `pretecho*`,
   `levensbeëindiging bij pasgeborenen` (NL), `Groningen-protocol` (NL),
   `seksuele en reproductieve gezondheid`, `reproductieve rechten`,
   `onbedoelde zwangerschap*`, `ongewenste zwangerschap*`, `doodgeboorte*`,
   `miskraam*`, `vondelingenluik*`, `babyluik*`.
2. **Assisted dying.** Tier 1: `euthanasie*`, `hulp bij zelfdoding`,
   `levensbeëindiging op verzoek`, `voltooid leven` (NL), `Wet toetsing
   levensbeëindiging` (NL), `levenseindekliniek*` (NL), `Expertisecentrum
   Euthanasie` (NL), `Toetsingscommissies Euthanasie` (NL),
   `laatstewilmiddel*` (NL), `Laatste Wil` (NL), `schriftelijke
   wilsverklaring*`, `euthanasieverklaring*`. Tier 2: `levensbeëindiging*`,
   `palliatieve zorg`, `palliatieve sedatie`, `hospice*`,
   `suïcidepreventie`, `zelfdoding*`, `levenseinde*`; `psychisch lijden`
   and `dementie`, each with euthanasie/levenseinde.
3. **Gender medicine and children.** Tier 1: `puberteitsremmer*`,
   `puberteitsremming*`, `genderdysforie*`, `geslachtsincongruentie*`,
   `genderzorg`, `transgenderzorg`, `transzorg`, `geslachtsaanpassende
   behandeling*`, `geslachtsaanpassende operatie*`, `genderbevestigende
   zorg`, `genderbevestigende behandeling*`, `Dutch protocol` (NL),
   `Nederlandse protocol` (NL), `detransitie*`, `genderteam*` (NL),
   `transitie` with kinderen/jongeren/minderjarigen/puberteit. Tier 2:
   `genderidentiteit` and `hormoonbehandeling*` with child guards,
   `transgender jongeren`, `transgenderjongeren`, `Kennis- en Zorgcentrum
   Genderdysforie` (NL).
4. **Conversion practices.** Tier 1: `conversietherapie*`,
   `conversiehandeling*` (NL: the statute's word), `conversiepraktijk*`,
   `homogenezing*`, `Wet verbod op conversiehandelingen`. Tier 2: `pastora*`
   and `gebedsgenezing`, guarded by conversie/verbod/gerichtheid.
5. **Sex-based rights.** Tier 1: `genderidentiteit*`,
   `geslachtsregistratie*`, `Transgenderwet*` (NL), `wijziging
   geslachtsregistratie`, `geslachtsaanduiding*`, `X in het paspoort`, `X in
   paspoort`, `non-binair*`, `transgender*`, `transperso*`, `biologisch
   geslacht`, `Istanbul-verdrag`, `Verdrag van Istanbul`, `femicide*`,
   `genderexpressie*`, `geslachtskenmerken`. Tier 2: `lhbti*`, `lhbtiq*`,
   `LHBTI*`, `LHBTIQ*` (the Dutch acronym; Flanders often writes `holebi`
   or `LGBTQI+`), `regenboogvlag*`, `Regenboogsteden` (NL), `genderneutra*`,
   `vrouwenopvang` and `kleedkamer*` with gender guards, `vrouwensport`,
   `genderquota`, `seksuele gerichtheid`, `seksuele oriëntatie`, `Wet
   gelijke behandeling` (NL).
6. **Parental rights and education.** Tier 1: `seksuele voorlichting`,
   `seksuele vorming`, `relationele en seksuele vorming`,
   `seksualiteitsonderwijs`, `seksuele diversiteit`, `Week van de
   Lentekriebels` (NL), `Lentekriebels` (NL), `Paarse Vrijdag` (NL),
   `vrijheid van onderwijs`, `bijzonder onderwijs` (NL), `huisonderwijs`,
   `thuisonderwijs`, `ouderlijk gezag`, `rechten van ouders`, `ouderrecht*`,
   `artikel 23` with onderwijs/Grondwet/school (NL: the constitutional
   freedom of education). Tier 2: `burgerschapsonderwijs` (NL),
   `burgerschapsopdracht` (NL), `kerndoelen` with seksu/burgerschap/
   diversiteit, `leerplicht*`, `smartphoneverbod*`, `telefoonverbod*`,
   `mobieltjesverbod*`, `sociale media` with child guards,
   `leeftijdsverificatie*`, `leeftijdsgrens voor sociale media`,
   `schermtijd`.
7. **Free speech and online safety.** Tier 1: `vrijheid van meningsuiting`,
   `meningsvrijheid`, `uitingsvrijheid`, `haatzaaien`, `groepsbelediging`,
   `artikel 137c` (NL), `artikel 137d` (NL), `Digital Services Act`, `DSA`,
   `chatcontrole`, `trusted flagger*`, `majesteitsschennis`, `censuur` with
   internet/online/platform/media guards. Tier 2: `desinformatie*`, `online
   haat`, `haatspraak`, `online intimidatie`, `doxing`, `deepfake*`,
   `platformregulering`, `Wet op de inlichtingen- en veiligheidsdiensten`
   (NL), `Wiv` (NL), `gezichtsherkenning*`, `demonstratierecht`, `Wet
   openbare manifestaties` (NL), `persvrijheid`, `vrijheid van vereniging`.
8. **Freedom of religion.** Tier 1: `godsdienstvrijheid`, `vrijheid van
   godsdienst`, `geloofsvrijheid`, `religievrijheid`, `religie- en
   levensbeschouwingsvrijheid`, `vrijheid van religie`,
   `christenvervolging`, `vervolging van christenen`, `christelijke
   minderhe*`, `religieuze minderhe*`, `godslastering`, `kerkasiel`,
   `enkele-feitconstructie` (NL), `enkele feit` (NL: the rule on
   confessional schools' staffing), `Speciaal gezant voor religie` (NL).
   Tier 2: `levensbeschouwing*` with vrijheid/onderwijs/school, `ritueel
   slachten`, `onverdoofd slachten`, `besnijdenis*`, `gezichtsbedekkende
   kleding` (NL statute), `boerkaverbod`, `hoofddoek*` with school/children/
   rechter/politie, `antisemitisme*`, `moslimhaat`, `moslimdiscriminatie`,
   `Jodenhaat`, `kerkgebouw*`, `religieuze organisatie*`,
   `geloofsgemeenschap*`, `kerkgenootschap*`.
9. **Marriage and family.** Tier 1: `kindhuwelijk*`, `huwelijksdwang`,
   `gedwongen huwelijk*`, `polygamie`, `meerouderschap` (NL),
   `meeroudergezag` (NL), `deelgezag` (NL), `Staatscommissie Herijking
   ouderschap` (NL), `gezinsbeleid`, `familiebeleid`,
   `huwelijksgevangenschap`. Tier 2: `huwelijk*` (to be guarded, see
   precision), `kinderbijslag`, `kindgebonden budget` (NL),
   `geboorteverlof`, `ouderschapsverlof`, `adoptie*`, `interlandelijke
   adoptie`, `eenoudergezin*`, `echtscheiding*`, `geregistreerd
   partnerschap`, `gezag over kinderen`, `kinderrechten in de Grondwet`.
10. **Surrogacy and embryology.** Tier 1: `draagmoederschap`,
    `draagmoeder*`, `draagouderschap`, `eiceldonatie`, `embryodonatie`,
    `Embryowet` (NL), `embryo-onderzoek`, `embryo's kweken`, `kweekverbod`
    (NL), `kiembaanmodificatie`, `kiembaan*`, `embryoselectie`,
    `pre-implantatie genetische test*`, `pre-implantatie genetische
    diagnostiek`, `PGT`, `kloneren`, `synthetische embryo*`,
    `embryo-achtige structuren`, `spermadonatie`, `zaaddonor*`,
    `spermadonor*`, `donorkind*`, `afstammingsrecht`, `Wet donorgegevens`
    (NL). Tier 2: `IVF`, `ivf-behandeling*`, `vruchtbaarheidsbehandeling*`,
    `kunstmatige inseminatie`, `eicellen invriezen`, `embryo*`, `stamcel*`,
    `medisch begeleide voortplanting` (the Belgian statute's phrase).
11. **Migration** (collated, hidden). Tier 1: `asielzoeker*`,
    `asielaanvraag*`, `gezinshereniging`, `nareis*` (NL),
    `Asielnoodmaatregelenwet` (NL), `Spreidingswet` (NL),
    `Vreemdelingenwet*` (NL), `tweestatusstelsel` (NL), `statushouder*`
    (NL), `Ter Apel` (NL), `terugkeerbeleid`, `strafbaarstelling van
    illegaliteit` (NL), `veilig land van herkomst`. Tier 2: `asiel*`,
    `migratie*`, `vreemdeling*`, `naturalisatie*`, `COA` (NL),
    `inburgering*`, `verblijfsvergunning*`, `uitzetting*`, `mensensmokkel*`.
12. **Prostitution and trafficking.** Tier 1: `prostitutie*`, `sekswerk*`,
    `Wet regulering sekswerk` (NL), `mensenhandel*`, `seksuele uitbuiting`,
    `pooierboy*`, `loverboy*`, `Noords model`, `Scandinavisch model`,
    `raamprostitutie` (NL), `gedwongen prostitutie`, `strafbaarstelling van
    klanten`, `pooier*`. Tier 2: `bordeel*`, `seksinrichting*`, `escort*`,
    `kinderporno*`, `seksueel kindermisbruik`, `online seksueel misbruik`,
    `Wet seksuele misdrijven` (NL), `seksuele intimidatie`, `afbeeldingen
    van seksueel kindermisbruik`.
13. **Organ donation.** Tier 1: `orgaandonatie*`, `orgaandonor*`, `Donorwet`
    (NL), `donorregistratie`, `Donorregister` (NL), `Wet op de
    orgaandonatie` (NL), `hersendood`, `orgaanhandel`,
    `orgaantransplantatie*`, `orgaanuitname*`, `actief
    donorregistratiesysteem` (NL). Tier 2: `transplantatie*`,
    `weefseldonatie`, `donatie na euthanasie` (NL practice).

Never bare: `huwelijk`, `leven`, `recht`, `kind`, `gezin`, `geslacht`,
`onderwijs`, `vrijheid`, `geweld`, `migratie`, `prostitutie` (the proposed
`exclusions_global`).

**Open questions for the reader:** where the rainbow flag belongs (filed
under area 5 here); whether antisemitism and anti-Muslim hatred belong in
area 8 at tier 2 (39 term hits between them this Kamer); whether `Wet openbare
manifestaties` stays at all; and whether `huwelijk*` needs a guard.

## What is built (phase 1)

| File | What |
|---|---|
| `src/nl_store.py` | `nl_fracties`, `nl_members`, `nl_zaken`, `nl_divisions`, `nl_votes`; the watchlist loader, applied by key. |
| `tools/nl_rollcalls.py` | The collector. Fracties and the 150 current seats, then every vote in the window with every position, its zaak and its dossier; `--reclassify`, `--since`, `--dry-run`, `--taxonomy`. Exit 3 on gaps. |
| `config/watchlist-nl.yaml` | Groundwork draft: 11 dossiers (Wet Abortus is zorg 37027, the beraadtermijn bill 35737, draagmoederschap 36390, Embryowet 36677, 36416, 36417, voltooid leven 35534, conversiehandelingen 36178, geslachtsregistratie 35825, Wet regulering sekswerk 35715, schoolverzuim 36663) and one zaak (the rainbow-flag motion 2026Z21728). Keyed by number, never title. |
| `tests/test_nl_rollcalls.py`, `tests/fixtures/nl/` | 30 tests on real saved responses: roll-call tally against the printed 46-97, the split group, pending positions, the declared mistake, withdrawal, paging, gaps, the window, reclassify, the watchlist, the job wiring. |
| `jobs/nl-weekly.sh`, `ops/launchd/net.citizengo.parlmonitor.nl-weekly.plist`, `.github/workflows/nl-weekly.yml` | The Mini-first weekly, Thursdays 03:00 London on the Mini; GitHub backup Thursdays 03:00 and 05:00 UTC, gated by `mini-check.yml` on `NL_WEEKLY` with 200 minutes' grace (the Australia pattern). |

**First run, 9 October 2026, into a scratch store:** 17 fracties, 150 sitting
members (168 with former members named in roll calls), 4,860 votes from
13 November 2025 to 8 October 2026 on 66 voting days, 86,530 positions, 21
awaiting positions, no gaps, 69 seconds. Later weeks re-read six weeks: two
to four pages.

**Classification today** is the watchlist alone, because the taxonomy is
not approved: 41 votes on our ground. The day `config/taxonomy-nl.yaml`
lands, dispatch the workflow with `reclassify` ticked (or run
`tools/nl_rollcalls.py --reclassify`); nothing needs refetching.

**Not yet built, on purpose:** no edition, no DM, no triage judge. Those are
phase 4, after the terms are approved.

## Phase plan

1. **Votes, positions, members (BUILT).** As above.
2. **Taxonomy (waiting on Chris).** Approve or correct the list above; then
   `docs/keyword-taxonomy-nl.md` is written as the master, a `"nl"` entry
   is added to `MASTERS` in `tools/generate_taxonomy.py`, and
   `config/taxonomy-nl.yaml` is generated. Then reclassify.
3. **The zaak layer independent of votes.** Kamervragen (written and oral),
   government letters, initiative bills and notes, read weekly by
   `GestartOp` and `ApiGewijzigdOp`, classified on titles: this is where
   most of the 393 matched zaken live, and most never reach a vote. Then
   document bodies (the PDFs behind `Document/resource`), matched by
   passage as `src/eudoc.py` does for the EU. And the agenda
   (`Activiteit`) for a week-ahead.
4. **Eerste Kamer.** Handelingen from the KOOP SRU service, plus the
   party-by-party results on eerstekamer.nl bill and motion pages. Votes
   there are by party ("bij zitten en opstaan") with occasional roll calls.
5. **Edition and DM to Chris**, on the US pattern (`tools/us_monitor.py`),
   with a Dutch triage judge and the hidden-migration rule.
6. **Provinces**, last.

## Shared files touched

Kept minimal for the thirteen-branch merge:

- `src/db.py` (+9 lines): the five `nl_*` names in `TABLES`, and
  `nl_store.ensure_schema(conn)` in `init_db`, both directly after the US
  entries.
- `tools/coverage.py` (+17 lines): `"Netherlands weekly"` in `PIPELINES`;
  `nl_members`, `nl_fracties` (7 days, grace 4), `nl_divisions` and
  `nl_zaken` (31, grace 31) in `FEEDS`; `PIPELINE_FEEDS` and
  `AWAITING_FIRST_RUN` entries. All directly after the US entries.
- `.github/workflows/alert.yml` (+1 line): `"Netherlands weekly"`.

Everything else is new and Netherlands-only.

## Waiting on Chris

1. **Approve or correct the Dutch term list** above (ideally with a Dutch
   reader; Belgium's scoping will want the shared terms agreed once). No
   `taxonomy-nl` file exists until then.
2. **Review the watchlist seeds** in `config/watchlist-nl.yaml`: 11 dossiers
   and 1 zaak, all a groundwork draft.
3. **Merge `netherlands` into main** when ready. The Mini runs main only
   (`tools/mini_run.sh`), so nothing is scheduled until then.
4. **Install the plist on the Mini** after the merge
   (`launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/net.citizengo.parlmonitor.nl-weekly.plist`);
   optionally add `HC_NL_WEEKLY` to `~/runner/env` for a heartbeat.
   `MINI_LAST_NL_WEEKLY` is set by the runner itself after its first clean run.
5. **Say what the Dutch DM should carry** when phase 5 comes: votes only,
   or the zaak layer too.
6. **The Eerste Kamer route:** a scrape of eerstekamer.nl HTML, the SRU
   Handelingen, or both.
7. **Someone reads the portal's terms** at
   `opendata.tweedekamer.nl/disclaimer` before the weekly runs unattended
   (the feed names it in every response).

## Decisions of 10 October 2026 (applied at the countries merge)

Recorded in `docs/country-decisions-2026-10-10.md`. Shared: accents fold and non-ASCII letters are word characters in the filter (X3); member positions are stored for every vote (X15); the AI judge stays off (X16).

Applied on the `countries` branch:

- Term list approved (NL1); `config/taxonomy-nl.yaml` (shared with Flanders) generated and loaded for `nl`.
- X5: `nl_store.derived_member_positions()` gives each member their fractie's position on a show of hands, labelled derived.

Later phases and items for Chris (not built at the merge):

- The DM carries votes only (NL3): for the edition phase.
- Phase: the Eerste Kamer via its web pages (NL4).
- Chris reads the open-data disclaimer (NL5) before the weekly runs unattended.
- Member profiles (handover item 3, built 10 October 2026, branch `parity-profiles`): `profiles/nl/` from the store each weekly run (`tools/member_profiles.py nl`, src/member_profiles.py): party, chamber, constituency, every recorded position on a vote on our ground as the edition classifies it, verbatim, with the basis of the party at the vote; no verdicts, no DM. Show-of-hands positions are DERIVED from the fractie vote (X5), labelled; roll calls are recorded per member.
