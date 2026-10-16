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
| MG | ALMG | Open-data API dadosabertos.almg.gov.br/api/v2/ | JSON/XML | **allows /api/v2/ since 14 October 2026** (changed at our request, protocolo 126599) but still **disallows paging and sorting** (`*?*p=`, `*?*tp=`, `*?*ord=`, `*?*ordenacao=`) | yes | **yes, primary since 15 October 2026**: bills, authors with party, situação, committee, last action; plenary results per bill; deputies with party. Never pages (see "ALMG open-data API") |
| RJ | ALERJ | Lotus Notes view scpro2327.nsf/Internet/LeiInt | HTML, 15 a page | none (404) | yes, slow, drops connections | **yes**: bills, author, committees, date |
| BA | ALBA | www.al.ba.gov.br / www.alba.ba.gov.br | | TLS handshake times out / self-signed certificate | no | no |
| PR | ALEP | consultas.assembleia.pr.leg.br (JHipster app) | JSON behind the app | allows | yes | **no: every search needs a reCAPTCHA token** (never bypassed); second pass: **adopted laws via the Casa Civil (`pr`)**; third pass: **bills, stages and results via ALEP's open-data API over plain HTTP (`alep`)**, the one exception |
| PR | ALEP | transparencia: Ordem do Dia, Controle de votações | PDFs; vote search reCAPTCHA-gated; the "dados abertos" per session answers 404 | allows | yes | no (agenda PDFs only; phase 2 candidate) |
| RS | ALRS | www.al.rs.gov.br, ww4.al.rs.gov.br | | robots.txt times out (read as Disallow: /) | no | no |
| PE | ALEPE | dadosabertos.alepe.pe.gov.br/api/v1 | JSON/CSV | allows | yes | first pass no; second pass: **yes (`pe`)**, the same API's `proposicoes/projetos` |
| CE | ALECE | www.al.ce.gov.br (avulsos, ordem do dia) | HTML + PDFs | allows | yes | first pass no; second pass: **yes (`ce`)**, the www2 proposições lists |
| PA | ALEPA | /Home/Page/Proposicoes | DevExpress MVC callbacks | allows | yes | first pass no; second pass: **yes (`pa`)**, a plain form POST. Has a "Votações Nominais" page |
| SC | ALESC | www.alesc.sc.gov.br | | robots.txt times out | no | no |
| GO | ALEGO | portal.al.go.leg.br | | allows | yes | no list of bills found; second pass: **adopted laws via the Casa Civil (`go`)** |
| MA | ALEMA | www.al.ma.leg.br, sapl.al.ma.leg.br | SAPL | robots.txt times out | no | tried every run (SAPL) |
| AM | ALEAM | **sapl.al.am.leg.br** | SAPL REST API | allows, Crawl-delay 60 | yes | **yes** |
| ES | ALES | www.al.es.gov.br | | robots.txt times out | no | no |
| PB | ALPB | **sapl.al.pb.leg.br** | SAPL REST API | allows, Crawl-delay 60 | yes | **yes** |
| RN | ALRN | www.al.rn.leg.br | | TLS times out | no (yes later that day) | second pass: **yes (`rn`)**, its Transparência Legislativa data |
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

**Covered: 10 of 27** after the first pass (SP, MG, RJ, AM, PB, AL, PI, RO,
TO, AC), plus RR and MA tried each run. Together the ten hold about 47% of
Brazil's population (SP 21.5%, MG 10%, RJ 7.8%, the SAPL seven about 8%).

**Covered: 16 of 27 after the second pass** (13 October 2026, "Alternative
routes" below): Pernambuco, Ceará, Pará and Rio Grande do Norte through
their own data on other hosts (bills), Paraná and Goiás through the state's
legislation portal (adopted laws only). About 73% of the population.

**Third pass** (13 October 2026, "Third pass" below): Paraná's **bills**,
stages and plenary/committee results are read too, from ALEP's open-data
API over plain HTTP (the repository's single, dated exception). Paraná
was already counted (adopted laws), so the count does not change here.

## Alternative routes (second pass, 13 October 2026)

The standing rule (Chris, 13 October): when a source blocks us, look for a
legitimate other route before recording a gap; never bypass the block.
Every route below was probed from the laptop with the honest User-Agent and
robots.txt read first; the hosts that did not answer the laptop were asked
from GitHub's runners with the read-only probe workflow
(`.github/workflows/probe-hosts.yml`: `contents: read`, no secrets, GET
only, an artifact; runs 38332427738 and 38334238732).

| UF | Routes tried | Outcome |
|---|---|---|
| PR | ALEP's bill search (consultas.assembleia.pr.leg.br): reCAPTCHA. ALEP's **documented open-data API** (transparencia → Dados Abertos: `POST /proposicao/filtrar`, `GET /proposicao/{id}`, `/norma-legal/...`) at `http://webservices.assembleia.pr.leg.br/api/public`: works, but **plain HTTP only** (its https port presents a self-signed "BLACKHOLE" certificate and answers 403, from the laptop and from GitHub; the same paths on consultas over https demand the reCAPTCHA token). The repository never fetches over plain HTTP (`tests/test_db_state.PlainHttpTests`). Diários da Assembleia page: an archive to 2011 only. Infolep: the staff intranet. LexML (below). **Casa Civil's Sistema Estadual de Legislação** (www.legislacao.pr.gov.br, no robots.txt: 404): the year list of laws, a form POST, 482 laws of 2026 on one page. | **Built (`pr`): adopted laws** (Lei, Lei Complementar, Emenda Constitucional), 3 requests a run. Waiting on Chris: ALEP's API over HTTP, or ask ALEP to serve it over https. |
| MG | Open-data API: robots.txt disallowed it until 14 October 2026; ALMG then allowed /api/v2/ at our request (paging still disallowed), and it is the primary route since 15 October 2026. Diário do Legislativo: same host as the website. The website and every almg.gov.br host timed out from the laptop on 13 October; from GitHub "network unreachable". | The existing website reader now **retries** (30 s, then 90 s, within the budget); once a type's search has failed even so, the other types get one try each. |
| RN | www.al.rn.leg.br answers now (it did not this morning). Its Transparência Legislativa app (transparencialegislativa.al.rn.leg.br) is a React app that loads JSON from `api-transparencialegislativa.al.rn.leg.br/elegis-api-transp-legislativa/` (robots.txt answers the app's HTML: no rules). `processo?tipoPropositura=` lists bills newest first with author, party and publication stage; `processo/ultimas-votacoes` the plenary results. | **Built (`rn`)**: PL, PLC, PDL, PEC, 50 a page, plus plenary results (no tallies printed). |
| CE | ALECE's transparency API (Swagger, transparencia.al.ce.gov.br/api): contracts and payments only. **Its proposições lists** (www2.al.ce.gov.br/legislativo/proposicoes/, linked from the transparency portal; no robots.txt): one search (POST, `escolha=ano`) returns every bill of a year and type, in passage (T) or decided (D), with author, law number and result. Roll calls: "Votações nominais" PDFs and spreadsheets (phase 2). | **Built (`ce`)**: PL, PLC, PEC, PDL; 8 requests a run. The lists print no dates: a new bill is dated the day first listed (the first read is a seed). |
| PE | dadosabertos.alepe.pe.gov.br: the documented endpoints are members, staff and contracts, but ALEPE's own proposições app (proposicoes.alepe.pe.gov.br) reads `/api/v1/proposicoes/projetos/?ano=` from the same open-data host (no robots.txt): every projeto of a year, one XML. | **Built (`pe`)**: PLO, PLC, PEC, PDL with authors and publication date; no stage. |
| PA | The proposições page is a DevExpress form, but a plain form POST (`Ano`, the type) returns the newest ten of a type, server-rendered, with author, date and ementa; by `Numero` a single bill. | **Built (`pa`)**: PLO, PLC, PEC, PDL; numbered gaps since the last run asked one by one (12 a run). |
| GO | portal.al.go.leg.br: no bill list; alegodigital.al.go.leg.br (the bill system, "Opine") resets the connection from the laptop and from GitHub. **Casa Civil's legislation portal** (legisla.casacivil.go.gov.br, robots.txt answers the app's HTML: no rules): the JSON its app loads, `/api/v2/pesquisa/legislacoes?tipo_legislacao=2,1,13&ano=`. | **Built (`go`): adopted laws** with the Diário Oficial edition. |
| BA | www.al.ba.gov.br answers now. Its proposições list (atividade-legislativa-nova/proposicoes) stops at PL 25.888/2025 of 30 July 2025: nothing newer. The Casa Civil's LegislaBahia lists laws, but its robots.txt puts `User-agent: *` and `User-agent: SemrushBot` in one group with `Disallow: /`, which the repository's reader (RFC 9309) reads as disallowed for everyone. | Not built. (One list page was fetched by hand before the robots.txt was read correctly; nothing from it is kept.) |
| SC | www.alesc.sc.gov.br, leis.alesc.sc.gov.br and the e-Legis portal (portalelegis.alesc.sc.gov.br/proposicoes/processo-legislativo, the same e-Legis family as Rio Grande do Norte's) answer **GitHub's runners only**. | **Built 13 October 2026 (`sc`), read on GitHub only** (the GitHub-side step, below): the e-Legis list (server-rendered, ten a page, newest first; robots.txt answers 404, no rules): type, number, year, ementa, entry date, authors, situação. |
| MT | Its SAPL holds nothing after 2025. www.al.mt.gov.br/proposicao ("Projetos em tramitação", a server-rendered report; robots.txt disallows only `/proposicao?` with a query) and api.al.mt.gov.br (an API landing page) answer **GitHub's runners only**. legislacao.mt.gov.br redirects to a private aggregator behind a Cloudflare challenge (not bypassed). | **Not buildable** (13 October 2026): page 1 of the report is all robots.txt allows (every page and filter is `/proposicao?...`, disallowed), and page 1 lists the number 1 of each type; api.al.mt.gov.br's proposição endpoints answer 401 (OAuth 2.0, for the Assembly's suppliers; we hold no credentials and create no account). |
| MS | sgpl.consulta.al.ms.gov.br: its public API (`/sgpl/sgpl-api/public/`) sits behind a proof-of-work captcha (`captcha/challenge`): a bot check, not bypassed. diariooficial.al.ms.gov.br lists the Diário's PDFs (phase 2: PDF parsing). aacpdappls.net.ms.gov.br (state legislation) answers 403. | Not built. |
| SE | al.se.leg.br: WordPress, atas and audio only. aleselegis.al.se.leg.br (its legislation system) times out from the laptop and from GitHub. | Not built. |
| DF | www.cl.df.gov.br and dadosabertos.cl.df.gov.br time out from the laptop and from GitHub. SINJ (the DF's legal database) answers, but its search backend `/sinj/ashx/` is disallowed by robots.txt. | Not built. |
| RS, ES, AP | Every host tried (www.al.rs.gov.br, ww4/ww3.al.rs.gov.br; www.al.es.gov.br, www3.al.es.gov.br; www.al.ap.gov.br, www.al.ap.leg.br) times out from the laptop and from GitHub. ES's Diário Oficial (ioes.dio.es.gov.br) answers: PDF editions (phase 2). | Not built. |
| MA, RR | sapl.al.ma.leg.br times out from GitHub too; sapl.al.rr.leg.br answers 403 to robots.txt from GitHub too. | Still tried every run. |

**LexML Brasil** (the national legal-information network): its robots.txt
disallows `/busca/`, where the documented SRU endpoint lives
(`/busca/SRU`); it allows `/sru` and `/urn`, but `/sru` answers 404 and
the URN resolver needs a known URN (it cannot list). Not used; asking the
Senate's LexML team to allow `/busca/SRU` for identified programs would
open every state's laws at once. Third pass (below): no other allowed
interface exists; the contact is found.

**Adopted laws are not bills.** For Paraná and Goiás the edition shows a
law the week it is published (keyed `pr/Lei 23448/2026`, kind Lei, LC or
EC), with "(via the ... Casa Civil's ...: adopted law)" on its line; a bill
in passage there is not seen until it becomes law.

**BUILT 13 October 2026 for Santa Catarina (Chris: include SC and MT in the
GitHub-side step; branch `us-github-states`); Mato Grosso not buildable
(above).** The step is shared with the US one (`tools/github_half.sh`,
`docs/mac-mini.md` "The GitHub-side step"): GitHub's own Brazil weekly reads
`sc` inline; on the Mini, `jobs/br-weekly.sh` asks GitHub at the start of
its week, before anything is written and while it holds its lock, for a run
of `br-weekly.yml` with `states_github=true`, which reads `sc` and publishes
the store; the Mini fetches it again and runs its step with
`--exclude-sources sc`. No artifact hand-off and no new workflow were
needed. The original proposal, kept for the record: A job on GitHub's runners (the IP they answer), read-only
towards the assemblies, that fetches ALESC's e-Legis proposições (once its
JSON backend is identified from the runner) and ALMT's "Projetos em
tramitação" report, writes the parsed rows as a small JSON artifact (or a
commit to a data branch), and lets the Brazil weekly import them into
`brs_bills` with source `sc` / `mt`. Needs Chris's go-ahead (a new
workflow that commits, or a new artifact hand-off to the Mini).

**Volumes measured on 13 October 2026** (first read, scratch store):
ALRN 176 bills (11 on our ground) and 46 plenary results; ALECE 602 bills
of 2026 (23 on our ground); ALEPE 536 (29); ALEPA 38 (newest ten of each
type); Goiás 50 laws; Paraná 490 laws of 2026 (6 on our ground). The six
take about a minute together.

## Third pass: Paraná's bills over plain HTTP, and LexML (13 October 2026)

Chris, 13 October 2026. Paraná: "Allow the narrow exception". LexML: "Yes,
both" (look for an interface LexML's robots.txt allows; find its contact).

### Paraná: ALEP's open-data API (`alep`, `tools/br_alep.py`)

ALEP documents the API on its transparency portal
(transparencia.assembleia.pr.leg.br/servicos/dados-abertos: "API de Dados
Abertos", base URL `http://webservices.assembleia.pr.leg.br/api/public`).
Six endpoints, all measured from the laptop on 13 October 2026:

| Endpoint | Method | Used |
|---|---|---|
| `/proposicao/campos` | GET | no (13 types, 177 subjects, 568 authors, 2 statuses) |
| `/proposicao/filtrar` | **POST** | **no**: Chris's condition is GET only |
| `/proposicao/{código}` | GET | **yes**: one proposição with its tramitação and the laws it became |
| `/norma-legal/campos`, `/norma-legal/filtrar` (POST), `/norma-legal/{código}` | | no (the Casa Civil's https list already gives the laws) |

robots.txt (read over the same scheme each run) disallows only account,
admin and `/v2/api-docs/` paths. The https port presents a self-signed
"BLACKHOLE" certificate and answers 403 (from the UK and from GitHub).

**The exception, in one place:** `src/http.PLAIN_HTTP_EXCEPTIONS` (date,
Chris's decision, reason, GET only, the API prefix and the host's
robots.txt). `tests/test_db_state.PlainHttpTests` scans every whole
http:// URL in `src/` and `tools/` and fails on any not under that entry;
`HttpClient` refuses a POST over plain HTTP and any other path on the
excepted host, before sending.

**How bills are found with GETs only.** A código is one sequence for every
document ALEP registers (ofícios, requerimentos, indicações, relatórios,
bills), rising with time: 994 is 2011, 50000 is 2014, 100000 is 2021,
125000 September 2025, 131469 PL 795/2026 of 6 October 2026; the highest on
13 October was 131522. The sequence has holes (131490 to 131499 absent,
131500 present), and a new bill appears first unnumbered ("AGUARDANDO
RECEBIMENTO", "ELABORAÇÃO"). The reader walks up from the last código seen
(seed 131400), stops after 40 misses in a row, asks the holes below the
top again on three later runs, asks unnumbered bills again for two months,
and re-reads ten bills on our ground a run for their stage. At most 200
GETs a run (1 s apart, about 0.55 s each from the UK): about three
minutes, inside the step's 600 s, in parallel with the other sources.

**What is stored:** PL, PLC, PDL, PEC keyed `pr/PL 781/2026` with ementa
(capitals), author as printed ("DEPUTADA MARIA VICTORIA", "PODER
EXECUTIVO"), received date, the latest substantive tramitação step and
where ("PARECER FAVORÁVEL (COMISSÃO DE CONSTITUIÇÃO E JUSTIÇA)"; handling
such as INFORMAÇÃO, DESPACHO, ENCAMINHADO is skipped), "Became Lei
23284/2026 (per ALEP)" once it is law; plenary results ("1º TURNO -
APROVADO", "TURNO ÚNICO - APROVADO") and committee decisions ("APROVADO O
PARECER FAVORÁVEL") as `brs_votes` with the result only. **Members'
votes: none** (the API has no vote endpoint; "Controle de votações" is
reCAPTCHA-gated). Every edition line ends "(via ALEP open data,
unencrypted)"; the coverage line says "ALEP (bills via open data,
unencrypted)".

**Cross-check against the https law list.** ALEP's `normasLegais` give the
law a bill became. `alep` is read and stored right after `pr` (the Casa
Civil's laws, over https), and each law ALEP names is compared with the
Casa Civil's row: the same number with a different title (word overlap and
character match both under 0.5), or near-identical text (character match
0.95) under another number, is a gap line ("ALEP open data (unencrypted)
cross-check: ... ALEP's copy not trusted") that marks the read as gapped
on the coverage line. A law the Casa Civil has not listed is not a
mismatch. Measured on 13 October 2026 over a sample of
2026 bills that became law (every ninth código from 127600): 23 laws named
by ALEP, 22 matching the Casa Civil's (titles 0.69 to 1.0), and **one real
mismatch**: ALEP gives PL 493/2026 as Lei 23976/2026, while the Casa
Civil lists the same text as Lei 23276/2026 (a slipped digit in ALEP's
record), flagged as a gap and not trusted.

**First read, 13 October 2026** (scratch store): 176 GETs, 15 bills of 5
and 6 October (PL 781 to 797/2026; none on our ground: titles of
utilidade pública, dates, budget), 24 holes and 13 unnumbered drafts kept
for the next run, under three minutes.

### LexML: no allowed interface

| Tried | Outcome |
|---|---|
| www.lexml.gov.br/robots.txt | `Disallow: /busca/`, `/doc/`, `/linker/`; `Allow: /urn`, `/sru`; Crawl-delay 5 |
| `/sru`, `/sru?operation=explain` | 404 |
| `/oai`, `/oai-pmh`, `/OAI`, `/oai/request` (`verb=Identify`), `/api`, `/dados` | 404 |
| `/urn/<urn>` | the resolver page for one known URN; it cannot list |
| The Senate's open-data catalogue, "Acervo do portal LexML" (www12.senado.leg.br/dados-abertos) | documents a "Webservice do acervo", the SRU, which lives under `/busca/` (disallowed); the webservice pages themselves sit behind a JavaScript bot check (not bypassed) |
| projeto.lexml.gov.br (documentation, downloads) | OAI-PMH is how LexML **harvests** its providers (Parte 4, the provider kit); LexML exposes none. Downloads: the provider toolkit only |
| github.com/lexml | code, schemas, vocabularies; no data dumps |
| The acervo (desc_acervo.html) | state providers: SC, AL, RO, AM, MG, SP; all six are read already (Santa Catarina by the GitHub-side step), so LexML would add state laws, not new assemblies |

Nothing built; never `/busca/` or any way round it.

**Contact for a permission request** (not sent): **lexml@senado.leg.br**,
"Equipe LexML - Senado Federal/Prodasen", tel. (61) 3311-3673, in the
official toolkit's leiame.txt:
https://github.com/lexml/lexml-toolkit/blob/master/lexml-toolkit-dist/src/main/doc/leiame.txt
(projeto.lexml.gov.br/contact-info answers 403).

## Taxonomy noise (second pass, 13 October 2026)

The false positives the first pass listed are left out of the Brazilian
edition by four `exclude_titles` rules in `config/edition-noise-br.yaml`
(hand-edited; no taxonomy change, so the store keeps every match and
`--reclassify` is not needed). Each rule needs the loose term **and** a
noise word in the title, and none of the words that make it our ground.
Measured on 13 October 2026 over the bills on our ground in a scratch store
(7,751 state bills from 15 assemblies: ALESP's whole legislature, the SAPL
houses' last month, the six new routes) plus the 1,080 Câmara proposições
of the federal store (read-only):

| Term (area, tier) | Rule leaves out when the title also has | Matched | Left out after | Before |
|---|---|---|---|---|
| `religios*` (8, 2) | turismo, rota, roteiro, patrimônio, calendário, festa, santuário, basílica, paróquia, romaria, peregrinação, utilidade pública, bem material/imaterial, interesse turístico; **kept** with liberdade, intolerância, perseguição, racismo, discriminação, preconceito, imunidade, isenção, templo, laico | 64 | 30 | 0 |
| `transplante*` (13, 2) | (anything) **kept** with doação, doador, remoção, retirada, captação, presumido, consentimento, morte encefálica/cerebral, tráfico, Lei 9.434 | 7 | 4 | 0 |
| `casamento civil` (9, 1) | comunitário, coletivo, pet, animais, gratuito, programa; **kept** with mesmo sexo, homoafetivo, menores, infantil | 1 | 1 | 0 |
| `infertilidade` / endometriose (10, 2) | dia, semana, mês, campanha, conscientização; **kept** with fertilização, reprodução assistida, embrião, inseminação, substituição, barriga solidária/de aluguel | 2 | 2 | 0 |

In all 37 of 340 items on our ground leave the edition (none federal). Left
out, for example: ALESP's "Rota Turística Religiosa" and utilidade-pública
declarations for religious associations, Pernambuco's sanctuaries as
"Área de Interesse Turístico Religioso", Paraná's religious-route laws,
ALESP's PL 648/2026 (care for transplant patients) and PL 630/2026 (organ
transport vehicles), ALESP's PL 690/2026 ("Programa Casamento Pet
Friendly"), Amazonas' PL 317/2026 (an infertility awareness week) and
Pernambuco's PLO 3892/2026 (an infertility awareness campaign). Kept, for
example: the Lei de Liberdade Religiosa amendments, religious intolerance
days, tax exemptions for religious entities, the "Dia do Doador de Órgãos"
and the federal PL 2288/2015 (the Lei dos Transplantes). One noise item
stays: a pedestrian-crossing bill near temples (PLO 3850/2026, PE).

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

### ALMG (Minas Gerais): the open-data API (primary since 15 October 2026)

ALMG rewrote `dadosabertos.almg.gov.br/robots.txt` at our written request
(Centro de Atendimento ao Cidadão, protocolo 126599, 14 October 2026;
recorded in `src/robots_guard.PERMISSIONS` with `asks_robots=True` and in
docs/robots-runtime.md). It now allows `/documentacao/`, `/api/ajuda/` and
`/api/v2/`, and still disallows `/api/v2/*?*p=`, `*?*ord=`, `*?*tp=`,
`*?*ordenacao=` and everything else. We asked whether paging is acceptable;
no answer yet. So `fetch_mg_api` (tools/br_states.py) **never pages or
sorts**:

- **Bills**: `proposicoes/pesquisa/direcionada?formato=json&tipo=<PL|PLC|PEC>&ini=<AAAAMMDD>&fim=<AAAAMMDD>&sitTram=2`,
  page 1 only, at the API's default page size (**20**, measured 15 October
  2026; it cannot be raised without `tp=`). One query per week from the
  last read (a week of overlap; a first read covers 60 days); a week whose
  `noOcorrencias` exceeds `tamanhoPagina` is split in halves down to single
  days. ALMG publishes bills in batches: 51 PLs on 25 June, 33 on 2 July,
  34 on 9 July and **100 on 14 August 2026**, so a single day often holds
  more than one page. Such a day keeps its page (the default order is type,
  year, number descending: the highest numbers) and the rest are read **one
  by one by number** (`proposicoes/PL/<n>/<year>?formato=json`, no other
  query), walking down from the lowest number listed until the day's count
  is reached or an already-read bill is met, at most 150 a run. What the cap
  leaves is a gap line ("N PL(s) published on <day> not read yet ...") and
  is carried in `brs_reads.meta` to the next run.
- **Moved bills**: bills on our ground or watched that a run's searches did
  not list are re-read by number (at most 40 a run, rotating), and only
  their stage is updated.
- **Plenary results**: `plenario/reunioes/pesquisa?formato=json&ini=&fim=`
  (weekly, split when over a page), then `plenario/reunioes/detalhes/<y>/<m>/<d>/<hh:mm>?formato=json`
  for each ordinária and extraordinária meeting: every PL, PLC and PEC on the
  Ordem do Dia with its recorded result ("Aprovado em 1º turno na forma do
  Substitutivo nº 1"). Results only: **the API publishes no plenary
  votações nominais** (no member's vote, no tally). A voted bill neither
  listed nor stored is classified from the ementa the meeting prints and,
  when on our ground or watched, read by number and stored with its vote.
- **Deputies**: `deputados/em_exercicio?formato=json`, id, name and party
  (`brs_members`, keyed `mg/<ALMG id>`); bill authors use the same ids.
- **Not read**: committee per-member votes (the committee results carry
  them only rarely, at about 450 KB a bill); the Diário do Legislativo.

ALMG's documented limits are kept: one request at a time, 1.5 s apart (they
allow two at once, one second apart). Measured 15 October 2026: a first
read (60 days) is about 65 requests when nothing is published (the election
recess: no bill since 14 August); a busy week adds a few splits and up to
150 bill-by-bill reads. If the API cannot be used on a run (robots.txt
unreachable or refusing, or the host down), the website search below is
read instead and one gap line says so.

If ALMG confirms paging and lifts the Disallow lines, the date splitting
and the number walk can give way to ordinary paging (`p=`), and the page
size could be raised (`tp=`).

### ALMG (Minas Gerais): the website's bill search (fallback)

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
retries. Since 15 October 2026 this is the fallback; the open-data API
above is read first.

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

**Classification false positives seen** (taxonomy matters, not code;
handled in the second pass, "Taxonomy noise" above):
`religios*` on utilidade-pública declarations for religious associations,
`imigrante*` on the Rodovia dos Imigrantes (area 11, hidden anyway),
`casamento civil` on a "pet-friendly wedding" programme, `transplante*`
(organ donation) on transplant policy. The noise file or a taxonomy tweak
can take them out.

## Not built, and why

(Updated after the second pass; the table under "Alternative routes" has
every route tried.)

- **Paraná (ALEP)**: the proposições search and the vote search both demand
  a reCAPTCHA token; never bypassed. Bills, stages and results are read
  from ALEP's open-data API over plain HTTP (`alep`, third pass), with the
  adopted laws from the Casa Civil (`pr`). Members' votes are not
  published as data. The Ordem do Dia (weekly PDFs listing the bills on
  the floor) could be read for "on the floor this week" (phase 2).
- **Unreachable from the UK and from GitHub's runners**: Rio Grande do Sul,
  Distrito Federal, Espírito Santo, Amapá, Maranhão. **GitHub only**: Santa
  Catarina (read by the GitHub-side step since 13 October 2026), Mato
  Grosso (not buildable: robots.txt and an OAuth API, above).
- **Blocked**: Mato Grosso do Sul (proof-of-work captcha); Bahia's laws
  portal (robots.txt). **No list**: Sergipe; Bahia's own list stops in July
  2025.
- **Votes**: no assembly read publishes plenary roll calls by member as
  data. ALESP's per-member committee votes are the exception; Pará and
  Ceará have "Votações nominais" pages (phase 2).
- **Vetoes**: a governor's veto of a bill on our ground is a SAPL type of
  its own (Veto Total/Parcial) and is not read yet; phase 2.

## Waiting on Chris

1. ~~**ALMG's open-data API**~~: done 15 October 2026. ALMG changed its
   robots.txt at our request (protocolo 126599) and the API is now the
   primary route (see "ALMG open-data API"). Still open: our question whether
   paging (`p=`, `tp=`) is acceptable; until robots.txt allows it the reader
   never pages. History: its robots.txt disallowed everything; the
   website search was used instead. Ask ALMG to allow it, or decide that a
   documented open-data API is exempt (the repository's rule today: no).
   Contact (13 October 2026, branch `access-routes`; nothing sent): ALMG
   publishes no email for the open-data service; its portal points to the
   "Fale com a Assembleia" form (www.almg.gov.br/servicos/fale-com-a-assembleia/),
   and the Ouvidoria's address, ouvidoria@almg.gov.br, appears on older
   ALMG pages (2013; low-medium confidence); main line (31) 2108-7000. The
   alternative routes for Minas Gerais (the Diário do Legislativo, LexML)
   are the branch `br-states-alt`'s work, not repeated here.
2. ~~Seed `config/watchlist-br-states.yaml`~~: seeded 13 October 2026
   (Chris: "Accept the watchlists, apply the terms after measuring") with ten
   bills found by the two passes, each key checked against that day's
   scratch store: Alagoas PLO 1275/2025 (abortion-prevention programme,
   awaiting sanction, area 1); São Paulo PL 734/2026 (trans toilets, 5),
   PL 457/2026 (toilets by biological sex, 5), PL 670/2026 (the Bible as a
   school text, 6 and 8), PL 336/2026 (pupils' conscientious objection, 6
   and 8), PL 1275/2025 (sexual and reproductive rights policy, 1), PL
   183/2025 (legal-abortion care programme, 1), PL 543/2025 (burial of the
   unborn and stillborn, 1), PL 646/2024 (children barred from the Pride
   parade, 5 and 6), PL 440/2025 (removal of teachers for indoctrination,
   6). A watched bill takes its areas and is never noise-filtered.
3. ~~Taxonomy-pt false positives~~: done in the second pass through the
   edition's noise rules (`config/edition-noise-br.yaml`, measured below).
4. Whether a Brazilian vantage point (a small VPS or a partner's machine)
   is worth it for the five assemblies that answer neither the UK nor
   GitHub (RS, DF, ES, AP, MA).
5. ~~ALEP's open-data API over plain HTTP~~: allowed by Chris on 13
   October 2026 as the single exception; built (`alep`, third pass).
6. ~~The GitHub-side step~~ for Santa Catarina: built 13 October 2026; Mato
   Grosso not buildable (above).
7. **LexML**: no allowed interface exists (third pass). Ask the LexML team
   (lexml@senado.leg.br) to allow `/busca/SRU` for identified programs (one
   source for every state's laws); not sent.

## Files touched outside the layer's own

Third pass: `src/http.py` (`PLAIN_HTTP_EXCEPTIONS`, the refusal of any
other plain-HTTP POST or path on that host), `tests/test_db_state.py`
(`PlainHttpTests` reads whole URLs against that list), `tools/br_alep.py`,
`tests/test_br_alep.py`, a hook in `br_states.store_result`
(`after_store`), `brs_store.VIA`/`READ_NOTES`.

`src/db.py` (5 table names, one ensure_schema call), `src/editions/br.py`
(post_render, notice, a coverage line), `jobs/br-weekly.sh` (one step, one
reclassify line, the collector's reserve), `tools/coverage.py` (two
freshness rows, two awaiting-first-run rows), `docs/brazil-scope.md`,
`docs/country-parity-handover.md`.

## Forward agenda (regional_agenda, 16 October 2026)

`src/regional_agendas/br.py` reads what each assembly has BOOKED (plenary
sessions with their pauta or ordem do dia, committee meetings with their
pauta) into `regional_agenda`, through the shared collector
(`python3 tools/regional_agenda.py br`). Region codes are the lower-case
UFs of `src/brs_store.STATES`. Every route below was probed live from the
laptop on 16 October 2026, robots.txt read first, honest User-Agent. Not
wired into any job yet.

2026 is an election year (run-off 25 October): plenaries are thin and most
pautas are published a day or two ahead, so the first run found few named
items. The readers are built for the normal rhythm.

| UF | Route | Format | Reaches | robots.txt | First run (16 Oct) |
|---|---|---|---|---|---|
| SP | `legis-api-portal-prd.al.sp.gov.br`: `sessoes-plenarias/consulta?dataInicial=&dataFinal=` (sessions of the window), `sessoes-plenarias/<id>/ordem-do-dia` or `/pauta` (HTML inside JSON, one block per propositura), `colegiado/reunioes?dataInicio=&dataFim=` and `colegiado/reuniao/<id>/pauta` | JSON (the API the portal's own SPA loads; found in its bundle `sessao-plenaria-api-*.js`) | sessions booked to late November (solemn sessions); pautas on the day | no robots.txt (404); www.al.sp.gov.br disallows only /web, /StaticFile and a few repositories | 15 items to 23 Nov, 1 on our ground (PL 875/2026, "Estatuto Paulista de Defesa da Vida desde a concepção", in pauta for amendments) |
| MG | `dadosabertos.almg.gov.br/api/v2/comissoes/reunioes/pesquisa?ini=&fim=` and `plenario/reunioes/pesquisa`, then `plenario/reunioes/detalhes/<y>/<m>/<d>/<hh:mm>` | JSON, 20 a page, never paged: a range holding more is split by date | committee meetings two weeks ahead; plenaries convened a day ahead | allowed since 14 October 2026 at our request; paging and sorting still disallowed (the reader refuses to build such a URL) | 4 items to 28 Oct (two audiências públicas with their purpose, two booked meetings) |
| RJ | `www2.alerj.rj.gov.br/ordemdodia/` (month calendar, days with a pauta marked) and `pauta/?op=D&data=Y;M;D` | HTML, about 30 s a request | the current month (the next month is an ASP.NET postback); pautas posted about a week ahead in normal weeks | www2 robots.txt answers the home page (no rules) | nothing booked after 15 October |
| PR | `transparencia.assembleia.pr.leg.br/plenario/pautas/{ordem-do-dia,ccj,comissoes-tematicas}/ajax?page=1` (the JSON the portal's pautas.js loads) and each sitting's PDF on `storage2.assembleia.pr.leg.br` | JSON + PDF (pypdf; "Item N – ..." blocks) | as published (sessions so far posted the week before) | allows all (`Disallow:` empty) | no session or meeting in the window (the last were 13 October and 25 August) |
| PE | `www.alepe.pe.gov.br/agenda` (form POST `operacao=lerAgendaMensal`, month and year) and `/ordem-do-dia/` (POST `operacao=lerOrdem`, the date) then `/detalhe-ordem-do-dia/?docid=` | HTML | plenaries booked to the month's end, committee hearings, solemn meetings; the ordem do dia on the day | allows all | 12 items to 29 Oct (9 plenaries booked, 2 committee hearings, 1 solemn meeting) |
| CE | `www.al.ce.gov.br/agenda?datetimes=dd/mm/yy - dd/mm/yy` | HTML, one page for the window | solemn sessions and committee hearings weeks ahead | disallows only `/banco-de-imagens/download/` | 6 items to 27 Oct |
| PA | `www.alepa.pa.gov.br/Home/Page/PautasdoPlenario` (dated list) and `/Legislativo/DetalhesPauta?Id=` | HTML | pautas posted shortly before the session | allows all | nothing after 13 October |
| PB, AM, AL, PI, RO, TO, AC | SAPL REST API: `/api/sessao/sessaoplenaria/?data_inicio__gte=<today>&page_size=100`, then for up to two sessions with a published pauta `/api/sessao/ordemdia/?sessao_plenaria=<id>&page_size=100` | JSON | sessions are created close to the day | allows /api/, **Crawl-delay: 60** (honoured: about a minute a request, so the seven houses are asked in parallel on the first SAPL region's turn) | no session booked after today in any house |

Not read, and what was tried:

- **Bahia**: ALBA's own ordem do dia, pauta and committee "resumo de
  pauta" pages stop in July 2025 and point to `albalegis.nopapercloud.com.br`
  (SPL), which answers 403 to robots.txt and to every page. No route.
- **Rio Grande do Sul, Espírito Santo, Distrito Federal, Amapá**: robots.txt
  timed out from the laptop on 16 October (150 to 185 s), as from GitHub's
  runners on 13 October.
- **Santa Catarina**: its hosts answer GitHub's runners only; this step
  runs where they do not.
- **Goiás**: `portal.al.go.leg.br/agenda?data=YYYY-MM-DD` answers (robots.txt
  allows it) but is one page a day of solemn sessions, talks and events with
  no pauta; not built (56 requests a run for little business).
- **Maranhão**: `sapl.al.ma.leg.br` times out from outside Brazil; not
  asked, so the SAPL houses stay inside the clock. **Roraima**: its SAPL
  answers 403 to robots.txt (blocked). **Mato Grosso**: answers GitHub's
  runners only; its SAPL held nothing recent on 13 October.
- **Rio Grande do Norte**: the site shows session photo albums; the
  Transparência Legislativa API read for bills has no agenda endpoint found.
- **Mato Grosso do Sul**: the ordem do dia appears only as news items; the
  bill system sits behind a proof-of-work captcha (never bypassed).
- **Sergipe**: atas and audio of past sessions only.

Live run (16 October 2026, scratch store): 14 of 27 regions read, 37 items,
1 on our ground, 11 to be announced, no gaps; 183 s wall time (the SAPL
houses' minute each, in parallel, and ALERJ's slow calendar).
THROTTLES: SAPL hosts 60 s, ALERJ 5 s, the others 1.5 to 2 s.

Privacy: ALMG's committee-meeting replies carry each invited guest's name and
CPF number (`listaConvidados`); the reader never reads them and the test
fixtures have them removed.
