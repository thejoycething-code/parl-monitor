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
| **Nova Scotia** | Yes. Hansard HTML, one page a sitting: a YEAS/NAYS table (seen 2019–2026) or paragraph lines (seen 2010), then the Clerk's count "For, 39. Against, 11." Read from CI (the laptop's VPN exit is reset) | Hansard listed from the 56th Assembly; Journals to 63-3 (2021) only | HTML listing per session, a page per bill with stage dates, first-reading text in HTML | HTML per sitting | HTML table per Assembly (61st on); profiles date party by year | ~15–35 (22 in the 25 sittings sampled) | 3 | 3 |
| **PEI** | Blocked, from CI too: every inner page 302s to a Radware CAPTCHA (validate.perfdrive.com) | peildo.ca holds the 32nd–43rd Assemblies' Journals only | Search app (POST), behind the challenge | Search app, behind the challenge | Behind the challenge | Unknown | 5 | 2 |
| **Yukon** | Blocked (Cloudflare managed challenge, even robots.txt) | Hansard 1978 (search only) | Unverified | PDF (search only) | Unverified | Unknown | 5 | 3 |
| **Northwest Territories** | Yes. Hansard HTML; members called **by constituency**. V&P are scans with no text layer | Hansard 2000 | HTML with stages | HTML, docx and PDF | HTML, **no parties** | ~30–60 (est.) | 2 | 2 |
| **Nunavut** | Yes but rare. Hansard PDF only, by surname | Hansard 2003 at least | HTML table, current session only | PDF in English and Inuktitut | HTML, **no parties** | 0–5 | 3 | 1 |

---

## Built

**Hansard speeches are read too, since 2 October 2026** (`tools/prov_speeches.py`; see "Hansard speeches" below). **Scheduled since 3 October 2026** (`.github/workflows/prov-weekly.yml`, "Provinces weekly", Wednesdays; see "Schedule and backfill" below). Nothing outside `tools/prov_*.py` reads their tables. By hand, run one province at a time, into a scratch store first:

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
| New Brunswick 60-2 | 9 May–16 Jun 2023 | 16 Journals | 16 (16) | 68 | 712 (0); party 712 | 61, 33 texts (1) | 1 |
| New Brunswick 61-2 | 18–21 Nov 2025 | 4 Journals | 5 (5) | 16 | 209 (0); party 209 | 51, 19 texts (0) | 2 (the Hansards of 19 and 20 Nov are truncated; party still covered) |
| Newfoundland and Labrador 48-1 | calendar 2016 | 57 Hansards | 34 (32) | 179 | 1,152 (0); party 0 | 72, 64 texts (1) | 3 |
| Newfoundland and Labrador 50-2 | 5 Oct 2022–22 May 2025 (whole session) | 120 Hansards | 27 (21) | 493 | 885 (2, both in uncounted divisions); party 0 | 114, 104 texts (2) | 8 |
| Newfoundland and Labrador 51-1 | 3 Nov 2025–17 Sep 2026 (whole session) | 39 Hansards | 11 (11) | 60 | 416 (0); party 416 | 19, all texts (0) | 3 |

(The NB and NL rows are the runs after the fixes of 3 October 2026 ("Fix New Brunswick and NL"), into copies of the 2 October scratch stores. Before them: NB 61-2 had 3 of 5 tallying and 2 unresolved, NL 50-2 15 of 27 and 157 unresolved, and no NB or NL vote had a party.)

- **New Brunswick:** every gap is the source's. The Journal of 9 June 2023 is served truncated (129,024 bytes, no `%%EOF`, twice), so it is stored `unreadable` and stays owed. The Journal of 20 November 2025 prints "Mr. Russel" twice; the reviewed alias clears both and all 21 divisions tally. Every vote has its party at the vote, from the Hansard member lists (7 lists for 2023, 2 for 2025: the Hansards of 19 and 20 November 2025 are both served truncated, and 20 November is covered by the lists of 18 and 21 November, which agree for every member).
- **Newfoundland and Labrador, divisions per year:** 34 in 2016 (57 sittings), 10 in 2022 (from October; 15 sittings), 8 in 2023, 5 in 2024, 4 in 2025, then 11 in the 51st Assembly's first session (38 sittings in 2026). That is about 5–35 a year: the scope's "about 10" holds for the 50th Assembly and the 2016 budget year is the outlier. 2016's are mostly the budget, the deficit levy (Bill 14) and supply.
- **Newfoundland and Labrador, gaps by cause:**
  - Committee of the Whole divisions whose count was never read aloud: 8 (2 in 2016, 6 on 12–18 October 2022). Names, no total: nothing to check against.
  - The 2024 attendance summary is a scan: now bridged (below); all 5 divisions of 2024 tally.
  - The Hansard typo "Lloyd Parrot" (19 October 2022) is cleared by a reviewed alias. The same typo on 12 October 2022 is in an uncounted Committee division and is left (that division can never place).
  - The progress table dates a reading to a day whose Hansard has no record of it: 5 (for example Bill 62's second reading, dated 12 December 2016, whose debate began that day and did not conclude in that file).
  - One count with no division read before it (1 April 2026).
- **NL on our ground:** the Access to Abortion Services Act (Bill 43, 2016) passed every reading on voice. Two false positives from the English taxonomy: the Credit Union Act amendment (50-2 Bill 8) on "right to withdraw" (area 6), and a Labour Standards Act amendment (50-2 Bill 82) whose organ-donor leave matched "organ donation*" (area 13). Both are taxonomy calls, not parser errors. They are real subject-matter text, not statute names, so the classifier's statute masking does not apply, and the provincial watchlist can only ADD areas to a key, not remove them: there is no per-province exclusion. Left for a taxonomy decision (`config/taxonomy.yaml` is not edited here); Manitoba 42-3 Bill 44 is the same organ-donor-leave case.
| Quebec, six windows 2013–2026 | see "Quebec" below | 42 procès-verbaux | 146 (146) | 18 | 14,573 (0) | 42-1 swept: 182, all texts read (8); 8 more by `--bill` | 0 |

- **Alberta:** 91 members with 116 dated terms; every bill-page "passed on division" stage matched a parsed division.
- **Saskatchewan:** 61 members from the day covers. Bill 137 has eleven divisions on our ground.
- **British Columbia:** 93 members. The whole session lists 73 transcripts (dry run).
- **Manitoba:** 56 members per day from the Hansard covers (85 across the two legislatures). Mark Wasyliw is NDP on 14 October 2021 and Independent on 2 June 2025: party at the vote is the day's.
- **Ontario:** 123 members from the 2022 Hansard list, 107 from 2015's, 124 from 2025's. Two first runs failed honestly and were fixed: the 2015 Hansard prints its member list ten pages from the end, not in the last six (0 members, so every 2015 division was a tally gap); and the late-2025 V&P prints every name twice (English and hidden French div) and drops the table under a nil list, so 7 of 9 divisions were refused by the tally check ('Allsopp Allsopp') and 4 were missed (caught by the "on the following division" count). No wrong position was stored either time.
- **5CA:** `tools/prov_5ca.py --all` wrote 4 Alberta, 1 Saskatchewan and 4 BC evidence sheets; on the Manitoba/Ontario store it wrote 1 Manitoba (area 1) and 3 Ontario sheets (areas 4, 5, 7), the Bill 77 sheet ending "Passed on voice, no member record: 2015-06-04 on-41-1/77 Third Reading", with nobody placed (the stance file is empty).
- **5CA:** `tools/prov_5ca.py --all` wrote 4 Alberta, 1 Saskatchewan and 4 BC evidence sheets, with nobody placed (the stance file is empty). For Quebec it wrote 8 evidence sheets (freedom of religion: 8 trusted divisions and 1 voice decision), nobody placed.

### Foundation (step 0)

- **Tables** (`src/prov_store.py`, in `db.TABLES`, created by `db.init_db`): `prov_members`, `prov_member_terms`, `prov_divisions`, `prov_votes`, `prov_bills`, `prov_sittings`, `prov_speeches`, keyed by `prov`.
  - The sighting column is `last_seen` (renamed from `last_read` on 3 October 2026, when the workflow began running these; `ensure_schema` renames it in an older scratch store).
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
  - The V&P parser was proven on the 31st Legislature, then on the 27th-30th by the 2010 backfill (below). A layout it does not know still shows up as a tally gap, not wrong votes.
  - A division's bill is the last bill named before it. Committee of the Whole sittings that take several bills together could attach a division to the wrong one.
  - The taxonomy's tier-1 "named person" (added for Holyrood) tags Alberta's Professional Governance Act (Bill 40) as area 6. That is a false positive, and the fix is a taxonomy decision.
- **The 2010 backfill's tally gaps (2 October 2026).** 358 of 1,338 recorded divisions failed the tally check, 306 of them in the 30th Legislature. Re-read locally from 186 fetched V&Ps (the 136 failing days, the six flag days and a 46-day sample of passing ones): 355 now pass in the parser and resolver and 2 more through reviewed Hansard facts; 1 (a name the V&P left out) is left, 0 regressions, and no identity on a previously passing division changed. By cause (a division can show several):

  | Cause | Divisions | Fix |
  |---|---|---|
  | "Nixon (Rimbey-Rocky Mtn. House-Sundre)": the V&P abbreviates Jason Nixon's riding | 185 | reviewed `riding_aliases` in config/prov_record.yaml |
  | "Glasgo": Michaela Frey sat as Glasgo until 2021; her member page says "Also served under Glasgo" | 133 | reviewed `other_surnames` in config/prov_record.yaml |
  | A list cut short or miscounted | 101 | glyph-spaced names closed up ("G a n l e y  P a y n e"); a split surname rejoined only when the join is a known surname ("La rivee"); "Against amendment:" with no "the"; a header with no total read, and failed |
  | The remote-vote mark "Amery*", "Hanson *", or a lone "*" wrapped to the next line. The V&P's own footnote: "* Member voted remotely" | 42 | the mark is kept on the raw label and dropped from the name |
  | A shared surname printed bare (the list was cut before its riding line) | 35 | the list fixes above |
  | "Intersessional Deposits" read as two surnames | 4 | the heading ends a name list |

  **Roster terms were being overwritten.** Reading one legislature's roster replaced ALL of a member's member-page terms with that legislature's, so a member who sat in the 29th, 30th and 31st kept only the last one read; re-reading their earlier divisions failed. `ps.replace_terms(..., legislature=)` now replaces one legislature's terms. The published store's terms are still in the overwritten state. The next Alberta backfill dispatch rebuilds them (a legislature's member page is re-read for any member holding no term in it) and re-reads the 136 gap sittings, which are still owed.

  **The record's own errors.** Christopher's decisions (2 October 2026) let a reviewed entry in config/prov_record.yaml, keyed to ONE division, use Hansard where it is explicit for the same division: 3 Dec 2012 (`hansard_totals`: the V&P prints no Nay total; Hansard's "Against - 29" is supplied and the 29 names are held to it) and 19 Nov 2013 (`hansard_labels`: a bare "Johnson" with two sitting; Hansard's "Johnson, L." settles that label in that list of that division only, and only because Linda Johnson is one of the two candidates). Both pass now. **Left in config/prov_known_gaps.yaml:** 13 May 2013 (the V&P lists 13 under "14"; Hansard's list has Wilson, but no reviewed fact may add a name the record left out).

  **The six "passed on division" flags with no division:** three were the parser (a Standing Order 64 question "on the Appropriation Bill standing on the Order Paper" names no bill; it now takes the one Appropriation bill the outcome line lists: 28 Apr 2011 Bill 17, 22 Jun 2015 Bill 3, 20 Nov 2019 Bill 24). 26 Nov 2015, where the V&P calls Bill 5 "Bill 9", is a reviewed `bill_corrections` entry: the division is stored under Bill 5 and its tally_note keeps "the record names Bill 9". 23 Mar 2022, one question approving Bills 7 and 8 together, is now linked to both (below). Left in known gaps: Bill 20's page on 26 Mar 2026, which is wrong (the V&P passed it on the voice).

  **One division, several bills: `prov_division_bills`** (division_key, bill_key, is_primary). `prov_divisions.bill_key` stays the primary bill, so every reader of it is unchanged; the link table holds the primary and every other bill the same question decided. `ps.store_division` writes it from `bill_key` plus `also_bill_keys`; `ps.ON_BILL` asks "did a division decide this bill" of both column and table; `ps.linked_bills` lists them. Alberta's areas inherit from every linked bill (and every watched one), its bill-page cross-check uses ON_BILL, and tools/prov_5ca.py names every linked bill on a vote line. Only Alberta's parser writes a second bill, on the one wording seen ("The question was put on the approval of Bill 7 ..., and Bill 8 ..."); the other provinces' cross-checks can switch to ON_BILL when a parser of theirs has the evidence.

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
- **Before 2023: the roster and the Minutes (2 October 2026).** One Hansard per legislature was fetched (honest UA, robots.txt checked: none on either host), 22 covers in all, March 2010 to December 2022.
  - **Two cover layouts, not one.** From the 28th Legislature (June 2016 on) every cover is the list `parse_cover` already read ("Beck, Carla — Regina Lakeview (NDP)", Party Standings below). The **26th and 27th Legislature** cover (March 2010 to spring 2016) is a table with the party *before* the riding, as a bare code, and no standings: "Name of Member Political Affiliation Constituency", then "Boyd, Hon. Bill SP Kindersley", "Huyghebaert, D.F. (Yogi) SP Wood River", "Vacant  Prince Albert Carlton". `parse_table_cover` reads it: 58 members on 9 December 2010, 57 and a vacancy on 19 November 2015. The codes are the ones the later covers print in brackets, so member keys and parties read the same across the change. Party is still the day's (Nadine Wilson is SP on the 2015 cover, Ind. on the 2023 one).
  - **The check without standings:** the count of member lines the table prints. A line the pattern misses makes it differ from the members parsed, and `roster_for_day` records the gap as it does a standings mismatch. The division's own tally check is unchanged.
  - **Three more faults, found end to end on a scratch store:**
    - *A spanning term skipped a day's cover.* A cover was taken as read when any term merely spanned the day. Read 2015 before 2012 and every member on both covers is "covered" on 23 April 2012, but McMillan and Hickie (2012 cover, not 2015) are not, so five 2012 divisions failed the tally. Now a day's cover counts as read only when a term starts or ends on that day (terms start and end only on days whose cover was read). Manitoba and Ontario have the same spanning check (`prov_mb.roster_for_day`, `prov_on.roster_for_day`); not changed here.
    - *The trigger phrase wraps.* "… on the following Recorded" / "Division:" (28th Legislature, 2 June and 24 November 2016): the roster was never read and nobody resolved. `has_division` matches across the line break, or on a YEAS/NAYS header line.
    - *The 27th Legislature's Minutes set drop capitals* as lines of their own ("Y" / "EAS – 9", "B" / "ill No. 127"), so no division header matched. `join_drop_caps` rejoins them. A heading in capitals now ends a name run ("ADJOURNED DEBATES" straight after the NAYS on 12 March 2014 was read as three more Nays; the tally check caught it). "which was agreed to on the following Recorded Division" and "it was a greed to" are results, and "the said bill was, accordingly, read a second time" is a voice decision.
  - **Hansard labels:** "Hon. Mr . Duncan : —" (a spaced full stop, 25 November 2015) was the one speaker of 69 unresolved; it is normalised in `prov_sk_hansard.parse_pdf`.
    - *2020–21 proxy votes* ("Beck*", "University)*", footnoted "*proxy vote by Vermette" between the YEAS and the NAYS) split each division in two and left the names unresolvable. The mark is dropped (the vote is the member's own, cast by a whip under the sessional order) and the footnote is furniture. "NAYS—N IL" is Nil.
    - *A re-read now replaces the record's divisions whole* (`drop_stale`): a corrected parse that makes fewer divisions than a broken one would otherwise leave the broken rows in the store as gaps beside the right ones.
  - **End to end, on scratch copies of the store (never the real file):**
    - 19 November 2015 (Bill 609 second reading, negatived 9–36): tally ok, 45 of 45 resolved, against that day's cover. Speeches: 25 November 2015 69 of 69 resolved (was 0 of 69), 26 November 66 of 66, 19 November 84 of 85 (the one is the Law Clerk, rightly unresolved).
    - **The re-dispatch, simulated:** main's code read 2015-10..12 and 2020-06..2021-04 into a scratch store (17 divisions, 0 tally ok, 192 votes unresolved), then this code ran over the same windows with no `--refresh`. It re-read only the 8 gap days and left 11 divisions, all tally ok, 0 unresolved, the split rows dropped.
    - **The whole backfill window, 2010-03 to 2022-12:** 773 Minutes records, 137 recorded divisions, 135 tally ok, 0 votes unresolved. The two gaps are 31 October 2019, where the Assembly printed "YEAS — 10" over eleven names (and "NAYS — 10" on the second division). The tally check refuses them, rightly.
  - **Not fixed:** the 26th–27th Legislature third reading "it was read the third time and passed", with no "agreed to", is not stored as a voice decision.

### British Columbia (step 3): `src/ingest/prov_bc.py`

- **What it does:**
  - **Sessions:** from the LIMS GraphQL API (POST only). `43-2` becomes id 206 and path code `43rd2nd`.
  - **Roster:** `allMemberParliaments`, with by-election and resignation dates as term bounds.
  - **Bills:** the progress-of-bills JSON, which gives reading dates, sponsor memberId and the text-file paths. Texts are served under `lims.leg.bc.ca/pdms` and classified per passage.
    - The trap is guarded: a reply whose file paths do not name the session's code (an unknown key answers 2006 data) is refused as a gap.
  - **Transcripts:** the House files in the session's debates JSON listing (`-Hansard-n119.html`, and `-Hansard-v19n3.htm` in the 39th and 40th).
  - **Divisions:** each division table in a transcript (six markups since 2009, below), with the Speaker's question, the StyleLine result, the Subject-Heading and the debate passages under it, all used for classification.
  - **Unnumbered bills:** a bill refused first reading is stored from the transcript as `bc-<leg>-<sess>/x-<slug>`.
  - **Voice decisions:** a reading date on a day whose transcripts were ALL read, with no recorded division on that bill and stage, is stored as a voice decision.
- **Proof reproduced:** the Gender Ideology and Child Protection Act was refused first reading on 19 February 2026, 38–49, tally matched. Rustad, Armstrong and Brodie voted Yea; Eby, Dix and Sharma voted Nay. The two Neufelds and two Andersons were told apart by initial. The bill is stored unnumbered with areas 3 and 6.
- **Party at the vote, dated to the sitting (built 2 October 2026).** The members API is not a dated source: it gives one party per member per parliament, the latest. It shows 13 Independents for the whole 43rd Parliament; on 26 February 2026 nine of them (Banman, Bird, Chan, Day, Milobar, Paton, Warbus, Wat, Wilson) sat as Conservatives, and eight were Conservatives at every division to 28 May 2026; it shows Bruce Banman, elected a BC Liberal in 2020, Conservative for all of the 42nd. `memberElections` carries a party only for 2024 and no election dates; member pages and bios print no party history; the Hansard Members Index and Voting Records index print none either. Those API terms stay `source = 'api'`, `party_dated = 0`, never written on a vote.
  - **The source:** every House issue's PDF (the `pdfLink` of the session's debates JSON, from 25 August 2009) prints an **"ALPHABETICAL LIST OF MEMBERS"** with each Member's party, and the **party standings** under it. It is, nearly always, the list for that sitting: the 6 February 2023 issue, produced in January 2024, still shows Banman "(BC Liberal Party)".
    - **Not always:** the 3 October 2022 morning issue (n221), regenerated in January 2024 like its neighbours, prints 2024's list (Banman "Conservative Party of BC", the Liberals as "BC United", standings "BC NDP 56; BC United 26; Conservative Party of BC 2"), where the afternoon issue of the same day prints 2022's. So **a party seen on one sitting alone is believed only when a sitting beside it agrees**: the listed sittings either side are read, and a lone list contradicted on both sides is dropped (a gap naming the members), the two sides joined where they agree. A list contradicting a run that was only assumed between two lists splits the run back to its two ends, and the sittings between are read again. On the live run this dropped n221 for 27 members and nothing else.
    - It prints the party **as the House recognised it**, not party membership: John van Dongen, who joined the BC Conservatives in March 2012, is "(Ind.)" ("Party Standings: BC Liberal 46; New Democratic 34; Independent 3; Vacant 2", 16 April 2012); John Rustad, BC Conservative leader from 2023, is Independent until the autumn 2023 sitting; Armstrong and Brodie are "OneBC" in autumn 2025 and Independent again from February 2026.
  - **Three layouts, all read:** the 39th ("Dix, adrian (nDP) ... Vancouver-kingsway": small capitals come out lower-case, "(l)" is Liberal; "Party Standings: liberal 49; new Democratic 35; independent 1"); the 40th to 42nd ("Banman, Bruce (BC Liberal Party) ... Abbotsford South"; "Party Standings: BC NDP 57; BC Liberal Party 28; BC Green Party 2"); the 43rd ("ALPHABETICAL LIST OF MEMBERS BY PARTY", one heading per party, two entries on one line where the columns meet; "BC NDP – 47 | Conservative Party of BC – 39 | ...").
  - **The standings are the tally check:** a list whose entries per party do not add up to the printed standings is refused whole (a gap). The cover's parliament and date must match the listing's. Each entry resolves against the roster terms valid that day by surname, then given name, then riding, unique-or-nothing. Parties are stored under the API's own names ("British Columbia United", "Conservative Party of British Columbia", "OneBC").
  - **Stored as party-only terms** (`source = 'party-hansard'`, `party_dated = 1`) spanning the sittings each party was seen on. Read: every division day (the issue of the part that held the division, then the day's other part); each session's first and last sitting; then, by **bisection** through the session's listed sittings, the sittings between a member's last list in one party and first in another, until the change lies between two sittings in a row. A vote in such a window, or on a day whose list cannot be read and whose neighbours disagree, carries **no party**, as in Nova Scotia.
  - **Written at write time, repaired by re-reading:** `party_at_vote` is a column of `prov_votes`, and both the store and the 5CA sheets read it (the 5CA's party column is the member's latest; each VOTE line says "as <party at the vote>"). After the lists, `prov_store.refresh_party` rewrites `party_at_vote` for every stored vote of the session, so a vote stored before its day's list was read gets its party without its transcript being fetched again (a transcript read cleanly is skipped).
  - **Changes found, each narrowed to two listed sittings in a row** (live run, 2 October 2026):
    - 43rd: Armstrong, Brodie and Kealy Conservative to Independent between 6 and 11 March 2025; Armstrong and Brodie "OneBC" from 6 October to 3 December 2025 and Independent again from 12 February 2026; Sturko Conservative to Independent between 29 May and 6 October 2025; Boultbee between 9 and 20 October 2025; Chan between 12 and 30 March 2026. The other eight the API calls Independent were Conservatives in every list to 28 May 2026.
    - 42nd: the Liberals become "BC United" between 6 and 17 April 2023; Banman BC United to Conservative between 11 May and 3 October 2023; Rustad Liberal to Independent between 2 June and 4 October 2022, Conservative from 3 October 2023; Adam Walker NDP to Independent between 11 May and 3 October 2023; Selina Robinson NDP to Independent between 5 and 6 March 2024.
    - 41st: Plecas Liberal to Independent between 12 and 13 September 2017 (he became Speaker); Weaver, Furstenau and Olsen Independent to BC Green between 2 and 6 November 2017 (recognised as a party); Weaver Independent again from 11 February 2020.
    - 40th: Pat Pimm Liberal to Independent between 28 July 2016 and 14 February 2017. 39th: Bennett, Lekstrom and Simpson in 2010–11; van Dongen (see above); John Slater in 2012–13.
  - The BC Liberal Party's rename to BC United (April 2023) is a change of printed party like any other: a vote between the last "BC Liberal" list and the first "BC United" one would carry none (there is none).
  - **End to end (scratch copy of the store, 2 October 2026), running the CI backfill command itself** (`tools/prov_collect.py --prov bc --all-sessions --since 2010-01-01`): 158 member lists read across the 23 sessions, 14 transcripts re-read (only those that had been gaps; every clean one was skipped); **8,508 of 8,508 stored votes carry a dated party, 0 undated, 0 with none**. All 8,508 are the 43rd Parliament's, because of the two silent losses below. On 26 February 2026 (126.2): 46 NDP, 39 Conservative, 2 Green, 5 Independent, where the API showed 13 Independents. 32 gaps besides the 19 known tally gaps: Campbell, Black and Penner (39th) are not in the API's roster of the 39th, which lists the members sitting at its end, so their list entries resolve to nobody; one morning issue (28 November 2017) prints no list (its afternoon issue is read instead); n221 refuted for 29 members.
- **Known limits:**
  - Party is dated to the sitting, not the hour. A member listed under two parties on one day (two parts) has none that day.
  - A list printing an EARLIER state, as a template not yet updated after a change would, cannot be told from the truth: the change would be dated a few sittings late. None was seen; only a later state (n221) was.
  - A party seen only on the newest sitting read (the session's frontier) is believed until a later sitting is read.
  - Hansard speeches are not stored.
- **Two silent losses, found 2 October 2026 and fixed the same day:**
  - **The 39th and 40th Parliaments (2009–2017) listed no transcript.** Their files are named `20100531am-Hansard-v19n3.htm` (volume and number) and `list_records` wanted `-Hansard-n<issue>`. Both forms are now read. **Guard:** a listed House transcript whose name is not taken, or a listing that yields none, is a gap.
  - **Every markup since 2009 is read now** (fixtures from real transcripts, `tests/fixtures/prov/bc_hansard_*`):
    - 2009–2017: `<table class="DivisionTable">` with the headers in `<td colspan="3"><p class="DivisionHeader">YEAS — 42</p>`: the old parser read only `<th>` headers, so 2017's headers were taken as names (the 19 tally gaps).
    - 2011: `<table border="0" ... class="DivisionTable">` (the class not first).
    - 2010–2012: the names run on into a second table after a page break: a table with no "on the following division" since the last one continues that division.
    - 20 November 2014: a StyleLine left open before its table, so a paragraph now ends at `</p>` or where a table begins.
    - 2015: upper-case tags with unquoted classes (`<TABLE class=DivisionTable>`, `<P class=StyleLine>`).
    - 2014–2017: the printed page number inside a cell (`<span class="PageNumber">[ Page 8656 ]</span>` before "NAYS — 45" or a name): stripped.
    - Throughout, 2010 to 2026 (60 of them): **a division with no names in the transcript**, "Second reading of Bill 2 approved unanimously on a division. [See Votes and Proceedings.]". It is stored as a recorded division with no votes, `positions_ok = 0` and a `tally_note` beginning "no names" (counted apart, like Ontario's "totals only": known and untrusted, never owed, since no re-read can give the names). The names are in the Votes and Proceedings, read for exactly those days (below).
- **Names from the Votes and Proceedings (built 2 October 2026).** Each session's V&P is listed by `lims.leg.bc.ca/pdms/votes-and-proceedings/<code>` (JSON: fileName, filePath, date; found in the leg.bc.ca app at `dyn.leg.bc.ca`, robots allows all) and served at `lims.leg.bc.ca/pdms/ldp/<code>/votes/v151007.htm`, one file a day. The same markup from 2010 to 2026: "Motion agreed to *nemine contradicente* on the following division:" (or "on the following deferred division"), then `<table class="division">` with a `Yeas — 68` head and the surnames, `<br>` between them, in four columns, initials where two share one ("B. Anderson", "L. Neufeld"). 7 October 2015 is served as UTF-16.
  - **Only the days that need it:** every stored division whose `tally_note` begins "no names" and does not yet say "Votes and Proceedings read" is tried, on every BC run (the backfill and the weekly), until it is: the listing once per session, then one file per such day.
  - **Matching:** the day's no-names divisions, in Hansard's order, against the V&P's unanimous tables in order, when the counts agree and every bill both name agrees ("Bill (No. 38)" in the paragraphs before the table); otherwise by a bill only one unanimous table names; otherwise not at all. The division keeps its Hansard key.
  - **Then** the names resolve against the day's terms, unique-or-nothing, and must add up to the printed Yeas: the division becomes a normal recorded division (`positions_ok = 1`), its `tally_note` naming the V&P file and its sentence. Names that do not add up are a gap, the V&P named. A V&P that cannot settle it (no file for the day, no match) leaves "no names" with the reason appended ("Votes and Proceedings read: ..."), and is not tried again; a failed fetch is tried again next run.
  - **Traps:** the older listings mark every file `"published": false` (all 47 of 39th2nd) though each is served, so the flag is not read; 22 November 2018 prints Committee Section A's unanimous division before the House's where Hansard has them the other way round (matched by bill); "Bill (No. M 213)" has a space after the M; in committee the sentence is "the Committee divided, *nemine contradicente*, as follows" (2014).
  - **End to end** (scratch copy after the backfill above, the same `--all-sessions --since 2010-01-01` command, 8 minutes, 53 V&P days fetched and 18 session listings): **61 of 61 named, every tally ok** (Yeas 17 to 92 printed and read), 0 unresolved. BC now holds 631 recorded divisions, all 631 tally ok, and 41,745 votes, all with a dated party. Spot checks against the printed V&P: 6 November 2014, section 28 of Bill 2 in committee, Yeas 65, in the printed order (Sturdy, Bing, Hogg, Yamamoto, Oakes, ...); 22 November 2018, Bond's subamendment to Bill 45 (17) and third reading of Bill 50 (80), each to its own division.
    - February 2018 to May 2024 (41-3 to 42-5): `<table class="division-table">` with `<p class="division-header">` and hyphenated lower-case paragraph classes. **725 transcripts had been stored "ok" with 0 divisions.**
    - Classes are compared folded (`Subject-Heading`, `SubjectHeading`, `subject-heading`). Before 2018 the question is often not restated, so the stage falls back on the business heading ("Introduction and First Reading", "Committee of the Whole House"), and "I move the bill be introduced and read a first time" counts as the question. "BILL 2", "BIll 21" name their bill.
  - **Guard 1, the transcript's own words:** a transcript that prints "on the following division" more often than it parses divisions is a gap and stays owed, never "ok". On the live run it caught the 2014 and 2015 markups above.
  - A bare surname two members share, beside the other named by initial in the same division ("Black" beside "D. Black", 2011), is the one not named: only when exactly one is left.
  - **Guard 2 and the repair, the Voting Records index:** each session's Hansard index (`/hdms/index/<code>`, "Voting Records", one page per letter) links every standing vote to its transcript from the 41st Parliament on ("../../Debates/42nd2nd/20210602pm-Hansard-n82.html#82B:1845"; the 39th's and 40th's print no links, and the first letter page tells). Before a session is read, every transcript it cites that is stored "ok" with no division is made **owed** (`prov_sittings.status = 'owed'`), so the run reads it again; after the read, a cited transcript still holding none is a gap. About 20 small pages a session. **No raw copy of those transcripts was kept** (the vote collector archives nothing; the 2 October raw archive holds only the members and sessions replies), so this, not the raw archive, picks the sittings to read again: only the cited ones, not all 725.
  - **Voice decisions withdrawn:** a reading stored as voice while its division went unparsed is deleted once a recorded division of that bill, stage and day is stored.
- **End to end, 2 October 2026** (scratch copy of the released store, the CI backfill command `tools/prov_collect.py --prov bc --all-sessions --since 2010-01-01`, against the live pages; one run of 37 minutes from the laptop, then a second that re-read the 2 sittings left owed):

  | | Before | After |
  |---|---|---|
  | Transcripts read | 982 (none 2009–2017) | 1,662 |
  | Recorded divisions | 184 (all 2017 or 2025–26) | 631, 9 February 2010 to 28 May 2026 |
  | Tally ok / gap / no names | 165 / 19 / 0 | 570 / 0 / 61 |
  | By parliament, ok (no names) | 41st 0 (19 gaps), 43rd 165 | 39th 65 (7), 40th 100 (15), 41st 122 (22), 42nd 118 (12), 43rd 165 (5) |
  | Votes / unresolved | 8,508 / 0 | 37,173 / 0 |
  | With a dated party | 8,508 | 37,173 |
  | Voice decisions | 1,511 | 2,327 (138 withdrawn as divided; the 39th and 40th added) |
  | Sittings "ok" with 0 divisions where the index cites a vote | 153 of the 725 (the rest held none) | 0: those 153 read again, nothing else |

  - Party line: 36,305 of 36,361 trusted party votes (99.8%) with their own party's majority.
  - The government against the Official Opposition leader, on trusted divisions both voted in: Campbell–James 4 of 4 opposite (Yea and Nay on the HST, Bill 9, 30 March 2010); Clark–Dix 18 of 20; Clark–Horgan 21 of 23; Horgan–Wilkinson 54 of 64; Horgan–Bond 13 of 13; Eby–Falcon 8 of 9; Eby–Rustad 52 of 66 (Eby Yea, Rustad Nay on the Supply Act, 28 May 2026; both Yea on the US tariffs motion, 24 February 2025).
  - The 39th's first session sat only in 2009, so `--since 2010-01-01` reads none of its divisions; `since: 2009-08-25` would.
- **Members the API's roster lacks.** `allMemberParliaments` lists a parliament's members at its end: the 39th omits Gordon Campbell, Iain Black and Barry Penner, who resigned in 2011–12, and the API holds no 39th term or resignation for them (`allMemberResignations` holds two rows in all). The Hansard issue's own list names them. A list entry no roster term fits is matched against every member the API knows (`allMembers`, 378) on surname, given name **and** riding together, unique-or-nothing, and gets a **membership** term (`source = 'hansard-list'`) spanning exactly the sittings it is listed on. The sittings their votes left unresolved are read again in the same run. Spencer Chandra Herbert sat as "Herbert" in the 39th: a reviewed `other_surnames` entry (`config/prov_record.yaml`), which BC's vote resolver now loads.

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
  - The cover parser assumes one given name before the constituency when "Hon." is absent (true for every member of the 39th to 43rd). A two-word given name would make that member's riding unmatchable: a gap, never a wrong member.
  - V&P layouts from the 39th Legislature (2010) on are read, by the 2010 backfill (below). Earlier ones are untested; a change shows as a tally or count gap.
  - **One member, one key.** The covers print a member's given name differently across years ("Gregory" and "Greg" Dewar, "Tom" and "Thomas" Nevakshonoff, "Cliff" and "Clifford" Graydon), and the key is the given name plus surname, so each had two keys. Since 2 October 2026 (Christopher's decision) Manitoba shares Ontario's seat rule, moved to `prov_store`: a cover member is stored under the one key already holding the same surname and riding in the same legislature when the given names agree (one contained in the other: Ontario's by-election guard) (`canonical_key`), and `merge_split_members` folds keys the store already holds, in place, with nothing fetched, at the end of every Manitoba collect. That joins Greg and Gregory Dewar. Two pairs need a reviewed `same_person` entry in config/prov_record.yaml, each citing the Assembly's former-members page: Graydon, whose keys sit in two legislatures (the rule is not applied across legislatures: Rosann and Rick Wowchuk both sat for Swan River), one "GRAYDON, Cliff (Emerson)", elected 2007, re-elected 2011 and 2016, Independent from 22 October 2018; and Nevakshonoff, since "Tom" and "Thomas" fail the guard, one "NEVAKSHONOFF, Thomas (Interlake)", minister from 29 April 2015, when the covers start printing "Thomas, Hon.". Kept is the key most votes name. Smith, Marcelino, Lamoureux and Wowchuk stay apart (tested).
  - Two 40-1 covers of 2011 (31 Oct) leave Sharon Blady and Dave Gaudreau out of the PDF's text layer (only "Kirkfield Park" and "St. Norbert" survive). Their terms are widened from the covers that do print them, so a division between two such covers still resolves; a division before the first would fail the tally, not guess.
- **The 2010 backfill's gaps (2 October 2026).** CI run 37007080895 (commit 77627886, which had 7bf10436, the spanning-term cover fix) left 58 of 625 recorded divisions failing the tally, 1,620 of 31,126 votes unresolved and 86 gaps. Re-read on a scratch store from the same files (a cached local backfill reproduced the run exactly, bar one 2025 day the published store already covered): 57 of the 58 now pass, every vote resolves, and the gaps fall to 5, all record errors in config/prov_known_gaps.yaml. No identity or party on the 566 previously passing divisions changed. The re-run on a copy of the before-store and a fresh backfill give the same 627 divisions and 31,217 votes. Partisan check: on the Opposition amendment of 14 April 2010 (negatived 20-35) Hugh McFadyen and Kelvin Goertzen (PC) vote Yea and Premier Greg Selinger (NDP) Nay; on the 19 April 2012 main motion (36-19) Selinger is Yea, McFadyen Nay.

  | Cause | Before | After | Fix |
  |---|---|---|---|
  | The 39th Legislature's covers (2010-2011) print the party as "N.D.P." and "P.C.": only the two "Lib." lines were read ("only 2 member(s) parsed") | 31 divisions, 1,543 votes, 19 cover gaps | 0 | the dotted spellings are read and stored as NDP and PC |
  | "McFADYEN, Hugh": the cover's mixed-case Mc never matched the capitals pattern | 24 divisions, 24 votes | 0 | a Mc/Mac prefix is read; surnames title-cased as McFadyen |
  | A cover read by the old parser counted as read | (the re-run path) | | a cover with fewer than 40 members does not count, and an owed sitting re-reads its cover |
  | Calendar cells left unclosed (16 April 2013, 4 November 2025): the next day's Hansard filed under the day before, "no Hansard listed" for the next | 1 division, 53 votes, 2 gaps (the published store resolved the 2025 one through spanning terms) | 0 | a cell ends where the next one starts |
  | "WOWCHUK 49" and a bare "0": totals printed without dot leaders (3 June 2010) | 1 division | 0 | read as name plus total, and a nil list |
  | "on division." over a full roll call (19 April 2012); "on th e following division" (29 April 2013) | 2 count gaps | 0 | the count reads the text with spacing and page furniture removed, and counts a roll call under "on division." |
  | No "YEA" header in the PDF at all (24 May 2018's second division, 15 March 2019) | 2 count gaps, 2 divisions never stored | 0 (both stored, 15-30 and 45-0) | a list straight after "on the following division:" is the YEA list; the NAY header and both totals are still required |
  | A phrase printed twice running (11 June 2012, "divisi on, on the following division") | 0 (the old count missed both by luck) | 0 | consecutive phrases count once |
  | 5 Dec 2013, Bill 27 third reading: "18" printed over 17 Nay names; Hansard p. 705 says "Nays 17" | 1 division | 0 | a reviewed `hansard_totals` entry in the REPLACE form (`replaces: 18`); the 17 names are held to 17 and tally_note keeps the printed 18 |
  | 41-3 votes_010.pdf (5 Dec 2017) serves "Resource Not Found" | 1 gap | 0 (1 division: adjourning debate on Bill 8, 35-17) | read from Hansard 10B's own list (`vp_not_served`) |
  | 43-3's blank votes_013.pdf link serves "Resource Not Found"; 42-4 votes_036.pdf (13 Apr 2022) answers 300 with only the French file | 2 gaps | 2, known gaps | none needed: Hansard shows no division either day |
  | 42-4 lists votes_041.pdf for 25 April 2022, but it is a copy of the 26th's record (No. 42). It was a log line, and the day's three divisions were silently missing | not counted | 0 (3 divisions: budget amendment 20-32, budget motion 32-20, Bill 18 second reading 31-17) | a listed copy of another day's record is a gap; this day is read from Hansard No. 41 (`vp_not_served`) |

  A cause of the 86 is counted once; "before" divisions add to 58 and votes to 1,620. **Reviewed facts (Christopher's three decisions, 2 October 2026).** A Hansard total may replace a misprinted printed one: the entry must say `replaces:`, the figure the record prints, applies only while the record still prints it, and the printed figure stays in tally_note. A day whose V&P is not served is read from Hansard's own "A RECORDED VOTE was taken" lists, only for a day `vp_not_served` names, only while its listed V&P still fails (an error page or a copy of another day), and only from PDFs the day's Hansard listing names; source_url is the Hansard PDF, the Clerk's "Yeas N, Nays M" are the totals the names are held to, and Hansard's count of recorded votes must equal both the lists parsed and the entry's `divisions`. A surname pypdf splits ("Fontai ne", "J ohnson") is closed only into a surname on the day's roster. With all three: 631 divisions, all passing, 31,421 votes, none unresolved, 2 gaps (both known). Against the before-store, no party changed and the only key changes are the three merged people (Graydon 101 votes, Dewar 24, Nevakshonoff 20 in the re-run simulation); a fresh backfill gives the same 631 divisions and 31,421 votes, differing only in which of Graydon's two keys is kept. Partisan check on the Hansard-read days: on 25 April 2022 Premier Stefanson (PC) is Nay on the NDP amendment and Yea on the budget motion, Kinew and Fontaine (NDP) the reverse; on 5 December 2017 Stefanson is Yea, Kinew, Gerrard and Fletcher Nay. Two other misdated links are harmless: 40-3 files 5 Dec 2013's votes_017 under 6 March 2014 (Hansard No. 23 that day has no recorded vote), and 42-5 files votes_005 under 7 Nov 2022 (it prints the 21st, not otherwise listed). The new titled-bill fallback ("THAT (No. 229) – The Intoxicated Persons Detention Amendment Act/Loi ...") attaches bills to divisions and voice decisions where the block printed no "Bill (No. N)"; only re-read sittings get it, so 6 passing divisions keep a NULL bill and 35 voice decisions stay unstored in the published store. None is on our ground.

  **The CI re-run** is one dispatch of Provinces weekly with `provinces: mb` (since 2010-01-01, the default). It re-reads the 36 gap sittings, and each owed sitting re-reads its Hansard cover; clean sittings are not fetched again. Manitoba's roster is widened per cover (`extend_term`), not replaced, so the Alberta `replace_terms` fault does not apply and no roster rebuild is needed. It also reads the two `vp_not_served` days (both are owed: one unreadable, one never stored), applies the reviewed total on 5 Dec 2013 (an owed gap sitting), and merges the three split keys in place. Expect 2 gaps, both known: the step passes.
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
- **The 2010 backfill's tally gaps (2 October 2026).** The backfill (39-1 to 44-1, run before 7bf10436) stored 1,420 recorded divisions: 1,003 passed, 393 failed the tally check, 24 totals only; 10,242 of 118,040 votes unresolved. It ran before the spanning-term fix, but that was not the main fault: the Hansard member list (the roster) was misread on most early days. Re-read on a scratch store from 747 fetched pages (every gap sitting's hub, V&P and Hansard PDF): **2 fail, 1,395 pass, 153 totals only; 0 votes unresolved** (with the casting vote below placed). 130 divisions the record names but the parser never stored are now stored (129 of them totals only). By cause (a division can show several):

  | Cause | Divisions | Votes unresolved | Fix |
  |---|---|---|---|
  | 2010-2012 cover: each row (member, riding, responsibilities) drawn as ONE fragment, so only ministers' rows parsed (27-33 of 107) | 127 | 6,693 | split after the "(LIB)" party mark; the riding cut where a responsibility begins ("Hamilton Mountain Minister of …") |
  | 2013-2017 cover: the "Member and Party" header drawn in pieces ("Member and " + "Party /", "Memb" + "er and …"), so the first page (A-G) was skipped | 34 | 1,033 | the header is found on the joined line |
  | 2018-2023 cover: pypdf places the text after an em dash at (0, 0); x = 0 became the commonest column (0 members) and the origin line ran into each page's last member | 23 | 2,064 | such a fragment takes the position of the one it follows |
  | A member missing from a day's roster read short: each page's last member ("French", "Oosterhoff", "Yurek"), the 2021 header "Member and Pa" + "rty", a spanned day | 51 | 228 | the two fixes above; the day's cover is read every time the day is read |
  | "Cuzzeto": the V&P misprinted Rudy Cuzzetto in every list of 19 July 2018 - 21 July 2020 (save Feb-June 2019) | 135 | 135 | a reviewed `misprints` entry (below) |
  | A capitalised heading after an old-layout list read as two names ("PETITIONS" / "PÉTITIONS", "ORDERS OF THE DAY", "MOTIONS") | 44 | 88 | an all-capitals cell ends a list |
  | A list read short: the same "AYES / POUR - 68" printed again over a page (6 June 2019), "NAYS / CONTRE – 50 - Continued" (19 April 2016), the August 2022 tables with no `lang` and a plain `drum-table` (0 names read) | 5 | 0 | each read |
  | The record's own errors | 3 | 1 | two known gaps; the casting vote placed from Hansard (below) |

  **Divisions never stored.** Before 2022 a dilatory motion's totals sit in a paragraph of their own ("Lost on the following division:-" then "AYES - 19 NAYS - 42"); 129 were missed and their days were gaps. They are stored as totals only. "Lost of the following division" (28 Nov 2022) and 30 April 2025's V&P, pasted from Word (`votesProceedingsDocdivisionHeader`, names in `MsoFooter` paragraphs), are read.

  **One member, one key.** A member's key is the slug of the name as the day's list prints it, and pieces of text read without their spacing gave second keys: "KevinDaniel" Flynn, "LisaM." Thompson, "PrabmeetSingh" Sarkaria, "Bis s on", "V incent" Ke, "L’hon . Andrea" Khanjin, "P.C., Aileen" Carroll. The published store held 15 such pairs, and on a day both of a pair were valid every "Flynn" was ambiguous. Now: `pdf_fragments(extents=True)` gives each fragment's end from its font widths, so words drawn apart keep their space; a space before a lower-case letter inside a name is closed up; and `merge_split_members` folds keys that share a surname and a riding in one legislature (one seat, one member) into the key most votes already name, moving votes, terms and sponsorships. `canonical_key` stores a new variant under that key. The re-read merged 25 members. **The seat rule was approved by Christopher on 2 October 2026.** Its one known risk, a by-election successor of the same surname in the same riding, is guarded: the given names must also agree (the letters of one within the other's: "KevinDaniel"/"Kevin Daniel", "M. Aileen"/"Aileen"), or nothing is merged and the run logs "NOT merged". A successor with the same full name would still merge (none is known), and the store holds no Ontario by-election dates to test against. All 25 merges pass the guard.

  **Checked:** all 1,003 previously passing divisions were found again by content and still pass; no vote moved to another member; 154 votes changed key only by a merge of one member's two keys; party at the vote unchanged. Seven passing divisions on three days (30 Nov and 1 Dec 2016, 8 Mar 2018) moved up one sequence number, because a totals-only division printed before them is now stored. No stance or decision names those keys. Sixty passing days (122 divisions, 10 per legislature) re-read with `--refresh` under the new parser came back identical, vote for vote. A known partisan's side: Accepting Schools Act third reading, 5 June 2012 (65-36, failed before): McGuinty (LIB) Yea, Hudak (PC) Nay; Bill 55 budget, 20 June 2012: the same; Better Local Government Act, 14 Aug 2018 (71-39, failed before): Ford (PC) Yea, Horwath (NDP) Nay.

  **Reviewed facts.** `misprints` in config/prov_record.yaml (approved by Christopher, 2 October 2026; `pn.load_misprints`, read by `pn.Aliased`): ONE misspelling of one member's name over a span of days, in documents under a URL prefix, only after the normal resolver found nobody, only to a member holding a term that day. "Cuzzeto" → rudy-cuzzetto, 19 Jul 2018 - 21 Jul 2020, 42-1 V&Ps; Hansard prints "Cuzzetto, Rudy" in the same divisions. **The casting vote, 21 Sep 2017** (Bill 146 second reading, 16-16, printed 17-16 with "Deputy Speaker" among the Ayes): a `hansard_labels` entry with `office: true`, keyed to on-41-2-2017-09-21-1 alone, maps "Deputy Speaker" to Soo Wong from Hansard (21-SEP-2017_L095.pdf, p. 5136: "The ayes are 16; the nays are 16. The Deputy Speaker (Ms. Soo Wong): I declare the motion carried."). `pn.ReviewedDivisions.settle` takes an office label only when it resolved to nobody; the tally check then runs as normal and passes (17-16, Wong Yea, LIB). **Christopher chose to place casting votes (2 October 2026), against the convention that a casting vote keeps the question open and is not a stance.**

  **Left in config/prov_known_gaps.yaml:** 4 Apr 2019 (the V&P prints the first two columns of each list twice and drops the rest; Hansard 22-51), 4 Apr 2022 (the 19 Ayes printed with no header; Hansard 19-39), 6 Dec 2022 (a tie printed "0 Ayes, 0 Nays", no list), and three pages with no proceedings (26 Sep 2017's second V&P, 8 and 9 Aug 2022, the opening of the 43rd Parliament).

  **The CI re-run** is one `provinces: on` dispatch (since 2010-01-01). It re-reads the 271 gap and 4 unreadable sittings (about 750 requests), and merges the split keys at the start. No sitting marked ok needs re-reading: every fault above failed its division or miscounted its day, and the key merge needs no fetch. The roster is not rebuilt: Ontario never had Alberta's `replace_terms` fault (its terms are only ever widened). Terms from the misread 2010-2012 covers keep their wrong ridings ("Hamilton Mountain Minister of Consumer Services"); they still date the member correctly and a riding label never matches them.

### Decisions needed (Manitoba and Ontario build, 2 October 2026)

- **Ontario Bill 28: area 7 or no area?** It is a labour bill that invoked s.33 over Charter ss. 2, 7 and 15. The watchlist gives it area 7 (civil liberties) as a draft, so its three divisions appear on an area-7 evidence sheet.
- **Manitoba backfill leftovers (2 October 2026): decided yes to all three.** (1) A reviewed Hansard total may replace a misprinted printed one (the `replaces:` form). (2) The four divisions of days whose V&P is not served are read from Hansard's own lists (`vp_not_served`). (3) The split keys are merged (the seat rule, and a reviewed `same_person` entry for Graydon). See the Manitoba "Built" notes.
- **Manitoba Bill 43 (gender expression):** area 5 is from the scope. The taxonomy has no "gender expression", so similar bills elsewhere will be missed. Adding the term is a taxonomy-versioning call.
- **Schedule:** done 3 October 2026 for all eight built provinces (see "Schedule and backfill").
- **A chair's casting vote (Ontario, 21 Sep 2017): DECIDED 2 October 2026, place it.** Soo Wong is placed Yea from Hansard (see the Ontario backfill notes), against the convention that a casting vote is not a stance. 6 Dec 2022 is a casting vote too, but on a dilatory motion with no list and no totals: nothing to place, so it stays a known gap.
- **Ontario's seat rule: APPROVED 2 October 2026.** `merge_split_members` treats two keys with the same surname in the same riding of the same legislature as one member, now only when their given names agree too (the by-election guard). It merged 25, each checked by name.
- **The `misprints` fact type: APPROVED 2 October 2026.**

### New Brunswick (step 6): `src/ingest/prov_nb.py`

- **Politeness:** robots.txt sets `crawl-delay: 10`. `prov_fetch` now raises the interval for that HOST only (`HttpClient.set_host_throttle`), so the run waits 10 s between legnb.ca requests without slowing anything else. A session's journals and bill pages take 20–30 minutes.
- **What it does:**
  - **Listing:** `/en/house-business/journals/<leg>/<sess>`. English files only ("e"; the French "f" files would count every division twice). File names are taken as listed, backslashes turned; where a date is listed twice the highest revision wins (`47230615e2.pdf`).
  - **Roster, dated by session:** the site lists only current members. For a past session the roster is the **compiled Journal's members page** (constituency and member), read by x-position (`prov_fetch.pdf_rows`). Its by-election footnotes date the terms: Susan Holt from 24 April 2023, Denis Landry to his resignation on 30 November 2022. The compiled Journal names its own session and is checked: the 60-3 listing links a file named for 2022–2023.
    - For the current legislature, when no compiled Journal exists yet (61-1 and 61-2), the roster is `/en/members/current`, with party but undated.
  - **Party at the vote, dated to the sitting (3 October 2026).** The compiled Journal prints no party, but every daily Hansard prints a "LIST OF MEMBERS BY CONSTITUENCY" with party codes and a legend ("Fredericton West-Hanwell (I) Dominic Cardy", 15 June 2023). For each division day that list is read (file names from `/en/house-business/hansard/<leg>/<sess>`), each member resolved unique-or-nothing, and the party stored as a party-only term (source `party-hansard`) spanning the sittings seen; `prov_store.refresh_party` writes it onto the votes. A day whose own Hansard is truncated is covered only by lists read either side; a party that differs between them leaves the day NULL. Today's party from `/en/members/current` is never used for a vote. Elections NB answers 403 from the laptop and was not needed.
    - Party-only terms never make anyone a member: `prov_names` resolution and `term_for` ignore any term whose source starts `party`.
  - **Bills:** the session's bills listing gives every stage date ("2nd Reading Passed: 5/11/2023", "Defeated"). For bills with a stage in the window (all, without one), the bill page gives the type, the sponsor and the English HTML text (`Bill-52-e.htm`), classified per passage.
  - **Divisions:** "on the following recorded division: YEAS - 26", three columns of "Hon. Mr. Holder", "Ms. M. Wilson", then "NAYS - 20". The question is the item from its start ("Pursuant to Notice of Motion 50 ...", "Debate resumed on ... Bill 46"), so a committee report read earlier the same morning does not classify the division.
  - **A unanimous recorded division prints YEAS only** (Motion 36 as amended, 8 June 2023: "YEAS - 44" and the next item). No NAYS total is printed, so none is checked; the 44 must all resolve, and the division says "no NAYS list printed (unanimous)".
  - **A division's bill is its own item's**, the last mention winning, including "The Order being read for third reading of Bill 37 ... on the following recorded division" (16 June 2023, where Bill 32's voice third reading came just before).
  - **Voice decisions:** "the question being put that Bill 52 be now read a third time, it was resolved in the affirmative." with no division, and the "following Bills were read a third time:" lists.
  - **Bill text:** the English HTML first, the PDF if the HTML is empty (`Bill-57-e.htm` in 60-2 is served as 0 bytes), and a gap if neither gives text.
  - **Cross-check:** every second or third reading the bills listing dates to a day whose Journal was read must be in that Journal, divided or on voice. A miss is a gap.
- **Fixed in the shared resolver:** "M." after another honorific is an initial, not Monsieur. "Mr. M. LeBlanc" and "Ms. M. Wilson" had come back ambiguous, and all five divisions of 15 June 2023 were gaps until it was fixed.
- **Known limits:**
  - Hansard is not read (bilingual two-column PDFs). The 20 November 2025 Hansard is truncated at source, and so is the **Journal** of 9 June 2023 (129,024 bytes, no `%%EOF`, on two fetches). Any record like them is stored `unreadable` and stays owed (tested); that day's listed readings are not cross-checked.
  - The Journal of 20 November 2025 prints "Mr. Russel" for Kevin Russell twice. A reviewed alias (`config/prov_record.yaml`, checked against the third division that day, which prints "Mr. Russell") clears both, on that day and in that Journal only.
  - **Unanimous divisions** (YEAS only, as on 8 June 2023) keep the existing rule: the YEAS total is printed and checked; no NAYS total is printed, so none is checked.
  - A past session with no compiled Journal has no roster unless a reviewed `roster_bridges` entry gives one (57-1). 56-4 has neither: its divisions come back as gaps (known, below).

- **The 2010 backfill's gaps (2 October 2026).** CI run 37026741496 read 56-4 to 58-1 before its clock ran out (58-2 to 61-2 not started) and stored 23 recorded divisions (2 tally ok, 21 gap), 224 voice decisions, 987 votes with 899 unresolved, and 268 gaps. By cause:

  | Cause | Gaps before | After |
  |---|---|---|
  | Bills-listing reading not found in the day's Journal | 207 (57-2 59, 57-3 61, 57-4 87) | 5, all bills-listing date errors (known) |
  | Tally check failed | 21 (all 57-x: no roster) | 8 of 243: 56-4's 7 (no roster, known) and 61-1's "Mr. Dawson" (below) |
  | "no Hansard listed" + "no party at the vote", per division day | 16 + 16 | 0 (one gap per session instead) |
  | No roster for the session | 6 (56-4 to 58-1) | 1 (56-4) |
  | No daily Journals parsed from the listing | 2 (56-4, 57-1) | 0 |

  The 899 unresolved votes were all the 21 divisions without a roster; the 207 listing misses were all the voice reader. Fixed, each from a fixture of a real page (`tests/test_prov_nb.py`, the `Backfill2010*` classes):
  - **Listings.** 56-4 and 57-1 name their files with no sitting number (`100416e.pdf`), so nothing was listed. 57-2 to 58-3 label the compiled Journal "Journals 2011 - 2012", not "Journals (Compiled)", so no roster was read for 57-2 to 58-1 although every one is online. A link outside the journals folder (60-1's "October 4, 2022" is a Question Period transcript) and a day linked only to a French file are gaps.
  - **Rosters.** The 2011–2016 members pages draw each row as one fragment padded with spaces; footnotes are read for every form printed 2011–2023 (a by-election, a resignation or death with no by-election, a resignation marked on the successor's row, a vacant seat, a renamed riding). A successor named only by "X resigned" starts the day after the vacancy, the bound the seat sets. A mark printed twice (58-1: "*" on Fairgrieve and Savoie, over two by-election notes) binds only through a reviewed row. Reviewed `roster_rows` in `config/prov_record.yaml`: Soucy's row has one space between the columns (57-2); "Wes McClean" (57-2, 57-3) and "Pan Lynch" (58-1 to 58-3) are misprints; "DanielGuitard" (58-3); Dubé's row is in an unmappable font (58-4); the 60-2 footnote's "Daniel Guitar"; the 58-1 by-election pairs. Each names its document, the row as printed and a second record.
  - **57-1** lists no compiled Journal. A reviewed `roster_bridges` entry reads the 57-2 members page as it stood on 23 November 2011 (55 members, Blaney for Rothesay). Evidence: the 57-2 page footnotes its only change; Legislative Activities 2010 and 2011 record no by-election or resignation after the 2010 election; no 57-1 Journal records a member taking a seat or resigning (scanned; the same scan finds Flemming's by-election return in 57-2). All 5 divisions of 57-1 tally.
  - **Journals before 2016 have no blank lines**, so the bill lists ("The following Bills were read a third time:") were never found: they are read line by line now. Also: "where" for "were" (30 May 2012), "Private Bills" with titles ending in ";" over a page break, "read a third time and passed:", the older running heads ("218 March 2458-59 Elizabeth II", "March 26 225Journal of Assembly"), "the motion for second reading of Bill 57 was defeated", "Debate resumed on the motion for second reading of Bill 23 ... the motion was defeated", "Hon. S. Graham" (a minister with no Mr.), "YAYS" (20 December 2011, 29 May 2013), and Committee of the Whole divisions.
  - **Two members, one folded surname.** "Mr. MacDonald" and "Mr. Macdonald" (Kirk and Brian, 57th and 58th) are told apart by their capitals, only when the resolver found them ambiguous and only one candidate's surname is spelt exactly so. "Hon. Ms. Landry"/"Hon. Mr. Landry" and "Ms. LeBlanc" (58-1) by reviewed `titles`, each read where the record joins the title to the full name (Bill 3's "By Hon. Ms. Landry" and its bill page's sponsor "Hon. Francine LANDRY"; "Mr. Bernard LeBlanc, Member for Memramcook-Tantramar"): a candidate whose reviewed title is the other one is ruled out.
  - **Guards.** A Journal whose own date is not the listed day is a gap and nothing is stored for the day (57-3 "May 7, 2013" is the Journal of 8 May; 57-4 links May 20 and 21, 2014, to the 21st's file; 58-2 does the same on 5-6 July 2016). An English file holding the French Journal is a gap (58-1, 11 March 2015). A Journal printing more recorded divisions than are parsed is a gap, never ok (it caught "YAYS"). A re-read sitting replaces everything stored from it. Sittings are keyed by day, not file.
  - **Bill pages named with accents** ("...Filles-de-J&#xE9;sus-Moncton", 58-2 Bill 17) crashed the run: the backfill would have stopped at 58-2. Non-ASCII is percent-encoded now.
- **The CI repair** is one `provinces: nb` dispatch (since 2010-01-01). `owe_stale` makes every sitting stored 'ok' before 3 October 2026 owed (the 181 sittings of the 2010 backfill, 110 of them 'ok' and empty, plus 61-2's 12), so they are read once more; gap and unreadable sittings are re-read as always; `owe_listed` re-reads any 'ok' day missing a listed reading. The rosters of 57-1 to 58-1 are read (the store holds none).
- **End to end** (scratch copy of the published store, the CI backfill command through a caching client, every page fetched live once at the 10-second crawl-delay): the published store (23 recorded divisions, 2 tally ok, 987 votes, 899 unresolved, 88 with a party, 224 voice decisions) becomes **243 recorded divisions, 235 tally ok, 10,269 votes, 311 unresolved (all 56-4's), 7,473 with a dated party, 2,511 voice decisions**, 834 sittings, 1,001 bills. Every session from 57-1 to 61-2 tallies but one division (61-1, below). Gaps 268 -> 67, of which 56 are known and the rest are truncated Hansard PDFs or 61-1. The 2 previously passing divisions (61-2) are unchanged, vote for vote, party for party; none of the 224 earlier voice decisions is lost. Partisan check: Bill 11 of 57-4, third reading 4 December 2013 (33-9), Premier Alward and Higgs Yea, Gallant and Boudreau Nay; Bill 5 of 58-1, third reading 19 December 2014 (26-20), Premier Gallant and Boudreau Yea, Higgs and Alward Nay; 29 November 2018's wage sub-amendment (22-26), Premier Higgs Nay, Gallant Yea. **Duration:** the run made 2,196 requests; the 1,621 fetched live averaged 9.9 s at the crawl-delay, so a CI re-run is about **6 hours: two `provinces: nb` dispatches at `minutes: 300`** (the second resumes; nothing read cleanly is fetched again).
- **Left open:**
  - **61-1 has no dated roster.** No compiled Journal yet, so the roster is `/en/members/current`, which lists today's members: Mike Dawson ("Miramichi West" in the 61st) is not on it, so 28 November 2024 is a tally gap and his Hansard list entry is unknown. It clears when 61-1's compiled Journal is published, or with a bridge like 57-1's.
  - **Journals served at exactly 129,024 bytes** (60-2: 15 Nov 2022, 30 Mar 2023, 9 Jun 2023; 61-1: eight days of 2024-25; 61-2 14 May 2026 at 161,280): the same size twice, on two days' fetches. It may be the server or our client; not investigated. They are stored `unreadable` and stay owed. Only 60-2's are known gaps.
  - **Hansard lists are sparse in 58-3 to 59-3** (58-3 lists 2 transcripts in 48 sittings). A day with no list is covered by the nearest listed days either side when they agree (the existing rule): in 58-3 that is 4 November 2016 and 9 February 2017 around 8 December 2016. 4 days have no party.
  - 59-3 Bill 1's page answered HTTP 500 once.
- **Party at the vote before 58-3 (Christopher, 7 October 2026: from the election reports).** The Hansard page lists transcripts from 58-3 (November 2016) on; for 56-4 to 58-2 one gap per session says so. The 58th: the party each member was elected under, from the Chief Electoral Officer's reports tabled in the House (general election of 22 September 2014, 58/1/tabled_documents/3; Saint John East by-election 2014, same folder; Carleton by-election 2015, 58/2/tabled_documents/1), carried to the member's first Hansard list only where it prints the same party (`prov_nb.fetch_election_results`, `carry_election_party`); a member who changed has no party until Hansard dates one; a member with no list (Alward, resigned May 2015) is carried to the end of his roster term only while the seat distributions the by-election reports print (2 December 2014 and 29 October 2015: L 26, PC 22, Green 1) reconcile. All 50 members matched, all 49 with a 58-3 list agree, both distributions reconcile: **58-1 and 58-2 go from 0 to 1,025 of 1,025 votes with a party** (on a copy of the published store, sha f91609d7; no vote's earlier dated party changed). The 57th stays NULL (1,284 votes): its 2010 report is not tabled on legnb.ca, and Elections NB, at electionsnb.ca and on gnb.ca, answers 403 (known gap). Every collect of a 57th or 58th session derives the carry again and refreshes `party_at_vote` for the whole Legislature, so the CI re-run sets it without re-reading a Journal.
- **Known gaps** (`config/prov_known_gaps.yaml`): 56-4's roster and its 7 divisions; the 7 sessions with no Hansard (party); the four misfiled days (57-3 7 May 2013, 57-4 20 May 2014, 58-2 5 July 2016, 59-2 28 May 2019) and 60-1's Question Period link for 4 October 2022; the French file of 11 March 2015; 60-2's two truncated Journals; bills-listing date errors (58-1 Bill 14, 58-3 Bill 16's hoist amendment, 60-1 Bills 2, 4 and 21). Each with its evidence.
- **Decisions (New Brunswick backfill), taken by Christopher on 7 October 2026: yes to all four.**
  - **Party before 58-3:** from the election reports, as above; the 57th stays NULL.
  - **56-4 (January-April 2010, 7 divisions):** Christopher has asked the Legislative Library for the compiled Journal; the 7 stay known gaps until it comes.
  - **The 57-1 bridge** (`roster_bridges`): approved 7 October 2026.
  - **`titles` and the `roster_rows` `elected:` field:** approved 7 October 2026 as reviewed-fact types.

### Newfoundland and Labrador (step 8): `src/ingest/prov_nl.py`

- **The record is Hansard, not the Journal.** The scope proposed the Journals. Read live, they print **no totals** ("Ayes Nayes", then names), so there is nothing to check a tally against, and the 51st General Assembly's are not posted. Hansard (Word-HTML, one file per sitting) reads every name standing and then the Clerk's count, "Speaker, the ayes: 21; the nays: 14". The count is the printed total.
- **What it does:**
  - **Listing:** the session's Hansard calendar (`/HouseBusiness/Hansard/ga48session1/`); file names as linked.
  - **Divisions:** one per "please rise" call that the Clerk answers with names. Handled variants: "please stand" in Committee of the Whole, counts in words ("the nays: nine"), "ayes: 25" without "the", lists interrupted by "SOME HON. MEMBERS: Hear, hear!", the Chair's aside before the Clerk, and a call the Speaker withdrew ("please rise. Sorry."). A division whose count was never read (Committee of the Whole, 12 May and 6 December 2016, 12 October 2022) is stored with NULL totals and is a gap. From the 50th Assembly: names read by a "TABLE OFFICER" (or "Table Officer"), "SOME HON. MEMBERS: Hear, hear!" between the call and the names, a list broken off with a dash and resumed ("Jeff Dwyer – ... CLERK: – Pleaman Forsey"), a list the Clerk starts again, and a unanimous vote with no call for those against ("the nays: 0" or "zero"; any other count without a list is a gap).
  - **Roster:** current members from `js/members-index.js` (named by `/Members/members.aspx`; party undated). For past years the only official list is the annual **Members' Attendance summary** (one PDF per calendar year, "all Members ... including those who resigned or were elected"). Each member gets a calendar-year term with district and no party. Both layouts seen are read: "Surname, Given" (2022) and given name first (2016).
  - **Names:** Hansard reads familiar names ("Eddie Joyce", "Pam Parsons", "Sherry Gambin-Walsh"); the summaries print formal ones ("Joyce, Edward", "Parsons, Pamela", "Gambin-Walsh, Sheryl"). A full name that does not resolve is retried as initial plus surname, the Journal's own form, still unique-or-nothing. Hyphen and space are the same in a surname (the 2016 PDF drops the hyphen).
  - The 2023 summary prints "LOA" (leave of absence) where the counts go; it is read as a count cell. The 2025 summary is set upside down and is read in reverse; the 2024 summary is a scan with no text.
  - **`ROSTER_CORRECTIONS`:** one entry. The 2022 summary prints "Dempter, Lisa"; Hansard and the Journal print Dempster. Without it every 2022 division would be a gap. **`DISTRICT_CORRECTIONS`:** the 2022 and 2023 summaries print "St. Barb"; the 2025 summary, the 2024 scan and the Roll of Members print St. Barbe.
  - **The 2024 roster, bridged (3 October 2026).** No OCR (tesseract is not on the laptop, and the bridge needs none). `bridge_year` builds 2024 from the 2023 and 2025 summaries and the four 2024 by-elections in `config/prov_record.yaml`, read from the Elections NL by-election reports (vacancy and swearing-in dates) and checked against the 50th Assembly's Roll of Members: Brazil resigned 29 Dec 2023 (Hutton sworn 21 Feb 2024), Bragg died 22 Jan 2024 (McKenna sworn 2 May), Warr resigned 1 Mar (Paddock sworn 26 Jun), Osborne resigned 8 Jul (Korab sworn 13 Sep). A member in both summaries for the same district (surname plus initial: "Dinn, James"/"Dinn, Jim") with no vacancy there sat all year; anyone else gets no term and is a gap. Result: 43 members, which is the scan's 42 rows (read by eye to check) plus Jim McKenna, whom the scan omits although he voted from 2 May 2024. All five 2024 divisions tally (155 votes).
  - "Scott Reid, Lucy Stoyles and Perry Trimper" (2 May 2024): names joined by "and" are split.
  - **Label aliases:** "Lloyd Parrot" (19 October 2022), checked against the same day's Journal ("L. Parrott", same place in the Ayes).
  - **Bills:** the progress-of-bills table (stage dates, loose formats such as "Decd. 14/2016") and each bill's HTML text, classified per passage.
  - **Voice decisions:** Hansard's formal record line, "On motion, a bill, '…', read a third time, ordered passed … (Bill 43)", with no division on that bill and stage that day. **Cross-check:** every listed second or third reading on a read day must be found.
- **Known limits:**
  - **Party at the vote: the current Assembly only.** The House's History of the Standings (`/Members/HistoricalStandings.aspx`) gives the parties returned at the 14 October 2025 election (21 PC, 15 Liberal, 2 NDP, 2 Independent) and every change since, dated (Keith Russell to Independent/Non-Affiliated, 14 September 2026). With the members page it dates everyone from the election: a member never named keeps today's party; a named change is dated; the party before it is taken only when the counts leave one answer (Russell was PC). Counts that do not reconcile, or a sentence not understood, store nothing. All 416 votes of 51-1 have a party.
  - **No party for earlier Assemblies.** They have no standings page. Elections NL's reports give a label on election day only, and for the 50th Assembly they conflict with the Chief Electoral Officer's own later statements: the 2021 report lists Lela Evans (Torngat Mountains) as the PC candidate, elected with 88.8%, and only two NDP members elected, while the by-election reports of December 2023 to July 2024 each give three NDP members, and Hansard reads her name with the NDP members until May 2024 and with the PCs by December 2024. No official record dates any change, so 48-1 and 50-2 votes carry no party. Those reports' seat counts are also unreliable (the March 2024 report gives 23 Liberals and one vacancy when two seats were empty).
  - **Committee of the Whole divisions with no count** (8): each was re-read (12 May and 6 December 2016; 12 and 18 October 2022). The record reads the names and then "The motion is carried" or "The amendment has been defeated", never a number, and the Journal prints names without totals. They stay unplaceable.
  - Roster terms are a calendar year wide **unless an official record dates them** (since 7 October 2026, below): a by-election report or a general election day. Resolution leans on the name, so an over-wide term matters only when two members share a surname and initial in the same year.
  - A member's key follows the summary's spelling, so "Sherry" (2016) and "Sheryl" (2022) Gambin-Walsh are two keys, and so are Joan Burke (2011) and Joan Shea (2012-2014), Tom (2011-2018) and Thomas (2019-2024) Osborne. Per-date resolution is right; a career view would need a join (`same_person`, not added).
  - The Journals are not read; three were read by hand as the second record of reviewed facts (below).

- **The 2010 backfill's gaps (7 October 2026).** CI run 37044556156 (2 October 2026) read 46-2 to 51-1 and stored 189 recorded divisions (105 tally ok, 84 gap), 1,780 voice decisions and 6,465 votes, 183 unresolved, with 166 gaps; the speeches backfill resolved 115,975 of 128,146 speaker turns (90.5%). By cause, before and after (the scratch re-run below):

  | Cause | Before | After |
  |---|---|---|
  | Tally: a label resolved to nobody, the roster's fault (the 2012-2014 summaries print "Jerome Kennedy, Q.C." and "Darin King, Ph.D", read as surnames "Jerome Kennedy" and "Darin King"; Ray Hunter's 2012 row is set the other way up and was dropped; Joan Shea is "Ms Burke" in Hansard until June 2012; the 2013 summary leaves out Yvonne Jones and Jerome Kennedy, who resigned that year) | 30 divisions | 0 |
  | Tally: two members fit a bare surname, the term being the whole calendar year (Paul and Bernard Davis, 2015 and November 2018; Darin and Neil King, Jim and Derek Bennett, 2015; Paul and James Dinn, spring 2019; Kelvin, Kevin and Andrew Parsons, October 2011), or only the title telling them apart (Ms/Mr. Bennett 2014-2018, Ms/Mr. Osborne 2011) | 23 | 0 |
  | Tally: the list or the count not read | 18 | 0 |
  | Tally: a name the record misspells ('Tom Osbourne', "Loyola O' Driscoll", 'Ms. Gambin- Walsh', 'Mr. Brown' for Mark Browne) | 4 | 0 |
  | Tally: no 2010 roster | 1 | 0 (the 2009 and 2010 summaries were text after all; the one 2010 division left prints no count, below) |
  | Tally: Committee of the Whole names with no count (2016, 2022) | 8 | 8 |
  | Tally: the record's own (below) | hidden behind the causes above | 4 |
  | Clerk's counts with no division read before them (the calls the parser did not know, two counts the Clerk corrected, the Speaker repeating a count) | 28 | 0 |
  | Listing misses | 52 | 8 (progress-table date errors) |
  | 2010 attendance summary unread (taken for a scan); truncated Hansard (3 October 2022) | 1 + 1 | 0 + 1 |
  | **Unresolved votes** | 183 (124 nobody, 53 two members, 6 misspelt) | 2 (in uncounted Committee divisions of 12 October 2022) |

  The speech turns left unresolved had three causes: no 2010 roster (5,221 turns, the whole year); the roster causes above (2012-2015 and 2018, about 4,900 turns); and people who are not members, witnesses before Committee of the Whole ('MR. CHAULK', November 2018; 'J. CHEE-ALOY', 'K. AKIMOV', January 2025; 'D. LEVERT', 'M. LADHA', September 2026: about 2,000 turns), rightly nobody's key. A fourth cause hid 18 days entirely: some Word exports open the bold before the paragraph (`<b><p>MR. SPEAKER (Wiseman): </b>`, 12 December 2012 and late 2013), so no speaker was found and the day read as "no speaker turns parsed".

  **2010 (7 October 2026, Christopher: "read the scanned 2009 and 2010 summaries by OCR, and bridge 2010").** No OCR was needed: the two summaries have a text layer. Every row is one line padded with spaces (the heading too, so no heading was found and nothing was read), names on a line of their own ('Brazil, David' / '(elected Dec. 2010)  Conception Bay East - Bell Island  n/a  n/a'), 'n/a' counts and notes in the name or district ('(deceased)', '(elected Nov. 26/09)'). `parse_attendance` reads that layout (fixtures `nl_attendance_2009_pages.json`, `nl_attendance_2010_pages.json`), so 2010 is read like any other year (49 members) and dated by the 2010 by-elections (`by_elections`: Topsail, Paul Davis from polling day 16 March 2010; Conception Bay East - Bell Island, Diane Whalen to her death on 3 October and David Brazil from 20 December; Humber West, Danny Williams to 3 December). Nothing is inferred and no bridge is needed; the names are the Assembly's own text, as in every other year. On the scratch store: 2010's three divisions went from 0 to 2 tally ok (14 June, 5-32; 23 June, 4-33; the third, 19 May, reads 41 names and 'carried unanimously' with no count, a known gap), 115 unresolved votes to 0, and its 5,224 speech turns from 0 to 5,224 resolved. 2011 is now dated from both sides too (33 terms dated inside the year).

  Fixed, each from a fixture of a real page (`tests/test_prov_nl.py`, the `Backfill2010*` classes; `nl_hansard_variants_2010_2022.json`, `nl_hansard_readings_2010_2025.json`, `nl_attendance_20{11..15,18}_pages.json`):
  - **Calls.** A call is now any "those in favour / against / opposed" the Clerk answers with names: 'All those in favour of the motion as put forward by the hon. the Member for ... please stand' (the 'hon.' hid it), 'All in favour'/'All opposed?' (2011), 'All those in favour of the motion?' with no 'please rise' (2012), 'All those for the motion' with the Nays called first (27 November 2013), 'in support of' (2014), 'in favor' (2017), 'all Members who are in favour' (2018), 'All those please signify by standing' (2019), 'all those Members against' (2019), 'All those not in favour or against' (2022). A call that does not ask members to rise is taken only when the Clerk answers it at once, as a whole sentence, with no 'Aye'/'Nay'/'Carried' between: Committee of Supply's voice calls ("All those against, 'nay.' Carried. ... CLERK: Office of the Executive Council, ...") are not divisions.
  - **Lists.** A list the Clerk takes up again after 'Order, please!' is followed to its end (with or without a dash; an ellipsis counts as a dash); one started again from the top (same first name) replaces itself; 'and Mr. Russell', 'Ms. Michael; Ms. Rogers', 'Mr. Byrne. Ms. Dempster' are split; 'CLERK: Speaker, on the amendment, the ayes ...' is the count, not names.
  - **Counts.** "the 'ayes' thirty-one", 'the ayes; forty;', 'it is unanimous, thirty-nine ayes', 'it is unanimous: the ayes thirty-four', 'The ayes: 31; there are no nays', a count read after an interruption (up to 3,000 characters, before the next call; the note says how late), the Speaker repeating the Clerk's count.
  - **Voice readings (the 52 listing misses).** 'read a third, ordered passed', 'read third time', 'On motion, Bill 26, as amended, read a second time', 'read the second time'; the Speaker's own words after the Clerk reads the title ('(Bill 1) MR. SPEAKER: This bill has now been read a second time', also 'has now been a second time'); 'CLERK: The second reading of Bill 23.'; the question put on a named bill, carried, and the Clerk reading that bill's title with no formal line after it. A formal line that contradicts the Clerk just before it ('(Bill 6) On motion, Bill 14 read a second time', 30 April 2018; 'Bill 2' for Bill 23, 5 June 2014) records nothing; the bill the Clerk read is recorded only by its own words, or the day is a gap.
  - **Rosters.** Credentials after a name are dropped; a row set the other way up is joined; the preamble above the heading and the 'Absences' heading line are not members (the 2017 preamble had become the member 'period-atte'); half-day counts ('5.5') are counts. Terms are **dated inside the year** (`date_terms`) from two kinds of official record only: the Elections NL by-election reports (`by_elections`, nine added: 2011 to 2019) and general election days (`general_elections`, from the reports: 11 October 2011, 30 November 2015, 16 May 2019, 13 February 2021, 14 October 2025), read against the summaries either side (and, for the current Assembly's election year, the members page). A member a summary leaves out the year they resign is added up to the vacancy when the previous summary has them in that district. Matching across summaries is by name, never by initial when two members of that surname share it (Kelvin and Kevin Parsons). Roster terms are now stored under `summary-<year>`; a year still under `attendance-<year>` is read again, and members nothing names any more are dropped.
  - **Reviewed facts** (`config/prov_record.yaml`, `nl`): `other_surnames` (Joan Shea, 'Burke'); `titles` (Cathy, Jim and Derek Bennett, Sheila and Tom Osborne, each where Hansard joins title and full name; read by `prov_nl.Titled` for an ambiguous label only); `label_aliases` ('Tom Osbourne' 18 May 2022 and 'Mr. Brown' 15 April 2019, each against the same day's Journal; 'Mr. Brown' 5 December 2017, a Committee division the Journal does not record, against the summary and the same Hansard); `hansard_labels` (27 October 2011, 'Mr. Parsons' is Andrew Parsons: the Journal prints "Mr. Andrew Parsons" in the same list); `hansard_totals` with `replaces:` (14 June 2012, Bill 29's third reading: the Clerk reads 31 and corrects it to 32 before the Speaker speaks; 12 December 2012: six nays corrected to five on a point of order). NL now reads `pn.ReviewedDivisions` as Alberta and Manitoba do; a corrected count the reviewed fact accounts for is not a stray count.
  - **Speeches.** The bold opened before the paragraph is moved inside it.
  - **A re-read replaces** what an earlier read stored from the same Hansard file (divisions are renumbered when the parser finds more).
- **The CI repair.** Votes: one `provinces: nl` dispatch (`since` 2010-01-01; the default `minutes` is ample: the backfill took 28 minutes). `owe_stale` makes every sitting stored 'ok' before `REREAD_BEFORE` (2026-10-08) owed, so all 798 are read once more (710 'ok' plus the 88 gap or unreadable); the rosters are read again (new source names). Speeches: then one `provinces: nl`, `speeches_since: 2010-01-01` dispatch. `speeches_since` alone does **not** re-read a day stored 'ok'; `prov_nl_hansard.owe_unresolved` (also `REREAD_BEFORE`) makes owed every day read before it with an unresolved speaker turn (267 in the scratch run), and gap and unreadable days are read as always. If the weekly reads NL with the old parser after 7 October (it runs Wednesdays) before this is merged, move both `REREAD_BEFORE` dates to the merge day.
- **End to end** (a scratch copy of the published store, sha256 f91609d7..., the CI backfill command then the speeches backfill, through a caching client; all 798 Hansards fetched live once, 3 s apart, robots by both readers; re-run with the 2010 roster): **214 recorded divisions, 201 tally ok** (was 189, 105), 1,819 voice decisions (1,780), **7,645 votes, 2 unresolved** (6,465, 183), 452 with a dated party (416: the 51st Assembly's newly found divisions), 788 sittings ok, 10 not (710, 88). Vote gaps 166 -> 22, every one a known gap (`config/prov_known_gaps.yaml`, `nl`). The 105 divisions that passed before are unchanged, vote for vote and party for party. Partisan check: Bill 29 (Access to Information and Protection of Privacy), third reading 14 June 2012, 32-11: Jerome Kennedy (PC Government House Leader) and Joan Shea ('Ms Burke') Yea, Dwight Ball (Liberal leader) and Lorraine Michael (NDP leader) Nay. 22 January 2015 (Committee, 39-3): 'Mr. Davis' is Paul Davis, 'Mr. King' Darin King, 'Mr. Bennett' Jim Bennett (title); 6 November 2018: 'Mr. Davis' is Bernard Davis (Paul Davis resigned on 2 November). Speeches: **127,872 of 129,918 speaker turns resolved (98.4%; was 115,975 of 128,146, 90.5%)**, the 2,046 left being Committee witnesses; 1,644 more turns found on the 18 days that had none; 272 speeches on our ground (259), none unattributed (14). Speech days not ok 73 -> 6.
- **Left open:**
  - **The 19 May 2010 division** prints no count ('carried unanimously'): a known gap, as 20 November 2013.
  - **The record's own (known gaps):** 20 November 2013 ('The vote is unanimous', no number) and 19 May 2010 ('carried unanimously', no number); 22 January 2015 (the Premier's vote withdrawn after the count; 40 names, 39 counted); 31 October 2018 (names read with no call transcribed); 14 June 2021 (three members added orally after the names); the 8 uncounted Committee of the Whole divisions; 8 progress-table date errors (2010-05-31 Bill 6, 2012-05-02 Bills 3, 5 and 9, 2012-06-19 Bill 33, 2014-05-22 Bill 8, 2014-06-05 Bill 24, 2022-05-18 Bill 62).
  - **Five speech days still parse no turns** (18 March 2018, 3 and 18 April 2019, 2 March 2020, 16 March 2023): not investigated; they were gaps before this work too.
  - Two terms are not dated: the 25 November 2014 by-elections in Trinity - Bay de Verde and Humber East have finance reports only (the summary's own note says "elected November 2014"); nothing resolved needed them.
- **Decisions (NL backfill, 7 October 2026):**
  - **2010: settled 7 October 2026** (read, not OCR'd: above).
  - **The new reviewed-fact types and rules: APPROVED by Christopher, 7 October 2026**: `general_elections` (dates from the Elections NL reports), `titles` for NL, a term starting or ending on election day where the member is missing from the next or previous year's summary, and a member the summary omits in their resignation year kept up to the vacancy date.
  - **One key per member: merged** (Christopher, 7 October 2026: "Merge them"). NL keys follow each summary's spelling, so five people had two keys (Gambin-Walsh three). Reviewed `same_person` entries (`config/prov_record.yaml`, each citing the same seat in the summaries, the members page or an Elections NL report, and for Burke/Shea the same minister called "MS BURKE" on 18 June 2012 and "MS SHEA" on 26 November 2012: no record of the change itself was found) are merged by `prov_nl.merge_members` through `prov_store.merge_split_members` on every collect, before anything is resolved, and by the speeches reader after its roster. The key kept is the entry's `keep:` (new, optional; `pn.load_same_person_keep`): the current members page's spelling for a sitting member, else the member's later records: **joan-shea** (joan-burke), **thomas-osborne** (tom-osborne), **sherry-gambin-walsh** (sherry-walsh, sheryl-gambin-walsh), **jordan-brown** (jordon-brown, the 2025 misprint), **james-dinn** (jim-dinn). Votes, terms, speeches (newly, for every province) and sponsorships are re-keyed in place; nothing is fetched. A title read under one key holds for the kept one. On the scratch store: 146 NL member keys -> 140; 183 votes re-keyed (joan-shea 48 votes in all, thomas-osborne 126, sherry-gambin-walsh 115, jordan-brown 54, james-dinn 63); every division's tally, totals, sides and party unchanged; the full CI path from the published store gives the same divisions and the same votes, key for merged key. Kelvin and Kevin Parsons, Sheila Osborne and the other Dinns are untouched (tested).

### Open decisions from New Brunswick and Newfoundland and Labrador (settled 3 October 2026)

Christopher, 3 October 2026: "Fix New Brunswick and NL."

1. **Label aliases: built.** `config/prov_record.yaml` `label_aliases`, each with the document, date, printed form, member, the record it was checked against and why. Consulted only after the normal resolver finds nobody, only on that day and in that document; the tally check still runs. "Mr. Russel" (NB) and "Lloyd Parrot" (NL) cleared.
2. **NL 2024 roster: bridged** from the 2023 and 2025 summaries and the official by-election record, not OCR. All five 2024 divisions tally.
3. **Dated party: New Brunswick complete** from the Hansard member lists; **NL for the current Assembly only** (History of the Standings). Earlier NL Assemblies stay NULL, for the reason above. Coverage in the smoke stores: NB 921 of 921 votes; NL 416 of 2,453 (all of 51-1).
4. **Committee of the Whole with no count: unchanged.** No count exists elsewhere in the record. NB unanimous divisions keep the existing rule (the printed YEAS total is checked).
5. **Taxonomy false positives: documented, not masked.** Neither is a statute name, and the provincial watchlist cannot remove an area. `config/taxonomy.yaml` was not edited.

### Decisions, 2 October 2026 (afternoon)

Christopher: "Leave NL blank, skip NWT and Nunavut, add SDIR".

1. **NL party before the 51st Assembly stays blank.** No hand-keyed party from Elections NL's reports: they give a label on election day only, and for the 50th Assembly they conflict with the Chief Electoral Officer's own figures. Those votes carry no party, and the 5CA sheets say so; nothing is guessed.
2. **NWT and Nunavut are skipped.** Neither is built, scheduled or collected, not even as evidence. They are consensus legislatures with no parties, and recorded votes are rare. The scoping notes below are kept in case the decision is revisited.
3. **SDIR joins the key committees** (federal; tools/ca_committees.py, `KEY_COMMITTEES`), read in full rather than by study title. Recorded here because it came in the same message.

### Quebec (step 7, built early at Christopher's "all provinces"): `src/ingest/prov_qc.py`

- **robots.txt, read in full.** `urllib.robotparser` keeps only the FIRST `User-agent: *` group, and assnat.qc.ca writes one group per rule: the standard parser reported `/json/` (the vote register's feed) ALLOWED and did not match the six disallowed `Process.aspx` documents. `src/prov_fetch.star_rules` now reads every group naming `*` or us, longest rule first, for every province. The vote register is never requested.
- **Sittings:** the session's sitting index shows one month; other months come only through the page's own ASP.NET form, so `HttpClient.post_form` posts the month select (throttled, honest UA, no retry). Every procès-verbal (PV) URL is taken from that listing; the `MediaId`s cannot be guessed. A reply that shows a different month from the one asked for is a gap.
- **Divisions: the procès-verbal annex, in every era.** The scope said names left the Journal des débats with electronic voting (2025) and that earlier years print them in the Journal. Both are true, but **the PV annex prints every named vote with names AND party in both eras** (checked on the PVs of 29 Oct 2013, 14 and 16 Jun 2019, Apr–Jun 2023, 30 Oct 2025 and 1 Apr 2026), so one parser serves 2013–2026 and the Journal is not read for votes.
  - The annex is four columns of "Surname (PARTY)", read top to bottom. A riding that disambiguates a surname sits on the line UNDER its name, in its own column, so in the text stream it lands beside the wrong name ("Lamontagne (CAQ) (Soulanges)" is Picard's riding). It is read from pypdf's layout fragments with x-positions: column edges from where many cells start (one stray start is not a column), name rows re-cut at the edges, cells ordered column by column across page breaks, a "(Riding)" or "(PARTY)" cell attached to the name above it.
  - Layout traps met and handled, each with a test: the layout engine's spacing ("D 'A mour" in 2013, repaired from the plain text's spelling); names that wrap inside their cell from 2023 ("Lakhoyan Olivier" / "(PLQ)"); a cell whose recorded end swallows its neighbour; an annex with no "ANNEXE" heading (14 Jun 2019); "(Identique au vote n° 109)" (2 Jun 2023).
  - The body gives each vote's question, the record's own result words and the printed totals ("Pour : 73 Contre : 35 Abstention : 0"); the annex's own counts must agree with them. The vote's item is cut at the last section heading before it and loses the previous vote's "En conséquence, ..." line, so a vote is not classified on the notice that preceded it.
- **Party at the vote is the annex's, as printed** ("Dubé (IND)", "Dufour (IND) (Abitibi-Est)"). The roster's party is the party a member was elected under and is undated (`party_dated = 0`).
- **Roster, dated:** "Membres de l'Assemblée nationale par circonscription" (`/fr/patrimoine/depcir/`, ten letter pages that link each other) gives every riding's members election by election with member ids; election dates from `election.html` (the legislature number is the row's ordinal from 1867), by-election dates from `partielles.html`, departures from the remarks. Rows before 1960 are not stored.
  - **depcir is incomplete for the 43rd legislature** (no 2022 row for Vanier-Les Rivières, Taschereau, Vaudreuil; nothing for the 2025 Terrebonne by-election; two rows printed without a link). Sitting members whose terms stop short are completed from their own page's dated mandates (14 on 2 Oct 2026). Members a PV names who are still unknown (Fitzgibbon, resigned 2024) are completed lazily from their page's prose biography ("Élu député de Terrebonne ... en 2018. Réélu en 2022 ... date de sa démission"), and only then retried.
  - Guards: a riding whose rows run backwards in time (a missed heading: FABRE's extra anchor filed Gilles Ouimet under Duplessis) is a gap and stored not at all; a row with no member is a gap.
  - **The President does not vote**, and the annex disambiguates surnames among those who vote: "Roy (CAQ)" in 2025–26 is Suzanne Roy, because Nathalie Roy presides. A candidate is set aside only when her own page dates her presidency on that day ("Présidente de l'Assemblée nationale depuis le 29 novembre 2022"). "H. Plante" is resolved as Marc H. Plante only because the printed form ends his full name.
  - **The 5 October 2026 election:** nothing assumes the 43rd legislature. The last terms stay open until `election.html` lists the next poll; the roster is re-read when a week old.
- **Bills:** the session listing gives each bill's OWN page link, so a reinstated bill keeps its first session's key (Bill 94, adopted in 43-2, is `qc-43-1/94`) and a vote naming "projet de loi n° 94" in 43-2 is joined through the listing. The bill page gives author (member id), type, every stage with its sittings and outcome notes, the presentation PDF (French only) and the English page (`title_en`). `--bill N` reads only those bill pages.
- **Voice:** a decided stage whose final sitting has no "Vote :" note is stored as `kind = 'voice'` with the page's own words (Bill 11's principle, 4 Apr 2023; Bill 94's report stage, 28 Oct 2025, "à la majorité des voix").
- **Cross-check:** every bill-page "Vote : Pour X, Contre Y" on a day whose PV was read must be a recorded division on that bill with those totals. Where the PV's words name no bill ("Sur le rapport de la Commission des relations avec les citoyens", Bill 11's report stage) and exactly one vote that day has those totals, the bill page joins it; two candidates stay unjoined and a miss.
- **Classification in French:** `config/taxonomy-qc.yaml` (master `docs/keyword-taxonomy-qc.md`, v0.1, same area keys) on French titles, bill texts and each vote's own words; the English taxonomy on English titles only. Statutes cited with their chapter number, and the capitalised heading an omnibus bill gives each Act it amends, are masked. Measured hit list in the taxonomy doc.

**Live smoke runs (2 October 2026, one scratch store):**

| Window | PVs read | Recorded divisions (tally ok) | Voice | Votes (unresolved) |
|---|---|---|---|---|
| 40-1, 29 Oct 2013 | 1 | 1 (1) | 0 | 110 (0) |
| 41-1, 5 Jun 2014 | 1 | 1 (1) | 0 | 116 (0) |
| 42-1, 4–16 Jun 2019 | 10 | 35 (35) | 16 | 3,862 (0) |
| 43-1, 4 Apr–7 Jun 2023 | 24 | 67 (67) | 1 | 7,047 (0) |
| 43-2, 28–30 Oct 2025 | 3 | 6 (6) | 1 | 601 (0) |
| 43-2, 31 Mar–2 Apr 2026 | 3 | 36 (36) | 0 | 2,837 (0) |

146 recorded divisions, all tally-matched, 14,573 votes, none unresolved, no bill-page tally missed. 993 members, 2,253 dated terms. The 42-1 bill sweep read all 182 bill pages and texts; 8 are on our ground (21 laicity; 70 and 599 conversion therapy; 73 assisted procreation; 83 amending the end-of-life care Act; 399 presumed consent for organ donation; and two budget bills, 74 (an assisted-procreation tax measure) and 82 (digital identity), which the judge should weigh). A dry run of 43-3 (the session dissolved for the election) lists 17 sittings and 89 bills.

- **Bill 21** (`qc-42-1/21`), adoption 16 June 2019, PV vote no. 165, **73–35, tally matched**: Legault and Jolin-Barrette Yea (CAQ), Nadeau-Dubois Nay (QS), Hivon Yea (PQ), Arcand Nay (PLQ). Report stage 73–35 (no. 164) and principle 77–38 (4 June, no. 131) also matched. Areas [8].
- **Electronic era, from the annex:** Bill 1 (Loi constitutionnelle de 2025), principle 1 April 2026, no. 139, **68–31–1, tally matched**, Pierre Dufour abstaining as "(IND)"; Bill 94 adoption 30 October 2025, no. 53, **70–27**, Drainville and Legault Yea, Nadeau-Dubois and Virginie Dufour (PLQ) Nay, areas [6, 8]; Bill 9 (renforcement de la laïcité) adoption 2 April 2026, 77–27.
- **Bill 52 (end-of-life care), recorded votes:** principle 29 October 2013 (`qc-40-1/52`, no. 64) **84–26**, Hivon and Legault Yea; reinstated as `qc-41-1/52` and adopted 5 June 2014 (no. 10) **94–22**, Couillard and Barrette Yea. Areas [2].
- **Bill 11 (MAID expansion, 2023):** principle 4 April 2023 **passed without a recorded vote** (stored as voice); report stage 2 June 107–0 (no. 111, joined by the bill page) and adoption 7 June **103–2–1** (no. 113), both tally-matched. Areas [2]. The scope's "107–0 at principle" was the report stage.
- **Known limits:**
  - Journal des débats speeches are not read (`prov_speeches` stays empty for qc).
  - A vote's bill is the last bill its own item names, else the bill page's tally join; a motion that cites a bill in its considerants is joined to it, stage "Motion".
  - A former member missing from depcir and named by no PV read stays absent; a lazily completed member's last term ends at the dated resignation if the biography gives one, else stays open.
  - The French layer is an AI draft with no Quebec reader yet.

**The 2010 backfill (CI run 37048289773, 2 October 2026) and its repair (7 October 2026).** The run stored 3,121 recorded divisions: 2,827 tallied, 294 failed; 157 bill-page tally misses; 316,585 votes, 1,147 unresolved; 475 gaps (294 + 157 + 24 sittings the listing gives no PV link). Re-read on a scratch copy of the published store (sha256 f91609d7) exactly as the re-run will (221 sittings: every one not 'ok', plus 70 owed by the misses), PVs fetched once at 3 seconds:

| | Before | After |
|---|---|---|
| Recorded divisions tallied | 2,827 of 3,121 | 3,079 of 3,119 (2 stale rows removed) |
| Tally gaps | 294 | 40: 19 record errors (`config/prov_known_gaps.yaml`), 21 bare homonyms |
| Bill-page misses | 157 | 12 |
| Votes / unresolved | 316,585 / 1,147 | 339,245 / 21 |
| Previously tallied divisions whose members or sides changed | | 0 (bill joins changed on 152, 145 of them now backed by the bill page's own tally, was 1) |

Causes of the 294, and the fix for each (all in `src/ingest/prov_qc.py`, each with a test from the real page in `tests/test_prov_qc.py`):

- **The 2008–2012 annex prints surnames only (190: all of 39-1 and 39-2).** "Arcand Cloutier Leclair Reid", a riding under its name where two VOTING members share it. Two encodings: 2011 writes a fragment per name (the layout engine splits "Dia mond", joined back from the plain text, `bare_tokens`); 2010 writes a whole row as ONE fragment with ridings in [brackets], cut into names that take the columns left to right. A riding that wraps alone on its line has no usable x-position and lands under the wrong name ("Deltell (Marguerite-D'Youville)"); the riding names one seat, so it is moved to the one ambiguous bare label of that member's surname in the same list (`place_bare_ridings`; it also fixes 12 February 2020's "Zanetti (QS) (Berthier)"), else stays a gap. Party at the vote is NULL for these years, never invented. These labels never fetch a member page (`lazy=False`).
- **Layout traps (about 40):** "(Vote No. 70)"; "Vote n° 309" without brackets; "Arcand (PLQ))" (22 Nov 2012), "Arcand ((PLQ))" (12 Nov 2014), "Arcand PLQ)" (7 Oct 2015); a glyph run split the same way down a column ("St" / "-Amand (PLQ)") taken for a column (`_edges` now drops a start within 40 pt of a busier one); "auvote"; vote and reference numbers whose glyphs the layout engine misorders ("241" for 421; "(Identique au vote n° 98)" read 89, a real earlier vote) or splits ("2 78"): numbers are read from the plain text in content order, and a reference the plain text does not print is never followed; a list with no POUR/CONTRE heading (13 May 2020, 7 Oct 2015), placed only when the body has one non-zero total equal to the names; "(Identique au vote n° 278)" naming a vote of an EARLIER sitting (7 Apr 2022), taken from the store only if that division is trusted; a heading printed twice ("938", "938" before 940, 20 Apr 2021) or misprinted ("1002" between 1101 and 1103, 9 Jun 2021), and a body number printed twice ("180", "180", 10 Dec 2021), each read from the sequence or left a gap. A re-read now replaces the PV's recorded divisions whole (the stale "241" and "1002" rows).
- **Ambiguous surnames (68 before):** the annex prints "Paradis (PLQ)" without a riding when only one homonym voted. Settled ONLY where the Journal des débats roll call of the same division (the Secretary reads every member by surname and riding, until electronic voting in September 2023) names one of them: 14 `hansard_labels` entries in `config/prov_record.yaml`, generated from the Journal pages and each quoted. France Dionne (member 1985–1997) had acquired a 2022 term from a biography sentence about a former members' association, so every "Dionne (CAQ)" since 2022 would have been ambiguous on a re-read: `parse_bio_mandates` now reads only sentences about election to the Assembly, and every member-page term is re-derived once a run (`recheck_page_terms`; it also removed Claude Simard's 1981 "Élu administrateur ..." term).
- **"Charrette" for Benoit Charette** (14 divisions of 2010, 13 of 2021): `misprints` entries, read only in the named procès-verbaux and days; 2010 checked against the Journal's roll calls, 2021 against the same annex's other lists.
- **Annex and body disagree (19).** The Assembly's rule decides which is the vote: "le secrétaire général communique le résultat à la présidence, qui le proclame à l'Assemblée. Les noms des parlementaires ayant voté ainsi que leur position sont consignés au procès-verbal" (assnat.qc.ca lexique, "Vote électronique"; the same for the roll call). The proclaimed result, as the Journal records it, is the record of the vote. 11 June 2026 (vote 60, Bill 10): the Journal has the Secretary announce "Pour : 102 Contre : 1 Abstentions : 1", the body agrees, the annex lists 103: the annex is wrong and which name is extra cannot be known, so it stays a known gap. 26 September 2024 (vote 311): the Journal has the corrected announcement "Pour : 32 Contre : 72 Abstentions : 1" for the amendment, the annex agrees, the body printed the next vote's 28-72-5: a `hansard_totals` entry with `replaces:`. The 2020–2021 group votes (leaders answer for their groups) read neither names nor totals in the Journal, so their disagreements stay known gaps.
- **Bill joins (124 of the 157 misses were presentation votes).** The body's "projet de loi suivant : n° 391" and "projet de loi d'intérêt privé n° 211" were not read, so 30 May 2019's vote on Bill 391 was filed under Bill 26, named earlier in the item. Sittings stored 'ok' before 7 October 2026 on a day a bill page dates a named vote the store lacks are read once more (`owe_missed`, `REREAD_BEFORE`); a re-read stamps today, so a miss the record causes is never fetched again. One PV misprint this exposed (private bill 219 printed "n° 192", 30 November 2021) is a `bill_corrections` entry.

**What is left (38 tally gaps, 12 misses; Christopher's decisions of 7 October 2026 applied):**

- 17 record errors, each a known gap with its evidence. The two of 7 December 2017 (votes 404-405) now pass: a new reviewed fact, `list_positions`, moves the 20 CAQ members the annex heads "CONTRE - 20" to Abstain, for that one division, only while the annex still prints 20 there, quoting the Journal ("Y a-t-il des abstentions?", "Pour : 89 Contre : 0 Abstentions : 20"); the printed heading stays in tally_note.
- 21 bare homonyms no record names: Picard (CAQ) ×9 and Proulx (CAQ) ×6 in the 2020–2021 group votes (two CAQ members of each name; the Journal reads no names), known gaps by Christopher's decision; Fournier (PLQ) ×4 (9 Dec 2016) and Paradis (PLQ) ×1 (21 Oct 2014), votes the Journal does not roll-call; "Tardif (CAQ) ()" (9 Feb 2022, a riding lost in the layout).
- 12 bill-page misses: mostly unanimous report-stage votes on days with several divisions of the same totals (the join refuses two candidates, by design), and three whose bill page and PV disagree on the totals.
- The 24 "no procès-verbal link" gaps are gone: the sitting index itself marks each of those days "Séance annulée" (22 days from 18 March to 14 May 2020, the COVID suspension; 9 May 2017; 8 June 2018; read 7 October 2026), so the House did not sit and no PV exists. `parse_sittings` reads the mark and the run logs those days instead of owing a PV. A day with no PV link and no such mark is still a gap.
- Still failing the run: Fournier (PLQ) ×4, Paradis (PLQ) ×1, Tardif ×1 and the 12 bill-page misses.

**Re-run:** dispatch "Provinces weekly" with `provinces: qc` (since `2010-01-01`, minutes `280`). It re-reads only the sittings not stored 'ok' plus the ones `owe_missed` marks (about 221 PVs and the bill listings: one dispatch). `gh workflow run prov-weekly.yml -R thejoycething-code/parl-monitor -f provinces=qc -f since=2010-01-01 -f minutes=280`.

**The 44th legislature (general election 5 October 2026).** Nothing to build until it sits (about November). When the session select lists 44-1, the run records "set CURRENT_SESSION" and fails until `CURRENT_SESSION` in `prov_qc.py` is moved (deliberate). The 43rd legislature's terms close when `election.html` lists the 2026 poll; until depcir prints the 2026 rows, sitting members are completed from their own pages (the existing supplement in `fetch_roster`), and the weekly `--roster-only` re-reads the roster. A new President is set aside by her or his own page's dated "Président(e) de l'Assemblée nationale depuis le ...". A new party code prints as "(XXX)" and is read as printed ("PCQ" is already in `PARTIES`). Check after the first 44-1 sitting: that the annex still prints party, that depcir's 2026 rows link member ids, and the first weekly's homonym count (new members sharing a surname print ridings only when both vote).

### Nova Scotia (step 9): `src/ingest/prov_ns.py`

Built 2 October 2026, entirely from CI: `nslegislature.ca` resets the laptop's VPN exit and answers a GitHub runner, so every fixture and every live sample was fetched by `.github/workflows/probe-hosts.yml` on the branch and downloaded as an artifact (`tools/probe_hosts.py`, below). robots.txt disallows only Drupal's admin paths and sets **`Crawl-delay: 10`**, honoured per host (`prov_fetch`), and kept by the module itself if robots.txt ever fails to answer.

- **The record is Hansard.** The Journals stop at the 63rd Assembly's third session (2021). Hansard is an HTML page per sitting, listed per session 45 to a page (`?page=1`, ...), linked as listed: some 2011 sittings live under the French path (`61e-assemblee-2e-session/house_11mar31`), and a part letter appears (`house_24feb27a`).
- **Divisions, three layouts, all read live:**
  - The table layout (seen from April 2019 to 2026): header row YEAS | NAYS (`<td>` or `<th>`), continued in a second table after the page break. Malformed rows are met and handled: rows with no `<tr>` (4 April 2024), cells with no `</td>` (25 March 2025), a continuation that repeats the header (9 November 2023).
  - October 2019: a "YEAS NAYS" paragraph, then a table with its own "Yeas | Nay" header.
  - The paragraph layout (seen in 2010; when it gave way to the table between 2011 and 2019 is not yet read): one paragraph per printed line, the two columns cut by a run of spaces ("Mr. Landry     Mr. Samson"). When one column runs out the rest are one name a line; they belong to the **longer** column, which the Clerk's count names. The tally check still runs on the whole.
  - The count: "THE CLERK: For, 39. Against, 11." (2010: "For, 28, Against 12."). The question is the Chair's "The motion is ..." before the bells, or the paragraph before the request ("We have a dilatory motion on the floor for the bill to recommit", 5 April 2024). **The stage comes from the question only**: that recommit motion (defeated 21–28) is a Motion on Bill 419, not its third reading (carried 28–17 minutes later).
- **Voice:** "The motion is for third reading of Bill No. 133. Would all those in favour ... The motion is carried." with no recorded vote, stored as `kind = 'voice'`. A reading that was divided is never also stored as voice.
- **Roster, per session:**
  - `/members/profiles-table/<assembly>` (61st on) lists everyone who sat in the Assembly, with the profile slug (`member_key`), district and the Member's **latest** party in that Assembly (Trevor Zinck is "IND" for the 61st): stored undated, never written on a vote.
  - **Cut to the session's own list of Members** where the Journals print one (61-1 to 63-3, `.../journals/<leg>-<sess>/...Member...pdf`): constituency and Member read by x-position, matched by constituency **and** surname, footnoted by-election winners by the constituency of the row their mark is on. The 61st Assembly had two David Wilsons; the 61-2 list names David A. Wilson (Sackville-Cobequid) only, and "Mr. Wilson" in May 2010 is his. Without the list both are valid and every NDP division that spring is a gap (tested).
  - **Dated by the profile**, `/members/profiles/<slug>` (the page Hansard links every speaker to; the table's `/history` link is a biography with no party table, checked from CI). Its "Constituency / Party / Start Date" rows ("PC 2017 - 2021", "Independent 2021") cut each Member's term to whole years: "Mr. Wilson" in April 2019 is Gordon Wilson because Dave Wilson's last year is 2018.
- **Party at the vote, dated by year.** The same rows are party-only terms (source `party-profile`). In the year a Member changed party two rows cover the day, so that year's votes carry no party: Brendan Maguire and Fred Tilley (Liberal to PC, 2024), Alana Paon (2019), Trevor Zinck (2010), Becky Druhan (PC, Independent 2025, Liberal 2026). A profile is read once per Member, and again only when the current Assembly's table shows another party.
- **Names.** Hansard prints full names in the 64th and 65th Assemblies ("Hon. Brian Comer") and honorific plus surname before ("Mr. Churchill", "Ms. K. Regan"). Allowances, all unique-or-nothing: the printed case may split Susan Leblanc from Colton LeBlanc; a middle initial the roster lacks is dropped; a misprinted **given** name falls back to the surname alone ("Diane Timmins", "Suzie Hansen", 24 March 2025; "Hon. Alan MacMaster", 26 March 2024). Misprinted **surnames** need a reviewed alias (`config/prov_record.yaml`): "Tom  Taggar" (25 March 2025) and "Hon. Timothy Hallman" (5 April 2024), each checked against another division.
- **Bills:** the session listing (type, the first-reading text linked from the number, latest status). Every text is read once and classified per passage; a bill quiet since the window opened is not read again. The bill's own page (stage dates, sponsor) is read only for a bill on our ground, a watched bill, or one a recorded division names: at ten seconds a request, every page would cost a session an extra hour. A window with no sitting reads no bills. **Cross-check:** every "Second/Third Reading Passed" on a page-read bill, dated to a day whose Hansard was read, must be found there.
- **On our ground, measured** (texts and pages fetched from CI): Bill 133 of 63-2 (deemed consent to organ donation; third reading 12 April 2019 **on voice**) area 13; Bill 242 of 63-2 (abortion access zones; third reading 10 March 2020 on voice) area 1; Bill 140 of 61-4 (gender identity and expression in the Human Rights Act, 2012) area 5; Bill 1 of 63-2 (conversion therapy) area 4. Bill 16 of 63-2, the conversion-practices ban, says "efforts to change **their** sexual orientation or gender identity" and matches nothing: it is watched by key. The four that passed (16, 133, 242 of 63-2; 140 of 61-4) are keys in `config/watchlist-prov.yaml`.

**Smoke runs (2 October 2026).** The collector could not be run from CI (only the read-only probe may run there), so the probe fetched every page a run would ask for and the collector was run offline against those bytes, into scratch stores, with `--no-bills`:

| Session | Window | Hansards read | Recorded divisions (tally ok) | Voice | Votes (unresolved); party |
|---|---|---|---|---|---|
| 65-1 | 18–26 Mar 2025 | 7 | 2 (2) | 8 | 94 (0); 94 |
| 64-1 | 25 Mar–5 Apr 2024 | 6 | 5 (5) | 1 | 237 (0); 228 |
| 63-2 | 8–12 Apr 2019 | 5 | 5 (5) | 11 | 236 (0); 230 |
| 61-2 | 3–11 May 2010 | 7 | 2 (2) | 17 | 87 (0); 85 |

Every one of the 22 divisions in the 25 sittings sampled (2010–2026) reads exactly as many names as the Clerk counted. Known partisans are on their side: Premier Houston Yea and Claudia Chender Nay on Bill 6 (25 March 2025, 39–11); Premier McNeil Yea and Houston Nay on the 2019 appropriations; Premier Dexter Yea and McNeil Nay on Bill 24 (6 May 2010, 28–12). The 17 votes with no party are the change-year votes above.

**The backfill to 2010, measured from the listings** (fetched from CI): 12 sessions, 61-2 to 65-1 (61-1 overlaps 2010 only by its prorogation and has no sitting in it); about **765 sittings** (exact for 8 sessions, ±22 for 61-3, 61-4, 62-2 and 63-1, whose last listing page was not fetched), **2,192 bills** (64-1 alone has 501), about 170 Member profiles once. At ten seconds a request that is about **3,300 requests, 9.3 hours**: two backfill dispatches at the 300-minute clock, a third to mop up. Recorded divisions run at roughly 15–35 a year (22 in the 25 sittings sampled, most on government bills at third reading).

**Known limits:**
- Party is dated to the year, not the day: a change year's votes have none. The Journals' member-list footnotes date changes exactly ("Alana Paon became an Independent on June 24, 2019") but are read only for who sat, not for party.
- Sessions with no Journal list (62-2, 62-3, 63-1, 64-1, 65-1) keep every Member of the Assembly, dated by profile year: two Members with one surname overlapping in a by-election year leave a surname-only label ambiguous (a gap). From the 64th Assembly Hansard prints full names, which resolve.
- Hansard speeches are not stored. Committee of the Whole House proceedings are separate transcripts and are not read.
- The CI probe could not fetch the four 61-3, 61-4, 62-2 and 63-1 listing tails, so their sitting counts are estimates; the backfill reads them in full.

- **The 2010 backfill's gaps (7 October 2026).** CI runs 37076568654 and 37108083021 (3 October) read 61-1 to 65-1, all 750 sittings, and stored 169 recorded divisions (61 tally ok, **108 gap**), 1,064 voice decisions, 6,829 votes with 153 unresolved, and 128 gaps (108 tally, 20 bills-listing readings not found). The pages were fetched from CI for the repair (`probe-hosts.yml` on branch `ns-backfill-tally`, runs 37568416383, 37572297330, 37572696872: every gap sitting, every bills-listing miss day, every sitting with a passing division, and 47 'ok' sittings with no division sampled across the sessions: 170 Hansards, the 62nd Assembly's Members table and dates, one profile). By cause:

  | Cause | Failed divisions | After |
  |---|---|---|
  | "Mr. David Wilson" in 2013-2018 lists: the roster (and his own profile's heading) calls him Dave Wilson, so the given name never matched and the surname alone was Dave or Gordon Wilson | 60 (69 votes, plus 1 bare "Mr. Wilson"; 10 of them also had a misprinted surname) | 0 |
  | List layouts the parser of 2 October did not know (below) | 23 | 0 |
  | Misprinted surnames and typesetting slips ("Mr. Bailey", "Hon. Twila Gross", "Mr.Scott", "&Mr. Rankinnbsp;") | 8 (plus the 10 above) | 0 |
  | Forms of the Clerk's count not read ("Those in favour of the motion, 31; those against, 17.", "Yays, 47. Nays, 0.", "For, 23. Against. 20. (Applause)", "in favour of Resolution No. 35, 33; against, 13") | 7 | 0 |
  | The record's own error: the list does not hold the names the Clerk counted (one to two names short, a name printed twice, a column printed twice) | 10 | 10, known gaps |

  Unresolved votes 153 -> 1 (in a known-gap division). Bills-listing misses 20 -> 4, all the record's (known gaps); 20 -> 1 with the bill-page stage (below). Fixed, each from a fixture of a real page (`tests/test_prov_ns.py`, the `Backfill2010*` classes):
  - **Layouts.** A column of names as one cell, a name a line (27 April 2012); the YEAS header inside its cell, so the list was never seen (5 November 2012: Bill 94's second reading, 28-19, a sitting stored 'ok' and empty); a double space inside a name ("Ms. Maureen  MacDonald  Mr. Samson", 2012-2013), which the old column cut read as three names; columns run together with one space ("Elizabeth Smith-McCrossin Larry Harrison", 2023, and again in 2026); a one-column list of full names with double spaces ("Dave  Ritcey", 2021-2022); a three-column list with ABSTENTIONS (17 October 2022, a division silently lost); a list printed with no YEAS NAYS header (9 March 2026, silently lost); a table whose list paragraphs finish (13 March 2026); the roll call broken into by the Chair or the gallery (5 May and 18 December 2015); a paragraph left open over a table (11 May 2015); two cells run into one (6 May 2016); a page marker inside a cell (12 April 2023). **Paragraphs the record never closes** (late 2011, `<p class="hsd_general">` with no `</p>`): those Hansards read as ten paragraphs each and were stored 'ok' and empty (14, 25 and 28 November 2011; 10 May 2011 too). That is why 61-3 stored 3 recorded divisions and 33 voice decisions in 68 sittings.
  - **The paragraph lists are placed by the Clerk's count.** The columns fill side by side and the shorter runs out first, so with a count of Y and N the first min(Y, N) printed lines hold two names and the rest the longer column's; a line is cut at each title it carries, and a line with no title is cut only where it leaves two full names (more than one such cut: only a cut after a known surname both sides; still more than one: a gap, never a guess). No count, no placing.
  - **Names.** A full name whose given name is not the roster's, where the surname alone is two Members, resolves by the INITIAL of the printed given name when that is one Member ("Mr. David Wilson" is D. Wilson; Gordon Wilson is G.). British Columbia's elimination: "Mr. Wilson" beside "Mr. Gordon Wilson" in one list (4 April 2014). Reviewed facts in `config/prov_record.yaml`: 24 label aliases, each on one day in one Hansard, each checked against another division printing the name rightly and the Assembly's Members table; one `hansard_labels` entry ("Ms. MacDonald", 23 April 2013, with Manning and Maureen MacDonald both sitting). `ReviewedDivisions.settle` is now read by Nova Scotia.
  - **Questions and readings.** "Bill 49" and "Bill 204" without "No."; "be read a third time" without "now"; "The motion is for second reading." with no bill (the bill is the one whose reading was moved); "a recorded vote on Bill No. 247" gives the bill, never a stage. Voice decisions: "... to close third reading of", "... to move second reading of", "... second reading on", "The motion is that Bill No. 198 be read a third time"; the mover's own "I move second reading of Bill No. 1." put at once (2010); a decision shown only by "Ordered that the bill be referred ..." (2025); bills called together, "The motions are carried." and "Ordered that these bills do pass." (2011-2012).
  - **Guards.** A Clerk's count that follows no list the parser read is a gap and the sitting stays owed, never 'ok' (it caught the three-column and headerless lists). A re-read sitting replaces everything stored from its record (`clear_record`).
- **The CI repair** is one `provinces: ns` dispatch (since 2010-01-01, `minutes: 300`). `owe_stale` makes every sitting stored 'ok' before `REREAD_BEFORE` (8 October 2026) owed, so all 676 'ok' sittings are read once more (the empty 2011 sittings and the header-in-cell days cannot be found any other way); the 74 gap sittings are re-read as always. `owe_listed` re-reads any 'ok' day missing a reading its bill page dates to it, from then on. About 750 Hansards plus listings and rosters, some 860 requests at the 10-second crawl-delay (11 s a request on 3 October): **about 2.7 hours, one dispatch**. Bill texts are not read again. If the dispatch runs before 8 October, bump `REREAD_BEFORE` to the day after it, or the next run reads everything a second time.
- **End to end** (scratch copy of the published store, sha256 f91609d7; every probe page re-read through `read_sitting`, then party refreshed and the bills cross-check run over every session): recorded divisions 169 -> 176 (61 -> 166 tally ok, 108 -> 10 gap), unresolved votes 153 -> 1, votes with a dated party 6,606 -> 7,609, voice decisions 1,064 -> 1,152, gap sittings 74 -> 9, listing misses 20 -> 4. The seven new divisions are silent losses found in the 170 pages re-read; the 600-odd 'ok' sittings not fetched are re-read by the CI repair and may hold more (the late-2011 pages especially). **All 61 previously passing divisions were found again with the same members on the same sides and the same parties**; four gained a bill or a stage from the question (Bill 49 third reading, 4 November 2014; Bill 203 second reading, 17 October 2019; Bill 120's recommittal, 22 April 2022; Bill 198 third reading, 2 April 2026). **Partisan check:** Bill 37 (essential health services) third reading, 4 April 2014, 31-17: Premier McNeil Yea, Baillie (PC) and Maureen MacDonald (NDP) Nay; Bill 6 second reading, 20 October 2014, 36-9: Baillie and Houston Nay; Bill 148 third reading, 18 December 2015, 30-14: McNeil Yea, Baillie Nay; the Financial Measures (2026) Act second reading, 13 March 2026, 37-13: Premier Houston Yea, Chender Nay.
- **Known gaps** (`config/prov_known_gaps.yaml`, `ns:`): the ten divisions whose lists do not hold the Clerk's count (in five the Premier is in no list while counted), each with the names the day's other divisions suggest and why that is not evidence; one reading a bill page dates to a day whose Hansard prints no decision for it (Bill 109, 31 March 2022).
- **Decisions (Christopher, 7 October 2026), all four approved:**
  - **The initial rule** ("Mr. David Wilson" -> D. Wilson when the surname alone is two Members) is approved, as a resolver allowance (`NameResolver._resolve`).
  - **The 24 label aliases and the `hansard_labels` entry** in `config/prov_record.yaml` are signed off.
  - **Stage from the bill page** is approved and built (`prov_ns.stage_from_bill_page`): where Hansard prints no question for a division but names the bill (or the division falls under the bill's heading), and the bill page dates exactly one second or third reading of it to that day which nothing else in the day's record holds, the division is that reading, with "stage from the bill page (...)" in its tally_note. On the scratch store it cleared three of the four listing gaps: Bill 203 third reading (25 October 2019, 26-22), Bill 201 second reading (27 February 2026), Bill 247 third reading (25 March 2026, 37-12). Bill 109 (31 March 2022) stays a known gap: Hansard puts its second reading and prints no decision at all. A sitting read before its bill pages were stored gets the rule on its next read, through `owe_listed`.
  - **A member counted but not printed** is a new reviewed fact type, `added_members` (`pn.ReviewedDivisions.add`): one division, one side, only while that side prints fewer names than the Clerk counted, only for a member placed nowhere in the division, and only from a second official record that states the vote, cited and quoted; the tally check then runs as normal. **No Nova Scotia entry could be evidenced**: the Journal of 14 April 2021 (the only one of the five days the Journals reach; `journals/63-3/017 2021Apr14.pdf`, read from CI on 7 October 2026) records Bill 98's second reading without names, the Journals stop at the 63rd Assembly, the House publishes no other vote record, and Hansard's narrative never says how the Premier voted. All five stay known gaps.

### Prince Edward Island: not built, out of reach

From a GitHub runner on 2 October 2026 (`probe-hosts.yml`, honest UA): the home page answers 200 but carries Radware's bot manager (`stormcaster.js`, `validate.perfdrive.com`), and the first inner page asked, `/legislative-business/house-records`, **302s to the Radware CAPTCHA** at `validate.perfdrive.com`. The probe stopped on the host there, as it must: we never solve or work around a challenge. `peildo.ca` (PEI Legislative Documents Online) answers, but lists the Journals of the 32nd to 43rd General Assemblies only, nothing since 2010. `docs.assembly.pe.ca` serves PDFs by UUID, and the UUIDs are only on the challenged pages. `tools/prov_collect.py --prov pe` says so. **Next step:** ask the Clerk of the Legislative Assembly of PEI to allowlist the CitizenGO User-Agent or provide the Journals and division records since 2010.

### Schedule and backfill (3 October 2026)

Christopher: "Schedule the provincial collectors and backfill to 2010", and for Quebec "DO what is necessary" (the month form POST is approved; backfill as deep as the PV annex allows; refresh the roster after the 5 October election).

- **The weekly** (`.github/workflows/prov-weekly.yml`, "Provinces weekly"): Wednesday 10:00 UTC, retry slot 12:00 behind a gate job, in the `parl-monitor-state` group. Wednesday 10:00–18:00 holds no other stateful cron (a test keeps it so). One step per province (ab, sk, bc, mb, on, nb, nl, qc, and ns since its build), each `if: always()`, each on its own `--budget-seconds` and step timeout, so one province failing never costs the others. Quebec's roster is read again every week (`--roster-only`) before Quebec is collected. Then `tools/prov_5ca.py --all` per province, the raw archive, the store and the sidecar commit, exactly as the Canada weekly does. Registered in `alert.yml`, `tools/coverage.py` (`PIPELINES`, `FEEDS`, `PIPELINE_FEEDS`, `ONCE_EVER`) and the structural tests.
- **The window is resumed, not fixed** (`tools/prov_collect.py --resume`): from the newest record already read, less 14 days, or from the oldest record still owed in the last 120 days. On a province with nothing read it is the module's own default (the whole current session; Saskatchewan's last 60 days), said in the log.
- **Sessions come from the legislature's own index**, never from a list typed into the repo (`list_sessions` in each module; `src/prov_fetch.py`, "sessions"). A session the index lists that is newer than the module's `CURRENT_SESSION` is collected that week **and** recorded as a gap ("set CURRENT_SESSION"), so the run fails loudly until a person moves the constant. Quebec's 44th legislature will arrive this way after the 5 October election.
- **The backfill:** dispatch the same workflow with `provinces` (one code is the intended use, e.g. `nb`) and `since` (default `2010-01-01`), optionally `minutes` (default 280, capped at 300; the job is killed at 330). It runs `prov_collect.py --all-sessions --since …` for each named province: every session the index lists whose dates touch the window, oldest first, on one clock. A dispatch with `provinces` set skips the weekly steps. Cut short by its clock, it says which sessions were not started, and the next dispatch resumes: a record read cleanly is never fetched again, and a closed session's bill page already read with its text is not re-read (Alberta and Quebec used to re-read every bill page every run). Saskatchewan's archive is listed by date, a calendar year at a time, each year on its own page cap (a year still paging at the cap is a gap, never a silent cut).
- **A layout the parser cannot read shows as gaps, never wrong votes.** Every division still passes the tally check: unresolved names or a count that does not match the printed totals is `positions_ok = 0`, a gap, and places nobody.

**How far back each source goes, and what has been tested.** "Listed" is what the legislature's own index offers; "tested" is what a parser was proven on. Everything between is untested and will show as gaps where the layout differs.

| Province | Sessions since 2010 (from the index) | Listed back to | Parser tested on | Expected gaps in a backfill to 2010 |
|---|---|---|---|---|
| Alberta | 27-2 to 31-2 (18), from the V&P listing's menu | V&P menu to the 22nd Legislature (1990); bills to 1906 | 31st Legislature V&P | 27th–30th Legislature V&P layouts untested; tally gaps if they differ |
| Saskatchewan | none needed: the archive is listed by date across sessions | Minutes PDF since March 2003, HTML since the 30th Legislature | 29L bilingual PDF (2023), 30L HTML | 26L–29L PDFs read end to end on scratch stores, 2 October 2026 (Saskatchewan notes, step 2): the 26th–27th Legislature cover is a table, read by `parse_table_cover` |
| British Columbia | from LIMS `allSessions` (the API decides; the fixture holds 42-1 on) | Hansard HTML in the API's sessions; voting index to 2019 (not read) | 43-2 transcripts | six division markups 2009–2026 read, each from a fixture; two guards (the transcript's own words, the Voting Records index) make a short read a gap; party dated to the sitting from each Hansard PDF's list of members |
| Manitoba | from the V&P sessions page (the 39th and earlier are on the live page; the fixture starts at 40-1) | V&P to 36-4 (1998) | 39th to 43rd Legislatures (the 2010 backfill, 2 October 2026) | pre-2010 V&P layouts untested: gaps, not wrong votes; the roster needs each division day's Hansard PDF cover |
| Ontario | from the house-documents index (40-1 on in the fixture; 39-2, 2010–2011, if the live index lists it) | V&P HTML to 2008 | the 2022+ tables, the late-2025 doubled names, and the pre-2022 layout on 2015 | 2008–2014 V&P untested; the roster is the Hansard PDF's member list (2015 needed a fix) |
| New Brunswick | 56-4 to 61-2 (17), from the journals page's selector | Journals to the 53rd Legislature (1995) | 56-4 to 61-2 (the 2010 backfill, 2 October 2026) | 56-4 has no roster (no compiled Journal): its 7 divisions are known gaps; no party at the vote before 58-3 (no Hansard published). 10-second crawl-delay: a full re-run from the published store is about 2,200 requests, 6 hours: two dispatches at minutes 300 |
| Newfoundland and Labrador | 46-2 to 51-1 (15), from the Hansard index | Hansard to the 23rd General Assembly; attendance summaries 2009+ | 46-2 to 51-1 (the 2010 backfill, 7 October 2026) | every year has a roster (2010 read from its padded text layout, 2024 bridged); party at the vote for the 51st Assembly only (Christopher's decision) |
| Nova Scotia | 61-1 to 65-1 (13; 61-1 has no sitting in 2010), from the Hansard index, dated by each Assembly's dates page | Hansard to the 56th Assembly; Members tables from the 61st | 61-2 to 65-1: the 2010 backfill's 74 gap sittings and 96 others, every layout met (7 October 2026) | 10 divisions whose lists are not the Clerk's count and 4 readings with no question printed (known gaps); the repair re-reads every sitting once, about 2.7 h, one dispatch |
| Quebec | 39-1 to 43-3 (9), from the sitting index's session select | the select lists sessions back to 1867; depcir roster stored from 1960 | every session 2010–2026 (the 2010 backfill, re-read 7 October 2026: the surname-only annex of 2008–2012 in both its encodings, and 14 layout traps) | 38 of 3,119 recorded divisions: 32 known gaps (17 record errors, 15 group-vote homonyms) and 6 open (see "The 2010 backfill" under Quebec) |

**Coverage:** `prov_members` and `prov_bills` are watched as heartbeats (re-stamped every run, measured); `prov_divisions` and `prov_sittings` are write-once in practice (`ONCE_EVER`). Until the workflow's first heartbeat, their empty tables are reported "AWAITING FIRST RUN" instead of overdue (`AWAITING_FIRST_RUN` in `tools/coverage.py`); the excuse expires by itself at the first run. The watch is per table: one province going dark shows as its own failed step and the failure alert, not in the coverage watch.

### Hansard speeches (2 October 2026): `tools/prov_speeches.py`

Christopher: provincial Hansard speeches, so the provincial 5CA sheets get speech evidence, not only votes. Built for all eight provinces that have vote collectors. This section supersedes the "Hansard speeches are not read" lines in each province's "Known limits" above.

- **The tool** (`tools/prov_speeches.py`) is the sibling of `prov_collect.py`, as `ca_hansard.py` is of the federal roll-call collector. It never writes a division, a vote, a bill or `prov_sittings`, so the vote collectors and the vote backfill behave exactly as before. Engine: `src/prov_speeches.py`; one reader per province: `src/ingest/prov_<code>_hansard.py`.
- **What a speech is:** a turn, meaning a paragraph opening with a speaker label plus the paragraphs after it, up to the next label or heading. Each turn sits under its rubric (Oral Questions, Orders of the Day) and its subject heading. The chair, the table and the collective labels (The Speaker, Le Président, Mr. Chairperson, Some Hon. Members, Des voix, the Clerk, His Honour) are counted, not stored.
- **Only speeches on our ground are stored, with an excerpt.** Matching is per passage (`filter.match_passages` through `prov_classify.classify_text`). Quebec uses the French layer (`config/taxonomy-qc.yaml`); every other province uses the English taxonomy plus `config/watchlist-prov.yaml`.
  - The subject heading, plus the bill's titles when the heading names a bill, is a passage of its own.
  - A watched bill KEY lends its areas to the debate held under its heading. A bill's TEXT classification does not, because an omnibus bill's passing citation would file every speech of a budget debate.
  - Statute names are not masked in speeches: a member who names an Act is talking about it.
  - The excerpt is the member's own best passage, or the speech's opening words, never the heading.
- **The bill** comes from the heading, or from the procedural text between the heading and its first turn ("Bill 27, An Act to enact …"). It never comes from a speech. It is joined to `prov_bills` in the same session only (the Senate lesson), or by exact short title where the heading prints only that (Ontario, Manitoba).
- **Who spoke:** the province's own resolver, wrapped as its vote collector wraps it (reviewed aliases, Newfoundland's `NameResolver`, Quebec's `MemberPages`), against the roster terms valid ON THE DAY, unique-or-nothing. The allowances:
  - A bracket is tried as a riding, then dropped as a role or nickname: "Hon. Jon Gerrard (River Heights)", "Hon. Kelvin Goertzen (Government House Leader)", "Mrs. Jennifer (Jennie) Stevens".
  - A full name whose given name differs from the roster's is retried as initial plus surname ("Mike" for Michael), Newfoundland's rule.
  - A word the PDF split ("Coc krill") is rejoined.
  - A name printed in two languages ("Laanas / Tamara Davidson") is tried on each side.
  - **Within one sitting only:** a bare surname that is ambiguous on the day resolves to the one candidate the same sitting named in full. Where two were named, the matching honorific decides: "Mrs. Bernadette Smith", so "Mrs. Smith".
  - Quebec's centred heading above a turn gives the speaker's full name.
- **Never is a name invented.** An unresolved label is stored as printed with `member_key` NULL, and counted per day in `prov_speech_sittings` (`members` less `resolved`; `unresolved` among the stored) and per run in the log. A day with at least 20 speaker turns where fewer than half resolve is a gap and stays owed: the roster is missing, not the members.
- **Record of days read:** `prov_speech_sittings`, one row per Hansard day or part read, whatever it held. It is deliberately not `prov_sittings`: BC and Newfoundland read their divisions from the very file read here, and a shared record would let one reader mark the other's work done. A truncated or unparseable file is `unreadable` and stays owed.
- **Raw archive:** each day's transcript is archived through `HttpClient` (`archive=True`, feed `prov-<code>-speeches`, names lowercased by `http.slugify`). The vote collectors still archive nothing.
- **The roster comes first.** Speakers resolve against what the vote collector stored, so the weekly runs the speeches steps after the collectors.
  - Where the vote collector reads its roster from each day's Hansard member list (Saskatchewan, Manitoba, Ontario), the speeches reader reads that day's list too, through the same function, when no term covers the day yet. That costs the PDF on a non-division day, and Saskatchewan reuses the bytes when it read the PDF for speeches.
  - BC, Alberta, New Brunswick, Newfoundland and Quebec read their roster once when the store holds none for that legislature.
  - **Back-fill a province's votes before its speeches.**
- **5CA** (`tools/prov_5ca.py`): speeches are evidence, never direction, as on the federal sheets. Each member's speeches on the area in one debate on one day are one line ("2021-10-14 SPEECH x9 Bill 207… : "…" [activity, not direction]"). A former member with only speeches is not listed; everyone who voted still is.
- **The weekly** (`prov-weekly.yml`): one "Speeches, <province>" step per province after the collectors and before the 5CA sheets, each `--resume` on its own clock.
  - The clocks add up to 85 minutes; the weekly job timeout rose from 150 to 240 minutes.
  - `--resume` starts at the newest day read, less 14 days, or at the oldest day still owed in 120 days.
  - On a province with nothing read it reads the last 60 days, never the backlog.
- **The speeches backfill is its own dispatch input:** `speeches_since`, default blank.
  - Blank: a `provinces`/`since`/`minutes` dispatch is the vote backfill, unchanged (its step now also checks `speeches_since == ''`, which a blank input always is).
  - Set: the same dispatch backfills the named provinces' speeches from that date INSTEAD of their votes, on the same clock (`prov_speeches.py --all-sessions --since …`). Re-dispatch until nothing is left.
- **Coverage:** `prov_speeches` and `prov_speech_sittings` are `ONCE_EVER`.
  - Their empty-table excuse (`AWAITING_FIRST_RUN`) is keyed on a STEP heartbeat: `prov_speeches.py` stamps "Provinces speeches" into `source_runs`.
  - It is not keyed on "Provinces weekly", because a vote backfill dispatch runs no speeches step and would have expired the excuse days before the first speeches run.

**Per province** (sizes measured on the days read on 2 October 2026; "turns resolved" from the test runs below):

| Province | Source (from the legislature's own index) | Format, mean size a day | Labels | Turns resolved | Notes |
|---|---|---|---|---|---|
| Alberta | `transcripts-by-type?legl=&session=` (one file per sitting: _1000_, _1330_, _1930_) | PDF, 885 KB | surname ("Mr. Nicolaides", "Member Irwin", "Ms Gray") | 96.1% | `head:` lines are the rubric; an evening Committee of the Whole has none and starts at its "Title:" line; "3:50  Bill 27" heads a bill. Two members of one surname on the day (the Wrights, the Sigurdsons) stay unattributed: no riding is printed. |
| Saskatchewan | Legislative Meeting Archive, by year | HTML from the 30th Legislature (about 300 KB, plus the day's PDF for the roster); PDF only before it (690 KB) | surname ": —" | 98.1% | The HTML is never requested where the archive lists none (29L and earlier); the PDF text is clean. The day's cover PDF is the roster. |
| British Columbia | the session's debates JSON (House transcripts only) | HTML, 240 KB | full name from 2025; initial and surname before ("Hon. P. Bell") | 98.6% (2026); 99.9% on the 2010–2024 sample | Committee rooms are not read. Every markup since 2009 read (7 October 2026, below). |

**British Columbia speeches, 2010–2024 (fixed 7 October 2026).** The backfill (run 37567998904) left 1,481 of 1,662 days owed with "no speaker turns parsed": only the 2025– label (`<span class="Speaker-Name">`) was read. Before it the label is `<span class="Attribution">Hon. C. Oakes: </span>` with the colon inside (2009–2017; `<SPAN class=Attribution>` in 2015) and `<span class="attribution" id="tt5945">S. Cadieux: </span>` (2018–2024). The reader now uses the vote reader's block grammar (`prov_bc._BLOCK`, folded classes), strips printed page numbers from speech text, and resolves with BC's dated terms (including `hansard-list` members) and its reviewed other surnames. Measured on a scratch store, one division day a year 2010–2024 plus 12 March 2012 (31 transcripts): every day parsed (15 to 341 turns), 2,794 of 2,795 member turns resolved, 7 speeches on our ground (Chouhan on Bill 22, the Education Improvement Act, 12 March 2012; Eby on Bill 2, the Protection of Public Participation Act, 13 February 2019). The owed days are re-read by an ordinary speeches dispatch (`provinces: bc`, `speeches_since: 2010-01-01`): a day not "ok" is never done.
| Manitoba | Hansard calendar → the day's `summary.html` → `h<n>.html` | Word HTML (windows-1252), 320 KB | riding first, then surname | 99.5% | "Questions" and "Debate" headings keep the bill; robots.txt read every run. |
| Ontario | the day's hub (`…/<date>/hansard`) IS the Hansard | HTML, 480 KB | full name ("MPP Jamie West") | 99.8% | Bilingual headings: the English half is kept; the division lists (`voteText`) are skipped. |
| New Brunswick | `/en/house-business/hansard/<leg>/<sess>` | bilingual PDF, 1.1 MB; 10 s crawl-delay | "Hon. Mr. Herron", "Ms. M. Wilson" | 99.7% | Left column as spoken, right column its translation, paragraph by paragraph. Pages are read with positions and glyph widths; the English paragraph of each pair is kept by its function words. French is never classified. Truncated PDFs at source (14 June 2023, 3 June 2026) are `unreadable` and owed. |
| Newfoundland and Labrador | the session's Hansard calendar | Word HTML, 460 KB | "S. CROCKER", "PREMIER WAKEHAM" | 100% | No subject headings; the Clerk's reading of a bill's title "(Bill 7)" sets the subject. |
| Quebec | the sitting index (month form POST, approved 3 Oct) | HTML, French, 550 KB | "M. Legault", plus the full-name heading above | 99.5% | French taxonomy layer; "Projet de loi n° 21" headings keep their bill through the stage headings. |

**Test runs (2 October 2026, live, from the laptop's VPN exit, scratch stores only):**

Cumulative over all the scratch stores. "Turns" are speaker turns other than the chair's; "unresolved" were stored, or would have been, with no member key, and were counted.

| Province | Days read (owed) | Days | Speaker turns | Resolved | Unresolved | Speeches on our ground | of them unattributed | Members with speeches |
|---|---|---|---|---|---|---|---|---|
| Alberta | 11 (0) | 25 Nov–4 Dec 2024 (Bills 26, 27, 29) | 1,291 | 1,241 (96.1%) | 50 | 105 | 5 | 33 |
| Saskatchewan | 21 (0) | 16–31 Oct 2023 (PDF, Bill 137), 22 Oct–6 Nov 2025 (HTML) | 1,207 | 1,184 (98.1%) | 23 | 192 | 1 | 24 |
| British Columbia | 12 (0) | 12–26 Feb 2026 | 831 | 819 (98.6%) | 12 | 9 | 0 | 7 |
| Manitoba | 12 (0) | 12–14 Oct 2021 (Bill 207), 26 May–2 Jun 2025 | 1,851 | 1,841 (99.5%) | 10 | 35 | 0 | 12 |
| Ontario | 12 (0) | 1–4 Jun 2015 (Bill 77), 17–27 Nov 2025 | 2,483 | 2,478 (99.8%) | 5 | 12 | 1 | 10 |
| New Brunswick | 10 (2) | 6–16 Jun 2023 (Policy 713), 3–4 Jun 2026 | 622 | 620 (99.7%) | 2 | 58 | 0 | 18 |
| Newfoundland and Labrador | 7 (0) | 21–23 Nov 2016 (Bill 43), 30 Mar–2 Apr 2026 | 1,259 | 1,259 (100%) | 0 | 4 | 0 | 3 |
| Quebec | 9 (0) | 14–16 Jun 2019 (Bill 21), 1–9 Jun 2023 (Bill 11) | 1,896 | 1,886 (99.5%) | 10 | 451 | 2 | 49 |
| **Total** | **94 (2)** | | **11,440** | **11,328 (99.0%)** | **112** | **866** | **9** | |

- **Owed:** the two New Brunswick days are PDFs served truncated (14 June 2023, 3 June 2026), stored `unreadable`.
- **Saskatchewan on 22 October 2025:** the opening ceremony, where elders and guests spoke, gave 4 of 9 resolved, rightly. It was a gap until the gap threshold was set at 20 speaker turns.
- **Proofs on our ground:**
  - Manitoba, Bill 207 second reading: Fontaine x12, Naylor, Martin, Asagwara, Nesbitt and Gerrard, the questions keeping the bill.
  - Alberta, 3 December 2024: LaGrange moving Bill 26; Hoffman, Shepherd and Al-Guneid against.
  - New Brunswick, 15 June 2023, Policy 713: Holt, Hogan, Higgs, Austin, Coon, Mitton and the two Arseneaults.
  - Quebec, 16 June 2019, Bill 21's closure and adoption: Jolin-Barrette, Legault, David and Nadeau-Dubois, classified in French.
  - Saskatchewan, Bill 137: Cockrill, Beck and Young.
  - British Columbia: Armstrong's Gender Ideology and Child Protection Act.
  - Ontario: Naqvi's Bill 77 motion.
- **What stayed unattributed was honest:**
  - surnames shared on the day ("Ms Wright" in Alberta, both Wrights sitting);
  - non-members (guests and elders at an opening);
  - one-word fragments ("Á’a", an Indigenous-language word printed in the speaker-name style).
  None was guessed.

**Backfill size to 2010 (measured 2 October 2026 by listing every session's Hansard days in a dry run; sizes from the mean day sizes above):**

Days are what each legislature's own index lists for every session touching 2010-01-01 onwards. "Fetched" is the transcripts alone; "archived" is what `data/raw` grows by (gzip).

| Province | Sessions | Hansard days (files) since 2010 | Fetched | Archived | Also fetched | Time at the polite rate | Dispatches of 280 min (`speeches_since`) |
|---|---|---|---|---|---|---|---|
| Alberta | 18 (27-2 to 31-2) | 1,402 PDFs | ~1.2 GB | ~1.2 GB (PDFs do not compress) | each legislature's member pages, once (~90 each) | ~2.5–3.5 h (fetch plus pypdf, ~6–8 s a file) | 1 |
| Saskatchewan | date-driven | 1,057 | ~0.7 GB | ~0.4 GB | nothing more on PDF days; the day's PDF on 30L HTML days | ~2.5 h | 1, but see below |
| British Columbia | 23 (39-1 to 43-2) | 982 | ~0.24 GB | ~0.06 GB | one members query per parliament | ~0.5 h | 1 |
| Manitoba | 19 (39-4 to 43-3) | 1,535 | ~0.5 GB (+ 14 KB summary a day) | ~0.12 GB | the day's Hansard PDF where the vote backfill has not read that day's cover (not measured; under 1 MB) | ~1.5–2.5 h | 1 |
| Ontario | 11 (39-1 to 44-1) | 1,334 | ~0.64 GB | ~0.18 GB | the day's Hansard PDF where no cover term covers the day: 650 KB–1.3 MB, up to ~1.3 GB | ~1.5–2.5 h | 1 |
| New Brunswick | 17 listed; **only 58-3 to 61-2 published online** | 347 | ~0.38 GB | ~0.34 GB | each session's compiled Journal, once | ~1.5–2 h (10 s crawl-delay) | 1 |
| Newfoundland and Labrador | 15 (46-2 to 51-1) | 798 | ~0.37 GB | ~0.06 GB | attendance summaries per year, once | ~0.5 h | 1 |
| Quebec | 9 (39-1 to 43-3) | 1,251 (and 24 sittings the listing gives no Journal link: two in 41-1 and 22 in the spring 2020 sittings of 42-1; each is a gap) | ~0.69 GB | ~0.18 GB | the month form POSTs (about 10 a session) | ~0.7–1 h | 1 |

**Pacing and prerequisites:**
- **Back-fill a province's votes first, then its speeches.** For Saskatchewan, Manitoba and Ontario the vote backfill reads the covers of division days; this reads the rest.
- **One province per dispatch**, as for votes. Every province fits one 280-minute clock on these estimates. Alberta is the slowest; a run cut short resumes where it stopped.
- **The raw archive grows by about 2.5 GB** for all eight, Quebec included. Alberta and New Brunswick are most of it, because PDFs do not compress.

**Not readable yet, found by the measurement and the probes (the vote collectors were not changed, as briefed):**
- **Saskatchewan before 2023: the vote collector's own archive listing finds nothing.** `prov_sk.list_records` reads "<span>Minutes (<a>…)</span>"; the archive before its 2023 redesign prints a bare "<a href=…Minutes.pdf>Minutes</a>". A 2015 archive page gives 0 records to the vote collector (13 for October 2023), with no gap recorded. **A vote backfill of Saskatchewan to 2010 would silently read nothing before 2023.** The speeches reader takes links by path and lists all 1,057 days. Fixed 2 October 2026 (b0a675d1): bare links are taken by their path.
- **Saskatchewan's Hansard cover before the 28th Legislature did not parse** (`prov_sk.parse_cover`: "no members parsed" on 25 and 26 November 2015; 0 of 69 speakers resolved on the 25th). **Fixed 2 October 2026:** the 26th–27th Legislature cover is a table (Saskatchewan notes, step 2). On a scratch store the 25th now resolves 69 of 69 and the 26th 66 of 66. Covers from June 2016 on always parsed.
- **New Brunswick before 58-3 (2010–2017):** the Hansard page offers sessions from 58-3 only. Earlier transcripts are "available upon request through the Legislative Library". These are logged as not published, not as gaps. The vote collector, which reads each division day's Hansard member list for the party, records one gap per session for them (a known gap).

**Known limits:**
- Same-surname members in surname-only Hansards (Alberta, Saskatchewan, Manitoba, Newfoundland) resolve only where the same sitting printed the full name, riding or initial. Otherwise they stay unattributed and counted. Honorific gender is used only within a sitting.
- The heading parsers were proven on the windows above. Older layouts (Alberta before the 31st Legislature, Saskatchewan's 26th–28th Legislature PDFs, Manitoba before the 42nd, NB before 2023) are untested. A layout that defeats them shows as fewer turns, or as a "no speaker turns parsed" or "only N of M resolved" gap, never as a speech pinned on the wrong member.
- New Brunswick's 2023 Hansard prints its headings one language per column; the 2026 one prints them bilingual. Both are handled, and a heading in a pair can come out in French when neither half scores English ("Logement").
- Rubric and subject come out imperfect in places (Newfoundland's debate before the Clerk's reading has no subject; Quebec subjects are question titles). Classification still reads the speech's own words per passage.
- The excerpt and the matching are English or French taxonomy only, with the same false positives the vote collectors document (organ-donor leave, "Down syndrome" in a budget debate).

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
  - Journal des débats and procès-verbal are **French only**, so the English taxonomy cannot read them. A French term layer is required, as in Germany. **Built** as `config/taxonomy-qc.yaml` (see "Built", Quebec); a native reader has not yet reviewed it.
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

### Nova Scotia (nslegislature.ca): value 3, difficulty 3 (built, from CI)

- **Built** (step 9, above). Reachable from a GitHub runner; still reset from the laptop's VPN exit.
- **Not reachable from the probe IP:** the TCP connection is reset on the TLS ClientHello, before our UA is ever sent, so this is not a UA filter.
- **Wayback only (unverified live):** Hansard HTML has YEAS/NAYS tables with full names. Example: Bill 6, third reading, 25 March 2025; YEAS include Hon. Tim Houston, NAYS include Claudia Chender. The journals appear to lag years behind (63-3, 2021).
- **Next step:** re-test from CI. If it is still reset, ask the Clerk to allowlist us.
- **Effort:** 16–20 h if reachable.

### Prince Edward Island (assembly.pe.ca): value 2, difficulty 5

- **Blocked, from CI too** (2 October 2026; see "Prince Edward Island: not built, out of reach" above).
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
- Quebec has its French layer, `config/taxonomy-qc.yaml` (built 2 October 2026).
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

- **Yukon and PEI**, unless their Clerks allowlist us: both challenge a GitHub runner too. We do not solve CAPTCHAs or challenges. (Nova Scotia was the VPN exit; it is built from CI.)
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

## Re-probe from a GitHub runner (3 October 2026, run 36951730486)

`.github/workflows/probe-hosts.yml` asked the three blocked hosts from the IP the collectors would use:

- **Nova Scotia:** 200 on the home page and the Journals. The reset was the VPN exit, not us.
- **PEI:** 200 on the home page; the house-records page redirects (302). Also the VPN exit.
- **Yukon:** 403 with a Cloudflare "Just a moment..." challenge, from the runner too. **Out of reach.** We do not work around bot challenges. If Yukon matters, ask the Assembly's clerk for access or a data export.

Nova Scotia and PEI can be built. Their live probes and fixtures must come from CI, because the laptop's VPN exit is still refused.

**Second round, 2 October 2026 (branch `prov-ns-pe`, runs 36989641244 to 36998529890).** `probe-hosts.yml` was extended to take URLs as dispatch inputs and run `tools/probe_hosts.py`: GET only, the repo's honest UA, robots.txt read first and honoured by both of the repo's readers, at least 2 s per host and the Crawl-delay where one is set (10 s for Nova Scotia), same-site redirects only, and a bot challenge, a 403/429 or a robots.txt that does not answer **stops the host for the run**. What was fetched is uploaded as an artifact. Nine runs fetched 267 Nova Scotia pages (264 answered 200, 3 same-site redirects); one run's every request to Nova Scotia timed out (run 36995006229: six pages and robots.txt, no answer within 60 s), and the probe was fixed so that a silent robots.txt stops the host instead of meaning "no rules".

- **PEI:** the home page answers, carrying Radware's bot-manager script; the house-records page 302s to the Radware CAPTCHA, from CI as from the laptop. Stopped there. Out of reach.
- **Nova Scotia:** 200 throughout, `Crawl-delay: 10` honoured. Built.
