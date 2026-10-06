# Brief Builder Rulebook

Rules for auto-drafting CitizenGO Campaigns Briefs (RF4 template) from an opportunity record.
Works in every country: Tier A (full parliament monitor, e.g. UK), Tier B (open parliament data, no monitor), Tier C (news only).

Owner tags: 🔒 Fact (machine, sourced) · ✏️ Draft (machine suggests, campaigner owns) · 👤 Campaigner only · ⛔ Leave blank

## Global rules

0. **House format for list cells** (from test run AS): numbered items, each `**Title.** text`. Applies to Injustice, Arguments, Why urgent, Why would they listen (pressure points).

1. Every cell carries an owner tag.
2. No source, no fact. If it can't be cited, write `[CAMPAIGNER: need X]`.
3. Low-context writing: no tool jargon, no raw counts a reader can't interpret.
4. No duplicated content across cells.
5. Never overwrite campaigner edits.
6. The whole brief is written in **English**, whatever the list. (The list language is still recorded in its own cell for copy generation.)

## Entry points and modes

- **Who starts a brief:** campaigners via the brief skill (on demand), or Chris via parl-monitor.
- **Flow:** builder drafts → proposes header values → campaigner submits the **pre-filled Asana form** → Zapier creates the sheet as today → builder writes the body cells into that sheet.
- So the builder **always writes into an existing sheet**. "Create" = updating a freshly made sheet; same rules for both.
- **Header cells belong to the form/Zapier.** The builder only proposes their values for the form; it never writes them into the sheet.
- **Update mode, per cell:**
  - Empty → fill.
  - Still holds the builder's earlier draft, unedited → may refresh with newer facts.
  - Edited by a person → leave it; put any suggested change in a sheet comment.
  - Changelog line in Notes: `<date> <who> updated <cells>`.
  - To tell "unedited draft" from "edited", the builder keeps a fingerprint of what it last wrote per cell.
- **To verify:** whether the Asana form supports pre-fill via URL parameters. If not, the skill outputs the form answers for copy-paste.

## Header

### 1. Campaign Name ✏️ — LOCKED 2026-10-06

- **Purpose:** internal label. Zapier copies it into the brief file name, Asana project and Marketo/Iterable programme. Staff read it, supporters don't (petition headline is written in Prepare).
- **Preferred format (from test run CT):** `<Provocative hook>? <Strong verb> the <Issue>`, e.g. `Prison for Praying? Stop the NI Conversion Bill`. The hook names the harm as a short question; the verb carries the call to action.
- **Fallback (from test run AS):** `<Strong verb> the <Issue>: <CTA>`, e.g. `Stop the Assisted Suicide Bill: Tell Your MP to Vote No`. (Original `Slogan: Issue` rejected.)
- **Must:** make sense on its own; carry a call to action; be lively. **Avoid:** procedural tags (years, stages) unless needed for uniqueness; slogans that mean nothing without context.
- **Language:** always English, whatever the list.
- **Vocabulary:** CitizenGO framing, not the official title (e.g. "Assisted Suicide", not "Terminally Ill Adults"). The exact official title always goes in Background / Context.
- **Constraints:** max 60 characters; no accents or special characters (Zapier); no "(DRAFT)" or internal notes (draft status goes in Notes).
- **Unique:** check against existing brief titles; a follow-up is "Phase 2", not a reused name.
- **Tier A:** issue from the bill/inquiry title, reframed via glossary. **Tier B/C:** issue from the news story, reframed via glossary.
- **Dependency:** a per-country framing glossary (official term → CitizenGO term).
- **Write path:** proposed for the Asana form; Zapier writes it. Campaigners can rename after director approval (cheat sheet), so update mode never touches it.

### 2. Campaigner (form field) — LOCKED 2026-10-06

- **Skill:** whoever runs the skill to create the brief.
- **parl-monitor:** Chris (or whoever submits the form for that draft).
- **Update mode:** never changed, even if someone else runs the skill. The editor goes in the Notes changelog.
- **All tiers:** identical.

### 3. Date of Submission (form field) — LOCKED 2026-10-06

- The date the Asana form is submitted (set by Zapier), not the date a draft was generated.
- Draft generation date goes in Notes.
- **Update mode:** never changed.

### 4. Urgency (form field) — LOCKED 2026-10-06

- **Default: Non-Urgent.** Urgent should be rare.
- **Timing constants:** submission → first email ≈ 3 working days; minimum petition run 14 days (2–3 weeks+ is normal); delivery 2 working days before the key date.
- **Propose Urgent only if all three hold:**
  1. There is a hard key date: vote/stage, consultation or evidence deadline, hearing, election, summit/treaty signing.
  2. That date is confirmed by an official source (parliament calendar, government/consultation page). News-only dates never trigger Urgent; they're flagged in Notes for the campaigner.
  3. The date is too close for a normal campaign: `key date − today < 3 working days + 14 days + 2 working days` (≈ 3 weeks).
- **Several dates:** use the nearest one we can still influence; list the rest in Background.
- **Form value:** the plain label only. Countdown, date and source go on the Builder tab.
- **Tight-window warning** (added after test run AS): when `latest launch − earliest launch ≤ 5 working days`, the campaign stays Non-Urgent but the launch-by date (`delivery date − 14 days`) is surfaced in the Notes line (`Drafted with brief builder · Launch by <date> · see Builder tab`) and in the Slack post.
- **Update mode:** never changed. If the key date moves, add a Notes line ("Key date moved to …") and flag it in Slack.
- **Check against v2 drafts:** Assisted Suicide (27 days) and OSA inquiry (25 days) were marked Urgent; under this rule both are Non-Urgent.

### 5. List and Sub-List (form fields) — LOCKED 2026-10-06

- **List:**
  - Skill run → the campaigner's own list (config table: campaigner → list).
  - parl-monitor → the list for that parliament's country (UK → EN GB).
  - Always the exact dropdown value, never free text (drafts have mixed `EN GB` / `EN_GB`).
- **Multi-country issues** (EU, UN, Council of Europe): **one global brief**, List = Global. Radar posts it to #campaigns-global and the relevant country channels; country lists join that brief rather than getting their own.
- **Sub-List = geographic region.** Set it only when the decision body is sub-national:
  - UK: Holyrood → Scotland; Stormont → Northern Ireland; Senedd → Wales.
  - Westminster → blank (whole list), even for England & Wales-only bills, because every MP votes.
  - Tier B/C: regional parliaments (Spanish autonomous communities, German Länder, etc.) → that region.
- **List codes (from the Asana campaign calendars, space-separated):** EN GB, EN US, EN CA, EN IE, EN AU, FR, FR CA, DE, DE AT, DE CH, IT, PL, SK, HR, HU, NL BE, PT PT, PT BR, HO, ES MX, ES AR, ES LATAM.
- **To verify:** these match the Asana form dropdown; the Global code; Sub-List values.
- **Update mode:** never changed.

### 6. Notes (form field) — LOCKED 2026-10-06

- Belongs to the campaigner. The builder proposes one line for the form: `Drafted with brief builder — see Builder tab`, plus `· Launch by <date>` when the tight-window warning applies (Cell 4).
- Everything else the builder records goes on the **Builder tab** (below), never in Notes.
- **Update mode:** never changed.

### 7. Approval Date (Zapier) — LOCKED 2026-10-06

- ⛔ Always blank. Zapier fills it on director approval.

## General information

### 8. Type of Campaign ✏️ — LOCKED 2026-10-06

- **Default: Opportunity.** Obligatory and Survival are extremely rare.
- Builder always suggests a type **with a one-line reason**; campaigner confirms.
- **Survival:** never suggested. Builder only flags "possible Survival" on the Builder tab when the issue could hit CitizenGO directly (NGO/foreign-agent laws, charity or data regulation, speech laws that could catch our content, platform or payment bans).
- **Obligatory:** suggested only when all three hold:
  1. Core issue (Life, Family & Education, Freedom).
  2. Low odds of winning (Tier A: persuadables can't close the 5CA gap; Tier B: seat arithmetic against us; Tier C: unknown, so this condition can't be met and Obligatory is never suggested).
  3. Comparable campaigns on this topic and list are in the **bottom 10%** for new members acquired (Bluebook).
- Bottom 10% is a trigger, not a definition: campaigners can still choose Obligatory for other reasons. When only some signals are present, keep Opportunity and note the signals on the Builder tab.
- **Update mode:** if the campaigner has set it, never changed.

### 9. Topic 🔒 — LOCKED 2026-10-06

- **One exact value:** Life · Family & Education · Freedom · Patriotism · Election Season · Other (confirmed current).
- **Why it matters:** Topic filters RF#1 comparables, TIM petitions and the Obligatory test. Wrong Topic = wrong benchmarks in three places.
- **Mapping:** parl-monitor's 10 campaign areas → one Topic each, set once in config. Tier B/C classify news text into the same 10 areas, then use the same mapping.
- **Elections:** any campaign triggered by an election (by-election, general, regional, referendum) is **Election Season**, whatever the underlying issue. The underlying issue goes on the Builder tab so comparables can also draw on that topic.
- **Several topics fit:** pick the one whose comparable campaigns match best; note the runner-up on the Builder tab.
- **Other:** means the builder couldn't decide. Always paired with a campaigner placeholder.
- **Dependency:** config table mapping the 10 campaign areas → Topic.

### 10. Main Purpose ✏️ — LOCKED 2026-10-06

- **One value only.** No secondary purpose recorded anywhere.
- **Order of precedence:**
  1. **Political Impact** if there's a named decision-maker and a key date (vote, consultation, hearing, election). Covers almost all Tier A triggers and all Election Season campaigns.
  2. Otherwise **List growth** if comparable campaigns on this topic and list are **above the list median** for new members acquired (Bluebook).
  3. Otherwise placeholder `[CAMPAIGNER: no decision date and comparables below median — confirm purpose]`.
- **Fundraise:** never suggested. Only the campaigner sets it (it switches on the funds cell and Fundraising Brief tab).
- **Update mode:** if the campaigner has set it, never changed.

### 11. Background / Context 🔒+✏️ — LOCKED 2026-10-06, revised after test run AS

- **Readers:** the director at approval, anyone reading the brief years later, and the copy generator. Low-context.
- **Three blocks, in this order:**
  1. **Narrative (≤250 words):** What (exact official title + what it would do) → Who (sponsor/proposer, party, deciding body, vote type) → Where it stands (stage + last event date) → What's next (key dates) → Why it matters (factual stake: what changes in law/practice, precedent set).
  2. **Path to victory:** where we stand on the numbers, then the realistic routes in order (e.g. persuadables → amendments → later stages/Lords/clock). **No probabilities.**
  3. **Fact sheet (labelled lines):** What · Who · Stage · Next date · 5CA summary (allies / opponents / persuadables, or party seats in Tier B/C) · Our history (earlier CitizenGO campaigns on the issue with signatures and links).
- **Sourcing:** every fact traceable to a source on the Builder tab. Tier C: two independent outlets per key fact, otherwise mark "(reported, unconfirmed)".
- **Banned:** tool jargon ("the monitor's ledger"), raw activity counts. A count is allowed only with meaning attached.
- **Must not repeat** "What is happening" (that cell is the news hook only).
- **Update mode:** refresh the stage/date lines and the 5CA summary if the cell is an unedited draft; otherwise suggest via a comment.

### 12. Estimated Launch date ✏️ — LOCKED 2026-10-06

- **Window:** earliest = submission + 3 working days; latest = delivery date − 14 days.
- **Suggest the earliest date** in the window (longest run, most follow-ups and list growth).
- **Clash check:** read the list's Asana campaigns calendar (`<LIST> Campaigns Calendar`, e.g. EN GB Campaigns Calendar). If another campaign launches on that list within 2 working days of the suggested date, move to the next clear working day inside the window. If none is clear, keep the earliest date and note the clash on the Builder tab.
- If latest < earliest, the campaign can't run its minimum length: this is the Urgent condition (Cell 4).
- Working days use that country's public holidays.
- **Update mode:** if the campaigner has set it, never changed; if the key date moves, recompute only an unedited draft.

### 13. Estimated date for Delivering Signatures ✏️ — LOCKED 2026-10-06

- **Date:** key date − 2 working days (country's public holidays).
- **Consultations / evidence calls:** delivery is the formal response, submitted 2 working days before closing, quoting the signature count.
- **No key date:** launch + 21 days, marked "(estimate)".
- **Include the method**, suggested from the target type:
  - Member votes (all members or persuadables) → **stack three methods** (confirmed in test run AS): per-signature emails to MPs during the campaign · constituency-matched delivery on the delivery date (each member gets their own constituents' count, via postcode) · a photographed handover at the parliament plus a total-count PDF to every member.
  - Minister / chair / single official → letter + request for in-person handover.
  - Consultation → formal submission.
- Never write "Before <date>"; always a specific date.

### 14. Ideas for eventual Offline Actions ✏️ — LOCKED 2026-10-06, revised after test run AS

- **Purpose:** feeds the Fundraising Lunch "Plan of Actions", so ideas must be concrete enough to fund.
- **No house style.** Each issue needs a different mix, so the cell is a **menu of 5–8 ideas across categories**:
  - **Mass mobilisation** (rallies, joint coalition events)
  - **Visibility** (billboard vans, posters, geo-targeted ads)
  - **Constituency targeting** (surgery visits, constituency letters, local media in target seats)
  - **Faith community** (letter-writing Sundays, vigils, clergy letters, pulpit mentions)
  - **Media** (press conference, handover photo-op, expert voices)
  - **Direct lobbying** (briefing allied members with constituency numbers)
- **Lead with what has worked on this issue before** (offline-actions history; e.g. assisted suicide: large coalition rallies, billboard vans, constituency targeting), then add other categories.
- **Each idea:** What · When (tied to the key date) · Where/who (tied to targets) · Cost band € (<€500) / €€ (€500–5k) / €€€ (>€5k) · Owner (Media Campaigner).
- **Faith-based actions** allowed where they fit the list and issue.
- **Guardrails:** nothing at private homes, nothing targeting private individuals, lawful in that country.
- **Banned:** generic ideas with no target, date or place.
- **Dependency:** offline-actions history per issue (from evaluated briefs' Timeline of Major Actions + campaigner input).

### 15. Petitions related TIM project 🔒 — LOCKED 2026-10-06, revised after test run AS

Source: Iterable Automated List Management guide (TIM section). Data: Bluebook 2.0 (Looker).

- **Just the suggested petition IDs**, ready for the TIM audience if one is run. Whether it runs depends on how the campaign's emails perform, which can't be known at the start.
- **Search window:** campaigns launched **12–24 months ago**, same list and country (Global brief: also the Bluebook "Global Campaign" filter). Same issue first, same Topic as fallback.
- **Format:** one per line, `<ID> — <title>` (title only so the ID is recognisable). Up to 10.
- **None found:** "No related petitions in the 12–24-month window."
- **Update mode (after launch):** if Launch 1 hits **CTAx1000 ≥ 55** or acquisition above the list average, flag "TIM candidate: discuss with manager" in Slack. The template choice (Option 1/2/3) is made then, not at plan stage.
- **All tiers:** identical.

## Prompts for AI — Plan phase

### 16. What is the language for this petition? 🔒 — LOCKED 2026-10-06

- From the List via config, **always naming the variant** (the copy step needs it):
  - EN GB → English (UK spelling) · EN US → English (US spelling) · EN CA / EN IE / EN AU → English (that country's spelling)
  - DE → German · DE AT → German (Austrian) · DE CH → German (Swiss: "ss", never "ß")
  - FR → French · FR CA → French (Canadian) · NL BE → Dutch (Belgian)
  - PT PT → Portuguese (Portugal) · PT BR → Portuguese (Brazil)
  - HO → Spanish (Spain) · ES MX / ES AR / ES LATAM → Spanish (Latin American, country noted)
  - IT, PL, SK, HR, HU → that language
- **Then (added after test run AS)** — because this cell feeds `{{LANGUAGE}}` in the copy generator:
  - **Institutional terms** for the deciding body (e.g. Westminster: "MPs", "the House of Commons", "Second Reading", "free vote", "the Bill"; Stormont: "MLAs", "the Assembly", "Second Stage", "Petition of Concern", never "MPs" or "third reading").
  - **Framing vocabulary** from the glossary (e.g. "assisted suicide", never "assisted dying"; "doctors", not "providers").
  - **No tone or style instructions** (left to the copy templates).
- Global brief: list every participating language.
- **Dependency:** list → language config table; institutional-terms table per deciding body; framing glossary.

### 17. Who will sign the emails? 🔒 — LOCKED 2026-10-06

- **The campaigner** on the brief (full name, from the Campaigner email via config).
- **Update mode:** follows the Campaigner cell, which never changes.

### 18. Who is the petition addressed to? ✏️ — LOCKED 2026-10-06

- **Principle (cheat sheet):** ideally one named individual who is in charge of the decision and can and will make it.
- **Target by decision type:**

  | Decision type | Target |
  |---|---|
  | Government bill / policy | Responsible minister, named |
  | Free / conscience vote | All members of the chamber (see below) |
  | Consultation | Minister or body running it, named |
  | Committee inquiry | Committee chair, named |
  | EU Parliament vote | Rapporteur, named, plus all MEPs |
  | EU Commission proposal | Responsible Commissioner, named |
  | Election | Candidates in that seat, named |
  | Regional decision | Regional minister, named |

- **Free votes:** no automatic per-signer routing exists, so delivery is manual. **Default: message every member.** Then add a suggestion line in the cell:
  `Option: split into separate petitions by 5CA segment — persuadables (0/+/−): N members, ask = <vote>; allies (++): N, ask = <speak up / amend>; firm opponents (−−): N, no petition.`
  Tier B/C: split by party (seat counts) instead of members.
- **Always:** verify the **current** officeholder against an official source, date-checked; record role + name; contact route goes on the Builder tab. Tier C: officeholder confirmed only by news → campaigner placeholder.
- **Banned:** unnamed groups ("MPs who could be persuaded").

### 19. What are we asking for in the petition? ✏️ — LOCKED 2026-10-06

- **Starts with an infinitive verb:** Vote against, Reject, Withdraw, Amend, Protect, Pledge to…
- **One ask, aimed at the Cell 18 target.** Supporter actions belong in the copy, never here.
- **Checkable:** names the decision, the stage and the date, so Evaluate can answer "did we win?".
- **Within the target's power** (a committee chair can't withdraw a bill).
- **Uses CitizenGO framing** (glossary), e.g. "Vote against the Assisted Suicide Bill at Second Reading on 11 September 2026."
- **Max 30 words;** no capitals for emphasis.
- **Segment asks (confirmed in test run AS):** whenever Cell 18 offers a 5CA split, add `Segment asks (if split):` with one line per segment (e.g. persuadables: vote against…; allies: speak in the debate and use your constituents' numbers). The main ask stays first and single.
- **No suggested petition text** in this cell.
- **No fallback asks.** Ever. Fallbacks are a campaigner call.

### 20. Why would they listen to us? (Theory of Change) ✏️ — LOCKED 2026-10-06, revised after test run AS

- **Shape (hybrid):**
  1. **Lead sentence:** `If we <action>, <target> will <behaviour>, because <pressure point>.`
  2. **3–6 numbered pressure points**, each `**Label:** one line of evidence`, sourced. These give the copy generator separate levers to use.
- **Pressure points to draw from** (only those that apply):
  - **Vote arithmetic:** Tier A 5CA (allies, opponents, gap, persuadables). Tier B/C party seat arithmetic, coalition dependence.
  - **Members move:** past shifts between votes on the same issue.
  - **Electoral exposure:** persuadables' majorities; upcoming elections, polling.
  - **Our members in their seats:** count from postcode data where available. A lever statement only; don't assume localised sends.
  - **Credible allies:** serious voices on our side, so the target can agree without looking extreme.
  - **Whip:** free vote vs whipped.
  - **Process weight:** consultations count responses; committees cite evidence; procedural tools (e.g. Petition of Concern).
- **Be honest:** no credible lever → write "No clear lever; value is in list growth".
- **Banned:** "scale of debate" filler, generic "MPs represent constituents".
- **Dependency:** member counts by constituency/region from postcode data.

### 21. What is happening that we are responding to? 🔒 — LOCKED 2026-10-06

- **The news hook:** the latest event, with its date. 1–2 sentences, max 40 words, present tense.
- Tier A: stage change, debate, vote or publication. Tier B/C: latest news report. Skill run: what prompted the campaigner.
- **Then a storytelling line (added after test run AS):** `Storytelling: villain = <the measure / the public actors driving it>; princess = <the decision-makers we need to win over>; hero = the reader (<their role, e.g. a constituent>); helper = CitizenGO (<how we carry their voice>).`
  - Villain may be a measure or public actors/organisations; never a private individual.
- Source on the Builder tab.
- **Must not reuse any sentence from Background.**

### 22. What is the key point of injustice at stake? ✏️ — LOCKED 2026-10-06, revised after test run AS

- **A numbered list of 5–10 injustices.**
- **Each item:** `**Title.** One or two sentences.` (NI-brief style.)
  - **Who is harmed:** concrete people, not "society".
  - **Who is doing it:** a named public actor (sponsor, minister, campaign organisation) where it fits.
  - **The wrong:** what they lose.
- **Mix of origins:** angles from the best-performing comparable campaigns (by CTAx1000) **only where genuinely relevant**, plus fresh angles. Proven first.
- **No labels in the cell.** Each item's origin (`Proven: <campaign>, CTAx1000 <n>` or `Fresh`) is recorded on the Builder tab, so performance can be learned from later.
- **True and defensible:** every factual claim sourced; no exaggeration beyond the evidence.
- **Guardrails:** public figures and institutions only, never private individuals; no dehumanising language.

## Prompts for AI — Prepare phase

### 23. What are some arguments supporting our point of view? ✏️ — LOCKED 2026-10-06, revised after test run AS

- **5–10 numbered arguments** (same count as Injustice).
- **Each item (NI style):** `**Title.** A short paragraph with the evidence and any quote woven in.`
- **Mix of types:** principle, evidence, precedent, voice (Tier A: allied members' Hansard quotes from the monitor; Tier B/C: allied orgs, experts, professional bodies), practical. Proven arguments from high-CTAx1000 comparables may be reused.
- **No labels in the cell.** Each argument's type, origin (Proven/Fresh) and source are recorded on the Builder tab.
- **No unsourced statistics.** No source → left out. Contested claims flagged "(contested)".
- **Then "What they'll say":** the opponents' top 3 arguments, numbered, each `**"Their claim."** Our answer.`, sourced on the Builder tab.

### 24. Why is it urgent that we take action now? ✏️ — LOCKED 2026-10-06

- **Supporter-facing reason to act now.** Every campaign needs one, unlike the Urgency flag (Cell 4).
- **A numbered ladder of 3–5 urgency items**, each `**Title (stage).** One sentence.` (NI style, confirmed in test run AS), max 60 words each, following the email series:
  1. Launch: the moment + what closes after it.
  2. Mid-campaign: time left + momentum (opponents mobilising, new developments).
  3. Final week.
  4. Final 48 hours.
  5. (Optional) Post-event, if a later stage follows.
- **Each line uses the three parts where they fit:**
  - **The moment:** key date + what happens on it.
  - **What closes:** what can't be influenced after it. Sourced or from parliamentary procedure, never invented.
  - **Time left:** as a duration ("five weeks"), not a date, because copy goes out later than the brief.
- **No hard date:** Tier C news-only → "expected <month> (reported)". No date at all → the honest reason (news momentum, consultation being drafted, window before recess) or a placeholder. **Never invent a deadline.**
- **Banned:** activity counts as urgency ("345 debate contributions").

### 25. Describe a bad outcome if we do not win ✏️ — LOCKED 2026-10-06

- **One main paragraph (60–120 words) + 2 one-line alternates** for later emails.
- **Style (from test run AS): concrete scenes.** 3–4 short everyday scenes showing who is affected and how (e.g. "A GP signs off a death after two short appointments"), then the long-term precedent, then "If you don't act now…". Scenes use illustrative roles, never real private individuals.
- **Who:** the named public actor from Injustice, driving it.
- **Evidence:** sourced precedent from elsewhere (what happened after similar laws/decisions).
- **Limit:** realistic. Nothing worse than the evidence supports.
- RF#4/2 comment points here.

### 26. Describe a good outcome if we do win ✏️ — LOCKED 2026-10-06

- **One main paragraph (60–120 words) + 2 one-line alternates.**
- **Structure (plain, confirmed in test run AS):** the concrete win (Cell 19 ask met) → the wider gain for our cause. No scenes; vividness belongs to the bad outcome.
- **Who:** our members as the reason it happened ("because you acted…").
- **Evidence:** precedent of similar wins where one exists.
- **Limit:** stays within what this ask achieves. No add-on goals (e.g. "funding redirected to palliative care" belongs to a different campaign).
- RF#4/1 comment points here.

### 27. If we are going to raise funds, what will we spend the money on? ✏️ — LOCKED 2026-10-06

- **Default: `N/A — AA emails carry the generic monthly-donation footer only.`** (Checked against live EN AU and EN GB AA emails, Oct 2026.) The footer is never amended.
- **Fill it only if** Main Purpose = Fundraise, or the campaigner plans campaign-specific donation asks (OTD/FR emails).
- **When filled:**
  - 3–5 spend items, each `What — why it moves the target — cost band`, built from Cell 14's offline actions plus ads and delivery, so the promise and the plan can't drift apart.
  - Only things we'll actually do; donors are promised exactly these.
  - Total band (€ / €€ / €€€).
  - Main Purpose = Fundraise → also fills the Fundraising Brief tab.

### 28. Which sources do you want to include? (titles + URLs) 🔒+✏️ — LOCKED 2026-10-06

- **Supporter-facing:** may appear below the PS in the launch, and copy links to sources inline.
- **Format (NI style, confirmed in test run AS):** `- <article headline as published> [<Publisher>, opinion]: <URL>`, one per line. Drop `, opinion` for news reports and primary sources (e.g. `[UK Parliament]`). Example: `- Gavin Robinson: Conversion bill is a siren call to parents and everyone who values religious liberty [News Letter, opinion]: https://www.newsletter.co.uk/…`
- **Up to 8 sources, at least one of each:** Primary (official bill/consultation/decision page) · News (reputable outlet) · Evidence (report/study behind the strongest Cell 23 argument).
- **Allowed:** reputable outlets; comment/opinion sites (e.g. UnHerd, The Spectator); individual Substacks if onside; allied organisations (ADF International, Jubilee Campaign…). Opinion pieces and allied organisations can't be the **only** source for a factual claim.
- **Never:** Wikipedia; outlets on the country's **hostile-outlet deny-list**; internal tools (e.g. parl-monitor-partner); anything behind a login.
- **Paywalls:** avoid; flag if it's the only source.
- **Language:** prefer the list's language for supporter-facing sources; English is fine for primary sources that only exist in English.
- **Links checked** at build time and again in update mode before launch.
- Full sourcing for every fact lives on the Builder tab; this cell is the curated supporter-ready subset.
- **Dependency:** per-country hostile-outlet deny-list (maintained by campaigners).

### 29. What should the image for this campaign look like? ✏️ — LOCKED 2026-10-06, revised after test run AS

- **AI-generated images are the default.** Tested with real Canva generations (brief-test-images/AS-*.jpg).
- **Cell content, in order:**
  1. **Main prompt (NI style), one paragraph:** `Text-free 16:9 editorial photograph: <subject, setting, light>. Mood: <one line>. Avoid: <list>.`
  2. **Two alternative concepts**, one line each. Useful as images for different emails in the series (e.g. a "decision ahead" image for urgency emails).
  3. **Overlay text for Canva:** max 6 words, in the list's language (with English gloss). Added in Canva in the brand font, **never baked into the AI image** (AI text isn't brand font, editable or translatable).
- **Avoid list always includes:** identifiable real people, party colours or logos, anything sensational or graphic unless the campaigner chooses otherwise.
- **Graphic imagery:** builder suggests non-graphic; the campaigner decides.
- **Real people (guardrail):** never an AI-generated or altered photorealistic likeness of a real, identifiable person.

## Shared comparables set — LOCKED 2026-10-06

Computed **once** per build from Bluebook 2.0, stored on the Builder tab, read by every cell that needs it (Type, Main Purpose, TIM, Injustice, Arguments, RF#1).

- **Window:** last 24 months (TIM uses the 12–24 month slice).
- **Selection:** same issue first, then same Topic + list. Global brief: include Global Campaign filter.
- **Per campaign:** title (full), list, launch month, Bluebook link, signatures, new members, reactivated members, acquisition %, € raised, CTAx1000.
- **List benchmarks:** list median for acquisition %, CTAx1000, € raised; plus the bottom-10% acquisition cut-off (for Type).

## Red Fox Four

### 30. RF4 scores (Plan and Evaluate) ⛔ — LOCKED 2026-10-06

- Always blank: campaigner and director judgement. TOTAL formulas never touched.

### 31. RF#1 comment — people or money? 🔒 — LOCKED 2026-10-06

- **3–5 comparables from the shared set**, full titles, so the reader compares several similar campaigns, never just one.
- **Per comparable, two groups:**
  - **People:** signatures · new members · reactivated members · acquisition %
  - **Money:** € raised
  - Plus Bluebook link.
- **Group averages** for the comparables vs the **list median**, each marked ▲ above / ▼ below.
- **Real data only** (from test run AS): every figure comes from Bluebook 2.0. Never leave placeholders; if a metric is unavailable, omit it and note why on the Builder tab.
- **One-line read** (a prediction, not a score), e.g. "Comparables sit above the EN GB median on acquisition and below on € raised: expect people more than money."

### 32. RF#2 comment — helps friends or allies? ✏️ — LOCKED 2026-10-06, revised after test run AS

- **3–5 items:** `<ally> — how this campaign helps them`.
- **Describe allies generically** ("Pro-life organisations", "Allied MPs who spoke at Second Reading", "Disabled people's advocates"). **Name an organisation only if it's a formal partner on this campaign or petition** (e.g. a partner petition with Christian Concern, ADF International or SPUC).
- The allies register is still used to find allies; it just isn't quoted by name in the cell.
- **How:** concrete benefit (speeches amplified, amendment backed, platform given, coalition built).
- **Banned:** 5CA vote tallies (they belong in Cell 20).

### 33. RF#3 comment — hurts enemies and their allies? ✏️ — LOCKED 2026-10-06

- **3–5 named items:** `Who — how this campaign costs them`, sourced. Name them directly (confirmed in test run AS).
- **Who:** named public actors: sponsor, vocal supporters, lobby groups, campaigning organisations, publicly declared funders.
  - Tier A: sponsor + supporters in debate + organisations giving evidence in favour.
  - Tier B/C: organisations and politicians pushing the measure in news.
  - Check the **opponents register** first.
- **How:** political/reputational cost by legitimate means (capital spent, vote on public record, funding scrutiny, delay).
- **Guardrails:** public actors only; never personal, never aimed at livelihoods.
- **Banned:** "not tracked" non-answers.

### 34. RF#4/1 and RF#4/2 comments ✏️ — LOCKED 2026-10-06

- **Purpose:** give the scorer the strategic facts the outcome paragraphs (written for supporters) leave out, so two directors score the same campaign alike.
- **RF#4/1 (gain if we win):** pointer to Good outcome (Cell 26) + **one sourced line on what the win is worth beyond this campaign**, choosing whichever applies:
  - **Durability:** how long the win lasts (e.g. Bill falls for the session vs a consultation the government can revisit).
  - **Precedent:** effect on other jurisdictions considering the same measure.
  - **Position:** what it does for us/allies on later stages.
- **RF#4/2 (cost if we lose):** pointer to Bad outcome (Cell 25) + **backlash check**. Default line: "No backlash risk identified → expect 0." Flag only with concrete evidence of:
  - Mobilising the other side / raising an obscure measure's profile.
  - Our input discounted (e.g. template consultation responses reported separately). Also suggest the fix: supporters write their own response.
  - Speeding up the harm (fast-tracking to "settle" it).
  - Damaging allies (letting opponents paint them as foreign-funded/extreme).
- Never a score; scores stay blank (Cell 30).

### 35. Evaluate stage ⛔ (build) — LOCKED 2026-10-06

- **At build time:** ⛔ all Evaluate cells blank (RF4 Evaluate scores, Timeline of Major Actions, Evaluate Dashboard, judgement questions).
- **Update mode after the campaign closes:**
  - **Pre-fill numbers** from Bluebook 2.0: Bluebook link, number of emails sent, total signatures, new members, reactivated members, acquisition %, total € raised; Asana project link, Asana Evaluate task link, copy-package Google Doc link.
  - **Draft the Timeline of Major Actions** from Asana tasks and the email send log (date — action — comment), marked as a draft for the campaigner to edit.
  - **Never fill judgement fields:** political impact evaluation, won the fight?, media/politicians talked about it?, delivered signatures (and how)?, good decision?, good practices, improvements, conclusions, other comments, moving forward. Also never: € spent, cost of offline actions.

## Five Column Analysis sheet

### 36. 5CA sheet — LOCKED 2026-10-06

- **When:** whenever there's a voting body (chamber, committee, board), even if the petition targets a minister. Otherwise write "N/A: no voting body".
- **Rows:**
  - Tier A: one per member, from the monitor's placements.
  - Tier B/C: one per party, seats spread across the columns (cheat sheet allows counts per party); individual rows only for swing members named in news.
- **Placement:** Tier A = monitor's evidence-based score. Tier B/C = party position from manifesto/whip/statements, sourced.
- **Comments:** the evidence behind the placement (votes, speeches, Hansard links). Tier B/C add confidence (high/medium/low).
- **No recorded position:** all five columns 0, comment "No recorded position". Kept distinct from a genuine 0.
- **Target (Y/N):** Y for 0, +, −, and no-record members who aren't abstentionist or devolved-seat. N for ++ and −−. Tier B/C: Y for parties that could swing.
- **Two sections (from test run AS):** Section 1 **Targets**: every Target = Y row, alphabetical, with evidence. Section 2 **All members**: everyone including targets, alphabetical. The TOTAL row sums Section 2 only (no double counting). `# Seats` = 1 per member row; party seat counts for party rows (Tier B/C).
- **Total row:** formulas kept.
- **Evaluate columns (update mode after the vote):** Tier A fills Vote from division records; Tier B from open parliamentary data where it exists; Tier C left to the campaigner. Vote Y/N = for/against the **bill**, not for/against us; the comment states which way round applies.

## Campaign Narrative sheet — LOCKED 2026-10-06

- ⛔ Left blank. Optional and written by the campaigner for Evaluation Meetings.

## Allies and opponents registers — LOCKED 2026-10-06

- **Per-country config tables**, maintained by campaigners, starting (mostly) empty and growing over time.
- **Allies seed (UK):** Christian Concern, ADF International, SPUC (partner petitions), plus others as added.
- **Opponents:** starts empty.
- **Learning loop:** each build lists newly discovered allies/opponents (from debates, news, partner petitions) on the Builder tab as **proposed additions**; a campaigner approves before they join the register.

## Builder tab — LOCKED 2026-10-06

A dedicated tab, always the **last tab** in the sheet. The only place the builder writes about itself.

- **Tier** (A/B/C) and the sources used.
- **Key dates:** each with countdown, official/news source, confirmed or unconfirmed. Moved dates logged here and flagged in Slack.
- **Campaigner checklist:** every cell still holding a `[CAMPAIGNER: …]` placeholder, with what's needed.
- **Changelog:** `<date> <who> updated <cells>`.
- **Fingerprints:** what the builder last wrote in each cell, so update mode can tell an untouched draft from a human edit.
- Created on first run if missing; appended to, never rewritten.

## Dependencies to build

| # | Dependency | Used by | Starts |
|---|---|---|---|
| 1 | Framing glossary per country (official term → CitizenGO term) | Cells 1, 19 | Empty |
| 2 | Campaigner → list, full name config | Cells 2, 5, 17 | From Asana users |
| 3 | List → language variant config | Cell 16 | Rulebook table |
| 4 | 10 campaign areas → Topic mapping | Cell 9 | From parl-monitor |
| 5 | Country public-holiday calendars | Cells 12, 13 | Public data |
| 6 | Asana campaigns calendar per list | Cell 12 | Exists (`<LIST> Campaigns Calendar`) |
| 7 | Bluebook 2.0 access (comparables, TIM, Evaluate numbers) | Shared set, 8, 10, 15, 22, 23, 31, Evaluate | Exists (Looker) |
| 8 | Member counts by constituency/region (postcode data) | Cell 20 | To check |
| 9 | Hostile-outlet deny-list per country | Cell 28 | Empty |
| 10 | Allies register per country | Cell 32 | UK seed: Christian Concern, ADF International, SPUC |
| 11 | Opponents register per country | Cell 33 | Empty |
| 12 | Opportunity-record feeds: Tier A monitor, Tier B open-data fetch, Tier C news scan | All | Tier A exists (UK; EP and DE in progress) |

## To verify

- Asana form supports pre-fill via URL parameters (else copy-paste answers).
- List dropdown values match the calendar codes; the Global list code; Sub-List values.
- Exact Main Purpose dropdown labels.
- How parl-monitor currently sources Bluebook data (repo `thejoycething-code/parl-monitor`).
