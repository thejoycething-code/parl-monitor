# Canada: three more federal sources, scoped

Probed live on 2 October 2026 with the User-Agent "parl-monitor (CitizenGO
research)", about one request a second per host, robots.txt read first.
Read-only: nothing in the repo or the store was written. Store figures below
come from read-only queries (`mode=ro`). Probe files and throwaway parsers are
in `scratchpad/probe/`.

| # | Source | Format | Depth verified | Volume since 2010 | Build |
|---|---|---|---|---|---|
| 3 | Senate Debates | HTML per sitting | 40-3 (March 2010) | 1,173 sittings, ~350 MB | 1 session |
| 4 | House committee Evidence | **XML, the same schema as House Hansard** | 40-3 (April 2010) | ~11,000 meetings (all committees); ~3,400 (key 8) | 1.5 sessions |
| 4 | Senate committee transcripts | HTML | 41-2 (2013); 40-3 has none linked | ~40-80 meetings a session per committee | +0.5 session |
| 5 | Supreme Court judgments | JSON feed + HTML per judgment | 1970 onward in the year index | ~1,000 judgments, ~300 MB | 1 session |

## robots.txt, read first

- **sencanada.ca:** robots.txt is 3 bytes and empty. Nothing is disallowed.
- **ourcommons.ca:** it disallows `/Search/`, `/PublicationSearch/`,
  `/Embed/` and `/ParlDataWidgets/`. So the collector walks the meeting lists
  and **never uses the site's search**.
- **parl.ca:** it disallows only diplomacy search and the error pages.
- **decisions.scc-csc.ca:** it disallows two named items and the BUbiNG
  crawler. **scc-csc.ca** disallows `/cso-dce/` and two PDFs.
- **lop.parl.ca (ParlInfo):** robots.txt allows it, but the senators page
  returned **403** to our honest UA. Don't fight that.

---

## (3) Senate of Canada Debates

### Endpoints (verified)

- **Session index:** `sencanada.ca/en/in-the-chamber/debates/<P-S>`, one HTML
  page that links every sitting. **The hrefs use backslashes**
  (`/en\content\sen\chamber\451\debates\001db_2025-05-26-e`), so normalise
  them before use. Each index also carries a single forward-slash link to the
  latest sitting overall, which has to be dropped from the count.
- **Sitting:** `sencanada.ca/en/content/sen/chamber/<PS>/debates/<NNN>db_<YYYY-MM-DD>-e`
  (HTML). There is a PDF beside it at
  `/content/sen/chamber/<PS>/debates/pdf/<NNN>db_<date>-e.pdf`. No XML or
  JSON was found.
- **Soft-404 trap:** a wrong number/date pair (`070db_2026-06-04-e`) returns
  **200** with a 47 KB page that has an empty `<title>`. URLs must come from
  the session index and never be built from a number. A page with no
  `THE SENATE` heading, or no interventions, is a gap, never an empty sitting.

### Volume, counted from the session indexes

| 40-3 | 41-1 | 41-2 | 42-1 | 43-1 | 43-2 | 44-1 | 45-1 (to 29 Sept 2026) |
|---|---|---|---|---|---|---|---|
| 99 | 181 | 162 | 308 | 29 | 56 | 250 | 88 |

That is 1,173 sittings since March 2010, about 70 a year. Pages are 205 KB
(2010), 245 KB (2021) and 486 KB (4 June 2026), so a full backfill is about
350 MB. That is roughly 20-25 minutes at one request a second, fetched with
`archive=False` as `ca_hansard` does. The weekly load is 2-3 sittings.

### Data shape

- **Structure:** headings are `<h1>` (rubric: SENATORS' STATEMENTS, ORDERS OF
  THE DAY), `<h2>` (subject: "Criminal Code") and `<h3>` (stage: "Bill to
  Amend—Third Reading"). Paragraphs are `<p>`.
- **Speaker label:** a leading `<b>Label:</b>` opens each intervention. In
  2010 the `<b>` is wrapped in `<span lang="en-ca">`; the parser in
  `probe/senparse.py` handles both forms.
- **Time:** inline markers such as `(1500)` every ten minutes give a time
  column, as Hansard's `Timestamp` does.
- **The bill number is not in the headings.** It sits in the procedural "On
  the Order: … third reading of Bill C-7, An Act to amend the Criminal Code
  (medical assistance in dying), as amended", the same pattern
  `ca_hansard.subject_bill` already reads.

### Who spoke, and the mapping to `ca_senators`

**Label forms:**

- The first time a senator speaks in a sitting the label is
  `Hon. First [Middle] Last (role)`.
- After that it is `Senator Last`.
- Where two senators share a surname, an initial is added:
  `Senator K. Wells`, `Senator C. Deacon`.
- Chair and collective labels are counted, not stored: `The Hon. the
  Speaker [pro tempore]`, `Hon. Senators`, `Some Hon. Senators` and `An Hon.
  Senator`.
- **There is no id on the page.** Nothing links a speaker to
  `/en/senators/...`.

**Resolution:**

1. Match the folded "first last" against `ca_senators.name`, which holds
   "Last, First Middle".
2. Then resolve `Senator Last` (or `Senator K. Last`) within the sitting to
   the `Hon.` label already seen. This is the same learn-then-resolve pass
   `ca_hansard.store_sitting` makes.

**Measured against the store's 178 senators:**

| Sitting | `Hon.` labels resolved |
|---|---|
| 16 June 2010 | 10 of 21 |
| 17 Feb 2021 (C-7) | 21 of 21 |
| 4 June 2026 (C-9) | 33 of 33 |

The 2010 misses are all senators who left before 42-1: LeBreton, Comeau,
Murray, Dallaire, De Bané, Poulin, Pépin, Chaput, Fox, Smith and
Hervieux-Payette. **`ca_senators` is built from recorded votes, which the
Senate publishes only from 42-1 (Dec 2015).**

**No historical senator register was found:**

- The Senate's list partial
  (`/umbraco/surface/SenatorsAjax/GetSenators?displayFor=senatorslist&Lang=en`)
  returns 94 current senators keyed by slug, not by the vote id, and it
  ignores `parlsession`.
- A former senator's slug page returns 404 (`/en/senators/segal-hugh/`).
- ParlInfo returns 403.

**Proposal:**

- Store unresolved senators with `person_id` NULL and a `speaker_key`, the
  folded full name, so they stay consistent across sittings.
- **Never mint an id from a name.** None of them sits today, and the 5CA
  totals count sitting members only, so the sheets lose nothing.

### Matching, measured offline against `config/taxonomy.yaml` and `watchlist-ca.yaml`

| Sitting | Interventions | Chair / collective | On our ground, title as h2+h3 | Bill long title joined |
|---|---|---|---|---|
| 16 Jun 2010 | 94 | 16 | 1 | 9 (**8 were wrong, see below**) |
| 17 Feb 2021 (C-7 third reading) | 73 | 18 | 7 | 7 |
| 4 Jun 2026 (C-9 third reading) | 268 | 90 | 9 | **21** |

- **The Senate needs the bill's long title in the title passage.** "Criminal
  Code — Bill to Amend—Third Reading" says nothing about C-9. Joining the
  long title from `ca_bills` took the C-9 day from 9 to 21. `ca_senate.py`
  already does this join for vote titles.
- **Bill numbers repeat across sessions.** The probe joined by number alone,
  newest session first. It tagged a 2010 Museums Act debate as areas 6 and 7
  using a later session's bill with the same number. **Join on (parliament,
  session, number), never on number alone.**

### Proof: C-7, 17 February 2021

Third reading, 43-2 sitting 29
(`/en/content/sen/chamber/432/debates/029db_2021-02-17-e`). The order reads
"third reading of Bill C-7, An Act to amend the Criminal Code (medical
assistance in dying), as amended".

- **Hon. Donald Neil Plett (Leader of the Opposition)**, resolved to
  `Plett, Donald Neil` (C): "Bill C-7 is the result of the federal
  government choosing to cave in to the opinion of one judge in one province,
  who decided unilaterally to strike down legislation that had been
  extensively debated and passed by both houses of Parliament."
- **Hon. Tony Dean:** "Bill C-7 reaches back to the 2015 Supreme Court
  decision in Carter but also, as importantly, to the federal government's
  response to that decision which, I think it's fair to say, was both
  cautious and conservative."

On C-9 (4 June 2026, sitting 79), **Hon. David M. Wells** (resolved to
`Wells, David M.`, C) said: "I rise at third reading in my capacity as critic
of Bill C-9". **Hon. Yonah Martin** opened the same debate.

### How it fits

**`ca_speeches`, plus a `chamber` column (default 'commons').** Two reasons
not to reuse things blindly:

- **Do not put Senate sittings in `ca_sittings`.**
  `ca_hansard.next_sitting()` and `backfill()` take `MAX(number)` per
  parliament and session with no chamber filter. Senate sitting 79 of 45-1
  would move the House frontier. Use a sibling table, `ca_senate_sittings`,
  keyed by the URL's `NNNdb_date`.
- **`tools/ca_5ca.py` (line 299) reads every `ca_speeches` row with a
  `person_id` into the Commons sheets.** Without a chamber filter,
  `senator-…` rows would appear on Commons sheets. Add a Senate branch that
  lists speeches as evidence, "activity, not direction", exactly as the
  Commons does. **Speeches never place anyone.**

**Two more details:**

- `speech_id`: the page has no ids, so use `sen-<PS>-<NNN>-<seq>`.
- `ca_retag.py` already gates and retags `ca_speeches`, so Senate rows get
  retag for free if they share the table.

**Effort:** one session, about 5 hours, for the collector, tests (fixtures
from the three sittings above), the schema and the ca-weekly step. Then one
announced backfill of about 25 minutes. Speeches on our ground since 2010
are estimated at 3,000-6,000, from 1, 7 and 21 in the three sittings; that
is a rough figure.

**Risks:**

- HTML markup with two generations seen so far.
- The soft-404.
- Backslash hrefs.
- Pre-2015 identity.
- The bill-number join.

---

## (4) Committee evidence and reports

### House of Commons (and joint committees): the best source of the three

**Endpoints (verified):**

- **Meeting list per committee and session:**
  `ourcommons.ca/Committees/en/<ACR>/Meetings?parl=<P>&session=<S>`.
  - Joint committees live on **parl.ca**:
    `parl.ca/Committees/en/AMAD/Meetings?parl=44&session=1`. The ourcommons
    URL 404s for AMAD.
  - Each meeting block carries its date, its number and its **study titles**
    (`studies-activities-item`), with links to notice, evidence and minutes.
  - A meeting with no Evidence link is in camera (AMAD 12 and 14). That is
    not a gap.
- **Evidence page:** `…/DocumentViewer/en/<P-S>/<ACR>/meeting-<N>/evidence`
  (HTML, about 700 KB). It is the only place found that links the XML:
  `/Content/Committee/<PS>/<ACR>/Evidence/EV<pubid>/<ACR>EV<NN>-E.XML`.
  - Example: `/Content/Committee/441/AMAD/Evidence/EV11823690/AMADEV10-E.XML`,
    169 KB.
  - The EV id is not the meeting id, so a meeting costs **two fetches**, and
    the heavy one is the HTML.
- **Reports:** the committee's `Work?parl=&session=` page lists
  `DocumentViewer/en/<P-S>/<ACR>/report-<N>/` and government responses
  (`report-1/response-8512-441-56`). JUST 44-1 has 36 such links.
  - A report is paginated HTML (`page-ToC`, `page-102`…) plus a PDF:
    `/Content/Committee/441/AMAD/Reports/RP12234766/amadrp02/amadrp02-e.pdf`,
    which is AMAD's February 2023 *MAID in Canada: Choices for Canadians*.
  - The PDF is the body to match. pypdf is already pinned in ca-weekly.

**The XML is House Hansard's own schema.**
`ca_hansard.parse_sitting()` read both test files **unchanged**: AMAD 10 gave
162 interventions and the date 2022-05-30; JUST 40-3/11 gave 200 and
2010-04-13. Committee files leave `SubjectOfBusinessTitle` empty, so the
meeting list's study title must be passed in as the title passage. With
passage matching alone, AMAD 10 put 71 of 162 interventions on our ground.

**Depth:** the same XML is served for 40-3. JUST meeting 11, 13 April 2010,
is 145 KB.

**Volume, from the 44-1 meeting lists:**

| JUST | HESA | FEWO | ETHI | AMAD |
|---|---|---|---|---|
| 106 | 113 of 147 | 99 of 139 | 126 of 146 | 30 |

Figures are public meetings with evidence, of all meetings. The House has 26
committees, so:

- **All committees:** about 2,900 public meetings in a long Parliament, and
  about 11,000 since 2010.
- **Key eight (JUST, HESA, FEWO, ETHI, AMAD, SECU, HUMA, CHPC):** about
  3,400 meetings since 2010. At about 850 KB per meeting (both fetches)
  that is roughly 3 GB, and about 2 hours at 1 request a second.

**Recommendation: gate the fetch, then match.**

- Fetch every meeting of the key eight.
- **SDIR is a key committee since 2 October 2026** (Christopher: "add SDIR"). The international human rights subcommittee's hearings on persecution, Nigeria for example, match no taxonomy term in their study titles, so the title gate collected nothing from it. It is now read in full, weekly and in the backfill.
- For the other committees, fetch only meetings whose study title matches
  the taxonomy.

### Keeping witnesses out of a member's record: the XML says who is who

Each `<Affiliation>` carries a `Type` attribute. The codes below were
observed, not documented:

| Type | Seen on |
|---|---|
| **28** | **every witness**: Dr. Ramona Coelho, RCMP officers, NGO directors |
| 47, 40 | members, House and Senate (Cooper 47, Thériault 40; Mégie carried both) |
| 35 / 36 | The Chair / The Joint Chair (Hon. Yonah Martin) |
| 3 | a senator's fully labelled first intervention |

The rule:

- **Type 28 never gets a `person_id` and never enters `ca_speeches`.** It
  goes to a sibling table, `ca_testimony`, keyed by intervention id. That
  table holds the witness name and the organisation from the first label
  ("Dr. Ramona Coelho (Physician, As an Individual)"), plus text and areas.
  It becomes a witness index of who testified for or against, and it is
  never part of a member's record.
- Members resolve exactly as in Hansard: **riding** first ("Mr. Michael
  Cooper (St. Albert—Edmonton, CPC)"), then a unique name. Senators resolve
  by "(Senator, Province, group)" plus name against `ca_senators`.
- **Committee DbIds are not Hansard DbIds.** None of seven tested matched
  `ca_speaker_roles`.
- **A DbId is not one per person even within a file.** Mégie spoke as both
  228785 and 288386 in AMAD 10. Resolve by name per document, and keep any
  committee role memory separate from `ca_speaker_roles`.

**Measured attribution:**

- **AMAD 10:** 63 witness interventions, 42 chair, and 57 member, of which
  49 resolved. The 8 misses are all bare "Hon. Marie-Françoise Mégie", a
  senator, which a name lookup in `ca_senators` fixes.
- **JUST 40-3/11 (2010):** 88 witness, 28 chair, and 84 member, all 84
  resolved.

### Proof: AMAD meeting 10, 30 May 2022 (Statutory Review – Medical Assistance in Dying)

- **MP: Mr. Michael Cooper** (St. Albert—Edmonton, CPC), Type 47, resolved
  to PersonId 89219: "Dr. Coelho, can you elaborate a little more on the
  case of the first patient you cited, who suffered from a stroke and was
  granted medical assistance in dying under the Bill C‑14 regime, despite not
  having a terminal diagnosis as required by law under Bill C‑14?"
- **Witness: Dr. Ramona Coelho** (Physician, As an Individual), Type 28: "I
  warned that many injuries and illnesses are accompanied by transient
  suicidality that ends with adaptation and support, but which on average
  takes two years."

### Senate committees: LCJC (id 1011), RIDR and others

**Endpoints:**

- **Meetings and studies, per committee and session:**
  `sencanada.ca/umbraco/surface/CommitteesAjax/GetTablePartialView?tableName=Studies&committeeId=<id>&selectedSession=<P-S>&isCommitteeSpecific=true&Lang=en&p=<page>`.
  - It is an HTML partial: studies (each bill or order of reference), their
    meetings, the **witness list with title and organisation**, and links.
  - Use `p=2…` to page through. `PageSize=250` is accepted.
  - The links are:
    - minutes: `/en/content/sen/committee/<PS>/<acr>/<NN>mn-<id>-e`
    - **transcripts:** `/en/content/sen/committee/<PS>/<acr>/<NN>ev-<id>-e`
  - RIDR's committee id was not looked up; it is in the committee list
    partial (`CommitteesAjax/GetCommitteeListPartialView`).
- **Transcript HTML:** the shape is the same as the Debates.
  - Senators: `<b>Senator Batters:</b>`.
  - Witnesses and ministers: `<b>Mr. Lametti:</b>`, `<b>Dr. Dosani:</b>`.
  - Chair: `<b>The Chair:</b>`, named in the opening paragraph ("Senator
    Mobina S. B. Jaffer (Chair) in the chair").
  - In 2014 the tags are uppercase `<B>`/`<P>`.
- **The rule is simpler than the House's:** a label that starts "Senator" is
  a senator, "The Chair" is the named chair, and everything else is a witness
  or official.
- **Depth:**
  - Transcript links verified for 41-2 (28 in the first page), 42-1 (39) and
    43-2 (22: 17 with `PageSize=250` plus 5 on `p=2`).
  - The 40-3 study table lists meetings and witnesses but **no transcript
    links**. The older proceedings route was not found, so treat 2010-13 as
    unverified.

**Proof: LCJC on C-7, 1 February 2021** (`/432/lcjc/10ev-55128-e`):

- **Senator:** **Senator Batters**: "Minister Lametti, you provided our
  committee with a Charter analysis that justifies the Charter compliance and
  constitutionality of your mental illness exclusion in Bill C-7".
- **Witness:** **Dr. Naheed Dosani** (Palliative Care Physician): "I'm not
  convinced that we've collected data that describes the experience of those
  who experience poverty".

### How it fits

- **Speeches:** members' and senators' committee interventions go into
  `ca_speeches` with `chamber` and `forum='committee'`, plus `committee`
  (the acronym) and `meeting_key`. They are evidence in the 5CA, "COMMITTEE
  JUST 44-1/12: …", and **never placement**, like floor speeches.
- **Testimony:** witnesses go only into `ca_testimony`.
- **Meetings:** `ca_committee_meetings` (one row per meeting read, with its
  totals and an in-camera flag) gives the same "never read" vs "quiet"
  distinction as `ca_sittings`.
- **Reports:** go into `ca_committee_reports`, matched on the PDF body per
  passage, as Gazette regulations are.
- **Pattern:** the UK and devolved collectors count witnesses and skip them
  (`tools/sp_committees.py`: "Witnesses and officials … are counted and
  skipped"). Canada can do better, because Type 28 is explicit.

**Effort:**

| Part | Estimate |
|---|---|
| House evidence (list walk, two-fetch resolve, parse reuse, Type split, tests) | about 8 h |
| Reports (PDF) | about 2 h |
| Senate committees | about 4 h |
| **Total** | **about 2 sessions** |

Backfill: about 2 hours for the key eight.

**Risks:**

- The 700 KB DocumentViewer hop is most of the transfer.
- The Type codes are inferred, not documented, so a test should pin "28 →
  testimony".
- The Senate's ajax partial is an undocumented surface.
- Senate committee transcripts before 41-2 are unverified.
- Ministers appearing in Senate committees are labelled like witnesses.
- Robots forbids ourcommons search, so lists are the only way in.

---

## (5) Supreme Court of Canada judgments

### Endpoints (verified)

- **The feed:** `decisions.scc-csc.ca/scc-csc/scc-csc/en/json/rss.do`, a JSON
  Feed with 100 items: `id`, `title` ("Sinclair-Desgagné v. Canada (Chief
  Electoral Officer) - 2026 SCC 31 - 2026-09-18"), `url`, `date_published`,
  `date_modified`, and `content_text` holding the subject.
  - The XML twin is `…/scc-csc/en/rss.do`.
  - The feed lists **published *and updated*** documents: Ford v. Quebec
    (1988) appears beside 2026 SCC 31. Key on the item id and read an old
    one once.
  - The 26 Sept scope noted that the guessed RSS path 404s. These are the
    real ones, found via `/scc-csc/en/rss/index.do?iframe=true`.
- **Leave to appeal:** `…/scc-csc/scc-l-csc-a/en/json/rss.do` (100 items,
  "Granted" / "Dismissed"). The leave text names the lower-court judgment and
  carries no subject. This is the early-warning layer, like the German
  `de_courts` planned-decisions list.
- **Year index for the backfill:**
  `…/scc-csc/scc-csc/en/<YYYY>/nav_date.do?iframe=true&page=<n>`, 25 a page,
  reaching back to 1970. Each row has the title, neutral citation, SCR
  citation, date, subjects and a PDF link (`/scc-csc/scc-csc/en/<id>/1/document.do`).
  - 2015 has 66 judgments and 2018 has 59, so 2010-2026 is about 1,000.
- **Judgment page:** `…/en/item/<id>/index.do?iframe=true` (266-607 KB).
  - Metadata: Date, Neutral citation, Report, **Case number (docket)**,
    Judges, On appeal from, and Subjects (absent on TWU).
  - The full text includes the headnote ("Held: …"), the parties, **the
    interveners** and counsel.
- **Docket page:** `scc-csc.ca/cases-dossiers/search-recherche/<docket>/`.
  The old `dock-regi-eng.aspx?cas=` redirects here.
  - It holds the full list of proceedings, the parties and counsel, and the
    **Registrar's case summary** with its catchwords ("Charter of Rights -
    Right to life - … - Terminally ill patients seeking assistance to commit
    suicide").
  - That summary is the text to classify a **pending** case by when leave is
    granted.

### Proof

| Case | Lexum id | Citation | Docket | From | Areas, headnote only | Full text adds |
|---|---|---|---|---|---|---|
| Carter v. Canada (AG) | 14637 | 2015 SCC 5, [2015] 1 SCR 331, 2015-02-06 | 35591 | BC | **2** | 1 ("abortion" in cited precedent) |
| Canada (AG) v. Bedford | 13389 | 2013 SCC 72, [2013] 3 SCR 1101, 2013-12-20 | 34788 | ON | **7, 12** | 1 |
| LSBC v. Trinity Western University | 17140 (+17141 LSUC) | 2018 SCC 32, [2018] 2 SCR 293, 2018-06-15 | 37318 | BC | **7, 8** (+2 via "coercion", noise) | 6, 9 |

- **Titles alone match nothing.** All three are party names. The text is
  required, as `src/ingest/caselaw.py` found for the UK.
- **Match the headnote (text up to "Cases Cited") and the Registrar's
  summary, not the full text.** Full text drags in every precedent it cites.
- **Interveners are the prize.**
  - **Carter:** 25 interveners, among them the Evangelical Fellowship, the
    Catholic Civil Rights League, Christian Legal Fellowship, ARPA, the
    Euthanasia Prevention Coalition, and Dying With Dignity.
  - **TWU:** 24 interveners, among them the CCCB, the EFC, ARPA, Egale and
    the Canadian Secular Alliance.
  - They give an ally and opponent map per case. Store them as a list.

### Classification and the 5CA

- **Tables:** `ca_judgments` (id, citation, docket, date, court, title,
  subjects, judges, on_appeal_from, interveners JSON, headnote excerpt,
  areas, terms, tier, url) and `ca_leave` (docket, status, date,
  summary_areas).
- **The judge:** taxonomy hits get the `ca_triage`-style 0-3 score with a
  why-line, because a tier-2 match on "coercion" is exactly what a judge
  separates.
- **Context only. A judgment never places anyone and never enters a 5CA
  sheet.** At most, a stance file can cite it in a reading's `why` (C-7 cites
  Truchon, C-14 cites Carter).

### Other courts

- **Federal Court:** `decisions.fct-cf.gc.ca/fc-cf/decisions/en/rss.do`
  answers 200 with 100 items, mostly immigration (area 11, hidden).
  Low yield.
- **Federal Court of Appeal:** the guessed feed path 404s. Not found.
- **Provincial courts of appeal:** the only uniform route is the **CanLII
  API**, which returns 401 without a key. A key is free on request for
  non-commercial use. This matters because much of our ground is provincial:
  Saskatchewan's pronoun case, Alberta's gender laws, and conscience rules.
  Applying for a key is Christopher's call.

**Effort:** one session, about 5 hours.

- **Data:** the JSON feed weekly, the leave feed with docket summaries for
  grants, and the year-index backfill. The backfill is about 50 index pages
  plus about 1,000 item pages, roughly 300 MB and 20 minutes.
- **Judge:** scoring only taxonomy hits costs under $1.

**Risks:**

- Lexum's `iframe=true` content page is the parse target, and its markup is
  undocumented.
- The headnote boundary ("Cases Cited") may vary by era.
- Subjects are sometimes missing.
- Feed updates re-surface old judgments.

---

## Placement and order

**All three join `ca-weekly.yml`** after `ca_hansard`, each in its own try,
so that a failure is a gap and not a lost week. The order is
`ca_senate_debates`, `ca_committees`, `ca_courts`.

**The rules carried over:**

- **Backfills** are hand-dispatched, announced and paced, under the
  Bundestag rule.
- **One writer at a time** on the store.
- **The `parl-monitor-state` group**, with one pending slot, sizes every run.
- **`coverage.py` FEEDS/ONCE_EVER entries** are needed the day these
  collectors are scheduled: Senate sittings and committee meetings are
  write-once; judgments are a feed.

**Suggested order:**

1. **(4) House committee evidence.** It has the richest signal and reuses the
   Hansard parser.
2. **(3) Senate Debates.**
3. **(5) SCC.**
4. Then Senate committees.

**Questions for Christopher:**

- Key eight committees or all 26?
- CanLII key for provincial appeal courts?
- Should witness testimony feed any reader-facing index, or stay collected
  only?
