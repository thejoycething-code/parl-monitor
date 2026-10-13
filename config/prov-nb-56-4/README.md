# New Brunswick, 56th Legislature, 4th Session (2009-2010): the Library's record

Source: the Legislative Library of New Brunswick (Kenda Clark-Gorey), scans
sent on 9 October 2026 from the compiled Journal of the 4th Session of the
56th Legislative Assembly, which legnb.ca does not publish. Transcribed by
Claude on 13 October 2026 and checked against the scans.

* `members.csv`: the Journal's "Members of the Legislative Assembly" page,
  55 constituencies as printed (honorifics and post-nominals kept). Two seats
  are printed "Vacant", with the page's own notes: Moncton North (Hon.
  Michael Murphy, Q.C., resigned 5 February 2010) and
  Rogersville-Kouchibouguac (Rose-May Poirier resigned 26 February 2010). The
  Speaker was Hon. Roy Boudreau. The page's Residence column is not kept: the
  store does not use it. `member_key` is ours, not the Journal's: it is set
  only where the member already has a key in the store under another form of
  the name (Christopher Collins is `chris-collins` from the 57th
  Legislature's compiled Journals); blank means the key is derived from the
  name as for every compiled Journal (`src/ingest/prov_nb.member_key`).
* `recorded-votes.csv`: the Journal index's entries for the session's 11
  recorded votes, with the Journal page; the dates were written on the scan
  by the librarian. Every one of them is matched to the day's Journal on
  legnb.ca (`src/ingest/prov_nb.check_seed_votes`).

Read by `src/ingest/prov_nb.py` (`load_seed_roster`, `load_seed_votes`)
whenever session 56-4 is collected: the members page dates each member's
term to the session, the two resignations end those members' terms, and
the division lists printed in each day's Journal are resolved against it.
The page prints no party, and the session has no Hansard online, so the
votes carry no party at the vote. The one-off run is in docs/mac-mini.md
("New Brunswick 56-4").
