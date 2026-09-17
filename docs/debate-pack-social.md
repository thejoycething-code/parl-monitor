# The social cut and the article: defaults for a debate

Set on the surrogacy debate (Westminster Hall, 7 September 2026) and adopted as the
defaults on 8 September. Anything here can be overridden per pack, but the tool and
the writer start from these.

## Order of work (rewritten 12 September 2026 after the Second Reading run)

The order matters: footage cut before the selector had chosen was cut twice on
11 September, and two sessions on one pack cost three hours. One pack, one
process (`.lock` in the pack folder; `PARL_FORCE_LOCK=1` only for a dead holder).

1. **During the debate** — `tools/live_debate.py --date D --find TERM --area N --dm`
   at lunchtime and again before the division: builds the pack from what Hansard
   has published so far (the stance read is cached per speaker) and DMs the
   WOBBLE / SLIP list — members whose words today contradict their last vote on
   the area. Goldman's 09:56 intervention would have been on the phone by 10:30.
2. **Pack** — `tools/debate_pack.py --date D --find TERM` once Hansard is complete
   (`pack.json` carries the day's divisions with the question put before each).
3. **Checklist from the vote** — when the debate ended in a division,
   `tools/debate_pack.py --pack F --apply --from-vote <division id>` fills ONSIDE
   from the lobbies (our side from `vote_tracker.yaml`, or `--our-side`). Members
   in both lobbies are left for a person. Fill by hand only when there was no vote.
4. **Selector** — `tools/pick_speeches.py --pack F --top 8 --write-sequence`:
   ranks every confirmed-onside speech for campaign value in batches of eight,
   verifies each passage verbatim, writes `selection.md` and the `sequence.md`
   the cutters read. The previous sequence is kept.
5. **Footage** — `tools/social_cut.py --pack F` (the reel, same evening), then
   `tools/speech_cut.py --pack F` (the full speeches, next morning is fine). Both
   begin with the clock self-check: the opener and the closer are probed and the
   offsets written to `pack.json`; a run stops if the two anchors drift apart by
   more than 20 seconds or either sits more than 45 seconds from Hansard's clock
   (Hansard's own times are ±30 s; on 11 Sept the opener read +27.7 s, the closer
   +10.5 s, and the windows absorb that). A speech interrupted by interventions is one clip.
6. **Report** — `tools/debate_report.py --pack F` (the vote is in, so no
   `--provisional`), then `--preview` to see the canvas alone.
7. **Publish** — `tools/debate_report.py --pack F --publish --with-clips`: puts the
   reel, clips, subtitles and logs on Drive ("Debate footage / <date> <title>" in the
   Automated Briefs shared drive) and posts the canvas to #campaigns-en-gb with the
   Drive link and a Best speeches section. Slack carries the link, never the bytes.
8. **Afterwards** — add the division to `config/vote_tracker.yaml` and sign it off;
   Monday's run ledgers the voters, writes the tracker's stance for both lobbies
   (`tracker:signed`, which outranks the model), records who was present but did
   not vote, and refreshes the 5CA.

## The standing evening task (12 September 2026; flagged days only from 14 September)

The scheduled task `tia-second-reading-debate-pack` (renamed "Debate day") fires
every weekday at 18:30 London and begins by reading `config/debate_watch.yaml`:
the days a person has flagged for a pack, each with the House, a phrase the
Hansard title contains, the 5CA area and a note. No watch today, and the task
ends at once: no Hansard, no store, no cost. (Christopher, 14 Sept: "I'm not sure
we need the daily pulls unless we flag something coming up in the week we want
a pack on.") On a flagged day it runs `tools/debate_today.py` to confirm Hansard
has the debate (the KEY DEBATE line also carries the areas earned and the clock
of the last contribution published, so a Bill day still being published is
visible), then the order of work above through the footage, with the report's
approval DM and a closing DM. It never publishes and never touches Drive.

Flagging: `python3 tools/debate_watch.py suggest` reads the week-ahead and prints
the debates on our ground as ready-made `add` commands; `add <date> "<phrase>"
--house --area --note` flags one; `list`, `today`, `remove`. Monday's edition is
the natural moment to flag the week.

Since 17 September 2026 the flag also arrives without a person, three ways, and
the note on each watch says which (`source: hand | auto | bill | same-day`):

1. **Monday's run** calls `suggest --write`: every week-ahead item on our ground
   whose category is debate-shaped (`AUTO_CATEGORIES` in `src/debatewatch.py`:
   debates, legislation, Westminster Hall, PMBs, motions, Lords short debates
   and SIs, committee oral evidence) is flagged; oral questions, statements and
   urgent questions are printed for the eye but not flagged, because an evening
   run on a statement only DMs "looks small". A bill committee's sitting has an
   empty description in the week-ahead and the bill's name on the committee;
   `suggest` reads it from there. The workflow commits `config/debate_watch.yaml`
   and the evening task pulls before it reads.
2. **A bill's stage sittings**: `add-bill <bills-api id> --area N --note "..."`
   writes one watch per future sitting from the Bills API, in the right House,
   and committee sittings carry `min_speakers: 8` (a committee seats about
   seventeen; 12 and 13 spoke at the Immigration and Asylum Bill's evidence
   sittings). The evening task reads "| min N" on the WATCH line in place of its
   fifteen-speaker floor. `refresh` re-expands every flagged bill and runs
   inside Monday's `suggest --write`, so a sitting booked later still gets its
   watch. The Bills API listed the Immigration and Asylum Bill's committee to
   3 November when the week-ahead showed it only to 15 October.
3. **The same-day net**, the scheduled task `debate-day-net` at 16:45 on weekdays:
   `net` runs `debate_today`'s title gate over both Houses and flags any debate
   Hansard already shows with eight or more speakers that no watch covers, so
   an urgent question that grew or a statement that became a debate is packed
   at 18:30. It costs one Hansard sections read a day plus one fetch per
   candidate; it commits the watch file and DMs one line only when it flags.

A hand `add` outranks all three: an automatic pass never rewrites a hand
watch's note or area, and a hand `add` over an automatic watch does.

The lunchtime wobble read is a hand step on a flagged day: `python3
tools/live_debate.py --date D --find "<phrase>" --house H --area A --dm` at
13:30 or so, when Hansard has the morning. (A 13:30 task existed for a day, 13
September; it was removed with the move to flagged days. Recreate it from the
evening task's prompt if a week has several flagged days.)

Trim fallbacks (13 September): when Hansard's first 25 words were not spoken
(`late_head`) or its last 25 were tidied in (`late_tail`), the anchor slides
through the text until a block is heard and the cut stops at the pause where the
Speaker called the next member. The report line says "start from Hansard word N"
or "end at Hansard word -N" when either fired.

## Re-cutting one speaker (12 September 2026)

`tools/speech_cut.py --pack F --only "Name"` re-cuts one speaker and leaves the
rest alone: the clip keeps the number it has in the sequence run (`number_from`),
a window cached for a different span is fetched again along with the part's
transcript (Bradley's merged 16-minute clip was first captioned against the
162-second transcript left under the same tag, and stopped at 2:42), and only
that speaker's lines in `speeches-cut.md` are rewritten. Then
`tools/drive_pack.py --pack F --prune`: a same-name file at a new size is
replaced, and clips the cutters named that the pack no longer has go to Drive's
bin (30 days). Files a person put in the folder are never touched. `--dry-run`
first shows every upload, replacement and bin. The 4:5 social variants keep the
numbers they were cut with.

## What the vote feeds (added 12 September 2026)

Everything below runs from the ledger once the division is signed off, so the
sign-off is the one hand step that unlocks the rest.

* **`tracker:signed` stances.** `src/trackerledger.apply_signed_stances` writes
  ±2 for both lobbies of every signed-off tracker division and outranks the model:
  on 12 September it corrected 68 refs, including nine June 2025 report-stage
  refs the model had scored 0 and the 2306 misread. A human sign-off is the
  vote record's direction; the model never overrides it.
* **Both lobbies = abstention.** A member in both lobbies gets one `:both` event
  and stance 0, never a flip (Snell, 11 September).
* **Present but did not vote.** For each Commons division on the tracker,
  `record_absences` looks at the day's other divisions (archived by
  `archive_same_day_divisions`) and writes a `:absent` event for anyone who voted
  that day but not on ours. Tellers count as voted (`voted_in`). On 2428 that left
  two true absentees, Onn and Stewart, not the tellers.
* **WAVERING** (`stance.wavering`): flagged when a member backed our side in at
  least two votes on the area (safeguard amendments included) or shows two of
  {good votes, majority under 5,000, recent words not hostile}. Measured on the
  Second Reading: the safeguards-two-plus list moved or stayed away at 24 per
  cent against a 16 per cent base; majority alone predicted nothing.
* **TARGETED** (`stance.campaign_targets`): a regex over `campaign_performance`
  names ("Tell <Name>: …", "Urge <Name> to …") matched to the members cache.
  `tools/campaign_targets.py --area N` prints the 20 targets against their column
  today. The campaign log is refreshed by hand (Max in #campaigns-en-gb, or the
  Looker export through `tools/load_looker_campaigns.py`); weekly is enough.
* **Caps.** `config/stance_overrides.yaml` `caps:` with `when_any`/`unless_any`:
  nobody who voted for the Bill at Second or Third Reading can sit at ++ (21
  members capped at +).
* **The sheet.** `tools/make_5ca_web.py` puts W / T / ± chips beside the name and
  a "Wavering" toggle on the internal build. The partner build carries neither
  the tiers nor the flags: our targets and our read of who might move are ours.
* **Between votes.** `tools/since_last_vote.py --area N [--since D] --write`
  lists the other side's members whose words since their last vote lean our way,
  and ours who have drifted. Areas are matched as a JSON list, never as a
  substring (area 2 is not area 12).

## sequence.md

```
# Sequence: surrogacy, 7 Sept

## Shivani Raja MP
party: Conservative · Leicester East
crop: centre
> A child cannot consent to a surrogacy arrangement. They cannot understand the
> promises adults have made.
```

* The order in the file is the order in the cut. The campaigner chooses it; the
  tool never reorders. On 8 Sept the order was: the strongest short line first
  (Raja), the front bench second (Shastri-Hurst), the sharpest image third
  (Hinder), then the rest.
* The passage is the words as SPOKEN. Start with Hansard if that is what you have;
  the report shows what was heard, and the passage is corrected to it.
* `crop:` is `left`, `centre`, `right`, or the speaker's horizontal centre in pixels
  of the 1920-wide frame. Speakers in Westminster Hall are usually a little left of
  centre; check the contact sheet.
* Six excerpts of 6-16 seconds make about 55 seconds. No end card unless asked.

## What the tool does, and why

* **1080p from the archive, one window per excerpt.** The live stream's window
  parameters are ignored by the archive, and the archive's clock is not the live
  stream's, so each window is pulled by offset with a margin, transcribed, and the
  passage found by its words. Never trust an offset you have not heard.
* **Word-exact cuts.** Hard in on the first word (cutting in the gap before it, or a
  hair early), a 0.55s tail after the last. If Hansard's text differs from the
  audio, the audio wins: Hansard tidies grammar ("that ban" became "such a ban";
  "his or herself" became "themselves"; a whole clause was added to Rebecca Smith).
* **Vertical is a full-height 9:16 crop**, placed per speaker, not a blurred
  letterbox: the speaker fills the frame. The landscape master is kept alongside.
* **Captions are the spoken words**, one or two lines of at most 30 characters,
  never crossing a sentence, every card centred on the same point (540, 1600) so
  the text never moves. Hansard wording belongs in the article; a caption that
  differs from the audio reads as a misquote.
* **Name plates** for the first 5.2 seconds of each excerpt: name in bold on
  CitizenGO principal blue `#4285F4`, party and seat on an ink `#202124` strip,
  bottom-left above the captions. White CitizenGO logo top-left. Font Helvetica
  Neue (Roboto, the brand face, is not installed on the build Mac).
* **Contact sheet and report** so the crop and the words are checked by eye before
  anything is posted.
* Footage is Parliament's, under the Parliamentary Recording Unit's terms, which
  restrict campaign use. That is the campaigner's call, recorded in the pack README.

## The article

Modelled on Right To Life UK's debate reports, openly from our perspective. See
`docs/debate-article-brief.md`. Defaults: about 800 words, continuous prose with no
subheadings, no organisation quote unless asked, every quotation in Hansard wording,
every speaker's name linked to their Hansard contribution, one paragraph for the
other side and one for the Government's line.

## Caption sync: fixed (10 Sept 2026)

Alexandra flagged on the published cut that "the audio doesn't sync up". It was never
audio against video -- both streams start at 0.000, the parts agree within 20ms, and the
accumulated delta over the whole cut is 0.000s. It was the captions, and it took four
attempts because the first three all solved the wrong problem:

1. **Spreading cards by token fraction** assumes an even speaking pace. Worst card 0.99s
   out, at a speaker's pause.
2. **Aligning each card independently** mistimed short fragments: one Yemm card 0.61s
   early and the next 0.61s late -- a boundary in the wrong place, not a drift.
3. **Consuming the words sequentially** is exactly right, and changed nothing, because
   the words being consumed came from the WINDOW's transcript rebased by the cut start.
4. **Timing against the PART's own transcript** fixed it. Two transcriptions of the same
   audio place words differently -- 0.51s and 0.71s apart on Yemm's cards -- and the part
   is what a viewer watches, so the part is the authority. One short transcription per
   part, a few seconds of CPU.

Worst card now 0.10s, which is the deliberate lead-in that puts a caption up just before
the words. Measured per part, never across the whole cut: "carrying a baby is" occurs
twice in Jim Shannon's passage and fooled a whole-cut measurement into reporting the sign
and size of the error wrongly.

## Sequencing trap: git pull comes BEFORE the store pull (9 Sept 2026)

`tools/db_state.py --pull` verifies the downloaded asset against the sidecar COMMITTED
IN THE REPO. So a job that pulls the store without pulling git first compares CI's new
asset against its own stale sidecar and reports "SHA MISMATCH ... the release asset and
the committed sidecar have diverged" -- which sounds like corruption and is not: the
guard is working and the repo is fine.

It happened on 9 Sept: a scoring job pulled the store while its checkout predated CI's
member-profiles sidecar commit. Two lessons, both cheap:

1. **`git pull` first, then `db_state.py --pull`.**
2. **A failed store pull must ABORT the job.** That run carried on and scored 3,700 refs
   into a local store that lacked CI's member-profiles work, so neither copy could
   simply overwrite the other. Recovering it meant capturing the stance rows, taking
   CI's store, and re-applying them -- survivable only because the stance table is keyed
   by ref and `INSERT OR REPLACE` is idempotent.


## Sweeping: sitting days, not weeks (9 Sept 2026)

Christopher asked whether to sweep on days with activity on our issues, or to sweep only
what is new. Sweeping "on days with activity" is circular -- you cannot know a debate
touched our ground until you have swept it. What is free to know is whether the House sat.

So the unit is the SITTING DAY, swept once, ever:

* `src/daysweep.py` + `tools/day_sweep.py`. `sweep_log` records one row per source, day
  and House, including that a recess day was checked and the House did not sit, so it is
  never checked again. About 150 sitting days a year at 55 free searches each.
* `sectionsforday.json` is the sitting test: empty for a Saturday, sections for a sitting
  day. There is no sitting-dates endpoint (404 as at 2026-09-09), and `lastsittingdate`
  gives only the most recent. An API failure is recorded as UNKNOWN, never as a recess:
  burying a day as "did not sit" would lose it for ever.
* A day within two days of today is looked at again, because Hansard publishes hours
  after the House rises and revises text afterwards.
* One search pass covers BOTH Houses -- Hansard's contribution search is not
  house-scoped -- so the watermark holds a row per House but the terms are paid for once.
* **One pass, two purposes.** The contributions fetched to decide whether a debate is
  worth a pack are exactly the rows the ledger wants; they used to be fetched twice.
* The weekly pass in run_weekly is now a REPAIR pass and skips days the daily sweep
  already covered. It stays because a day the daily job missed -- runner down, a term
  refused, text revised late -- would otherwise be lost, and record_event upserts, so
  repeating a day costs only the search.

**What deliberately did NOT move.** Written questions are answered days or weeks after
they are asked, and Early Day Motion signatures accrue for weeks. Those genuinely change
after the fact, so a once-only day sweep would freeze them wrong; they stay on the
weekly rolling window.

## Footage without the Mac (10 Sept 2026)

The reel pipeline no longer downloads the sitting. Two steps, both cheap:

1. **Locate.** Hansard already says when each member was on their feet, so the search is
   bounded to their own speech. That span is fetched at 180p -- a few MB -- transcribed,
   and the passage aligned inside it. If `clips/whole-debate.words.json` happens to exist
   the answer is free and this is skipped.
2. **Fetch.** Only the passage is pulled at 1080p, by HLS segment: about 7 MB and two
   seconds. `vod-idx.ism/.mp4` is 403 and `?t=` clipping answers 206 but is ignored, so
   segments are the only route -- and they are plain sequential HTTPS with no auth.

Measured on two speakers with NO whole-debate transcript: 76 MB fetched and 62 seconds
end to end, against 515 MB and about an hour before. That is what makes the whole
pipeline runnable on a CI runner rather than a laptop.

**EVERY span must be searched, longest first.** Jonathan Hinder spoke twice on 7 Sept and
the passage wanted was in his second, shorter contribution; a longest-span-only search
reported words he plainly said as "not heard". The union first-to-last is not used
either: a member who intervenes early and speaks late would span an hour and a half.

yt-dlp is now needed only to resolve a manifest for a pack that has none; `pack.json`
already carries it, and no fetching uses yt-dlp at all.

## Full speeches in 16:9 (added 11 September 2026)

`tools/speech_cut.py --pack F` cuts every onside speaker's full speech as a
1920x1080 clip alongside the vertical reel: `clips/final/speech-NN-<name>-<time>.mp4`
(subtitled, name plate, logo), `-clean.mp4` (no burn-in) and a `.srt`, with
`speeches-cut.md` in the pack saying what was cut and how well the trim anchored.

* Footage is the speaker's own Hansard span fetched by HLS segment at 1080p with 25
  seconds either side. Never the whole sitting.
* The trim is word-exact: the speech's first and last twenty-five Hansard words are
  each located in the window's transcript. Hansard timestamps alone are a minute out
  either way, which is why the old `--download` clips began mid-sentence of the
  previous speaker. If an end cannot be placed, the Hansard time is used and
  `speeches-cut.md` says so.
* Contributions under 120 words are interventions, not speeches, and are skipped.
* Captions are the Hansard text in 44-character cards timed against the part's own
  transcript (`card_times`), so a misheard word never reaches the screen but the
  timing is what was spoken. The reel's captions stay spoken-word, because a 45-second
  passage is checked by ear; a ten-minute speech is not.
* By default it cuts the speakers named in `sequence.md` (the ones judged worth a
  reel); `--all` cuts every onside speaker, `--only "Name"` one. Before the checklist
  is confirmed the pass read stands in, as for `--draft` and `--provisional`;
  `--confirmed-only` ignores it.

## When the House divided, the vote fills the checklist (11 September 2026)

The Second Reading of the Terminally Ill Adults (End of Life) Bill was negatived 270-286
(Commons Votes division 2428; Hansard numbers it 75). Every one of the 75 speakers voted, so
ONSIDE was filled from the division record rather than read from their words: a No vote on
"That the Bill now be read a Second time" is a vote against the Bill, so No = yes, Aye = no,
and each checklist block carries a `- vote:` line saying which. The pass had misread two No
voters as "against us" (Simon Hoare's devil's-advocate intervention, Sir Edward Leigh's
rhetorical concession) and nine as neutral. The division is the House's own record and
settles the question the checklist asks; it does not replace the campaigner's reading of a
debate with no vote. `divisions()` now puts the result at the head of roundup.md and into
the report writer's input, so a report can no longer describe a decided debate as ongoing.

Two traps found the same evening. The reel draft's `limit` of eight silently dropped fourteen
other cuttable speakers (the strongest speech among them); they are now listed at the foot
with their passage. The writer's brief, ranked by longest single contribution, dropped a
sponsor interrupted 37 times and the Minister, so the report said no Minister had replied;
the opener and anyone attributed by office are now always in, and the rest rank by all their
words. MAX_TOKENS 8000 was hit (the writer's thinking counts against it) and the transport's
120s timeout then fired; both scale now. And: one pack, one session. Two sessions rendering
the same pack from different sequence.md files race on identical output paths in clips/final.

## Choosing the speeches (added 11 September 2026)

`tools/pick_speeches.py --pack F --top 8 --write-sequence` ranks every confirmed-onside
member who made a speech (250 words or more) with one model call — one clear argument,
emotional force, a standalone 30-60 second passage in their own words, a distinct angle,
the speaker's standing — verifies each proposed passage verbatim against the member's
words, and writes `selection.md`/`selection.json` and a `sequence.md` for the top N (the
previous sequence is kept as `sequence-previous.md`). Onside is still the checklist's
decision; the judge only orders it. `debate_report.py --publish --with-clips` then adds
a "Best speeches" section to the canvas and uploads the reel and the chosen full-speech
clips into the thread (the Slack app needs the `files:write` scope for that).
