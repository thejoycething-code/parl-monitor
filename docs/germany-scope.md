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

## The IP block of 24 September 2026, and the rule it bought

bundestag.de began resetting our connections **during the TLS handshake** --
CONNECTED, then errno 54, no peer certificate. DNS resolved and port 443 was
open, so it was not an outage, not routing, not the API key and not the
User-Agent: the server never got far enough to see a request. An edge block
on this machine's IP.

It followed roughly 2,000 requests to that host in one day, and one of them
was not like the others: a committee-report backfill with
`--since 2025-06-01` that pulled **1,816 documents in a single pass**. The
weekly's own window is 60 days and its recurring load is a fraction of that.

**THE RULE: backfills run from CI, paced, and are announced.** A one-off
historical sweep is the heaviest thing this project does to any source, it is
always a deliberate act rather than a scheduled one, and running it from a
laptop puts a single IP behind every request. The weekly windows are chosen
to be light; the backfills are what will get us blocked.

Five German collectors depend on that host -- de_documents, de_speeches,
de_amendments, de_committees and de_agenda. The Sunday run uses GitHub's IPs
and is probably unaffected, but that is a hope rather than a verification
while the block stands.

**The block lifted overnight on 25 September**, without a word from anyone:
both hosts answered normally again the next morning. Nothing about the rule
above changes -- an edge block that lifts by itself can return by itself, and
it left the debate packs unbuildable for a day.

## Debate packs (25 September 2026)

`tools/de_debate_pack.py` builds the German equivalent of the Westminster
pack: round-up, onside checklist, quotes and shot list for one agenda item.
The differences from Westminster are all forced by the sources, and each was
measured on sitting 96:

- **The Stenografischer Bericht carries no per-speech timecodes.** Protocol
  21/96 has four "Uhr" mentions in 858,106 characters and three are about
  voting urns, so Hansard's trick of reading a clock off each contribution
  does not exist here. Interpolating from `Beginn: 09:00 Uhr` across a
  sitting that ended at 02:15 would drift by hours.
- **The Mediathek is better than interpolation, and better than Hansard.** It
  publishes ONE VIDEO PER SPEECH with the speaker, their party and the
  wall-clock second they rose. Sitting 96 has 309 of them. So the clock times
  in a German pack are the Bundestag's own, and there is nothing to
  interpolate.
- **The speaker list therefore comes from the Mediathek, not the text.** The
  protocol DIP serves on the day is a *Vorabfassung*: sitting 96's ran TOP 7,
  8, 9, 10, 12 -- item 11 was not in it at all, while the Mediathek had the
  whole debate on video. The recording is complete on the day and the
  transcript is not, so the recording decides who spoke and the pack reports
  how many of them the protocol carries the words of.
- **Footage is LINKED, never downloaded.** The Westminster pack downloads
  under the Parliamentary Recording Unit's terms. The Bundestag's terms are
  its own and nobody here has read them, so this pack links to their player
  and stops. That is a decision for whoever reads the licence, and it belongs
  with the open question above.

Building it turned up a recall bug in the SPEECHES COLLECTOR, not just the
packs: `Michael Brand (Fulda) (CDU/CSU):` -- a constituency printed to tell
two members of the same name apart -- and `Karl-Josef Laumann, Minister
(Nordrhein-\nWestfalen):`, a Land minister speaking for the Bundesrat with
the Land name hyphenated across a line break. Neither matched, so the
speeches were dropped silently: five headings in protocol 21/96, one of them
the lead signatory of the motion being debated. Fixed in `src/de_protocol.py`,
which is where the parser now lives so the packs and the collector share one
copy. **Protocols read before 25 September were parsed without the fix**, so
past speeches by members whose heading takes either form are still missing
from the store.

## If DIP is ever refused us (surveyed 26 September 2026)

We are NOT blocked today: `src/dip.py` reads the key the Bundestag
publishes as an example in its own spec, and that works. The survey below
is a fallback, and the answer is that one exists but is worse.

**Only DIP needs a key at all.** Everything else the German monitor reads is
keyless already: abgeordnetenwatch (votes, members, profiles), dserver
(Drucksachen), `www.bundestag.de` (the Tagesordnung and the Mediathek) and
epetitionen. What DIP carries is two layers: **Vorgänge**, and the
**plenary protocol text**.

**Protocols have a keyless route, in PDF only.** The list endpoint answers
plain curl with no key --
`www.bundestag.de/ajax/filterlist/de/dokumente/protokolle/plenarprotokolle/442112-442112`
-- and reports 4,656 protocols with a predictable URL per sitting:
`dserver.bundestag.de/btp/<wp>/<wp><nnn>.pdf` (21/96 is `21096.pdf`, 1.7 MB,
verified). **No XML is offered on that route**, despite the Bundestag
publishing a DTD for plenary protocols on its open-data page;
`btp/21/21096.xml` is a 404. So the fallback reverses the property this
scope doc opens by celebrating -- that Germany needs no PDF parsing at all
because DIP returns text. `pypdf` is already installed by the weekly, so it
is buildable; it is just a step down, and it should be built only if DIP
actually refuses us.

**BUILT, 26 September.** `src/de_btp.py` plus `tools/de_speeches.py
--source pdf`. Measured on protocol 21/96 against the same protocol's DIP
text: 474 speeches parsed from each, 137 distinct speakers from each of
which 136 are shared, and 464 of 474 speech bodies found VERBATIM in the
PDF text. The parser needed no change. Two things do not survive
extraction and both nearly sank it:

- **Order.** The front matter interleaves differently, so the two texts are
  not the same sequence. Anything comparing them must normalise first.
- **Hyphenation.** The Bericht is justified and breaks words freely --
  3,467 hyphen-newline splits in 21/96, where DIP's text has none. Left
  alone, `Bundesregie-\nrung` is not `Bundesregierung` and the term list
  silently under-matches: the first live run found 11 speeches on our
  ground where DIP found 14, and 13 after `dehyphenate()`. A word is
  rejoined only when the next line starts lower case, so a real compound
  keeps its hyphen.

Comparing raw prefixes, before normalising, suggested 33 of 474 bodies
matched. That number was an artefact of line breaking and is the reason to
normalise before judging any two renderings of the same document.

**Vorgänge have no keyless equivalent.** The only other route to them is
scraping DIP's own web interface, which is the same service without the
API. That is a bigger terms-of-use exposure than using the published
example key, not a smaller one.

**MdB-Stammdaten: TAKEN, 26 September.** `tools/de_stammdaten.py` ->
`de_mdb` and `de_mdb_terms`. 4,614 members, 13,046 terms, Wahlperioden 1 to
21, keyless. Deeper history than abgeordnetenwatch, and the right source
when a German 5CA needs a member who left before the current Wahlperiode.

It also answers the parser question from the day before. **532 members
carry an ORTSZUSATZ** -- the constituency the Bericht prints to tell two
members apart -- and in the current Wahlperiode alone **26 surnames are
held by more than one sitting member**, Schmidt by eight of them and Müller
by six. That is why "Michael Brand (Fulda)" is written that way, and this
is the authoritative list of who is written that way.

Two traps in the file. A member can have SEVERAL names, recorded with
HISTORIE_VON/BIS -- 434 name elements across 400 members in the sample --
so the current one is the one with no HISTORIE_BIS, and taking the first
would give some members the name they were elected under decades ago. And
ORTSZUSATZ arrives as `(Fulda)`, brackets included, which are stripped so
the value compares with what a parser pulled out of a heading.

**RELIGION is in the file and is not stored.** It is special category data,
holding it is not necessary for anything this monitor does, and a public
register being the source does not make it ours to keep. The omission is
named in `src/db.py` and in the tool, so it reads as a decision rather than
an oversight.

## Still open

- **Who reads the terms of use** at `dip.bundestag.de/über-dip/nutzungsbedingungen`
  before the German weekly starts running unattended.
- **When the German team verifies the taxonomy.** Until they do, every German
  surface carries the draft warning on its face.
