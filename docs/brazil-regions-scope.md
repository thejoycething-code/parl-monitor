# Brazil: the state assemblies (scope and build, 13 October 2026)

The 26 Assembleias Legislativas and the Câmara Legislativa do Distrito
Federal: what each publishes, what can be read from here, and what was
built. Every number below was measured from the laptop on 13 October 2026
with the honest User-Agent, robots.txt read first (`src/robots_guard.py`).
Code: `tools/br_states.py`, `src/brs_store.py`, `src/brs_edition.py`,
`config/watchlist-br-states.yaml`, `tests/test_br_states.py`. A step of
`jobs/br-weekly.sh`; no new Mini job.

## Why the states matter for CitizenGO

Much of Brazil's fight on our ground is state law: school policy (Escola
sem Partido, bans on "linguagem neutra", gender in curricula, the Bible as a
school text), sex-education rules, toilets and changing rooms "by biological
sex", state "Dia do Nascituro" and pregnancy-support laws, Pride parades
declared state heritage, and, since 2025, the betting ("bets") advertising
bans of area 14. The National Congress has no aggregator for any of this,
and there is no Open States for Brazil.

Measured on ALESP's open data, the one assembly whose whole record can be
read: of 5,236 bills (PL, PLC, PEC, PDL) presented from February 2023 to
28 July 2026, **224 are on our ground** with taxonomy-pt (country 'br'), and
115 committee votes on them carry each member's vote. Area 5 (sex-based
rights) leads, then 8 (marriage and family), 1 (abortion), 15 (drug
decriminalisation), 14 (betting), 9 (religious freedom) and 6 (education).

## Ranking and what was found

Order: population and salience, then source quality. "Reachable" means it
answered the laptop (in the UK); several Brazilian state hosts drop
connections from abroad.

| UF | Assembly | Source for bills | Format | robots.txt | Reachable | Built |
|---|---|---|---|---|---|---|
| SP | ALESP | Open-data files (repositorioDados), daily | zipped XML | allows | yes | **yes**: bills, authors with party, current stage, committee votes with each member's vote |
| MG | ALMG | Website bill search (/atividade-parlamentar/projetos-de-lei/) | HTML, 10 a page | allows (only /atividade_parlamentar/ with an underscore is disallowed) | yes, but slow and intermittent (see below) | **yes**: bills, authors with party, situação; bill pages for bills on our ground |
| MG | ALMG | Open-data API dadosabertos.almg.gov.br/ws | JSON/XML | **Disallow: /** (only the documentation allowed) | | no: robots.txt |
| RJ | ALERJ | Lotus Notes view scpro2327.nsf/Internet/LeiInt | HTML, 15 a page | none (404) | yes, slow, drops connections | **yes**: bills, author, committees, date |
| BA | ALBA | www.al.ba.gov.br / www.alba.ba.gov.br | | TLS handshake times out / self-signed certificate | no | no |
| PR | ALEP | consultas.assembleia.pr.leg.br (JHipster app) | JSON behind the app | allows | yes | **no: every search needs a reCAPTCHA token** (never bypassed) |
| PR | ALEP | transparencia: Ordem do Dia, Controle de votações | PDFs; vote search reCAPTCHA-gated; the "dados abertos" per session answers 404 | allows | yes | no (agenda PDFs only; phase 2 candidate) |
| RS | ALRS | www.al.rs.gov.br, ww4.al.rs.gov.br | | robots.txt times out (read as Disallow: /) | no | no |
| PE | ALEPE | dadosabertos.alepe.pe.gov.br/api/v1 | JSON/CSV | allows | yes | no: the API has members, staff and contracts, no bills |
| CE | ALECE | www.al.ce.gov.br (avulsos, ordem do dia) | HTML + PDFs | allows | yes | no machine-readable list found |
| PA | ALEPA | /Home/Page/Proposicoes | DevExpress MVC callbacks | allows | yes | no (callback form; phase 2 candidate). Has a "Votações Nominais" page |
| SC | ALESC | www.alesc.sc.gov.br | | robots.txt times out | no | no |
| GO | ALEGO | portal.al.go.leg.br | | allows | yes | no list of bills found |
| MA | ALEMA | www.al.ma.leg.br, sapl.al.ma.leg.br | SAPL | robots.txt times out | no | tried every run (SAPL) |
| AM | ALEAM | **sapl.al.am.leg.br** | SAPL REST API | allows, Crawl-delay 60 | yes | **yes** |
| ES | ALES | www.al.es.gov.br | | robots.txt times out | no | no |
| PB | ALPB | **sapl.al.pb.leg.br** | SAPL REST API | allows, Crawl-delay 60 | yes | **yes** |
| RN | ALRN | www.al.rn.leg.br | | TLS times out | no | no |
| MT | ALMT | www.al.mt.gov.br; sapl.al.mt.leg.br | SAPL | main site times out; SAPL allows | SAPL yes | no: its SAPL lists no matéria for 2026 |
| AL | ALE-AL | **sapl.al.al.leg.br** | SAPL REST API | allows, Crawl-delay 60 | yes | **yes** |
| PI | ALEPI | **sapl.al.pi.leg.br** | SAPL REST API | allows, Crawl-delay 60 | yes | **yes** |
| DF | CLDF | www.cl.df.gov.br, dadosabertos.cl.df.gov.br | | times out | no | no |
| MS | ALEMS | sgpl.consulta.al.ms.gov.br (JavaScript app) | | www allows | partly | no |
| SE | ALESE | al.se.leg.br | | allows | yes | no list of bills found (atas and audio only) |
| RO | ALERO | **sapl.al.ro.leg.br** | SAPL REST API | allows, Crawl-delay 60 | yes | **yes** |
| TO | ALETO | **sapl.al.to.leg.br** | SAPL REST API | allows, Crawl-delay 60 | yes | **yes** |
| AC | ALEAC | **sapl.al.ac.leg.br** | SAPL REST API | allows, Crawl-delay 60 | yes (TLS slow) | **yes** |
| AP | ALAP | www.al.ap.gov.br | | times out; no SAPL host | no | no |
| RR | ALE-RR | sapl.al.rr.leg.br | SAPL | allows | the API answers 403 Forbidden | tried every run (SAPL) |

**Covered: 10 of 27** (SP, MG, RJ, AM, PB, AL, PI, RO, TO, AC), plus RR and
MA tried each run. Together the ten hold about 47% of Brazil's population
(SP 21.5%, MG 10%, RJ 7.8%, the SAPL seven about 8%).

## The sources in detail

### ALESP (São Paulo): open data

`https://www.al.sp.gov.br/repositorioDados/processo_legislativo/`, every
file updated daily at about 03:30 (Last-Modified 12 October 2026 06:27 GMT):

| File | Size | Used for |
|---|---|---|
| proposituras.zip | 17.4 MB (132 MB XML) | every propositura since 1995: IdDocumento, natureza, number, year, ementa, dates |
| documento_autor.zip | 6.5 MB | authors per document (IdAutor = the deputy's IdSPL) |
| documento_andamento_atual.zip | 2.0 MB | the current stage per document (NmEtapa, Descricao, Data) |
| deputados/deputados.xml | 0.3 MB | name and party of the 94 sitting deputies (biographies in the file are never read into the store) |
| comissoes_permanentes_reunioes.xml | 2.9 MB | committee meetings, dated |
| comissoes_permanentes_votacoes.xml | 67.5 MB | **each member's vote** in committee, per document and meeting |
| comissoes_permanentes_deliberacoes.xml | 12.5 MB | the committee's decision per document and meeting |
| comissoes.xml | 34 KB | committee names |
| documento_andamento.zip | 106 MB | the full tramitação history: not read |

Naturezas kept (naturezasSpl.xml): 1 PL, 2 PLC, 4 PDL, 5 PEC. In 2026 to
28 July: 13,185 indicações, 2,205 requerimentos, 760 PL, 325 requerimentos
de informação, 232 moções, 21 PDL, 15 PLC, 10 resolutions, 1 PEC. The file's
newest date is 28 July 2026: the mid-year recess, then the election
campaign (the state elections were on 4 October). Some newer documents say
only "tramita exclusivamente no Alesp Sem Papel" (the digital system) for
their stage; that status is stored as unknown, not as a stage.

Cost: about 26 MB a week; the 83 MB of committee files only when the
meetings file shows a meeting newer than the last read (none during a
recess). The large files are not archived to data/raw (they are the
Assembly's own, re-downloadable; the read is recorded in brs_reads).
ALESP does not publish plenary roll calls as open data.

### ALMG (Minas Gerais): the website's bill search

`/atividade-parlamentar/projetos-de-lei/?pesquisou=true&tipo=<5 PL|6 PLC|9 PEC>&ano=<year>&ordem=<0 date|3 last action>&pagina=<n>`:
ten bills a page, each with number, ementa (or, where a bill has none, its
last action: detected and dropped), authors with party, situação. Searches
**must name the year**: with a year one answered in 2.9 s; without, none
answered within the timeout. A bill's own page (`/projetos-de-lei/PL/6055/2026`)
gives the publication date, situação, local and the latest tramitação
step: read only for bills on our ground (at most 12 a run), and re-read
for older bills on our ground to catch their stage moves. Newest PL on
13 October: PL 6067/2026 (published mid-August; the Assembly then went
into its election recess).

The ALMG host answered normally in the morning and then timed out from the
laptop for over an hour (robots.txt included; the guard used its saved
copy, under 24 hours old). The step records a gap and the next run
retries. The open-data API (dadosabertos.almg.gov.br/ws/...) would be far
better, but its robots.txt disallows everything except the documentation,
and is respected (Waiting on Chris, below).

### ALERJ (Rio de Janeiro): Lotus Notes

`https://alerjln1.alerj.rj.gov.br/scpro2327.nsf/Internet/LeiInt?OpenForm&Start=<n>`
(read over HTTPS, which it also serves, 21 s for a page):
fifteen bills a page, newest first (PL 8400/2026 on 9 October 2026), with
the bill code (YYYY + 03 + number: 20260308397 is PL 8397/2026), ementa in
capitals, committees in braces, the date (US format: 10/08/2026 is
8 October) and the author. No robots.txt (404: no rules). The server is
slow (one page 26 s, a bill page 31 s) and often drops the connection
(three of six requests on 13 October); `Count=` larger than 15 is refused.
A failed page is a gap; the next run resumes. No stage or votes are read
(bill pages hold the text, not the tramitação).

### The SAPL houses (Interlegis): one platform for seven states

SAPL 3.1's documented REST API, the same on every house:

- `/api/materia/tipomaterialegislativa/`: the house's types (read once,
  refreshed every four weeks). Bill types are picked by description
  (projeto de lei of any kind, proposta de emenda, projeto de decreto
  legislativo, projeto de código); a sigla used twice gets its id
  (Tocantins has two "PEC" types: `PEC` and `PEC-36`).
- `/api/materia/materialegislativa/?tipo__in=..&data_ultima_atualizacao__gte=<date>&o=-data_ultima_atualizacao&page_size=100`:
  bills new or updated since the last read (two days' overlap); verified
  that `tipo__in`, `__gte` and `o=` filter (Amazonas: 118 bills of four
  types updated since 13 September). `tipo=1&tipo=5` keeps only the last.
- `/api/sessao/registrovotacao/?data_hora__gte=<date>`: plenary vote
  tallies (yes, no, abstentions, the result in the house's words) with the
  matéria; Rondônia had 12 since 13 September (requerimentos and vetoes),
  Amazonas 6,582 in all. Per-member votes (`votoparlamentar`) are empty
  where checked (Tocantins).
- `/api/materia/tramitacao/?materia=<id>` (the latest step: status and
  date) and `/api/base/autor/<id>` (the author's name): read only for bills
  on our ground, at most three and two a house a run.

Every SAPL robots.txt says `Crawl-delay: 60`, honoured: a request a minute
per house, the houses in parallel threads. Five of them (AC, AL, MT, PI,
RO) are on one Interlegis address. The API also returns the IP address of
the clerk who last edited a record; it is never stored.

Volumes, bills of 2026: Paraíba 7,857 matérias (mostly autógrafos and
requerimentos; more than 300 bills updated in a month, so a first read is
capped at 300 and drains over later runs), Rondônia 5,520 (mostly
indicações), Amazonas 4,781, Acre 1,103, Tocantins 1,081, Alagoas 739,
Piauí 605.

## What was built

`tools/br_states.py` (sources `sp`, `mg`, `rj`, `sapl:<uf>`), fetching in
parallel threads (one client per source, robots.txt per host, each within
the run's budget), then writing in the main thread:

- `brs_bills`: one row per bill, keyed `<uf>/<type> <number>/<year>`
  (`sp/PL 734/2026`, `mg/PEC 41/2026`, `rj/PL 8397/2026`, `ro/PLO 1541/2026`),
  with ementa, authors (with party where printed), presented, status and
  status date, committees, URL, and taxonomy-pt areas. Every bill is stored,
  on our ground or not, so `--reclassify` re-derives offline.
- `brs_votes`, `brs_positions`: ALESP committee votes on bills on our ground
  with each member's vote and party; SAPL plenary tallies.
- `brs_members`: names and parties as printed (ALESP's deputados.xml,
  ALMG's author lines, SAPL autores).
- `brs_reads`: one row per source per run (status, detail, newest date,
  the source's bookkeeping).

**Edition:** a "State assemblies" section in the Brazilian weekly
(`src/brs_edition.py` via `Country.post_render`, before the Watchlist):
bills on our ground new in the week, stage moves (routine handling such as
co-authorship requests left out), and votes on them with tallies, party
split and the members who voted against. The section ends with a coverage
line naming which assemblies were read, with gaps, and not read and why.
The DM gets one line when the section has items. The edition's noise rules
(`config/edition-noise-br.yaml`) apply.

**Sample** (live run 13 October 2026, window 13 to 26 July 2026): 10 items
from ALESP, among them PL 734/2026 (toilets for transgender and non-binary
people, area 5), PL 670/2026 (the Bible as a school text, area 9, stage
move into the CCJR), PL 735, 736, 738 and 739/2026 (betting advertising,
area 14). Window 3 to 10 October 2026: 3 items, among them Alagoas'
PLO 1275/2025 (a state abortion-prevention programme, "matéria aprovada
aguardando sanção governamental", read through SAPL) and Amazonas' PL
317/2026 (an infertility week, a tier-2 false positive for area 13).
Second live run, the SAPL houses: Amazonas 118 bills updated in a month
(4 on our ground, 17 plenary votes), Alagoas 71 (2), Piauí 45, Acre 5,
Rondônia 52, Tocantins 17, Paraíba 300 (capped; 8); Roraima answered 403,
Maranhão did not answer.

**Job:** a step of `jobs/br-weekly.sh` after the Congress collector, with
600 s (`tools/collector_budget.sh 600`; the collector's own budget keeps
600 s for it). Its gaps never cost the run.

**Classification false positives seen** (taxonomy matters, not code):
`religios*` on utilidade-pública declarations for religious associations,
`imigrante*` on the Rodovia dos Imigrantes (area 11, hidden anyway),
`casamento civil` on a "pet-friendly wedding" programme, `transplante*`
(organ donation) on transplant policy. The noise file or a taxonomy tweak
can take them out.

## Not built, and why

- **Paraná (ALEP)**: the proposições search and the vote search both demand
  a reCAPTCHA token; never bypassed. The Ordem do Dia (weekly PDFs listing
  the bills on the floor) is open and could be read for "on the floor this
  week" (phase 2).
- **Unreachable from the UK** (time out, drop the TLS handshake or present
  a failing certificate): Rio Grande do Sul, Santa Catarina, Bahia,
  Distrito Federal, Espírito Santo, Rio Grande do Norte, Amapá, Maranhão,
  Mato Grosso (main site). They may answer from a Brazilian address; the
  Mini is in the UK too.
- **No usable list**: Goiás, Ceará, Sergipe (sites without a bill list),
  Pará (DevExpress callback form), Mato Grosso do Sul (JavaScript app),
  Pernambuco (open-data API without bills).
- **Votes**: no assembly read publishes plenary roll calls by member as
  data. ALESP's per-member committee votes are the exception; Pará and
  Ceará have "Votações nominais" pages (phase 2).
- **Vetoes**: a governor's veto of a bill on our ground is a SAPL type of
  its own (Veto Total/Parcial) and is not read yet; phase 2.

## Waiting on Chris

1. **ALMG's open-data API**: its robots.txt disallows everything; the
   website search is used instead. Ask ALMG to allow it, or decide that a
   documented open-data API is exempt (the repository's rule today: no).
2. **Seed `config/watchlist-br-states.yaml`** with the state bills that
   matter (empty at launch).
3. **Taxonomy-pt false positives** above: cut `religios*` from utilidade
   pública titles, `transplante*`, `casamento civil` with "pet"?
4. Whether a Brazilian vantage point (a small VPS or a partner's machine)
   is worth it for the nine assemblies that do not answer from the UK.

## Files touched outside the layer's own

`src/db.py` (5 table names, one ensure_schema call), `src/editions/br.py`
(post_render, notice, a coverage line), `jobs/br-weekly.sh` (one step, one
reclassify line, the collector's reserve), `tools/coverage.py` (two
freshness rows, two awaiting-first-run rows), `docs/brazil-scope.md`,
`docs/country-parity-handover.md`.
