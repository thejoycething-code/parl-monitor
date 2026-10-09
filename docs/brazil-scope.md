# Brazil: scoping the National Congress monitor

Probed live on 9 October 2026, from the laptop, through `src/http.py` (the
CitizenGO User-Agent, a one-second throttle, retries) or, for three large
files, curl with the same User-Agent. Every number below was measured, not
estimated. Raw responses are archived under `data/raw/2026-10-09/`
(`br-probe_*`, about 24 MB, gitignored like the rest of the raw tree).
National Congress first (Câmara dos Deputados and Senado Federal); the state
assemblies are listed at the end and are a later decision.

## Decisions already taken (Christopher, before this scope)

- **Own edition**, delivered to Christopher alone (Slack DM), as the US is.
- **Shared taxonomy concept, separate term file.** The areas are CitizenGO's
  and do not change; the Portuguese terms are proposed below and become
  `config/taxonomy-pt.yaml` only after Christopher approves them. No existing
  taxonomy file is touched.
- **Congress first**, state assemblies later.
- **Mac Mini first, GitHub Actions as backup**, as the Australia weekly does.
  No new paid services. Nothing is ever posted publicly.

## The finding that shapes everything

**The English taxonomy is blind to Portuguese**, exactly as it was to German.
`config/taxonomy.yaml`, unchanged, run over the Câmara's own records:

| Corpus | English taxonomy | Draft Portuguese list (below) |
|---|---|---|
| Câmara bills of 2025-26 (PL, PEC, PLP, PDL, MPV, PRC: 14,443) | 20 | 705 (366 at tier 1) |
| Câmara nominal votes, 2023 to 2026 (1,597) | 0 | 48, on 28 measures |
| Senado bills of 2025-26 (PL, PEC, PLP, PDL: 1,990) | 1 | 43 |
| Senado nominal votes, 2025-26 (187) | 0 | 1 |

So the expected "high volume" is real on the **bill** side (about 5% of all
Câmara bills, some 30 a month), and thin on the **vote** side. Of the 1,125
plenary nominal votes in the Câmara since February 2023, the draft list finds
17; of the 1,597 nominal votes in plenary and committee together, 48. Most of
the Câmara's fight on our ground happens in committees (CCJC, the family
committee CPASF, the human rights committee CDHMIR) and in bills that are
filed and never voted.

The vote side is thin for a structural reason, not a vocabulary one:
**both houses decide almost everything by symbolic vote**, which records no
member's position. Measured:

| | Votações (all) | Nominal | Of which plenary |
|---|---|---|---|
| Câmara 2023 | 10,851 | 447 | 300 |
| Câmara 2024 | 10,373 | 448 | 273 |
| Câmara 2025 | 13,827 | 550 | 429 |
| Câmara 2026 (to 3 September) | 7,360 | 152 | 123 |
| Senado 2025 | | 128 | 128 (72 secret ballots) |
| Senado 2026 (to 8 October) | | 59 | 59 (40 secret ballots) |

A Senate secret ballot (authorities: ambassadors, judges, agency heads) says
only who voted (`Votou`), not how. Of the Senate's 187 nominal votes in
2025-26, 86 are nominations (MSF) and 24 are external-credit authorisations
(OFS); 7 are on a PL.

**And the vote's own text is useless on its own.** Matched on the vote's
description alone, the draft list finds 0 of 1,597 Câmara votes: descriptions
read "Aprovado o Parecer" or "Rejeitado o Requerimento de Retirada de Pauta".
A vote means something only when joined to the proposição it is about, and
the bill's **keywords** carry what its ementa leaves out (PL 1904/2024 cites
only "arts. 124 to 128 of the Penal Code"; its Câmara keywords say "aborto
provocado, aborto legal, estupro"). That is the Westminster rule again: key
on the bill, never on the title, and here the vote often has no title at all.

## What Brazil publishes

### Câmara dos Deputados: Dados Abertos API v2 (open, no key) -- WORKS TODAY

`https://dadosabertos.camara.leg.br/api/v2`, JSON (XML on request). No key,
no registration. Every response carries `retry-after: 30` and
`cache-control: max-age=1800`; 250 consecutive requests at one a second (the
vote-to-bill join below) drew no refusal, about 1.1 s each.

- **Votações** `/votacoes?dataInicio&dataFim&itens&pagina`. `itens` is
  capped at **100 silently** (asking for 200 gives 100). The date window is
  limited: four months answered, six months gave **HTTP 400**. Pages beyond
  the last return an empty list, not an error. The list has no totals, so it
  cannot tell a nominal vote from a symbolic one without a request per vote.
- **Votos** `/votacoes/<id>/votos`: every deputy's position on one vote,
  with **party and state at the vote** and the deputy's ID. Only deputies
  who registered appear (396 rows on a 513-seat vote; absence is implicit).
  Positions as printed: Sim, Não, Abstenção, Obstrução, Artigo 17 (the
  presiding officer), and a null `tipoVoto` for a registered deputy who cast
  none. A symbolic vote returns an empty list.
- **Orientações** `/votacoes/<id>/orientacoes`: how each party leader, the
  Government and the Opposition told their bench to vote. Leaders' blank
  orientations are common; bloc names are truncated by the Câmara itself
  ("Solidaried"). This is a whip signal Westminster publishes nowhere.
- **Proposições** `/proposicoes`, `/proposicoes/<id>`,
  `/proposicoes/<id>/tramitacoes` (PL 1904/2024: 15 steps),
  `/proposicoes/<id>/votacoes`, `/proposicoes/<id>/temas` (the Câmara's
  own 40-odd topic vocabulary). The detail record carries `ementa`,
  `ementaDetalhada`, `keywords` (indexing terms), status and full-text URL.
  A `keywords=` search exists but is loose (18 hits for "aborto" since 2025).
- **Deputados** `/deputados?itens=1000`: the 513 in office in one call
  (PL 98, PT 65, União 52, PSD 48, PP 46, Republicanos 42, MDB 38, ...).
  `idLegislatura=57` lists everyone who sat this legislature (9 pages).
- **Agenda** `/eventos?dataInicio&dataFim` and `/eventos/<id>/pauta` (36
  events in the sitting week of 31 August 2026; each pauta lists the
  proposições to be taken, with rapporteur and a link to the vote). Only 4
  events are listed for 5-16 October 2026: the House is in its election
  recess.

### Câmara bulk files (open, no key) -- WORKS TODAY, the better route for votes

`https://dadosabertos.camara.leg.br/arquivos/<set>/json/<set>-<year>.json`,
rebuilt **daily** (Last-Modified between 04:00 and 07:20 UTC on 8 October).

| File (2026) | Size | Rows |
|---|---|---|
| votacoes | 8.2 MB | 7,360 votações, **with yes/no/other totals** |
| votacoesVotos | 31.8 MB | 51,832 positions |
| votacoesProposicoes | 4.3 MB | 5,677 vote-to-bill links |
| votacoesOrientacoes | 0.7 MB | 1,859 orientations |
| proposicoes | 71.3 MB | 45,413 records of every type (2025: 165 MB, 107,587) |
| proposicoesTemas | 6.3 MB | 25,133 |
| proposicoesAutores | 30.2 MB | |
| deputados | 3.6 MB | 7,889 (every deputy since 1826) |

**Quirk: the server drops large uncompressed downloads.** `proposicoes-2026`
failed four times with `IncompleteRead` after about 18 MB through
`src/http.py`; `votacoesVotos` (32 MB) took 120 s. The same server honours
`Accept-Encoding: gzip`: `proposicoes-2026` then came as 6.0 MB in 10 s.
`src/http.py` does not ask for gzip, and this edition does not change a
shared module, so the collector uses the small files (votacoes,
votacoesProposicoes, votacoesOrientacoes) and asks the API for the
positions of each nominal vote (one request per vote, 450-550 a year).
Adding gzip to `src/http.py` would make the bill layer cheap; see Waiting on
Chris.

**Quirk: the yearly proposições file mixes years.** `proposicoes-2026`
holds PL 1051/2026, presented in 2005: an old bill that took a new number
(see the renumbering quirk below).

### Senado Federal: Dados Abertos (open, no key) -- WORKS TODAY

`https://legis.senado.leg.br/dadosabertos`. Old services answer XML by
default and JSON with a `.json` suffix; the newer ones answer JSON.
`cache-control: max-age=900`. No key.

- **Votações** `/votacao?dataInicio&dataFim` (new service, JSON list):
  **every nominal vote with every senator's position in one call**, plus the
  matter (`sigla`, `numero`, `ano`, `ementa`, `codigoMateria`) and the
  session record. A whole year in one request (2025: 128 votes, 10,368
  positions, 34 s); **two years gave HTTP 400**. Totals are null in the
  Senate's own record and must be counted. Position codes as printed: Sim,
  Não, Abstenção, P-NRV (present, did not vote), AP, LS, LP, MIS, NCom, NA,
  "Presidente (art. 51 RISF)", and Votou on secret ballots.
- The older `/plenario/lista/votacao/<from>/<to>.json` answers the same
  ground in the v2 XML-shaped JSON (137 KB for August-October 2026).
- **Senadores** `/senador/lista/atual.json`: 81 in office, with party, state
  and bloc (4.6 s).
- **Processos** `/processo?sigla=PL&ano=2026` (JSON; 502 PLs of 2026 in the
  Senate, 10.9 s) and `/processo/<id>` (situation, autuações, the deliberation
  record, the originating Câmara process). No indexing terms in the list.
  The older `/materia/pesquisa/lista.json` still answers; **`/materia/tramitando.json`
  took 98 s**, so avoid it in a schedule.
- **Agenda** `/plenario/agenda/mes/<yyyymmdd>.json`: the month's plenary
  sessions with their pauta and speakers (5 October 2026: "Sessão não
  realizada", the election week).

### Keys, and the renumbering quirk

- **Since 2019 both houses share one numbering**: a bill keeps its number
  (PL 2630/2020, PLP 124/2022) as it crosses. Before 2019 they numbered
  separately, so pre-2019 Senate matters are keyed `SF ...` here.
- **An older Câmara bill takes a NEW number when it reaches the Senate, and
  the Câmara's own record then shows the new one.** Measured:
  `proposicoes?siglaTipo=PL&numero=3179&ano=2012` (the 2022 homeschooling
  bill) returns nothing; its Câmara ID 534328 now reads **PL 1338/2022**.
  The Câmara ID does not change, so the collector keys on the printed
  number, stores the Câmara ID beside it, and renames a bill in place when
  the same ID turns up under a new number. The watchlist must be re-keyed by
  hand when that happens (the collector logs every rename).
- A vote's ID (`2611313-31`) is the ID of the proposição it was registered
  under plus a sequence. That proposição is often an urgency request (REQ),
  not the bill: 25 of 152 nominal votes in 2026 were registered under
  something other than their linked bill. The collector takes the bill from
  `votacoesProposicoes`, preferring PEC, PLP, PL, MPV, PDL over a REQ.

## How many items touch CitizenGO's ground

With the draft Portuguese list below (measured on the Câmara's bills
presented in 2025 and 2026, matched on ementa + ementaDetalhada + keywords):

| Area | Bills, 2025-26 |
|---|---|
| 1 Abortion | 38 |
| 2 Assisted dying | 7 |
| 3 Gender medicine (children) | 5 |
| 4 Conversion practices | 1 |
| 5 Sex-based rights / gender ideology | 139 |
| 6 Parental rights and education | 151 |
| 7 Free speech and online safety | 228 |
| 8 Freedom of religion | 51 |
| 9 Marriage and family | 43 |
| 10 Surrogacy and embryology | 10 |
| 12 Prostitution, trafficking, pornography | 151 |
| 13 Organ donation | 20 |
| **Bills on our ground (one bill can carry several areas)** | **705 of 14,443** |

The nominal votes on our ground (48 since 2023) fall on 28 measures, led by
PEC 5/2023 (tax immunity for religious organisations, 8 votes), PL 7292/2017
and PL 3224/2024 (4 each), PL 1329/2024 (3), PL 580/2007 (same-sex unions),
PEC 164/2012 (life from conception, CCJC 2024) and PL 4322/2024.

Two terms were measured, found noisy and already tightened in the proposal:
"inteligência artificial" (190 bills, almost none ours: dropped) and
"plataformas digitais" (141, mostly gig-economy labour law: now guarded to
content, children or moderation, 62). "união estável" (30, mostly inheritance
and divorce) is guarded to same-sex and polyamorous unions.

## Proposed Portuguese terms (for Christopher's approval)

An AI first draft, to be read by a Brazilian campaigner before anything is
scored against it, exactly as the German list was. Conventions are the
English file's: `*` is a stem (inside a phrase it means "this word
inflects"), `{term, with: [...]}` needs a guard word in the same text,
all-caps acronyms match case-sensitively. **The filter does not fold
accents**: "gênero" and "genero" are different strings. The Câmara and
Senate write correct accents, so the terms carry them; a source that
strips accents (some state assemblies do) would need folding first.

Once approved, the list goes into `docs/keyword-taxonomy-pt.md` and
`tools/generate_taxonomy.py --lang pt` (one line added to its MASTERS)
generates `config/taxonomy-pt.yaml`. The collector reads that file the day
it exists, with no code change; then `--reclassify` (or the workflow's
reclassify input) re-derives every stored row.

**1 Abortion.** Tier 1: aborto\*, abortamento\*, abortiv\*, nascituro\*,
interrupção voluntária da gravidez, interrupção da gravidez, interrupção da
gestação, interrupção de gravidez, interrupção de gestação, desde a
concepção, assistolia fetal, mifepristona, misoprostol, Cytotec, ADPF 442,
bolsa estupro, anencefal\*. Tier 2: direitos reprodutivos, saúde
reprodutiva, direitos sexuais e reprodutivos, {vida intrauterina, with:
proteção, direito}, feto\*, fetal, nidação, pílula do dia seguinte,
contracepção de emergência, gestação/gravidez decorrente de estupro, Dia do
Nascituro. (ADPF 442 is the Supreme Court case on decriminalisation to 12
weeks; "bolsa estupro" is the campaigners' name for the Estatuto do
Nascituro's support payment.)

**2 Assisted dying.** Tier 1: eutanásia\*, suicídio assistido, morte
assistida, morte digna, distanásia, ortotanásia. Tier 2: cuidados
paliativos, diretivas antecipadas de vontade, testamento vital,
terminalidade da vida, prevenção do suicídio.

**3 Gender medicine (children).** Tier 1: bloqueador\* de puberdade,
bloqueador\* puberais, bloqueio puberal, bloqueio da puberdade, hormonização
cruzada, terapia hormonal cruzada, redesignação sexual, redesignação de
sexo, cirurgia\* de transgenitalização, transgenitalização, disforia de
gênero, incongruência de gênero, crianças trans, crianças transgênero,
adolescentes trans, processo transexualizador, afirmação de gênero,
detransição, destransição. Tier 2, guarded to criança/adolescente/menor:
hormonização, transição de gênero, bloqueadores hormonais. (The "processo
transexualizador" is the SUS programme; the CFM resolution of 2025 on minors
is the Brazilian Cass moment and needs its number added once confirmed.)

**4 Conversion practices.** Tier 1: terapia\* de conversão, terapia\* de
reversão, cura gay, reorientação sexual, reversão sexual, conversão sexual.
Tier 2: {orientação sexual, with: terapia, tratamento, psicólogo(s),
reversão}.

**5 Sex-based rights and gender ideology.** Tier 1: ideologia de gênero,
identidade de gênero, linguagem neutra, linguagem não binária, pronome
neutro, nome social, sexo biológico, transgênero\*, transexua\*, travesti\*,
mulher\* trans, atleta\* trans, LGBT\* (case-sensitive; catches LGBTQIA+ and
LGBTfobia), não binári\*, homotransfobia, transfobia, LGBTfobia, homofobia.
Tier 2: {banheiro\*, with: sexo, gênero, trans, unissex, biológico},
{vestiário\*, with: sexo, gênero, trans, biológico}, orientação sexual,
diversidade sexual, igualdade/perspectiva/equidade/questões de gênero,
{esporte\* feminino\*, with: sexo, trans, biológico, gênero}, misoginia,
Convenção de Belém do Pará. ("Ideologia de gênero" is the single most used
phrase on our side of the Brazilian debate, and "misoginia" carries the
2026 bills criminalising misogyny, which our free-speech reading may want
under area 7 instead.)

**6 Parental rights and education.** Tier 1: Escola sem Partido, educação
domiciliar, ensino domiciliar, homeschooling, doutrinação, educação sexual,
direito(s) dos pais, direito das famílias na educação, adultização, ECA
Digital, erotização infantil, erotização de crianças, sexualização infantil,
sexualização de crianças. Tier 2: {redes sociais, with: criança(s),
adolescente(s), menor(es)}, {celular\*, with: escola(s), sala de aula,
ensino}, {smartphone\*, with: escola(s), sala de aula}, {Base Nacional Comum
Curricular, with: gênero, sexual, sexualidade}, {Plano Nacional de Educação,
with: gênero, sexual, sexualidade}, poder familiar, educação para a
sexualidade, verificação de idade, {ambiente digital, with: criança(s),
adolescente(s)}. ("Adultização" became a political term in August 2025 and
carries 76 bills since; the ECA Digital is Lei 15.211/2025.)

**7 Free speech and online safety.** Tier 1: liberdade de expressão, PL das
Fake News, Lei das Fake News, regulação/regulamentação das redes,
regulação/regulamentação das plataformas, censura, crime de opinião, delito
de opinião. Tier 2: Marco Civil da Internet, fake news, desinformação,
discurso de ódio, moderação de conteúdo, {plataformas digitais, with:
conteúdo(s), moderação, remoção, criança(s), adolescente(s), redes sociais,
desinformação}, remoção de conteúdo, liberdade de imprensa, liberdade de
manifestação, notícias fraudulentas. (Marco Civil sits at tier 2 because it
is amended by every online-fraud bill: 112 hits.)

**8 Freedom of religion.** Tier 1: liberdade religiosa, liberdade de culto,
liberdade de crença, liberdade de consciência e de crença, intolerância
religiosa, perseguição religiosa, perseguição a cristãos, cristãos
perseguidos, objeção de consciência, ensino religioso, templos de qualquer
culto, cultos religiosos. Tier 2: {imunidade tributária, with: templo(s),
igreja(s), religios\*, culto}, capelania\*, capelão, Bíblia, estado laico,
laicidade, organizações religiosas, entidades religiosas, {igreja\*, with:
fechamento, liberdade, proibição, perseguição}, racismo religioso, religiões
de matriz africana.

**9 Marriage and family.** Tier 1: casamento homoafetivo, união/uniões
homoafetiva(s), casamento (civil) entre pessoas do mesmo sexo, Estatuto da
Família, entidade familiar, união poliafetiva, poliamor, casamento infantil,
casamento de menores, adoção homoafetiva. Tier 2: {união estável, with:
homoafetiv\*, mesmo sexo, poliafetiv\*}, licença-paternidade (both
spellings), licença-maternidade, planejamento familiar, família natural,
multiparentalidade, parentalidade socioafetiva.

**10 Surrogacy and embryology.** Tier 1: barriga de aluguel, barriga
solidária, gestação de substituição, útero de substituição, cessão
temporária de útero, maternidade de substituição, reprodução (humana)
assistida, células-tronco embrionárias, clonagem humana, embriões humanos,
embriões excedentários. Tier 2: fertilização in vitro, inseminação
artificial, embrião, embriões, edição genética, doação de gametas, Lei de
Biossegurança.

**11 Migration (collated, never campaigned).** imigração, imigrante\*,
migrante\*, refugiad\*, Lei de Migração, deportação; tier 2 asilo,
apátrida\*, acolhida humanitária, visto humanitário.

**12 Prostitution, trafficking and pornography.** Tier 1: prostituição,
tráfico de pessoas, tráfico humano, exploração sexual, pornografia\*,
pornográfic\*, casa de prostituição, profissionais do sexo, trabalho
sexual, Lei Gabriela Leite. Tier 2: abuso sexual infantil, abuso sexual de
crianças, conteúdo sexual, turismo sexual, nudez, deepfake\*, imagens
íntimas.

**13 Organ donation.** Tier 1: doação de órgãos, doação presumida, doador
presumido, consentimento presumido, tráfico de órgãos. Tier 2:
transplante\*, morte encefálica, doador(es) de órgãos.

**Global exclusions** (never terms alone): vida, família, gênero, criança,
mulher, saúde, educação, escola, religião, direitos.

**Bill numbers** go in `config/watchlist-br.yaml`, keyed by proposição,
never in the term list (12 entries, each checked against the Câmara's record
on 9 October 2026; most were chosen because their ementa never names the
issue: PEC 164/2012 is "new wording for the head of art. 5").

## Phase 1: built, 9 October 2026

`tools/br_rollcalls.py` into `br_members`, `br_bills`, `br_divisions`,
`br_votes` and `br_orientations` (schema in `src/br_store.py`, declared in
`db.TABLES`). No key anywhere.

- **Câmara**: the year's `votacoes` file picks out the nominal votes (yes +
  no + other > 0); `votacoesProposicoes` gives each vote its bills;
  `votacoesOrientacoes` the leaders' orientations; then one
  `/votacoes/<id>/votos` request per nominal vote, newest first, and one
  `/proposicoes/<id>` request per voted bill (for its keywords). Positions
  and bill records are fetched once ever; a run cut short by its budget
  resumes where it stopped.
- **Senado**: one `/votacao` request per year, positions included.
- **Members**: both houses' lists of those in office; former members are
  filled from the positions they cast.
- **Classification**: `config/watchlist-br.yaml` by key, plus
  `config/taxonomy-pt.yaml` the day it exists. A vote's areas are its own
  text's plus those of every bill it is linked to; `own_areas` keeps the
  first apart. Without the Portuguese list, only watched bills give areas,
  and that is deliberate: classifying with the English list would look like
  a strict filter while seeing nothing.
- **Years read**: the current one; the previous one too in January and
  February; and, on the first run, every year back to 2023 (the 57th
  legislature). `--from-year` overrides.
- **Exit 3** when it stored what it could and recorded gaps, as the
  Australia collector does; the job script publishes that run.

Live run into a scratch database, 2026 only (`--from-year 2026`):
two runs, the first cut by the default 600 s
budget and resumed by the second, as designed.

| | Measured |
|---|---|
| Members in office | 594 (513 deputies, 81 senators); 659 with former members filled from votes |
| Câmara nominal votes 2026 | 152, all with positions (56,611 positions across both houses) |
| Senate nominal votes 2026 | 59, all with positions |
| Câmara orientations | 1,377 |
| Proposições linked to the votes | 156; 97 Câmara records read for keywords |
| Time | positions for 152 votes in about 8.5 minutes (about 3.3 s per vote: the responses are large); 97 bill records in about 2 minutes |
| Gaps | none |
| On our ground (watchlist only) | 7 votes, all plenary votes on PEC 5/2023 (religious tax immunity), 1 bill |

At about 3.3 s per vote, the first backfill to 2023 (1,597 Câmara votes)
needs about 90 minutes of positions, so it spreads over two or three weekly
runs at the job's 2,700 s budget. Every later week reads only what is new.

Tests: `tests/test_br_rollcalls.py` (27 tests) on real responses of
9 October 2026, trimmed, in `tests/fixtures/br/`.

### The weekly job (Mini first)

- `jobs/br-weekly.sh`: the collector with a 2,700 s budget, then
  `raw_state.py --push` and `db_state.py --push`.
- `ops/launchd/net.citizengo.parlmonitor.br-weekly.plist`: Saturdays 09:30
  London on the Mini, via `tools/mini_run.sh br-weekly` (which records
  `MINI_LAST_BR_WEEKLY`).
- `.github/workflows/br-weekly.yml`: Saturday 09:30 and 13:30 UTC (half an hour later than first built) as the
  backup, behind `mini-check` with job `BR_WEEKLY` and a 300-minute grace
  (09:30 London is 08:30 UTC in summer, five hours before the retry), then
  the same-day retry gate. Saturday was chosen because Brasília sits
  Tuesday to Thursday and the Câmara rebuilds its files by about 07:20 UTC;
  Saturday's other crons are 06:00, 07:00, 10:00, 14:00 and 18:00.
- **It runs only once merged to main**: GitHub schedules from the default
  branch, and the Mini runs `main` unless `RUNNER_REF` says otherwise.

### Shared files touched (for the 13-branch merge)

Kept to registration lines only, each a pure addition:

- `src/db.py`: five `br_*` names in `TABLES`; `br_store.ensure_schema(conn)`
  in `init_db`.
- `tools/coverage.py`: `"Brazil weekly"` in `PIPELINES`; `br_members`,
  `br_bills`, `br_divisions` in `FEEDS`; `"Brazil weekly": ["br_members"]`
  in `PIPELINE_FEEDS`; `"Brazil weekly"` in `AWAITING_FIRST_RUN`.
- `.github/workflows/alert.yml`: `"Brazil weekly"` in the watched workflows.

Everything else is new and Brazil's own: `src/br_store.py`,
`tools/br_rollcalls.py`, `config/watchlist-br.yaml`, `tests/test_br_rollcalls.py`,
`tests/fixtures/br/`, `jobs/br-weekly.sh`, the plist, `br-weekly.yml`, this
document. No taxonomy file, no `src/http.py` change.

## Proposed phasing

1. **Phase 1 (built): nominal votes and positions, both houses**, with the
   bills they are about, members and orientations. Thin but exact: the 5CA
   layer, complete, for the votes that exist.
2. **Phase 2 (needs Christopher's term approval): the Portuguese taxonomy**,
   then the **bill layer**: every Câmara proposição of the main types
   (PL, PEC, PLP, PDL, MPV, PRC; about 8,000 a year) matched on ementa and
   keywords, and the Senate's processos. This is where the weekly volume is
   (about 30 bills a month on our ground). Best done from the bulk
   `proposicoes-<year>.json`, which needs gzip in `src/http.py` (see below),
   or from the paged API by date and type (about 80 requests a year).
3. **Phase 3: agenda and tramitação**: the Câmara's `eventos` + `pauta` and
   the Senate's monthly agenda as the What's On equivalent, and tramitação
   steps for watched bills (committee, rapporteur, urgency).
4. **Phase 4: edition and 5CA**: a Portuguese-language or English-language
   edition (Christopher's call), triage, and a Brazilian 5CA from positions
   plus orientations. Divisions are signed by hand, as everywhere.
5. **Phase 5: state assemblies** (below).

## Dates that matter

- **4 October 2026: general election, first round** (done); **25 October:
  run-off**. Every deputy and two-thirds of the Senate (54 seats) were up.
  Congress has been in its election recess since early September: the last
  Câmara nominal vote was on 3 September, the last Senate one on 3 September.
- **Lame duck, November-December 2026**: the budget (PLOA 2027) and whatever
  the outgoing majority wants through before February.
- **1 February 2027: the 58th legislature opens.** Under the Câmara's rules
  (RICD art. 105) proposições are archived at the end of a legislature
  unless an author asks within 180 days to revive them: Brazil's version of
  a prorogation fall. The Senate's rule (RISF art. 332) differs. Both need
  confirming before the board treats any bill as dead.
- **Party-switch windows** (the "janela partidária", 30 days in March-April
  of an election year, when deputies may change party without losing the
  seat) are why party is stored per vote.

## State assemblies (later; listed, not probed)

26 Assembleias Legislativas plus the Câmara Legislativa do Distrito Federal.
Open-data quality varies widely and there is no aggregator like Open States.
Likely order by salience and data (to be probed): São Paulo (ALESP), Minas
Gerais (ALMG), Rio de Janeiro (ALERJ), Rio Grande do
Sul (ALRS), Paraná (ALEP), Santa Catarina (ALESC), Bahia (ALBA), Goiás
(ALEGO), Pernambuco (ALEPE), Distrito Federal (CLDF), then the rest: Acre,
Alagoas, Amapá, Amazonas, Ceará, Espírito Santo, Maranhão, Mato Grosso, Mato
Grosso do Sul, Pará, Paraíba, Piauí, Rio Grande do Norte, Rondônia, Roraima,
Sergipe, Tocantins. Much of the school-policy fight (Escola sem Partido,
"linguagem neutra" bans, gender in curricula) and many municipal laws sit
here, as Germany's Länder carry part of its ground.

## Waiting on Chris

1. **Approve, cut or correct the Portuguese terms above**, ideally with a
   Brazilian campaigner's read (the "wrong side of the debate" errors only a
   native reader catches). Nothing is classified by term until then.
2. **Scope questions the terms raise**: is misogyny criminalisation area 7
   (speech) or out? Do **gambling ("bets", casinos, jogos de azar)** and
   **drug decriminalisation (cannabis, STF RE 635659)** belong in the
   Brazilian edition? Both are likely ground for CitizenGO Brazil, and
   neither has an area in the shared taxonomy. Contraception ("pílula do dia seguinte")
   sits at tier 2 in area 1, as the US decision did.
3. **Gzip in `src/http.py`** (an opt-in `Accept-Encoding: gzip` and
   decompression): a shared-module change, so not made here. It turns the
   Câmara's 71 MB bill file into 6 MB and makes phase 2 one download.
4. **Merge and schedule**: the weekly runs only from `main`. Install the
   plist on the Mini once merged; create `HC_BR_WEEKLY` (healthchecks) if
   wanted.
5. **Edition language** for phase 4: Portuguese source text with English
   takeaways (as Germany), or English throughout?
6. **Watchlist review** (`config/watchlist-br.yaml`, 12 bills): add the
   bills CitizenGO Brazil is actually campaigning on.

## Decisions of 10 October 2026 (applied at the countries merge)

Recorded in `docs/country-decisions-2026-10-10.md`. Shared: accents fold and non-ASCII letters are word characters in the filter (X3); member positions are stored for every vote (X15); the AI judge stays off (X16).

Applied on the `countries` branch:

- Term list approved (BR1, BR2 misogyny area 7) and merged into the shared `config/taxonomy-pt.yaml` (`docs/keyword-taxonomy-pt.md`), loaded for this country's code.
- Weekly moved to Saturday 09:30/13:30 UTC (Switzerland and France hold 09:00/13:00).

Later phases and items for Chris (not built at the merge):

- BR3 (gambling) and BR4 (drug decriminalisation) are in scope but the scope proposed no terms or area: they need terms before they match.
- Portuguese source text with English takeaways (BR5): the edition phase.
