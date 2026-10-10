# Country editions: Chris's decisions, 10 October 2026

Recorded on the decisions page (claude.ai artifact T4UHhY3HdkJjYh2WxA3NCh)
after the 30 country scopes of 9 October. This file is the spec for merging
the country branches. Each `docs/<country>-scope.md` holds the detail behind
each item.

## Edition structure

- **Own editions** (Slack DM to Chris): Spain, Italy, France, Netherlands,
  Belgium, Austria, Switzerland, Poland, Portugal, Croatia, Slovakia, Hungary,
  Brazil, Argentina, Mexico. These are the countries with their own CitizenGO
  presence.
- **One Latam monitor** for every other Latin American country, where
  CitizenGO works through CitizenGO Latam: Colombia, Chile, Peru, Ecuador,
  Bolivia, Uruguay, Paraguay, Guatemala, Panama, Honduras, El Salvador,
  Dominican Republic, Costa Rica, Venezuela, Nicaragua. This replaces the
  "Central America digest" (X10) and the per-country cadence answers (EC5,
  SV1, HN1): one Latam edition, with a section per country that has news and
  instant alerts for watched or tier-1 items. Collection stays per country
  (`<cc>_store`, `<cc>_rollcalls`); one Mini job may run the Latam collectors
  in sequence.
  - Venezuela (VE1 "build something", VE2, VE3): a monthly keyword note from
    the Asamblea's news feed, plus the Ley contra el Odio reform watched by hand.
  - Nicaragua (NI1 no edition, NI2 yes): no parliamentary section; La Gaceta
    in scope for religious-freedom tracking (church and NGO closures).
  - Costa Rica, Paraguay: no collector until access is cleared (CR1, PY1);
    sections stay empty until then.

## Shared decisions

| Ref | Decision |
|---|---|
| X1 | One shared `taxonomy-es`, country-only terms tagged |
| X2 | One shared `taxonomy-pt` (Brazil + Portugal), spelling variants tagged |
| X3 | Fix `src/filter.py` at merge: fold accents, treat non-ASCII letters as word characters |
| X4 | Approve term lists without a native read |
| X5 | Party-group countries (AT, PT, NL): derive member records from the group, labelled as derived |
| X6 | Source party history before relying on party at the vote (HR, CL, GT) |
| X7 | Tesseract OCR on the Mini: yes (PE, HR, CO later phases) |
| X8 | Constitutional courts as a later phase: yes |
| X9 | Guatemala and Mexico run on GitHub Actions fortnightly rather than weekly, to save Actions minutes (GT in even ISO weeks, MX in odd); backfill budgets as built |
| X11 | Gender-violence and femicide laws: in, tier 2 |
| X12 | Contraception in area 1 at tier 2, everywhere |
| X13 | Antisemitism out, consistent with the US |
| X14 | Allow opt-in gzip in `src/http.py` |
| X15 | Store every member position |
| X16 | AI judge: deferred (stays off). The paid API judge stays off; the free session judge (Claude Code on the Mac Mini, plan allowance) is adopted for the editions and Latam, 10 October 2026 (below) |
| X17 | Merge one branch at a time, strongest data first |

## Term lists

Every proposed list is approved as drafted (ES1, IT1, FR1, NL1, BE1, AT1,
CH1, PL1, PT1, HR1, SK1, HU3, BR1, AR1, MX1, CO1, CL1, PE1, EC1, BO1, UY2,
PY2, GT2, PA2, HN2, SV2, DO1, CR2), with these scope calls applied:

- In: Spain's sexual-offences law (ES3, as drafted) and VOX public-space bill
  as religious freedom (ES4); Democratic Memory only where it touches the
  Church and Cuelgamuros (ES2). France: political Islam in area 8 (FR2).
  Belgium: stillborn-child bills area 1 (BE3), religious-symbol bans and
  laicity (BE4), labour trafficking area 12 (BE5). Austria: family benefits
  area 9 (AT2), Pride and queer funding (AT3). Switzerland: individual
  taxation area 9 (CH2), E-ID (CH3), burqa ban (CH4). Portugal: family policy
  area 9 (PT2), school choice area 6 (PT3), face-covering law, which CitizenGO
  supports (PT4), Church abuse compensation (PT5). Croatia: WHO declaration
  (HR2), Sunday trading area 8 (HR3), ombudsperson reports (HR4). Slovakia:
  NGO Act (SK2), Education Act net (SK3), parental allowance area 9 (SK4).
  Brazil: misogyny area 7 (BR2), gambling (BR3), drug decriminalisation (BR4).
  Mexico: feminicide (MX2), political gender violence area 7 (MX3). Colombia:
  "enfoque de género" tier 1 (CO2). Ecuador: palliative care area 2 (EC2),
  children's code and LOEI tier 2 (EC3). Honduras: criminal defamation (HN3),
  emergency contraception tier 1 (HN4), prayer sessions and church grants
  (HN5). El Salvador: state of exception (SV3), church items (SV4). Panama:
  family maintenance (PA3), sterilisation tier 2 area 1 (PA4). Uruguay: pedidos
  reported (UY3), INAU guarded (UY4). Paraguay: declarations and pedidos count
  (PY3). Costa Rica: 25825 in (CR3), 25829 religious freedom (CR4). Chile:
  migration watched but hidden (CL2). Hungary: constitutional amendments always
  triaged (HU4), interpellation votes count (HU5).

## Watchlists

Approved as drafted: NL2, BE2, AT4, CH5, PL3, HR5, SK5 (tlač 733), BR6, AR5,
MX5, CO5, PE3, BO3, GT3, HN6, DO3. Panama's stays empty (PA5 deferred).

## Per-country actions

- Spain: build the edition now (ES6). Senado: write to its open-data contact
  (ES5, a message in Chris's name).
- Italy: keep Openpolis for Camera votes, and add the official
  dati.camera.it service as a backup, or main when it is quicker (IT2).
  Regions after national (IT3).
- France: archive the AN weekly zips (FR3); follow the aide a mourir decrees
  first (FR4); go ahead with the Senat phase (FR5).
- Netherlands: DM carries votes only (NL3); Eerste Kamer via its web pages
  (NL4); Chris reads the open data disclaimer (NL5).
- Belgium: votes-only DM before the full edition (BE6).
- Austria: ask meineabgeordneten.at for a licence (AT5, Chris's name);
  Landtage after national (AT6).
- Switzerland: run the Italian list on the Italian texts too (CH6).
- Poland: accept the Senate gap (PL2).
- Portugal: backfill XV and XVI from CI (PT6); Chris reads the reuse terms (PT7).
- Slovakia: phase 2, bill documents (SK6).
- Hungary: register for the W-API token (HU1, name to confirm); write to the
  Office if the CAPTCHA persists (HU2); build the gazette collector now (HU6);
  use karzat's CC BY data with attribution (HU7).
  HU6 built 10 October 2026 (branch `hu-gazette`): `tools/hu_gazette.py`
  reads the Magyar Közlöny's contents, the Hungarian edition
  (`src/editions/hu.py`) reports what became law with a standing line that
  bills and votes await the token, and `hu-weekly` runs Wednesdays 03:00
  London on the Mini. HU7: karzat publishes its derived tables as files in
  its GitHub repository (`data/derived/`, CC BY 4.0), so they may be used.
  HU7 built 10 October 2026 (branch `hu-karzat`): a one-off, hand-run Mini
  job (`jobs/hu-karzat-backfill.sh`) loads the term's papers, votes and
  positions to 28 August 2026, credited to karzat (name, link, CC BY 4.0)
  wherever they appear; see docs/hungary-scope.md, "HU7, as built". The
  divorce term no longer matches elections (taxonomy-hu v0.2).
- Brazil: Portuguese source text with English takeaways (BR5).
- Brazil: BR3 and BR4 terms approved by Chris on 10 October 2026, added to
  `docs/keyword-taxonomy-pt.md` as areas 14 (gambling and betting) and 15
  (drug decriminalisation), every term tagged [only: br].
- Argentina: try Diputados votes from the Mini (AR2); read the register gently
  (AR3); the monitor may read www.hcdn.gob.ar (AR4; no Claude session crawls
  it, the scheduled monitor script only); store 2024-25 Senate actas (AR6);
  Ley 13.640 lapse rule confirmed (AR7).
- Mexico: Senate stays out per its robots.txt (MX4).
- Colombia: no votes for now (CO3); Court section yes (CO4).
- Peru: the encrypted expediente endpoint is left out (PE2, reversed on
  10 October 2026: do not build it); regional councils later (PE4).
- Ecuador: do not use the bill portal's embedded login (EC4).
- Bolivia: bills-only (BO2); phase 2 written questions (BO4).
- Uruguay: probe parlamento.gub.uy from the Mini first (UY1); build vote
  totals from the Diario PDFs now (UY5).
- Paraguay: ask the Senate's IT office for access (PY1, Chris's name).
- Guatemala: run the curl check from the Mini (GT1); current bloc only (GT4);
  ask the Constitutional Court for access (GT5, Chris's name).
- Panama: no votes (PA1).
- El Salvador: archive vote PDFs (SV5); ask for the unpublished votes (SV6,
  Chris's name); backfill over six Sundays (SV7).
- Dominican Republic: Chamber-only votes (DO2); backfill 2020-24 (DO4).
- Costa Rica: ask the Asamblea for access (CR1, Chris's name).

## Later decisions

- PE2 reversed: Peru's encrypted expediente endpoint is left out and will not
  be built (its identifiers are AES-encrypted with a key in the site's front
  end).
- Quebec: `config/taxonomy-qc.yaml` stays unchanged. The Belgian and Swiss
  requests to edit existing Quebec terms (the IVG veto, the euthanasie guard
  and the tier differences) are declined; country additions stay additions.
- France 5CA sign-off scope: limited to final votes and watched amendments.
  Only a vote on the whole text, a motion to reject it (or a Yes recorded as
  rejecting it), procedure about the whole text, and the amendment or
  article votes listed under a dossier's `amendments:` in
  `config/watchlist-fr.yaml` (by division key, or by amendment number within
  that dossier) are drafted for sign-off. Built on branch `fr-signoff-scope`
  as a per-country scope on `country5ca.Spec` (every other country keeps the
  full scope) and a reusable `tools/country_5ca.py --prune-out-of-scope`
  (never removes a confirmed or hand-edited entry). Run for France the same
  day: 1,037 unsigned, untouched amendment and article entries removed, 13
  final and reject votes left (10 proposed, 3 need reading), none kept for
  hand edits. No amendment is watched yet.

## The Latam monitor as built (branch `latam`)

- Edition: `tools/latam_monitor.py`, monthly (the 1st, `jobs/latam-monthly.sh`,
  Mini first, `latam-monthly.yml` as backup), to Chris alone by DM, archived
  to `editions/latam-monitor-<date>.md`. A section per country with news on
  our ground since the last edition; one "nothing new" line for the quiet
  countries; one "access pending" line for Costa Rica and Paraguay (CR1, PY1).
- Instant alerts: `tools/latam_alerts.py`, run by each Latam country's weekly
  job after its collector, and by the monthly job for Venezuela and
  Nicaragua. Watched items (any kind), tier-1 items, and status moves of
  watched items; de-duplicated in `data/latam-alerts/<cc>.json`; the first
  pass per country seeds silently; at most eight DMs a run.
- Classification: the collectors' taxonomy-es and watchlist pass, then the
  stub triage for order only (X16: no judge). No [ACT] items.
- Venezuela (VE1-VE3): `tools/ve_news.py` reads the Legislativa news feed
  monthly; the Ley contra el Odio reform is watched by hand in
  `config/watchlist-ve.yaml`.
- Nicaragua (NI2): `tools/nic_gaceta.py` reads La Gaceta (reachable openly,
  keyless; robots.txt 404; the PDF is embedded in each issue page) and keeps
  the notices taxonomy-es (`nic`) matches; the edition shows area 8.
- Not done: one consolidated `latam-weekly` Mini job (each country keeps its
  own job and gate; see docs/mac-mini.md).

## Latam noise filters (branch `latam-noise`)

Chris, 10 October 2026: "no judge yet, we need free alternatives". With the
stub triage only, tier-1 matches were noisy, worst in Honduras's press
releases and the Dominican Cámara's procedural votes. Added, all free and
deterministic, none touching a watched item:

- `config/latam-noise.yaml` (hand-edited; read by `src/latam_noise.py`):
  procedural votes (order of the day, minutes, quorum, recesses, agenda
  changes; for the Dominican Republic also "liberado del trámite de
  lectura", "dejado sobre la mesa", the bulk "grupo de resoluciones
  internas" votes and the honours committee's reports) and excluded titles
  (Dominican honours resolutions, and a vote naming only such bills) leave
  the edition and so the alerts. Referral of a bill to a committee is kept:
  sending a Penal Code bill to the bicameral commission is where the
  causales fight moves. Nicaragua's gazette notices need a cancellation or a
  religious body in their text (approvals of sports associations say
  "personalidad jurídica" too).
- Minimum evidence for an alert: a tier-1 item that is not watched alerts
  only with a tier-1 term in its own title, or two distinct terms in shown
  areas (variants of one term count once; migration terms do not count).
  Honduras's press releases alert only on a watchlist hit, a decree or
  expediente number, or a tier-1 term in the headline; the rest are
  edition-only.
- `config/watchlist-hn.yaml` entries carry `match` phrases (the bill's name
  as releases write it), so a release naming the Ley de Derechos Parentales
  counts as a watchlist hit.
- `config/latam-mute.yaml`: Chris's mute list, by alert key or title
  pattern; the alerts always honour it, the edition while
  `mute_in_edition` is true. A pattern never mutes a watched item.
- The edition's Coverage section counts what the filters left out, per
  country and reason.
- Taxonomy-es (v0.1, `docs/keyword-taxonomy-es.md`, regenerated): guards on
  four terms that misfired in the sample. `capellan*` now needs religious,
  military, hospital or prison company (it matched the surname Capellán,
  as the Dominican scope doc had measured); `materno infantil` and
  `materno-infantil` need abortion, unborn, conception, prenatal or
  gestation company (every sample hit was hospital funding, as El
  Salvador's scope doc had measured); bare `custodia` needs a child,
  parent, divorce or visiting-rights word (it matched police and prison
  custody); `seguridad ciudadana` keeps its free-speech guards but loses
  the loose `libertad*` and `reforma` (it matched Honduran policing
  releases), and gains "Ley Mordaza", "4/2015" and the rights of assembly
  and demonstration.

Measured on the October sample (the scoping stores, 9 September to 9
October 2026): every item the old rules put in the edition (106) or in an
alert (35), labelled by hand as on our ground, doubtful (counted as on our
ground) or noise. The rules were written on the same set, so these numbers
flatter them; the next real month is the honest test.

| | Before | After |
|---|---|---|
| Edition items | 106 | 83 |
| Edition precision | 55.7% | 71.1% |
| Edition recall | 100% | 100% |
| Alerts | 35 | 27 |
| Alert precision | 77.1% | 100% |
| Alert recall | 100% | 100% |

By country (edition, alerts): Honduras 23 to 15 and 10 to 4; Dominican
Republic 28 to 15 and 4 to 4; Venezuela alerts 3 to 2; Nicaragua 2 to 0
and 1 to 0; Colombia, Chile, Peru, Bolivia, Uruguay, Panama and El
Salvador unchanged. The remaining edition noise is tier 2 (hospital and
church funding in Honduras, school-discipline and computer-crime bills in
Peru), left for the mute list rather than more rules.

The guards, over every store held (all rows, not only the month): Spain
and the Argentine Senate unchanged; Argentina's Diputados 83 to 82 (a
flag "en custodia" in a museum); Colombia 112 to 109 and Chile 97 to 93
(custody of evidence, weapons, deposits); Uruguay 67 to 64 (prison guards,
state property); Dominican Republic 196 to 174 bills and 196 to 172 votes
(hospital resolutions, the surname Capellán, police custody); Honduras's
press 208 to 186 (policing, hospital funding); Nicaragua 13 to 12. Every
row lost was read and was noise. Mexico, Guatemala, Ecuador's bills and
the countries without a store were not measured.

### A free local model as judge, later (not installed)

If the deterministic filters stop being enough, a small open model run on
the Mac Mini would be a judge at zero API cost. Nothing below is built.

- **What it needs.** Ollama (`brew install ollama`, then `brew services
  start ollama`; it serves on `http://127.0.0.1:11434` and starts with the
  Mini) or llama.cpp's `llama-server`. A 7 to 9 billion parameter instruct
  model at 4-bit quantisation, good in Spanish: Qwen2.5 7B Instruct
  (Apache 2.0), Llama 3.1 8B Instruct (Meta's community licence) or Gemma
  2 9B. About 5 GB of disk and 6 to 8 GB of RAM while loaded, so a 16 GB
  Mini runs it beside everything else; an 8 GB Mini should use a 3 to 4
  billion parameter model (Qwen2.5 3B, Llama 3.2 3B) and expect weaker
  Spanish. `ollama pull qwen2.5:7b-instruct` once.
- **Expected speed** on Apple silicon: roughly 20 to 40 tokens a second
  generated and a few hundred read. A Latam item is about 300 tokens in
  and 60 out, so 2 to 5 seconds an item; a month's edition (100 to 200
  candidates) in 5 to 15 minutes, a weekly alert pass in a minute or two.
- **How it plugs in.** `src/triage.py` already takes an injectable
  transport: `score_live(items, transport=...)` builds the payload with the
  system prompt and the JSON contract and parses the reply with
  `_parse_reply`. A `local_transport(payload, api_key)` would post the same
  system prompt and items to Ollama's `/api/chat` (`format: "json"`,
  temperature 0, a fixed seed) and wrap the answer as
  `{"content": [{"type": "text", "text": ...}], "usage": {}}`; a
  `TRIAGE=local` mode in `triage.triage()` would select it, and
  `src/latam.score()` would pass `mode="local"` instead of `"stub"` when
  the Mini's server answers. The noise filters stay in front, so the model
  sees only what survives them; GitHub backups, with no model, fall back to
  the stub.
- **Risks.** Quality first: a small model over-flags or misses, and must
  be measured on a labelled set (the one above, and `docs/judge-eval.md`)
  before it changes what Chris sees; its score should order items and gate
  alerts, never delete from the edition. Malformed JSON: a batch that fails
  to parse falls back to the stub, as the live judge does. It runs on the
  Mini only, which must be awake and not busy clipping; the first load of
  the model takes 10 to 30 seconds. Results drift when the model is
  updated, so the model tag is pinned. It is still a judge: X16 deferred
  the judge, so switching it on is Chris's call.

## The free session judge for the editions and Latam (branch `editions-free-judge`)

Chris, 10 October 2026, approved: the free "session judge" built for the
Canadian provinces (Claude Code on the Mac Mini, signed in to his claude.ai
account, on the plan allowance; no API key, no per-call cost) is adopted for
the fifteen weekly country editions and the Latam monitor. **The paid API
judge stays off (X16).** The local-model idea above stays unbuilt.

- One generic queue for all sixteen, keyed by country code:
  `tools/edition_judge.py --queue-out / --queue-in` (src/session_queue.py's
  format, its own marker), scores in `edition_scores` (src/edition_judge.py),
  one digit 0-3 and a why-line per item, once ever, model
  `claude-code-session`. An item is offered only when its edition would show
  it (on our ground, not muted, not noise-filtered); a vote group once.
- In the editions: an unwatched item scored 0 leaves (counted under
  Coverage); the scores order the items; the lead is watched items, items
  scored 3, and items scored 2 with the minimum evidence; each judged item
  shows its score and why-line. Unscored items render as before.
- Latam alerts: watched items always alert. A tier-1 item that is not
  watched, once judged, alerts only at 2 or 3 (the judge's reading replaces
  the minimum-evidence rule); while the judge is running it is held for it
  (at most eight days, then it goes out unscored).
- Plan usage kept lean (the plan is shared with Chris's other scheduled
  jobs): one Mini job a week, `jobs/editions-session-judge.sh`, Sundays
  16:45 London, at most 100 items in sessions of 25, watched then tier 1
  then tier 2, newest first. Mini only, no GitHub workflow. Signed out or
  missing: a [gap] and a clean exit. `ANTHROPIC_API_KEY` is never passed.
- Editions already sent: rewritten in place (as the provinces judge does),
  with one short DM to Chris only when the scores changed what leads an
  edition already sent. See docs/mac-mini.md, "Editions session judge".

## The weekly country editions as built (branch `editions-core`)

- One framework, `src/country_edition.py`, renders a weekly edition per
  own-edition country from a small adapter (`src/editions/<cc>.py`, the
  interface in the module docstring); `tools/<cc>_monitor.py` is the entry
  point; the edition is the last step of `jobs/<cc>-weekly.sh` (Mini first,
  GitHub backup), DMed to Chris alone once a day and archived to
  `editions/<cc>-monitor-<date>.md`. Stub triage only (X16); no [ACT] items.
- The Latam noise filters are generalised into `src/noise.py`
  (`src/latam_noise.py` is now its Latam instance, behaviour unchanged);
  each edition reads `config/edition-noise-<cc>.yaml` and
  `config/edition-mute-<cc>.yaml`.
- Batch 1: Austria (Klub votes; member positions derived and labelled,
  X5), the Netherlands (votes only, NL3; derived positions on a show of
  hands, X5), Belgium (the full edition: BE6's votes-only step is
  superseded now the terms are approved), Poland (every deputy's position).
- Samples (SAMPLE, never sent), from the 9 October scoping stores
  reclassified under the current taxonomies: `editions/at-monitor-2026-07-10.md`
  (the Sterbeverfügung week: the week to 9 October held only questions),
  `editions/nl-monitor-2026-10-09.md`, `editions/be-monitor-2026-10-09.md`,
  `editions/pl-monitor-2026-10-09.md` (a month, since the week held only the
  alcohol-bill votes the noise rules leave out).
- Noise measured on those stores: Poland, 24 votes on the alcohol bills
  (druki 2007 and 2010, area 7 through "weryfikacj* wieku" and "radiofonii
  i telewizji" in the Sejm's summary) and 3 procedural votes left out; the
  Netherlands, one Defence workplace-conduct motion ("seksuele
  intimidatie"); Austria, the same question put to every ministry is
  folded into one entry (fourteen Pride Month answers); Belgium, nothing.
  A taxonomy-pl guard on "weryfikacj* wieku" (online company, not alcohol)
  would fix the Polish case at the source; the taxonomy is generated, so it
  is left for the next term-list round.

### Batch 2: Italy, Switzerland, France, Portugal (branch `editions-it-ch-fr-pt`)

- Adapters `src/editions/{it,ch,fr,pt}.py` on the framework unchanged;
  entry points `tools/{it,ch,fr,pt}_monitor.py`; the edition is the last
  step of `jobs/{it,ch,fr,pt}-weekly.sh` (Portugal's skips a backfill run,
  `PT_LEGISLATURE` set).
- Italy: bills of both chambers; Senate and Camera votes with every
  member's position and the group at the vote. Switzerland: businesses
  (German title, French when the German is "Titel folgt"), both councils'
  votes; the Nationalrat's tallies are counted from positions and no
  result is shown (it publishes none); the watchlist is re-keyed from the
  Geschaeftsnummer to the printed number. France: dossiers by their latest
  act (the store keeps no deposit date), scrutins with group split and
  mises au point counted, scheduled committee acts in the week ahead.
  Portugal: group sides as printed, named deputies as facts, member
  positions DERIVED and labelled (X5).
- FR4: no Journal officiel collector yet, so the France week ahead carries
  a standing "Aide a mourir: decrees to watch" note, read from a `decrees`
  list on the law's entry in `config/watchlist-fr.yaml` (hand-edited: the
  list is drawn from the text as first adopted and must be checked against
  the promulgated law).
- Samples (SAMPLE, never sent), 9 September to 9 October 2026, from the
  scoping raw archives replayed offline through the collectors (no
  network): Italy 13 items (1 left out), Switzerland 80 (2 left out),
  France 4 plus the FR4 note, Portugal 20. Noise measured there and over
  each whole store: Italy, a hunting-wardens' conscience bill and Holy See
  solar-farm agreements, plus quorum checks (an Italian "ordine del
  giorno" is a resolution, never procedure); Switzerland, animal welfare
  (ritual slaughter kept) and disability insurance by title, about 15
  tier-2 or single-term questions left for the mute list; France, the
  demande de suspension de seance; Portugal, requests to waive the final
  drafting.

## Not acted on

- U1 (Uruguay Ley 20.431 referendum): ignore.
- S1, S2 (Congreso Visible debug mode, DR Senate credentials): leave.

- **Campaign briefs language (10 October 2026):** briefs for the new countries are written in English, per brief rulebook rule 6, like the German briefs (`language: en` in `config/country-briefs.yaml`).
