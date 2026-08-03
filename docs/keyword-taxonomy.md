# Parliamentary Monitor: keyword taxonomy
**Version 0.2 | 3 August 2026 | Owner: Christopher**

## Purpose

This taxonomy is the filter layer of the Parliamentary Monitor pipeline. It is applied to the text fields of every item ingested from the source feeds: bill titles, PQ questions and answers, EDM text, committee business titles, SI names, consultation titles, What's On descriptions and written ministerial statements.

Every item that survives the filter is written to the store with its issue tags and tier; triage scores it and drafts the "why it matters" line. The weekly digest, alerts and MP intelligence are all views of that store. Nothing is written for the digest directly.

**This file is the master.** `config/taxonomy.yaml` is generated from it: edit here, then run `python3 tools/generate_taxonomy.py`. The test suite fails if the two drift (tests/test_taxonomy_sync.py), so hand-edits to the yaml cannot survive.

## Matching conventions

- Matching is case-insensitive, except that ALL-CAPS terms (RSE, EOTAS, PATHWAYS, CARE, FoRB counts too) match case-sensitively, so RSE never matches "nurse" and CARE never matches "social care".
- `"quoted phrases"` require an exact phrase match; quotes are part of the term syntax and carry into the yaml.
- A trailing asterisk (`*`) is a stem wildcard: `"safe access zone*"` matches zone and zones.
- Smart quotes in source text are folded to straight quotes before matching ("Children's" matches "Children’s").
- US spellings are included where Hansard or witnesses may use them (fetal/foetal).
- Term lines below are semicolon-separated; the `{#key}` anchor on each heading is the area's yaml key. Both are parsed by the generator: keep the format.

## Tiers and triage

**Tier 1 (auto-include).** High-precision terms. A match tags the item and sends it to the scoring pass with a floor of digest consideration.

**Tier 2 (triage).** Broad or ambiguous terms. A match sends the item to the Claude relevance pass (handoff section 7 rubric: 0 discard-and-log, 1 background, 2 digest, 3 campaign trigger).

**Entity watchlist** (config/watchlist.yaml, not this file): named bills, Acts, reviews, organisations and parliamentarians. Any item mentioning a watchlist entity is included regardless of keyword match, at minimum score 2.

## Issue areas

### 1. Abortion {#1_abortion}

- **Tier 1:** abortion; "Abortion Act 1967"; "termination of pregnancy"; "safe access zone*"; "buffer zone*"; "abortion time limit"; "foetal viability"; "fetal viability"; "pills by post"; "telemedicine abortion"; "sex-selective abortion"; "Offences against the Person Act 1861"; "Infant Life (Preservation)"; "Ground E"; "disability-selective"; BPAS; "MSI Reproductive Choices"
- **Tier 2:** "reproductive rights"; "reproductive healthcare"; "crisis pregnancy"; "conscientious objection"; "gestational limit"; "foetal pain"; "silent prayer"; "decriminalis*"
- **Notes:** Decriminalisation is now law (Crime and Policing Act 2026 s.241, in force at Royal Assent); the watch is implementation, the s.242 pardons scheme, and amendment vehicles on any Home Office or MoJ bill.

### 2. Assisted dying and end of life {#2_assisted_dying}

- **Tier 1:** "assisted dying"; "assisted suicide"; euthanasia; "Terminally Ill Adults"; "End of Life Bill"; "Suicide Act 1961"; "physician-assisted"; "assisted death"
- **Tier 2:** "palliative care"; hospice; "end of life care"; "terminal illness"; "mental capacity"; "right to die"; coercion; anorexia; "medical assistance in dying"; MAiD
- **Notes:** Palliative care and hospice funding items are the positive-agenda flank of this area and useful for coalition framing.

### 3. Gender medicine and children {#3_gender_medicine_children}

- **Tier 1:** "puberty blocker*"; "puberty-suppressing hormones"; "puberty suppressing hormones"; "cross-sex hormones"; "Cass Review"; Tavistock; GIDS; "gender identity service*"; "gender dysphoria"; "gender questioning children"; "youth gender"; PATHWAYS
- **Tier 2:** "detransition*"; "gender-affirming"; "Gillick competence"; "gender clinic*"; "private prescriptions"; "indefinite ban"; "social transition*"

### 4. Conversion practices {#4_conversion_practices}

- **Tier 1:** "conversion therapy"; "conversion practices"; "Conversion Practices Bill"
- **Tier 2:** "gender exploratory therapy"; "talking therap*"; "religious exemption"; "affirmation-only"
- **Notes:** Cross-tag with area 3 (a ban drafted to cover gender identity is the live risk to exploratory therapy) and area 8 (prayer and pastoral care exemptions).

### 5. Sex-based rights and single-sex spaces {#5_sex_based_rights}

- **Tier 1:** "single-sex space*"; "single-sex service*"; "single-sex ward*"; "Gender Recognition Act"; "gender recognition certificate"; "self-identification"; "self-ID"; "biological sex"; "legal definition of woman"; "For Women Scotland"; "women's sport"; "female category"
- **Tier 2:** "Equality Act 2010"; "Sullivan Review"; "sex and gender data"; "changing room*"; "toilet provision"; transgender; "protected characteristic"; "women's prison*"; EHRC; "gender reassignment"
- **Notes:** Equality Act mentions are extremely frequent; triage should score 2+ only where sex/gender definitions, single-sex exceptions or guidance revisions are at stake.

### 6. Parental rights and education {#6_parental_rights_education}

- **Tier 1:** "relationships and sex education"; RSE; "sex education guidance"; "parental consent"; "parental rights"; "right to withdraw"; "home education"; "elective home education"; "children not in school"; "education otherwise than at school"; EOTAS; "home schooling"; "homeschool*"
- **Tier 2:** PSHE; "curriculum review"; "external providers"; "smartphone* in schools"; "faith school*"; "collective worship"; "child protection"; "foster care"; "sex education"; "grooming gang*"
- **Notes:** EOTAS and the broadened tier 2 (child protection, foster care) are v0.2 pilot patches: government labels rarely match campaign vocabulary.

### 7. Free speech and online safety {#7_free_speech_online_safety}

- **Tier 1:** "Online Safety Act"; "age verification"; "age assurance"; "free speech"; "freedom of expression"; "non-crime hate incident*"; "silent prayer"; "Higher Education (Freedom of Speech)"; censorship; "anti-Muslim hostility"; "Islamophobia definition"; Islamophobia
- **Tier 2:** Ofcom; misinformation; disinformation; "harmful content"; "hate speech"; blasphemy; "client-side scanning"; encryption; "street preacher*"; "Islamis*"
- **Notes:** anti-Muslim hostility and the Islamophobia definition are v0.2 pilot patches. Powers granted for child protection can migrate toward viewpoint censorship; scope-expansion language scores 3.

### 8. Freedom of religion or belief {#8_freedom_of_religion}

- **Tier 1:** "freedom of religion or belief"; FoRB; "Christian persecution"; "persecution of Christians"; "religious persecution"; "Truro Review"; "Special Envoy for Freedom of Religion"; apostasy; "blasphemy law*"
- **Tier 2:** "religious minorit*"; "religious conversion"; "chaplain*"; "places of worship"; "religious freedom"; "religious liberty"
- **Notes:** Includes domestic manifestation cases (street preaching arrests, employment cases), which cross-tag with area 7.

### 9. Marriage and family {#9_marriage_family}

- **Tier 1:** "marriage law"; "weddings law"; "Tying the Knot"; "Law Commission"; "cohabitation reform"; "cohabitation rights"; "marriage allowance"; "family breakdown"; "no-fault divorce"
- **Tier 2:** "civil partnership*"; "family hub*"; fatherhood; "forced marriage"; "humanist marriage"; sharia
- **Notes:** Deliberately lean; childcare and general family-benefit items are excluded. Tying the Knot is a v0.2 pilot patch.

### 10. Surrogacy and embryology {#10_surrogacy_embryology}

- **Tier 1:** surrogacy; surrogate; "Surrogacy Arrangements Act"; "Human Fertilisation and Embryology"; HFEA; "commercial surrogacy"; "embryo research"; "14-day rule"; "gamete donation"; "egg donation"
- **Tier 2:** "fertility treatment"; IVF; "donor conception"; "donor-conceived"; "mitochondrial donation"; "genome editing"; "embryo screening"; "polygenic screening"; "artificial womb*"
- **Notes:** Ties to the Bought and Broken documentary workstream; any Law Commission surrogacy implementation signal is an automatic score 3.

## Global exclusions

Terms that alone generate noise and never match without a Tier 1 companion: termination (contracts, employment), conversion (loft, data, currency), transition (energy, EU, staffing), blocker (beta blockers, planning), and the bare words gender, safeguarding, education, equality.

- **Terms:** termination; conversion; transition; blocker; gender; safeguarding; education; equality

## Maintenance

- Reviewed monthly against a sample of discarded (score 0) items to catch false negatives; first review due early September 2026.
- Any [ACT]-worthy item that reached the team through another route but was missed by the filter triggers an immediate taxonomy patch here, then regeneration.
- New bills matching any Tier 1 term are auto-proposed for the watchlist; a human confirms.
- Version-control this file; the yaml is generated, never hand-edited.
