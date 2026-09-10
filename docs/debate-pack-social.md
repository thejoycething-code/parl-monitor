# The social cut and the article: defaults for a debate

Set on the surrogacy debate (Westminster Hall, 7 September 2026) and adopted as the
defaults on 8 September. Anything here can be overridden per pack, but the tool and
the writer start from these.

## Order of work

1. `tools/debate_pack.py --date D --find TERM` once Hansard is up: roundup, checklist,
   speeches, quotes, shotlist.
2. Confirm who is onside in `checklist.md` (the pass's reading is never the verdict),
   then `--apply`.
3. NOT NEEDED since 2026-09-10: the whole-sitting download. Each passage is located
   inside the speaker's own Hansard span and fetched by HLS segment. Optional, and
   still cheapest when it exists: `--download-debate` then `--transcribe`.
4. `tools/social_cut.py --pack F --draft` writes a first `sequence.md` of REEL-LENGTH
   passages (30-60 seconds of speech, `reel_passage`) from each onside speaker's
   longest contribution in speeches.md, longest first. Run it before the checklist
   is confirmed and the pass read stands in: the file then carries a PROVISIONAL
   line and lists, at the foot, who was left out and why. The template is
   `docs/sequence-template.md`. Reorder, trim to about six, then run
   `tools/social_cut.py --pack F`.
   Before publishing a report, `tools/debate_report.py --pack F --preview` creates
   the canvas and shares it with the DM recipient alone, so the rendering is seen
   before anything reaches the channel; `--publish` is the separate, explicit step.
   The report has the same mode: `tools/debate_report.py --pack F --provisional`
   drafts from the pass read, marks report.md, social.md and report.json, and
   `--publish` refuses it (no flag clears that) until the checklist is confirmed and
   the report regenerated plain. Onside remains the campaigner's decision; the
   provisional mode exists so a draft can be waiting the same evening.
5. Check `clips/final/social-cut-contact-sheet.jpg` (crops) and `social-cut.md`
   (the words heard). Correct `sequence.md` and re-run with `--render`.
6. Write the article from `speeches.md` to the brief below.

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

