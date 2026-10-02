# Canada's provinces and territories: scoping the 13 legislatures

Probed live on 2 October 2026. This was read-only work: no repo file was edited, no store was touched and nothing was dispatched. The probe directories are `scratchpad/provprobe` (BC, AB, SK, ON, QC, NB), `scratchpad/provprobe-atl` (MB, NS, PE, NL) and `scratchpad/provprobe-terr` (YT, NT, NU). Every request used an honest User-Agent and was spaced at least 1.1 s apart per host; New Brunswick's 10-second crawl-delay was honoured.

**Where the probes came from.** All requests left from a Proton VPN exit in Dublin. Three blocks recorded below may belong to that IP and not to us: Nova Scotia (TCP reset), PEI (Radware CAPTCHA) and Yukon (Cloudflare challenge). **Re-test all three from a GitHub Actions runner before writing any of them off.**

**"Verified"** means fetched and parsed live today. Anything taken from search results or the Wayback Machine is labelled.

---

## The three findings that shape everything

1. **Recorded divisions with named members exist in 10 of the 13 legislatures, and we read them live in all 10.** Proof divisions on test-case bills were read in Alberta, Saskatchewan, Ontario, Quebec, New Brunswick, British Columbia and Manitoba (quoted below). The other three (Nova Scotia, PEI, Yukon) were unreachable from the probe IP.

2. **The English taxonomy matches 2 of 18 test-case titles.** I ran `src/filter.filter_item` with `config/taxonomy.yaml` and `config/watchlist-ca.yaml` on 18 test-case titles, in a scratch process with no database.
   - Only "The Abortion Protest Buffer Zone Act" (MB) and "Access to Abortion Services Act" (NL) matched area 1. "Gender Ideology and Child Protection Act" (BC) caught only "child protection", in area 6 at tier 2.
   - These all missed:
     - Alberta: "Health Statutes Amendment Act, 2024 (No. 2)", "Education Amendment Act, 2024", "Fairness and Safety in Sport Act";
     - Saskatchewan: "The Education (Parents' Bill of Rights) Amendment Act, 2023";
     - Ontario: Bill 77's "efforts to change sexual orientation or gender identity";
     - Quebec: "laicity of the State", "end-of-life care" and "soins de fin de vie";
     - New Brunswick: "Human Organ and Tissue Donation Act" and the Policy 713 motion.
   - Provincial titles are omnibus amendment titles that name a statute, not a subject. This is the Canadian federal lesson (C-34 "Digital Safety") several times over.
   - **Classifying on the bill text works.** Alberta Bill 26's PDF text matched area 3 at tier 1 on "gender dysphoria". It also matched area 13 on a passing "organ donation" reference, which is the Gazette lesson again: match **per passage**, never on the whole document.
   - **Conclusion:** provincial classification has to run on bill text (explanatory notes) and debate headings, plus a per-province watchlist of bill numbers and policy names (Policy 713, SOGI 123, "Parents' Bill of Rights"), plus the judge. Titles alone will miss nearly everything.

3. **Many of our test cases never had a recorded division**, so the 5CA has nothing to place for them:
   - Ontario Bill 77 (conversion therapy, 2015) passed third reading "Carried", by voice.
   - New Brunswick Bill 52 (Human Organ and Tissue Donation Act, 15 June 2023) passed by voice.
   - NL's Access to Abortion Services Act (2016) passed by voice.
   - Nova Scotia's 2018 and PEI's 2019 conversion-therapy bills are reported as unanimous (press only, not verified).

   A division exists only when the opposition stands to demand one. That is common in Alberta, Ontario, Quebec and BC, and rare in the Atlantic provinces and the territories. The edition should say "passed on voice, no member record" rather than show an empty 5CA.

---

## Summary table

Divisions per year are measured where a sample was taken and marked "est." otherwise. Difficulty runs from 1 (easy) to 5 (blocked or very hard); value for CitizenGO runs from 1 to 5.

| Legislature | Divisions with member votes? Format | Online back to | Bills | Hansard | Roster with party | Divisions per year | Difficulty | Value |
|---|---|---|---|---|---|---|---|---|
| **Alberta** | Yes. V&P PDF (surnames, riding where two members share a name) and Hansard PDF | Bills to 1906; Hansard to 1972; V&P per session (31-1 checked) | HTML page per bill, each stage marked "passed on division" with Hansard page numbers | PDF only | HTML, caucus per legislature | ~50 (31-1 index: 124 division refs) | 3 | **5** |
| **Saskatchewan** | Yes. Minutes HTML since the 30th Legislature (full names), PDF since 2003 (bilingual, two columns) | Minutes 2003 | Progress-of-bills PDF per session | PDF, plus HTML since at least 2023 | HTML, "Government/Opposition Caucus" | ~20 (20 in 65 sitting days, 30L2S) | 2 (3 for the PDF backfill) | **5** |
| **British Columbia** | Yes. Hansard HTML division lists, plus a **per-member Voting Records index** (HTML) | Voting index to 2019 at least; Hansard older | **JSON** `pdms/bills/progress-of-bills/<sessionId>` | HTML per sitting | **GraphQL API** (members, parties, parliaments) | ~120 (2025 session); 54+ in spring 2026 | 2 | 4 |
| **Manitoba** | Yes. V&P PDF, one name per line in capitals, riding where two members share a name | 1998 (36-4) | HTML index per session, plus a status PDF | HTML since 1958 | HTML table | ~48 (43-2, all 72 V&P read) | 2 | 4 |
| **Ontario** | Yes. V&P **HTML table**, one `<td>` per member (2022+); older text layout (2008, 2015) | V&P HTML 2008; Hansard HTML 1995 | HTML bill page with status and votes tabs | HTML, speaker in bold, no ids | HTML with party | ~100–150 (est. from a 10-day sample) | 2 | 3 |
| **New Brunswick** | Yes. Journals PDF, three columns ("Hon. Mr. Higgs", initials where needed), English and French files | Journals 1995 (53rd) | HTML bill page with timeline | PDF, bilingual two-column edition, current | HTML with party | ~25 (5 in 10 sampled sittings) | 3 | 4 |
| **Quebec** | Yes. Before 2025: Journal des débats HTML prose roll call (surname and riding). Since electronic voting (2025): **names only in the procès-verbal PDF annex**, with party | JD 1963+; vote register 42-1+ | HTML bill page in French and English with tallies per stage | JD HTML, French only | HTML with party | ~200+ (vote no. 139 by 1 Apr 2026) | 4 | 4 |
| **Newfoundland and Labrador** | Yes. Journals PDF, two columns, initial and surname | Daily files from the 45th GA | HTML progress of bills | Word-exported HTML; PDFs to 1909 | JS array with party | ~10 | 3 | 2 |
| **Nova Scotia** | Unverified (TCP reset to us). Wayback shows Hansard HTML YEAS/NAYS tables with full names | Hansard 56th–65th Assembly (Wayback) | Unverified | HTML (Wayback) | Unverified | Unknown | 4 (blocked) | 3 |
| **PEI** | Blocked (Radware CAPTCHA on inner pages) | peildo.ca has historical journals | Search app (POST) | Search app | Blocked | Unknown | 5 | 2 |
| **Yukon** | Blocked (Cloudflare managed challenge, even robots.txt) | Hansard 1978 (search only) | Unverified | PDF (search only) | Unverified | Unknown | 5 | 3 |
| **Northwest Territories** | Yes. Hansard HTML; members called **by constituency**. V&P are scans with no text layer | Hansard 2000 | HTML with stages | HTML, docx and PDF | HTML, **no parties** | ~30–60 (est.) | 2 | 2 |
| **Nunavut** | Yes but rare. Hansard PDF only, by surname | Hansard 2003 at least | HTML table, current session only | PDF in English and Inuktitut | HTML, **no parties** | 0–5 | 3 | 1 |

---

## Built

Nothing schedules these collectors and nothing outside `tools/prov_*.py` reads their tables. Run one province at a time, into a scratch store first:

    python3 tools/prov_collect.py --prov ab --session 31-1 --since 2024-10-28 --until 2024-12-05 --db /tmp/prov.db

**Live smoke runs (2 October 2026, one scratch store, from the probe IP):**

| Province | Window | Records read | Recorded divisions (tally ok) | Voice decisions | Votes (unresolved) | Bills (on our ground) | Gaps |
|---|---|---|---|---|---|---|---|
| Alberta 31-1 | 28 Oct–5 Dec 2024 | 19 V&P | 40 (40) | 36 | 2,789 (0) | 75, all texts read (6) | 0 |
| Saskatchewan 29-3 | October 2023 | 9 Minutes | 12 (12) | 0 | 550 (0) | 1 (1) | 0 |
| British Columbia 43-2 | 12–28 Feb 2026 | 12 transcripts | 5 (5) | 13 | 442 (0) | 46 incl. 2 unnumbered, 44 texts (3) | 0 |
| Manitoba 42-3 | 12–14 Oct 2021 | 3 V&P | 7 (7) | 2 | 359 (0) | 120, 119 texts (4) | 0 |
| Manitoba 43-2 | 26 May–2 Jun 2025 | 5 V&P | 13 (13) | 28 | 618 (0) | 87, 86 texts (2) | 0 |
| Ontario 43-1 | 3 Nov 2022 | 1 V&P | 4 (3, plus 1 totals only) | 5 | 327 (0) | 7 pages read (1) | 0 |
| Ontario 41-1 | 4 Jun 2015 | 1 V&P | 4 (4) | 21 | 346 (0) | 17 pages read (1) | 0 after the fix below |
| Ontario 44-1 | 17–27 Nov 2025 | 8 V&P | 19 (17, plus 2 totals only) | 14 | 1,830 (0) | 25 pages read (0) | 0 after the fix below |

- **Alberta:** 91 members with 116 dated terms; every bill-page "passed on division" stage matched a parsed division.
- **Saskatchewan:** 61 members from the day covers. Bill 137 has eleven divisions on our ground.
- **British Columbia:** 93 members. The whole session lists 73 transcripts (dry run).
- **Manitoba:** 56 members per day from the Hansard covers (85 across the two legislatures). Mark Wasyliw is NDP on 14 October 2021 and Independent on 2 June 2025: party at the vote is the day's.
- **Ontario:** 123 members from the 2022 Hansard list, 107 from 2015's, 124 from 2025's. Two first runs failed honestly and were fixed: the 2015 Hansard prints its member list ten pages from the end, not in the last six (0 members, so every 2015 division was a tally gap); and the late-2025 V&P prints every name twice (English and hidden French div) and drops the table under a nil list, so 7 of 9 divisions were refused by the tally check ('Allsopp Allsopp') and 4 were missed (caught by the "on the following division" count). No wrong position was stored either time.
- **5CA:** `tools/prov_5ca.py --all` wrote 4 Alberta, 1 Saskatchewan and 4 BC evidence sheets; on the Manitoba/Ontario store it wrote 1 Manitoba (area 1) and 3 Ontario sheets (areas 4, 5, 7), the Bill 77 sheet ending "Passed on voice, no member record: 2015-06-04 on-41-1/77 Third Reading", with nobody placed (the stance file is empty).

### Foundation (step 0)

- **Tables** (`src/prov_store.py`, in `db.TABLES`, created by `db.init_db`): `prov_members`, `prov_member_terms`, `prov_divisions`, `prov_votes`, `prov_bills`, `prov_sittings`, `prov_speeches`, keyed by `prov`.
  - The sighting column is `last_read`, not `last_seen`: `tests/test_coverage.py` would otherwise require a `tools/coverage.py` entry for a feed nothing schedules. Rename it when a workflow runs these.
  - `prov_divisions.kind` is `recorded` or `voice`. A voice decision has NULL totals, NULL `positions_ok` and no votes, so "passed on voice, no member record" can be said.
- **Name resolution** (`src/prov_names.py`): against the roster terms valid **on the day** of the division, unique-or-nothing. It handles surnames, ridings (wrapped or not), initials in both orders, honorifics, full names, accents and two-word surnames. An unresolved label is stored with a NULL member and its reason in `prov_votes.how`.
- **The tally check** (`prov_store.tally`): resolved names must account for the printed totals one member per label. Otherwise `positions_ok = 0`, a row in `gaps`, the sitting's status is `gap`, and the record is read again on the next run. Only `positions_ok = 1` places anyone.
  - It earned its keep on the first live run: a member-page parsing bug gave every Alberta member wrong dates, and all 40 divisions came back as gaps instead of 2,789 silently wrong positions.
- **Classification** (`src/prov_classify.py`, `config/watchlist-prov.yaml`): bill TEXT, per passage, with PDF line breaks reflowed and statute names masked. Watched bills are matched by KEY only. Measured terms the taxonomy lacks: preferred names and pronouns, parental notification, Policy 713, SOGI 123, "Parents' Bill of Rights", mixed-sex leagues, the s.33 formula "operate notwithstanding".
- **Runner** (`tools/prov_collect.py --prov <code>`): `--session`, `--since/--until`, `--limit` (records), `--budget-seconds`, `--dry-run`, `--refresh`, `--no-roster`, `--no-bills`. It honours robots.txt (a disallowed URL is a gap; a Crawl-delay raises the throttle), never goes below 1.1 s per host, and writes gaps through `db.record_gaps`. Exit 1 on any gap.
- **The 5CA** (`tools/prov_5ca.py --prov ab --area 3`, `config/prov_stance.yaml`): the mirror of `tools/ca_5ca.py`.
  - The stance file ships EMPTY, so every provincial sheet is an evidence list. A reading starts `draft: true` and places nobody until that line is deleted.
  - Only a division whose tally check passed can place anyone. An untrusted division is named at the foot of the sheet and its positions are never shown.
  - Voice decisions on the area are listed as "Passed on voice, no member record".
  - NWT and Nunavut are refused, because they are consensus legislatures.
  - The suggested first readings to draft are listed in the stance file's header.

### Alberta (step 1): `src/ingest/prov_ab.py`

- **What it does:**
  - **Roster:** the roster listing for the legislature, then every member's information page. Terms are the dated party affiliations intersected with each spell of service, so `party_at_vote` is the party on the day. Pete Guthrie's four parties in 2025 are four terms.
  - **Bills:** the session's bills listing, every bill page (stages, dates, "passed" or "passed on division", sponsor by mid) and every bill-text PDF, classified per passage.
  - **Voice decisions:** a stage marked plain "passed" is stored as a voice decision.
  - **Divisions:** Votes and Proceedings PDFs, file names taken from the session listing (backslashes turned, nothing constructed). Divisions are parsed with question, stage, bill, the record's own result words and printed totals.
  - **Cross-check:** every "passed on division" stage on a day read must match a recorded division on that bill, or it is a gap.
- **Proof reproduced:** on 3 December 2024, third readings of Bill 26 (47–35, area 3), Bill 27 (47–33, area 6) and Bill 29 (47–33, area 5) all had their tallies matched. Smith and LaGrange voted Yea; Notley and Gray voted Nay. Party at the vote was United Conservative or Alberta NDP.
- **Known limits:**
  - Hansard (speeches) is not read.
  - The V&P parser knows the 31st-Legislature layout; older layouts are untested and will show up as tally gaps, not wrong votes.
  - A division's bill is the last bill named before it. Committee of the Whole sittings that take several bills together could attach a division to the wrong one.
  - The taxonomy's tier-1 "named person" (added for Holyrood) tags Alberta's Professional Governance Act (Bill 40) as area 6. That is a false positive, and the fix is a taxonomy decision.

### Saskatchewan (step 2): `src/ingest/prov_sk.py`

- **What it does:**
  - **Listing:** the Legislative Meeting Archive, filtered to the Assembly and the date window. It gives each day's Minutes (PDF, plus HTML from the 30th Legislature) and Debates, with their real names. Those names cover both path roots, both date formats, the "Revised" suffixes and the prorogation day that carries Minutes for two sessions.
  - **Roster, dated to the day:** for every day with a recorded division, the second page of that day's Hansard PDF, which lists every member with riding and party *as at that sitting*, plus the standings. Each term covers exactly the days it was seen on, and the standings are the roster's own tally check.
  - **Minutes:** the 30L HTML tables (full names) and the 29L bilingual PDFs (surnames, ridings wrapping across lines). "It was agreed to and the said bill was accordingly read a second time" is stored as a voice decision.
- **Proof reproduced:** Bill 137 third reading on 20 October 2023, 40–12, tally matched. Moe (SP) voted Yea and Beck (NDP) voted Nay. Both Harrisons, both McLeods, both Youngs and both Rosses were told apart by riding.
  - The live run of October 2023 also read first reading (12 Oct, 37–12), second reading (19 Oct, 37–11) and seven Committee-of-the-Whole clause and amendment divisions on the same bill. All tallies matched.
- **Known limits:**
  - Bill text is not read. There is no per-bill page; the bill text is on publications.saskatchewan.ca and progress-of-bills is a session PDF. Bills are rows made from the Minutes' own "Bill No. N — title" lines, classified on title, terms and key.
  - Stage is best-effort from headings and "be now read a … time".
  - Hansard speeches are not read.
  - Without `--since`, a run reads the last 60 days and says so.

### British Columbia (step 3): `src/ingest/prov_bc.py`

- **What it does:**
  - **Sessions:** from the LIMS GraphQL API (POST only). `43-2` becomes id 206 and path code `43rd2nd`.
  - **Roster:** `allMemberParliaments`, with by-election and resignation dates as term bounds.
  - **Bills:** the progress-of-bills JSON, which gives reading dates, sponsor memberId and the text-file paths. Texts are served under `lims.leg.bc.ca/pdms` and classified per passage.
    - The trap is guarded: a reply whose file paths do not name the session's code (an unknown key answers 2006 data) is refused as a gap.
  - **Transcripts:** the House files in the session's debates JSON listing.
  - **Divisions:** each `DivisionTable` in a transcript, with the Speaker's question, the StyleLine result, the Subject-Heading and the debate passages under it, all used for classification.
  - **Unnumbered bills:** a bill refused first reading is stored from the transcript as `bc-<leg>-<sess>/x-<slug>`.
  - **Voice decisions:** a reading date on a day whose transcripts were ALL read, with no recorded division on that bill and stage, is stored as a voice decision.
- **Proof reproduced:** the Gender Ideology and Child Protection Act was refused first reading on 19 February 2026, 38–49, tally matched. Rustad, Armstrong and Brodie voted Yea; Eby, Dix and Sharma voted Nay. The two Neufelds and two Andersons were told apart by initial. The bill is stored unnumbered with areas 3 and 6.
- **Known limits:**
  - **Party is NOT stored at the vote for BC.** The API has one party per member per parliament and no dates. Armstrong and Brodie, who left the Conservative caucus in 2025, show Independent for the whole parliament, so `party_dated = 0` and `party_at_vote` stays NULL.
    - A dated source is needed: the caucus history, or the per-member Voting Records index read against a dated caucus list.
  - The per-member Voting Records index (`Index/43rd2nd/2026-Votes?.htm`) is not read. It would give a second, independent tally check and each vote's stage label.
  - Hansard speeches are not stored.

### Manitoba (step 4): `src/ingest/prov_mb.py`

Collected on Christopher's decision of 2 October 2026 (see "Decisions"). The collector reads gov.mb.ca's robots.txt on every run with `src/prov_fetch.Robots`: the named AI-crawler groups do not name our agent, and every `*` rule is obeyed. If Manitoba names us there, every fetch becomes a gap. If Manitoba asks us to stop, we stop.

- **What it does:**
  - **Listings, never constructed:** `business/votes_proceedings.html` gives each session's V&P calendar, `hansard/hansard_archive.html` each Hansard calendar, and `web2.gov.mb.ca/bills/sess/index.php` each bills page. A V&P link with no day number (42-3 repeats `votes_029` blank in the 6 October cell) is dropped when the file is listed under its day. The PDF's own printed date is the record's date.
  - **Roster, dated to the day:** the second page of each division day's Hansard PDF lists the whole House as at that sitting ("COX, Cathy, Hon. Kildonan-River East PC", "Vacant Fort Whyte"). Terms cover exactly the days seen, as for Saskatchewan. Party at the vote is a fact of the day.
  - **Divisions:** V&P PDFs, YEA (42nd Legislature) or AYE (43rd), one capitalised name per line, the riding only where two share a surname ("SMITH (Lagimodière)"), the printed total on the last name's line. A second check counts "on the following division" in the text: a division the parser missed is a gap.
  - **Voice:** "It was agreed to." with "The Bill was accordingly read a Second Time…" or "…concurred in, read a Third Time and passed", "on division" (dissent noted, no names), and the day's first-reading list.
  - **Bills:** every bill's HTML text from the session's bills page, classified per passage.
- **Proof reproduced live:** Bill 207, The Abortion Protest Buffer Zone Act, second reading on 14 October 2021, negatived 20–30, tally matched. Fontaine, Kinew and Asagwara (NDP) voted Yea; Cox, Cullen and Pedersen (PC) voted Nay. Smith (Lagimodière) was told from Bernadette Smith by riding. Bill 207's text matches area 1 on its own. Bill 43 (gender expression) third reading 33–16 on 2 June 2025 also tallied; it is caught only by its watchlist key, because the taxonomy has no "gender expression".
- **Known limits:**
  - Hansard speeches are not read, nor `billstatus.pdf`: stage dates come only from the V&P read.
  - Hansard lags the V&P by days. A division day with no Hansard yet is a gap and is read again next run.
  - The cover parser assumes one given name before the constituency when "Hon." is absent (true for every member of the 42nd and 43rd). A two-word given name would make that member's riding unmatchable: a gap, never a wrong member.
  - V&P layouts before the 42nd Legislature are untested; a change shows as a tally or count gap.
  - Taxonomy false positive: 42-3 Bill 44 (Employment Standards Code, organ-donor leave) is tagged area 13 on "organ donation".

### Ontario (step 5): `src/ingest/prov_on.py`

- **Access:** the repo's standard UA passes Akamai, and nothing else is used. robots.txt's second `User-agent: *` group says `Disallow: /*?`, which `urllib.robotparser` cannot read: it ignores every `*` group after the first and treats `*` literally. `src/prov_fetch.Robots` (RFC 9309: merged groups, `*` and `$`, longest match) replaces it for every province, and no query-string URL is ever requested. A test asserts that.
- **What it does:**
  - **Sittings:** house-documents → the session page → each day's hub (`…/<date>/hansard`). The hub names the day's V&P and Hansard PDF.
  - **Roster, dated to the day:** the member list in the back of the day's Hansard PDF, read by column position (`prov_fetch.pdf_fragments`), because ridings wrap and carry a French name after " / ". Terms cover exactly the days seen.
  - **Divisions:** three V&P layouts, all tested:
    - since 2022, bilingual event tables with `divisionHeader` / `votesList`;
    - since late 2025, each name doubled in English and hidden French divs, and a nil list printed as a header with no table;
    - before 2022 (2015 checked), one table of English/French cells, with "AYES / POUR - 95" and "… - Continued".
    - The printed totals and the "on the following division" count are both checked.
  - **Totals only:** a dilatory motion's division ("Carried on the following division – Ayes 74, Nays 30") prints no names. It is stored recorded with `positions_ok = 0` and a "totals only" note. It is not a gap, because no re-read can resolve it. `prov_store.summary` counts these apart from gaps.
  - **Voice:** "Carried." / "Lost." after a reading, and the day's first-, second- and third-reading lists.
  - **Bills:** only the bill pages (about 750 KB each, text included) that the window's records or the watchlist name.
- **Proofs reproduced live:**
  - **Bill 28, 3 November 2022.** Time allocation 78–33, second reading 76–32 and third reading 74–34, every tally matched. At third reading Lecce (PC) voted Yea; Fife (NDP) and Schreiner (GRN) voted Nay. Both Fords, both Chos, the Joneses and four Smiths were told apart by riding. The adjournment-of-debate division on Bill 26 was stored as totals only.
  - **Bill 77, 4 June 2015.** Third reading is stored as a voice decision ("Carried.") with no member record. The same day's four recorded divisions all tallied against the 2015 Hansard list. Bill 77's text matches area 4 on "efforts to change sexual orientation or gender identity".
- **Known limits:**
  - Hansard speeches are not read, so the names behind a totals-only division are not collected.
  - One URL is constructed: the session's bills listing (`/en/legislative-business/bills/parliament-N/session-M`). No index links past sessions' listings except from inside a bill. A wrong guess is a 404 and a gap.
  - A sitting costs the hub page (about 300 KB) plus the V&P (150–200 KB), and the Hansard PDF (650 KB to 1.3 MB) on division days.
  - Bill 28's area 7 is a draft judgement (see "Decisions needed" below).

### Decisions needed (Manitoba and Ontario build, 2 October 2026)

- **Ontario Bill 28: area 7 or no area?** It is a labour bill that invoked s.33 over Charter ss. 2, 7 and 15. The watchlist gives it area 7 (civil liberties) as a draft, so its three divisions appear on an area-7 evidence sheet.
- **Manitoba Bill 43 (gender expression):** area 5 is from the scope. The taxonomy has no "gender expression", so similar bills elsewhere will be missed. Adding the term is a taxonomy-versioning call.
- **Schedule:** none of the five provincial collectors is scheduled. Wiring one into a workflow means the `last_read` → `last_seen` rename and a `tools/coverage.py` entry.

---

## Per-legislature detail

### Alberta (assembly.ab.ca): value 5, difficulty 3

- **robots.txt:** only a sitemap line; nothing disallowed. No WAF.
- **Votes and Proceedings (the best division source):**
  - Path pattern: `https://docs.assembly.ab.ca/LADDAR_files/docs/houserecords/vp/legislature_31/session_1/20241203_1200_01_vp.pdf`.
  - The time token is **always `_1200_` for V&P**. Hansard files use the real sitting time (`_1330_`, `_1000_`, `_1930_`), so the guessed `20241203_1330_01_vp.pdf` 404s. **Take file names from the listing pages. Never construct them.** The listing hrefs use Windows backslashes.
  - Format: "the names being called for were taken as follows: For the amendment: 35", then three columns of surnames. A riding is added on the next line where two members share a name ("Sigurdson (Highwood)", "Wright (Cypress-Medicine Hat)"). The printed totals give a free tally check.
- **Hansard:** `https://docs.assembly.ab.ca/LADDAR_files/docs/hansards/han/legislature_31/session_1/20241203_1330_01_han.pdf`, PDF only, back to the 17th Legislature (1972).
  - Divisions are repeated here as "For the motion: … Against the motion: … Totals: For – 47 Against – 35", disambiguated by initials ("Sigurdson, L." / "Sigurdson, R.J.").
  - Three-column surnames run together when a surname has two words ("Calahoo Stonehouse Haji Sabir"), so names must be matched greedily against the roster, not split on spaces.
- **PROOF: all three 2024 test bills reached third reading on division on 3 December 2024.**
  - Bill 26, Health Statutes Amendment Act, 2024 (No. 2), puberty blockers. The hoist amendment HA1 failed 35–47; third reading carried **47–35**.
    - For: Amery, LaGrange, Smith.
    - Against: Notley, Gray, Hoffman.
  - Bill 27, Education Amendment Act, 2024 (pronouns, parental notification). Third reading carried **47–33**.
    - For: Nicolaides.
    - Against: Pancholi, Shepherd.
  - Bill 29, Fairness and Safety in Sport Act. Third reading carried **47–33**.
    - For: Schow.
    - Against: Eggen, Irwin.
  - Sources: V&P above and Hansard pp. 2299–2316.
- **Bills:** `https://www.assembly.ab.ca/assembly-business/bills/bills-by-legislature?legl=31&session=1` (back to legl=1, 1906).
  - Bill page: `.../bills/bill?billinfoid=12049&from=bills`. It shows every stage with date, "passed on division", the Hansard page range and a deep link (`...han.pdf#page=17`). **That flag is a free index of which stages had divisions.**
  - Status reports: `/LAO/Bills/bsr31-1.pdf`.
  - Bill text PDF: `.../docs/bills/bill/legislature_31/session_1/20230530_bill-026.pdf`.
- **Roster:** `https://www.assembly.ab.ca/members/members-of-the-legislative-assembly`, an HTML table of name, caucus (UC / NDP) and constituency, with a legislature selector back to 1906. Member pages are `member-information?mid=0984&legl=31`.
- **Volume:** the 31-1 journals index (`.../indexes/journals/ji/legislature_31/session_1/20230530_1200_01_ji.pdf`) has 124 lines mentioning a division. Most are opposition hoist and reasoned amendments. That suggests about 50 divisions a year, with six on one afternoon on 3 December 2024.
- **Also available:** written questions, motions for returns, petitions and order papers (HTML listing pages).
- **Effort:** 10–12 h for divisions (V&P), bills and roster; +6 h for Hansard speeches (PDF, labels like "Mr. Nicolaides:").

### Saskatchewan (legassembly.sk.ca): value 5, difficulty 2 (3 for the backfill)

- **robots.txt:** www returns 404, so there are no rules. The document host `docs.legassembly.sk.ca` is an Azure blob with no robots file. No WAF.
- **Minutes (Votes):**
  - PDF since March 2003. **HTML since the 30th Legislature**, e.g. `https://docs.legassembly.sk.ca/legdocs/Assembly/Minutes/30L2S/20251023Minutes-HTML.htm`.
  - The HTML is Word-exported and windows-1252 encoded. Each "recorded division" is a table with one `<p>` per member and **full names** ("Scott Moe", "Carla Beck").
  - Path quirks:
    - two roots: `legdocs/Assembly/` and `legdocs/Legislative%20Assembly/`;
    - date formats: YYMMDD in 29L, YYYYMMDD in 30L;
    - HTML file names vary: `-HTML.htm` and `HTML.htm` both occur.
  - The listing comes from `/legislative-business/archive/?page=N` (about 350 pages).
- **PROOF: Bill 137, The Education (Parents' Bill of Rights) Amendment Act, 2023**, third reading 20 October 2023, carried **40–12**.
  - Source: `https://docs.legassembly.sk.ca/legdocs/Assembly/Minutes/29L3S/231020Minutes.pdf`.
  - YEAS: Moe, McMorris, Cockrill.
  - NAYS: Beck, Nippi-Albright, Wotherspoon.
  - The 29L PDF is bilingual and two-column, with ridings that wrap ("Harrison (Meadow Lake)"). Second reading on 19 October was 37–11 (from search results; not re-fetched).
- **Hansard:** `.../legdocs/Assembly/Debates/29L3S/20231020Debates.pdf`, plus `...DebatesHTML.htm`, which exists back to 29L3S at least. Speaker labels look like "Hon. Mr. Cockrill: —".
- **Bills:** progress-of-bills PDFs per session from 1998 (`/media/jquc1jcw/progress-of-bills-29-4.pdf`). There is no per-bill HTML page.
- **Roster:** `https://www.legassembly.sk.ca/mlas/` labels members "Government Caucus" or "Opposition Caucus", not by party. Map GC to the Saskatchewan Party and OC to the NDP, per legislature.
- **Volume:** 20 recorded divisions in 65 sitting days (30L2S, October 2025 to May 2026); all 65 HTML minutes were read.
- **Effort:** 8–10 h for HTML minutes, bills and roster; +4–6 h for the 29L PDF backfill (Bill 137 lives there); +4 h for Hansard HTML.

### British Columbia (leg.bc.ca / lims.leg.bc.ca): value 4, difficulty 2

- **robots.txt:** www is a standard Drupal file (disallows /search/, /admin/). `lims.leg.bc.ca` and `api.lims.leg.bc.ca` have none (404). No WAF.
- **The best structured source of the thirteen:**
  - **Voting Records by Member:** `https://lims.leg.bc.ca/hdms/file/Index/43rd2nd/2026-Votesr.htm` (one page per letter). Each member's every standing vote is listed by bill and stage ("1R, Yea"), linked to a Hansard timestamp anchor (`20260219am-Hansard-n119.html#119B:1030`). Checked back to 41st 4th (2019); the 2010 path 404s.
  - **Hansard HTML:** `https://lims.leg.bc.ca/hdms/file/Debates/43rd2nd/20260219am-Hansard-n119.html`. Each division appears as "YEAS — 38 … NAYS — 49" with surnames, initials where two share a name ("L. Neufeld", "K. Neufeld").
  - **Bills JSON:** `https://lims.leg.bc.ca/pdms/bills/progress-of-bills/206`, keyed by **session id** (206 is 43-2). It gives every reading date, sponsor memberId and file paths.
    - Trap: a session code such as `43rd2nd` silently returns another session (2006 data).
  - **Members GraphQL:** `https://api.lims.leg.bc.ca/graphql` takes POST only (PostGraphile). It has `allMembers`, `allMemberParliaments` (party and constituency per parliament), `allParties` and `allSessions`. I made two small read queries.
- **PROOF:** Gender Ideology and Child Protection Act (Tara Armstrong, Conservative). First reading was **negatived 38–49** on 19 February 2026 (Hansard n119, 10:25 a.m.).
  - YEAS: Rustad, Armstrong, Brodie.
  - NAYS: Eby, Dix, Sharma.
  - **Trap:** a bill refused first reading gets no number, so it is **absent from the bills JSON**. Only Hansard and the voting index carry it. The 2026 index also shows a divided first reading of a "Human Rights Code Repeal Act" (126B:1035) and Bill 12 Safe Access to Schools.
  - BC "SOGI" itself was a policy, not a bill; no SOGI division was found.
- **Volume:** about 119 distinct divisions in the 2025 session and 54 or more by spring 2026. With a Conservative Official Opposition, divisions on our ground are now frequent.
- **Effort:** 8–10 h for divisions, bills and roster; +4 h for Hansard.

### Manitoba (gov.mb.ca/legislature): value 4, difficulty 2

- **Divisions:** V&P PDFs, e.g. `https://www.gov.mb.ca/legislature/business/42nd/3rd/votes_082.pdf`, with the session index at `business/43rd/43rd_2nd.html`, back to 36-4 (about 1998).
  - The marker phrase is "on the following division:". Names are listed one per line in capitals ("SMITH (Lagimodière)"), and the totals are printed.
  - pypdf extracts the text cleanly.
- **PROOF:** I re-verified this myself.
  - Bill 207, The Abortion Protest Buffer Zone Act, second reading on 14 October 2021, was **negatived 20–30**.
    - YEA: FONTAINE, KINEW, ASAGWARA.
    - NAY: COX, CULLEN, PEDERSEN.
  - Bill 43 (Human Rights Code, adding "gender expression") passed third reading 33–16 on 2 June 2025 (`43rd/2nd/votes_063.pdf`; the probe agent read it).
- **Bills:** `https://web2.gov.mb.ca/bills/43-2/index.php`, from 37-1 onward. Stage dates are only in `business/billstatus.pdf`.
- **Hansard:** HTML, e.g. `hansard/43rd_3rd/vol_60/h60.html`, back to 1958. Speakers are labelled with full name and riding.
- **Roster:** `legislature/members/mla_list_alphabetical.html` (NDP / PC).
- **Volume:** 48 divisions across all 72 V&P of 43-2.
- **Policy flag:** gov.mb.ca's robots.txt gives `Disallow: /` to GPTBot, ClaudeBot, anthropic-ai, Claude-Web, CCBot and others. Our UA is not on the list and the `*` rules allow /legislature/. But the province has said plainly that it objects to AI crawlers, and our pipeline uses Claude to judge items. **Christopher should decide this before we build.** The ask-permission route is the Clerk's office. *(Decided 2 October 2026: collect. See "Decisions" and the Manitoba "Built" notes.)*
- **Effort:** 12–16 h for divisions, bills and roster; +6 h for Hansard.

### Ontario (ola.org): value 3, difficulty 2

- **WAF (Akamai):** it 403s a bot UA without a contact.
  - `parl-monitor (CitizenGO research)` and `parl-monitor/1.0 (...)` were refused; so was `(contact: research)`.
  - A UA carrying a URL or email passes: `parl-monitor (CitizenGO research; +https://citizengo.org)`, and the repo's standard `CitizenGO-ParlMonitor/1.0 (contact: …)` from `src/http.py`. So the existing HttpClient works as it is.
  - It also 403'd the plain UA on robots.txt itself.
- **robots.txt: `Disallow: /*?`**. Query-string URLs are off-limits; every page needed has a path URL. `/search/` and some 42nd Parliament committee pages are also disallowed.
- **V&P:** `https://www.ola.org/en/legislative-business/house-documents/parliament-43/session-1/2022-11-03/votes-proceedings`.
  - Since about 2022 each division is `<h5 class="divisionHeader">Ayes/pour (74)</h5>` followed by `<table class="votesList">`, one surname per `<td>` and a riding where two members share a name ("Cho (Willowdale)", "Ford (Etobicoke North)").
  - Older pages (2008, 2015) carry "AYES / POUR - 95" as text, sometimes split with "AYES / POUR - Continued". That needs a second parser.
  - A 1995 V&P page exists but holds no V&P text.
- **PROOF:** Bill 28, Keeping Students in Class Act, 2022 (notwithstanding clause), 3 November 2022.
  - Time allocation carried 78–33. Third reading carried **74–34**.
  - Ayes: Anand, Lecce, Ford (Etobicoke North).
  - Nays: Andrew, Fife, Schreiner.
  - **Bill 77 (2015 conversion therapy) had no recorded division.** Third reading "Carried. Adoptée." on 4 June 2015 (`parliament-41/session-1/2015-06-04/votes-proceedings`).
- **Hansard:** `.../2025-11-24/hansard`, HTML with `<p class="speakerStart"><strong>Mr. Brian Saunderson:</strong>`. Names only, no member ids. Back to parliament-36 (1995) at least.
- **Bills:** `/en/legislative-business/bills/parliament-43/session-1/bill-28` with `/status` (each stage, "Carried on division", principal debaters with ridings).
- **Roster:** `/en/members/current` (124 MPPs, party, riding). Past MPPs have pages too. Drupal `/jsonapi` is 404, so there is no API.
- **Volume:** about 13 divisions in 10 sampled sittings out of the 81 in 44-1, so roughly 100–150 a year.
- **Value is 3, not higher**, because few recent Ontario divisions are on our ground. Bill 28 is a labour bill whose relevance is the notwithstanding clause.
- **Effort:** 8–10 h for divisions, bills and roster (two V&P layouts); +5 h for Hansard.

### Quebec (assnat.qc.ca): value 4, difficulty 4

- **robots.txt** disallows `/json/`, `/scripts/`, `/fr/rss/`, `/fr/recherche/`, `/media/` (lower case) and six specific `/Media/Process.aspx` documents. No WAF.
- **The vote register** (`/fr/travaux-parlementaires/registre-des-votes/index.html`) is an ASP.NET postback page whose results load from `/json/`, which robots.txt **disallows**. It is off-limits.
- **Before electronic voting**, the Journal des débats prints every roll call in prose with surname and riding:
  - Source: `https://www.assnat.qc.ca/fr/travaux-parlementaires/assemblee-nationale/42-1/journal-debats/20190616/247401.html` (843 KB for one sitting).
  - **PROOF: Bill 21, Loi sur la laïcité de l'État**, adoption on 16 June 2019, **Pour 73 / Contre 35**.
    - Pour: M. Legault (L'Assomption), M. Jolin-Barrette (Borduas), Mme Hivon (Joliette) (PQ).
    - Contre: M. Arcand (Mont-Royal—Outremont), M. Nadeau-Dubois (Gouin).
- **Since electronic voting (in use by 30 October 2025)**, the Journal prints totals only ("Pour : 70 Contre : 27"). The names are in the **procès-verbal PDF annex**:
  - The PDF is served at `/Media/Process.aspx?MediaId=ANQ.Vigie.Bll.DocumentGenerique_220051&process=Default&token=…`, linked from the session's sitting index `/fr/travaux-parlementaires/assemblee-nationale/43-2/index.html`. The ids cannot be guessed, so the sitting index must be scraped.
  - The annex helpfully gives **party at the vote**: "(Vote n° 139) POUR - 68 Allaire (CAQ) … Dubé (IND) … CONTRE - 31 Arseneau (PQ) Cliche-Rivard (QS) Kelley (PLQ) … ABSTENTIONS - 1 Dufour (IND) (Abitibi-Est)".
  - It is four columns, and riding lines wrap under the wrong column, so parsing needs a layout-aware pass.
  - **PROOF (format):** Bill 1, Loi constitutionnelle de 2025 sur le Québec, adoption in principle 68–31–1 (PV of 1 April 2026).
  - **Bill 94** (laïcité in education) passed 70–27 on 30 October 2025. The tally is verified from the Journal; the names would come from that day's PV, which I did not fetch.
- **Bills:** `/fr/travaux-parlementaires/projets-loi/projet-loi-21-42-1.html`, with an **English version at `/en/...`** ("An Act respecting the laicity of the State"). Each stage shows its tally ("Vote : Pour 73, Contre 35, Abstention 0").
  - Bill 52 (end-of-life care, 2013): principle 84–26.
  - Bill 11 (MAID expansion, 2023): 107–0 at principle, 103–2–1 at adoption.
- **Roster:** `/fr/deputes/index.html` (CAQ / PLQ / PQ / QS / Indépendant).
- **Volume:** vote no. 139 by 1 April 2026 in a session that opened 30 September 2025, so roughly 200 or more a year.
- **Language:**
  - Journal des débats and procès-verbal are **French only**, so the English taxonomy cannot read them. A French term layer (`taxonomy-fr.yaml`), drafted with a native reader, is required, as in Germany.
  - Bill titles do exist in English, but that does not save classification: the English taxonomy has no "laicity", "secularism" or "religious symbols", and missed "end-of-life care".
- **Timing:** the vote register shows the 43rd Legislature's 3rd session closing on 27 August 2026, and a general election is due on 5 October 2026. A new roster and session numbering (44-1) arrive this autumn. Build against 43rd-legislature data, but key members on name plus riding plus date.
- **Effort:** 16–20 h for divisions (two eras, two formats), bills and roster; +8 h for the French term layer plus native review; +6 h for the Journal des débats.

### New Brunswick (legnb.ca): value 4, difficulty 3

- **robots.txt sets `crawl-delay: 10`.** It was honoured, which makes backfills slow: about 50 journals per session take more than 8 minutes. No WAF.
- **Journals:** `https://www.legnb.ca/content/house_business/60/2/journals/47230615e2.pdf`, from listing pages `/en/house-business/journals/60/2`.
  - Names: "e" is English, "f" is French. File names carry sitting number, YYMMDD and occasionally a revision suffix ("e2"), so take them from the listing.
  - Format: "on the following recorded division: YEAS - 26", then three columns of "Hon. Mr. Holder", "Ms. Holt", "Mr. J. LeBlanc".
  - Back to the 53rd Legislature (1995).
- **PROOF: Policy 713.** Motion 50 as amended (asking the Child and Youth Advocate to consult on the Policy 713 changes) was **carried 26–20** on 15 June 2023.
  - YEAS: Ms. Holt, Mr. Arseneault, and the PC rebels Hon. Mr. Holder and Hon. Ms. Shephard.
  - NAYS: Hon. Mr. Higgs, Hon. Mr. Hogan.
  - The same day, Bill 46 (Education Act) second reading passed 27–20. Bill 52, Human Organ and Tissue Donation Act (area 13), passed third reading **on voice**.
- **Hansard:** `/content/house_business/61/2/hansard/10%202025-11-05b.pdf`, current. The **"b" edition is bilingual**: English and its French translation in parallel columns that pypdf interleaves, so it needs the left-column split from `src/ca_gazette_pdf.py`. Labels look like "Hon. Mr. Dornan:".
  - **One file is truncated at source:** the 20 November 2025 Hansard served exactly 1,290,240 bytes with no EOF marker, twice. It must be recorded as a gap, never as an empty sitting.
- **Bills:** `/en/legislation/bills/61/2/46/energy-sector-consumer-advocate-act`, with sponsor, party and a dated progression timeline.
- **Roster:** `/en/members/current` (Liberal / PC / Green).
- **Volume:** 5 recorded divisions in 10 sampled sittings of 61-2, so about 25 a year.
- **Effort:** 12–14 h for divisions, bills and roster; +8 h for Hansard (bilingual columns).

### Newfoundland and Labrador (assembly.nl.ca): value 2, difficulty 3 (probe agent)

- **Divisions:** Journals PDFs, e.g. `https://www.assembly.nl.ca/HouseBusiness/Journals/ga50session2/22-11-01.pdf`.
  - Two columns, AYES and NAYS, with an initial and surname ("T. Wakeham"). They need `extraction_mode="layout"`.
  - Proof: Schools Act Bill 7, third reading on 1 November 2022. Ayes: S. Crocker, A. Parsons. Nays: B. Petten, J. Dinn.
- **Volume:** about 10 a year (27 in 130 sittings).
- **Lag:** the 51st GA journals are not posted yet.
- **Other sources:** bills in HTML (`HouseBusiness/Bills/ga51session1/`); Hansard as Word-HTML; the roster is the JS array `js/members-index.js`.
- **Effort:** about 16 h, +6 h for Hansard.

### Nova Scotia (nslegislature.ca): value 3, difficulty 4 while blocked

- **Not reachable from the probe IP:** the TCP connection is reset on the TLS ClientHello, before our UA is ever sent, so this is not a UA filter.
- **Wayback only (unverified live):** Hansard HTML has YEAS/NAYS tables with full names. Example: Bill 6, third reading, 25 March 2025; YEAS include Hon. Tim Houston, NAYS include Claudia Chender. The journals appear to lag years behind (63-3, 2021).
- **Next step:** re-test from CI. If it is still reset, ask the Clerk to allowlist us.
- **Effort:** 16–20 h if reachable.

### Prince Edward Island (assembly.pe.ca): value 2, difficulty 5

- **Blocked:** every inner page redirects to a Radware CAPTCHA (`validate.perfdrive.com`). I did not attempt it.
- Bills and debates are POST search apps. `docs.assembly.pe.ca` serves PDFs by UUID, but the UUIDs can only be found from the challenged pages. `peildo.ca` has historical journals.
- **Out of reach** without allowlisting.

### Yukon (yukonassembly.ca): value 3, difficulty 5

- **Blocked:** a Cloudflare managed challenge on every path, including robots.txt and the Hansard PDF paths, across four tries in 25 minutes and on alternate hosts.
- It is the only territory with parties, so it is worth asking (yla@gov.yk.ca) and re-testing from CI.
- Unverified from search: Hansard PDFs at `/sites/default/files/hansard/35-1-NNN.pdf`, back to 1978.

### Northwest Territories (ntlegislativeassembly.ca): value 2, difficulty 2 (probe agent)

- **Recorded votes** are in Hansard HTML (`/hansard/hn260604`, recorded-vote section).
  - Members are called **by constituency** ("The Member for Range Lake"), so a dated constituency-to-member join is needed.
  - Proof: Motion 80-20(1), 4 June 2026, 6–0–11. Range Lake (Testart) voted for; Yellowknife South (Wawzonek, a minister) abstained.
- **V&P** are scanned PDFs with no text layer; skip them.
- **Third party:** `hansard.opennwt.ca` already parses per-member votes, back to the 18th Assembly. Licence not checked; same caution as openparliament.ca.

### Nunavut (assembly.nu.ca): value 1, difficulty 3 (probe agent)

- **Recorded votes** appear only inside Hansard PDFs, and are very rare (0–5 a year).
- Historic proof: Bill 12, Human Rights Act, November 2003 (`/sites/default/files/Hansard_20031104.pdf`). The amendment to strike "sexual orientation" failed 6–9–1; third reading passed 10–8.
- Hansard is published in English and Inuktitut. There is an archive-only case for a one-off pull.

### What consensus government (NWT, Nunavut) means for the 5CA

- There are no parties. The grouping axis is **Cabinet versus Regular Member**; cabinet is chosen by all MLAs and is always a minority (NWT 7 of 19, Nunavut 9 of 22).
- **Cabinet abstains as a bloc on regular members' motions** by convention (NWT 4 June 2026: 6–0–11). A minister's abstention must score **0, never soft opposition**.
- Bills pass on voice. Most members will have no recorded position on our ground, and the sheet must say "no recorded position", not impute one.
- **Recommendation:** no 5CA for NWT or Nunavut unless an area has at least two recorded votes. Use them as evidence lists only.

---

## Recommended build order and effort

A "session" here is about 4–6 hours of Claude-assisted build plus tests, the pace of the federal phases.

| # | Build | Why now | Effort |
|---|---|---|---|
| 0 | **Shared foundation**: `src/prov_store.py`, `src/prov_names.py` resolver, tally check, `config/watchlist-prov.yaml` seeded with the test-case bill keys, tests | Every province needs the same name resolution and the same "tally must match" guard | 6–8 h (1–2 sessions) |
| 1 | **Alberta** | Highest value: Bills 26/27/29, a UCP/NDP split on almost every one of our bills, divisions about 50 a year, bill pages flag "passed on division" | 16–18 h with Hansard (3 sessions) |
| 2 | **Saskatchewan** | Bill 137; HTML minutes with full names since 30L; small volume | 12–16 h with 29L backfill and Hansard (2–3 sessions) |
| 3 | **British Columbia** | Cleanest data (voting index, bills JSON, members GraphQL); Conservative opposition now forces divisions on our ground | 12–14 h (2–3 sessions) |
| 4 | **Manitoba** | Buffer-zone and gender-expression divisions; easy PDFs. **Christopher's call on the AI-crawler robots policy first.** | 18–22 h (3–4 sessions) |
| 5 | **Ontario** | Volume and HTML tables, but less on our ground lately | 13–15 h (2–3 sessions) |
| 6 | **New Brunswick** | Policy 713; slowed by the 10 s crawl-delay and the bilingual Hansard | 20–22 h (4 sessions) |
| 7 | **Quebec** | High value but the French layer is a project of its own, and the 2025 electronic-vote format change means two parsers. Start after the 5 October 2026 election settles the roster | 30–34 h incl. French terms (6 sessions) |
| 8 | Newfoundland and Labrador | About 10 divisions a year, mostly budget | 20–22 h (4 sessions) |
| 9 | NWT, then Nunavut | Evidence only, no 5CA; NWT via opennwt if its licence allows | 12–16 h; 12–18 h |
| — | Nova Scotia, PEI, Yukon | Re-probe from CI. If still blocked, write to each Clerk asking to be allowlisted | 0 until reachable; NS about 16–20 h after |

**Total for steps 0–7:** about 130–150 hours, or roughly 25 sessions. A practical first milestone is steps 0–3 (Alberta, Saskatchewan, BC), about 50 hours. That covers every English-language test case except Policy 713 and Ontario.

---

## Proposed common design

It mirrors the `ca_*` pattern: a module of its own, idempotent schema, nothing outside the prov tools reading it, and `db.TABLES` declared from day one. That last point avoids the federal mistake, where `tests/test_db.py` failed until phase 3.

**Modules.** There is one ingest module per legislature, `src/ingest/prov_ab.py`, `prov_sk.py` and so on, each exposing the same small interface:

- `list_records(client, since) -> [RecordRef]`: listing pages to file URLs. Never construct a file name.
- `parse_divisions(raw) -> [Division(number_in_day, question, bill_ref, result_words, printed_totals, [(raw_label, position)])]`
- `fetch_roster(client, legislature) -> [Member(name, party, riding, from, to)]`
- `fetch_bills(client, session) -> [Bill]`
- `parse_speeches(raw) -> [Speech]`, optional.

A thin runner, `tools/prov_collect.py --prov ab`, drives them through `src/http.HttpClient`, which already carries the honest UA, per-host throttle and raw archive. Each host gets a throttle and a crawl-delay entry (legnb.ca: 10 s).

**Tables (`src/prov_store.py`), keyed by `prov`** (`ab`, `bc`, `mb`, `nb`, `nl`, `ns`, `nt`, `nu`, `on`, `pe`, `qc`, `sk`, `yt`):

- `prov_members (prov, member_key, name, surname, riding, party, first_seen, last_seen, sitting)`. `member_key` is the legislature's own id where one exists (BC memberId, AB mid, ON slug); otherwise a slug of name plus riding.
- `prov_member_terms (prov, member_key, legislature, party, riding, start, end)`. Party **over time**, because the NI and federal lesson is that the party at the vote is a fact, not a join. Quebec's annex gives it directly.
- `prov_divisions (division_key, prov, legislature, session, date, seq, question, bill_key, stage, result, yeas, nays, abstentions, source_url, areas, matched_terms, tier, positions_ok, first_seen)`. `division_key` is `'<prov>-<leg>-<sess>-<date>-<seq>'`. `result` is the legislature's own words, never derived.
- `prov_votes (division_key, member_key NULLABLE, raw_label, position, party_at_vote)`. The `raw_label` is kept exactly as printed, and **an unresolved label is stored with a NULL member, never guessed**, as in `ca_speeches`.
- `prov_bills (bill_key, prov, legislature, session, number, title_en, title_fr, sponsor, is_government, stages JSON, latest_stage, royal_assent, text_url, areas, matched_terms, tier, …)`
- `prov_sittings (prov, sitting_key, date, record_url, divisions, speeches_stored, read_at, status)`. Every record read gets a row, and a truncated or unreadable file is a **gap**, not an empty day (NB Hansard 20 November 2025).
- `prov_speeches (speech_id, prov, sitting_key, date, subject, bill_key, member_key NULLABLE, speaker_label, language, text, areas, excerpt)`

**The guard that matters most:** if the resolved name count does not equal the printed totals, the division is a **gap** and stays owed (the Senate rule). Every one of these sources prints totals, so it is a free check on every PDF parse.

**Name resolution (`src/prov_names.py`).** It works against the roster terms valid on the division date, and must handle:

- surname only;
- surname plus riding in parentheses on a wrapped line;
- initial plus surname ("J. LeBlanc", "Sigurdson, R.J.");
- honorifics ("Hon. Mr.", "Mme", "M.");
- constituency only (NWT);
- two-word surnames that run into the next column ("Calahoo Stonehouse").

**The 5CA:** `config/prov_stance.yaml`, the mirror of `ca_stance.yaml`. Everything starts as `draft: true`. Consensus legislatures are evidence lists only.

**Classification:**

- Titles fail (2 of 18), so per-passage matching runs on bill text: explanatory notes and the bill PDF.
- Debate headings are matched too.
- A **per-province watchlist** names the bill keys and policy names: Policy 713, SOGI 123, "Parents' Bill of Rights", "laïcité", "notwithstanding clause", "pronoun", "puberty".
- The judge decides tier 2.
- Quebec needs `taxonomy-fr.yaml`.
- Consider for the shared English list: "laicity"/"secularism"/"religious symbols", "end-of-life care", "efforts to change sexual orientation or gender identity", "Parents' Bill of Rights", "presumed/deemed consent" variants. That is Christopher's taxonomy-versioning call.

## PDF parsing needs

pypdf 6.x is installed. `src/ca_gazette_pdf.py`'s column split, using the private layout interface, is the reusable piece.

| Source | Layout | What to do |
|---|---|---|
| AB V&P | 3 columns of surnames; riding on a wrapped line | Greedy roster match, re-attach "(Riding)" lines, tally check |
| SK Minutes 29L and earlier | Bilingual, two columns, English left; ridings wrap | Left-column filter (ca_gazette_pdf), then the AB-style matcher. 30L+ is HTML: no PDF needed |
| MB V&P | One name per line, capitals | Plain extract |
| NB Journals | 3 columns, honorific plus initial plus surname; separate EN file | Plain extract and honorific stripping |
| NB Hansard | Bilingual two-column, EN and FR interleaved | Column split |
| QC procès-verbal annex | 4 columns "Surname (PARTY)", riding wraps under the wrong column | Layout mode with x-positions, or token-stream matching against "(CAQ|PLQ|PQ|QS|IND)" |
| NL Journals | 2 columns AYES/NAYS, initial plus surname | `extraction_mode="layout"`, which leaves stray spaces ("T. W akeham"); normalise |
| Nunavut Hansard | Prose | Regex on the Speaker's calling of names |
| NWT V&P | Scanned images | Avoid (OCR); use Hansard HTML |

## Risks

- **Blocks and WAFs:**
  - Yukon (Cloudflare), PEI (Radware) and Nova Scotia (TCP reset) may be blocking the VPN IP. Ontario's Akamai rejects a contact-less UA.
  - **Never switch to a browser UA to get in.** The repo allows that only per host and with Christopher's sign-off (`src/http.py`). Ask the Clerks instead.
- **Robots and policy:**
  - Manitoba's explicit AI-crawler ban is an ethical flag, even though our UA is technically allowed.
  - Ontario forbids query strings.
  - Quebec forbids `/json/`, so its vote register is out.
  - New Brunswick's crawl-delay of 10 s makes backfills slow.
- **Format change:**
  - Quebec moved to electronic voting in 2025 and the names left the Journal des débats.
  - Ontario has two V&P layouts.
  - Saskatchewan moved PDF to HTML at the 30th Legislature.
  - Expect more of this. The tally check turns a silent layout change into a gap.
- **Path quirks:**
  - Alberta's `_1200_` versus `_1330_` and its backslash hrefs.
  - Saskatchewan's two path roots and its date formats.
  - New Brunswick's "e2" revision suffixes.
  - BC's progress-of-bills silently answering a wrong session for an unknown key.
- **Truncated sources:** the NB Hansard of 20 November 2025 is served truncated. Gap it and retry later.
- **Names, not ids:** no province publishes member ids on divisions. Resolution errors are the main correctness risk, so test with a known partisan's side on every new legislature (the Lords-inversion lesson).
- **Voice votes:** many of the signature fights have no member record. The 5CA must not read silence as anything.
- **Language:**
  - Quebec's Journal and procès-verbal are French only.
  - NB and SK minutes are bilingual, and the French column must be dropped or it double-counts.
  - Nunavut is published in Inuktitut too.
  - The English taxonomy already misses most provincial English titles.
- **Elections reset rosters:** Quebec votes on 5 October 2026. Roster terms must carry dates.

## What is honestly out of reach

- **Yukon, PEI and probably Nova Scotia**, unless CI gets through or the Clerks allowlist us. We do not solve CAPTCHAs or challenges.
- **Quebec's vote register JSON**, which robots.txt disallows. The procès-verbal PDFs are the lawful route.
- **NWT Votes and Proceedings**, which are scans. Hansard covers the votes.
- **Stable member ids on votes** anywhere. Every province needs name resolution.
- **Member positions on voice-vote bills** (Ontario Bill 77, NB Bill 52, the NL abortion-access bill and others). There is nothing to collect.
- **A Quebec classification that is ready on day one.** It waits for a French term layer and a native reader.
- **Real-time coverage in NL and Nova Scotia**, whose journals lag months to years. Hansard is the timelier source where it can be reached.

## Proof URLs (all fetched 2 October 2026)

- AB: https://docs.assembly.ab.ca/LADDAR_files/docs/houserecords/vp/legislature_31/session_1/20241203_1200_01_vp.pdf and …/hansards/han/legislature_31/session_1/20241203_1330_01_han.pdf
- SK: https://docs.legassembly.sk.ca/legdocs/Assembly/Minutes/29L3S/231020Minutes.pdf
- ON: https://www.ola.org/en/legislative-business/house-documents/parliament-43/session-1/2022-11-03/votes-proceedings
- QC: https://www.assnat.qc.ca/fr/travaux-parlementaires/assemblee-nationale/42-1/journal-debats/20190616/247401.html, plus the 1 April 2026 PV via `/Media/Process.aspx?MediaId=ANQ.Vigie.Bll.DocumentGenerique_220051…`
- NB: https://www.legnb.ca/content/house_business/60/2/journals/47230615e2.pdf
- BC: https://lims.leg.bc.ca/hdms/file/Debates/43rd2nd/20260219am-Hansard-n119.html and https://lims.leg.bc.ca/hdms/file/Index/43rd2nd/2026-Votesr.htm
- MB: https://www.gov.mb.ca/legislature/business/42nd/3rd/votes_082.pdf
- NL: https://www.assembly.nl.ca/HouseBusiness/Journals/ga50session2/22-11-01.pdf (probe agent)
- NT: https://www.ntlegislativeassembly.ca/hansard/hn260604 (probe agent)
- NU: https://assembly.nu.ca/sites/default/files/Hansard_20031104.pdf (probe agent)

## Decisions (Christopher, 2 October 2026)

"Go with your defaults and collect Manitoba. No CanLII key for now."

- **Manitoba is collected.** Its robots.txt bans named AI crawlers. Our collector is not one of them: it is not a training crawler, it identifies itself honestly, it reads public parliamentary records at about one request a second, and it obeys any path disallowed for `*`. If Manitoba names it, or asks us to stop, we stop.
- **No CanLII key**, so provincial appeal courts stay out of scope. The SCC collector covers the Supreme Court.
- **Committees:** every meeting of the key eight (JUST, HESA, FEWO, ETHI, AMAD, SECU, HUMA, CHPC). Other committees are fetched only when a meeting's study title matches the taxonomy.
- **Witness testimony** is collected for internal use (`ca_testimony`). It is never part of a member's record and never shown on a reader-facing page.
