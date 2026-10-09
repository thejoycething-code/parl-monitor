# Paraguay: scoping the Congreso Nacional monitor

Probed live on 9 October 2026 from the laptop, with the repo's honest UA
(`CitizenGO-ParlMonitor/1.0 (contact: cjoyce@citizengo.net)`), one request
at a time, about one a second. Every number below was measured. Raw
responses are archived under `data/raw/2026-10-09/py-probe_*` (41 files,
1.3 MB, gitignored like the rest of `data/raw`). The taxonomy figures are
reproducible offline with `python3 tools/py_measure.py` (`--list` prints
every match).

## Decisions already taken (Chris)

- Own edition, delivered to Chris alone by Slack DM, like the US.
- Shared taxonomy concept; no existing taxonomy file is edited. Spanish
  terms are PROPOSED below for approval.
- National parliament first; regional bodies listed only.
- Mac Mini first, GitHub Actions as backup. No paid services. Never post
  publicly.

## The findings that shape everything

### 1. The only live source, SILpy, disallows all robots

`https://silpy.congreso.gov.py/robots.txt` redirects to `/web/robots.txt`,
which reads in full:

```
User-agent: *
Disallow: /

User-agent: Googlebot
Allow: /

User-agent: Googlebot-Image
Allow: /
```

SILpy (Sistema de Información Legislativa, run by the Senate's DGTIC) is
where every live record of the Paraguayan Congress is: bills
(`expedientes`), recorded votes with every member's position, sessions,
committees, members, laws and three RSS feeds. The Senate's and the
Chamber of Deputies' own sites link into it for session results rather than
publish their own (the Senate's "Resultado de sesiones" page is a list of
links to `silpy.congreso.gov.py/sesion/<id>`).

This repo obeys robots.txt (ourcommons search is not used because robots
forbids it; Manitoba was put to Chris before building). A blanket
`Disallow: /` for every agent except Google's is the publisher saying no to
automated collection, so **no collector has been built against SILpy**.
This is the blocker, and the first item in "Waiting on Chris".

**Disclosure:** about 80 requests went to SILpy on 9 October before its
robots.txt was read (home page, the three RSS feeds, 8 vote listings, 2
vote pages, 43 expediente pages for an ID-density sample, and a few search
form attempts). None were made after it was read. Everything those
requests returned is archived and used below only to describe the source
and measure the taxonomy; nothing is stored in the database.

### 2. The open-data API is open but frozen, and has no votes

`https://datos.congreso.gov.py/opendata/api/data/` (CC BY 4.0, no key, no
robots.txt: 404) is the Congress's 2014-16 open-government API. It works,
and it stopped being fed:

| Endpoint | Measured |
|---|---|
| `proyecto?offset=<page>&limit=<n>` | `offset` is a PAGE number (1-based), `limit` up to at least 1000 (1000 rows, 700 KB, 5-15 s). The listing tops out at idProyecto 129338, entered **31 May 2023**. |
| `proyecto/{id}` | Single records exist up to about **130100 (29 January 2024)**; 130150 and every later ID tried (up to the live 159392) return the HTML error page with HTTP 200. Today's bills are around 159,400. |
| `proyecto/{id}/tramitaciones`, `/autores`, `/dictamenes`, `/adjuntos`, `/detalle` | Work for frozen records; their stages are as of the freeze (130100 still "DICTAMEN DE COMISIÓN"). |
| `proyecto/total` | HTML error page. |
| `ley/anho/{year}` | 174 laws for 2021, 155 for 2022, 138 for 2023, **0 for 2024 and 2025**. |
| `parlamentario/camara/{S,D}` | 45 senators, 80 deputies, all "2023-2028", with party, bancada, department, email, photo. Frozen too: 5 of the 45 senators on a September 2026 vote page are not in it. Its `idParlamentario` is SILpy's `legislador` ID (the other 40 match exactly). |
| `sesion/camara/{S,D}` | `[]` |
| votes | **No endpoint.** The API never published votes. |

Errors come back as an HTML page with HTTP 200, never as JSON or a 4xx, so
a client must check the content type.

The API is good for history (October 2020 to May 2023 in the six pages
pulled) and for the member roster with a replacement check, and useless for
a weekly monitor.

### 3. The English taxonomy is blind to Paraguay

`config/taxonomy.yaml`, run as is over both corpora: **0 of 1,164 recorded
votes and 0 of 6,000 expedientes matched any area.** As in Germany and
Spain, an English term list collects everything and sees nothing.

### 4. Little of the Congress's recorded business touches our ground

Even in Spanish, at title level, CitizenGO ground is thin (figures in
"How much touches CitizenGO's ground" below): 10 of the 812 expedientes
voted on by name since July 2023, almost all tier 2, and none of them on
abortion, gender identity in schools or the Transformación Educativa plan.
The education and gender fights show up instead in **declarations and
pedidos de informe** (Art. 192 requests for information), which never go
to a recorded vote.

## What SILpy publishes (described from the pre-robots probe)

All JSF/PrimeFaces 13 pages, server-rendered HTML, bookmarkable GET URLs,
no login, no CAPTCHA, no WAF seen. Each page is 55-220 KB and took 1.3-2.4 s.

- **Recorded votes, list:** `/web/votaciones/<S|D>/<idPeriodoParlamentario>`
  (the form at `/web/votaciones` POSTs and redirects to this). Periods
  (1 July to 30 June): 100267 = 2026-27 (current), 100257 = 2025-26,
  100237 = 2024-25, 100217 = 2023-24, back to 1968. Every vote of the
  period on one page, no pagination:

  | Period | Senate | Deputies |
  |---|---|---|
  | 2026-27 (to 7 Oct) | 13 | 54 |
  | 2025-26 | 73 | 204 |
  | 2024-25 | 92 | 278 |
  | 2023-24 | 121 | 329 |

  1,164 votes on 812 distinct expedientes. Each row: vote ID, the motion
  ("La Presidencia somete a votación electrónica ..."), result, a result
  line, date, session ID and name, expediente type, acápite (the bill's
  title-summary), expediente number (`S-2603407`) and SILpy ID, status and
  stage. Only electronic or nominal votes are recorded; show-of-hands
  decisions are not.
- **Recorded vote, detail:** `/web/votacion/<id>`. Totals (SI, NO,
  ABSTENCIÓN/BLANCO, AUSENTE, NO VOTA, TOTAL) and **every member's
  position**, each linked to `/web/legislador/<id>`, plus the signed PDF of
  the electronic board. Measured: 45 rows on Senate vote 109386 (11-14-1,
  12 absent, 7 not voting), 80 on Deputies vote 109345.
- **Expediente:** `/web/expediente/<id>`. Type, number, acápite, status,
  stage, entry date, origin, initiative, urgency, full tramitación (each
  step with chamber, stage, session and result), committee opinions,
  resolutions, documents (PDF) and links to its votes. **A missing ID
  returns HTTP 500** (a 26 KB error page), not 404. Near the top of the
  range, 14 of IDs 159380-159420 existed; IDs are not in date order
  (D-2675733 sits among D-26957xx).
- **RSS:** `/web/FeedRss?opcionRSS=1` (bills entered), `=2` (laws), `=3`
  (executive vetoes). Ten items each; feed 1 spanned 18 September to
  7 October 2026, so a weekly reader would miss items in a busy week.
- **Search:** the expediente search form returned HTTP 500 to every scripted
  POST tried (with and without the session cookie and the AJAX headers).
- **Sessions, committees, agenda, members, bancadas, public hearings:**
  `/web/sesiones/<S|D>/<period>`, `/web/comisiones/...`, `/web/legislador/<id>`.

### Allowed by robots, but not a substitute

- **diputados.gov.py** (robots: allow all): agenda, Diario de Sesiones
  (session transcripts, PDF, a concrete5 file list), bancada lists (PDF).
  No vote records found; its session links point to SILpy.
- **senado.gov.py** (Joomla; robots blocks only system folders): orden del
  día, asuntos entrados and session results, each a list of SILpy links.
- **bacn.gov.py** (Biblioteca y Archivo Central del Congreso; robots allows
  all, sitemap published): law texts. Not probed further.

## Context: is an edition worth it?

Paraguay is a working, if one-party-dominant, presidential democracy.
Congress is bicameral: 45 senators elected nationally and 80 deputies by
department, five-year terms, current term 2023-2028. The Asociación
Nacional Republicana (Colorado) holds a majority in both chambers (24 of
45 senators, 48 of 80 deputies in the open-data roster) alongside President
Santiago Peña. Opposition voices exist and vote; the Senate's expulsion of
opposition senator Kattya González in February 2024 is the usual example
cited about the majority's use of its numbers. Congress is independent
enough to monitor.

Paraguay's settled law already sits largely where CitizenGO does: the
Constitution protects life "desde la concepción" (art. 4) and defines
marriage as between a man and a woman; MEC Resolution 29664 (2017) barred
"teoría de género" materials from schools. The fights are therefore about
defending that position: school curriculum and the Plan Nacional de
Transformación Educativa 2040 (measured below: a 2022 declaration urging the
MEC to stop designing it, a pedido de informe on the plan and "ideología de
género", a pedido on implementation of Resolution 29664, one on the MEC's
"mesa técnica de padres"), international commitments, and violence-against-
women legislation that carries gender language.

**Recommendation:** worth a small edition IF access is cleared, because
the vote data is unusually good (every member, every recorded vote, clean
HTML, IDs throughout) and cheap to collect (about 120 pages a year).
Without SILpy there is nothing current to collect, and I recommend no
edition rather than one built on the frozen API.

## How much touches CitizenGO's ground

Corpora: VOTES = the 1,164 recorded votes 2023-2027 (motion, result and
acápite); BILLS = 6,000 expedientes from the API, October 2020 to May 2023,
all types (3,087 pedidos de informe, 1,284 bills, 1,234 declarations, 216
resolutions, the rest agreements and authorisations). Proposed terms below,
text and terms accent-folded.

| | Votes 2023-27 | Bills 2020-23 |
|---|---|---|
| English taxonomy, any area | 0 | 0 |
| Proposed Spanish, any area | 16 votes | 67 |
| ... on our ground (area 11 hidden) | 15 votes, **10 expedientes** | **45** |
| area 1 abortion | 0 | 3 |
| area 2 assisted dying | 1 | 2 |
| area 5 sex-based rights | 2 | 10 |
| area 6 parental rights and education | 0 | 4 |
| area 7 free speech | 3 | 7 |
| area 8 religion | 1 | 5 |
| area 9 marriage and family | 2 | 4 |
| area 12 trafficking and exploitation | 2 | 10 |
| area 13 organ donation | 0 | 4 |
| area 11 migration (hidden) | 1 | 23 |

The voted ten: palliative care for the terminally ill (D-2372478, two
votes), the women and girls violence emergency bill (S-2300232), a
feminicide-law amendment, the Deputies' rule change on the gender equality
committee, data protection, data retention against child pornography,
criadazgo (child domestic servitude), two breast-milk and lactation bills,
the Día Nacional de la Iglesia Evangélica (S-2603870, approved 22 September
2026) and an award citing freedom of expression. No recorded vote touched
abortion, gender identity, sex education or Transformación Educativa.

The tier-1 hits in BILLS are the ones a campaigner would want: 121879
(2020, urges Foreign Affairs to lead a "core group pro vida y pro familia"
and a declaration on parental rights), 125672 (2022, register of deaths of
"concebidos no nacidos"), 126680 (2022, stop designing the Transformación
Educativa plan), 127033 (2022, Plan 2040 and "ideología de género"), 127284
(2022, Resolution 29664), 128194 (2023, a national day for "personas
trans"), 125088 (2022, "Son niñas, no madres" report).

Precision traps found: `Concepción` is a department and its capital, so
"concepción" never stands alone; "Secretaría de Desarrollo para
Repatriados y Refugiados Connacionales" is about returning Paraguayans
(vetoed in `refugiad*`); "medidas paliativas" turned up in agriculture
(bare `paliativ*` dropped); "Ministerio de la Mujer" tagged requests on
drugs policy and urban crime (dropped); "objeción de conciencia" also
names the military-service objection law (124877).

## Proposed Spanish terms (v0.1, for Chris's approval)

Written unaccented: SILpy text is mostly upper case with inconsistent
accents ("MINISTERIO DE EDUCACION Y CIENCAS"), so both sides should be
folded. **The shared filter does not fold accents**; Peru's collector folds
before matching, Spain's list carries accents. The merged `taxonomy-es`
needs one rule, and I recommend folding. `*` is the stem wildcard; `[with:
...]` is a guard, `[without: ...]` a veto. **(PY)** marks Paraguay-specific
terms; everything else is shared Spanish for merging with Spain, Peru,
Argentina, Mexico and the rest. Terms marked *verify* are from memory, not
measured, and need a Paraguayan reader. The live list is `PROPOSED` in
`tools/py_measure.py`.

**1 Abortion.** T1: aborto*, abortiv*, interrupcion voluntaria del
embarazo, interrupcion legal del embarazo, interrupcion del embarazo, por
nacer, no nacido*, vida desde la concepcion, desde la concepcion, derecho a
la vida [with: concepcion, nacer, embarazo, aborto, gestacion], provida, pro
vida, misoprostol, mifepristona, pildora del dia despues, pildora del dia
siguiente, objecion de conciencia [with: aborto, salud, medic, sanitari],
consenso de ginebra. T2: salud sexual y reproductiva, derechos sexuales y
reproductivos, derechos reproductivos, embarazo adolescente, embarazo
infantil, embarazo* precoz*, no madres [with: ninas] (PY/PE "Son niñas, no
madres"), anticoncepci*, anticonceptiv*, planificacion familiar, duelo
gestacional, muerte perinatal, embarazada* [with: apoyo, vulnerab,
proteccion integral].

**2 Assisted dying.** T1: eutanasi*, suicidio asistido, suicidio
medicamente asistido, muerte digna, muerte asistida, ayuda para morir,
homicidio motivado por suplica (PY, Penal Code, *verify*). T2: cuidados
paliativos, medicina paliativa, voluntades anticipadas, testamento vital,
final de la vida, fin de la vida, enfermedades terminales, prevencion del
suicidio.

**3 Gender medicine and children.** T1: bloqueador* de la pubertad,
bloqueador* puberal*, hormonizacion, terapia hormonal cruzada, hormonas
cruzadas, disforia de genero, incongruencia de genero, menores trans, ninez
trans, infancias trans, reasignacion de sexo, reasignacion sexual,
afirmacion de genero, detransici*, cambio de sexo [with: menor, nino, nina,
adolescente]. T2: transicion de genero [with: menor, nino, nina,
adolescente], tratamiento hormonal [with: menor, adolescente, genero, trans].

**4 Conversion practices.** T1: terapia* de conversion, terapias
reparativas, ECOSIEG, esfuerzos de cambio de orientacion sexual, practicas
de conversion.

**5 Sex-based rights and gender ideology.** T1: ideologia de genero, teoria
de genero (PY usage: the word Resolution 29664 uses), identidad de genero,
expresion de genero, identidad autopercibida, personas trans, transgenero*,
transexual*, no binari*, LGBT*, LGTB*, LGBTI*, LGTBI*, 29664 [with:
educacion, MEC, genero] (PY, MEC Resolution 29664/2017). T2: enfoque de
genero, perspectiva de genero, igualdad de genero, equidad de genero,
razones de genero, violencia de genero, feminicidio*, femicidio*, Ley 5777
and Ley N 5777 (PY, the 2016 law on violence against women), orientacion
sexual, diversidad sexual, lenguaje inclusivo, Belem do Para, CEDAW,
paridad.

**6 Parental rights and education.** T1: derecho de los padres, derechos de
los padres, derechos parentales, derecho preferente de los padres,
educacion sexual integral, educacion integral de la sexualidad, educacion
sexual, marco rector pedagogico (PY, the withdrawn 2010-11 sex-education
framework, *verify*), transformacion educativa (PY), plan nacional 2040
[with: educa, MEC, transformacion] (PY), PNTE (PY), con mis hijos no te
metas, homeschooling, educacion en casa, educacion en el hogar, libertad de
ensenanza. T2: padres de familia, mesa tecnica de padres (PY), patria
potestad, malla curricular [with: genero, sexual, valores, familia],
curricul* [with: genero, sexual, valores, familia, religio], materiales
educativos [with: genero, sexual], textos escolares, redes sociales [with:
menores, ninos, ninas, adolescentes].

**7 Free speech and online safety.** T1: libertad de expresion, discurso*
de odio, delito* de odio, incitacion al odio, censura previa, pornograf*,
verificacion de edad. T2: libertad de prensa, libertad de informacion,
desinformacion, noticias falsas, censura [with: expresion, redes, prensa,
internet], proteccion de datos personales, ciberacoso.

**8 Freedom of religion.** T1: libertad religiosa, libertad de culto,
libertad de conciencia, objecion de conciencia, entidades religiosas,
confesion* religios*, educacion religiosa, simbolos religiosos, persecucion
religiosa, cristianos perseguidos, minorias religiosas. T2: iglesia
catolica, conferencia episcopal (PY: Conferencia Episcopal Paraguaya), santa
sede, iglesia evangelica (PY, measured), lugares de culto, instituciones
religiosas, capellan*.

**9 Marriage and family.** T1: matrimonio igualitario, matrimonio entre
personas del mismo sexo, matrimonio homosexual, union civil, uniones
civiles, adopcion homoparental, proteccion de la familia, proteccion
integral de la familia, pro familia, profamilia, familia natural. T2:
divorcio*, union* de hecho, familias numerosas, natalidad, licencia por
maternidad, licencia de paternidad, permiso de paternidad, lactancia
materna, Ley 5508 (PY, maternity and breastfeeding law), Ministerio de la
Familia, dia de la familia.

**10 Surrogacy and embryology.** T1: gestacion subrogada, maternidad
subrogada, vientre* de alquiler, gestacion por sustitucion, reproduccion
humana asistida, tecnicas de reproduccion asistida, fecundacion in vitro,
clonacion. T2: reproduccion asistida, embrion*, donacion de gametos,
donacion de ovulos. (Nothing measured.)

**11 Migration (collated, never campaigned).** T1: migracion, migraciones,
migrante*, inmigra*, refugiad* [without: connacionales, repatriados] (PY
veto), asilo [with: politico, refugi, proteccion internacional] ("asilo de
ancianos" is an old people's home), Ley 6984 (PY migration law, *verify*).
T2: migratori*, extranjeros [with: radicacion, expulsion, migra],
deportaci*.

**12 Prostitution, trafficking and exploitation.** T1: trata de personas,
trata de seres humanos, Ley 4788 (PY, 2012 trafficking law), prostituci*,
proxenetismo, proxeneta*, explotacion sexual, pornografia infantil,
material de abuso sexual infantil. T2: abuso sexual infantil, abuso sexual
[with: nino, nina, menor, adolescente], criadazgo (PY), agresores sexuales
(PY: Ley 6572/2020 register), turismo sexual.

**13 Organ donation.** T1: donacion de organos, trasplante* de organos,
trafico de organos, donante* de organos, Ley Anita (PY, presumed-consent
law, *verify*), donacion presunta, consentimiento presunto. T2: trasplante*,
ablacion y trasplante (PY: the national transplant institute).

**Global exclusions:** vida, familia, genero, sexo, menores, matrimonio,
libertad, religion, educacion, odio, mujer, igualdad, trans, and for
Paraguay concepcion (a department), trata ("se trata de"), asilo, and
Ministerio de la Mujer.

## Phase plan

**Phase 0 (done, this branch):** this document and the offline measurement
script. No store tables, no job.

**Phase 1 (on clearance, about a day's work).** `tools/py_rollcalls.py`,
`src/py_store.py`, `config/watchlist-py.yaml`, fixtures from the archived
probe pages, tests, and the Mini-first weekly job (`jobs/py-weekly.sh`,
launchd plist, `.github/workflows/py-weekly.yml` gated with `PY_WEEKLY`) on
the Australia pattern:

- read the current period's two vote listings (2 pages), fetch only vote
  pages not yet stored (about 2-5 a week), store every position keyed on
  SILpy's vote ID and legislador ID; party per vote from the member's
  bancada;
- fetch each voted expediente's page (keyed on SILpy's expediente ID, the
  `S-`/`D-` number kept beside it, never the acápite) for stage and status;
- members from the open-data roster, topped up from `legislador` pages for
  replacements;
- first run back-fills 2023-24 onward: 8 listing pages, 1,164 vote pages
  and 812 expedientes, about 35 minutes at one request a second;
- classification with the approved Spanish taxonomy plus the watchlist by
  expediente ID. A missing page answers HTTP 500, which `src/http.py`
  retries once: the collector should treat a 500 on a known-good URL as a
  gap and never walk unknown IDs.

**Phase 2:** new bills between votes. RSS feeds (ten items) are not
enough; either a bounded walk above the highest ID seen (about 75 new
expedientes a week, with one HTTP 500 per missing ID, roughly two misses
per hit) or the search, if the Senate's DGTIC can say how to call it.
Pedidos de informe and declarations are where the education fight is
visible, so phase 2 matters more here than in most countries.

**Later:** agenda (SILpy sesiones, the chambers' orden del día), committee
opinions, laws via BACN.

**Regions (not probed):** 17 departmental boards (Juntas Departamentales)
and about 260 municipal councils (Juntas Municipales), Asunción's the
largest. **Courts:** the Supreme Court's Constitutional Chamber hears
unconstitutionality actions and is the likely channel for any challenge to
Resolution 29664 or to education policy. No national referendum channel in
practice.

## Shared files touched

None. This branch adds only `docs/paraguay-scope.md` and
`tools/py_measure.py` (offline, reads only the archive, writes nothing).

## Waiting on Chris

1. **SILpy access.** Its robots.txt disallows every agent but Google's.
   Options: (a) write to the Senate's Dirección de Sistemas y Seguridad
   Informática (DGTIC-HCS, which runs SILpy) or the Congress's open-data
   office asking permission for a weekly, throttled, identified collector,
   about 10-20 pages a week, or asking them to resume the open-data API
   (which already has the right shape and lacks only votes and fresh
   data); (b) decide the edition is not worth it; (c) collect anyway,
   which this repo has not done before and I do not recommend. Phase 1 is
   ready to build the day this clears.
2. **Approve, cut or amend the Spanish terms** above, ideally after a
   Paraguayan reader checks the *verify* items, and decide whether
   `taxonomy-es` matches accent-folded (my recommendation) for all Spanish
   editions.
3. **Scope of tier-2 violence-against-women terms** (feminicide, Ley 5777,
   violencia de género): they are most of area 5's Paraguayan hits, as in
   Spain.
4. **Whether pedidos de informe and declarations count** for this edition.
   They are 72% of expedientes and carry the education and pro-life signals
   that recorded votes never do; they need phase 2 collection.
5. **Watchlist seeds** (expediente IDs) once access is cleared: 127033 and
   126680 (Transformación Educativa), 127284 (Resolution 29664), 121879
   (pro vida y pro familia core group), 128194 (personas trans day).
