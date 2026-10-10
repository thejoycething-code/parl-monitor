# Panama: scope of a parliamentary monitor edition

Probed live from the laptop on 9 October 2026 (branch `panama`). Every
number below was measured that day unless it says otherwise. Raw responses
are archived under `data/raw/2026-10-09/` (`pa-rollcalls_*` from the
collector's own runs, `pa-probe_*` from the hand probes).

## Decisions already taken (Christopher)

- Own edition per country, delivered to Christopher alone (Slack DM), as the US.
- Shared taxonomy concept, but no existing taxonomy file is edited. The
  Spanish term list below is a PROPOSAL; no `taxonomy-*` file is generated
  until Christopher approves it.
- National parliament first; sub-national bodies listed only.
- Mac Mini first, GitHub Actions as the backup. No new paid services. Never
  post publicly.

## The three findings that shape everything

### 1. No recorded votes are public

Panama's Asamblea Nacional is unicameral (71 deputies) and votes
electronically. The system is "Asamblea 507" at
`prensa507.asamblea.gob.pa`, an Ionic/Angular app with a REST API
(`/api/v1/...`) and a socket. The official site links it as "Votación Pleno".
Measured:

| Endpoint | Answer without a login |
|---|---|
| `/api/v1/public/settings/?forPage=0` | 200, app settings |
| `/api/v1/political-parties` | 200, 10 parties |
| `/api/v1/plenary-sessions-years` | **401** `{"errorCode":"invalidSession"}` |
| `/api/v1/plenary-sessions?paginated=false&onlyEnded=true` | **401** `invalidSession` |

Every session, voting, question and deputy-position endpoint the bundle
names (`/api/v1/voting/{id}/votes`, `/who-votes`, `/plenary-session/{id}`,
`/question/{id}/answer/{a}/deputies`) sits behind the same session. The
public "press" route (`/press/votings`, "Reportes de transparencia de la
Asamblea Nacional de Panamá") renders only "Votaciones del día": the
current day's votes, pushed live, and empty on a Friday with no sitting. The
bundle contains a guest login (role 8) driven by stored credentials; we did
not, and will not, try it.

Press reports (La Estrella, TVN) say the board is now shown in the
chamber and on the official broadcast, mostly for third debates. That is
television, not data. The segLegis stage history records only "APROBADO EN
III DEBATE", with no tally and no names.

**So the edition cannot do what the UK, US, Spain or Germany do: say how
each deputy voted.** It can follow every bill on our ground from
presentation to law, say which are on the plenary's agenda each day, and
name each bill's proponent. Recorded votes are the first item on the
Waiting-on-Chris list (whether to ask the Asamblea for a public feed).

### 2. The English taxonomy is blind to Spanish

`config/taxonomy.yaml`, unchanged, over every title in segLegis:

| Text matched | Rows | Any area |
|---|---|---|
| Anteproyecto and proyecto titles, 2024-2029 term | 931 | **0** |

The same result as Germany and Spain.

**With the Spanish list proposed below** (draft v0.1, measured on the same
931 titles):

| | Bills | On our ground (area 11 hidden) | Tier 1 |
|---|---|---|---|
| Titles accent-folded (as built) | 931 | **38** | 10 |
| Titles as typed | 931 | 27 | 5 |
| Last twelve months (presented since 9 Oct 2025) | 408 | 18 | |

By area: abortion 2, assisted dying 1, sex-based rights 5, parental rights
and education 4, free speech 1, marriage and family 13, prostitution,
trafficking and sexual exploitation 12, organ donation 1, migration 1 (with
trafficking, so not hidden). Nothing in areas 3, 4, 8 or 10.

**The accent problem is Panama's own.** segLegis titles are capitals typed
with or without accents ("ORGANICA DE EDUCACION" beside "ORGÁNICA DE
EDUCACIÓN"), and the filter treats `é` and `e` as different letters. Folding
both the title and the terms before matching found 11 bills the plain match
missed. The collector does this locally (`deaccent()` in
`tools/pa_rollcalls.py`); the shared filter is untouched. Any other edition
whose source types capitals without accents will need the same.

### 3. The classic fights are not in this Asamblea's bills

A raw substring count over the 931 accent-folded titles: `ABORT` 0,
`GENERO` 0, `SEXUALIDAD` 0, `EUTANAS` 0, `RELIGIOS` 0, `IGLESIA` 0,
`EMBARAZ` 0, `CONCEPCION` 0, `MATRIMONI` 1 (a compensatory-pension change
to the Family Code). No bill of the 2024-2029 term is titled on abortion,
gender identity, same-sex marriage, euthanasia or sexuality education.

The example in the brief, **proyecto 61 on sexuality education** (Crispiano
Adames, PRD, "políticas de educación integral, atención y promoción de la
salud"), belongs to the 2014-2019 term: first debate passed, then sent back
to first debate by the plenary after the 2016 evangelical and Catholic
marches, and left in the temario. segLegis's public list starts on 1 July
2024, so it is not there, and **proyecto 61 of the current term (ficha 7848)
is an unrelated criminal-procedure law**, now in force. That collision is
why everything here is keyed by ficha, never by proyecto number or title.

What this Asamblea does bring to our ground is family law (the Family Code,
adoptions, maintenance), sexual offences against children, trafficking,
the Ministry of Education's sphere (social-media limits for minors, values
education, parents' associations) and one sterilisation-on-request bill.
That is a thinner edition than Spain's, and an honest one: the ground is
quiet in the chamber.

## What Panama publishes

### segLegis, "Seguimiento Legislativo": WORKS, no key

`https://sistemas.asamblea.gob.pa/segLegis/viewsPublico/SeguimientoLegislativo`

- **Format**: an ASP.NET Web Forms page (`__VIEWSTATE`,
  `__EVENTVALIDATION`, `__doPostBack`). No API, no JSON, no export. A GET
  shows the empty search form; "Buscar todo" (`btnMostrarTodo`) lists the
  whole current term, newest first, 20 rows a page. Filters (title, proyecto,
  anteproyecto, proponent type, stage, committee) are a separate postback
  (`btnFiltrar`).
- **Paging is sequential**: page n+1 is a postback of page n's own form, and
  event validation only accepts page links the previous page rendered. No
  cookies are needed (measured: the walk works with none).
- **Measured walk**: 47 pages, **931 items** (fichas 7403 to 8634, presented
  2 July 2024 to 8 October 2026), 4 min 34 s and 4 min 35 s on two runs. A
  GET answers in about 1.3 s; each paging postback takes 5 to 25 s. One
  hand walk hit three dropped TLS handshakes and a read timeout in a row;
  the collector's runs hit none. The collector waits 2 s between requests
  and retries a postback after 10, 30 and 90 s.
- **Row**: ficha, presentation date (DD-MM-YYYY), proyecto number (blank
  until there is one: 739 of 931 have one), anteproyecto number, title (in
  capitals), current stage, proponent(s), "Ver documento" (926 of 931) and
  "Ver etapas".
- **Stages on 9 October**: Primer Debate 202, Segundo Debate 164, Preliminar
  115, Ley 114, "Enviado a subcomisión para analisis" 105, Archivado 67,
  Negado 61, Retirado por proponente 48, Objetado por Ejecutivo 31, Enviado
  al Ejecutivo 9, Suspendido 7, Tercer Debate 3, two objected variants, Prohijado 1.
- **Stage history** ("Ver etapas", one more postback per bill): dated rows
  newest first, e.g. ficha 7653: Preliminar 24 Sep 2024, Prohijado,
  Pendiente de I debate, Aprobado en I debate 19 Aug 2025, ..., Aprobado en
  III debate 2 Oct 2025, Enviado al Ejecutivo, Sancionado 24 Nov 2025. Dates
  are written "24-noviembre-2025".
- **Text**: `https://sistemas.asamblea.gob.pa/segLegis/Documents/<ficha>.pdf`,
  a stable URL.
- **Quirks**: numbers restart every term (proyecto 61 above); the grid's
  last row is its pager (filtered out by requiring a date); titles mix
  accented and unaccented capitals; one row can name several proponents.

### Deputies: WORKS, no key

`https://www.asamblea.gob.pa/Data/Diputado/List?page=1&pageSize=100&search=`,
JSON. `totalRecords` 71, all 71 in one call (the site's own page asks for 6
at a time). Each record: numeric ID, name, party, province, electoral
circuit, substitutes, slug, photo, CV PDF, official e-mail (not stored).
Parties on 9 October: Libre Postulación (independents) 20, Realizando Metas
14, PRD 12, Cambio Democrático 9, Panameñista 8, Movimiento Otro Camino 3,
Alianza 2, Partido Popular 2, Molirena 1. Sitting deputies only; no history.

### Orden del día (plenary agenda): WORKS, no key

`POST https://www.asamblea.gob.pa/Data/OrdenDia/21/0/List`, a DataTables
server-side endpoint (`draw`, `start`, `length`, `order[0][dir]=desc`).
`recordsTotal` 360, from 25 January 2024. Each record links a PDF under
`/Uploads/OrdenDia/<id>/`. The PDFs have a text layer (pypdf reads them;
25 pages on 8 October) and list items as "Segundo Debate al Proyecto de Ley
No. 724;" plus the title, with "(Suspendido)" where suspended.

Measured on the 15 newest (10 September to 8 October 2026): **2,553 bill
items, every one joined to a segLegis ficha** by (term, proyecto number);
2,543 second-debate and 10 third-debate items; 98 suspended. Each agenda
carries the whole second-debate backlog, about 170 items a day, so the
agenda says what is pending on the floor rather than what was taken. Twelve
of the 38 bills on our ground sit on every one of those agendas.

Quirks: names carry typos ("JUEVES1 DE OCTUBRE"; doc 483 "LUNES 31 DE
AGOSTO DE 2025" published 31 August 2026; the collector takes the
publication year when the two are more than 60 days apart); doc 498 (28
September) is listed with no PDF at all.

### Also public, not collected

- **Asistencia al Pleno**: `POST /Data/Documentos/FList/46` (JSON), 15
  monthly attendance PDFs, latest August 2026. Per-deputy, monthly; a
  possible phase 2 signal.
- **Agenda de Comisiones**: `/Page/LABORLEGISLATIVA/AgendaComisiones`, not probed further.
- **Legispan** (`legispan.asamblea.gob.pa`, norms, records, Gaceta
  "tabloids"): an Angular app over `https://legispan.asamblea.gob.pa/api`;
  its calls are in lazy chunks and did not render in a headless pane. Laws in
  force, not bills; the Gaceta Oficial is the official alternative.
- **Transparencia**: `/Data/Transparencia/...` JSON (Ley 6 de 2002
  disclosures). Administrative.
- **Propuestas ciudadanas** (`sistemas.asamblea.gob.pa/partLegis/...`): a
  Telerik page listing citizens' proposals by the citizen's name. Not
  collected: private individuals, and nothing reaches the plenary without
  a deputy or committee adopting it, at which point segLegis carries it.

### Hosts, robots and access

No `robots.txt` on any host (404 or the app shell). No CAPTCHA or bot
challenge met anywhere. Our honest UA (`CitizenGO-ParlMonitor/1.0 (contact:
...)`) was accepted everywhere. **Not measured: whether
sistemas.asamblea.gob.pa answers GitHub's runners** (Spain's Senado did
not); the Mini is the measured runtime.

## Political context in one paragraph

The Asamblea is an elected, independent legislature (2024 elections; a
fragmented chamber with 20 independents, no majority party) and a real
venue: bills move, the Executive vetoes ("Objetado por Ejecutivo", 31 this
term) and the Asamblea overrides or shelves. An edition is worth having.
The bigger battles on our ground have run through the streets (the 2016
marches) and the courts: the Corte Suprema de Justicia upheld the Family
Code's man-woman definition of marriage in 2023 (from memory, not probed).
Courts are a channel for a later phase; referendums are not a regular one.

## Phase 1: built, 9 October 2026

- `src/pa_store.py`: `pa_members`, `pa_bills` (key: ficha), `pa_bill_stages`,
  `pa_agenda`, `pa_agenda_items`. No votes table, on purpose (see finding 1).
- `tools/pa_rollcalls.py`: deputies; the full segLegis walk; stage histories
  for bills whose stage moved since the last run, and once for each bill on
  our ground or watched (at most 60 a run); the 25 newest orden del día
  documents and the bill items of up to 15 unread PDFs. Areas stay NULL
  until a Spanish taxonomy exists; `config/watchlist-pa.yaml` (empty, keyed
  by ficha) lends areas meanwhile. `--taxonomy` classifies with a draft.
  Exit 3 on gaps, as Spain.
- `tests/test_pa_rollcalls.py`: 27 tests on real fixtures saved 9 October
  (`tests/fixtures/pa/`: the bare form, page 1, the real last page 47, the
  stage history of ficha 7653, the deputies JSON without e-mails, the agenda
  list and the 8 October agenda's extracted text).
- `jobs/pa-weekly.sh`, `ops/launchd/net.citizengo.parlmonitor.pa-weekly.plist`
  (Saturdays 17:30 London), `.github/workflows/pa-weekly.yml` (Saturdays 17:30
  and 21:30 UTC since the countries merge, Portugal holding 16:00; gated by `mini-check` with `PA_WEEKLY`, grace 320 minutes).
  Publishes raw archive then store, the order `tests/test_raw_state` expects.
- **Measured runs into a scratch store**: first run 71 deputies, 47 pages,
  931 bills, 24 agendas listed (one without a PDF), 15 read, 2,553 items, 0
  gaps. Second run with the draft taxonomy: 38 on our ground, 38 stage
  histories (162 stage rows), 4 min 35 s, 0 gaps.

Installing on the Mini (not done):

```
cp ~/runner/parl-monitor/ops/launchd/net.citizengo.parlmonitor.pa-weekly.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/net.citizengo.parlmonitor.pa-weekly.plist
```

pypdf must be importable on the Mini (it is in `tools/macmini_setup.sh`);
without it the agenda is listed but its items are not parsed, and the log
says so.

No edition or DM yet: phase 1 is the collector, as for Spain. The edition
follows the taxonomy decision.

## Proposed Spanish taxonomy for Panama (v0.1, FOR APPROVAL)

Drafted by Claude on 9 October 2026 and measured against the 931 titles
above, **not yet read by a Panamanian who campaigns**. It starts from the
Spain branch's v0.1 (`docs/spain-scope.md`), drops Spain's statute numbers
and usages, and adds Panama's. Written in the generator's format. Two
routes once approved: merge the shared terms into one `taxonomy-es` with
Spain, Mexico and the rest of Latin America, and keep the `Panama only`
lines as a Panama addendum; or a Panama file of its own. Either way the
collector must keep folding accents (above).

Panama-specific traps:

- **Capitals without accents**: see finding 2. Terms are written with
  accents here, as the generator expects; the collector folds both sides.
- **Short words never stand alone**: `familia` ("Centros Familiares",
  "familiares de pacientes"), `vida` ("seguros de vida", "estilo de vida
  saludable"), `menores`, `niñez`, `mujer`, `valores` ("valores de la etnia").
- **`Ley 47 de 1946` (Ley Orgánica de Educación) is cited in every education
  bill**: unguarded it tagged 12 bills about school meals, uniforms and the
  calendar. It is guarded to sexuality, gender, values, religion and parents.
- **`Código de la Familia` at tier 1 is deliberately wide**: it tags
  guardianship and procedure changes as well as anything touching marriage.
  The Code holds Panama's marriage definition (art. 26), so every amendment
  deserves a look; triage drops the procedural ones.

### 1. Abortion {#1_abortion}

- **Tier 1:** aborto*; abortiv*; "interrupción voluntaria del embarazo"; "interrupción legal del embarazo"; "interrupción del embarazo"; IVE; ILE; "píldora abortiva"; mifepristona; misoprostol; provida; "pro vida"; "no nacido*"; "por nacer"; nasciturus; "derecho a la vida" [with: concebido, concepción, nacer, embarazo, aborto, gestación]; "desde la concepción"; "comisión multidisciplinaria" [with: aborto, embarazo]
- **Tier 2:** "salud sexual y reproductiva"; "derechos sexuales y reproductivos"; "salud reproductiva"; anticoncepci*; anticonceptiv*; "píldora del día después"; "anticoncepción de emergencia"; "diagnóstico prenatal"; "duelo gestacional"; "muerte perinatal"; "embarazo adolescente"; "embarazo en adolescentes"; "embarazo precoz"; "mujeres embarazadas" [with: ayuda, apoyo, vulnerab]; "madres adolescentes"; esterilizaci* [with: salud, petición, voluntaria, quirúrgica, mujeres, hombres]
- **Panama only:** "comisión multidisciplinaria" [with: aborto, embarazo]; "por nacer"; "desde la concepción"; "embarazo adolescente"; "embarazo en adolescentes"; "embarazo precoz"; "madres adolescentes"
- **Notes:** the multidisciplinary commission is, to our knowledge, the body the Penal Code makes authorise a lawful abortion (check with the Panama team). Teenage pregnancy is the frame in which Panama's sexuality-education fights are argued, hence tier 2. MEASURED: 2 bills (gestational grief, 8575; sterilisation on request, 7922, on every recent agenda).

### 2. Assisted dying and end of life {#2_assisted_dying}

- **Tier 1:** eutanasia*; eutanási*; "suicidio asistido"; "suicidio médicamente asistido"; "ayuda para morir"; "muerte digna"; "morir dignamente"; "muerte asistida"
- **Tier 2:** "cuidados paliativos"; paliativ*; "sedación paliativa"; "testamento vital"; "voluntades anticipadas"; "voluntad anticipada"; "final de la vida"; "fin de la vida"; "enfermos terminales"; "enfermedad terminal"; "prevención del suicidio"
- **Panama only:** none.
- **Notes:** MEASURED: 1 bill (a cancer plan naming palliative care, 8504).

### 3. Gender medicine and children {#3_gender_medicine_children}

- **Tier 1:** "bloqueador* de la pubertad"; "bloqueador* puberal*"; "bloqueo puberal"; "hormonación cruzada"; "hormonas cruzadas"; "disforia de género"; "incongruencia de género"; "menores trans"; "infancia trans"; "niños trans"; "niñas trans"; "adolescentes trans"; "reasignación de sexo"; "reasignación sexual"; "cirugía de reasignación"; detransici*; destransici*
- **Tier 2:** "transición de género" [with: menor, niño, niña, adolescente, infancia]; "tratamiento hormonal" [with: menor, niño, niña, adolescente, género, trans]; "afirmación de género"; "identidad de género" [with: menor, niño, niña, adolescente, infancia, escuela, colegio]
- **Panama only:** none.
- **Notes:** Spain's list less its "unidades de identidad de género". MEASURED: 0.

### 4. Conversion practices {#4_conversion_practices}

- **Tier 1:** "terapia* de conversión"; "terapia* de aversión"; "prácticas de conversión"; "terapia* reparativa*"
- **Tier 2:** "acompañamiento espiritual" [with: conversión, orientación, identidad]
- **Panama only:** none.
- **Notes:** MEASURED: 0.

### 5. Sex-based rights and gender identity {#5_sex_based_rights}

- **Tier 1:** "identidad de género"; "expresión de género"; "ideología de género"; "enfoque de género" [with: educación, escuela, currículo, niñez, menores]; "personas trans"; transexual*; transgénero*; "no binari*"; LGTBI*; LGBTI*; LGTB; LGBT; LGBTIQ*; "cambio de sexo"; "cambio de nombre" [with: sexo, género, identidad]; "autodeterminación de género"; "Convenio de Estambul"
- **Tier 2:** "perspectiva de género" [with: educación, escuela, menores, currículo, infancia, niñez]; "violencia de género"; "violencia contra las mujeres"; "violencia contra la mujer"; "violencia sexual"; femicidio*; feminicidio*; "orientación sexual"; "diversidad sexual"; "lenguaje inclusivo"; "deporte femenino" [with: trans, sexo, identidad]; "discriminación" [with: orientación sexual, identidad de género, sexo]; "Instituto Nacional de la Mujer"; "Ministerio de la Mujer"
- **Panama only:** "cambio de nombre" [with: sexo, género, identidad]; "Instituto Nacional de la Mujer"; "Ministerio de la Mujer"
- **Notes:** `femicidio` is Panama's legal word (Ley 82 de 2013); `feminicidio` is kept for the shared list. The gender-violence terms are tier 2 and the same scope question as in Spain: here they are 4 of the area's 5 bills (two of them withdrawn). The fifth is the bill creating the Instituto Nacional de la Mujer (8193, on every recent agenda).

### 6. Parental rights and education {#6_parental_rights_education}

- **Tier 1:** "educación sexual"; "educación integral en sexualidad"; "educación sexual integral"; "educación integral de la sexualidad"; "educación en sexualidad"; "educación afectivo-sexual"; "educación afectiva"; "guías de sexualidad"; "guías de educación sexual"; "derecho de los padres"; "derechos de los padres"; "derecho preferente de los padres"; "patria potestad"; "asociaciones de padres de familia"; "asociación de padres de familia"; "libertad de enseñanza"; "libertad educativa"; homeschooling; "educación en casa"; "educación en el hogar"; "entorno* digital*" [with: menores, infancia, niños, niñas, adolescentes]
- **Tier 2:** "consentimiento parental"; "consentimiento de los padres"; "padres de familia" [with: educación, escuela, colegio, currículo, sexual]; "Orgánica de Educación" [with: sexual, sexualidad, género, valores, religi, padres de familia]; "Ley 47 de 1946" [with: sexual, sexualidad, género, valores, religi, padres de familia]; "Ministerio de Educación" [with: sexual, sexualidad, género, valores]; "redes sociales" [with: menores, edad, niños, adolescentes, escuela]; "teléfono* celular*" [with: aula, colegio, centros educativos, escuela, menores]; "control parental"; adoctrinamiento; "protección integral de los derechos de la niñez"; "Sistema de Garantías" [with: niñez, adolescencia]; "educación en valores"; "valores morales"
- **Panama only:** "guías de sexualidad"; "guías de educación sexual"; "asociaciones de padres de familia"; "asociación de padres de familia"; "Orgánica de Educación"; "Ley 47 de 1946"; "teléfono* celular*"; "Sistema de Garantías"; "protección integral de los derechos de la niñez"
- **Notes:** `educación integral en sexualidad` is the wording of the proyecto 61 fight and of the Ministry of Education's 2019 sexuality guides, the two great Panamanian battles on this ground. The `Sistema de Garantías` is Ley 285 de 2022 on children's rights, contested by parents' groups when it passed; unguarded `Ley 285 de 2022` tagged two juvenile-crime bills and was dropped. `celular` is Panama's (and most of Latin America's) word for a mobile phone. MEASURED: 4 bills (patria potestad, 8466; parents' associations, 8019; values education, 8023; social-media limits for minors, 8095).

### 7. Free speech, privacy and civil liberties {#7_free_speech_online_safety}

- **Tier 1:** "libertad de expresión"; "delito* de odio"; "discurso* de odio"; "incitación al odio"; "ley mordaza"; "leyes mordaza"; pornograf*; "verificación de edad"; "ciberacoso"
- **Tier 2:** desinformaci*; "noticias falsas"; "libertad de prensa"; "libertad de información"; censura [with: expresión, redes, prensa, internet, libros]; calumnia* [with: injuria, prensa, periodist]; "secreto de las comunicaciones"; "reconocimiento facial"
- **Panama only:** "leyes mordaza"; calumnia* [with: injuria, prensa, periodist]
- **Notes:** criminal `calumnia e injuria` is how Panamanian journalists have been prosecuted, and its decriminalisation recurs. `protección de datos personales` and `derecho a la intimidad` were tried and dropped: they matched debt-collection and court-expert privacy bills. MEASURED: 1 bill (decriminalising calumnia e injuria, 7888, archived).

### 8. Freedom of religion or belief {#8_freedom_of_religion}

- **Tier 1:** "libertad religiosa"; "libertad de culto*"; "libertad de conciencia"; "objeción de conciencia"; "sentimientos religiosos"; blasfemia*; "Santa Sede"; cristianofobia; "persecución de cristianos"; "cristianos perseguidos"; "minorías religiosas"; "minoría religiosa"; "asistencia religiosa"; capellan*
- **Tier 2:** "Iglesia católica"; "Iglesia Católica"; "religión católica"; "Conferencia Episcopal"; "Alianza Evangélica"; "iglesias evangélicas"; "lugares de culto"; "confesiones religiosas"; "organizaciones religiosas"; "entidades religiosas"; "enseñanza religiosa"; "educación religiosa"; "clase de religión"; "símbolos religiosos"; "Día de la Biblia"; "Día Nacional de la Biblia"; "Jornada Mundial de la Juventud"; "abusos" [with: Iglesia, clero, religios]
- **Panama only:** "libertad de culto*"; "Alianza Evangélica"; "Día de la Biblia"; "Día Nacional de la Biblia"; "Jornada Mundial de la Juventud"
- **Notes:** the Constitution speaks of "libertad de cultos" and of Catholic religious teaching in public schools (art. 107), so `enseñanza religiosa` is a live Panamanian term. The Alianza Evangélica was a party to the 2016 fight. A day for the Mama Tata religion of the Ngäbe-Buglé (8500) and a Corpus Christi festival (8389) are left out on purpose. MEASURED: 0.

### 9. Marriage and family {#9_marriage_family}

- **Tier 1:** "matrimonio entre personas del mismo sexo"; "matrimonio igualitario"; "matrimonio homosexual"; "parejas del mismo sexo"; "uniones civiles"; "unión civil"; "Código de la Familia"; "matrimonio infantil"; "matrimonio de menores"; "uniones tempranas"; poligamia; "protección a la familia"; "protección de la familia"; "fortalecimiento de la familia"; "perspectiva de familia"
- **Tier 2:** "unión de hecho"; "uniones de hecho"; natalidad; "licencia de maternidad"; "licencia de paternidad"; "fuero de maternidad"; "custodia compartida"; "guarda y crianza"; divorcio*; "pensión alimenticia"; "pensiones alimenticias"; "familias monoparentales"; "Ley General de Adopciones"; "Ley 46 de 2013"; adopción [with: menores, familia, parejas, niño, niña]; adopciones; "Secretaría Nacional de Niñez, Adolescencia y Familia"; SENNIAF; "Día de la Familia"; acogimiento [with: niños, niñas, adolescentes, familiar]
- **Panama only:** "Código de la Familia"; "fuero de maternidad"; "guarda y crianza"; "Ley General de Adopciones"; "Ley 46 de 2013"; "Secretaría Nacional de Niñez, Adolescencia y Familia"; SENNIAF
- **Notes:** `Código de la Familia`: see the traps above. `guarda y crianza` is Panama's custody term. Maintenance (`pensión alimenticia`) is tier 2 and is four of the area's 13 bills; triage should read and mostly drop them. MEASURED: 13 bills, the largest area (Family Code 4, maintenance 4, adoptions 2, paternity leave 2, children's residential care 1).

### 10. Surrogacy and embryology {#10_surrogacy_embryology}

- **Tier 1:** "gestación subrogada"; "gestación por sustitución"; "maternidad subrogada"; "vientre* de alquiler"; "reproducción asistida"; "reproducción humana asistida"; embrion*; embrión; "fecundación in vitro"; "diagnóstico genético preimplantacional"; clonación; "edición genética"; "células madre embrionarias"
- **Tier 2:** "donación de óvulos"; "donación de gametos"; "donación de semen"; "banco de semen"; "investigación biomédica"; filiación [with: gestación, subrogada, sustitución, reproducción]; "preservación de la fertilidad"; infertilidad
- **Panama only:** none.
- **Notes:** MEASURED: 0.

### 11. Migration {#11_migration}

- **Tier 1:** inmigración; inmigrante*; migrante*; "Servicio Nacional de Migración"; "protección internacional"; asilo; refugiad*; "regularización migratoria"; "flujo* migratorio*"; "migración irregular"; "Crisol de Razas"
- **Tier 2:** migración; migratori*; Darién [with: migra, frontera, selva]; deportaci*; "naturalización"; "carta de naturaleza"
- **Panama only:** "Servicio Nacional de Migración"; "Crisol de Razas"; Darién [with: migra, frontera, selva]; "carta de naturaleza"
- **Notes:** collated, never campaigned, hidden (`HIDDEN_AREAS = (11,)`). The Darién crossing and the Crisol de Razas regularisation programme are Panama's. MEASURED: 1 bill, together with trafficking.

### 12. Prostitution, trafficking and sexual exploitation {#12_prostitution}

- **Tier 1:** prostituci*; proxenetismo; proxeneta*; "trata de personas"; "trata de seres humanos"; "explotación sexual"; "explotación sexual comercial"; "turismo sexual"; "abolición de la prostitución"; "compra de sexo"; "matrimonio* forzado*"; "pornografía infantil"
- **Tier 2:** "trabajo sexual"; "trabajadoras sexuales"; "trabajadores sexuales"; "abuso sexual infantil"; "abuso sexual" [with: menores, niños, niñas, infancia, adolescentes]; "delitos sexuales"; "libertad e integridad sexual"; "integridad y la libertad sexual"; "libertad sexual" [with: delito*, menores]; "sexuales contra" [with: niños, niñas, menores, adolescentes]; "tráfico de personas menores"; "tráfico de menores"; "agresión sexual" [with: menores, infancia]; "material de abuso sexual infantil"; "indemnidad sexual"; "ofensores sexuales"; "violencia sexual" [with: menores, niños, niñas, adolescentes, digital]; grooming
- **Panama only:** "explotación sexual comercial"; "libertad e integridad sexual"; "integridad y la libertad sexual"; "tráfico de personas menores"; "ofensores sexuales"
- **Notes:** the Penal Code's chapter is "delitos contra la libertad e integridad sexual", and the sex-offender register is Ley 244 de 2021. `"sexuales contra"` joined on measurement: the day against sexual violence against children (8381) writes "la explotación, el abuso y la violencia sexuales contra los niños". MEASURED: 12 bills, including the trafficking reform now in force (7525) and the sex-offender register change now in force (7653).

### 13. Organ donation {#13_organ_donation}

- **Tier 1:** "donación de órganos"; "trasplante* de órganos"; "tráfico de órganos"; "turismo de trasplantes"; "donación y trasplante"; "donación de órganos, tejidos"; "componentes anatómicos"
- **Tier 2:** trasplante*; "donante* de órganos"; "muerte encefálica"; "consentimiento presunto"; "donación de sangre"
- **Panama only:** "componentes anatómicos"
- **Notes:** `componentes anatómicos` is the Panamanian statutory phrase for organs and tissues (7936). MEASURED: 1 bill.

### Global exclusions (advisory)

- **Terms:** vida; familia; género; sexo; menores; matrimonio; libertad; religión; educación; odio; mujer; igualdad; trans; niñez

## Proposed phasing

1. **Phase 1 (built, this branch).** segLegis bills with stage histories,
   the orden del día, deputies; Mini-first weekly; unclassified until the
   taxonomy is approved.
2. **Phase 1b, after the taxonomy**: generate it, `--reclassify`, then a
   weekly DM edition (new bills on our ground, stage moves, which of them
   are on the agenda, proponents), as the US edition. The proponent column
   is the nearest thing to a "who" the data offers; party comes from
   `pa_members` by name, which needs a small name-matching step (segLegis
   prints "H.D ALAIN ALBENIS CEDEÑO HERRERA", the deputies list "ALAIN
   ALBENIS CEDEÑO HERRERA").
3. **Phase 2**: committee agendas, monthly plenary attendance PDFs, the
   bill texts for bills on our ground (the PDF is one fixed URL per ficha),
   and the Corte Suprema's constitutional rulings. Recorded votes only if a
   public source appears (see Waiting on Chris).

## Sub-national bodies (later, not probed)

Panama is unitary: no state or provincial legislatures. Below the Asamblea
are 82 municipal councils (concejos municipales), provincial councils
(consejos provinciales, which can propose bills and appear in segLegis as
a proponent type) and the indigenous comarcas' general congresses
(Ngäbe-Buglé, Guna Yala, Emberá-Wounaan and others), which legislate
customary matters. None is a priority.

## Shared files touched (for the merge of the country branches)

- `src/db.py`: five `pa_*` names in `TABLES`, and `pa_store.ensure_schema`
  in `init_db` (10 lines).
- `tools/coverage.py`: `Panama weekly` in `PIPELINES`, `PIPELINE_FEEDS`
  and `AWAITING_FIRST_RUN`; `pa_members`, `pa_bills`, `pa_agenda` in
  `FEEDS` (15 lines).
- `.github/workflows/alert.yml`: `Panama weekly` in the watched list (1 line).

Not touched: `docs/mac-mini.md` (install steps are above instead),
`tools/generate_taxonomy.py`, any taxonomy file.

## Waiting on Chris

1. **Recorded votes.** None are public (finding 1). Options: (a) accept a
   bills-and-agenda edition without votes; (b) ask the Asamblea's Secretaría
   General (or its transparency office, under Ley 6 de 2002) for a public
   export of "Asamblea 507" votes; (c) a watcher on the live press page
   during sittings, which needs a browser and a socket and only ever sees
   the day's votes. Claude recommends (a) now and (b) in parallel. Using
   the app's guest login is not an option we would take.
2. **Approve, amend or reject the Panama term list** above, and choose: one
   shared `taxonomy-es` with a Panama addendum, or a Panama file.
3. **Scope questions** the measurement raised: is family-maintenance law
   (`pensión alimenticia`, 4 bills) our ground? Gender violence and
   femicide (4 of area 5's 5 bills), as asked for Spain? Sterilisation on
   request (7922) under abortion and contraception at tier 2?
4. **Is a thinner edition worth a weekly DM?** 18 bills on our ground in
   twelve months, about one new one every three weeks, plus stage moves.
   An alternative is to fold Panama into a monthly Central America digest
   with its neighbours.
5. **Install the plist on the Mini** (two commands above). Until then the
   GitHub backup runs, unmeasured against this host.
6. **Watchlist entries**: none yet. Any current-term bill the Panama team
   already follows whose title hides it should be added by ficha.

## Decisions of 10 October 2026 (applied at the countries merge)

Recorded in `docs/country-decisions-2026-10-10.md`. Shared: accents fold and non-ASCII letters are word characters in the filter (X3); member positions are stored for every vote (X15); the AI judge stays off (X16).

Applied on the `countries` branch:

- Term list approved (PA2, PA3 family maintenance, PA4 sterilisation tier 2 area 1) and merged into the shared `config/taxonomy-es.yaml` (`docs/keyword-taxonomy-es.md`), loaded for this country's code.
- Weekly moved to Saturday 17:30/21:30 UTC (Portugal holds 16:00).

Later phases and items for Chris (not built at the merge):

- No votes (PA1).
- The watchlist stays empty (PA5 deferred).


## Debate packs (built 10 October 2026, branch `camp-debate-packs`)

A manual command, like the UK and German packs; no scheduled job:

    python3 tools/country_debate_pack.py --country pa --date YYYY-MM-DD --list
    python3 tools/country_debate_pack.py --country pa --date YYYY-MM-DD --item "<bill key>" [--speakers "Name; Name"]
    python3 tools/country_debate_pack.py --country pa --date YYYY-MM-DD --find "<words of the title>"
    python3 tools/country_debate_pack.py --pack data/packs/pa-<date>-<slug> --onside

It writes `data/packs/pa-<date>-<slug>/`: `pack.md` and `checklist.md` in Spanish (the frame is
translated in `src/debatepack_i18n.py`; titles, names and positions stay the source's own words),
`members.csv`, `pack.json`, and an English `README.md`. It reads the store only (the item through
this country's edition classification, votes by ID), fetches nothing and calls no AI. No member-level votes are collected here, so a pack holds the item and the agenda slot only, and says so.
Agenda slot: not collected for this country yet; the pack says so. Likely speakers: no source here publishes a speakers' list ahead, so they are named by
hand with `--speakers` (matched to the member list) once known. Placements come only from
readings confirmed in `config/pa_stance.yaml`; none is confirmed yet, so every pack shows
"pendiente de firma" (awaiting sign-off) and places nobody. See docs/debate-pack-social.md, "New
countries".
