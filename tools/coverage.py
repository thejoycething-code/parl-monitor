"""Is every source still being tracked? -- the watcher nobody had.

    python3 tools/coverage.py            # report; exit 1 if a source is overdue
    python3 tools/coverage.py --quiet    # report only what is overdue

Christopher, 2026-09-04: "What else needs building to ensure we're
properly tracking". This is the answer to how the last failure went
unseen. On 3 September the UPR monthly harvested 1,218 new
recommendations, published them, and had its store overwritten three
hours later by a hand push from a laptop holding an older copy. Both
runs were green. Nothing anywhere said "this source has not refreshed in
19 days", so the loss surfaced a day later only because someone thought
to measure it.

Two questions, because they fail differently:

  1. IS THE PIPELINE RUNNING?  source_runs, stamped by db_state.py --push
     at the end of every workflow. Answers "did the Sunday pull run?",
     which no amount of reading Westminster's tables could -- they carry
     no captured_at at all.
  2. IS THE SOURCE ANSWERING?  the newest last_seen / captured_at in each
     table. A pipeline can run green while one feed inside it 403s.

Recess is not failure. A chamber that is not sitting produces no
divisions, so this never judges freshness by the DATE OF THE BUSINESS --
only by when we last SAW the source. Feeds that are written once per
item and never re-stamped are listed as such and never fail the run.
"""

from __future__ import annotations

import datetime
import json
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# workflow -> (expected cadence in days, grace, why)
PIPELINES = {
    "Sunday pull": (7, 3, "Westminster: roster, events, divisions"),
    "Monday publish": (7, 3, "the edition, the pages, the briefs"),
    "Holyrood weekly": (7, 4, "Scotland"),
    "Senedd weekly": (7, 4, "Wales"),
    "NI Assembly weekly": (7, 4, "Northern Ireland"),
    "EU weekly": (7, 3, "the EU edition and its collectors"),
    "Germany weekly": (7, 4, "Bundestag and the sixteen Land parliaments"),
    # Nightly, and it stamps a heartbeat whether or not the Parliament sat:
    # most nights it records "did not sit" and publishes nothing else, which
    # is exactly the signal we want -- silence here means the workflow died,
    # not that Brussels is quiet. Grace of 2 covers a cancelled slot.
    "EU day sweep": (1, 2, "the EP swept per sitting day (roll calls and adopted texts)"),
    "UPR monthly": (31, 7, "UN Universal Periodic Review"),
    # Missing until 2026-09-04, like EU weekly was from the alert list:
    # it pulls service history, party spells and contact details for
    # every chamber, and nothing would have said if it stopped.
    # MONTHLY since 40c07189 (22 Sept 2026, on the 10th, to save CI minutes),
    # which left this at 7 and failed the watch every day from 28 Sept.
    "Member profiles": (31, 7, "service history, party spells, contacts"),
    # Since 2026-09-09 this is the ledger's PRIMARY source of speeches; the
    # Sunday pull only repairs what it missed. Cadence 1 with a grace of 3
    # because it runs on sitting weekdays only: Friday evening to Monday
    # morning is the longest legitimate gap.
    "Day sweep": (1, 3, "the day's speeches on our issues, and the radar"),
    # Scheduled 26 September 2026, Tuesdays. Grace 4 as for the other weeklies.
    "Canada weekly": (7, 4, "Parliament of Canada: House, Senate, petitions, Gazette"),
    "US weekly": (7, 4, "US Congress: bills, House and Senate roll calls"),
    # Scheduled 9 October 2026, Fridays (au-weekly.yml; the Mac Mini first).
    "Australia weekly": (7, 4, "Australia's Federal Parliament: bills, House and Senate divisions"),
    # Scheduled 9 October 2026, Fridays (ie-weekly.yml; the Mac Mini first).
    "Ireland weekly": (7, 4, "the Oireachtas: Dail, Seanad and committee divisions, bills, members"),
    # Scheduled 9 October 2026, Saturdays (at-weekly.yml; the Mac Mini first).
    "Austria weekly": (7, 4, "Austria's Parliament: Nationalrat and Bundesrat items and Klub votes"),
    # Scheduled 9 October 2026, Thursdays (nl-weekly.yml; the Mac Mini first).
    "Netherlands weekly": (7, 4, "Tweede Kamer: fracties, members, votes and positions"),
    # Scheduled 9 October 2026, Sundays (pl-weekly.yml; the Mac Mini first).
    "Poland weekly": (7, 4, "Polish Sejm: prints, processes, recorded votes"),
    # Scheduled 9 October 2026, Saturdays (it-weekly.yml; the Mac Mini first).
    "Italy weekly": (7, 4, "Italy's Parliament: bills, Senate and Camera votes"),
    # Scheduled 9 October 2026, Saturdays (ch-weekly.yml; the Mac Mini first).
    "Switzerland weekly": (7, 4, "Swiss Federal Assembly: businesses, Nationalrat and Staenderat votes"),
    # Scheduled 9 October 2026, Saturdays (be-weekly.yml; the Mac Mini first).
    "Belgium weekly": (7, 4, "Belgium's federal Chamber: dossiers and recorded votes"),
    # Scheduled 9 October 2026, Saturdays (fr-weekly.yml; the Mac Mini first).
    "France weekly": (7, 4, "France's Assemblee nationale: dossiers, scrutins, deputies"),
    # Scheduled 9 October 2026, Saturdays (pt-weekly.yml; the Mac Mini first).
    "Portugal weekly": (7, 4, "Portugal's Assembleia da Republica: initiatives, votes, deputies"),
    # Scheduled 3 October 2026, Wednesdays (prov-weekly.yml). Grace 4 as for
    # the other weeklies.
    "Provinces weekly": (7, 4, "Canada's provincial legislatures: AB SK BC MB ON NB NL QC NS"),
}

# Pipelines deliberately not running. Listed so a PAUSE never reads as a
# failure, and a pause nobody remembers never reads as health.
PAUSED = {
    "UN calls weekly": "paused 2026-08-17 by Christopher: nothing "
                       "UN-related publishes until the monitor covers the "
                       "issues and the forward calendar properly.",
}

# table -> (freshness column, expected days, grace, note)
FEEDS = [
    ("bill_amendments", "last_seen", 7, 3, "amendments to watched Bills (Sunday pull)"),
    # MEASURED (22 September 2026), not assumed: de_documents writes with
    # INSERT OR IGNORE and de_divisions SKIPS votes it already holds, so
    # neither re-stamps and both belong in ONCE_EVER. de_vorgaenge is the
    # one German table that really is a heartbeat: its upsert sets
    # last_seen=excluded.last_seen, and the weekly term sweep asks DIP for
    # every tier-1 term over a 120-day window, so a live run re-sees the
    # recent ones whether or not anything new appeared.
    ("de_vorgaenge", "last_seen", 7, 4, "Bundestag Vorgänge from DIP (Germany weekly)"),
    # The Tagesordnungen feed re-stamps every sighting, so this IS a
    # heartbeat -- and a loud one: it is a rolling window with no archive,
    # so a week the collector does not run is a week of agendas nobody can
    # ever recover.
    ("de_agenda", "last_seen", 7, 4, "Bundestag committee and plenary agendas (Germany weekly)"),
    # All four re-stamp on every sweep, so each is a real heartbeat.
    ("de_petitions", "last_seen", 7, 4, "Bundestag e-petitions open for co-signature (Germany weekly)"),
    ("de_petition_snapshots", "captured_at", 7, 4, "German petition signature snapshots"),
    ("de_judgments", "last_seen", 7, 4, "Bundesverfassungsgericht cases listed for decision"),
    ("de_amendments", "last_seen", 7, 4, "Änderungsanträge to bills (Germany weekly)"),
    ("de_committee_reports", "last_seen", 7, 4, "Bundestag committee reports and laid papers (Germany weekly)"),
    ("judge_verdicts", "captured_at", 7, 3, "the judge evaluation bank (Sunday pull)"),
    ("dv_petitions", "last_seen", 7, 4, "Senedd and Holyrood petitions (devolved weeklies)"),
    ("dv_petition_snapshots", "captured_at", 7, 4, "devolved petition signature snapshots"),
    ("petitions", "last_seen", 7, 3, "e-petitions on our ground (collated, not published)"),
    ("petition_snapshots", "captured_at", 7, 3, "e-petition signature snapshots"),
    ("sp_items", "last_seen", 7, 4, "Holyrood questions and motions"),
    ("sp_divisions", "last_seen", 7, 4, "Holyrood divisions"),
    ("sp_members", "last_seen", 7, 4, "MSP roster"),
    ("sd_items", "last_seen", 7, 4, "Senedd questions"),
    ("sd_divisions", "last_seen", 7, 4, "Senedd divisions"),
    ("sd_members", "captured_at", 7, 4, "MS roster"),
    ("member_aliases", "captured_at", 7, 4, "the Welsh name bridge"),
    ("ni_items", "last_seen", 7, 4, "NI questions and motions"),
    ("ni_divisions", "last_seen", 7, 4, "NI divisions"),
    ("ni_members", "last_seen", 7, 4, "MLA roster"),
    ("dg_consultations", "last_seen", 7, 4, "devolved consultations"),
    ("sp_events", "last_seen", 7, 4, "Holyrood events"),
    ("sp_bills", "last_seen", 7, 4, "Holyrood bill register"),
    ("sp_committees", "last_seen", 7, 4, "Holyrood committees"),
    ("sd_events", "last_seen", 7, 4, "Senedd events"),
    ("sd_bills", "last_seen", 7, 4, "Senedd bill register"),
    ("sd_committees", "last_seen", 7, 4, "Senedd committees"),
    ("ni_committees", "last_seen", 7, 4, "NI committees"),
    ("eu_cmte_meetings", "last_seen", 7, 3, "EP committee meetings"),
    ("dv_post", "last_seen", 31, 7, "devolved members' posts"),   # Member profiles is monthly
    ("dv_contact", "last_seen", 31, 7, "devolved members' contacts"),   # Member profiles is monthly
    ("eu_agenda", "last_seen", 7, 3, "EP forward agenda"),
    ("eu_texts", "last_seen", 7, 3, "EP adopted texts"),
    ("eu_pqs", "last_seen", 7, 3, "EP written questions"),
    ("eu_cmte_docs", "last_seen", 7, 3, "EP committee documents"),
    ("eu_ecis", "last_seen", 7, 3, "European Citizens' Initiatives"),
    ("eu_consultations", "last_seen", 7, 3, "Commission consultations"),
    ("eu_meps", "last_seen", 7, 3, "MEP roster"),

    ("upr_recommendations", "captured_at", 31, 7, "UPR recommendations"),
    # Canada (26 September 2026). MEASURED which re-stamp: the division and
    # bill lists are re-read whole every run and their upserts set
    # last_seen, and tools/ca_hansard.py refreshes the roster, so these three
    # move every week even in recess. ca_petitions re-stamps only what it
    # fetches (new, open, or ours awaiting a response), so it gets a week's
    # extra grace for a quiet stretch.
    ("ca_divisions", "last_seen", 7, 4, "House and Senate divisions (Canada weekly)"),
    ("ca_bills", "last_seen", 7, 4, "LEGISinfo bills (Canada weekly)"),
    ("ca_members", "last_seen", 7, 4, "House of Commons roster (Canada weekly)"),
    ("ca_petitions", "last_seen", 7, 7, "House petitions, presented and open (Canada weekly)"),
    # The SCC feed always lists 100 items and every one is re-stamped, so
    # this moves every week, recess included (tools/ca_courts.py).
    ("ca_judgments", "last_seen", 7, 4, "Supreme Court judgments feed (Canada weekly)"),
    # US Congress (9 October 2026). The BILLSTATUS zips are re-read whole
    # every run and the crosswalk too, so bills and members move every week,
    # recess included. Divisions are new rows only (a vote is final), and
    # Congress is out for long stretches: the House cast no vote between
    # 16 September 2026 and the 3 November midterms, about eight weeks. So a
    # month expected plus a month's grace, or every election recess cries wolf.
    ("us_bills", "last_seen", 7, 4, "Congress bills (US weekly)"),
    ("us_members", "last_seen", 7, 4, "Congress members crosswalk (US weekly)"),
    ("us_divisions", "last_seen", 31, 31, "House and Senate roll calls (US weekly)"),
    # Australia (9 October 2026). MEASURED which re-stamp: the OpenAustralia
    # member lists are re-read whole every run, and every bill that became an
    # Act is re-stamped from the Federal Register's listing every run, so
    # members and bills move every week, recess included. Divisions move only
    # when a Hansard day file is new or re-parsed, and Canberra sits in
    # blocks (no sitting day between 17 September and 9 October 2026, nor
    # between 2 July and 11 August): a month plus a month's grace, as for
    # the US. au_offices, au_votes and au_hansard_files carry no sighting
    # column.
    ("au_members", "last_seen", 7, 4, "Federal Parliament members (Australia weekly)"),
    ("au_bills", "last_seen", 7, 4, "Federal bills, from Hansard and the Register of Legislation (Australia weekly)"),
    ("au_divisions", "last_seen", 31, 31, "House and Senate divisions (Australia weekly)"),
    # The week ahead (tools/us_schedule.py, 9 October 2026). MEASURED on the
    # live run of that day, in the election recess: us_schedule_weeks gains
    # or re-stamps a row for every week and source ASKED, 404 or not, so it
    # moves every run. us_schedule moves every run too: when no week ahead
    # is listed, the latest list the House posted (14 September) is read
    # again. Committee meetings are only re-stamped while they are posted,
    # and the House posts none in recess, so a month plus a month's grace,
    # as for the roll calls.
    ("us_schedule_weeks", "last_seen", 7, 4, "the week ahead, one row per week and source asked (US weekly)"),
    ("us_schedule", "last_seen", 7, 7, "bills scheduled for the floor or a committee (US weekly)"),
    ("us_meetings", "last_seen", 31, 31, "House and Senate committee meetings (US weekly)"),
    # The executive and the Court (9 October 2026). Each Federal Register run
    # re-reads the last fourteen days of publication and re-stamps what it
    # sees, and the Register publishes every working day, so this moves every
    # week. The slip-opinion pages of the current and last term are re-read
    # whole, like the SCC feed, so us_court_cases moves every week too.
    ("us_fr_documents", "last_seen", 7, 4, "Federal Register: orders and rules (US weekly)"),
    ("us_court_cases", "last_seen", 7, 4, "Supreme Court opinions and grants (US weekly)"),
    # Ireland (9 October 2026). MEASURED which re-stamp: tools/ie_rollcalls.py
    # re-reads both rosters, every bill with an event since the Dail first
    # met, and every division of both Houses whole on each run, and all three
    # upserts set last_seen. So unlike the US divisions these move every
    # week, recess included (the Dail divided on no day between 15 July and
    # 16 September 2026 except a recall on 28 August).
    ("ie_members", "last_seen", 7, 4, "Dail and Seanad rosters (Ireland weekly)"),
    ("ie_bills", "last_seen", 7, 4, "Oireachtas bills (Ireland weekly)"),
    ("ie_divisions", "last_seen", 7, 4, "Dail, Seanad and committee divisions (Ireland weekly)"),
    # Austria (9 October 2026). MEASURED which re-stamp: both chambers' item
    # lists and both member lists are re-read whole every run, so items and
    # members move every week, recess included. A division is re-stamped only
    # when its item's history page is read again, which happens only when the
    # item moved; the Nationalrat's summer recess runs from early July to
    # mid-September. A month plus a month's grace, as for the US. at_votes
    # carries no sighting column.
    ("at_items", "last_seen", 7, 4, "Nationalrat and Bundesrat items (Austria weekly)"),
    ("at_members", "last_seen", 7, 4, "Nationalrat and Bundesrat members (Austria weekly)"),
    ("at_divisions", "last_seen", 31, 31, "Klub votes on our ground (Austria weekly)"),
    # Netherlands (9 October 2026). MEASURED which re-stamp: the fracties and
    # the 150 current seats are re-read whole every run, so they move every
    # week, recess included. Votes are re-stamped whenever they fall in the
    # six-week window the collector re-reads, so they stop moving about six
    # weeks into the summer recess (the Kamer did not vote between 2 July and
    # 3 September 2026): a month plus a month's grace, as for the US. A zaak
    # is re-stamped with its vote, so it gets the same.
    ("nl_members", "last_seen", 7, 4, "Tweede Kamer members (Netherlands weekly)"),
    ("nl_fracties", "last_seen", 7, 4, "Tweede Kamer fracties (Netherlands weekly)"),
    ("nl_divisions", "last_seen", 31, 31, "Tweede Kamer votes (Netherlands weekly)"),
    ("nl_zaken", "last_seen", 31, 31, "Zaken voted on in the Tweede Kamer (Netherlands weekly)"),
    # Poland (9 October 2026). MEASURED which re-stamp: the deputy list, the
    # print list and every process page are re-read whole on every run, so
    # those move every week, recess included. Votes move only when a sitting
    # is re-read (the newest two every run, so a recess week still re-stamps
    # them, but the Sejm's summer break runs late July to early September):
    # a month plus a month's grace, as for the US. pl_votes carries no
    # sighting column.
    ("pl_members", "last_seen", 7, 4, "Sejm deputies (Poland weekly)"),
    ("pl_prints", "last_seen", 7, 4, "Sejm prints, the whole term's list (Poland weekly)"),
    ("pl_processes", "last_seen", 7, 4, "Sejm legislative processes (Poland weekly)"),
    ("pl_divisions", "last_seen", 31, 31, "Sejm recorded votes (Poland weekly)"),
    # Italy (9 October 2026). MEASURED which re-stamp: every bill reading of
    # the legislature is re-read whole from dati.senato.it every run, and so
    # are the 212 senators, so bills and members move every week, recess
    # included. Divisions move only when the chambers vote (the last two
    # Senate sittings and 14 Camera days are re-read): a month plus a
    # month's grace, as for the US, for the summer and election recesses.
    # it_votes carries no sighting column.
    ("it_bills", "last_seen", 7, 4, "Bill readings of both chambers, from dati.senato.it (Italy weekly)"),
    ("it_members", "last_seen", 7, 4, "Senators and Camera deputies (Italy weekly)"),
    ("it_divisions", "last_seen", 31, 31, "Senate and Camera votes (Italy weekly)"),
    # Switzerland (9 October 2026). MEASURED which re-stamp: members and the
    # legislature's sessions are re-read whole every run; businesses only when
    # the service has modified them, which it did to 4,018 between 1 September
    # and 9 October 2026, recess weeks included. Divisions move only while a
    # session is open or within 21 days of its end, and the longest gap
    # between sessions is the summer (Sommersession ends mid-June, the
    # Herbstsession starts mid-September: 66 days after the 21): a month plus
    # 45 days' grace. ch_votes carries no sighting column.
    ("ch_members", "last_seen", 7, 4, "Federal Assembly members (Switzerland weekly)"),
    ("ch_sessions", "last_seen", 7, 4, "Federal Assembly sessions (Switzerland weekly)"),
    ("ch_businesses", "last_seen", 7, 7, "Federal Assembly businesses, DE and FR (Switzerland weekly)"),
    ("ch_divisions", "last_seen", 31, 45, "Nationalrat and Staenderat votes (Switzerland weekly)"),
    # Belgium (9 October 2026). MEASURED which re-stamp: both member lists and
    # all 39 pages of the dossier index are re-read whole every run, so
    # be_members and be_dossiers move every week, recess included. Divisions
    # move only when a sitting is new or among the three re-read: the Chamber
    # breaks from late July to mid-September, so a month plus a month's grace,
    # as for the US. be_sittings and be_votes carry no sighting column.
    ("be_members", "last_seen", 7, 4, "Chamber members (Belgium weekly)"),
    ("be_dossiers", "last_seen", 7, 4, "Chamber dossier index (Belgium weekly)"),
    ("be_divisions", "last_seen", 31, 31, "Chamber recorded votes (Belgium weekly)"),
    # France (9 October 2026). MEASURED which re-stamp: every dossier and
    # every sitting deputy is re-read whole from the AN's nightly zips on
    # every run, recess included. Scrutins are written once, then re-read for
    # 30 days (mises au point), so they move only when the Assemblee votes:
    # none between 22 July and late September 2026. A month plus a month's
    # grace, as for the US. fr_groups and fr_votes carry no sighting column.
    ("fr_dossiers", "last_seen", 7, 4, "Assemblee nationale dossiers legislatifs (France weekly)"),
    ("fr_members", "last_seen", 7, 4, "Assemblee nationale deputies (France weekly)"),
    ("fr_divisions", "last_seen", 31, 31, "Assemblee nationale scrutins (France weekly)"),
    # Portugal (9 October 2026). MEASURED which re-stamp: the Assembleia's
    # dumps are per legislature and re-read whole every run, and every
    # initiative, vote and deputy in them is upserted, so all three move every
    # week, recess included. pt_authors, pt_group_votes and pt_votes carry no
    # sighting column.
    ("pt_members", "last_seen", 7, 4, "Assembleia deputies (Portugal weekly)"),
    ("pt_initiatives", "last_seen", 7, 4, "Assembleia initiatives (Portugal weekly)"),
    ("pt_divisions", "last_seen", 7, 4, "Assembleia plenary votes (Portugal weekly)"),
    # Canada's provinces (3 October 2026). MEASURED which re-stamp, writer by
    # writer: Alberta, BC and Newfoundland upsert their whole roster on every
    # run (Quebec's when a week old, and prov-weekly re-reads it weekly), and
    # Alberta, BC, Manitoba and Quebec re-store every bill on the session's
    # listing on every run, recess included -- so these two move every week.
    # The watch is per TABLE, not per province: one province dying shows as
    # its own failed step (and the failure alert), not here.
    ("prov_members", "last_seen", 7, 4, "provincial rosters (Provinces weekly)"),
    ("prov_bills", "last_seen", 7, 4, "provincial bills, from each session's listing (Provinces weekly)"),
]

# Which feeds each pipeline is responsible for. This drives the check
# that actually catches a CLOBBER: a pipeline that ran yesterday whose
# data is weeks old did not fail -- it succeeded and its work was thrown
# away, or it stored nothing while reporting success. That is exactly
# what happened to the UPR monthly on 2026-09-03: green run, 1,218
# recommendations harvested, and a store 19 days stale afterwards.
# Feeds a human has confirmed are legitimately empty, and why. Keep it short:
# every entry here is an alert somebody decided not to hear.
ALLOWED_EMPTY = {
    # de_documents is filled by tools/de_documents.py --mode WINDOW, which
    # sweeps /drucksache by date and body-matches. The Germany weekly runs
    # --mode TERMS, which drives /vorgang from the tier-1 German terms and
    # writes de_vorgaenge only. So this table is empty because of a mode
    # choice, not a broken collector, and the day someone adds a window step
    # to de-weekly.yml this entry must come straight back out.
    "de_documents": "the weekly runs --mode terms, which writes Vorgänge "
                    "only; --mode window is what fills this table",
}

# Write-once feeds belonging to a pipeline that is deliberately stopped: an
# empty table there is the pause, not a wipe.
PAUSED_TABLES = {"un_votes", "un_documents", "un_calendar"}


PIPELINE_FEEDS = {
    "Holyrood weekly": ["sp_items", "sp_divisions", "sp_members",
                        "sp_events", "sp_bills", "sp_committees"],
    "Senedd weekly": ["sd_items", "sd_divisions", "sd_members",
                      "member_aliases", "sd_events", "sd_bills",
                      "sd_committees"],
    "NI Assembly weekly": ["ni_items", "ni_divisions", "ni_members",
                           "ni_committees"],
    # eu_judgments is deliberately ABSENT, for the same reason the German
    # once-ever tables are: PIPELINE_FEEDS drives the CLOBBER check -- a
    # pipeline that ran but whose data is stale -- and a table written once
    # per item cannot pass it during a quiet month. Listed here it reported
    # "LOST WORK" for eleven days while nothing was lost and the Strasbourg
    # court had simply not ruled on our issues since 16 July.
    "EU weekly": ["eu_agenda", "eu_texts", "eu_pqs", "eu_cmte_docs",
                  "eu_ecis", "eu_consultations", "eu_meps",
                  "eu_cmte_meetings"],
    # de_vorgaenge only: PIPELINE_FEEDS drives the CLOBBER check (a pipeline
    # that ran but whose data is stale), and the other three German tables
    # legitimately never move -- the Bundestag takes recorded votes in
    # bursts, so listing them here would cry clobber every quiet month.
    "Germany weekly": ["de_vorgaenge", "de_agenda", "de_petitions",
                       "de_petition_snapshots", "de_judgments",
                       "de_amendments", "de_committee_reports"],
    "UPR monthly": ["upr_recommendations"],
    # "EU day sweep" is deliberately absent. PIPELINE_FEEDS drives the clobber
    # check -- a pipeline that ran but whose data is stale -- and the EP sits in
    # blocks with weeks of recess between them, so its feeds age legitimately
    # and every recess would raise a false alarm. Its heartbeat in PIPELINES is
    # the honest signal: the workflow runs nightly even when nothing sat.
    "Member profiles": ["dv_post", "dv_contact"],
    "Day sweep": ["sweep_log"],
    # The three that move every run whatever Parliament did; petitions and
    # the Gazette can legitimately be quiet, which would cry clobber.
    "Canada weekly": ["ca_divisions", "ca_bills", "ca_members"],
    # Divisions are left out: new rows only, so a recess week cannot move them.
    "US weekly": ["us_bills", "us_members", "us_schedule_weeks", "us_schedule",
                  "us_fr_documents", "us_court_cases"],
    # Divisions left out for the same reason as the US: a recess week cannot move them.
    "Australia weekly": ["au_bills", "au_members"],
    # All three are re-read whole and re-stamped every run (see FEEDS).
    "Ireland weekly": ["ie_members", "ie_bills", "ie_divisions"],
    # Divisions left out for the same reason: a recess week cannot move them.
    "Austria weekly": ["at_items", "at_members"],
    # Re-read whole every run; votes are left out for the US's reason.
    "Netherlands weekly": ["nl_members", "nl_fracties"],
    "Poland weekly": ["pl_processes", "pl_members"],
    # Divisions left out for the same reason as the US: a recess week cannot move them.
    "Italy weekly": ["it_bills", "it_members"],
    # The two Swiss tables re-read whole every run; divisions move only in session.
    "Switzerland weekly": ["ch_members", "ch_sessions"],
    # Divisions left out for the same reason as the US: a recess week cannot move them.
    "Belgium weekly": ["be_dossiers", "be_members"],
    # Divisions left out for the same reason as the US: a recess week cannot move them.
    "France weekly": ["fr_dossiers", "fr_members"],
    # All three are re-stamped on every run (the whole legislature is re-read).
    "Portugal weekly": ["pt_initiatives", "pt_divisions", "pt_members"],
    # The two provincial tables re-stamped on every run; prov_divisions is
    # write-once in practice (ONCE_EVER) and cannot support this check.
    "Provinces weekly": ["prov_members", "prov_bills"],
}

# A pipeline that has never run yet: its tables exist (db.init_db creates
# every table in db.TABLES) but are empty, and an empty watched table is a
# fault -- except here, and only until the pipeline's first heartbeat. The
# excuse expires by itself: once source_runs holds the pipeline, an empty
# table is OVERDUE again, so this entry can never hide a later wipe.
AWAITING_FIRST_RUN = {
    "Ireland weekly": (("ie_members", "ie_bills", "ie_divisions"),
                       "scheduled 9 October 2026; its tables fill on its first run"),
    "US weekly": (("us_bills", "us_members", "us_divisions"),
                  "scheduled 9 October 2026; its tables fill on its first run"),
    "Australia weekly": (("au_members", "au_bills", "au_divisions"),
                         "scheduled 9 October 2026; its tables fill on its first run"),
    "Austria weekly": (("at_items", "at_members", "at_divisions"),
                       "scheduled 9 October 2026; its tables fill on its first run"),
    "Netherlands weekly": (("nl_members", "nl_fracties", "nl_divisions"),
                           "scheduled 9 October 2026; its tables fill on its first run"),
    "Poland weekly": (("pl_members", "pl_processes", "pl_divisions"),
                      "scheduled 9 October 2026; its tables fill on its first run"),
    "Italy weekly": (("it_members", "it_bills", "it_divisions"),
                     "scheduled 9 October 2026; its tables fill on its first run"),
    "Switzerland weekly": (("ch_members", "ch_sessions", "ch_businesses", "ch_divisions"),
                           "scheduled 9 October 2026; its tables fill on its first run"),
    "Belgium weekly": (("be_members", "be_dossiers", "be_divisions"),
                       "scheduled 9 October 2026; its tables fill on its first run"),
    "France weekly": (("fr_dossiers", "fr_members", "fr_divisions"),
                      "scheduled 9 October 2026; its tables fill on its first run"),
    "Portugal weekly": (("pt_members", "pt_initiatives", "pt_divisions"),
                        "scheduled 9 October 2026; its tables fill on its first run"),
    "Provinces weekly": (("prov_members", "prov_bills", "prov_divisions", "prov_sittings"),
                         "scheduled 3 October 2026; its tables fill on its first run"),
    # A STEP heartbeat, as "Provinces speeches" below: tools/us_schedule.py
    # stamps "US schedule" at the end of every stored run. Keyed on the step,
    # not on "US weekly", whose heartbeat already exists and would leave
    # these new tables crying wipe until the step first ran.
    "US schedule": (("us_schedule", "us_meetings", "us_schedule_weeks"),
                    "week-ahead step added to US weekly 9 October 2026; its tables "
                    "fill on the step's first run"),
    # A STEP heartbeat, not a workflow's: tools/prov_speeches.py stamps
    # "Provinces speeches" into source_runs at the end of every stored run.
    # Keyed on the workflow it would have expired at the first vote backfill
    # dispatch, which runs no speeches step, and the empty speech tables
    # would have cried wipe until the next Wednesday. Once the step has run,
    # an empty table here is a wipe again.
    # STEP heartbeats, as for Provinces speeches: tools/us_federal_register.py
    # and tools/us_courts.py stamp their own source_runs rows, so the new US
    # tables are excused only until their own step has run once -- the US
    # weekly itself had run before they existed.
    "US Federal Register": (("us_fr_documents",),
                            "executive actions added to US weekly 9 October 2026; "
                            "the table fills on the step's first run"),
    "US Supreme Court": (("us_court_cases", "us_court_orders"),
                         "Supreme Court added to US weekly 9 October 2026; "
                         "its tables fill on the step's first run"),
    "Provinces speeches": (("prov_speeches", "prov_speech_sittings"),
                           "Hansard speeches step added to Provinces weekly 2 October 2026; "
                           "its tables fill on the step's first run"),
}

# Tables carrying a sighting column that are DELIBERATELY not watched,
# each with its reason. The structural test allows only what is declared
# here, so a new source cannot arrive unwatched AND unexplained -- which
# is exactly how EU weekly stayed off the failure alert from the day it
# was written, and how Member profiles was missing from this file.
EXEMPT = {}

# Workflows that write the store but run ONLY when a human dispatches
# them. They cannot "stop dead" -- there is no cadence to miss -- so they
# get no heartbeat expectation. They still stamp one when they run, which
# is what makes the clobber check work for them too.
ON_DEMAND = {
    "Historic backfill": "workflow_dispatch only: a sweep run by hand "
                         "when the taxonomy or the cutoff changes.",
    "Score stance": "workflow_dispatch only: scores outstanding refs "
                    "when someone asks for it.",
    "Germany backfill": "workflow_dispatch only: the one-off read of Bundestag "
                        "protocols and votes back to 2020, then its judging in "
                        "bounded chunks; re-dispatched until the queue is empty.",
}

# Written once per item and never re-stamped, so an old date means "no new
# items", not "the feed died". Reported, never failed.
# MEASURED, not assumed: each of these was checked for whether its
# writer re-stamps last_seen on every sighting (ON CONFLICT ... SET
# last_seen=excluded.last_seen) or only writes new rows. A table that
# only gains rows goes quiet in recess through no fault of anyone, and
# alarming on it would train people to ignore the alert.
ONCE_EVER = {
    # 8 October 2026, MEASURED: the Sunday pull writes sections only for the
    # sitting days of the week just ended (run_weekly.sweep_hansard_sections),
    # so both Houses in conference recess means no rows, and it failed the
    # coverage watch daily from 5 Oct while the Sunday pull ran green.
    "hansard_sections": "one row per section of a sitting day; quiet in recess",
    # Canada: senators are written only when a Senate vote ON OUR GROUND is
    # fetched, and sittings once each -- both only gain rows, and both go
    # quiet in recess.
    "ca_senators": "written only when a Senate vote on our ground is fetched",
    "ca_sittings": "one row per Hansard sitting read, stored once",
    # read_at is when the ISSUE was read, one row per issue: a write-once
    # table, not a sighting column the cadence check may use (RecessTests).
    "ca_gazette_issues": "one row per Gazette issue read, stored once",
    # 3 October 2026: Senate debates and committee evidence. One row per
    # sitting or meeting read, stored once; testimony one row per witness
    # intervention on our ground. All quiet in recess.
    "ca_senate_sittings": "one row per Senate sitting read, stored once",
    "ca_committee_meetings": "one row per committee meeting read, stored once",
    "ca_testimony": "one row per witness intervention on our ground, stored once",
    "ca_leave": "one row per leave-to-appeal decision, written once",
    # One row per Supreme Court order PDF read; an order list is final, so
    # it is read once and never re-stamped.
    "us_court_orders": "one row per Supreme Court order PDF read, stored once",
    # Canada's provinces (3 October 2026), MEASURED: store_division re-stamps
    # last_seen only when its sitting record is read again (a clean one never
    # is) or when a bill page naming a voice decision is re-read, so the table
    # gains rows in sitting weeks and goes quiet in recess.
    "prov_divisions": "re-stamped only when its record, or a bill page naming a "
                      "voice decision, is read again: quiet in recess",
    "prov_sittings": "one row per provincial sitting record read; a clean record "
                     "is never read again",
    # Provincial Hansard speeches (2 October 2026): one row per Hansard day
    # read, stored once (read_at is when it was read, not a sighting), and
    # speeches on our ground written once per day read. Quiet in recess.
    "prov_speech_sittings": "one row per provincial Hansard day read for speeches, stored once",
    "prov_speeches": "speeches on our ground, written once per Hansard day read",
    "items": "new rows only: PQs, SIs, consultations and what's on are "
             "inserted when they appear and not re-stamped",
    "sp_affiliations": "new rows only: an MSP's committee places",
    "ni_agenda": "new rows only: the forward Order Paper",
    "ni_votes": "new rows only: a member-vote is stored once",
    "ni_affiliations": "new rows only: an MLA's committee places",
    "ni_sittings": "one row per sitting date, archived once",
    "ni_sponsors": "fetched once per motion",
    "eu_speeches": "one row per speech, stored once",
    "eu_divisions": "one row per roll call, stored once",
    # MEASURED 23 September 2026, after eleven days of "LOST WORK" that was
    # no such thing. tools/eu_courts.py builds `known` from the stored item
    # ids and SKIPS anything already held, so a judgment is written once and
    # its last_seen never moves again -- the table can only ever look stale.
    #
    # The alarm was NOT simply silenced: HUDOC was probed first, because
    # "the court is quiet" and "the query broke" produce an identical empty
    # result. It answers, and it still returns 1 judgment since January, 21
    # since 2024 and 50 since 2015 -- so the search works and the Strasbourg
    # court has genuinely issued nothing on our terms since 16 July.
    "eu_judgments": "new rows only: eu_courts.py skips item ids it already "
                    "holds, so last_seen never moves; a court is quiet for "
                    "months at a time and that is not a failure",
    "eu_dossiers": "hand-curated watchlist",
    # GERMANY (promoted out of EXEMPT on 22 September 2026, when
    # de-weekly.yml started pushing the store). Each placement was checked
    # against its writer rather than guessed:
    "de_documents": "new rows only: INSERT OR IGNORE, so a Drucksache is "
                    "stored once and never re-stamped",
    "de_divisions": "new rows only in practice: tools/de_rollcalls.py skips "
                    "polls it already holds, and the Bundestag votes in "
                    "bursts -- 68 in sixteen months",
    "de_members": "re-stamped only when a recorded vote is collected, which "
                  "is itself a burst",
    "de_affiliations": "new rows only: a member's committee seats, written "
                       "when they are first profiled and re-stamped only "
                       "when a seat changes",
    "de_speeches": "new rows only: a Stenografischer Bericht is final and is "
                   "read once, and the Bundestag sits in blocks with months "
                   "of recess between them",
    "de_mdb": "the Bundestag's own register of every member since 1949, "
               "loaded on demand from MdB-Stammdaten.zip. It is not in any "
               "workflow: the file is republished a few times a year (the "
               "copy read on 26 September 2026 was stamped 29 April), and a "
               "register that reaches back to 1949 does not go stale in a "
               "week. Re-run tools/de_stammdaten.py after a general election",
    "de_authorship": "who put their name to a Bundestag paper on our ground, "
                     "for the German 5CA (tools/de_authorship.py). Run on "
                     "demand, per area, before a sheet is regenerated: DIP's "
                     "authors are fixed once a Drucksache is printed, so "
                     "rows are re-stamped only when a run happens",
    "un_votes": "UN pipeline is paused",
    "un_documents": "UN pipeline is paused",
    "un_calendar": "UN pipeline is paused",
}


def age_of(conn, table, col, today):
    try:
        row = conn.execute("SELECT MAX({0}) FROM {1}".format(col, table)
                           ).fetchone()
    except sqlite3.Error:
        return None, None
    val = (row[0] or "")[:10] if row else ""
    try:
        return val, (today - datetime.date.fromisoformat(val)).days
    except ValueError:
        return val or None, None


def table_exists(conn, table):
    """A table this store has never carried is a schema gap, not a data loss:
    init_db creates every one in production, so this only separates a real
    emptying from a fixture or a store that predates the table."""
    try:
        row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' "
                           "AND name = ?", (table,)).fetchone()
    except sqlite3.Error:
        return False
    return bool(row)


def awaiting_first_run(table, seen):
    """The reason an EMPTY table is excused, or None: only while the pipeline
    that fills it has never stamped a heartbeat (AWAITING_FIRST_RUN)."""
    for pipeline, (tables, why) in AWAITING_FIRST_RUN.items():
        if table in tables and pipeline not in seen:
            return "{0}: {1}".format(pipeline, why)
    return None


def check(conn, today=None, log=print, quiet=False, found=None):
    """The overdue lines, for a human. `found`, if given, also receives one
    (key, age) per problem: a stable key, so --state can tell a problem it
    has reported from a new one, and its age in days (None when it has none)."""
    today = today or datetime.date.today()
    overdue = []
    found = found if found is not None else []

    def flag(key, age, text):
        overdue.append(text)
        found.append((key, age))

    log("PIPELINES  (did the workflow run at all?)")
    seen = {}
    try:
        for r in conn.execute("SELECT source, last_run FROM source_runs"):
            seen[r[0]] = r[1]
    except sqlite3.Error:
        log("  no heartbeat table yet: every workflow stamps one on its "
            "next successful push (tools/db_state.py).")
    for name, (days, grace, why) in sorted(PIPELINES.items()):
        last = seen.get(name)
        if not last:
            log("  {0:<20} NO HEARTBEAT YET   {1}".format(name, why))
            continue
        try:
            age = (today - datetime.date.fromisoformat(last)).days
        except ValueError:
            continue
        late = age > days + grace
        if late:
            flag("pipeline:" + name, age,
                 "{0} last published {1} days ago (expected every "
                 "{2})".format(name, age, days))
        if late or not quiet:
            log("  {0:<20} {1:>3} days ago{2}   {3}".format(
                name, age, "  <-- OVERDUE" if late else "", why))
    for name, why in sorted(PAUSED.items()):
        if not quiet:
            log("  {0:<20} PAUSED   {1}".format(name, why[:60]))

    if not quiet:
        log("")
    log("FEEDS  (is the source still answering?)")
    for table, col, days, grace, why in FEEDS:
        val, age = age_of(conn, table, col, today)
        if age is None:
            # AN EMPTY WATCHED FEED IS A FAULT, NOT SILENCE (17 Sept 2026).
            # This printed "NO DATA" and moved on, so it read the same whether
            # a feed had never been populated or had just lost every row. Five
            # EU tables were emptied by the 9 Sept store rebuild -- 21 plenary
            # divisions, the adopted texts, the consultations -- and the watch
            # that exists to catch exactly that said nothing for eight days
            # while the EU weekly was also being cancelled. A feed is listed
            # here because we expect rows in it; if it has none, say so loudly
            # and put it in ALLOWED_EMPTY with a reason once a human agrees.
            if not table_exists(conn, table):
                log("  {0:<22} NO TABLE   {1}".format(table, why))
                continue
            reason = ALLOWED_EMPTY.get(table)
            if reason:
                if not quiet:
                    log("  {0:<22} EMPTY BY DESIGN   {1}".format(table, reason))
                continue
            waiting = awaiting_first_run(table, seen)
            if waiting:
                if not quiet:
                    log("  {0:<22} AWAITING FIRST RUN   {1}".format(table, waiting))
                continue
            flag("empty:" + table, None,
                 "{0} holds NO ROWS AT ALL; it is watched because we "
                 "expect data in it ({1})".format(table, why))
            log("  {0:<22} NO ROWS AT ALL  <-- OVERDUE   {1}".format(table, why))
            continue
        late = age > days + grace
        if late:
            flag("feed:" + table, age,
                 "{0} last saw data {1} days ago (expected every "
                 "{2})".format(table, age, days))
        if late or not quiet:
            log("  {0:<22} {1:>3} days ago{2}   {3}".format(
                table, age, "  <-- OVERDUE" if late else "", why))
    # THE CLOBBER CHECK. A pipeline whose own heartbeat is fresh but
    # whose data is old either stored nothing or had its store
    # overwritten. Both are silent, and both are invisible to a
    # cadence test on either signal alone.
    if not quiet:
        log("")
    log("RAN BUT DID NOT LAND  (fresh pipeline, stale data)")
    flagged = False
    for name, tables in sorted(PIPELINE_FEEDS.items()):
        last = seen.get(name)
        if not last:
            continue
        try:
            pipe_age = (today - datetime.date.fromisoformat(last)).days
        except ValueError:
            continue
        cadence = PIPELINES.get(name, (7, 3, ""))[0]
        if pipe_age > cadence:
            continue          # it is simply overdue; reported above
        for table in tables:
            col = next((c for c, _d, _g, _n in
                        [(f[1], f[2], f[3], f[4]) for f in FEEDS
                         if f[0] == table]), "last_seen")
            _val, age = age_of(conn, table, col, today)
            # A week of slack: a feed legitimately quiet for a few days
            # inside a pipeline that ran is normal; a month is not.
            if age is not None and age > pipe_age + 7:
                flagged = True
                flag("lost:{0}:{1}".format(name, table), age,
                     "{0} ran {1} days ago but {2} has not refreshed in {3} "
                     "-- it stored nothing, or its store was overwritten"
                     .format(name, pipe_age, table, age))
                log("  {0:<20} ran {1}d ago, {2} is {3}d old   <-- LOST WORK"
                    .format(name, pipe_age, table, age))
    if not flagged:
        log("  nothing: every pipeline that ran has data as fresh as its run.")

    if not quiet:
        log("")
        log("WRITTEN ONCE PER ITEM  (an old date here means no new items)")
    # Reported even in quiet mode, because the ONE thing a write-once feed can
    # tell you is fatal: it holds nothing. A quiet month is why these are not
    # cadence-checked; an EMPTY table is not a quiet month, it is a wipe. The
    # 9 Sept store rebuild emptied eu_divisions of 21 plenary roll calls, and
    # this section printed "? days ago" beside it for eight days.
    for table, why in sorted(ONCE_EVER.items()):
        if table in PAUSED_TABLES:
            continue
        if not table_exists(conn, table):
            continue
        cols = [c[1] for c in conn.execute(
            "PRAGMA table_info({0})".format(table))]
        col = next((c for c in ("last_seen", "captured_at") if c in cols), None)
        val, age = age_of(conn, table, col, today) if col else (None, None)
        empty = conn.execute("SELECT COUNT(*) FROM {0}".format(table)).fetchone()[0] == 0
        waiting = awaiting_first_run(table, seen) if empty else None
        if waiting:
            if not quiet:
                log("  {0:<22} AWAITING FIRST RUN   {1}".format(table, waiting))
        elif empty and table not in ALLOWED_EMPTY:
            flag("empty:" + table, None,
                 "{0} is written once per item and holds NO ROWS AT "
                 "ALL: every row it had is gone ({1})".format(table, why))
            log("  {0:<22} NO ROWS AT ALL  <-- OVERDUE   {1}".format(table, why))
        elif not quiet:
            log("  {0:<22} {1:>3} days ago   {2}".format(
                table, age if age is not None else "?", why))
    return overdue


# --state: SAY A PROBLEM ONCE (docs/mac-mini-runner.md, step 5). Until
# 9 October 2026 this exited 1 every day an overdue source stayed overdue,
# so the same DM arrived daily and was learned to be ignored -- the failure
# mode the Monday retry-slot fix (tests/test_db_state.py) was written against.
# With --state it fails only for a problem it has not reported, or one that
# has grown a week (ESCALATE days) since it last said so: NI 12 days overdue
# is said at 12 and again at 19, not at 13, 14, 15. The daily health summary
# (tools/health_summary.py) still lists every overdue source, every day.
ESCALATE = 7


def triage(found, state, today):
    """(new, worse, known, resolved, next_state) for this run's problems.

    found: [(key, age)] from check(). state: {key: {"first", "reported_age",
    "reported"}} from the last run. A problem with no age (an emptied table)
    never grows, so it is said once until it clears.
    """
    today_s = today.isoformat()
    new, worse, known, nxt = [], [], [], {}
    for key, age in found:
        was = state.get(key)
        if was is None:
            new.append(key)
            nxt[key] = {"first": today_s, "reported_age": age, "reported": today_s}
        elif age is not None and was.get("reported_age") is not None \
                and age >= was["reported_age"] + ESCALATE:
            worse.append(key)
            nxt[key] = dict(was, reported_age=age, reported=today_s)
        else:
            known.append(key)
            nxt[key] = was
    resolved = sorted(k for k in state if k not in nxt)
    return new, worse, known, resolved, nxt


def load_state(path):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {}


def save_state(path, state):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2, sort_keys=True)
        handle.write("\n")


def _arg(name):
    if name in sys.argv:
        i = sys.argv.index(name)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return None


def main():
    quiet = "--quiet" in sys.argv
    state_path = _arg("--state")
    conn = sqlite3.connect(os.path.join(ROOT, "data", "parl-monitor.db"))
    found = []
    overdue = check(conn, quiet=quiet, found=found)
    stamped = set()
    if conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND "
                    "name='source_runs'").fetchone():
        stamped = {r[0] for r in conn.execute("SELECT source FROM source_runs")}
    conn.close()
    print("")
    if overdue:
        # LOUD, and non-zero: this workflow is watched by the failure
        # alert, so an overdue source becomes a DM rather than a line in a
        # log nobody opens.
        print("{0} SOURCE(S) OVERDUE:".format(len(overdue)))
        for line in overdue:
            print("  * {0}".format(line))
        if state_path:
            return report_against_state(found, overdue, state_path)
        return 1
    if state_path:
        _new, _worse, _known, resolved, nxt = triage([], load_state(state_path),
                                                     datetime.date.today())
        if resolved:
            print("Cleared since last run: {0}".format(", ".join(resolved)))
        save_state(state_path, nxt)
    missing = sorted(n for n in PIPELINES if n not in stamped)
    if missing:
        print("Feeds are within cadence. {0} pipeline(s) have not stamped a "
              "heartbeat yet, so whether they RAN is still unknown: {1}"
              .format(len(missing), ", ".join(missing)))
        return 0
    print("Every pipeline and feed is within its expected cadence.")
    return 0


def report_against_state(found, overdue, state_path):
    """Exit 1 only for what is new or a week worse; save what was said."""
    new, worse, known, resolved, nxt = triage(
        found, load_state(state_path), datetime.date.today())
    text = dict((k, line) for (k, _a), line in zip(found, overdue))
    print("")
    for label, keys in (("NEW", new), ("WORSE", worse)):
        for key in keys:
            print("  {0}: {1}".format(label, text[key]))
    if known:
        print("  {0} already reported and no worse (listed in the daily "
              "health summary).".format(len(known)))
    if resolved:
        print("  Cleared since last run: {0}".format(", ".join(resolved)))
    save_state(state_path, nxt)
    return 1 if (new or worse) else 0


if __name__ == "__main__":
    sys.exit(main())
