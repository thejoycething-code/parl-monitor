# Venezuela: scoping the Asamblea Nacional monitor

Probed live on 9 October 2026 from the UK, with the project User-Agent
(`CitizenGO-ParlMonitor/1.0`), a 2 second throttle and every response archived
under `data/raw/ve-probe/` (247 files, 4.6 MB). The probes are reproducible
with `tools/ve_probe.py` (single URLs), `tools/ve_news_crawl.py` (the news
sample) and `tools/ve_news_scan.py` (the term scan). No CAPTCHA or bot
challenge was met; two plain HTTP 403s are noted below.

## Recommendation, first

**Do not build a Venezuela edition.** Keep a manual watch on one item (the
reform of the *Ley contra el Odio*) and revisit only if the Assembly's
make-up or publishing changes.

The reasons, all measured below:

1. **No recorded votes, and nothing to record.** In six months of the
   Assembly's own legislative news (203 items), every decision that mentions a
   vote was reported as unanimous; the only number given was "275 votos a
   favor" for the Attorney General's appointment. No per-member positions are
   published anywhere. The 5CA layer, which is the point of the other
   editions, cannot exist here.
2. **The official bill register is frozen.** The *Proyectos*, *Sancionadas*
   and *Vigentes* lists stop in July 2022, December 2021 and February 2023
   respectively, although the Assembly sanctioned about 20 laws in the last
   six months (counted from news headlines). The *Gaceta Legislativa* search
   returns "No se encontraron resultados".
3. **The agendas are scanned images.** The 2026 *orden del día* PDFs (about
   30, last one 26 August 2026) have no text layer; reading them needs OCR.
4. **Very little touches CitizenGO ground.** Two of the 203 news items do,
   both about the same reform (free speech). Nothing on abortion, marriage,
   gender identity, euthanasia or religious liberty in six months.
5. **Little independence.** The Assembly elected in 2025 is dominated by the
   governing PSUV bloc; unanimity is the norm, and the decisions that matter
   come from the executive and the Supreme Tribunal (TSJ), whose site timed
   out from here.

## What Venezuela publishes

### asambleanacional.gob.ve (open, no key) -- REACHABLE, THIN

Only `www.asambleanacional.gob.ve` answers; the bare domain did not resolve
from our resolver. `robots.txt` allows everything. Server-rendered HTML,
UTF-8, about 1.4 s per page, no API (`/api` and `/sitemap.xml` are 404).

| Section | URL | Measured |
|---|---|---|
| Bills | `/leyes/proyectos` | 15 bills on page 1, newest entered 17/07/2022. Page 2 (`?page=2`) returns **HTTP 403**. Detail pages (`/leyes/proyecto/<slug>`) give status, dates of first and second reading, committee and initiative; keyed by slug, no numeric ID. |
| Sanctioned laws | `/leyes/sancionadas` | 2 entries, both 14/12/2021 (2022 budget and borrowing laws). `?page=2` is 403. |
| Laws in force | `/leyes/vigentes` | 10 entries, newest 23/02/2023, with *Gaceta Oficial* number. |
| Legislative gazette | `/gacetas` | Empty: "No se encontraron resultados". |
| Search | `/buscar?q=...` | HTTP 403. |
| Members | `/diputados?page=1..15` | 289 profiles (14 pages of 20 plus 9). Each profile gives party (e.g. PSUV) and state; no votes, "No hay proyectos relacionados". |
| Plenary resolutions | `/actos` | *Acuerdos* from 2021 to 19/05/2026; the 2026 ones are commemorations and political statements (Esequibo, sanctions, baseball). |
| Documents | `/transparencia/documentos` | 228 PDF links from 2021 to 26/09/2026, including the 2026 *orden del día* PDFs (image only, no text layer), the Amnesty Law bill, judicial nominations lists. |
| News | `/noticias?categoria=Legislativa&page=N` | Current (newest 07/10/2026), about 15 items per page, 167 pages. Pagination works here. **This is the only live, structured source.** |

The `/sec/proyectos-de-reforma-leyes-del-poder-popular` page exists but
lists nothing parseable as bills.

### Other channels

- **TSJ (tsj.gob.ve)**: timed out after 30 s on both http and https, three
  tries. Likely geo-restricted or down. The Constitutional Chamber is the real
  decision point on rights questions in Venezuela, so this is the channel that
  would matter, and it is unreachable.
- **The 2015 Assembly** (`asambleanacionalvenezuela.org`): the domain has
  lapsed and now redirects to an unrelated restaurant site.
- **Acceso a la Justicia** (`accesoalajusticia.org`, NGO): reachable, tracks
  the Assembly and the TSJ critically. A possible secondary source for a human
  reader, not a data feed.
- **Gaceta Oficial / Procuraduría (`pgr.gob.ve`)**: certificate chain fails
  verification; not pursued.
- **Regional bodies**: the 23 state *Consejos Legislativos* exist; not
  probed, and not worth it on this evidence.

## Taxonomy match (measured)

Sample: all 203 items in the *Legislativa* news category from 09/04/2026 to
07/10/2026 (14 list pages, 203 article bodies, no fetch errors after one
transient HTTP 500 was retried).

- A first pass with broad Spanish stems matched 45 items, but by hand nearly
  all were noise (housing, earthquake relief, "redes sociales" in
  boilerplate, "despenalización" inside the hate-law story).
- **Hand-checked, real CitizenGO ground: 2 of 203** (1%), both on the
  reform of the *Ley Constitucional contra el Odio, por la Convivencia
  Pacífica y la Tolerancia* (2017): a special committee of 11 deputies is
  drafting it, and government deputies talk of easing prosecutions of
  journalists. That is a free speech item worth knowing about.
- Zero items mention *aborto*, *iglesia*, *LOPNNA*; "género" appears in 4
  items, none on gender identity; "educación" in 15, none on curriculum or
  parental rights.
- Vote language: 17 items; 16 say *por unanimidad*; numeric tallies appear
  in 3 items, all the same 275-vote appointment.

The English taxonomy was not run: the Germany precedent already shows it is
blind to another language, and the hand count above is the honest figure.

## Proposed Spanish terms

Use the Spain branch list (`docs/spain-scope.md` on the `spain` branch, the proposed Spanish base for
all Spanish-language editions) as the shared list. Venezuela-specific
additions, only if an edition is ever built:

- Speech: "Ley contra el Odio"; "Ley Constitucional contra el Odio";
  "convivencia pacífica y la tolerancia"; "Ley de Responsabilidad Social en
  Radio, Televisión y Medios Electrónicos" (Resorte-ME); "Ley de
  Fiscalización, Regularización, Actuación y Financiamiento de las
  Organizaciones No Gubernamentales" (2024 NGO law; association and
  religious charities).
- Children and family: "LOPNNA"; "Ley Orgánica para la Protección de Niños,
  Niñas y Adolescentes"; "Ley de Tutela Civil"; "unión estable de hecho";
  "Ley Orgánica de Registro Civil".
- Gender: "sexodiversidad" / "sexo-diversa*" (local usage); "Ley Orgánica
  sobre el Derecho de las Mujeres a una Vida Libre de Violencia" (tier 2).
- Religion: "Comisión Permanente de las Familias, la Libertad de Religión y
  de Cultos" (the committee that would own any such bill).
- Education: "Ley Orgánica de Educación"; "Ley de Participación Estudiantil".

Life terms need no local additions: abortion remains in the Penal Code
(arts. 430 to 433) and no reform appeared in the sample.

## Phase plan

- **Phase 0 (this document)**: done. No collector built, by design: there is
  no vote source, the bill register is stale, the agenda needs OCR, and the
  topical yield is about one item a quarter.
- **If Chris still wants coverage**: a monthly keyword pass over the
  *Legislativa* news feed (about 35 items a month, one page fetch per 15
  items, no key) feeding a two-line note in another Spanish edition, rather
  than a standalone edition. Roughly half a day of work, reusing
  `tools/ve_news_crawl.py`.
- **Revisit triggers**: the Assembly starts publishing per-member votes; a
  life, family or gender bill appears; the bill register is updated again;
  the TSJ site becomes reachable.

## Waiting on Chris

1. **Confirm: no Venezuela edition.** (Recommendation above.)
2. If some coverage is wanted: monthly news-feed keyword note folded into
   another edition, yes or no.
3. Should the *Ley contra el Odio* reform be added by hand to a watch list
   somewhere (it has no bill ID on the site; the only stable reference is the
   2017 law's name and the special committee)?
4. Approve the Venezuela-specific Spanish terms above only if an edition is
   ever revived; otherwise ignore.

## Files touched

Country-only: `docs/venezuela-scope.md`, `tools/ve_probe.py`,
`tools/ve_news_crawl.py`, `tools/ve_news_scan.py`. Raw archive in
`data/raw/ve-probe/` (git-ignored, like all of `data/raw/`). **No shared
files edited.**

## Decisions of 10 October 2026 (applied at the countries merge)

Recorded in `docs/country-decisions-2026-10-10.md`. Shared: accents fold and non-ASCII letters are word characters in the filter (X3); member positions are stored for every vote (X15); the AI judge stays off (X16).

Applied on the `countries` branch:

- Terms merged into the shared `config/taxonomy-es.yaml` (`docs/keyword-taxonomy-es.md`), loaded for this country's code.

Later phases and items for Chris (not built at the merge):

- Built on the `latam` branch: a monthly keyword note from the Asamblea's news feed (VE1-VE3, `tools/ve_news.py`, in the Latam monitor), and the Ley contra el Odio reform watched by hand (`config/watchlist-ve.yaml`).
