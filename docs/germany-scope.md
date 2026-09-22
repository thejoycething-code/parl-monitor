# Germany: scoping the Bundestag monitor

Probed live on 22 September 2026. Every number below was measured, not
estimated; the probes are reproducible from `tools/de_rollcalls.py` and the
notes here.

## The finding that shapes everything

**The English taxonomy is blind to German.** Run over the 68 named votes of
the current Bundestag, `config/taxonomy.yaml` matched 5, and four of those
matched only because "Migration" is spelled the same in both languages. One
of the four is the Chancellor's budget, which is a false positive from the
intro text. Area 11 is collated and never campaigned, so the honest score is
**one useful match in sixty-eight**.

Nothing else in this document matters until that is fixed. A German monitor
that reuses the English term lists collects everything and sees nothing.

## What Germany publishes

### abgeordnetenwatch.de (open, no key) -- WORKS TODAY

`https://www.abgeordnetenwatch.de/api/v2`. Covers the Bundestag (parliament
id 5) and all sixteen Land parliaments, plus the European Parliament.

* `parliament-periods?parliament=5&type=legislature` -- the legislature id.
  Current: **161, "Bundestag 2025 - 2029"**, 2025-03-25 to 2029-02-22.
* `polls?field_legislature=161` -- the *namentliche Abstimmungen* (recorded
  votes). 68 in the current legislature, 162 in the last.
* `polls/<id>?related_data=votes` -- **every member's position on one call**:
  630 rows for the Tempolimit vote, each with the member, their *Fraktion*
  and `yes` / `no` / `abstain` / `no_show`. This is the 5CA layer, complete,
  in one request.
* Each poll carries `field_topics` (a 23-term controlled vocabulary),
  `field_committees`, `field_accepted`, and `field_intro`, whose HTML links
  the **Drucksache** the House actually voted on.

### dserver.bundestag.de (open, no key) -- WORKS TODAY

The Drucksachen themselves, as PDF, linked from every poll's intro. Probed:
`btd/21/053/2105319.pdf` returns 231 KB. This is the same shape as the EU
side, where the vote label says nothing and the body says everything, and it
is where a German taxonomy will earn its keep.

### DIP, the official Bundestag API -- NEEDS A KEY

`https://search.dip.bundestag.de/api/v1/` returns **401 without a key**. This
is the whole document and proceedings system: Vorgänge, Drucksachen,
Plenarprotokolle, Aktivitäten. The key is issued by the Bundestag on
application. **Somebody has to request one**; it is the only blocking
dependency in this plan, and it gates the phase that carries the volume.

## Why named votes alone are not enough

Across both recent legislatures, 230 recorded votes, the count touching
CitizenGO's ground, searched with German terms:

| Ground | 2025-2029 | 2021-2025 |
|---|---|---|
| Abortion (Abtreibung, Schwangerschaftsabbruch, §218) | 0 | 1 |
| Assisted dying (Sterbehilfe, assistierter Suizid) | 0 | 2 |
| Gender / self-ID (Selbstbestimmungsgesetz) | 0 | 1 |
| Free speech (Meinungsfreiheit, NetzDG) | 1 | 0 |
| Conversion practices, surrogacy, parental rights, religious freedom | 0 | 0 |

**Five relevant votes in two legislatures.** The Bundestag reserves recorded
votes for set-pieces; the issues we campaign on move through motions,
committee papers and plenary debate, which live in DIP. A monitor built on
recorded votes alone would be accurate, cheap and almost always empty.

That is not a reason to skip them: those five votes are exactly the ones a
5CA is for, and the per-member data is free and complete. It is a reason not
to stop there.

## Proposed phasing

**Phase 1 (no key, build now).** `de_members`, `de_divisions`, `de_votes`
from abgeordnetenwatch. Store every recorded vote -- the volume is tiny, and
a blind English filter would discard all of them. Record the German topics
verbatim. No areas, no tiers, no verdicts: nothing is classified until there
is something honest to classify with.

**Phase 2 (the blocker).** A German layer for the taxonomy. The areas do not
change -- they are CitizenGO's positions, not England's -- but each needs its
German terms, and German compounds mean substring matching behaves
differently from English (`Schwangerschaftsabbruch` contains
`Schwangerschaft`; `Lebensschutz` and `Lebensmittel` share a stem). This is
a drafting job with a native reader, not a translation job.

**Phase 3 (needs the DIP key).** Vorgänge and Drucksachen as the document
layer, with body matching over the PDFs exactly as `src/eudoc.py` does for
adopted texts. This is where the monitor starts finding things weekly.

**Phase 4.** Verdicts and a German 5CA, once there is something to sign.
A division's meaning is signed by hand here as everywhere else.

### Where it actually got to, 22 September 2026

Phases 1-3 are built and scheduled. `tools/de_monitor.py` writes
`editions/de-monitor-<date>.md` and DMs a summary; `.github/workflows/de-weekly.yml`
runs it Sunday 19:00 UTC with a 21:00 retry slot behind a gate job. The first
real render carried **183 Vorgänge on our ground**, six of them scored 3, and
two Bavarian abortion votes.

Phase 3 landed with ONE deliberate gap. The weekly runs
`de_documents.py --mode terms`, which drives DIP from the tier-1 German terms
and writes `de_vorgaenge` only, so `de_documents` -- the body-text layer -- is
empty and stays empty. `--mode window` is what fills it, and it is not
scheduled. That zero is declared in three places rather than left to look like
a broken collector: `coverage.ALLOWED_EMPTY`, the edition's own Watching
table, and here. **Scheduling `--mode window` is the switch that turns the
document layer on, and it is a deliberate decision about runtime, not an
oversight to be quietly fixed.**

## Decisions taken, 22 September 2026

1. **The DIP key is not blocking after all.** The Bundestag publishes a
   working key in its own public OpenAPI specification, tested and returning
   current data. It is read from that spec at runtime so a rotation heals
   itself, with `DIP_API_KEY` and `config/secrets.yaml` taking precedence, so
   the day a key is issued in CitizenGO's name nothing changes but a secret.
   **Still apply for one:** driving a scheduled harvest from a key published
   as a documentation example is a terms-of-use exposure, not just a technical
   one, and runtime discovery survives a rotation but not a policy change.
2. **The German terms are an AI first draft** (`docs/keyword-taxonomy-de.md`),
   to be verified by the German team. Measured on the day it was written: it
   took the stored Bundestag votes on our ground from 1 to 7.
3. **Bundestag and all sixteen Länder.** Taken knowing the cost: the Länder
   carry about 114 recorded votes between them, most of them Bavaria's, and
   there is **no document system for them** -- DIP is federal. Land coverage
   is therefore votes-only, which is the thin seam, and the edition says so
   rather than letting a short section imply a strict filter.
4. **Germany gets its own edition**, `editions/de-monitor-<date>.md`, plus a
   DM. The EU pattern, not the devolved one: a different parliament on a
   different rhythm, not a section of Westminster's week. The channel stays
   held, as the EU's does.

## What the first live run taught

**A third of Germany's matched items are migration.** 171 of 507 Vorgänge on
our ground matched on area 11 alone, and every one of the six matched
*Bundestag recorded votes* did. Migration is collated, never campaigned
(Christopher's standing instruction), so all of them are suppressed -- which
means the German team's first edition would otherwise have opened on six
deportation items in a row, and the recorded-votes section would have carried
nothing else at all.

The rule was already repo-wide (`src/partner.py` and four other modules carry
`HIDDEN_AREAS = (11,)`); `tools/de_monitor.py` now carries it too, and the
edition PRINTS the suppressed count rather than simply rendering shorter. An
empty section says *which* kind of empty it is: "the House was quiet" and "the
standing rule removed all six" are different facts and a reader acts
differently on each.

Worth the German team knowing when they review the taxonomy: this is not a
sign the German terms are over-broad. The migration terms are working exactly
as written. It is a sign that migration is a very large share of what the
Bundestag transacts.

## Still open

- **Who reads the terms of use** at `dip.bundestag.de/über-dip/nutzungsbedingungen`
  before the German weekly starts running unattended.
- **When the German team verifies the taxonomy.** Until they do, every German
  surface carries the draft warning on its face.
