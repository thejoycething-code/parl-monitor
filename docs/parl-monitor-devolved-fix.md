# parl-monitor change spec: surface actionable devolved items

**Written 2026-08-31. Prompted by the NI RE Core Syllabus consultation (closes
2026-09-30) appearing in Edition 5 with no Campaigns Brief generated.**

## The bug

It is not a scoring miss and not a failed run. It is a design assumption.

The Devolved section of the edition carries its own rule in its subheading:

> *Scotland, Wales and Northern Ireland. Watching brief: recorded because it bears on
> our issues, not because it asks anything of us.*

Jurisdiction is currently being used as a proxy for actionability. Anything routed to
Devolved is classified as non-actionable by construction, so it never reaches the brief
generator regardless of taxonomy score, deadline proximity, or whether we have prior
campaign history on the issue.

That the generator itself is healthy is demonstrable: the SEND reform brief
auto-generated on 24 August from a Westminster consultation with the same shape
(government consultation, dated deadline, education/parental-rights taxonomy hit).
Same object type, different jurisdiction, opposite outcome.

## Why it matters beyond this one item

Edition 5's Devolved table currently holds four open consultations. All four are
invisible to briefing:

| Consultation | Nation | Closes |
|---|---|---|
| Protections in the justice system for women and girls | Scotland | 2026-08-31 |
| A New Good Relations Framework, Call For Views | N. Ireland | 2026-09-21 |
| Consultation on the Religious Education Core Syllabus | N. Ireland | 2026-09-30 |
| Measures to Support Mobile Phone-Free Schools in NI | N. Ireland | 2026-11-19 |

The Scottish one closes today, having been surfaced only through a manual pull on
24 August. The RE syllabus one is the deliverable on a written ministerial commitment
that CitizenGO won with 96,328 signatures.

## The fix

**Replace the jurisdiction test with an action-window test.** Actionability is a
property of the item, not of the parliament it came from.

### Rule

An item is `actionable` when **all** of the following hold, whatever its jurisdiction:

1. It has an **open response window** with a stated closing date in the future. This
   covers consultations, calls for evidence, calls for views, and committee inquiries
   accepting written submissions. It excludes items that only *report* something:
   questions answered, votes recorded, bills already passed, stages already taken.
2. It **scores on the issue taxonomy** at the threshold already used for Westminster
   items. No separate or lowered threshold.
3. A response is **open to us or to our supporters**, rather than restricted to a
   closed list of invited parties.

Everything failing (1) stays exactly where it is today: Devolved watching brief,
recorded, not briefed. The Holyrood and Senedd bill tracking, the committee scrutiny
record and the questions/votes stores are all unaffected. This change touches
consultations and calls for evidence only.

### Consequences of the rule

- `actionable` items generate a Campaigns Brief draft and an Asana review task in
  project `1211423235936092`, identically to Westminster items today. Same approval
  buttons, same Drive upload, same naming.
- `actionable` items appear in the **Top lines** of the Slack post, not only in the
  canvas. The current failure is partly a visibility one: the RE consultation *was* in
  Edition 5's canvas, but only in a table below the fold in a section whose own
  subheading tells the reader it asks nothing of them.
- The Devolved section subheading must stop asserting non-actionability as a blanket.
  Suggested replacement:

  > *Scotland, Wales and Northern Ireland. Items with an open response window are
  > briefed and appear in Top lines; the remainder are a watching brief, recorded
  > because they bear on our issues.*

### Deadline-proximity guard

Apply the same urgency banding used for Westminster consultations, and additionally
flag any actionable item first detected with **fewer than 21 days** to its deadline as
`late-detection`. The RE consultation opened on 24 June and reached a generated
edition on 31 August, 30 days before closing. The Scottish justice consultation
reached one with 0 days. A late-detection counter in the edition footer makes that
failure mode visible instead of silent.

## Acceptance tests

Run against the current stores; no new data needed.

1. **RE Core Syllabus (NI, closes 2026-09-30)** produces a brief draft and an Asana
   review task, and appears in Top lines. *This is the regression test for the bug.*
2. **Good Relations Framework (NI, closes 2026-09-21)** produces a brief draft.
   Confirms the rule is not special-cased to education.
3. **Mobile Phone-Free Schools (NI, closes 2026-11-19)** produces a brief draft and is
   banded as non-urgent on deadline distance, not suppressed by jurisdiction.
4. **Protections in the justice system for women and girls (Scotland, closed
   2026-08-31)** produces no new brief once past its deadline, and is marked
   `late-detection` in the historical record.
5. **Children (Withdrawal from RE) (Scotland) Bill, Stage 3 taken 2026-02-17**
   produces **no** brief and remains in the watching brief. Confirms passed
   legislation is still correctly excluded by test (1).
6. **Senedd written questions** produce no briefs. Confirms reporting-only items are
   still excluded.
7. **SEND reform (Westminster)** still produces exactly one brief. Confirms no
   Westminster regression or duplication.

## Not in scope

- Do not lower the taxonomy threshold. The taxonomy is working: v1.1 added religious
  education at tier 1 and immediately surfaced this consultation. The routing was the
  failure, not the scoring.
- Do not auto-post the devolved watching brief in full to Slack. The manual-pull
  design for the wider devolved stores is deliberate and should stay. Only actionable
  items are being promoted.
- Do not change the approve/reject/request-changes flow.

## One open question for the Minister-facing side

The brief generator populates the 5CA from Westminster division lists. For devolved
items there is no equivalent source wired in, so the 5CA came out unpopulated in the
manual NI brief and had to be marked for the campaigner. Either wire in the
Assembly/Holyrood/Senedd membership sources, or have the generator emit an explicit
`5CA not available for devolved items - populate manually` marker rather than an empty
grid that looks like an oversight.
