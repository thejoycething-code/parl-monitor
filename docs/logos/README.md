# Party logos — drop-in slot

The party mark in the MP header is a circular slot. Put a file here named
after the party and it fills the circle; with no file the circle shows the
party colour alone, so a missing logo can never leave a hole. (The initials
that briefly sat inside it were removed on 2026-08-27 at Christopher's
request.)

## Naming

Lowercase the party name exactly as the Members API gives it, strip accents,
replace `&` with `and`, and turn every other run of non-alphanumerics into a
single hyphen:

    Labour                            -> labour.svg
    Conservative                      -> conservative.svg
    Liberal Democrat                  -> liberal-democrat.svg
    Scottish National Party           -> scottish-national-party.svg
    Reform UK                         -> reform-uk.svg
    Green Party                       -> green-party.svg
    Plaid Cymru                       -> plaid-cymru.svg
    Democratic Unionist Party         -> democratic-unionist-party.svg
    Sinn Féin                         -> sinn-fein.svg
    Social Democratic & Labour Party  -> social-democratic-and-labour-party.svg
    Alliance                          -> alliance.svg
    Ulster Unionist Party             -> ulster-unionist-party.svg
    Traditional Unionist Voice        -> traditional-unionist-voice.svg

`tools/party_logo_slots.py` prints the exact filename for every party
currently sitting, with the number of MPs affected.

## Format

SVG preferred, PNG works. The slot is 17px and crops to a circle
(`object-fit: cover`), so a square logo on a transparent or white ground
works best; a wide wordmark will be cropped to its middle. Both builds need
the file: `partner_site/logos/` and `docs/logos/`.

## Sourcing: what I found when I tried (2026-08-27)

Christopher asked me to source the four main logos. I did the search; the
blocker is licensing and geometry, not effort.

| Party | Best free file | Licence | Aspect | Usable in a circle? |
|---|---|---|---|---|
| Labour (361 MPs) | `File:Labour Party (UK) logo.svg` (en.wikipedia) | **Fair use** | square | **No — copyrighted** |
| Conservative (118) | `File:Conservative Party wordmark.svg` (Commons) | Public domain, marked *trademarked* | 8.4:1 | No — wordmark |
| Liberal Democrat (71) | `File:Liberal Democrats logo (wordmark).svg` (Commons) | Public domain | 2.9:1 | No — wordmark |
| Co-operative (43) | `File:Co-operative party wordmark.svg` (Commons) | Public domain | 3.4:1 | No — wordmark |

Two separate walls:

1. **The square emblems are all copyrighted.** The rose, the oak tree, the
   bird of liberty and the Co-op square mark exist on Wikipedia only under
   fair-use rationales written for their own articles. That rationale does
   not travel to our site, so they cannot be copied here. Commons — which
   accepts freely-licensed files only — has no party emblem at all; a search
   returns unrelated newspapers and PDFs.

2. **The freely-licensed files are wordmarks.** Public domain, because plain
   text falls below the threshold of originality — and 2.9:1 to 8.4:1, so
   `object-fit: cover` in a 17px circle shows two letters of nonsense, and
   `contain` shows an illegible strip.

So none of the four can be dropped in as they stand. I have downloaded
nothing.

### If you do want logos

* **Ask the parties.** Press or media offices supply brand assets, usually
  including a square avatar version, under stated terms. That solves both
  walls at once.
* **Have a designer make square marks.** Nominative use of a party's mark to
  identify it in a factual record is ordinarily defensible; a redrawn
  approximation is not obviously better than initials.
* **Grow the slot first, either way.** At 17px a full party emblem is a blob
  — favicons are 16px and are drawn as radically simplified marks. A logo
  needs roughly 24–32px to read. The initials the slot shows today are
  arguably the *better* design at 17px, because two or three glyphs are
  exactly what that size can hold.

Party logos are registered trademarks. Publishing them is CitizenGO's
judgement, not mine.
