# Costa Rica: scoping the Asamblea Legislativa monitor

Branch `costa-rica`, code `cr` / `CR`, language Spanish. Probed live on
9 October 2026 from the laptop (BT, London), from a GitHub Actions runner
(two rounds, `.github/workflows/cr-probe.yml`) and from WebFetch's US
network. Every number below was measured that day unless marked otherwise.
Raw responses are under `data/raw/cr-probe/` (git-ignored, laptop only;
`gh-r1/` and `gh-r2/` hold the two runner artifacts with their logs).

## Decisions already taken (Christopher)

- Own edition, delivered to Christopher alone (Slack DM), like the US.
- Shared taxonomy concept; no existing taxonomy file is edited. The Spanish
  term list is PROPOSED below for approval.
- National parliament first. Costa Rica is unitary and unicameral, so there
  is no second chamber or state level; the 84 municipal councils are out.
- Mac Mini first, GitHub Actions as backup. No new paid services. Never post
  publicly.

## The finding that shapes everything: the Asamblea is unreachable from outside Costa Rica

**Every official host that carries data refuses our traffic at the network
level, from London and from GitHub's (US) runners alike.** No CAPTCHA, no
bot page, no HTTP error: the packets are dropped or the TLS handshake is
reset. Nothing was bypassed or retried around it.

| Host | IP (RACSA) | What it serves | Laptop (London) | GitHub runner | WebFetch (US) |
|---|---|---|---|---|---|
| `www.asamblea.go.cr` | 196.40.23.181 | SharePoint site: SIL pages, `glcp/votaciones_plenario` library, `_api/` | TCP timeout on 80 and 443 | timeout | ECONNREFUSED 443 |
| `datosabiertos.asamblea.go.cr` | 196.40.23.181 | the open-data portal (if it exists; see below) | TCP timeout | timeout | not tried |
| `consultassil3.asamblea.go.cr` | 196.40.23.181 | **the SIL itself**: `frmConsultaProyectos.aspx`, `frmConsultaActasPlenario.aspx`, `frmOrdenDiaPlenario.aspx` | TCP timeout on 80 and 443 | timeout | not tried |
| `consultassil.asamblea.go.cr` | 196.40.23.187 | older SIL host | TCP 443 connects, TLS reset by peer; 80 unreachable | reset (Errno 104) | not tried |
| `sil.asamblea.go.cr` | 196.40.23.183 | IIS 8.5 default page only (port 80); every path tried is 404 | answers on 80 only | answers on 80 only | not tried |
| `biblioteca.asamblea.go.cr` | 196.40.23.174 | IIS 7 default page only (port 80) | answers on 80 only | answers on 80 only | not tried |

DNS for `asamblea.go.cr` is on Cloudflare (`dale`/`adele.ns.cloudflare.com`)
but the A records point straight at RACSA (Radiográfica Costarricense)
addresses, so there is no CDN in front to reach instead. The block is almost
certainly geographic (Costa Rican and perhaps regional addresses only): the
Asamblea is clearly up, because acontecer.co.cr ingested plenary votes from
the SIL's actas at 20:00 on 8 October 2026 (below).

The Internet Archive last captured the home page on 14 July 2026 (302) and
`ConsultaProyectos.aspx` on 21 July 2026 (200), so either the block began
after mid-July or it spares archive.org's addresses. It is not certain that
it is permanent, but three vantage points on two continents agree today.

`imprentanacional.go.cr` (La Gaceta, where bills are published) returns a
Cloudflare **522** (origin unreachable) to the laptop: the same pattern one
step removed. By contrast the judiciary (`nexuspj.poder-judicial.go.cr`,
200), the electoral tribunal (`www.tse.go.cr`, 200), SINALEVI/SCIJ
(`pgrweb.go.cr/scij/` -> `sinalevi.go.cr`, 302) and the national CKAN portal
(`datos.go.cr`, 200) all answer.

**The Mac Mini sits on Christopher's own network, the same London address
as the laptop, so it will be refused too.** This is a blocker for phase 1 as
specified (Mini first, GitHub backup). Per the common brief, I stopped after
the scope doc and the probe; no collector, store, watchlist file or weekly
job was built.

## What Costa Rica publishes (from archived copies and third parties)

Measured from Internet Archive captures (`id_` raw copies), because the live
site is closed to us.

### The SIL (Sistema de Información Legislativa)

- The SharePoint pages under `www.asamblea.go.cr/Centro_de_informacion/Consultas_SIL/`
  are shells. `ConsultaProyectos.aspx` (capture of 21 July 2026, 88 KB)
  embeds an **iframe to `https://consultassil3.asamblea.go.cr/frmConsultaProyectos.aspx`**,
  which is where the data lives.
- `consultassil3` is **ASP.NET WebForms**: every list is a GridView paged by
  `__doPostBack` with `__VIEWSTATE` (about 6 KB) and `__EVENTVALIDATION`.
  Scrapable with stdlib (GET, then POST the hidden fields back), but each
  page is a stateful round trip; there is no JSON.
  - `frmConsultaProyectos.aspx`: search by expediente number
    (`tbxBuscaLey`) or title words (`tbxBuscaDescripcion`); the default
    grid lists expedientes newest first, number and title, 11+ pages
    (capture of 12 March 2024 showed 24209 down to 24200 on page 1).
  - `frmConsultaActasPlenario.aspx`: plenary minutes by date range
    (`tbxFechaInicio`, `tbxFechaFin`), rows like
    `2023-2024-PLENARIO-SESION-134, 05-mar.-2024, 14:45, ORDINARIA, id 38180`.
  - Also captured: `frmOrdenDiaPlenario.aspx` (plenary order paper),
    `frmConsultaProyectosODPlenario.aspx`, `frmConsultaProyectosODComisiones.aspx`,
    `frmConsultaActasComisiones.aspx`, `frmConsultaODComisiones.aspx`,
    `frmConsultaLey.aspx`, `frmConsultaConvocatoria.aspx`. No `robots.txt`
    (404 in 2024).
- **Expedientes are numbered** (25832 was the newest on 9 October 2026) and
  the number is stable for a bill's whole life. That is the key, never the
  title. Constitutional reforms are expedientes like any other.
- The SharePoint REST `_api/` answered anonymously when the Archive crawled
  it in February 2026 (`_api/` 200, `_api/navigation/MenuState` 200), and
  the SIL also exposes Business Connectivity Services entities
  (`LOBSystemInstanceName=SIL_Instance`, `EntityNamespace=Diputados`,
  entities `Integrante`, `Organos`, `Sesion`). Possibly a cleaner route if
  access is ever granted; untested.

### Votes with per-member positions

- **Where they come from**: acontecer.co.cr's vote records carry
  `"fuente":"acta_sil"` and a `clave_acta` such as
  `primer-debate-24719-ORD75-2026-8`, i.e. they are parsed from the SIL's
  plenary actas, which record the electronic vote. I could not open an acta
  to confirm the per-member layout (unverified).
- `www.asamblea.go.cr/glcp/votaciones_plenario/` is a SharePoint document
  library of PDFs, but its 67 archived folders are **elections and
  appointments** (magistrates, Defensoría, Procurador, the Directorio,
  committee installation, ballot sheets), not bill votes.
- The official mobile app (`go.cr.AsambleaLegislativa`) advertises a votes
  section showing each deputy's vote. Its backend was not examined
  (downloading and unpacking the APK was out of bounds).
- Plenary: 57 deputies, legislature 2026-2030 (installed 1 May 2026).
  Ordinary sessions Monday to Thursday afternoons (14:45 in the actas list).
  Bills pass in **primer debate** and **segundo debate**; motions
  (`moción de fondo`, `dispensa de lectura`, `posposición`) are voted too.

### The open-data portal

`datosabiertos.asamblea.go.cr` resolves to the main IP and is refused like
it. **The Internet Archive has never captured it** (`archived_snapshots`
empty), and the national CKAN portal `datos.go.cr` has no Asamblea
organisation and **0 datasets** for `q=asamblea` (organisations: gobcr,
micitt, MEIC, Hacienda, MTSS, a test institution). Its existence and
content are unverified.

### Third parties that can see the Asamblea

| Source | Status 9 Oct 2026 | What it has | Use |
|---|---|---|---|
| **acontecer.co.cr/asamblea** (news site, Next.js) | 200 to our UA from London | `/asamblea/expedientes`: the 200 newest expedientes with number, title, status and proponent in server-rendered HTML (5,135 "en trámite" claimed); `/asamblea/votaciones`: 117 plenary vote records since May 2026 (71 approved, 45 rejected), 10 per page with expediente, stage, yes/no/abstain totals, date; "mapas de votos individuales" | robots.txt allows `/asamblea/` pages, **disallows `/api/`** (where the per-deputy data appears to load) and `/asamblea/votaciones/*/imagen`. Footer: "Todos los derechos reservados". Needs permission before any collector. |
| **delfino.cr/asamblea** (news site) | 503 "En mantenimiento" behind Cloudflare | per-bill vote pages (`/asamblea/votaciones/proyecto/<id>`) and a legislation list, by search-engine evidence | robots.txt disallows `/api/` only. Recheck when back. Same permission question. |
| La Nación, "¿Qué proyectos apoyó o rechazó cada diputado?" | not probed | first and second debate votes per deputy | Newsroom tool; permission question. |
| CONARE mirror (`proyectos.conare.ac.cr/asamblea/`) | not probed | old expediente PDFs and actas | Historical only. |

## How much touches CitizenGO ground

Measured on the 200 newest expedientes (25633 to 25832, filed roughly
May to October 2026) from acontecer's listing, titles only:

- **The English taxonomy (`config/taxonomy.yaml`, 462 terms) matches 0 of
  200**, as Germany's precedent predicted.
- **The draft Spanish list below matches 10 of 200**. Read by hand, **6 are
  on our ground** (3 per cent), plus 1 that names only article numbers and
  belongs on a watchlist by key:

| Expediente | Title (shortened) | Area |
|---|---|---|
| 25830 | Constitutional reform of art. 21 "para proteger la vida desde la concepción hasta la muerte natural" (Kattia Mora and 10 others) | 1 abortion, 2 end of life |
| 25829 | Amends art. 28 para. 3 and adds art. 95 inciso 9 of the Constitution (same proponents) | 8 religion, by key: art. 28 is the ban on political propaganda invoking religion. Title names only articles. |
| 25776 | Ban on "esfuerzos para cambiar la orientación sexual, identidad o expresión de género (ECOSIG)" | 4 conversion practices |
| 25805 | Minimum age for access to social media | 6 parental rights / online |
| 25753 | Art. 29 of the Ley de Penalización de la Violencia contra las Mujeres (8589) | 5, scope question |
| 25825 | Constitutional reform removing immunity for sexual offences | 12, marginal |
| 25707 | National migration policy governance | 11 (collated, hidden) |

The other matches were noise the list was tightened against (`familia*`
caught "patrimonio familiar" and "vivienda familiar"; `personas menores de
edad` caught youth brawls and risk-prevention bills, kept at tier 2).

Votes could not be measured against the list: acontecer's 117 vote records
name only stage and expediente number ("PRIMER DEBATE EXP 24719"), so
classification needs the expediente title join, which a collector would do.

## Proposed Spanish taxonomy for Costa Rica (v0.1, FOR APPROVAL)

Built on the Spain branch's draft (`docs/spain-scope.md`, v0.1, same
generator format and conventions: trailing `*` for inflection, accents
significant, short words never alone, acronyms case-sensitive). **Only the
Costa Rica additions are listed here**; everything in Spain's shared
(non-"Spain only") terms applies unchanged. The `Costa Rica only` lines are
statute numbers, institutions and local usage, so a merged
`taxonomy-es` can keep them as a country addendum. Not yet read by a Costa
Rican campaigner. The statute numbers, decree and case names are from
background knowledge, not probed (the official law database was not
queried); check them before generating.

1. **Abortion.** Tier 1: "aborto impune"; "aborto terapéutico"; "norma
   técnica" [with: aborto, 121, interrupción]; "artículo 121 del Código
   Penal"; "persona por nacer"; "desde la concepción"; "derecho a la vida"
   [with: concepción, nacer, embarazo]; "vida humana" [with: concepción,
   nacer]. Tier 2: "salud sexual y reproductiva"; anticoncepci*. *Costa
   Rica only*: "aborto impune"; "norma técnica"; "artículo 121 del Código
   Penal". Note: art. 121 of the Penal Code permits abortion only to save
   the mother's life or health; the 2019 "Norma Técnica" regulating it is
   the live fight.
2. **Assisted dying.** Tier 1: "muerte asistida"; "muerte digna"; "hasta la
   muerte natural". Tier 2: "voluntades anticipadas"; "cuidados paliativos".
   *Costa Rica only*: none.
3. **Gender medicine and children.** Tier 1: "niñez trans"; "hormonización"
   [with: menor, persona menor de edad, adolescente]. *Costa Rica only*:
   none.
4. **Conversion practices.** Tier 1: ECOSIG; "esfuerzos para cambiar la
   orientación sexual"; "esfuerzos de cambio de orientación sexual".
   *Costa Rica only*: ECOSIG (the local acronym, used in bill 25776's
   title).
5. **Sex-based rights and gender identity.** Tier 1: "cambio de nombre"
   [with: identidad de género, sexo, registro civil]; "Decreto Ejecutivo
   41173"; "Opinión Consultiva OC-24/17"; "OC-24/17". Tier 2: "violencia
   contra las mujeres"; "Ley de Penalización de la Violencia contra las
   Mujeres"; "Ley 8589"; femicidio*; "acoso sexual callejero"; "Ley 9877".
   *Costa Rica only*: "Decreto Ejecutivo 41173" (gender-identity name
   change); OC-24/17 (the Inter-American Court opinion behind same-sex
   marriage and identity changes); "Ley 8589"; "Ley 9877" (street
   harassment).
6. **Parental rights and education.** Tier 1: "afectividad y sexualidad";
   "Educación para la Afectividad y Sexualidad Integral"; "guías de
   sexualidad"; "derecho de los padres"; "redes sociales" [with: edad,
   menor, persona menor de edad, adolescente]. Tier 2: "personas menores de
   edad" [with: educación, escuela, colegio, digital, redes]; "Código de la
   Niñez y la Adolescencia"; "Patronato Nacional de la Infancia"; PANI;
   "Ministerio de Educación Pública" [with: sexualidad, afectividad,
   religión]; "relaciones impropias"; "Ley 9406". *Costa Rica only*: the
   MEP's "Programa de Educación para la Afectividad y Sexualidad Integral"
   (the "guías de sexualidad" dispute); PANI; "Ley 9406" (relaciones
   impropias, statutory rape of minors).
7. **Free speech.** No Costa Rica additions; Spain's shared list.
8. **Freedom of religion.** Tier 1: "Estado confesional"; "Estado laico";
   "artículo 75" [with: Constitución, religión, Estado]; "artículo 28"
   [with: Constitución, religión, propaganda]; "Ley de Libertad Religiosa";
   "libertad de culto"; "educación religiosa". Tier 2: "Iglesia católica";
   "Conferencia Episcopal"; "organizaciones religiosas"; "templos"
   [with: impuesto, patente, municipal]. *Costa Rica only*: "Estado
   confesional" and "artículo 75" (Costa Rica is constitutionally Catholic;
   bills to make it lay recur); "artículo 28" (the ban on clergy and laity
   invoking religion in politics); "Ley de Libertad Religiosa" (the
   evangelical churches' long-running bill).
9. **Marriage and family.** Tier 1: "matrimonio igualitario"; "matrimonio
   entre personas del mismo sexo"; "unión de hecho entre personas del mismo
   sexo"; "protección de la familia". Tier 2: "Código de Familia"; "unión de
   hecho"; "pensión alimentaria"; natalidad; "licencia de maternidad";
   "licencia de paternidad". *Costa Rica only*: "Código de Familia" (Ley
   5476); "matrimonio igualitario" (in force since 26 May 2020 by Sala
   Constitucional ruling).
10. **Surrogacy and embryology.** Tier 1: "fecundación in vitro";
    "fertilización in vitro"; FIV; "Artavia Murillo". *Costa Rica only*:
    "Artavia Murillo" (the 2012 Inter-American Court ruling that overturned
    Costa Rica's IVF ban).
11. **Migration** (collated, hidden). Tier 1: "Ley General de Migración y
    Extranjería"; "Dirección General de Migración"; refugio; "política
    migratoria". *Costa Rica only*: all four.
12. **Prostitution, trafficking.** Tier 1: "Ley contra la Trata de Personas";
    "Ley 9095". Tier 2: "delitos sexuales"; "explotación sexual comercial".
    *Costa Rica only*: "Ley 9095".
13. **Organ donation.** Tier 1: "Ley 9222". *Costa Rica only*: "Ley 9222"
    (donation and transplant law).

Global exclusions as Spain's, plus `familia*` alone (measured noise above).

## Courts and referendums (major channels)

- **Sala Constitucional (Sala IV)** is decisive: deputies file *consultas
  facultativas de constitucionalidad* on bills between debates, and it gave
  Costa Rica same-sex marriage (2018 ruling, effective 2020) and blocked the
  2010 civil-unions referendum. Its decisions are on Nexus
  (`nexuspj.poder-judicial.go.cr`, **answers from London**, not explored
  further). A phase-2 candidate that is reachable today.
- **Inter-American Court**: Artavia Murillo (IVF, 2012) and OC-24/17 (2018)
  were requested by or about Costa Rica; San José hosts the Court.
- **Referendums** run through the TSE (`www.tse.go.cr`, answers); rare
  (CAFTA 2007), but citizen-initiated ones on our ground have been tried.

## Proposed phasing

0. **Access first** (Waiting on Chris, item 1). Nothing else can start.
1. **Phase 1, once reachable from wherever it runs**: `tools/cr_rollcalls.py`
   on the SIL (WebForms: expedientes by number and title, plenary actas by
   date range, votes parsed from the actas), `src/cr_store.py` (`cr_members`,
   `cr_expedientes`, `cr_divisions`, `cr_votes`), `config/watchlist-cr.yaml`
   keyed by expediente number (start: 25830, 25829, 25776, 25805),
   fixtures and tests, and the Mini-first weekly job in the Spain pattern
   (`jobs/cr-weekly.sh`, launchd plist, `.github/workflows/cr-weekly.yml`
   gated by `CR_WEEKLY`). Weekly on Saturday after the Monday-Thursday
   plenary week. Note the GitHub backup will only work if the access route
   also works from Actions.
2. **Phase 2**: plenary order paper (`frmOrdenDiaPlenario.aspx`) for a
   week-ahead; committee actas; Sala IV consultations via Nexus.

## Shared files touched

**None.** The only files added are this document and the probe:
`tools/cr_probe.py` (adapted from the Mexico branch's `mx_probe.py`),
`.github/workflows/cr-probe.yml` (runs only on pushes to `costa-rica` that
change it or its args; read-only, no secrets, no commit; delete once a
collector exists) and `ops/cr-probe-args.txt`. No change to `src/db.py`,
`tools/coverage.py`, `alert.yml`, `mini_run.sh` or any taxonomy.

## Waiting on Chris

1. **Choose an access route** (the blocker):
   - (a) **Ask the Asamblea** to let our honest UA through, or whether
     `datosabiertos.asamblea.go.cr` is meant to be public abroad. Contact on
     the site: `participacion-consultas@asamblea.go.cr`, tel. 2243 2895. I
     have not written; sending is yours.
   - (b) **A Costa Rican vantage point at no cost**: a CitizenGO colleague's
     or partner's always-on machine in Costa Rica running the weekly job
     (the Mini pattern, a second runner). No paid VPS, per the rules.
   - (c) **A third-party source, with the owner's permission**:
     acontecer.co.cr already holds expedientes, all 117 plenary votes of
     the 2026-2030 legislature and per-deputy maps (its `/api/` is closed
     to crawlers by robots.txt and the site reserves all rights), or
     delfino.cr when it is back from maintenance. Reading their HTML pages
     is allowed by robots.txt but reuse is a permission question, so I
     built nothing on them.
   - (d) **Park Costa Rica** until one of those lands. The parliament is
     fully independent and the ground is live (a life-from-conception
     constitutional reform and an ECOSIG ban both filed this autumn), so
     the edition is worth having once there is a lawful route.
2. **Approve or amend the Costa Rica additions** to the Spanish list,
   ideally after a read by the Costa Rica team; they merge into the shared
   `taxonomy-es` with Spain, Argentina and the rest.
3. **Scope questions**: the violence-against-women law (Ley 8589, tier 2
   here, as Spain's gender-violence question); sexual-offence immunity
   (25825) in or out; is the art. 28 reform (25829) religious-freedom ground
   (assumed yes, by key)?
4. **Recheck date**: if the block turns out to be temporary, rerun the probe
   (edit `ops/cr-probe-args.txt` and push to `costa-rica`) before building.
