# Honduras: scoping the Congreso Nacional monitor

Probed live on 9 October 2026 from the laptop, with the honest CitizenGO
User-Agent, at one request every 1.2 seconds. Every number below was
measured, not estimated; the probes are reproducible from
`tools/hn_rollcalls.py` and the notes here, and the raw responses (about
550 files, 9 MB: API replies, the site's JavaScript, listing pages) are
archived under `data/raw/2026-10-09/` as `hn-rollcalls_*` and `hn-probe_*`.

## Decisions already taken (Christopher)

- Own edition, delivered to Christopher alone by Slack DM, as for the US.
- Shared taxonomy concept; no taxonomy file is generated or edited here.
  The Spanish term list below is a PROPOSAL for approval.
- National parliament first. Honduras has no regional legislatures (see
  the end), so "first" is also "only".
- Mac Mini first, GitHub Actions as the backup. No paid services, no
  public posting.

## The three findings that shape everything

### 1. There are no recorded votes, and none are coming soon

The Congreso Nacional runs a vendor system ("matizzo",
`api-cnh.matizzo.com`, proxied as `congresonacional.hn/api/matizzo/*`)
that is plainly built to hold votes: every agenda item has a `resultado`
field and the dashboard has a `totalVotaciones` counter, split into
approved, rejected and in progress, month by month. On 9 October 2026:

- `resultado` was **null on all 1,488 agenda items** of the 359 sessions
  read (every session the system lists but one, whose agenda the vendor
  failed to serve);
- `totalVotaciones` was **0** for 2026, in every month and every committee,
  against 361 sessions recorded.

Plenary votes reach the public as totals in the press releases: of 1,219
releases this legislature, 66 say "por unanimidad", 97 give a count
("con 90 votos"), and 7 mention the electronic voting board. Per-member
positions are not published anywhere we could find: not in the API, not
on the site, not in the press releases. **There is no 5CA layer for Honduras and no
recorded-vote scorecard.** The edition, if built, is a record of what was
tabled, scheduled, reported and approved, not of who voted how.

### 2. The English taxonomy is blind to Spanish, again

`config/taxonomy.yaml` matched **1 of 1,488 agenda items and 1 of 1,219
press releases** of the current legislature (the press-release match was
area 7, on an English loan word). With the draft Spanish list proposed
below:

| Corpus | Rows | On our ground (area 11 hidden) | Tier 1 | English list |
|---|---|---|---|---|
| Agenda items, all sessions, Jan 2025 to Sep 2026 | 1,488 | **27** (22 distinct files or motions) | 10 | 1 |
| of which plenary | 641 | 17 | 6 | 0 |
| Press releases since 25 January 2026 | 1,219 | **107** | 49 | 1 |
| the same, titles only | 1,219 | 35 | 14 | 0 |
| press releases, last 12 weeks | 455 | 32 | | |
| "Recent expedientes" (10 per stage) | 40 | 1 | 0 | 0 |
| La Gaceta issues, 2026 (sumario text) | 228 | 0 | 0 | 0 |

By area, press releases: abortion 8, assisted dying 1, sex-based rights
36, parental rights and education 15, free speech 18, religion 17,
marriage and family 5, trafficking 21, organ donation 6; migration
(collated, hidden) 49. Agenda items: abortion 1, sex-based rights 7,
parental rights 5, free speech 1, religion 3, marriage and family 7,
trafficking 1, organ donation 2; migration 7.

Read honestly:

- **About three press releases a week touch our ground**, and that is
  where a bill on our ground is first named. Agenda items carry the bill's
  title only, often cut off by the API, and many plenary items are motions
  with no file at all.
- **Area 5 is mostly femicide and gender-based violence** (Penal Code
  reforms, the femicide orphans law, the "emergencia nacional por violencia
  de género" declaration): 32 of its 36 press-release matches carry only
gender-violence terms. As for
  Spain, whether gender-violence law is our ground is a scope question.
- **Area 9 on agenda items is mostly "Código de Familia"** at tier 2, and
  the commonest such item (EXP-2026-0316, the repeal of article 225) is
  about child-maintenance debts. Triage would drop it; the term stays
  because the Family Code is where marriage and adoption live.
- **La Gaceta matches nothing**, by construction: its sumario names
  decree numbers ("PODER LEGISLATIVO Decreto No. 151-2026"), not
  subjects. Its value is as the record of enactment, joined by decree
  number once a bill on our ground is approved (phase 2).

### 3. This Congreso is legislating on our ground, in our direction

Measured from the agenda and press corpus, January to October 2026, the
current legislature (installed 25 January 2026, Congreso president Tomás
Zambrano) has on its books:

- **Ley de Derechos Parentales** (EXP-2026-0390): the parents' preferential
  right to choose their children's education and guide their moral and
  religious formation. Comisión de Educación agenda 17 March, reported
  favourably 9 June, listed for second debate in September.
- **Ley de protección integral a la mujer embarazada y al No nacido**
  (EXP-2026-0441), on the plenary agenda of 25 March.
- **Plan Nacional de Lectura de la Biblia en centros educativos**
  (EXP-2026-1219, the Congreso president's own initiative, September), after
  a plenary motion of 4 February with no file.
- A **unanimous motion of 22 July** instructing the Comisión de Familia to
  investigate the illegal promotion of abortion pills on social media.
- The **Ley contra la Violencia Doméstica** reform of 11 June, at which the
  Congreso president welcomed a Supreme Court "reconsideración sobre
  identidad de género".
- Against the current: a **Ley de reconocimiento, dignidad y protección
  integral de la población LGBTIQ** (EXP-2026-1045), on the Comisión de
  Legislación agenda of 11 August.
- Also: trafficking-law reforms, child sexual abuse, an organ transplant
  law, a cybersecurity law (free-speech ground), a school mobile-phone law.

The constitutional ground is already held: the 2021 "escudo contra el
aborto" reform wrote an absolute abortion ban and the man-woman definition
of marriage into articles 67 and 112 and required a three-quarters majority
to change either (Decreto 6-2021 as commonly cited; the decree number was
not verified against La Gaceta here). So the live threats are less likely
to come through Congress than through **the courts** (the Sala de lo
Constitucional of the Corte Suprema, which reconsidered a gender-identity
ruling in June 2026) and **the Inter-American system** (Vicky Hernández v.
Honduras, 2021, which ordered a procedure for legal gender recognition),
and through executive acts (emergency contraception, the "PAE", which a
2023 executive decision allowed again, from background knowledge, not
measured here). None of these is in this collector.

## Is an edition worth it?

**Yes, a light one.** The Congreso is an independent, functioning
legislature with a working majority that is actively passing and promoting
measures on CitizenGO's ground, and its open data, though thin on votes, is
real JSON with no key. Against that: no per-member votes, no full bill
listing, a session register that stops recording plenaries after 20 May
(see below), and a press office that is the best single source. The
recommended shape is a short weekly or fortnightly digest built from press
releases and agenda items, with a bill board for the watchlist files, and
no 5CA. Volume is small (about three items a week on our ground), so it
could also run as a section of a wider Central America digest if
Christopher prefers fewer DMs.

## What Honduras publishes

### congresonacional.hn/api/matizzo (open, no key) -- WORKS TODAY

The public site is a static Next.js export; its pages fetch JSON from
same-origin `/api/matizzo/*`, which proxies the vendor's
`api-cnh.matizzo.com/External/*` (the vendor URL leaks in an error
message). Endpoints, all GET, all keyless, each reply
`{"isError": false, "message": "OK", "data": ...}`, measured times 0.7 to
1.6 s:

- `diputados`: **257 records** (128 seats plus substitutes; the API's own
  metrics say `propietarios 0, suplentes 257, bancadas 5`, so the
  propietario/suplente flag is not usable), each with `userId`, name,
  party, department, role, `isActive`, a photo URL, **the deputy's
  national identity number (`userDocument`) and e-mail**. The collector
  keeps neither of the last two. 112 KB.
- `diputados/departamentos?departamento=`, `diputados/<id>`: not needed.
- `sesiones?page=N&pageSize=M[&listId=L&estado=&desde=&hasta=]`: every
  session, plenary and committee. **362 rows, 360 distinct `roomId`s**,
  25 January 2025 to 23 September 2026, every one `Finalizada`. `pageSize`
  up to 100 honoured. `listId=8` is the plenary (34 sessions); the site's
  own page asks for `listId=1` and gets **zero**, which is why the public
  "Sesiones del Pleno" page is empty.
- `sesiones/<roomId>`: one session with its agenda, each item's `status`
  and `order`, a YouTube link and counters (`manifestaciones`,
  `mociones`...).
- `sesiones/orden-del-dia?roomId=<roomId>`: the agenda with each item's
  `legislativeProjectId`, `legislativeProject {number, title}`, author and
  the empty `resultado`. 1,488 distinct items from 359 sessions; **1,414
  carry a legislative file**. One session (390) returned
  `isError: true` from the vendor.
- `expediente?estado=K[&tipoId=&page=&pageSize=]`: totals per stage and
  **only the ten most recently touched files** in stage K (`page` and
  `pageSize` are ignored). Stage codes found by probing: 0 Iniciativa
  (473), 1 EnComision (573), 3 EnDebate (17), 6 Aprobado (174); 2, 4, 5,
  7, 8, 9 return nothing, and the names are refused ("The value
  'Aprobado' is not valid."). Total 1,237. **There is no full listing of
  bills**: the 1,237 can be met only ten per stage at a time or on an
  agenda. `fechaCreacion` moves with the stage (all ten approved files
  read 2026-09-23), so it is a last-touched date, not a filing date.
- `dashboard?anio=`: the counters quoted above. `comisiones`,
  `comisiones/<id>`: 50 committees with members.

Quirks, each handled in `tools/hn_rollcalls.py` and tested:

1. **Item statuses are unexplained codes.** Over the 34 plenary sessions:
   0 (442 items), 6 (123), 3 (31), 4 (30), 1 (15); item types 4, 5, 6, 7.
   Nothing on the site or in its JavaScript names them. Stored raw.
2. **The plenary register stops on 20 May 2026.** The 34 plenary sessions
   run 4 February to 20 May; nothing later, though the press releases
   report plenary approvals through June, July and September (the 11 June
   violence-law reform, the 22 July motion, a batch approved 23 September)
   and committees are recorded to 23 September. Agenda coverage of the
   plenary after May is therefore **missing at source**; the press releases
   fill the gap.
3. **A file number is near-unique, not unique**: 806 numbers on 807 files
   (EXP-2026-0254 is on two). The store keys on the internal id and the
   watchlist on the number.
4. **Titles are cut off** by the API at about 150 characters, ending in a
   full stop mid-sentence ("...declarar a la población LGBTIQ+ como.").
5. `www.congresonacional.hn` fails TLS (certificate for the apex only);
   the apex works. No `robots.txt` (404 on both hosts).

### api.congresonacional.hn/public (open, no key) -- WORKS TODAY

The CMS behind the news pages. `GET /public/news/<limit>/<skip>/` returns
`{successed, count, posts}`; **the second number is an offset, not a page**
(`/100/2/` overlaps `/100/1/` by 98 posts, which cost one confused probe).
**2,405 posts**; about 150 a month in 2026 (126 to 200), 7 to 25 a month in
late 2025. Each post's `body` is a JWT whose payload is the Draft.js
document, readable as base64 without the key. A 100-post page is about
1.27 MB and takes 4 to 10 s. `/public/categories` lists the CMS
categories; `/public/search` does not exist (404), though the site's
search page calls it.

### La Gaceta, enag.gob.hn (open, no key) -- WORKS TODAY

Free since the Congreso's 2026 agreement with ENAG. Joomla listings at
`/index.php/gaceta-digital/<year>/<mes>?start=N`, 12 issues a page, one
row per issue with its **sumario printed in the listing**, so the
collector reads no PDF. 2015 to 2026 available. **228 issues from
2 January to 2 October 2026; 86 carry legislative decrees.** Issues are
posted one to two weeks after their date (37,241 of 8 September was
created 21 September). Titles are typed by hand ("20260909 -37242"), so
the issue number is read off the generated download link. The PDFs carry a
text layer (37,241: 604 pages, 27 MB, read with pypdf) but are too heavy
to fetch weekly; fetching only the legislative issues' PDFs is a phase 2
option. The `consulta.enag.gob.hn` register is a WaveMaker JavaScript
application and was not used.

### Not used

- `cni.congresonacional.hn` is the Children's Congress, not data.
- `portalunico.iaip.gob.hn` (transparency portal) and the TSC: not
  legislative.
- YouTube links per session (full video of each sitting): kept in the
  store for debate packs later.

No CAPTCHA, bot challenge, login or rate limit was met on any host:
about 900 requests over the day (the full agenda backfill included) were
all answered, apart from two client timeouts (sessions 237 and 431, both
fetched cleanly on a second try) and the vendor error on session 390.

## Phase 1: built, 9 October 2026

`tools/hn_rollcalls.py` (named by convention; it collects no roll calls),
`src/hn_store.py`, `config/watchlist-hn.yaml`, `tests/test_hn_rollcalls.py`
with fixtures under `tests/fixtures/hn/` (the deputies' identity numbers
and e-mails replaced before saving), and the Mini-first weekly
(`jobs/hn-weekly.sh`, `ops/launchd/net.citizengo.parlmonitor.hn-weekly.plist`,
`.github/workflows/hn-weekly.yml`, gated by `mini-check` with
`HN_WEEKLY`; Sundays 14:00 London on the Mini, 14:00 and 17:00 UTC on
GitHub).

Each run: deputies (1 request), the four "recent expedientes" lists (4),
press releases until a page holds nothing new (1 a week; 13 on the first
run, back to 25 January 2026), La Gaceta's current and previous month (up
to 6; about 30 on the first run, back to January), the session list (4),
then the agenda and detail of every session not yet read or held in the
last 21 days (2 each; about 720 on the first run, cut by the 40-minute
budget and resumed). Tables: `hn_members`, `hn_sessions`,
`hn_agenda_items`, `hn_bills`, `hn_news`, `hn_gazette`.

Live run into a scratch store, 9 October 2026: 257 deputies, 40 recent
files, 1,300 press releases (115 on our ground under the draft list), 228
Gaceta issues, 362 sessions listed, agendas read for five; a second run
read one press page, found nothing new and stopped. Areas stay NULL until
a Spanish taxonomy exists (`config/taxonomy-es.yaml`, read automatically
when generated); the watchlist lends areas by number meanwhile. Tests:
20 in `tests/test_hn_rollcalls.py`, all passing.
## Proposed Spanish taxonomy (v0.1, FOR APPROVAL)

Drafted by Claude on 9 October 2026, measured against the corpus above
(1,488 agenda items, 1,219 press releases), **not yet read by a Honduran
who campaigns**: 267 terms over the 13 areas, checked to parse with
`tools/generate_taxonomy.parse_master`. It starts from the shared Spanish vocabulary in the Spain
branch's proposal (`docs/spain-scope.md` on branch `spain`), drops
Spain's own statutes, and adds Honduras's. Written in the generator's
format, so once approved the shared lines lift into a Spanish master and
`python3 tools/generate_taxonomy.py --lang es` produces
`config/taxonomy-es.yaml`, which `tools/hn_rollcalls.py` reads
automatically.

**For the merge with the other Spanish-language editions**: each area has
a `Honduras only` line naming the terms that are Honduran law, institutions
or usage (`escudo contra el aborto`, `artículo 67`, `artículo 112`, `PAE`,
`Ley de Derechos Parentales`, `Cuidando mi salud y mi vida`, `Plan Nacional
de Lectura de la Biblia`, `Vicky Hernández`, `CICESCT`, `DINAF`). Everything
else is ordinary Spanish legal and political vocabulary and is shared with
Spain's list or should be. The generator ignores the `Honduras only` lines.

The matching traps are Spain's (plurals and gender inflect the end of the
word, so nouns carry `*`; accents are part of the word; short words never
stand alone; acronyms are case-sensitive), plus two found here:
`paliativ*` and guarded `adopción` both matched economic prose and were
narrowed, and `clonación` matched card fraud and is now guarded.

### 1. Abortion {#1_abortion}
- **Tier 1:** aborto*; abortiv*; "interrupción voluntaria del embarazo"; "interrupción legal del embarazo"; "interrupción del embarazo"; IVE; ILE; objetor* [with: aborto, interrupción, embarazo, sanitari]; "píldora abortiva"; mifepristona; misoprostol; provida; "pro vida"; "no nacido*"; nasciturus; "derecho a la vida" [with: concebido, concepción, nacer, embarazo, aborto, gestación]; "desde la concepción"; "escudo contra el aborto"; "artículo 67" [with: Constitución, concebido, aborto, vida]; "tres causales"; "anticoncepción de emergencia"; "anticonceptivo de emergencia"; "píldora anticonceptiva de emergencia"; "pastilla anticonceptiva de emergencia"; "píldora del día después"; "pastilla del día después"; PAE [with: anticoncep, píldora, pastilla, emergencia]
- **Tier 2:** "salud sexual y reproductiva"; "derechos sexuales y reproductivos"; "salud reproductiva"; anticoncepci*; anticonceptiv*; "diagnóstico prenatal"; "vida prenatal"; "muerte perinatal"; "mujeres embarazadas" [with: ayuda, apoyo, vulnerab, protección]; "mujer embarazada" [with: ayuda, apoyo, vulnerab, protección]; "embarazo adolescente"; "embarazo en adolescentes"; "embarazo infantil"; "embarazo en niñas"
- **Honduras only:** "escudo contra el aborto"; "artículo 67"; "tres causales"; PAE; "píldora anticonceptiva de emergencia"; "pastilla anticonceptiva de emergencia"
- **Notes:** `aborto` is the plain word and the Penal Code's; `artículo 67` (guarded) is the constitutional article the 2021 reform shielded, `escudo contra el aborto` its political name, `tres causales` the exceptions campaign (rape, foetal anomaly, risk to life). The `PAE` (píldora anticonceptiva de emergencia) is tier 1 in Honduras, not tier 2 as contraception elsewhere, because it was banned as an abortifacient from 2009 to 2023 and its status is the abortion fight here. `embarazo adolescente` at tier 2: it is the frame of the 2023 sex-education law. MEASURED: 8 press releases, 1 agenda item (EXP-2026-0441).

### 2. Assisted dying and end of life {#2_assisted_dying}
- **Tier 1:** eutanasia*; eutanási*; "suicidio asistido"; "suicidio médicamente asistido"; "ayuda para morir"; "muerte digna"; "morir dignamente"
- **Tier 2:** "cuidados paliativos"; "sedación paliativa"; "medicina paliativa"; "testamento vital"; "voluntades anticipadas"; "final de la vida"; "fin de la vida"; "prevención del suicidio"
- **Honduras only:** (none)
- **Notes:** Not live in Honduras; drafted from the shared Spanish list. `paliativ*` was dropped on measurement: it matched "medidas paliativas" for fuel prices and power cuts. MEASURED: 1 press release.

### 3. Gender medicine and children {#3_gender_medicine_children}
- **Tier 1:** "bloqueador* de la pubertad"; "bloqueador* puberal*"; "bloqueo puberal"; "hormonación cruzada"; "hormonas cruzadas"; "disforia de género"; "incongruencia de género"; "menores trans"; "infancia trans"; "niños trans"; "niñas trans"; "adolescentes trans"; "reasignación de sexo"; "reasignación sexual"; "cirugía de reasignación"; detransici*; destransici*
- **Tier 2:** "transición de género" [with: menor, niño, niña, adolescente, infancia]; "tratamiento hormonal" [with: menor, niño, niña, adolescente, género, trans]; "afirmación de género"; "identidad de género" [with: menor, niño, niña, adolescente, infancia, escuela, colegio]
- **Honduras only:** (none)
- **Notes:** Drafted from the shared Spanish list. MEASURED: nothing.

### 4. Conversion practices {#4_conversion_practices}
- **Tier 1:** "terapia* de conversión"; "terapia* de aversión"; "prácticas de conversión"; "terapias reparativas"
- **Tier 2:** "acompañamiento espiritual" [with: conversión, orientación, identidad]
- **Honduras only:** "terapias reparativas"
- **Notes:** MEASURED: nothing.

### 5. Sex-based rights and gender identity {#5_sex_based_rights}
- **Tier 1:** "autodeterminación de género"; "rectificación registral"; "cambio de sexo registral"; "cambio de nombre" [with: identidad de género, trans, sexo]; "identidad de género"; "expresión de género"; "ideología de género"; "personas trans"; transexual*; transgénero*; "no binari*"; LGTBI*; LGBTI*; LGTB; LGBT; "Vicky Hernández"; "Convenio de Estambul"
- **Tier 2:** "perspectiva de género" [with: educación, escuela, menores, currículo, infancia]; "violencia de género"; "violencia machista"; "violencia sexual"; feminicidio*; femicidio*; "categoría femenina"; "lenguaje inclusivo"; "orientación sexual"; "diversidad sexual"; "Secretaría de la Mujer"; "Casas Refugio"; "Ley contra la Violencia Doméstica"
- **Honduras only:** "Vicky Hernández"; "Secretaría de la Mujer"; "Casas Refugio"; "Ley contra la Violencia Doméstica"; "cambio de nombre" [with: identidad de género, trans, sexo]
- **Notes:** `Vicky Hernández` names the Inter-American Court judgment (2021, background) that ordered Honduras to create a gender-recognition procedure; `cambio de nombre` guarded is how that procedure is discussed. The gender-violence terms are tier 2 and a scope question: 32 of this area's 36 press releases match only on them. MEASURED: 36 press releases, 7 agenda items, among them the LGBTIQ recognition bill (EXP-2026-1045).

### 6. Parental rights and education {#6_parental_rights_education}
- **Tier 1:** "derechos parentales"; "Ley de Derechos Parentales"; "derecho de los padres"; "derechos de los padres"; "derecho preferente de los padres"; "libertad de enseñanza"; "libertad educativa"; "educación sexual integral"; "educación integral en sexualidad"; "educación sexual"; "guías de educación sexual"; "Cuidando mi salud y mi vida"; "Ley de Educación Integral de Prevención al Embarazo Adolescente"; homeschooling; "educación en casa"; "educación en el hogar"
- **Tier 2:** "consentimiento parental"; "consentimiento de los padres"; "patria potestad"; "redes sociales" [with: menores, niños, niñas, adolescentes, escuela]; "teléfono* móvil*" [with: aula, escuela, centros educativos, menores]; "control parental"; adoctrinamiento; "Ley Fundamental de Educación"
- **Honduras only:** "Ley de Derechos Parentales"; "derechos parentales"; "Cuidando mi salud y mi vida"; "guías de educación sexual"; "Ley de Educación Integral de Prevención al Embarazo Adolescente"; "Ley Fundamental de Educación"
- **Notes:** `Ley de Derechos Parentales` is this session's flagship (EXP-2026-0390). `Cuidando mi salud y mi vida` names the 2011 sex-education guides whose withdrawal was a long fight, and the 2023 `Ley de Educación Integral de Prevención al Embarazo Adolescente` was passed and vetoed (both background knowledge, not measured here). `Ley Fundamental de Educación` is the 2012 education law, tier 2 because it is cited in all education traffic. MEASURED: 15 press releases, 5 agenda items.

### 7. Free speech, privacy and civil liberties {#7_free_speech_online_safety}
- **Tier 1:** "libertad de expresión"; "delito* de odio"; "discurso* de odio"; "incitación al odio"; pornograf*; "verificación de edad"; "Ley de Ciberseguridad"; "ciberseguridad" [with: expresión, censura, contenidos, redes sociales]
- **Tier 2:** desinformaci*; "noticias falsas"; "libertad de prensa"; "libertad de información"; censura [with: expresión, redes, prensa, internet]; "secreto de las comunicaciones"; "intervención de las comunicaciones"; "reconocimiento facial"; "protección de periodistas"
- **Honduras only:** "Ley de Ciberseguridad"; "ciberseguridad" [with: expresión, censura, contenidos, redes sociales]; "protección de periodistas"
- **Notes:** Honduras's live speech questions are the cybersecurity bill, criminal defamation ("delitos contra el honor", whose removal from the Penal Code a vice-president proposed) and the protection of journalists. `delitos contra el honor` is NOT drafted: it is also ordinary litigation; a scope question. MEASURED: 18 press releases (several are the Congreso president's speeches on press freedom), 1 agenda item.

### 8. Freedom of religion or belief {#8_freedom_of_religion}
- **Tier 1:** "libertad religiosa"; "libertad de culto"; "libertad de conciencia"; "objeción de conciencia"; "sentimientos religiosos"; blasfemia*; cristianofobia; "persecución de cristianos"; "cristianos perseguidos"; "minorías religiosas"; capellan*; "lectura de la Biblia"; "Plan Nacional de Lectura de la Biblia"; "Plan de Lectura de la Biblia"; "Día Nacional de la Biblia"; "Día de la Biblia"
- **Tier 2:** Biblia [with: escuela, escuelas, centros educativos, estudiantes]; "Iglesia católica"; "Conferencia Episcopal"; "Confraternidad Evangélica"; "iglesias evangélicas"; "lugares de culto"; "confesiones religiosas"; "entidades religiosas"; "organizaciones religiosas"; "asociaciones religiosas"; "enseñanza de la religión"; "educación religiosa"; "símbolos religiosos"; "Día Nacional de Oración"
- **Honduras only:** "Plan Nacional de Lectura de la Biblia"; "Plan de Lectura de la Biblia"; "lectura de la Biblia"; "Día Nacional de la Biblia"; "Día de la Biblia"; "Confraternidad Evangélica"; "Día Nacional de Oración"; Biblia [with: escuela, escuelas, centros educativos, estudiantes]
- **Notes:** The Bible-reading plan for schools (EXP-2026-1219) is the area's centre this session. Bare `Biblia` is guarded and tier 2: it also appears in the chaplain-led prayer sessions the Congreso holds and reports. `Confraternidad Evangélica` is the evangelical umbrella body consulted on social bills. MEASURED: 17 press releases, 3 agenda items (one a property-tax waiver for a Catholic parish, tier 2).

### 9. Marriage and family {#9_marriage_family}
- **Tier 1:** "matrimonio entre personas del mismo sexo"; "matrimonio igualitario"; "matrimonio homosexual"; "artículo 112" [with: Constitución, matrimonio]; "matrimonio infantil"; "uniones tempranas"; "unión entre personas del mismo sexo"; "uniones de hecho entre personas del mismo sexo"; "adopción por parejas del mismo sexo"; poligamia; "protección a la familia"; "protección de la familia"; "valores de la familia"; "valores familiares"
- **Tier 2:** "Código de Familia"; natalidad; "invierno demográfico"; "permiso de maternidad"; "permiso de paternidad"; "custodia compartida"; divorcio*; "unión de hecho"; "adopción de menores"; "adopción de niños"; "Ley de Adopciones"; "Dirección de Niñez, Adolescencia y Familia"; DINAF
- **Honduras only:** "artículo 112" [with: Constitución, matrimonio]; "valores de la familia"; "valores familiares"; "uniones tempranas"; "Código de Familia"; "unión de hecho"; "Dirección de Niñez, Adolescencia y Familia"; DINAF; "Ley de Adopciones"
- **Notes:** `artículo 112` (guarded) is the marriage article the 2021 reform shielded. Honduras banned child marriage in 2017 (background); `uniones tempranas` is the term for the informal unions that replaced it. `Código de Familia` is tier 2 and mostly maintenance law (see above). `adopción` was narrowed to phrases on measurement: guarded, it matched "adopción de medidas". MEASURED: 5 press releases, 7 agenda items.

### 10. Surrogacy and embryology {#10_surrogacy_embryology}
- **Tier 1:** "gestación subrogada"; "gestación por sustitución"; "maternidad subrogada"; "vientre* de alquiler"; "reproducción asistida"; "reproducción humana asistida"; embrion*; embrión; "fecundación in vitro"; clonación [with: humana, embrión, embriones, genética, reproductiva]; "edición genética"; "células madre embrionarias"
- **Tier 2:** "donación de óvulos"; "donación de gametos"; FIV; "investigación biomédica"
- **Honduras only:** (none)
- **Notes:** `clonación` is guarded on measurement: it matched card cloning in a fraud trial. MEASURED: nothing.

### 11. Migration {#11_migration}
- **Tier 1:** inmigración; inmigrante*; migrante*; emigrante*; "protección internacional"; asilo; refugiad*; retornad* [with: migrante, deportad, Estados Unidos]; deportad*; "hondureños en el exterior"; "Ley de Migración y Extranjería"
- **Tier 2:** migración; migratori*; deportaci*; remesas; TPS
- **Honduras only:** "hondureños en el exterior"; "Ley de Migración y Extranjería"; retornad* [with: migrante, deportad, Estados Unidos]; deportad*; TPS; remesas
- **Notes:** Collated, never campaigned, hidden on every surface. Honduras's migration traffic is about its own emigrants and deportees (`retornados`, `TPS`, `remesas`), not immigration. MEASURED: 49 press releases, 7 agenda items.

### 12. Prostitution, trafficking and sexual exploitation {#12_prostitution}
- **Tier 1:** prostituci*; proxenetismo; proxeneta*; "trata de seres humanos"; "trata de personas"; "Ley contra la Trata de Personas"; "explotación sexual"; "explotación sexual comercial"; CICESCT; "matrimonio* forzado*"
- **Tier 2:** "trabajo sexual"; "trabajadoras sexuales"; "abuso sexual infantil"; "explotación sexual infantil"; "agresión sexual" [with: menores, niños, niñas]; "violación" [with: menores, niñas, niños]; "pornografía infantil"
- **Honduras only:** CICESCT; "Ley contra la Trata de Personas"; "explotación sexual comercial"
- **Notes:** `CICESCT` is the inter-institutional commission against commercial sexual exploitation and trafficking, named in every reform of the trafficking law. MEASURED: 21 press releases (several on child sexual abuse), 1 agenda item.

### 13. Organ donation {#13_organ_donation}
- **Tier 1:** "donación de órganos"; "trasplante* de órganos"; "tráfico de órganos"; "turismo de trasplantes"
- **Tier 2:** trasplante*; "donante* de órganos"; "muerte encefálica"; "consentimiento presunto"
## Global exclusions (advisory)
- **Terms:** vida; familia; género; sexo; menores; matrimonio; libertad; religión; educación; odio; mujer; igualdad; trans; iglesia
- **Honduras only:** (none)
- **Notes:** MEASURED: 6 press releases, 2 agenda items (the organ and tissue transplant law, in the Comisión de Salud).

### Global exclusions (advisory)

vida; familia; género; sexo; menores; matrimonio; libertad; religión; educación; odio; mujer; igualdad; trans; iglesia. These bare words must never become terms on their own.

## Proposed phasing

1. **Phase 1 (built, this branch).** Deputies, sessions, agendas with item
   statuses, the recent expedientes, press releases and La Gaceta's
   listings; Mini-first weekly; unclassified until the Spanish list is
   approved, the watchlist lending areas by number meanwhile.
2. **Phase 2 (needs the approved list).** Generate `config/taxonomy-es.yaml`
   (shared with the other Spanish-language editions), reclassify
   (`HN_RECLASSIFY=true`), and render a short edition from press releases,
   agenda items and a bill board for the watchlist files, DM'd to
   Christopher. Join approved files to their decree and Gaceta issue by
   decree number, reading only the legislative issues' PDFs.
3. **Phase 3 (optional).** The Sala de lo Constitucional's rulings and the
   Inter-American Court's Honduras cases as a courts channel; the session
   YouTube links for debate packs. Ask the Congreso (or the vendor,
   matizzo) whether the vote module will be switched on: the fields exist.

There is no 5CA phase while the Congreso publishes no per-member votes.

## Regions (later, not probed)

Honduras is unitary: departments with appointed governors and elected
municipal corporations, **no regional legislatures** (background, not
probed). Nothing to add. Honduras's deputies to the Central American
Parliament (Parlacen) appear in the press releases (a July prayer session
was held jointly) and are not a legislative channel for our issues.

## Shared files touched (for the merge of the country branches)

- `src/db.py`: six `hn_*` names added to `TABLES`, and
  `hn_store.ensure_schema` called from `init_db` (10 lines).
- `tools/coverage.py`: `Honduras weekly` in `PIPELINES`, `PIPELINE_FEEDS`
  and `AWAITING_FIRST_RUN`; `hn_members`, `hn_bills`, `hn_news`,
  `hn_gazette`, `hn_sessions` (7 + 4 days) and `hn_agenda_items` (31 + 62
  days, for the November to January recess) in `FEEDS`.
- `.github/workflows/alert.yml`: `"Honduras weekly"` added to the watched
  workflows (1 line).

Not touched: any taxonomy file, `tools/generate_taxonomy.py`,
`tools/mini_run.sh`, `.github/workflows/mini-check.yml`. New files only
otherwise: `src/hn_store.py`, `tools/hn_rollcalls.py`,
`config/watchlist-hn.yaml`, `jobs/hn-weekly.sh`,
`ops/launchd/net.citizengo.parlmonitor.hn-weekly.plist`,
`.github/workflows/hn-weekly.yml`, `tests/test_hn_rollcalls.py`,
`tests/fixtures/hn/`, this document.

Test suite on this branch: `tests/test_hn_rollcalls.py` 20 of 20 pass.
The full suite (3,312 tests) shows 1 failure and 10 errors, all from files a
worktree does not carry (the frozen raw fixtures under `data/raw/` other
than 2026-08-01, linked in for the run, and the working-copy store
`data/parl-monitor.db`); none touches Honduras code.

## Waiting on Chris

1. **Is a Honduras edition worth it in this shape** (no votes, about three
   items a week, press-led)? Recommended: yes, light, fortnightly or as a
   section of a Central America digest; say which.
2. **Approve or amend the Spanish terms above**, ideally after a read by
   someone in the Latin American team, and settle how the Spanish-language
   lists merge (one shared `taxonomy-es` with country addenda is assumed).
3. **Scope questions the corpus raised:**
   - **Gender-based violence and femicide law** (32 of 36 area-5 press
     releases): in or out? Drafted at tier 2 so triage reads it.
   - **Criminal defamation** ("delitos contra el honor"): free-speech
     ground or ordinary litigation? Not drafted.
   - **Emergency contraception (PAE)**: drafted at tier 1 under abortion,
     unlike the US decision on contraception, because of its Honduran
     history. Agree?
   - **Prayer sessions and church grants** the Congreso holds and reports
     (religion, tier 2): useful colour or noise?
4. **Watchlist**: five files are on it (Derechos Parentales, the unborn
   child protection law, the Bible-reading plan, the LGBTIQ recognition
   bill, and the substitute judicial authorisation over parental authority,
   whose direction needs a reading before campaigning). Add or remove.
5. **Merge and install.** Merge `honduras` to main when ready (the workflow
   schedules only from main); copy the plist to the Mini and bootstrap it.
   `MINI_LAST_HN_WEEKLY` is written by `mini_run.sh` on the first clean
   run; no secret or key is needed.
6. **The first-run backfill** (about 770 requests, mostly the 360 session
   agendas, at 1.2 s each over one or two Sundays, on the Mini): announced
   here; say if it should run differently.

## Decisions of 10 October 2026 (applied at the countries merge)

Recorded in `docs/country-decisions-2026-10-10.md`. Shared: accents fold and non-ASCII letters are word characters in the filter (X3); member positions are stored for every vote (X15); the AI judge stays off (X16).

Applied on the `countries` branch:

- Term list approved (HN2, HN3 criminal defamation, HN4 emergency contraception tier 1, HN5 prayer sessions and church grants) and merged into the shared `config/taxonomy-es.yaml` (`docs/keyword-taxonomy-es.md`), loaded for this country's code.
