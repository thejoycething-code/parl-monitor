# Party logos — drop-in slot

The party mark in the MP header is a circular slot. Put a file here named
after the party and it fills the circle; with no file, the circle shows the
party colour with the party's initials on it, so a missing logo can never
leave a hole.

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

## Before you add them

Party logos are registered trademarks. Using them to identify a party in a
factual record is ordinarily fine, but it is a judgement for CitizenGO, not
for me — and I have deliberately not downloaded any. Most parties publish
brand assets or a press/media page; those are the source to use, under
whatever terms they set.
