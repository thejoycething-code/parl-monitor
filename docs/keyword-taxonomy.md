# Parliamentary Monitor: keyword taxonomy
**Version 0.1 (draft for review) | 1 August 2026 | Owner: Christopher**

## Purpose

This taxonomy is the filter layer of the Parliamentary Monitor pipeline. It is applied to the text fields of every item ingested from the source feeds: bill titles and long titles, PQ questions and answers, Hansard contributions, EDM text, committee inquiry titles and descriptions, SI names and explanatory memoranda, consultation titles, and written ministerial statements.

Every item that survives the filter is written to the store with its issue tags, tier, and a draft "why it matters" line. The weekly digest, urgent alerts and MP intelligence are all views of that store. Nothing is written for the digest directly.

## Matching conventions

- Matching is case-insensitive.
- `"quoted phrases"` require an exact phrase match.
- An asterisk (`*`) is a stem wildcard: `decriminalis*` matches decriminalise, decriminalisation, decriminalised.
- Short or ambiguous terms use word-boundary matching so `RSE` does not match "nurse".
- US spellings are included where Hansard or witnesses may use them (fetal/foetal).
- Terms compile to a YAML config at build time; this document is the human-readable master.

## Tiers and triage

**Tier 1 (auto-include).** High-precision terms. A match tags the item with the issue area and sends it straight to the review queue.

**Tier 2 (triage).** Broad or ambiguous terms. A match sends the item to a Claude relevance pass, which scores it and drafts the one-line "why it matters" for human edit.

**Triage scoring rubric (Claude pass):**

| Score | Meaning | Destination |
|---|---|---|
| 0 | Irrelevant to any tracked issue | Discard (logged) |
| 1 | Background awareness only | Store, no digest by default |
| 2 | Monitor: belongs in the weekly digest | Review queue as [WATCH] or [NOTE] |
| 3 | Act: likely campaign or lobbying trigger | Review queue as [ACT] candidate, alert-eligible |

**Entity watchlist.** Named bills, reviews, organisations and parliamentarians. Any item mentioning a watchlist entity is included regardless of keyword match, at minimum score 2.

**Global exclusions.** Terms that alone generate noise and never match without a Tier 1 companion: *termination* (contracts, employment), *conversion* (loft, data, rugby, currency), *transition* (energy, EU, staffing), *blocker* (beta blockers, planning), *gender* alone, *safeguarding* alone, *education* alone, *equality* alone.

---

## Issue areas

### 1. Abortion

- **Tier 1:** abortion; "Abortion Act 1967"; "termination of pregnancy"; "safe access zone*"; "buffer zone*"; decriminalis* (within 10 words of abortion/pregnancy); "abortion time limit"; foetal viability; fetal viability; "pills by post"; "telemedicine abortion"; "at-home abortion"; "sex-selective abortion"; "Offences Against the Person Act 1861"; "Infant Life (Preservation) Act"; "Ground E"; "disability-selective"; "Down's syndrome" (abortion/screening context); BPAS; "MSI Reproductive Choices"
- **Tier 2:** reproductive rights; reproductive healthcare; "crisis pregnancy"; "conscientious objection"; gestational limit; foetal pain; abortion statistics; "Public Order Act" (s.9 / clinic context); "silent prayer" (cross-tag with free speech)
- **Notes:** decriminalisation is currently live via amendment to Government criminal justice legislation rather than a standalone bill, so bill-level tracking alone will miss it. Amendment papers on any Home Office or MoJ bill must run through this area's terms.

### 2. Assisted dying and end of life

- **Tier 1:** "assisted dying"; "assisted suicide"; euthanasia; "Terminally Ill Adults"; "End of Life Bill"; "Suicide Act 1961"; "physician-assisted"; "assisted death"
- **Tier 2:** "palliative care"; hospice; "end of life care"; "terminal illness"; "mental capacity" (end-of-life context); "right to die"; "death with dignity"; coercion (end-of-life context); "anorexia" (capacity/eligibility debate context)
- **Notes:** palliative care and hospice funding items score 2 by default; they are the positive-agenda flank of this area and useful for coalition framing.

### 3. Gender medicine and children

- **Tier 1:** "puberty blocker*"; "puberty-suppressing hormones"; "cross-sex hormones"; "Cass Review"; Tavistock; GIDS; "gender identity service*"; "gender dysphoria"; "gender questioning children"; "youth gender"; "gender incongruence" (minors context)
- **Tier 2:** detransition*; "gender-affirming"; "Gillick competence"; "private prescriptions" (blockers context); "gender clinic*"; "indefinite ban" (blockers context)
- **Exclusions:** transition alone; blocker alone; hormone alone (menopause/HRT noise).

### 4. Conversion practices

- **Tier 1:** "conversion therapy"; "conversion practices"; "conversion therapy ban"; "Conversion Practices Bill"
- **Tier 2:** "gender exploratory therapy"; "talking therap*" (in CT context); "religious exemption" (CT context); "affirmation-only"; "parental consent" (CT context)
- **Notes:** cross-tag with area 3 (a ban drafted to cover "gender identity" is the live risk to exploratory therapy) and area 8 (prayer and pastoral care exemptions).

### 5. Sex-based rights and single-sex spaces

- **Tier 1:** "single-sex space*"; "single-sex service*"; "single-sex ward*"; "Gender Recognition Act"; "gender recognition certificate"; "self-identification" / "self-ID" (gender context); "biological sex"; "legal definition of woman"; "For Women Scotland"; "women's sport"; "female category"
- **Tier 2:** "Equality Act 2010"; "Sullivan Review"; "sex and gender data"; "changing room*"; "toilet provision"; transgender (broad); "protected characteristic"; "women's prison*"
- **Notes:** Equality Act mentions are extremely frequent; the triage pass should score 2+ only where sex/gender definitions, single-sex exceptions or guidance revisions are at stake.

### 6. Parental rights and education

- **Tier 1:** "relationships and sex education"; RSE; "sex education guidance"; "gender questioning children" (schools guidance context); "parental consent" (education/medical); "parental rights"; "right to withdraw" (RSE context); "home education"; "elective home education"; "children not in school"
- **Tier 2:** PSHE; curriculum review; "external providers" (RSE materials context); "smartphone* in schools"; "faith school*"; "collective worship"; admissions (faith context); safeguarding (only with education companion term)
- **Notes:** Northern Ireland RSE regulations remain a distinct devolved thread; tag NI items accordingly.

### 7. Free speech and online safety

- **Tier 1:** "Online Safety Act"; "age verification"; "age assurance"; "free speech"; "freedom of expression"; "non-crime hate incident*"; "silent prayer"; "Higher Education (Freedom of Speech)"; censorship
- **Tier 2:** Ofcom (content regulation context); misinformation; disinformation; "harmful content"; "hate speech"; blasphemy; "client-side scanning"; encryption (safety context); "street preacher*" (cross-tag with area 8)
- **Notes:** the standing risk framing carries over from the current briefing doc: powers granted for child protection can migrate toward viewpoint censorship. The triage pass should surface scope-expansion language ("legal but harmful", new priority-content categories) at score 3.

### 8. Freedom of religion or belief

- **Tier 1:** "freedom of religion or belief"; FoRB; "Christian persecution"; "persecution of Christians"; "religious persecution"; "Truro Review"; "Special Envoy for Freedom of Religion"; apostasy; "blasphemy law*"
- **Tier 2:** "religious minorit*"; "religious conversion" (asylum context); chaplain*; "places of worship" (security/attacks context); Nigeria / Pakistan / China (persecution context, country list maintained by team)
- **Notes:** includes domestic manifestation cases (street preaching arrests, employment cases) which cross-tag with area 7.

### 9. Marriage and family

- **Tier 1:** "marriage law"; "weddings law"; "Law Commission" (weddings/cohabitation context); "cohabitation reform"; "cohabitation rights"; "marriage allowance"; "family breakdown"; "no-fault divorce"
- **Tier 2:** "civil partnership*"; "family hub*"; fatherhood; "forced marriage"; "humanist marriage"; "family stability"
- **Notes:** deliberately lean. Childcare and general family-benefits items are excluded unless the team requests otherwise; they overwhelm the digest for little campaign value.

### 10. Surrogacy and embryology

- **Tier 1:** surrogacy; surrogate (pregnancy context); "Surrogacy Arrangements Act"; "Human Fertilisation and Embryology"; HFEA; "commercial surrogacy"; "embryo research"; "14-day rule"; "gamete donation"; "egg donation"
- **Tier 2:** "fertility treatment"; IVF (policy context); "donor conception"; "donor-conceived"; "mitochondrial donation"; "genome editing" (embryo context)
- **Notes:** ties directly to the Bought and Broken documentary workstream; any Law Commission surrogacy implementation signal is an automatic score 3.

---

## Entity watchlist

**Live bills (seed list; stages shown are illustrative as of drafting and MUST be populated from the Bills API at build):**

| Bill | Legislature | Our areas |
|---|---|---|
| Terminally Ill Adults (End of Life) Bill | Westminster (Lords stages) | 2 |
| Crime and Policing Bill (abortion decriminalisation clause) | Westminster (Lords stages) | 1 |
| Children's Wellbeing and Schools Bill | Westminster | 6 |
| Assisted Dying for Terminally Ill Adults (Scotland) Bill | Holyrood | 2 |
| Conversion practices legislation (draft/pre-legislative) | Westminster | 4, 3, 8 |

Board rules: a bill enters the watchlist when introduced (or a draft is published) and tagged to any area; it leaves at Royal Assent, withdrawal, or fall at end of session, with one closing entry in that week's digest.

**Named reviews and processes:** Cass Review implementation; Sullivan Review (sex and data); Law Commission weddings response; Law Commission surrogacy response; RSE statutory guidance review; Online Safety Act codes of practice (Ofcom).

**Organisations (committee-witness and stakeholder watch, both sides):** Right To Life UK; SPUC; CARE; Christian Concern / Christian Legal Centre; ADF International; Care Not Killing; Sex Matters; Christian Institute; Coalition for Marriage; BPAS; MSI Reproductive Choices; Dignity in Dying; Humanists UK; Stonewall; Mermaids.

**Parliamentarians (seed list only; the working list is generated and maintained from the MP voting tracker and EDM signatory data, not hand-curated):** Kim Leadbeater; Danny Kruger; Tonia Antoniazzi; Stella Creasy; Carla Lockhart; Jim Shannon; Lord Falconer; Baroness Grey-Thompson. Any contribution by a listed parliamentarian on any topic scores minimum 1 and is logged to their intelligence profile.

## Devolved tagging

Every item carries a jurisdiction tag: UK, England, Scotland, Wales, NI. Holyrood, Senedd and NI Assembly feeds run through the same taxonomy. Devolved items appear in their own digest section and never displace Westminster items from the week ahead.

## Maintenance

- The taxonomy is reviewed monthly against a sample of discarded (score 0) items to catch false negatives.
- Any [ACT] item that reached the team through another route (press, partner orgs) but was missed by the filter triggers an immediate taxonomy patch.
- New bills matching any Tier 1 term are auto-proposed for the watchlist; a human confirms.
- Version-control this file; the YAML config is generated, never hand-edited.
