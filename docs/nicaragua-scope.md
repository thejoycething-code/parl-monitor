# Nicaragua: scoping the Asamblea Nacional monitor

Probed live on 9 October 2026 from the laptop (UK IP), with the CitizenGO
User-Agent, 2 seconds between calls. Every number below was measured. The
vote-list probe is reproducible with `tools/nic_probe.py`; raw responses are
archived under `data/raw/nic/` (git-ignored, as all of `data/raw/` is).

Prefix: **`nic` / `NIC`** throughout, because `ni` already means Northern
Ireland in this repo (`config/ni_stance.yaml`, `ni_watch.yaml`).

## Recommendation, in one paragraph

**Do not build a Nicaragua edition.** The data is better than expected (the
Assembly does publish every plenary vote with every member's name, open and
keyless), but it carries no information. In 21 months, **609 substantive
recorded votes produced 0 votes against and 0 abstentions**: every vote
passed with all members present voting yes. A per-member record in which
nobody ever dissents cannot tell Chris anything about any member. Across
the 146 distinct items voted, **no title touches CitizenGO's ground**
(abortion, family, gender, religion, education/parental rights, NGO status,
trafficking). The real pressure on CitizenGO's issues in Nicaragua,
religious freedom above all (closures of churches, religious associations
and NGOs; expulsions and denationalisation of clergy), runs through the
executive (Ministry of the Interior decisions published in *La Gaceta*) and
the courts, not through the Assembly. If Chris wants anything, the most it
is worth is a cheap monthly tripwire (see "If Chris wants a tripwire"),
and even that would mostly report constitutional reforms that are already
news.

## Context

The Asamblea Nacional is unicameral, 91 seats in the votes measured
(the maximum "Si" count in any vote is 91). Since the 2021 elections the
governing FSLN and allied parties hold every functioning seat; the 2025
constitutional reform reshaped the state around a co-presidency. The
Assembly passes executive initiatives unanimously, typically within days.
That is the setting for every number below.

## What Nicaragua publishes

### verifica.asamblea.gob.ni: plenary votes per member, open, no key, WORKS

Linked as "Votaciones" from the SELEY menu. ASP.NET WebForms pages, plain
GET, no JavaScript needed to read them.

* `https://verifica.asamblea.gob.ni/vtn/Votaciones_/Votaciones` lists years
  **1997 to 2026**. `Votaciones.aspx?...` 301-redirects to the extensionless
  path, so each fetch costs two requests.
* `Votaciones.aspx?anio=2026` lists months; `&mes=9` lists sitting dates;
  `&fecha=2026-09-29` lists the votes of that sitting. Each vote is a card:
  a running number (`24327`), a title that names the item and the stage
  (`... -> EN LO GENERAL`, `-> ARTICULO 4`), and counts
  `Si / No / Abs / Pres`.
* `VotacionDetalle.aspx?id=<GUID>&...` gives the per-member lists under
  `SI (90)`, `NO (0)`, `ABS (0)`, `PRS (0)`, the timestamp
  (`29/09/2026 10:48:00`) and the **Código Iniciativa** (`202610198`), which
  is the SILEG key. Members appear as short names (`EDWIN CASTRO`), **with
  no party**.
* Performance: usually under 1 second, but the TLS handshake stalls for
  60 seconds at random; the crawl of 2025 and 2026 (192 pages) needed 7
  retries and about 18 minutes.

Measured, 1 January 2025 to 9 October 2026:

| | 2025 | 2026 (to 9 Oct) |
|---|---|---|
| Recorded votes (all) | 589 | 190 |
| of which quorum calls | 124 | 46 |
| Substantive votes | 465 | 144 |
| Sitting dates with votes | 123 | 46 |
| "En lo general" votes (roughly, distinct bills) | 77 | 25 |
| Votes with any "No" | **0** | **0** |
| Votes with any abstention | **0** | **0** |
| "Si" count of 91 / 90 / 89 / 88 | 422 / 39 / 2 / 2 | 104 / 37 / 1 / 2 |

The 146 distinct items voted (titles stripped of the stage suffix), sorted
by a rough title rule: 38 laws or reforms, 27 treaties and agreements, 22
appointments and elections, 19 loans and credit agreements, 12 declarations
and commemorations, 5 constitutional reforms, 23 other.

### legislacion.asamblea.gob.ni / SILEG (SELEY): bill tracker, open, no key, WORKS over HTTP only

The "Sistema de Seguimiento de Ley". IBM Domino with XPages.

* **HTTPS times out** (40 s, twice). Plain **HTTP** answers in under 0.5 s.
* The XPages front end (`/SILEG/Iniciativas.nsf/index.xsp`) is postback
  driven and not worth scraping, but **classic Domino URLs work**:
  `/SILEG/Iniciativas.nsf/$defaultview?ReadViewEntries&ExpandView&Count=1000&outputformat=JSON`
  returns the view as JSON (500 KB), categorised by current stage
  (`EtapaActual`: Secretaria, Comision, Agenda, Comisión de Estilo,
  Presidencia, Archivo) and type (Ley, Decreto), with `CodigoIniciativa` and
  the title. Domino caps a request at 1,000 entries, so the full archive
  needs `&Start=` paging; 135 of the first 1,000 entries are 2024 to 2026.
* One initiative: `/SILEG/Iniciativas.nsf/xpIniciativa.xsp?documentId=<UNID>&action=openDocument`
  gives type, sponsor list (initiative `202610194`, a constitutional reform
  now in Secretaría, lists some 80 deputies as sponsors), and tabs for
  committee and publication.
* The Domino Data Service (`/api/data/collections`) is **403**. `normaweb.nsf`
  (the consolidated legislation database) just redirects to the main site.

### www.asamblea.gob.ni: BLOCKED (Cloudflare challenge)

Every path tried (`/`, `/wp-json/`, `/feed/`, `noticias.asamblea.gob.ni`)
returns **403 with `cf-mitigated: challenge`**, a Cloudflare managed
JavaScript challenge. Per the rules this was not solved or worked around.
This is where member pages, party groups, committee lists and the *Diario
de Debates* would be. Not needed for anything recommended here, but it is a
blocker for party affiliation.

### La Gaceta (lagaceta.gob.ni): open home page, PDF editions

Answers 200 over HTTPS (HTTP resets). Daily editions as pages such as
`/la-gaceta-no-184-jueves-08-de-octubre-de-2026/`, linking PDFs; the site
also sells subscriptions, so how much is free was not tested. **This, not
the Assembly, is where religious-freedom actions appear** (Interior Ministry
decisions cancelling the legal status of associations, churches and
foundations). Not probed further: it is an executive gazette, outside a
parliamentary monitor, and PDF-only.

## Taxonomy finding

The English-blindness precedent from Germany applies (titles are entirely
Spanish). But here it hardly matters: a broad Spanish stem scan (abortion,
end of life, gender identity, family and marriage, children and education,
religion, NGO status, speech, trafficking, violence against women,
surrogacy, migration) over all 146 voted items found:

* **0** on abortion, end of life, gender, family/marriage, religion, NGO
  legal status, trafficking, surrogacy, migration.
* **2** on education/children: the June 2025 reform of the universities
  law and general education law; an August 2025 declaration endorsing a
  parliamentary inquiry report on crimes against minors.
* **1** on speech/sovereignty: a January 2025 declaration of support for
  Cuba.
* **7** constitutional items, including four January 2026 partial reforms
  (articles 23 and 25; 118; 125; 132, 159 and 160) and a July 2026
  endorsement of a special constitutional commission. The titles do not say
  what the articles cover; these are the only items a reader would open.

SILEG's 2024 to 2026 initiative titles show the same picture: constitutional
reforms, education law reforms, extradition and prisoner-transfer treaties
with Russia. Nothing on the core areas.

Notably, **no vote cancelled an association's legal status** in 2025 or
2026. Those cancellations once went through the Assembly as decrees; they
are now ministerial, which is part of why the Assembly is the wrong place
to watch.

## Proposed Spanish terms (NOT APPROVED)

Use the shared Spanish list drafted on the Spain branch
(`docs/spain-scope.md`, "Proposed Spanish taxonomy"), minus its "Spain
only" lines. Nicaragua-only additions, all **to be verified by a Spanish
speaker before any approval** (statute numbers drafted from memory, not
from the probe):

* Abortion: "aborto terapéutico"; "Ley 603" (the 2006 repeal of therapeutic
  abortion); "artículo 143" [with: Código Penal, aborto].
* Family and children: "Código de la Familia"; "Ley 870"; "Código de la
  Niñez y la Adolescencia"; "Ley 287"; "Ministerio de la Familia,
  Adolescencia y Niñez"; MIFAN.
* Violence against women (tier 2, scope question as in Spain): "Ley 779";
  "Ley Integral contra la Violencia hacia las Mujeres"; femicidio*.
* Religion and NGO status: "personalidad jurídica" [with: cancela*,
  asociación, fundación, iglesia, organismo]; "organismos sin fines de
  lucro"; "Ley 1115"; "agentes extranjeros"; "Ley 1040"; "Ley 977" [with:
  organismos, iglesia, asociación]; iglesia* [with: cancela*, confisca*,
  personalidad]; "libertad religiosa"; "libertad de culto".
* Speech and civil liberties: "Ley 1042"; ciberdelito*; "Ley 1055";
  "traición a la patria"; "pérdida de la nacionalidad"; desnacionaliz*;
  apátrida*.

## Phase plan

* **Phase 0 (this document): done.** No collector built, by instruction
  and on the evidence.
* **Phase 1: not recommended.** If built, it would be a monthly job, not
  weekly: crawl the current month on `verifica`, join each vote to SILEG by
  Código Iniciativa, run the approved terms over titles, and DM Chris only
  on a hit or on any vote with a "No" or an abstention (which would itself
  be news). Watchlist keyed by Código Iniciativa (for example `202610194`),
  never by title. Estimated cost: about 10 to 20 requests a month.
* Regional bodies (later, not probed): the two Caribbean Coast autonomous
  regional councils (RACCN, RACCS) and the municipal councils. Not
  recommended either.
* Other channels that matter more than the Assembly: *La Gaceta*
  (ministerial cancellations of legal status) and the Supreme Court
  (Corte Suprema de Justicia). No referendums.

### If Chris wants a tripwire

The only cheap, keyless thing worth having: once a month, read the
current month's vote list and the SILEG default view, and DM Chris if (a)
any title matches the approved terms, (b) a constitutional reform is
introduced or voted, or (c) any vote is not unanimous. Two sources, both
already proven above, no new services, and it would stay silent most
months.

## Files touched

Only Nicaragua's own: `docs/nicaragua-scope.md`, `tools/nic_probe.py`.
**No shared file was edited** (`src/db.py`, `tools/coverage.py`,
`alert.yml`, taxonomy files all untouched).

## Waiting on Chris

1. **Agree the recommendation: no Nicaragua edition.** Or ask for the
   monthly tripwire above, which would take a short build.
2. If a tripwire is wanted: approve the Nicaragua-only terms after a
   Spanish speaker checks the statute numbers, and decide whether the Spain
   branch's shared Spanish list is the base.
3. Decide whether *La Gaceta* (an executive gazette, PDF) is in scope for
   religious-freedom tracking anywhere in the monitor; it is where the
   Nicaraguan action is, but it is not parliamentary.
4. Party affiliation is behind a Cloudflare challenge on www.asamblea.gob.ni.
   Only matters if any per-member work is ever wanted; it is not
   recommended.

## Decisions of 10 October 2026 (applied at the countries merge)

Recorded in `docs/country-decisions-2026-10-10.md`. Shared: accents fold and non-ASCII letters are word characters in the filter (X3); member positions are stored for every vote (X15); the AI judge stays off (X16).

Applied on the `countries` branch:

- Terms merged into the shared `config/taxonomy-es.yaml` (`docs/keyword-taxonomy-es.md`), loaded for this country's code (code `nic`).

Later phases and items for Chris (not built at the merge):

- No parliamentary section (NI1).
- Phase: La Gaceta in scope for religious-freedom tracking, church and NGO closures (NI2).
