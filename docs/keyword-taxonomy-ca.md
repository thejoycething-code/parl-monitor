# Parliamentary Monitor: Catalan/Valencian keyword taxonomy

**Version 0.1 | 12 October 2026 | Owner: Christopher | Status: UNMEASURED DRAFT, CHRIS APPROVED 12 OCT 2026, NOT YET READ BY A NATIVE READER**

## Purpose

One Catalan/Valencian list for the regional parliaments of Spain that publish bill titles in Catalan or Valencian only: the Corts Valencianes now (`tools/es_regions.py`, source `vc`), and the Parlament de Catalunya and the Parlament de les Illes Balears if a list of theirs can be read later (`docs/spain-regions-scope.md`). The areas are identical to the English taxonomy and carry the same keys. Spanish titles keep the Spanish list (`config/taxonomy-es.yaml`); this file is for titles published in Catalan or Valencian alone.

**This file is the master.** `config/taxonomy-ca.yaml` is generated from it:
edit here, then run `python3 tools/generate_taxonomy.py --lang ca`. The suite
fails if the two drift (`tests/test_taxonomy_sync.py`).

## How it was made

Chris, 12 October 2026: "Add the Spain keyword terms", approving the Catalan/Valencian proposal of `docs/spain-regions-scope.md` (avortament, interrupció voluntària de l'embaràs, eutanàsia, mort digna, gestació subrogada, LGTBI*, identitat de gènere, família, escola concertada, llibertat religiosa, prostitució, discurs d'odi). To that proposal were added the natural Catalan forms of the most important Spanish terms per area, kept short and conservative: the forms a native speaker writes in a bill title, in both the Catalan and the Valencian standard where they differ ("ajuda per morir" and "ajuda per a morir").

**Unmeasured draft.** On 12 October 2026 the only stored Catalan or Valencian titles are the Corts Valencianes' first page (10 bills, none on our ground: land, forests, civil protection, budgets, tourism taxes, cultural heritage, a Down syndrome care unit), so no term here has a measured hit or a measured false positive yet. Every term is a phrase or a stem that does not occur in ordinary legislative Catalan outside its subject; the bare words that do (família, vida, gènere, sexe, llibertat, religió, educació, odi, església) are never terms on their own (Global exclusions). Accents fold for matching (X3), so "eutanàsia" and "eutanasia" are one term; apostrophes are folded to straight quotes before matching.

Calls made while drafting:

- Bare `família` is everywhere (every social-services, housing and tax bill), so it appears only in phrases ("suport a la família", "protecció de la família", "família nombrosa") and once GUARDED at tier 2 by family-policy company (natalitat, nombros*, monoparental*, conciliació).
- `"identitat de gènere"` mirrors the Spanish list: bare at tier 1 in area 5 (where the Spanish "identidad de género" sits), and guarded by minors company at tier 2 in area 3.
- `LGTBI*` and `LGBTI*` are the same all-caps stems as the Spanish list (case-sensitive): Catalan writes LGTBI, as the Cantabrian bill and Cataluña's Ley 13/2025 do in Spanish.
- `avortament*` rather than `avort*`: "avortar" also means to abort a plan or a launch, and the noun is the one a title uses for abortion.
- The middle dot of "pal·liatives" is matched as written (l·l); a title written "pal.liatives" would be missed, recorded here for the native reader.
- Migration (area 11) is collated, never campaigned, and hidden on every surface (repo-wide rule); its terms are here so the area is recorded, not shown.

## Issue areas

### 1. Abortion {#1_abortion}

- **Tier 1:** avortament*; "interrupció voluntària de l'embaràs"; "interrupció de l'embaràs"; "píndola abortiva"; "no nascut*"; nasciturus; "del concebut"; "dret a la vida" [with: concebut, néixer, embaràs, avortament, gestació, concepció]; "objecció de consciència" [with: avortament*, embaràs, sanitari*]
- **Tier 2:** "salut sexual i reproductiva"; "drets sexuals i reproductius"; anticoncepci*; anticonceptiu*; "píndola de l'endemà"; "anticoncepció d'emergència"; "dones embarassades" [with: suport, ajuda, vulnerab*]; "diagnòstic prenatal"; "dol gestacional"; "dol perinatal"; "mort perinatal"
- **Notes:** Catalan/Valencian v0.1 (Chris, 12 October 2026, unmeasured draft): avortament and interrupció voluntària de l'embaràs from the scope proposal; "del concebut" is the Catalan form of the Spanish "del concebido" added the same day for Madrid's Ley 5/2026 (BOE 29 August 2026). Bare "concebut" is not a term: like the Spanish "concebido", it also means "designed" ("concebut per a").

### 2. Assisted dying and end of life {#2_assisted_dying}

- **Tier 1:** eutanàsi*; "mort digna"; "suïcidi assistit"; "ajuda per morir"; "ajuda per a morir"; "prestació d'ajuda per morir"; "prestació d'ajuda per a morir"
- **Tier 2:** "cures pal·liatives"; "sedació pal·liativa"; "voluntats anticipades"; "document de voluntats anticipades"; "testament vital"
- **Notes:** Catalan/Valencian v0.1 (Chris, 12 October 2026, unmeasured draft): eutanàsia and mort digna from the scope proposal (the Catalan right-to-die campaign's own phrase); "prestació d'ajuda per (a) morir" is the Catalan name of the LORE's act in both standards.

### 3. Gender medicine and children {#3_gender_medicine_children}

- **Tier 1:** "bloquejador* de la pubertat"; "bloquejador* puberal*"; "disfòria de gènere"; "reassignació de sexe"; "menors trans"; "infància trans"; detransici*
- **Tier 2:** "identitat de gènere" [with: menor*, infant*, infància, adolescent*, escola*, xiquet*]; "tractament* hormonal*" [with: menor*, infant*, infància, adolescent*]
- **Notes:** Catalan/Valencian v0.1 (Chris, 12 October 2026, unmeasured draft): the Spanish list's area 3 core in Catalan; "xiquet*" is the Valencian word for children, "infant*" the Catalan.

### 4. Conversion practices {#4_conversion_practices}

- **Tier 1:** "teràpi* de conversió"; "teràpi* d'aversió"
- **Tier 2:** "acompanyament espiritual" [with: conversió, orientació, identitat]
- **Notes:** Catalan/Valencian v0.1 (Chris, 12 October 2026, unmeasured draft): the Catalan forms of the Spanish "terapias de conversión" and "de aversión".

### 5. Sex-based rights and single-sex spaces {#5_sex_based_rights}

- **Tier 1:** LGTBI*; LGBTI*; "identitat de gènere"; "autodeterminació de gènere"; "ideologia de gènere"; "llei trans"; "persones trans"; transsexual*; "no binàri*"
- **Tier 2:** "expressió de gènere"; "orientació sexual"; "perspectiva de gènere" [with: educació, escola*, menors, currículum, infància]; "violència de gènere"; "violència masclista"; "llenguatge inclusiu"
- **Notes:** Catalan/Valencian v0.1 (Chris, 12 October 2026, unmeasured draft): LGTBI* (shared with the Spanish list) and identitat de gènere from the scope proposal. Gender-violence terms at tier 2, as in the Spanish list (X11).

### 6. Parental rights and education {#6_parental_rights_education}

- **Tier 1:** "escola concertada"; "escoles concertades"; "educació concertada"; "pin parental"; "dret dels pares"; "drets dels pares"; "llibertat d'ensenyament"; "educació diferenciada"
- **Tier 2:** "educació sexual"; "educació afectivosexual"; "consentiment parental"; "pàtria potestat"; "xarxes socials" [with: menors, infants, xiquets, adolescents]
- **Notes:** Catalan/Valencian v0.1 (Chris, 12 October 2026, unmeasured draft): escola concertada from the scope proposal (state-funded independent schools, the live Valencian and Catalan fight over admissions and funding).

### 7. Free speech, privacy and civil liberties {#7_free_speech_online_safety}

- **Name:** Free speech, privacy and civil liberties
- **Tier 1:** "llibertat d'expressió"; "discurs d'odi"; "discursos d'odi"; "delicte* d'odi"; "incitació a l'odi"
- **Tier 2:** desinformaci*; "llibertat de premsa"; "llibertat d'informació"; "verificació d'edat"; pornografi*
- **Notes:** Catalan/Valencian v0.1 (Chris, 12 October 2026, unmeasured draft): discurs d'odi from the scope proposal; bare "odi" is never a term.

### 8. Freedom of religion or belief {#8_freedom_of_religion}

- **Tier 1:** "llibertat religiosa"; "llibertat de consciència"; "persecució dels cristians"; "persecució religiosa"; "Santa Seu"
- **Tier 2:** "Església catòlica"; "confessions religioses"; "llocs de culte"; "ensenyament de la religió"; "objecció de consciència"
- **Notes:** Catalan/Valencian v0.1 (Chris, 12 October 2026, unmeasured draft): llibertat religiosa from the scope proposal. Bare església is never a term.

### 9. Marriage and family {#9_marriage_family}

- **Tier 1:** "matrimoni entre persones del mateix sexe"; "matrimoni homosexual"; "protecció de la família"; "política familiar"; "família nombrosa"; "famílies nombroses"
- **Tier 2:** "suport a la família"; "suport a les famílies"; "mesures de suport a la família"; família [with: natalitat, nombros*, monoparental*, conciliació]; natalitat; "famílies monoparentals"; "custòdia compartida"; "permís de maternitat"; "permís de paternitat"; "permís per naixement"; "conciliació de la vida familiar"; adopció [with: menors, infants, xiquets, famíli*]
- **Notes:** Catalan/Valencian v0.1 (Chris, 12 October 2026, unmeasured draft): família from the scope proposal, as phrases and once guarded (bare família is in every social-services and housing title); "suport a la família" and "mesures de suport a la família" are the Catalan forms of the Spanish "apoyo a la familia" terms added the same day for Madrid's Ley 5/2026 (BOE 29 August 2026).

### 10. Surrogacy and embryology {#10_surrogacy_embryology}

- **Tier 1:** "gestació subrogada"; "gestació per substitució"; "maternitat subrogada"; "ventre* de lloguer"
- **Tier 2:** "reproducció assistida"; "reproducció humana assistida"; embrió*; "fecundació in vitro"
- **Notes:** Catalan/Valencian v0.1 (Chris, 12 October 2026, unmeasured draft): gestació subrogada from the scope proposal.

### 11. Migration {#11_migration}

- **Tier 1:** immigració; immigrant*
- **Tier 2:** migrant*; migratori*; "persones migrades"
- **Notes:** Catalan/Valencian v0.1 (Chris, 12 October 2026, unmeasured draft): collated, never campaigned, hidden on every surface, as in the Spanish list for Spain.

### 12. Prostitution, trafficking and sexual exploitation {#12_prostitution}

- **Name:** Prostitution, trafficking and sexual exploitation
- **Tier 1:** prostitució; proxenetisme; proxeneta*; "tracta d'éssers humans"
- **Tier 2:** "tracta de persones"; "explotació sexual"; "treball sexual"; "treballadores sexuals"
- **Notes:** Catalan/Valencian v0.1 (Chris, 12 October 2026, unmeasured draft): prostitució from the scope proposal; bare "tracta" is never a term.

### 13. Organ donation and transplant ethics {#13_organ_donation}

- **Name:** Organ donation and transplant ethics
- **Tier 1:** "donació d'òrgans"; "trasplantament* d'òrgans"; "tràfic d'òrgans"
- **Tier 2:** "donant* d'òrgans"; "mort encefàlica"
- **Notes:** Catalan/Valencian v0.1 (Chris, 12 October 2026, unmeasured draft): the Catalan forms of the Spanish list's core.

## Global exclusions

The bare words that must never be promoted to a term on their own (advisory prose, not a filter input).

- **Terms:** família; vida; gènere; sexe; menors; matrimoni; llibertat; religió; educació; odi; dona; igualtat; trans; tracta; església; concebut

## Maintenance

Corrections from a native reader come in here, then `python3 tools/generate_taxonomy.py --lang ca`. A new term needs a measurement, written in the area's Notes; the first measured round replaces "unmeasured draft" in the header.
