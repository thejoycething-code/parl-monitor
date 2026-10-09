# Bolivia: scoping the Asamblea Legislativa Plurinacional monitor

Probed live on 9 October 2026, from the laptop, through `src/http.py` (the
CitizenGO User-Agent, throttled to one request a second or slower, every
response archived under `data/raw/2026-10-09/`: 140 files, 5.8 MB). Every
number below was measured, not estimated. National Assembly only; the nine
departmental assemblies are a later decision.

## Decisions already taken (Chris)

- **Own edition**, delivered to Chris alone (Slack DM), as the US is.
- **Shared taxonomy concept, Spanish terms.** `config/taxonomy.yaml` and the
  other taxonomy files are not touched. The Spanish term list is PROPOSED
  below; a `config/taxonomy-es.yaml` is generated only after Chris approves
  it. Peru, Spain, Argentina, Mexico, Colombia, Chile and others are being
  scoped in parallel, so the list marks which terms are Bolivia-specific.
- **National Assembly first**, departmental assemblies later.
- **Mac Mini first, GitHub Actions as the backup.** No new paid services.
  Nothing is ever posted publicly.

## The findings that shape everything

1. **No per-member votes exist anywhere public.** The Camara de Diputados
   votes electronically (its president defended the system's security on
   24 January 2025, diputados.gob.bo news) but never publishes the result
   by member. The Senado's JSON API has a `sesiones` list: it is empty
   (0 records). Session agendas on diputados.gob.bo are JPG images. News
   items report "por mayoria" or "por unanimidad"; a search of the
   Diputados news since 1 July 2026 for "votos" found two items and no
   tally. A media search for "votacion" returned three photographs of a
   show of hands. **A 5CA-style voting record cannot be built for Bolivia
   from official sources.** What can be built is a bill tracker: every
   proyecto, its stage in each chamber, and every move between stages.
2. **The bill data is good, open, structured and keyless.** Two JSON
   sources, both found by reading the sites' own front ends:
   diputados.gob.bo's WordPress REST API (custom post type `ley`, 5,352
   records since December 2020) and the Senado's own API
   (`apisi.senado.gob.bo/page`, six stage lists, 754 records). No key, no
   account, no CAPTCHA or bot challenge on any data endpoint.
3. **The English taxonomy is blind to Spanish.** Run over all 6,106 bill
   titles of both chambers, `config/taxonomy.yaml` matched **none**. The
   Germany lesson again: until `taxonomy-es` exists the edition collects
   everything and sees nothing, which is why `config/watchlist-bo.yaml`
   carries the eight bills found by hand below.
4. **The Assembly is plural and active.** The Senate's 36 titulares
   (measured from the API): PDC 16, LIBRE 12, UNIDAD 7, APB-SUMATE 1. No
   party holds a majority on its own, so bills have to be negotiated, and
   the chambers are busy: 958 Diputados bill records and 340 Senado bill
   records in the 2025-2026 legislative year so far. This is not a
   rubber-stamp legislature, so an edition is worth having; it will simply
   be a bill edition, not a votes edition.

## Sources

### Diputados bills: works today, open, no key

`GET https://diputados.gob.bo/wp-json/wp/v2/ley?per_page=100&page=N`
(WordPress REST, custom post type `ley`). Useful fields under `acf`:
`titulo` (the bill number), `descripcion` (the title), `estado_de_ley`
(status in the chamber's own words), `gestion`, `ley_nro`, `archivo_ley`
(media id of the bill PDF). Taxonomies `legislatura_de_ley`,
`comision_de_ley` and `estado_de_ley` are their own endpoints. `_fields=`
trims a page from about 900 KB to 70 KB. `modified_after=` and
`legislatura_de_ley=<id>` both work.

| Measure | Value |
|---|---|
| Records | 5,352 (9 December 2020 to 5 October 2026) |
| Legislatura 2025-2026 (term id 274) | 958 records, 20 November 2025 to 5 October 2026 |
| 2024-2025 / 2023-2024 / 2022-2023 | 818 / 741 / 103 |
| No legislatura term set | 2,670 (older records, laws by date) |
| Status, all records | Archivado 2,737; Ley Promulgada 1,293; en Tratamiento 814; Aprobado 254; en Revision 137; Sancionado 62; con Modificacion 3; blank 51 |
| Status, 2025-2026 | en Tratamiento 801; en Revision 16; Aprobado 9; Sancionado 3; blank 3 |
| Committees named | 13 (Planificacion 866 bills, Naciones y Pueblos 412, Economia Plural 329, ...) |
| Full read | 55 pages, 224 seconds at one request a second |
| A weekly read | current year (10 pages) plus `modified_after` three weeks: 36 seconds |

Quirks, measured:

- **Twelve spellings of a bill number.** `PL No 820/2025-2026`,
  `PL N° 005/2020-2021`, `PLS N°092/2024-2025`, `PLS-291/2025-2026`,
  `PLA 429-2023-2024`, `PLA  N° 113/2021-2022`, `PL CS N°098/2022-2023`,
  `PL-CS N° 125/2021-2022`, `PLS CD N° 114/2019-2020`, `N°219/2022-2023`,
  laws as `PLP LEY D N° 1512` and as `Ley de 11 de Noviembre de 2022` with
  the number in `ley_nro` (`Ley No 1491`, or a bare `348`).
  `src/bo_store.dip_key` folds all of them into one canonical key and keys
  99.3% of records (5,315 of 5,352); the other 37 (mostly `PLA 386-21`
  stubs with no year) are kept under their post id.
- **`PLS` is a Senado bill in revision at Diputados** and carries the
  Senado's number: `PLS-133/2025-2026` is the Senado's
  `P.L. N° 133/2025-2026 C.S.` (same church, same title).
- **`PLA` is the approved text of a Diputados bill**, posted as a second
  record: `PLA 429-2023-2024` (Aprobado, October 2024) beside
  `PL No 429/2023-2024` (Archivado, June 2024). The collector folds them
  and lets the most recently modified post speak.
- **Bill PDFs are scans.** PL 691/2025-2026 is 25 pages, 2.8 MB, and pypdf
  finds no text on any page. Titles are all there is from this chamber.
- **The server stalls.** The first trial run lost the current-year query
  to four consecutive 60-second timeouts; five minutes later the same query
  answered in 1.4 seconds. Treated as a gap (exit 3), re-read next week.
- There is no robots.txt (404) and no rate-limit header.

### Senado bills: works today, open, no key

`GET https://apisi.senado.gob.bo/page/<list>/buscar?per_page=100&page=N`,
found in the site's React bundle (`senado.gob.bo/assets/index-*.js`:
`apiUrl: "https://apisi.senado.gob.bo/page"`). Laravel-style paging
(`data.data`, `data.total`, `data.last_page`); `per_page=100` is honoured.
Each record: `id`, `titulo` (`P.L. N° 743/2025-2026 C.D.`, `LEY N° 1754`),
`numero`, `asunto` (title), `documento` (PDF path under
`apisi.senado.gob.bo/images/`).

| List | Records |
|---|---|
| `ley-tratamiento` (in treatment) | 323 |
| `ley-aprobados` (approved) | 176 |
| `ley-sancionada` (sanctioned, sent for promulgation) | 56 |
| `ley-promulgada` (promulgated laws, `LEY N° ...`) | 170 |
| `ley-rechazada` (rejected) | 26 |
| `ley-devuelto` (returned) | 3 |

750 distinct keys; four bills sit in both `aprobados` and `sancionada`
(the collector keeps the more advanced stage). By legislative year:
2025-2026 340, 2024-2025 181, 2023-2024 48, earlier 15. 268 keys are also
on diputados.gob.bo, so a bill's passage through both chambers joins on
one row. The Senado's PDFs are OCR'd: P.L. 743/2025-2026 has a usable,
imperfect text layer ("ASAMBL€A L€GISLATIVÁ"), which makes full-text
classification possible later.

The same API also serves, all open:

| Endpoint | Records | Use |
|---|---|---|
| `peticion-informe-escrito` | 4,770 | written questions to ministers, with summary and answer PDF |
| `peticion-informe-oral` | 81 | oral questions |
| `minutas-comunicacion` | 798 | Senate recommendations to authorities |
| `declaraciones-camarales` | 423 | chamber declarations, with the proposing senator |
| `resolucion-camarales` | 150 | chamber resolutions |
| `comisiones-permanentes` | 10 commissions with their comites | committee structure |
| `sesiones` | 0 | empty: no session records |
| `calendarios/horario?categoria=senado` | 0 | empty calendar |

The Senado's contact forms carry a reCAPTCHA site key; no data endpoint
does, and nothing here touches a form.

### Members: works, thin on the Diputados side

- **Senado:** `senadores/pleno`, 72 records: 36 titulares and 36
  suplentes, each with bancada (name and code), department (`brigada`)
  and board role. The fuller `senadores` endpoint (144 records) also
  serves e-mail, date and place of birth: **not stored**.
- **Diputados:** `wp/v2/diputados`, 255 posts (130 seats plus suplentes
  and replacements; the site does not say which). Name, seat
  ("Diputado/Diputada Nacional"), board membership via the `cargo`
  taxonomy (7 on the Directiva) and a biography. **No party field at
  all**: the party appears only inside the biography text. Not stored
  beyond name and role.

### Questions: available, not built

Senado written questions (4,770, above) and Diputados
`wp/v2/peticiones-informe` (2,312 posts with petitioner, addressee and
summary) are both open. They are the best member-attributed signal
Bolivia offers, since votes are not published. Phase 2.

### Agenda: images only

Diputados `wp/v2/mec-events`: 968 events ("203a SESION ORDINARIA",
"AGENDA SEMANAL DEL 28 DE SEPTIEMBRE ..."), each an image
(`203°-SESION.jpg`) with an empty text body. Unreadable without OCR. The
Senado calendar endpoint is empty.

### Not reachable

- `gacetaoficialdebolivia.gob.bo` (the official gazette) and
  `vicepresidencia.gob.bo` (the Vice President presides over the joint
  Assembly) **do not resolve in DNS** from here, through the local
  resolver, 1.1.1.1 or 8.8.8.8. Not a block by us; recorded so a later
  probe can retry. Promulgated laws are in both chambers' lists anyway.
- `asamblea.gob.bo` does not resolve either.

### Courts and other channels

The Tribunal Constitucional Plurinacional is a major channel on our
ground in Bolivia: by reputation its rulings have shaped abortion access,
the reach of the 2016 gender identity law and the registration of
same-sex free unions. Its site was not probed in this pass, so none of
that is measured here; listed for phase 3. The nine departmental
assemblies are later.

## How much touches CitizenGO's ground

With the proposed Spanish terms below (a measurement draft, not config),
over bill titles:

| Corpus | Titles | On our ground (not migration) | Tier 1 |
|---|---|---|---|
| Diputados, all records 2020-2026 | 5,352 | 54 (1.0%) | 29 |
| Diputados, legislatura 2025-2026 | 958 | 11 | 5 |
| Senado, all stage lists | 754 | 6 | 5 |

By area, Diputados 2020-2026: gender (Ley 348 and its amendments) 10,
marriage and family 6, free speech 7, religion 8, prostitution and
trafficking 6, parental rights and education 5, abortion 5 (the "Dia del
Nino por Nacer" bill filed five times since 2022), organ donation 5,
assisted dying 2.

The current legislative year, by hand:

| Key | What | Status |
|---|---|---|
| PL 691/2025-2026 CD | Ley de cuidados paliativos, muerte digna y **eutanasia** | in committee (Constitucion), filed 19 Aug 2026 |
| PL 790/2025-2026 CD | donation and transplant of organs, tissues and cells | in treatment |
| PL 797/2025-2026 CD | chronic kidney disease, faster organ donation | in treatment |
| PL 788/2025-2026 CD | amends the Codigo de las Familias (Ley 603) | in treatment |
| PL 126/2025-2026 CS, PL 158/2025-2026 CS | Senado amendments to the Codigo de las Familias | in treatment |
| PL 238/2025-2026 CS | libertad de conciencia and political neutrality in higher education | in treatment |
| PL 37/2025-2026 CS, PL 306/2025-2026 CD | conscientious objection to military service | in treatment |
| PL 603/2025-2026 CD | discrimination and harassment on social media (speech) | in treatment |
| PL 415/2025-2026 CD, PL 66/2025-2026 CD | reform of Ley 070, the education law | in treatment |
| PL 297/2025-2026 CD, PL 714/2025-2026 CD, PL 41/2025-2026 CS | amend Ley 348 (violence against women) | in treatment |

Earlier and notable: Ley 807 (2016, change of name and sex for
transsexual and transgender people), Ley 1161 (2019, religious freedom
and religious organisations, with four bills since to extend its
registration deadline), Ley 1639 (child marriage ban, amending Ley 603),
and the 2023-2024 "hombres victimas de violencia familiar" bill.

Noise measured and removed from the draft: `iglesia*` (44 hits, almost all
heritage declarations of colonial churches), `despatriarcalizacion` (the
name of a ministry receiving property transfers), and `curricula` /
`curriculo escolar` alone (financial education bills), now guarded.

## Proposed Spanish terms (for Chris's approval)

The base is the shared list proposed in `docs/peru-scope.md` on the Peru
branch (same areas, same tiers, accent-folded on both sides, `*` a stem
wildcard); only the differences are listed here so the lists merge
cleanly. **BO** marks a Bolivia-specific term (a Bolivian law, institution
or ruling); everything else is shared Spanish.

**Add, Bolivia-specific:**

- 1 Abortion. Tier 1: aborto impune (BO: Penal Code art. 266).
- 5 Sex-based rights. Tier 1: ley 807 (BO: the 2016 gender identity law).
  Tier 2: ley 348, vida libre de violencia (BO: Ley 348, the comprehensive
  law on violence against women, amended or challenged by a bill most
  years), paridad y alternancia (BO: electoral parity rules), equidad de
  genero, diversidades sexuales.
- 6 Parental rights and education. Tier 2: ley 070, avelino sinani (BO:
  the 2010 education law), unidades educativas privadas, unidades
  educativas de convenio (BO: church-run schools under agreement);
  guarded tier 2: curricula, curricul* escolar, malla curricular, only
  with sexual*, genero, valores, religio*, moral* or padres.
- 7 Free speech. Tier 1: ley 045, racismo y toda forma de discriminacion
  (BO: Ley 045 against racism and discrimination, with its media
  sanctions). Tier 2: ley de imprenta (BO: the 1925 press law).
- 8 Freedom of religion. Tier 1: organizaciones religiosas, creencias
  espirituales, ley 1161 (BO: Ley 1161 de Libertad Religiosa,
  Organizaciones Religiosas y de Creencias Espirituales), estado laico
  (BO: Constitution art. 4, "independiente de la religion"), objecion de
  conciencia (moved here from area 1 for Bolivia: every Bolivian hit is
  conscientious objection to military service).
- 9 Marriage and family. Tier 1: codigo de las familias, ley 603 (BO: the
  2014 Family Code), mismo sexo. Tier 2: union libre, uniones libres (BO:
  Constitution art. 63 "uniones libres o de hecho").
- 12 Prostitution and trafficking. Tier 1: trata y trafico, ley 263 (BO:
  Ley 263 Integral contra la Trata y Trafico de Personas).
- 13 Organ donation. Tier 1: ley 1716 (BO: the 1996 organ donation and transplant law).
- 2 Assisted dying. Tier 2: enfermo* terminal* (kept for Bolivia: no
  pension noise in these titles, unlike Peru).

**Drop or demote for Bolivia (shared terms that misfire here):** `iglesia*`
alone (heritage churches; keep `iglesia catolica` tier 2);
`despatriarcalizacion` (a ministry's name); `curricul* escolar` and
`curricula` unguarded. "Genero" alone stays out, as in Peru.

## What was built (phase 1, 9 October 2026)

- `tools/bo_rollcalls.py`: members of both chambers; Diputados bills (the
  current legislative year whole, plus anything modified in the last 21
  days; `--backfill` reads all 5,352 once); every Senado stage list.
  `--reclassify` re-derives areas offline. Exit 3 means it stored what it
  could and recorded gaps. The name keeps the country tools' pattern;
  the docstring says plainly that there are no roll calls to collect.
- `src/bo_store.py`: `bo_members`, `bo_bills` (one row per bill across
  both chambers: `dip_*` and `sen_*` columns), `bo_bill_changes` (every
  status or stage move, with old and new). No vote tables until a
  per-member source exists. Canonical keys `PL 820/2025-2026 CD`,
  `PL 291/2025-2026 CS`, `LEY 1754`, never the title.
- `config/watchlist-bo.yaml`: an eight-entry draft (the table above),
  applied by key.
- Classification: `config/taxonomy-es.yaml` when it exists, otherwise the
  English taxonomy (blind; the plumbing runs). When `taxonomy-es` lands,
  dispatch the workflow with "reclassify".
- Tests: `tests/test_bo_rollcalls.py` (26 tests) on real replies in
  `tests/fixtures/bo/` (a Diputados `ley` page of nine records covering
  each key shape, PL and PLA pairs and an unnumbered stub; Senado stage
  pages; both member lists, a biography cut; a test-only Spanish term
  file, not the proposed taxonomy).
- The weekly job, Mac Mini first: `jobs/bo-weekly.sh` (the
  `jobs/au-weekly.sh` pattern, `BO_PUBLISH=false` under GitHub, publish
  order archive then store), `ops/launchd/net.citizengo.parlmonitor.bo-weekly.plist`
  (Sundays 11:00 London) and `.github/workflows/bo-weekly.yml` (Sundays
  12:30 and 16:30 UTC, gated by `mini-check.yml` with job `BO_WEEKLY`,
  grace 420 minutes; a `backfill` dispatch input for the first run). It
  needs only `pyyaml`. **It runs on GitHub only once merged to main.**

A trial run into a scratch database (not the store): 327 members (255
Diputados, 72 Senado), 1,522 bills, 186 in both chambers, 8 on our ground
(all via the watchlist: the English taxonomy found none), 36 seconds.

### Edits to shared files (for the merge of the country branches)

- `src/db.py`: three `bo_*` names in `TABLES`; two lines in `init_db`
  calling `bo_store.ensure_schema`.
- `tools/coverage.py`: "Bolivia weekly" in `PIPELINES`, `PIPELINE_FEEDS`
  and `AWAITING_FIRST_RUN`; two `bo_*` rows in `FEEDS`.
- `.github/workflows/alert.yml`: "Bolivia weekly" in the watched list.

Nothing else outside Bolivia's own files changed. `docs/mac-mini.md` is not
edited; its job table needs a row for `bo-weekly` (Sundays 11:00, backup
12:30/16:30 UTC, `MINI_LAST_BO_WEEKLY`, grace 420) when this merges.

## Phase plan

1. **Phase 1 (built):** members, bills of both chambers with stage moves,
   Spanish classification once approved. The weekly edition section is
   "what moved": new bills on our ground, and stage changes
   (`bo_bill_changes`) on watched or matched bills.
2. **Phase 1b:** a first `--backfill` run; classify Senado bills on their
   OCR'd PDF text as well as the title (pypdf, already used elsewhere).
3. **Phase 2:** written and oral questions (Senado 4,851, Diputados
   2,312), which name the member; Senado declarations and minutas (they
   name the proposing senator).
4. **Phase 3:** the Tribunal Constitucional Plurinacional; retry the
   Gaceta Oficial when it resolves; departmental assemblies.
5. **Never, unless the chambers change:** per-member votes. If Diputados
   ever publishes its electronic vote results, `bo_divisions` and
   `bo_votes` follow the Peru schema.

## Dates that matter

- The legislative year rolls over in November (2025-2026 started on
  20 November 2025); bill numbering restarts with it, which is why the
  year is in every key. The collector finds the newest `legislatura_de_ley`
  term each run, so the rollover needs no code change.
- The current Assembly was installed in November 2025.

## Waiting on Chris

1. **Approve the Spanish term list**, the Bolivia additions above and the
   demotions, so `config/taxonomy-es.yaml` can be generated (one shared
   file across the Spanish-language countries, or one per country?).
   Until then the edition sees only the watchlist.
2. **Accept a bills-only edition.** There are no per-member votes to
   publish; the edition would report new bills on our ground and their
   moves between stages. Worth it, given a plural Assembly with live
   bills on euthanasia, the Family Code and conscience; but it is a
   thinner product than Peru or Spain.
3. **Confirm or prune `config/watchlist-bo.yaml`** (eight bills).
4. **Merge to main and switch on**: create `MINI_LAST_BO_WEEKLY`, install
   the plist on the Mini, add the `docs/mac-mini.md` row, and dispatch the
   first run once with `backfill` ticked.
5. **Phase 2 go-ahead** for written questions, the one member-attributed
   source Bolivia offers.

## Decisions of 10 October 2026 (applied at the countries merge)

Recorded in `docs/country-decisions-2026-10-10.md`. Shared: accents fold and non-ASCII letters are word characters in the filter (X3); member positions are stored for every vote (X15); the AI judge stays off (X16).

Applied on the `countries` branch:

- Term list approved (BO1) and merged into the shared `config/taxonomy-es.yaml` (`docs/keyword-taxonomy-es.md`), loaded for this country's code.

Later phases and items for Chris (not built at the merge):

- Bills only (BO2).
- Phase 2: written questions (BO4).
