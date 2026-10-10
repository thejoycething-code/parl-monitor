# Ecuador: scoping the Asamblea Nacional monitor

Probed live on 9 October 2026, from the laptop, with the honest CitizenGO
User-Agent and a second between requests. Every number below was measured,
not estimated. Raw responses are archived under `data/raw/` (ignored by git;
the probe set is in `data/raw/ec-probe/` on the laptop that ran it).

## Decisions already taken (Christopher)

- Own edition, delivered to Christopher alone by Slack DM, like the US.
- Shared taxonomy concept; no existing taxonomy file is edited. The Spanish
  term list is PROPOSED below and generated only once approved.
- National parliament first. Ecuador is unicameral, so that is the whole
  legislature; provincial and cantonal councils are later (listed at the end).
- Mac Mini first, GitHub Actions as backup. No paid services, nothing public.

## The three findings that shape everything

### 1. The votes are open, keyless JSON with every position

The Asamblea's "Sistema de Consulta de Datos Parlamentarios"
(datos.asambleanacional.gob.ec) is an Angular page over a JSON service that
answers without any login, key or cookie. It carries **every plenary vote
with totals, and every member's position on each one**; its periods start
on 31 July 2009, and periods 6 to 8 (May 2021 onwards) were read in full.
Phase 1 is built on it (below).

### 2. The English taxonomy is blind to Spanish, and the draft list works

`config/taxonomy.yaml`, unchanged, over the vote text (agenda item plus the
motion put) of three periods:

| Period | Votes | English list: any area | Draft Spanish list: on our ground (area 11 hidden) | Distinct items |
|---|---|---|---|---|
| 6: May 2021 to May 2023 | 661 | 0 | 30 | 13 |
| 7: Nov 2023 to May 2025 | 745 | 0 | 32 | 19 |
| 8: May 2025 to 6 Oct 2026 (current) | 521 | 0 | **3** | 2 |
| **All** | **1,927** | **0** | **65** | **34** |

**Zero matches in 1,927 votes** for the English list, as in Germany and
Spain. With the draft Spanish list (v0.1 below, 176 tier-1 and 128 tier-2
terms) 65 votes land on our ground, 22 of them at tier 1.

What they are, read by hand:

- **Abortion (area 1), 9 votes.** The six votes of 2022 on the Ley Orgánica
  que Regula la Interrupción Voluntaria del Embarazo para Niñas,
  Adolescentes y Mujeres en caso de Violación (the law the Constitutional
  Court ordered in 2021): the approval 75-41-14 on 17 February 2022, and the
  votes on President Lasso's partial veto in April 2022. Then the total veto of the Código Orgánico de Salud (5 December
  2024) and the archiving, on 28 April 2025, of a bill to register the
  deaths of "concebidos no nacidos".
- **Assisted dying (2), 5 votes**, all on the Ley Orgánica de Cuidados
  Paliativos (second debate October 2024, the partial veto February 2025),
  tier 2: the positive flank. **No vote on euthanasia at all**, although the
  Constitutional Court decriminalised it in February 2024 (case 67-23-IN)
  and told the Asamblea to legislate.
- **Sex-based rights and gender identity (5), 27 votes**, mostly tier 2:
  the identity and civil-data law of December 2023 and its veto (the law
  that governs the identity card, including its sex and gender field),
  gender-violence and femicide
  resolutions, and the July 2021 reform of the criminal code on sexual
  violence. Whether gender-violence law is our ground is the same scope
  question Spain raised.
- **Parental rights and education (6), 5 votes**: the Ley Orgánica de
  Educación Intercultural (LOEI) codification and interpretation, and the
  new Código Orgánico de Protección Integral a Niñas, Niños y Adolescentes
  (12 May 2025).
- **Free speech (7), 10 votes**: the 2022 reform of the Ley Orgánica de
  Comunicación and its veto, and the press-freedom law of July 2022.
- **Religious freedom (8), 2 votes**: the Proyecto de Ley Orgánica de
  Libertad e Igualdad Religiosa, sent to archive at first debate on
  23 April 2025.
- **Trafficking (12), 4 votes; organ donation (13), 3 votes**; migration
  (hidden) 37, 33 of them on area 11 alone.

### 3. The current Asamblea has barely touched our ground

**Three votes in seventeen months**, two on organ-transplant reform and one
on trafficking. The 2025-2029 Asamblea (ADN 67 of 151 seats, Revolución
Ciudadana 61) has legislated on security, the economy and the executive's
agenda, not on life, family or speech. On our ground Ecuador's live channel
is the **Constitutional Court** (abortion for rape, 34-19-IN/21; same-sex
marriage, 11-18-CN/19; euthanasia, 67-23-IN/24), and secondly the
**consulta popular** (7 plenary votes on referendum matters in periods 7
and 8).

**Recommendation: an edition is worth having but will be quiet.** The data
is excellent and the Asamblea is a real, contested legislature (a
government majority, a strong opposition, recorded votes on everything), so
nothing is lost by monitoring it, and a vote on euthanasia or the children's
code would be caught the week it happens with every member's position. But
a weekly Ecuador edition built on plenary votes alone would be empty most
weeks. The recommended shape is a fortnightly or monthly DM, with the
Constitutional Court added in phase 3.

## What Ecuador publishes

### The datos parlamentarios service: WORKS TODAY, open, no key

Base `https://datos.asambleanacional.gob.ec/ecurul/`. Found by reading the
page's own JavaScript bundle; the endpoints are the ones the public page
calls.

| Endpoint | What | Measured |
|---|---|---|
| `reports/period?idPeriod=` | the legislative periods | 6 periods: 2 (2009-2013), 4, 5, 6, 7, 8 (2025-05-14 to 2029-05-13). There is no period for 17 May to 17 November 2023 (the muerte cruzada dissolution) |
| `reports/votingList?datePeriod=&dateIn=YYYY-MM-DD&dateOut=YYYY-MM-DD&sessionNumber=&theme=&proposal=` | every plenary vote in a window, with the session number, the agenda item (`theme`), the motion put (`proposalType`), the four totals and the `votingId` | period 8: 521 votes, 457 KB, 7.0 s; period 7: 745, 687 KB, 8.0 s; period 6: 661, 611 KB, **35 s**. `datePeriod` may be blank |
| `assemblyman/votingDetail?idVoting=N` | every position on one vote: `firstName`, `lastname`, `description` (SI / NO / ABSTENCION / BLANCO) and `territorial` | about 15 KB, 1.0 to 4.2 s (median 1.1 s over 12 samples; the full backfill below averaged about 3.5 s a request including our own second) |
| `assemblyman/assemblymemberlist` | the member register | 798 names since 2009, 85 KB, each with the service's own id |
| `themes/typeThemes` | the agenda-item types | 30-odd: Informe para Primer/Segundo Debate, Objeción, Juicio Político, Resolución, ... |

Quirks, all handled by the collector:

- **HTTP 200 with `[]`** for a vote number that does not exist and for a
  window with no votes. Emptiness is checked, never the status.
- **Only those who voted are listed.** The detail's rows equal yes + no +
  blank + abstain on every one of the 521 votes of period 8; absent members
  are not in it.
- **No member id, no party, no bill number on a vote.** Positions carry the
  name only. The register orders its two name fields the other way round
  from the vote detail (surnames in `firstName`), and does not hold every
  voter: of 324 distinct names voting in period 8, 171 are in the register
  (alternates who sat for a day are missing). Names are therefore stored as
  printed, surnames first, with an accent-folded token key to join on.
- **The `theme` field can be stale.** Three votes of 25 January 2024 on the
  identity-law veto carry the theme "Himno Nacional de la República del
  Ecuador"; the subject is only in the motion text. Both fields are stored
  and both are classified.
- Times are served in UTC; the collector stores the Ecuador date (UTC-5, no
  daylight saving).
- The same Angular bundle embeds an application username and password for
  another back end (`apiapp.asambleanacional.gob.ec`, used only to generate
  a vote PDF). **Not used and not needed.**

### Members and parties: the plenary page, WORKS TODAY

`https://www.asambleanacional.gob.ec/es/pleno-asambleistas` (566 KB of
Drupal HTML) shows the sitting 151 with their constituency; the party is
legible only from each member's avatar image: `adn` 67,
`revolucion-ciudadana` 61, `pachakutik` 9, `psc` 4, and three bare list
numbers the page does not label (`15` 3, `16` 3, `26` 4: the page's party
menu lists "Independiente" and "Movimientos Provinciales" beside the four
parties, so these are likely those). The party menu loads each party's
members by a script call not exposed in the page; not pursued. Gender split
on the page: 68 women, 83 men.

**Joining roster to votes**: 139 of the 151 roster names match a voter's name
exactly on the folded token set; the 12 that do not are short forms
("Camila León", "Viviana Veloz R.") and need a hand crosswalk. Party is the
party now, not at the vote. A per-vote party needs that crosswalk plus the
roster history, which the weekly builds from here on.

### Bills: the old portal is frozen, the new one needs a login (BLOCKER)

- `https://leyes.asambleanacional.gob.ec/` (JSF/PrimeFaces, "Consulta de
  Propuestas y Proyectos de Ley"): open, workable with a ViewState POST,
  **but frozen**: 2,740 bills, the newest presented on **2 August 2024**. A
  search over 14 May 2025 to 8 October 2026 returns 0; over 2024 it returns
  263. Pages cap at 15 rows (100 is refused with
  `IllegalArgumentException: Unsupported rows per page value: 100`). Each
  bill carries a code and a trámite number ("Cod. AN-2024-3009 / 453797"),
  proponent, committee and state.
- `https://proyectosdeley.asambleanacional.gob.ec/report` (Angular, the
  successor): its service `pplessservice2/` answers **403 to every
  unauthenticated request**. The public page obtains a token by logging in
  with a username and password written into its own JavaScript bundle.
  **I did not use them**: authenticating with credentials, even published
  ones, is a decision for Christopher, not for an agent (compare the
  Bundestag key read from its public OpenAPI spec, which Christopher
  approved for Germany).
- So **no vote can be joined to a bill number today**, and the watchlist is
  keyed by division key (`ec-<votingId>`), never by title.

### Also measured

- `datosabiertos.gob.ec` (the national open-data portal) and its CKAN API
  answer **403** to our User-Agent on every path tried. Not pursued (no
  User-Agent spoofing).
- "Votaciones del Pleno" on the Asamblea site redirects to a Nextcloud
  share (colabora.asambleanacional.gob.ec, 329.2 MB of vote PDFs): redundant
  with the JSON service.
- Committee votes ("Votaciones de las Comisiones Permanentes"), the weekly
  agenda (a PDF linked from the home page: AGENDA-PARLAMENTARIA-...pdf), the
  news RSS feed (`/es/rss.xml`, 21 KB) and bill-presentation news
  (`/es/noticias/presentacion-proyectos-de-ley`): open; not built.
- Constitutional Court: `www.corteconstitucional.gob.ec` (200),
  `esacc.corteconstitucional.gob.ec` (the case system, 200, a Java
  application) and `buscador.corteconstitucional.gob.ec` (an Angular search
  page). Not probed further; phase 3.
- Robots: `www.asambleanacional.gob.ec/robots.txt` asks for `Crawl-delay: 1`
  and disallows only Drupal internals; the datos host serves its page shell
  for robots.txt (no rules). The collector keeps one request a second.
- No CAPTCHA or bot challenge anywhere.

## Phase 1: built, 9 October 2026

`tools/ec_rollcalls.py` into `ec_divisions`, `ec_votes`, `ec_members` and
`ec_roster` (schema in `src/ec_store.py`, declared in `db.TABLES`). Live run
into a scratch database (not the store), the whole of period 8:

| | Read | Notes |
|---|---|---|
| Plenary votes, 14 May 2025 to 6 October 2026 | 521 | session, agenda item, motion, four totals |
| Vote details | 521 | two failed on a TLS handshake timeout and were read by the next run |
| Positions | 73,586 | on every one of the 521, the rows equal the totals |
| Distinct voter names | 324 | 171 of them in the register |
| Member register | 798 | every name since 2009 |
| Sitting roster | 151 | 139 join a voter's name exactly |

19 minutes 34 seconds for 514 details in the first pass, about 2.3 seconds
a request including our own second; 2.2 MB of raw archive. Reclassified
offline with the draft list, the store holds 3 votes on our ground, the
figure in the table above.

- **Keys**: a division is `ec-<votingId>` (`ec-1004966`). Never a title.
- **Areas stay NULL until the Spanish taxonomy exists.** NULL is
  "unclassified", `[]` is "classified, nothing found". Only
  `config/watchlist-ec.yaml`, applied by division key, lends areas now (nine
  entries: the six 2022 abortion-law votes, the unborn-death-registration
  bill, the religious-freedom bill, the children's code). `--taxonomy
  <file>` classifies with a draft; `--reclassify` re-derives offline.
- **Re-reads**: each run lists the current period's votes from the last
  stored date less a fortnight (the first run lists the whole period), then
  reads every detail not yet stored. A detail whose row count does not equal
  the totals is stored and recorded as a gap; an empty detail is a gap and
  is retried next run. `--period 7` / `--period 6` backfill older periods
  (745 and 661 details, about 45 and 40 minutes) as a one-off.
- **Exit codes**: 0 clean, 3 stored what it could and recorded gaps (the job
  still publishes), 1 otherwise.

**The weekly** (`jobs/ec-weekly.sh`, shared by both runners): Saturdays
15:30 London on the Mac Mini (`ops/launchd/net.citizengo.parlmonitor.ec-weekly.plist`);
`.github/workflows/ec-weekly.yml` at 15:30 and 19:30 UTC (half an hour later than first built; France and Portugal hold 15:00 and 19:00) is the backup,
gated by `mini-check` with job `EC_WEEKLY` (grace 320 minutes: the Mini's
summer run stamps 14:00 UTC, five hours before the retry slot). The job
publishes the raw archive, then the store (`raw_state.py --push` before
`db_state.py --push`, as `tests/test_raw_state` requires). **It runs only
once merged to main.** The first run is the backfill of period 8 (about 520
details, roughly half an hour at the measured rate); the 45-minute budget
stops a slow run cleanly and the next resumes.

Tests: `tests/test_ec_rollcalls.py`, 34 tests on real responses saved on
9 October (`tests/fixtures/ec/`, 176 KB): periods, two vote lists (September
2026; the abortion-law day of 17 February 2022), two details, the register
and the roster page.

## Proposed Spanish taxonomy for Ecuador (v0.1, FOR APPROVAL)

Drafted by Claude on 9 October 2026 and measured against the 1,927 votes
above, **not yet read by an Ecuadorian campaigner**. It starts from the
Spain branch's draft (`docs/spain-scope.md` on branch `spain`) and keeps its
shared vocabulary, drops what is Spanish law, and adds Ecuador's legal
names. Written in the generator's format: once approved it lifts into
`docs/keyword-taxonomy-<lang>.md` and `tools/generate_taxonomy.py` produces
the yaml (that needs one line in `MASTERS`, a shared edit not made).

**For the merge with Spain, Mexico, Colombia, Peru and the rest**: each area
has an `Ecuador only` line. Everything else is ordinary Spanish legal and
political vocabulary, almost all of it already in Spain's draft. Terms new
here that are probably shared across Latin America: `"embarazo en caso de
violación"` (as a concept), `"matrimonio igualitario"`, `"unión de hecho"`,
`"movilidad humana"`, `"niñez trans"`, `"enfoque de género"`, `"desde la
concepción"` (the American Convention's wording, art. 4.1), `"educación de
la sexualidad"`, `"licencia de maternidad/paternidad"` (Spain says
`permiso`).

Matching traps, beyond Spain's (plural and gender endings, accents, short
words never alone):

- **`trata` is a verb.** "se trata de" is everywhere (26 votes contain
  "trata", none about trafficking); only `"trata de personas"` and its
  siblings are terms, and `trata` joins the global exclusions.
- **`objeción` is procedure.** 105 votes mention an "Objeción Parcial" or
  "Objeción Total", the President's veto; only `"objeción de conciencia"` is
  a term.
- **Court case numbers are terms** (`"34-19-IN"`, `"67-23-IN"`,
  `"11-18-CN"`, `"10-18-CN"`): the Asamblea cites the sentence when it
  legislates on its order.
- **The stale-theme quirk** means the motion text must always be matched
  too; the collector does.

### 1. Abortion {#1_abortion}

- **Tier 1:** aborto*; abortiv*; "interrupción voluntaria del embarazo"; "interrupción legal del embarazo"; "interrupción del embarazo"; IVE; ILE; "embarazo en caso de violación"; "embarazo producto de violación"; "aborto por violación"; "aborto no punible"; objetor* [with: aborto, interrupción, embarazo, sanitari]; "píldora abortiva"; mifepristona; misoprostol; provida; "pro vida"; "no nacido*"; "concebido* no nacido*"; nasciturus; "desde la concepción"; "derecho a la vida" [with: concebido, nacer, embarazo, aborto, gestación, concepción]; "34-19-IN"
- **Tier 2:** "salud sexual y reproductiva"; "derechos sexuales y reproductivos"; "salud reproductiva"; anticoncepci*; anticonceptiv*; "píldora del día después"; "anticoncepción de emergencia"; "diagnóstico prenatal"; "vida prenatal"; "muerte perinatal"; "maternidad vulnerable"; "mujeres embarazadas" [with: ayuda, apoyo, vulnerab]; "embarazo adolescente"; "embarazo infantil"; "embarazo en niñas"; "Código Orgánico de Salud"; "artículo 150" [with: "Código Orgánico Integral Penal", COIP, aborto]
- **Ecuador only:** "embarazo en caso de violación"; "34-19-IN"; "Código Orgánico de Salud"; "artículo 150"
- **Notes:** The 2022 law's title says "Interrupción Voluntaria del Embarazo ... en caso de Violación"; its veto stage drops "Voluntaria", hence both phrases. COIP art. 150 is the non-punishable abortion article the Court widened in 34-19-IN/21. The Código Orgánico de Salud (vetoed in 2020 and again in December 2024) carried emergency-care and reproductive-health clauses. `"concebidos no nacidos"` joined on measurement (the 2025 death-registration bill). Art. 45 of the Constitution protects life "desde la concepción". MEASURED: 9 votes (6 in 2022, 3 in 2024-2025).

### 2. Assisted dying and end of life {#2_assisted_dying}

- **Tier 1:** eutanasia*; eutanási*; "suicidio asistido"; "suicidio médicamente asistido"; "ayuda para morir"; "muerte digna"; "morir dignamente"; "muerte voluntaria"; "67-23-IN"
- **Tier 2:** "cuidados paliativos"; paliativ*; "sedación paliativa"; "testamento vital"; "voluntades anticipadas"; "directivas anticipadas"; "final de la vida"; "fin de la vida"; "prevención del suicidio"
- **Ecuador only:** "67-23-IN"; "directivas anticipadas"
- **Notes:** 67-23-IN/24 (the Paola Roldán case, February 2024) decriminalised euthanasia and ordered a law; no plenary vote has followed. MEASURED: 5 votes, all the palliative-care law, tier 2.

### 3. Gender medicine and children {#3_gender_medicine_children}

- **Tier 1:** "bloqueador* de la pubertad"; "bloqueador* puberal*"; "bloqueo puberal"; "hormonación cruzada"; "hormonas cruzadas"; "disforia de género"; "incongruencia de género"; "menores trans"; "infancia trans"; "niños trans"; "niñas trans"; "niñez trans"; "adolescentes trans"; "reasignación de sexo"; "reasignación sexual"; "cirugía de reasignación"; detransici*; destransici*
- **Tier 2:** "transición de género" [with: menor, niño, niña, adolescente, infancia, niñez]; "tratamiento hormonal" [with: menor, niño, niña, adolescente, género, trans]; "afirmación de género"; "identidad de género" [with: menor, niño, niña, adolescente, infancia, niñez, escuela, colegio, "unidad educativa"]
- **Ecuador only:** none (`niñez trans` is Andean usage, probably shared)
- **Notes:** MEASURED: no vote.

### 4. Conversion practices {#4_conversion_practices}

- **Tier 1:** "terapia* de conversión"; "terapia* de aversión"; "prácticas de conversión"; "terapias de reorientación"; deshomosexualiz*; "clínicas de deshomosexualización"; "centros de deshomosexualización"
- **Tier 2:** "acompañamiento espiritual" [with: conversión, orientación, identidad]; "asesoramiento" [with: conversión, "orientación sexual", "identidad de género"]
- **Ecuador only:** deshomosexualiz*; "clínicas de deshomosexualización"; "centros de deshomosexualización"
- **Notes:** "Clínicas de deshomosexualización" is the Ecuadorian name for the private centres the criminal code targets. MEASURED: no vote.

### 5. Sex-based rights and gender identity {#5_sex_based_rights}

- **Tier 1:** "autodeterminación de género"; "autodeterminación de sexo"; "autodeterminación del sexo"; "autodeterminación de la identidad"; "rectificación registral"; "cambio de sexo" [with: cédula, registro, registral, identidad]; "sexo por género"; "género en la cédula"; "campo sexo"; "identidad de género"; "expresión de género"; "ideología de género"; "personas trans"; transexual*; transgénero*; "no binari*"; LGTBI*; LGBTI*; LGTB; LGBT; "diversidad sexo-genérica"; "Convenio de Estambul"
- **Tier 2:** "perspectiva de género" [with: educación, escuela, menores, currículo, infancia, niñez]; "enfoque de género" [with: educación, escuela, currículo, malla, niñez]; "violencia de género"; "violencia contra las mujeres"; "violencia machista"; "violencia sexual"; "Ley Orgánica Integral para Prevenir y Erradicar la Violencia contra las Mujeres"; feminicidio*; femicidio*; "categoría femenina"; "deporte femenino" [with: trans, sexo, identidad]; "lenguaje inclusivo"; "orientación sexual"; "diversidad sexual"; "Ley Orgánica de Gestión de la Identidad y Datos Civiles"; "Gestión de Identidad y Datos Civiles"
- **Ecuador only:** "sexo por género"; "género en la cédula"; "campo sexo"; "diversidad sexo-genérica"; "Ley Orgánica Integral para Prevenir y Erradicar la Violencia contra las Mujeres"; "Ley Orgánica de Gestión de la Identidad y Datos Civiles"; "Gestión de Identidad y Datos Civiles"
- **Notes:** Ecuador's fight is over the identity card: whether "sexo" may be replaced by "género" (the 2016 identity law and its 2023 reform). The 2023 reform's title, "Gestión de Identidad y Datos Civiles", is tier 2 because the law is mostly administrative. Gender-violence terms are tier 2 and a scope question (see Waiting on Chris): 16 of this area's 27 votes match on nothing else. MEASURED: 27 votes.

### 6. Parental rights and education {#6_parental_rights_education}

- **Tier 1:** "derecho de los padres"; "derechos de los padres"; "derecho preferente de los padres"; "derecho de las madres y padres"; "libertad de enseñanza"; "libertad educativa"; "educación afectivo-sexual"; "educación afectivo sexual"; "educación sexual integral"; "educación sexual"; "educación de la sexualidad"; homeschooling; "educación en casa"; "educación en el hogar"; "educación diferenciada"; "entorno* digital*" [with: menores, infancia, niños, niñas, adolescentes]
- **Tier 2:** "consentimiento parental"; "consentimiento de los padres"; "patria potestad"; "corresponsabilidad parental"; "Ley Orgánica de Educación Intercultural"; LOEI; "Código de la Niñez y Adolescencia"; "Código Orgánico de Protección Integral a Niñas, Niños y Adolescentes"; "Código Orgánico de la Niñez"; "educación particular"; "educación fiscomisional"; "unidades educativas fiscomisionales"; "redes sociales" [with: menores, edad, niños, niñas, adolescentes, escuela]; "teléfono* móvil*" [with: aula, colegio, "unidades educativas", escuela, menores]; "control parental"; adoctrinamiento
- **Ecuador only:** "Ley Orgánica de Educación Intercultural"; LOEI; "Código de la Niñez y Adolescencia"; "Código Orgánico de Protección Integral a Niñas, Niños y Adolescentes"; "Código Orgánico de la Niñez"; "educación fiscomisional"; "unidades educativas fiscomisionales"
- **Notes:** The LOEI is the schools law (sex education, parents' role, faith schools); `fiscomisional` schools are the publicly funded, mostly Catholic, ones. The children's code (COPINNA, second debate 12 May 2025) replaces the 2003 Código de la Niñez y Adolescencia. Both are tier 2 because they carry far more than our ground. MEASURED: 5 votes.

### 7. Free speech, privacy and civil liberties {#7_free_speech_online_safety}

- **Tier 1:** "libertad de expresión"; "delito* de odio"; "discurso* de odio"; "incitación al odio"; "Ley Orgánica de Comunicación"; "linchamiento mediático"; pornograf*; "verificación de edad"
- **Tier 2:** desinformaci*; "noticias falsas"; "libertad de prensa"; "libertad de información"; censura [with: expresión, redes, prensa, internet, libros]; "Superintendencia de la Información y Comunicación"; Supercom; "Consejo de Regulación"; "Ley Orgánica de Protección de Datos Personales"; "protección de datos personales"; "cifrado de extremo a extremo"; "reconocimiento facial"; islamofobia
- **Ecuador only:** "Ley Orgánica de Comunicación"; "linchamiento mediático"; "Superintendencia de la Información y Comunicación"; Supercom; "Ley Orgánica de Protección de Datos Personales"
- **Notes:** The Ley Orgánica de Comunicación (2013, reformed 2019 and 2022) is Ecuador's central free-speech law; "linchamiento mediático" was its most contested offence. MEASURED: 10 votes (two of them a financial-services bill that amends the LOC in passing, which triage should drop).

### 8. Freedom of religion or belief {#8_freedom_of_religion}

- **Tier 1:** "libertad religiosa"; "libertad e igualdad religiosa"; "Ley Orgánica de Libertad e Igualdad Religiosa"; "libertad de culto*"; "libertad de conciencia"; "objeción de conciencia"; "sentimientos religiosos"; blasfemia*; "Santa Sede"; "Modus Vivendi"; "Ley de Cultos"; cristianofobia; "persecución de cristianos"; "cristianos perseguidos"; "minorías religiosas"; "minoría religiosa"; "asistencia religiosa"; capellan*
- **Tier 2:** "Iglesia católica"; "Conferencia Episcopal"; "lugares de culto"; "confesiones religiosas"; "entidades religiosas"; "organizaciones religiosas"; "Estado laico"; laicidad; "educación religiosa"; "enseñanza de la religión"; "símbolos religiosos"; crucifijo*
- **Ecuador only:** "Ley Orgánica de Libertad e Igualdad Religiosa"; "libertad e igualdad religiosa"; "Modus Vivendi"; "Ley de Cultos"
- **Notes:** The 1937 Modus Vivendi with the Holy See and the Ley de Cultos of the same year are the old frame for religious bodies; the 2025 bill was archived at first debate. MEASURED: 2 votes.

### 9. Marriage and family {#9_marriage_family}

- **Tier 1:** "matrimonio entre personas del mismo sexo"; "matrimonio igualitario"; "matrimonio homosexual"; "diversidad familiar"; "protección a la familia"; "protección de la familia"; "fortalecimiento de la familia"; "matrimonio infantil"; poligamia; "perspectiva de familia"; "11-18-CN"; "10-18-CN"
- **Tier 2:** natalidad; "invierno demográfico"; "licencia de maternidad"; "licencia de paternidad"; "licencia por paternidad"; "licencia por maternidad"; "tenencia compartida"; "custodia compartida"; divorcio*; "unión de hecho"; "uniones de hecho"; adopción [with: menores, familia, parejas]; "conciliación de la vida familiar"; "corresponsabilidad familiar"
- **Ecuador only:** "11-18-CN"; "10-18-CN"; "tenencia compartida"
- **Notes:** Same-sex marriage came by the Court (11-18-CN/19 and 10-18-CN/19), not by the Asamblea; the Civil Code's man-and-woman definition was never amended. "Unión de hecho" is open to same-sex couples under art. 68 of the Constitution. MEASURED: no vote.

### 10. Surrogacy and embryology {#10_surrogacy_embryology}

- **Tier 1:** "gestación subrogada"; "gestación por sustitución"; "maternidad subrogada"; "vientre* de alquiler"; "útero* subrogado*"; "reproducción asistida"; "reproducción humana asistida"; embrion*; embrión; "fecundación in vitro"; "diagnóstico genético preimplantacional"; clonación; "edición genética"; "células madre embrionarias"
- **Tier 2:** "donación de óvulos"; "donación de gametos"; "donación de semen"; FIV; "investigación biomédica"; filiación [with: gestación, subrogada, sustitución]; "preservación de la fertilidad"; "congelación de óvulos"
- **Ecuador only:** none
- **Notes:** No plenary item on assisted reproduction or surrogacy appears in the three periods measured. MEASURED: no vote.

### 11. Migration {#11_migration}

- **Tier 1:** inmigración; inmigrante*; migrante*; "movilidad humana"; "Ley Orgánica de Movilidad Humana"; "protección internacional"; asilo; refugiad*; "regularización migratoria"; "regularización extraordinaria"; "menores no acompañados"; deportaci*
- **Tier 2:** migración; migratori*; "naturalización" [with: extranjer, carta]
- **Ecuador only:** "Ley Orgánica de Movilidad Humana"
- **Notes:** Collated, never campaigned, hidden on every surface (`HIDDEN_AREAS = (11,)`). "Movilidad humana" is the Constitution's own word for migration. MEASURED: 37 votes on area 11 alone.

### 12. Prostitution, trafficking and sexual exploitation {#12_prostitution}

- **Tier 1:** prostituci*; proxenetismo; proxeneta*; "trata de seres humanos"; "trata de personas"; "trata con fines de explotación sexual"; "explotación sexual"; "abolición de la prostitución"; "compra de sexo"; "matrimonio* forzado*"; "unión* forzada*"
- **Tier 2:** "trabajo sexual"; "trabajadoras sexuales"; "trabajadores sexuales"; prostíbulo*; "abuso sexual infantil"; "explotación sexual infantil"; "violencia sexual" [with: niñas, niños, adolescentes, escuela, "unidad educativa", "sistema educativo"]; "material de abuso sexual infantil"; "pornografía infantil"
- **Ecuador only:** none
- **Notes:** "Unión forzada" sits beside forced marriage because informal unions are the commoner form of child marriage in the region. MEASURED: 4 votes (the 2023 trafficking law, a commemorative resolution of December 2022, and the first debate of its reform in December 2025).

### 13. Organ donation {#13_organ_donation}

- **Tier 1:** "donación de órganos"; "trasplante* de órganos"; "Donación y Trasplante de Órganos"; "tráfico de órganos"; "turismo de trasplantes"; INDOT
- **Tier 2:** trasplante*; "donante* de órganos"; "muerte encefálica"; "donante presunto"; "donación presunta"
- **Ecuador only:** "Donación y Trasplante de Órganos"; INDOT; "donante presunto"
- **Notes:** INDOT is the national donation and transplant institute; the 2011 organ law made every adult a presumed donor. MEASURED: 3 votes (the 2025 reform, first and second debate).

### Global exclusions (advisory)

vida; familia; género; sexo; menores; matrimonio; libertad; religión;
educación; odio; mujer; igualdad; trans; trata. These bare words never
become terms on their own.

## Proposed phasing

1. **Phase 1 (built, this branch).** Plenary votes with every position,
   member register, sitting roster with party; Mini-first weekly;
   unclassified until the taxonomy is approved; nine watched votes.
2. **Phase 1b (after approval).** Generate the taxonomy, dispatch
   `ec-weekly` with "reclassify"; backfill periods 7 and 6 once
   (`--period 7`, `--period 6`), so the 2022 abortion-law and 2024
   palliative-care votes sit in the store with positions; the 13-name roster
   crosswalk, so positions carry party.
3. **Phase 2 (needs Christopher's decision on the bill system).** Bills:
   either the proyectosdeley service (needs a login) or bill-presentation
   news plus the frozen portal for pre-August 2024. Committee votes and the
   weekly agenda PDF.
4. **Phase 3.** The Constitutional Court (sentences and pending cases on our
   ground), then the edition and DM (`tools/ec_monitor.py`, the
   `us_monitor.py` pattern), fortnightly or monthly rather than weekly.
5. **Later.** Provincial and cantonal councils (below).

## Regions (later, not probed)

Twenty-four provinces, each with a Consejo Provincial, and 221 cantons with
Concejos Municipales (the Quito Metropolitan Council among them; one
plenary vote of 14 October 2025 asked it to follow up its own plans). The
Galápagos special regime has its own Consejo de Gobierno. None was probed;
municipal ordinances are the only regional law-making, and none of it is
national in reach.

## Shared files touched (for the merge of the country branches)

- `src/db.py`: four `ec_*` names added to `TABLES`, and
  `ec_store.ensure_schema` called from `init_db` (8 lines).
- `tools/coverage.py`: `Ecuador weekly` in `PIPELINES`, `PIPELINE_FEEDS` and
  `AWAITING_FIRST_RUN`; `ec_members`, `ec_roster`, `ec_divisions` (7 + 4
  days each) in `FEEDS` (13 lines).
- `.github/workflows/alert.yml`: `"Ecuador weekly"` added to the watched
  workflows (1 line).

Not touched: any taxonomy file, `tools/generate_taxonomy.py`,
`tools/mini_run.sh`, `.github/workflows/mini-check.yml`, `src/http.py`. New
files only otherwise: `src/ec_store.py`, `tools/ec_rollcalls.py`,
`config/watchlist-ec.yaml`, `jobs/ec-weekly.sh`,
`ops/launchd/net.citizengo.parlmonitor.ec-weekly.plist`,
`.github/workflows/ec-weekly.yml`, `tests/test_ec_rollcalls.py`,
`tests/fixtures/ec/`, this document.

## Waiting on Chris

1. **Approve or amend the Spanish terms above**, ideally after a read by
   CitizenGO's Ecuador or Andean team. Then decide the file: one shared
   Spanish file with Spain and the other Latin American countries (with the
   "only" lines as provenance), or a `taxonomy-ec.yaml` of its own (what
   the collector reads today).
2. **Scope questions the corpus raised:**
   - **Gender-violence law** (Ley Orgánica Integral para Prevenir y
     Erradicar la Violencia contra las Mujeres, femicide resolutions): 16 of
     27 area-5 votes match on nothing else. In or out? (Spain asks the same.)
   - **Palliative care** at tier 2 in area 2: the only end-of-life votes
     Ecuador has had. Keep?
   - **The children's code** (COPINNA) and the LOEI at tier 2 in area 6:
     right, or tier 1 given that parental authority and sex education live
     in them?
   - **Contraception** in area 1 at tier 2, following the US decision: the
     same for Ecuador?
3. **The bill system.** The successor bill portal answers only with a token
   its public page obtains by logging in with a username and password
   embedded in its own JavaScript. Options: (a) authorise using them, as the
   published Bundestag key was authorised for Germany; (b) write to the
   Asamblea (Unidad Técnica Legislativa or Parlamento Abierto) asking for
   open access; (c) go without bill numbers and key on votes, as now.
4. **Cadence.** Weekly collection is built; for the DM, weekly, fortnightly
   or monthly? Three votes on our ground in seventeen months argues for
   monthly, with an immediate alert when a watched or tier-1 vote lands.
5. **The Constitutional Court** as phase 3: yes or no? On our ground it has
   moved Ecuador more than the Asamblea has in a decade.
6. **Merge and install.** Merge `ecuador` to main when ready (GitHub
   schedules only from main); copy the plist to the Mini and bootstrap it.
   No secret or key is needed. The first run backfills period 8 (about 520
   requests, half an hour, on the Mini).

## Decisions of 10 October 2026 (applied at the countries merge)

Recorded in `docs/country-decisions-2026-10-10.md`. Shared: accents fold and non-ASCII letters are word characters in the filter (X3); member positions are stored for every vote (X15); the AI judge stays off (X16).

Applied on the `countries` branch:

- Term list approved (EC1, EC2 palliative care area 2, EC3 children's code and LOEI tier 2) and merged into the shared `config/taxonomy-es.yaml` (`docs/keyword-taxonomy-es.md`), loaded for this country's code; the collector now reads taxonomy-es, not a separate taxonomy-ec.
- Weekly moved to Saturday 15:30/19:30 UTC (France and Portugal hold 15:00/19:00).

Later phases and items for Chris (not built at the merge):

- The bill portal's embedded login stays unused (EC4).

## Parity work, set B (10 October 2026, branch `parity-phases-b`)

- **X8, built:** `tools/ec_courts.py`, a step in `ec-weekly`: the Corte
  Constitucional's own WordPress API (www.corteconstitucional.gob.ec,
  `/wp-json/wp/v2/posts`, keyless, robots.txt disallows nothing), three
  categories: Novedades jurisprudenciales (one plain-language summary per
  judgment, 1,182), Boletines comunicacionales (192) and Comunicados (127).
  The Actividades jurisdiccionales category (session agendas, lists of case
  numbers) is not read. Into `ec_rulings`, keyed on the case number
  ('ec:34-19-IN/21') or the post id, classified on the Court's summary,
  never the judgment (esacc's PDF). Measured live: 555 posts since January
  2024, 58 on our ground after a court guard on "causales" (it matched
  fourteen rulings on grounds for annulling arbitral awards and none on
  abortion; the same guard belongs in docs/keyword-taxonomy-es.md at the
  next term-list round). The weekly reads from 30 days before the newest
  held; the hand-run `jobs/latam-courts-backfill.sh` reads from 2019.
