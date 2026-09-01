# EU Monitor — spec and build state

Christopher, 2026-09-01: "like the Westminster one but catching all items of
concern the EU are promoting." This document records what was live-probed,
what is built, and the decisions that are his before it goes further.

## Sources, live-probed 2026-09-01 (raw responses in data/raw/eu-probe-2026-09-01/)

| Source | Endpoint | Probe result | Verdict |
|---|---|---|---|
| Commission "Have your say" | `ec.europa.eu/.../brpapi/searchInitiatives` | 200; 4,101 initiatives; `feedbackStatus=OPEN` filters server-side to 41; `text=` search works; per-item feedback window with start/end dates | **Phase 1, BUILT** |
| HYS initiative detail | `brpapi/groupInitiatives/{id}` | 200; EN `dossierSummary`, DG, committee, publications | **Phase 1, BUILT** (one fetch per new item) |
| HYS public page | `have-your-say/initiatives/{id}` | 200 direct | the citizen-facing URL every row carries |
| EP Open Data: adopted texts | `data.europarl.europa.eu/api/v2/adopted-texts` | 200; JSON-LD; multilingual titles, subjects, dates | Phase 2 |
| EP Open Data: meetings | `/api/v2/meetings` | 200; plenary calendar | Phase 2 (the "coming up" strip) |
| EP Open Data: parliamentary questions | `/api/v2/parliamentary-questions` | 200 but id-only stubs; one fetch PER question for content | Phase 2/3, expensive |
| OEIL (Legislative Observatory) RSS | `oeil.secure.europarl.europa.eu/.../rss` | 307 redirect, not yet chased | Phase 2 (dossier tracking = bills-board analog) |

## Why "Have your say" is phase 1

Everything the EU is *promoting* passes through the Better Regulation
portal: legislative proposals, delegated/implementing acts, evaluations and
fitness checks all take public feedback in defined windows. It is the one
EU source where the action-window rule (docs/parl-monitor-devolved-fix.md)
transfers unchanged — open window, stated closing date, open to anyone.
It is also the *actionable* end: a feedback window is something supporters
can be pointed at, where an EP resolution is already history.

## Built (phase 1)

- `eu_consultations` table (src/db.py), mirroring `dg_consultations` plus
  `reference`, `act_type`, `topics`, `stage`.
- `tools/eu_monitor.py`: one listing call weekly (41 items today), one
  detail call per NEW initiative for the EN summary, same taxonomy pass as
  the devolved monitors over title + summary, ON-OUR-GROUND / WATCHING
  render with nothing silently suppressed.
- Separation guarantee held: the tool writes `eu_consultations` only —
  never `items`/`mp_events` — so nothing reaches the Westminster digest
  until wired deliberately.
- 7 tests on fixtures cut from the real probe responses.
- First live pull (2026-09-01): 41 open, 0 matched the taxonomy — a real
  zero (the week's crop is vineyards, batteries, Chips Act; the test
  fixture proves a VAW/abortion text matches). The EU Strategy on victims'
  rights (closes 4 Sep) and Quality Education for All 2040 (closes 8 Sep)
  are the nearest misses, visible in WATCHING.

**NOT yet wired into CI** — no sunday-pull step, no digest section, no
Top lines, no briefs. The local pull was validation; canonical population
happens when the wiring is approved.

## Decisions that are Christopher's (checkpoint 1)

1. **Taxonomy vocabulary.** The UK taxonomy misses EU-flavoured terms:
   SRHR, gender mainstreaming, Istanbul Convention, conversion practices,
   CSAM regulation / chat control, DSA enforcement, surrogacy/ART,
   rule-of-law conditionality. An EU term extension needs his sign-off the
   way taxonomy v0.3 did — and it decides whether weeks like this one stay
   at zero.
2. **Wiring.** Add to sunday-pull + a "European Union" section in the
   weekly edition (devolved-style: Briefed/Watching, action-window rule)?
   Or a separate EU edition?
3. **Actionability downstream.** Does an EU consultation on our ground
   reach Top lines and generate a Campaigns Brief? If so: which CitizenGO
   list (EN? per-country?), who is the 5CA equivalent (none exists — MEP
   voting records could build one later from EP roll-call data), and does
   the Asana approval + PPAE loop apply as-is?
4. **Cadence.** Weekly matches windows (~4 weeks typical). Daily would only
   matter for late-detection on short windows.

## Phase 2 candidates (in rough order of value)

1. **OEIL dossier tracking** — the bills-board analog: watched procedures
   (e.g. anything touching abortion, gender, family law, freedom of
   expression) with stage movement per week.
2. **EP plenary calendar + committee agendas** (LIBE, FEMM, JURI, EMPL) —
   the Order-Paper/coming-up analog, and the 1–2-month forward look
   Caroline asked for lands naturally here.
3. **EP adopted texts** — what the Parliament just resolved, taxonomy-
   matched; resolutions are non-binding but set the promotion agenda.
4. **MEP roll-call votes** — the vote-tracker analog, eventually a 5CA for
   the Parliament.

## Costs

All sources are public JSON, no keys, no LLM spend in phase 1. The weekly
pull is ~1 + new-items requests. Taxonomy triage stays deterministic; LLM
triage would only enter if Christopher wants EU items scored like
Westminster ones.
