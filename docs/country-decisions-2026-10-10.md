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
| X16 | AI judge: deferred (stays off) |
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
- Peru: use the encrypted expediente endpoint (PE2); regional councils later (PE4).
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

## Not acted on

- U1 (Uruguay Ley 20.431 referendum): ignore.
- S1, S2 (Congreso Visible debug mode, DR Senate credentials): leave.
