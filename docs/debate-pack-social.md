# The social cut and the article: defaults for a debate

Set on the surrogacy debate (Westminster Hall, 7 September 2026) and adopted as the
defaults on 8 September. Anything here can be overridden per pack, but the tool and
the writer start from these.

## Order of work

1. `tools/debate_pack.py --date D --find TERM` once Hansard is up: roundup, checklist,
   speeches, quotes, shotlist.
2. Confirm who is onside in `checklist.md` (the pass's reading is never the verdict),
   then `--apply`.
3. Download the whole debate once and transcribe it, so every later cut is word-exact:
   `--download-debate --from HH:MM --to HH:MM`, then `--cut cuts.md` (which caches
   `clips/whole-debate.words.json`).
4. Write `sequence.md` and run `tools/social_cut.py --pack F`.
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
