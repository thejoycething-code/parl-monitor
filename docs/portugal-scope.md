# Portugal: scoping the Assembleia da República monitor

Probed live on 9 October 2026, from the laptop. Every number below was
measured, not estimated. The raw responses are archived under
`data/raw/2026-10-09/` (`pt-probe_*` and `pt-rollcalls_*`). National
parliament first; the two regional assemblies are listed at the end and not
built.

## Decisions already taken (Chris, standing for every new country)

- Own edition, delivered to Chris alone (Slack DM), as the US.
- Shared taxonomy concept, but no existing taxonomy file is edited. The
  Portuguese term list is PROPOSED below; Chris approves it before any
  `config/taxonomy-pt.yaml` is generated.
- Mac Mini first, GitHub Actions as backup. No paid services. Nothing posted
  publicly.

## The finding that shapes everything

**Two findings, one about words and one about votes.**

**1. The English taxonomy is blind to Portuguese, as it was to German.**
`config/taxonomy.yaml` (v1.17), unchanged, run over the initiative titles of
the last three legislatures:

| Legislature | Initiatives | English list: on our ground | Draft Portuguese list: on our ground (tier 1) |
|---|---|---|---|
| XVII (from 3 June 2025) | 2,328 | **5** | 86 (36) |
| XVI (2024-2025) | 1,548 | 2 | 85 (39) |
| XV (2022-2024) | 2,167 | 2 | 83 (50) |

All nine English matches are area 7, and every one matched because "Chat
Control" or "European Democracy Shield" is written in English inside a
Portuguese title. The English list did not see the euthanasia law, the
self-ID amendments, the conversion-practices ban, the January 2025 abortion
package or this year's puberty-blocker bill. Measured with the draft list
below, votes on our ground: XVII 85, XVI 96, XV 141.

**2. Portugal votes by group, not by deputy.** The plenary votes by sitting
and standing. The record is each parliamentary group's position:

    A Favor: PSD, CDS-PP   Contra: CH, IL, L, PCP, BE   Abstenção: PS, PAN, JPP

A deputy appears by name only when they break from their group, and the
group then appears twice, as a whole and as a counted block:

    A Favor: 13-PS, L, ... Pedro Nuno Santos (PS), Edite Estrela (PS), ...
    Abstenção: PS

So there is no per-member roll call to copy, as Germany and the US have. A
5CA here is derived: a deputy's position is their group's unless the record
names them. The record does not distinguish "voted with the group" from
"absent", and the collector does not pretend it does.

On a free vote there is no group line at all, only counted blocks on each
side, and the record names the deputies of the smaller block only. The
euthanasia confirmation vote of 12 May 2023 reads "A Favor: 107-PS, 8-PSD,
..." and "Contra: 4-PS, 60-PSD, 12-CH, 5-PCP, ..." with four PS names and
none of the sixty PSD deputies. Which sixty is an inference (everyone in
the group not named elsewhere), and must be labelled as one. Votes that need
an absolute majority, such as that confirmation, carry a count for every
group. On our ground this
matters most where it is most interesting: conscience votes. Of the tier-1
votes on our ground, **40 of 108 in the XV named individual deputies**
(euthanasia, gender self-ID, conversion practices), 10 of 49 in the XVI, 0 of
35 so far in the XVII.

## What Portugal publishes

### Dados Abertos, Assembleia da República: WORKS TODAY, open, no key

`www.parlamento.pt/Cidadania/Paginas/DadosAbertos.aspx`. One page per
dataset, one folder per legislature (Constituinte, I to XVII), each folder
holding the dataset as XML and as JSON (`<Name><LEG>_json.txt`, served as
`application/json`). Keyless, no login, answered our User-Agent at once.

**The download URLs are encrypted tokens**:
`app.parlamento.pt/webutils/docs/doc.txt?path=<token>&fich=IniciativasXVII_json.txt`.
The token was identical on two visits an hour apart, but nothing promises
it, so the collector discovers it each run: dataset page (about 370 KB of
HTML), legislature folder page (about 345 KB), then the file. Three requests
per dataset. **No Last-Modified, no ETag** on the files, so every run reads
them whole.

XVII sizes and contents, measured:

| Dataset | Size | Contents |
|---|---|---|
| Iniciativas | **97 MB** (82 s, 5.6 MB gzipped) | 2,328 initiatives with their whole history: 70 phase types, every vote inside the phase that took it |
| InformacaoBase | 0.57 MB | 1,446 deputies (effective and substitute), 10 groups, 22 circles, sessions |
| Atividades | 1.9 MB | 847 activities (773 votos, 40 elections, 6 interpelações, 2 moções), 204 with a vote; 36 reports |
| PerguntasRequerimentos | 7.8 MB | 4,076: 2,801 written questions (perguntas), 1,275 requests (requerimentos), with authors and replies |
| Peticoes | 0.79 MB | 233 petitions |
| DiplomasAprovados | 2.0 MB | 934: 101 Leis, 111 Decretos da AR, 341 Resoluções da AR, 346 Resoluções, 32 Deliberações |
| AtividadeDeputado | 38.7 MB | per-deputy activity (not downloaded) |
| Intervencoes | **2 bytes** (`[]`) | empty for the XVII: the debate layer is not published by this route |

Earlier legislatures, for a backfill: Iniciativas XVI 66.5 MB (1,548
initiatives, 1,436 votes), XV 100.7 MB (2,167, 2,583 votes). One request
each after discovery.

**Rate limits.** None met on parlamento.pt: about twenty requests across
the morning, a second apart, every one answered. Throughput is the limit:
about 1.2 MB/s, so the 97 MB file takes 70 to 85 seconds.

**Quirks.**
- Open terms are dated to *yesterday*: a sitting deputy's `gpDtFim` read
  2026-10-08. The dumps are regenerated daily, which is why the weekly runs
  on Saturday afternoon, after Friday's votes.
- Counts in the vote record are floats in the deputies file
  (`DepCadId: 9008.0`); the collector stores integers.
- Initiative numbers restart every legislature; `IniId` is unique across
  all. The key is `<LEG>/<IniTipo>/<number>` (`XVII/J/479` for Projeto de
  Lei 479/XVII), checked unique: 2,328 initiatives, 2,328 keys.
- Vote ids are unique across the legislature: 2,162 ids, no repeats.
- The constitutional court reaches the record only as a **veto**: there is
  no TC phase. The nationality law (Proposta de Lei 1/XVII) carries three
  `Veto (Receção)` events; the collector counts them per initiative.
- 309 of 2,162 XVII votes are unanimous (no detail); 3 carry neither detail
  nor the unanimous flag.

### Members and parties: WORKS TODAY (InformacaoBase above)

230 seated deputies in the XVII: PSD 89, CH 60, PS 58, IL 9, L 6, PCP 3,
CDS-PP 2, BE 1, PAN 1, JPP 1. The 1,446 rows include the substitutes
(*suplentes*, 1,171) who may take a seat. Every deputy has a stable
`DepCadId` (the Assembleia's person id), which authors of initiatives and
written questions also carry (`idCadastro`). Named votes print the
parliamentary name and group: **all 127 named positions in the XVII resolved
to a single deputy id** by name, with the group as tie-break.

### Agenda: NOT PROBED

There is no agenda dataset on the open-data page. The weekly plenary agenda
is published as web pages; a later phase.

### Debates (Diário da Assembleia da República): PARTLY

The Intervenções dataset is empty for the XVII. The DAR is linked from every
vote (`debates.parlamento.pt/catalogo/r3/dar/01/17/01/089/2026-05-09/77`),
page by page. Debate packs would be built from there; not probed further.

### Constitutional Court (Tribunal Constitucional): REACHABLE, HTML, rate-limited

`www.tribunalconstitucional.pt/tc/acordaos/<year><nnnn>.html`, keyless HTML,
one page per ruling (Acórdão 5/2023, 727 KB, the euthanasia ruling on
Decreto 23/XV). **It answered 429 Too Many Requests to a second request one
second after the first**, and 200 again later. A collector would need
several seconds between requests. The court matters in Portugal more than
in most countries on our list: the President can send any decree for
preventive review, and the euthanasia law was struck down by it before it
was finally passed.

## Assisted dying: the law, the court and the record

Measured from the XV dump, the record of how Lei 22/2023 (morte medicamente
assistida) became law:

- Four bills, merged: Projetos de Lei 5/XV (BE), 74/XV (PS), 83/XV (PAN) and
  111/XV (IL). Generality vote 9 June 2022, approved. **PSD and PS both
  split**: "A Favor: PS, 5-PSD, ..." and "Contra: 7-PS, 63-PSD, CH, PCP,
  ...", the five PSD and seven PS dissenters named. Final global vote
  9 December 2022, the same shape (6 PSD for, 58 against).
- The decree (Decreto 23/XV) went to the Constitutional Court. Acórdão
  5/2023 (fetched, above), of 30 January 2023, found norms of articles 2, 3,
  5, 6, 7 and 28 unconstitutional and the rest not. It cites the court's
  earlier ruling, Acórdão 123/2021, which struck down the XIV legislature's
  decree (Decreto 109/XIV).
- A new decree was voted on 31 March 2023, was vetoed, and was **confirmed
  on 12 May 2023**, overriding the veto. Each bill carries two veto events.
- Published 25 May 2023.
- The Chega referendum proposal (Projeto de Resolução 62/XV) was rejected on
  9 June 2022, PSD again split by name.
- The law needs regulations to operate. Projeto de Resolução 290/XVI, asking
  the Government to complete them, was **rejected on 27 September 2024**. No
  XVII initiative mentions euthanasia by title so far.

## What the XVII is doing on our ground (from the record)

- **Puberty blockers.** Projeto de Lei 479/XVII (CDS-PP) bans puberty
  blockers and cross-sex hormones for minors. Approved on generality on
  20 March 2026, PSD, CH and CDS-PP for. Now in committee.
- **Face coverings.** Projeto de Lei 47/XVII (CH) bans face coverings in
  public. Final vote 17 July 2026, published as law.
- **Gender self-ID.** Projeto de Lei 493/XVII (BE) amending Lei 38/2018 was
  rejected on 20 March 2026. Two more bills on change of sex in the civil
  register (486/XVII, 391/XVII) are filed.
- **Abortion.** Chega's bill protecting the unborn (88/XVII) was rejected on
  11 July 2025; BE's resolution on abortion access (1202/XVII) is filed.
- **Schools.** CDS-PP's resolution on Cidadania e Desenvolvimento (35/XVII)
  and Chega's on ideological neutrality in schools (1015/XVII).
- **Surrogacy.** IL asks for regulation of the surrogacy law (897/XVII).
- **Free speech.** Four resolutions against Chat Control, all rejected
  19 September 2025; one against the European Democracy Shield, rejected
  25 September 2026.
- **Petitions:** "Pelo Fim da Ideologia de Género nas Instituições e pela
  Revogação da Lei 15/2024" (the conversion-practices law) and one against
  legalising conversion therapy.

Every one of these is in `config/watchlist-pt.yaml`, keyed.

## Referendums

A real channel in Portugal on our ground: abortion was put to referendum in
1998 and 2007 before Lei 16/2007. Referendum proposals arrive as Projetos de
Resolução and are in the same dump (the euthanasia one above; an immigration
one, 693/XVII). No separate source is needed.

## Phase 1: built, 9 October 2026

`tools/pt_rollcalls.py` into six tables (schema in `src/pt_store.py`,
declared in `db.TABLES`): `pt_members`, `pt_initiatives`, `pt_authors`,
`pt_divisions`, `pt_group_votes`, `pt_votes`. Live run, end to end, into a
scratch database:

| | Read | On our ground (English list + watchlist) |
|---|---|---|
| Initiatives, XVII | 2,328 | 23 |
| Votes | 2,162 | 21 |
| Group positions | 18,446 | |
| Named deputy positions | 127 (all resolved to a deputy id) | |
| Deputies | 1,446 | |

72 seconds for the initiatives, under 10 for the deputies.

- **Classification**: `config/taxonomy-pt.yaml` if it exists, else the
  English list, plus `config/watchlist-pt.yaml` by key. The day Chris
  approves the Portuguese list and it is generated, a `--reclassify` (or the
  workflow's reclassify input) re-derives everything offline. Nothing else
  changes.
- **Votes inherit their initiative's areas**; `own_areas` keeps the vote's
  own match apart (amendment and requerimento votes carry a description).
- **Exit codes**: 0 clean, 3 gaps recorded (published anyway), 1 nothing
  read.
- **Weekly**: `jobs/pt-weekly.sh`, Mac Mini Saturdays 15:00 London
  (`ops/launchd/net.citizengo.parlmonitor.pt-weekly.plist`), GitHub backup
  Saturdays 16:00 and 19:00 UTC (`.github/workflows/pt-weekly.yml`), gated by
  `mini-check` with `PT_WEEKLY`, grace 320 minutes. Registered with the
  failure alert and the coverage watch. **It runs only once merged to main.**
- **Tests**: `tests/test_pt_rollcalls.py`, 25 tests on trimmed real files in
  `tests/fixtures/pt/`.

No edition, no judge, no DM yet: nothing is shown to anyone until there is a
Portuguese list to show it with (the German lesson).

## Proposed Portuguese term list (for Chris to approve)

Drafted 9 October 2026 and measured on the three dumps above. It is an AI
first draft and needs a native European Portuguese reader. Format is that of
`config/taxonomy-de.yaml` (tier 1 raises an item, tier 2 needs company or is
low-signal; `*` is a stem; `with`/`without` are guards).

**Marked [PT]** are Portugal-specific (laws, bodies, school subjects, or
European spelling). Everything unmarked is shared vocabulary that a merged
Portuguese list for Portugal and Brazil could carry once. **[PT spelling]**
marks the European form where Brazil writes it differently; the Brazilian
form is given so the two lists can be merged.

### 1 Abortion
- Tier 1: aborto*, interrupção voluntária da gravidez, interrupção
  voluntária de gravidez, interrupção da gravidez, IVG [PT: Brazil says
  "aborto legal"], Lei n.º 16/2007, Lei 16/2007 [PT], nascituro*, vida
  intrauterina, vida pré-natal, mifepristona, misoprostol, pílula abortiva,
  pílula do dia seguinte, contraceção de emergência [PT spelling; BR
  contracepção], direitos sexuais e reprodutivos, objeção de consciência,
  objecção de consciência [pre-1990 spelling, still in older texts],
  objetor*, objector*.
- Tier 2: saúde sexual e reprodutiva, contraceção [PT spelling],
  contracepção [BR], diagnóstico pré-natal, planeamento familiar [PT; BR
  planejamento familiar], grávida*, gestante*.

### 2 Assisted dying
- Tier 1: morte medicamente assistida [PT legal term; BR uses eutanásia,
  suicídio assistido], Lei n.º 22/2023 [PT], eutanásia, eutanasia, suicídio
  assistido, suicídio medicamente assistido, antecipação da morte, morte
  assistida, morte digna.
- Tier 2: cuidados paliativos, fim de vida, testamento vital, diretivas
  antecipadas de vontade, directivas antecipadas de vontade, distanásia,
  obstinação terapêutica. (Brazil adds ortotanásia.)
- Measured note: "cuidados paliativos" is twelve of the XVII's twelve area-2
  matches, all palliative-care funding. Tier 2 is right; drop it if it
  floods.

### 3 Gender medicine and children
- Tier 1: bloqueadores da puberdade, bloqueadores hormonais, disforia de
  género, incongruência de género, transição de género, afirmação de género
  [PT spelling: género; BR gênero], redesignação sexual, cirurgia de
  redesignação, reatribuição de sexo.
- Tier 2: tratamentos hormonais (with menores, crianças, jovens, género),
  identidade de género (with menores, crianças, escolas, jovens).

### 4 Conversion practices
- Tier 1: práticas de conversão, terapias de conversão, terapia de
  conversão, conversão sexual, Lei n.º 15/2024 [PT].

### 5 Sex-based rights and gender identity
- Tier 1: autodeterminação da identidade de género, autodeterminação de
  género, identidade de género, expressão de género, características
  sexuais, Lei n.º 38/2018, Lei 38/2018 [PT], mudança de sexo, menção do
  sexo, mudança da menção do sexo [PT: the civil-register term], não
  binári*, transgénero* [PT spelling; BR transgênero], pessoas trans,
  ideologia de género [BR ideologia de gênero], linguagem inclusiva, LGBT*,
  homofobia, transfobia.
- Tier 2: Convenção de Istambul, orientação sexual, igualdade de género
  (only with identidade de género, trans, escola), casas de banho [PT; BR
  banheiros], balneários [PT; BR vestiários], desporto feminino [PT; BR
  esporte feminino].

### 6 Parental rights and education
- Tier 1: Cidadania e Desenvolvimento [PT school subject], Estratégia
  Nacional de Educação para a Cidadania [PT], educação para a cidadania,
  educação sexual, Lei n.º 60/2009 [PT], educação para a saúde, ensino
  doméstico [PT; BR educação domiciliar, homeschooling], ensino individual
  [PT], liberdade de educação, liberdade de ensino, direito dos pais,
  direitos dos pais, neutralidade ideológica, doutrinação.
- Tier 2: responsabilidades parentais [PT; BR poder familiar], ensino
  particular e cooperativo [PT], contratos de associação [PT],
  telemóve* (with escola, aluno, ensino) [PT; BR celular], redes sociais
  (with menores, crianças, jovens, idade), controlo parental [PT; BR
  controle parental], manuais escolares [PT; BR livros didáticos].
- Measured note: ten of the XVII's seventeen area-6 matches are funding of
  private and cooperative schools. Whether school choice is our ground is a
  scope question (below).

### 7 Free speech and online safety
- Tier 1: liberdade de expressão, discurso de ódio, incitamento ao ódio,
  crimes de ódio, desinformação, censura, verificação de idade, pornografia,
  Carta Portuguesa de Direitos Humanos na Era Digital [PT], Regulamento dos
  Serviços Digitais.
- Tier 2: liberdade de imprensa, conteúdos ilegais.
- Dropped after measuring: "inteligência artificial" and "plataformas
  digitais" pulled in forest fires, delivery riders and an AI model.

### 8 Freedom of religion
- Tier 1: liberdade religiosa, Lei da Liberdade Religiosa, Lei n.º 16/2001
  [PT], Concordata [PT], Igreja Católica, confissões religiosas, comunidades
  religiosas, assistência religiosa, Educação Moral e Religiosa, EMRC [PT],
  laicidade, símbolos religiosos, ocultação do rosto, burca*, burqa*,
  niqab*, abusos sexuais na Igreja, liberdade de consciência, lugares de
  culto.
- Tier 2: religios*, cristãos, perseguição religiosa, antissemitismo,
  islamofobia.

### 9 Marriage and family
- Tier 1: casamento entre pessoas do mesmo sexo, adoção por casais do mesmo
  sexo, coadoção [PT], casamento civil, união de facto, uniões de facto
  [PT; BR união estável], divórcio.
- Tier 2: natalidade, parentalidade, apoio à família, famílias numerosas,
  licença parental, conciliação da vida familiar, quociente familiar [PT].
- Measured note: tier 2 here is family policy (parental leave, child
  benefit, tax): 20 of the XVII's 21 area-9 matches. A scope question.

### 10 Surrogacy and embryology
- Tier 1: gestação de substituição [PT legal term], barrigas de aluguer,
  barriga de aluguer [PT; BR barriga de aluguel], maternidade de
  substituição, procriação medicamente assistida, PMA [PT; BR reprodução
  assistida], Lei n.º 32/2006 [PT], CNPMA [PT], inseminação post mortem,
  embrião, embriões, gâmetas, doação de gâmetas, dação de gâmetas [PT
  spelling; BR gametas].
- Tier 2: infertilidade, fertilidade, células estaminais [PT; BR
  células-tronco], clonagem.

### 11 Migration (collated, never campaigned)
- Tier 1: imigração, imigrantes, estrangeiros, Lei de Estrangeiros, lei da
  nacionalidade, AIMA [PT], manifestação de interesse [PT], reagrupamento
  familiar [PT; BR reunião familiar], asilo.
- Tier 2: nacionalidade, migrantes, refugiados.
- 42 of the XVII's 126 matches are migration, about a third, as in Germany.
  Hidden on every surface by the standing rule.

### 12 Prostitution, trafficking and child abuse
- Tier 1: prostituição, lenocínio [PT legal term], tráfico de seres
  humanos, tráfico de pessoas, trabalho sexual, exploração sexual,
  pornografia infantil, abuso sexual de crianças, abuso sexual de menores,
  abusos sexuais de menores.
- Tier 2: mutilação genital feminina, casamento infantil, casamentos
  forçados.

### 13 Organ donation
- Tier 1: doação de órgãos, dádiva de órgãos, colheita de órgãos,
  transplante*, morte cerebral, RENNDA [PT: the opt-out register], dador*
  only with órgãos, tecidos or transplant and never with "dador de sangue"
  [PT; BR doador].
- Measured note: unguarded, "dador" matched six blood-donor bills and
  nothing else.

### Notes for whoever generates the file

- **Accents are not folded by the shared filter.** "eutanasia" and
  "eutanásia" are different strings to `src/filter.py`, so both are listed.
  The filter's word boundary is `[a-z0-9]`, so an accented letter counts as
  a boundary; no false match was seen, but a stem like `gesta*` would match
  inside `gestação`. Not changed here (shared code); worth knowing for
  Spanish too.
- **Pre-1990 spelling** survives in older texts and in some deputies'
  drafting (objecção, directivas, protecção): listed where it matters.
- Areas 1 to 13 are CitizenGO's, unchanged. Nothing new was invented.

## Phase plan

1. **Built** (above): deputies, initiatives, votes, group and named
   positions, authorship, watchlist, weekly job.
2. **Portuguese list** once Chris approves it: generate
   `config/taxonomy-pt.yaml`, reclassify, then a Portuguese judge prompt and
   an edition with a DM (the `tools/de_monitor.py` pattern).
3. **Written questions and petitions**: the same discovery code, 7.8 MB and
   0.8 MB. Measured with the draft list: 50 of 4,076 questions on our ground
   (27 tier 1); 5 of 233 petitions (4 tier 1). The English list finds 0 of
   either.
4. **The Constitutional Court** (acórdãos, paced for its 429s) and the DAR
   for debate packs.
5. **A derived 5CA**: group positions plus named breakaways plus authorship
   (2,104 of 2,328 initiatives name their deputy authors). Earlier
   legislatures by backfill (XV holds the euthanasia, self-ID and
   conversion-practices votes).
6. **Regional assemblies, later**: Assembleia Legislativa da Região Autónoma
   dos Açores (ALRAA) and da Madeira (ALRAM). Their formal opinions on
   national bills already appear in the national record as phases
   ("Parecer da ALRAA").

## Shared files touched (for the merge)

- `src/db.py`: six table names in `TABLES`, and `pt_store.ensure_schema` in
  `init_db` (10 lines).
- `tools/coverage.py`: the Portugal weekly in `PIPELINES`, three tables in
  `FEEDS`, `PIPELINE_FEEDS`, `AWAITING_FIRST_RUN` (14 lines).
- `.github/workflows/alert.yml`: "Portugal weekly" (1 line).
- `docs/mac-mini.md`: a Portugal weekly section at the end.

Everything else is Portugal's own: `tools/pt_rollcalls.py`,
`src/pt_store.py`, `config/watchlist-pt.yaml`, `tests/test_pt_rollcalls.py`,
`tests/fixtures/pt/`, `jobs/pt-weekly.sh`, the plist and `pt-weekly.yml`.

## Waiting on Chris

1. **Approve or correct the Portuguese term list above**, ideally with a
   European Portuguese reader. And decide whether Portugal and Brazil share
   one `taxonomy-pt` with country-specific terms marked, or keep two.
2. **Scope calls the measuring raised**:
   - family policy (parental leave, child benefit, family tax): area 9 tier
     2, or out?
   - school choice (private and cooperative school funding): area 6, or out?
   - the face-covering ban (passed July 2026): filed under area 8; which
     side is CitizenGO's?
   - Church abuse compensation (three XVII initiatives): in or out?
3. **Merge `portugal` to main** so the schedule runs (GitHub schedules only
   from the default branch), then install the plist on the Mini.
4. **A backfill of the XV and XVI** (two files, 167 MB, run from CI and
   announced, per the Bundestag rule): yes or no? It is what gives the 5CA
   its euthanasia and self-ID votes.
5. **The parlamento.pt terms of reuse** for the open data have not been
   read. Someone should, before the weekly runs unattended.
6. **The Constitutional Court** as a source (phase 4): wanted?

## Decisions of 10 October 2026 (applied at the countries merge)

Recorded in `docs/country-decisions-2026-10-10.md`. Shared: accents fold and non-ASCII letters are word characters in the filter (X3); member positions are stored for every vote (X15); the AI judge stays off (X16).

Applied on the `countries` branch:

- Term list approved (PT1, PT2 family policy area 9, PT3 school choice area 6, PT4 face covering, PT5 Church abuse compensation) and merged into the shared `config/taxonomy-pt.yaml` (`docs/keyword-taxonomy-pt.md`), loaded for this country's code.
- X5: `pt_store.derived_member_positions()`: named deputies are facts, the rest of a whole-group row derived and labelled.
- PT6: the weekly workflow takes a `legislature` dispatch input (XV, XVI) for the backfill from CI.

Later phases and items for Chris (not built at the merge):

- Chris reads the parlamento.pt reuse terms (PT7).

## Same-day vote briefs (built 10 October 2026, branch `parity-vote-briefs`)

Handover item 1: a brief for each watched or tier-1 vote, naming the members who voted against their group's majority, one DM to Chris per run, de-duplicated in `data/vote-briefs/pt.json` (`src/country_vote_brief.py`, step in `jobs/pt-weekly.sh`). Briefed after each weekly collection. Group votes, positions derived (X5); only the deputies the record names as voting apart are named. See docs/mac-mini.md, "Vote briefs for the new countries".
