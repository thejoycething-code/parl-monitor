# Peru: regional governments and Lima Metropolitana (PE4)

Scoped and built 12 October 2026, branch `regions-pe`. Every number below was
measured live from the laptop that day, through `src/http.py` (the honest
CitizenGO UA, throttled), with the raw replies archived under `data/raw/`.

## What the regional layer is

Peru has 25 regional governments: the 24 departments plus the Constitutional
Province of Callao. Each has a Gobernador Regional (executive) and a Consejo
Regional (the legislature, 7 to 25 consejeros) that passes **ordenanzas
regionales** (the region's laws) and **acuerdos de consejo regional**
(resolutions: declarations, approvals, travel, transfers). The governor issues
**decretos regionales** and resoluciones. Lima Metropolitana is not one of the
25: the Municipalidad Metropolitana de Lima holds the regional functions for
the province of Lima (Ley Orgánica de Municipalidades, arts. 151 onwards), and
its Concejo Metropolitano passes ordenanzas (numbered 2,8xx in 2026). It is
read with the regions. The Gobierno Regional de Lima covers the provinces
outside the capital.

An ordenanza regional takes effect only once published in **El Peruano**, the
official gazette. That makes the gazette the one national source for every
region's laws.

## Sources

| Source | What | Format | robots.txt | Reachable | Used |
|---|---|---|---|---|---|
| El Peruano, Normas Legales (`diariooficial.elperuano.pe/Normas/Filtro`) | every norm published in a date range, with issuer heading, number, date, sumilla, dispositivo link and PDF link | HTML, one read-only form POST (`cddesde`, `cdhasta`, day first) | disallows only `/Normas/NLactualizada` and file folders; the filter is allowed | yes, 200, no challenge served (2.3 s for ten days) | **yes, weekly** |
| El Peruano dispositivo pages (`busquedas.elperuano.pe/dispositivo/NL/<id>`) | the full text of each norm | Next.js HTML, text server-rendered | `Allow: /` | yes | linked, not read (see "What is classified") |
| El Peruano search (`busquedas.elperuano.pe/?q=`) | full-text search | client-side, behind a bot-manager script (`/bnith__...js`) | allowed | the results are fetched by script, not in the HTML | **no**: not worth it when the Filtro form serves the same listing in plain HTML |
| gob.pe, each institution's `normas-legales/tipos/<type>` pages | the institution's own uploads by norm type, 25 newest per page, with sumilla, date and a CDN PDF | HTML | disallows `/admin/` and `?sheet=` only | yes, 200 for all 26 institutions | **yes, weekly**, council acts only |
| Regional councils' own sites (agendas, actas, session videos) | sittings, agendas, minutes | 26 different sites, mostly PDF or Facebook video | varies | not probed one by one | no (see "Not built") |
| JNE Infogob / Plataforma Electoral | consejeros regionales and their parties | HTML | not probed | not probed | no |

### El Peruano, measured

- 1 to 10 October 2026: 597 norms from all issuers in one reply (992 KB);
  September 2026: 2,285 norms in one reply (3.8 MB, 4.1 s). No cap seen: every
  day of the range is present, Sundays included.
- Regional governments' and Lima Metropolitana's norms, 1 September to
  12 October 2026: **105** (35 ordenanzas regionales, 24 acuerdos, decretos,
  resoluciones, and Lima's ordenanzas, acuerdos de concejo and decretos de
  alcaldía). 22 of them were Lima Metropolitana's.
- Two article classes: `edicionesoficiales_articulos` and, for the
  "Publicación Digital" norms (Lima Metropolitana's among them),
  `edicionesoficiales_articulos_dig`, whose heading carries a
  `<br />Publicación Digital` tail. Both are read.
- The form's dates are day first (`01/09/2026`); the form action's
  `dateparam` is month first, as the page's own form sends it.

### gob.pe, measured

All 26 institution slugs answered (`regionamazonas` ... `regionucayali`,
`munilima`). Each institution's `normas-legales/tipos` page lists the types it
has used; the council's acts are type 40 (ordenanza regional), 246 (acuerdo de
consejo regional) and 79 (acuerdo regional), and for Lima 13 (ordenanza) and
108 (acuerdo de concejo). The types read per institution are in
`config/pe-regions.yaml`. A full weekly pass is 61 pages at 3 s: 4.5 minutes
measured (1,305 listing rows, no refusals).

How current each institution keeps its gob.pe pages varies a great deal,
which is why the gazette leads and gob.pe fills in:

| Region | Pop. (m) | Gazette norms, 1 Sep to 12 Oct | gob.pe rows read | Latest ordenanza on gob.pe | On our ground in the first read |
|---|---|---|---|---|---|
| Lima Metropolitana | 10.1 | 22 | 32 | March 2025 (stale; gazette only) | 0 |
| Piura | 2.1 | 3 | 75 | Sep 2026 | 1 |
| La Libertad | 2.0 | 9 | 50 | Sep 2026 | 0 |
| Arequipa | 1.5 | 10 | 53 | Oct 2026 | 2 |
| Cajamarca | 1.5 | 3 | 27 | April 2022 (stale; gazette only) | 0 |
| Junín | 1.4 | 5 | 52 | Oct 2026 | 1 |
| Cusco | 1.4 | 3 | 74 | Mar 2026 | 1 |
| Lambayeque | 1.3 | 6 | 67 | Sep 2026 | 0 |
| Puno | 1.2 | 8 | 50 | May 2025 (stale) | 0 |
| Callao | 1.2 | 1 | 55 | Sep 2026 | 0 |
| Áncash | 1.2 | 10 | 38 | Jul 2026 | 0 |
| Loreto | 1.1 | 0 | 54 | Jun 2026 | 2 |
| Ica | 1.0 | 1 | 50 | Sep 2026 | 0 |
| Lima (region) | 1.0 | 0 | 50 | Apr 2026 | 0 |
| San Martín | 0.9 | 0 | 37 | Dec 2023 (stale) | 0 |
| Huánuco | 0.8 | 0 | 2 | Jan 2025 (nearly empty) | 0 |
| Ayacucho | 0.7 | 1 | 52 | Apr 2026 | 2 |
| Ucayali | 0.6 | 3 | 50 | Aug 2026 | 3 |
| Apurímac | 0.4 | 2 | 50 | Sep 2026 | 1 |
| Amazonas | 0.4 | 2 | 50 | Sep 2026 | 2 |
| Huancavelica | 0.4 | 2 | 75 | Dec 2025 | 0 |
| Tacna | 0.4 | 1 | 51 | Aug 2026 | 0 |
| Pasco | 0.3 | 2 | 48 | Apr 2026 | 1 (noise, filtered) |
| Tumbes | 0.3 | 9 | 48 | Oct 2026 | 2 |
| Moquegua | 0.2 | 1 | 48 | Aug 2026 | 1 |
| Madre de Dios | 0.2 | 1 | 50 | Sep 2026 | 0 |

Population: rounded INEI estimates, for ranking only. "On our ground in the
first read" counts shown kinds (ordenanzas, acuerdos, decretos) the taxonomy
or watchlist placed in a visible area, over everything the first run stored
(the gazette's six weeks and gob.pe's 25 newest per type, back to 2018 for
slow uploaders).

## Ranking (CitizenGO relevance and source quality)

1. **Lima Metropolitana**: a third of the country; its Concejo Metropolitano's
   ordenanzas are in the gazette every week (22 in six weeks). Gob.pe is stale,
   so the gazette is its source.
2. **Arequipa, Piura, La Libertad, Junín, Cusco, Lambayeque, Callao**: the
   large regions, current on both sources. Arequipa passed the region's
   educación sexual integral ordinance (538-2025, tier 1) and a child-marriage
   board (561-2026).
3. **Ayacucho, Ucayali, Amazonas, Tumbes, Loreto, Apurímac, Moquegua**: small
   but the most active on our ground in the sample (child marriage under Ley
   31945, sexual violence, "conciliación de la vida familiar", gender
   mainstreaming and gender-equality plans).
4. **Cajamarca, Puno, San Martín, Huánuco**: large or medium regions whose
   gob.pe pages are stale or nearly empty; covered through the gazette only.

## What the taxonomy finds

taxonomy-es v0.2 with Peru's country tag, over the heading and the sumilla
only, matched 19 norms of the 1,352 stored: child and forced marriage (areas
9), the region's sex-education ordinance (6, tier 1), gender-equality plans and
"transversalización del enfoque de género" (5), violence against women and
sexual harassment (5, 12), trafficking (12, with migration 11 hidden), family
policy (9). One false positive: an acuerdo declaring a colonial church of
"interés turístico" matched "iglesia" (8); it is filtered by a Peru line in
`config/latam-noise.yaml`. A few relevant sumillas carry no term (Puno's
ordenanza guaranteeing school access and continuity for girls, Tumbes's
"protección integral" of children): the session judge or a watchlist entry is
the route for those, not a looser term.

No term-list change was proposed at the build: the national list covers what
the regions pass. The two country-specific candidates were **APPLIED 13
October 2026** (Chris, 13 October 2026: "Accept the watchlists, apply the terms after measuring"; taxonomy-es v0.4, both tagged pe, area 9):
"uniones infantiles tempranas forzadas" (tier 1) and Ley 31945 as the number
`31945` guarded by ley, matrimonio* or menores (tier 1), because the gazette
prints the law as Ley N"31945 and Ley N."° 31945, which no phrase matched.
Measured on the 2,238 stored regional norms: Arequipa's ordinance 561-2026
and Ayacucho's 19-2025 and 21-2025 match, all already area 9 through
"matrimonio"; national bills unchanged; 0 false positives.

## What is classified

The heading and the sumilla, verbatim. Never the full text: every regional
ordinance's considerandos cite articles 4 and 6 of the Constitution
("protegen especialmente al niño, al adolescente, a la madre...") whatever the
subject, the Canadian lesson (tools/ca_courts.py). When gazette and gob.pe
both hold a norm, the longer sumilla is kept (gob.pe's often quotes the
operative article).

## As built (12 October 2026)

- `tools/pe_regions.py`: one El Peruano Filtro POST for the last 14 days
  (`--since` for a longer seed), then the council-act pages of each
  institution on gob.pe (3 s apart; `--budget-seconds` cuts the pass short and
  records the gap; `--no-gobpe` for the gazette alone); `--reclassify`,
  `--dry-run`, `--db`. Exit 3 on a recorded gap.
- `pe_regional_norms` (src/pe_store.py, in db.TABLES): one row per norm,
  keyed `'<region>/<kind>/<n>-<year>'` (the printed number reduced to its first
  integer and year, so `000013-2026-GR.LAMB/CR` in the gazette and
  `0013-2026-GR.LAMB/CR` on gob.pe meet on one row); `source` says which saw
  it; the gazette's date, link and heading win.
- `config/pe-regions.yaml`: the 26 institutions, gazette headings, gob.pe
  slugs, types read, population.
- Watchlist: a `regional` section in `config/watchlist-pe.yaml`, keyed by
  norm_key (none yet); a watched norm is tier 1 and always shown.
- Latam monitor (monthly, `tools/latam_monitor.py`): Peru's section gains a
  sub-heading **"Regional governments and Lima Metropolitana"** under the
  Congress's items, with its own cap of 12; kind "Regional norm"; each item
  gives the sumilla (Spanish, verbatim), the norm's English kind and region,
  its printed number, where it was seen, and the PDF. Shown: ordenanzas,
  acuerdos and decretos on our ground or watched; resoluciones are stored and
  never shown. Window: dated in the month, or first seen in it when dated at
  most 60 days before; the first run's seed counts only by date, so switching
  the layer on floods nothing. A Coverage line says when the layer was last
  read and how many norms it holds.
- Instant alerts (`tools/latam_alerts.py`): a watched or tier-1 regional norm
  with the minimum evidence alerts like any Latam item, after the
  collectors in the Peru weekly.
- `jobs/pe-weekly.sh`: a step after the Tribunal's press notes and before the
  vote briefs and alerts, budget `collector_budget.sh 300`; the Congress
  collector's budget now keeps those 300 s aside. `PE_RECLASSIFY=true` also
  reclassifies the regional norms. No new job, no new plist, nothing to
  install on the Mac Mini.
- `tools/coverage.py`: `pe_regional_norms` is a weekly heartbeat (re-stamped
  every run) and one of the Peru weekly's first-run tables.
- Tests: `tests/test_pe_regions.py` (17 tests, real replies trimmed into
  `tests/fixtures/pe_regions/`, no network).
- First live run (laptop, scratch store, 12 October): El Peruano 1 September
  to 12 October, 105 regional norms; gob.pe 1,305 rows; 1,352 norms stored;
  4 minutes 31 seconds; no gaps.

Shared files touched: `src/db.py` (TABLES), `src/pe_store.py`, `src/latam.py`,
`tools/latam_monitor.py`, `tools/coverage.py`, `config/latam-noise.yaml`,
`jobs/pe-weekly.sh`.

## Not built, and why

- **Votes**: regional councils publish no roll calls. Acuerdos record "por
  unanimidad" or "por mayoría" in the text at best; no per-member positions
  anywhere that was found.
- **Sittings and agendas**: each council posts its sesiones on its own site,
  in PDF or as Facebook video; 26 different formats with no shared platform.
  Not worth a scraper per region for the volume on our ground (about one
  norm a month across all 26).
- **Consejeros (members)**: not collected. The JNE's Infogob holds them by
  election; a later phase if regional votes ever become visible.
- **El Peruano's full-text search** (busquedas.elperuano.pe): client-side,
  behind a bot-manager script; not used, and not needed.
- **District and provincial municipalities**: out of scope (hundreds; the
  gazette carries Lima's districts' ordenanzas, which the collector skips).

## Waiting on Chris

- Whether regional tier-1 norms should send instant alerts (they do now, like
  every Latam item), or appear only in the monthly edition.
- Any regional norms to watch by hand (`regional:` section of
  `config/watchlist-pe.yaml`, keyed by norm_key), for sumillas no term catches.
- The Peru weekly job picks the step up when this branch is on main; nothing
  to install.

## Forward agenda (regional_agenda, 16 October 2026)

`src/regional_agendas/pe.py`, run by `tools/regional_agenda.py pe` (the
step in the Peru weekly is the lead's). Probed live from the laptop on 16
October 2026, robots.txt read first (gob.pe disallows only /admin/ and
?sheet= URLs), honest user agent, 3 s between requests.

The councils publish their session agendas mostly as PDFs or Facebook posts
(Facebook is not a route). The one machine-readable list is gob.pe's
publication type **'Agenda de Sesión de Consejo Regional'**
(`/institucion/<slug>/informes-publicaciones/tipos/91-agenda-de-sesion-de-consejo-regional`;
Lima Metropolitana's 'Agenda de Sesión de Concejo Municipal', type 93): one
entry per agenda or convocation, the sitting's date in the entry's own
words ('... del 15 de Octubre del 2026'), the agenda itself a PDF. Each
sitting in the window is one 'to be announced' item with the entry's title
and summary; a 'Reprogramada' convocation is dropped for the new one.

Measured, one request per institution: 13 of 26 have used the type. Newest
upload: Lima region 7 October (the 15 October sitting, a week ahead), Piura
11 September (on the sitting day), Ica 31 August (convocations a few days
ahead), Lambayeque 24 February, Arequipa 6 February, Ayacucho 18 June, Cusco
May 2025, Moquegua November 2024, Tumbes March 2024, Amazonas March 2023,
Lima Metropolitana January 2023, Callao January 2023, La Libertad July 2020.
These thirteen are read every run (cheap; a council that resumes is caught).
The other thirteen (Cajamarca, Junín, Puno, Áncash, Loreto, San Martín,
Huánuco, Ucayali, Apurímac, Huancavelica, Tacna, Pasco, Madre de Dios) have
never used it: no route. Also looked at: gob.pe's 'Agenda' page per
institution (the governor's or mayor's own diary, not the council; empty for
Lima and Arequipa, an iframe of servicios.regionpiura.gob.pe for Piura).

**Live run** (scratch store, 16 October 2026, 56 days): 13 of 26 read, 0
items (no council had posted a sitting after today), 51 s, no gap. The
route is honest but thin: expect a sitting or two a month, mostly from Lima
region and Ica.
