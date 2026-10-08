---
name: tia-second-reading-debate-pack
description: Every weekday evening read config/debate_watch.yaml; on a flagged day, confirm Hansard has the debate and build the debate pack, the provisional reel sequence, the provisional report (approval DM), the vertical reels and the subtitled 16:9 full speeches, and DM Christopher. Unflagged days end at once with no Hansard or store access.
---

You are working in the CitizenGO UK Parliamentary Monitor repo at /Users/chrisjoyce/parl-monitor (private GitHub repo thejoycething-code/parl-monitor). Christopher (cjoyce@citizengo.net; Slack DM recipient configured in config/secrets.yaml as slack_dm_user_id) set this up as a STANDING weekday task on 12 September 2026 and, on 14 September, made it run only on FLAGGED days: "I'm not sure we need the daily pulls unless we flag something coming up in the week we want a pack on." Read docs/debate-pack-social.md ("Order of work", "Re-cutting one speaker" and "The standing evening task") and docs/debate-article-brief.md first: they are the defaults you must follow. Today's date is the London date when this runs.

STANDING RULES. Never post to any Slack channel: Slack contact is a DM to Christopher only, sent with publish.slack_dm (python3 -c "import sys; sys.path.insert(0,'.'); from src import publish; publish.slack_dm(publish.load_secrets(), open('/tmp/dm.txt').read())"). NEVER run tools/debate_report.py with --publish or --with-clips: publishing is Christopher's act after he has read the draft (--preview, which shares a canvas with him alone, is allowed). Never run tools/drive_pack.py: footage goes to Drive when Christopher publishes. Never print or paste config/google-service-account.json or any secret. Never invent a parliamentarian's name or words. Do not fill in checklist.md: ONSIDE is Christopher's decision, or the division's lobbies (STEP 3); the tools draft from the stance pass's reading and mark everything PROVISIONAL, which is intended. Footage is Parliament's under the Parliamentary Recording Unit's terms; the tools fetch only parliamentlive.tv segments; never fetch the whole sitting. Expected API cost when a pack is built: the stance read (about one Anthropic call per twenty speakers), the selector (a few calls, batches of eight) and one report call; all usual and allowed; run nothing else that spends. On an unflagged day the cost is zero. Write any git commit message to a file and commit with -F (quotes in -m broke the shell on 9 Sept). If a tool refuses or fails, do not force it or work around it by hand: record what happened and tell Christopher in the DM. One pack, one process: if a pack folder for today already has a .lock, or ps shows another speech_cut/social_cut/pick_speeches on it, stop and DM one line saying so.

STEP 0, IS TODAY FLAGGED? From the repo root, with NO network and NO store access:
  cd /Users/chrisjoyce/parl-monitor && git pull -q --rebase --autostash origin main && python3 tools/debate_watch.py today
- If it prints "no watch today": STOP. Nothing else. No DM, no Hansard, no store, no commit.
- If it prints one or more "WATCH: <house> | <term> | area <A> | <note>" lines: for each (the Commons one first if there are two), continue with house H, title phrase T and area A. A line may end "| min N": then N replaces the fifteen-speaker floor in STEP 1 for that watch (bill committees seat about seventeen members, so their watches carry min 8). Watches are flagged by a person, by Monday's week-ahead pass, by a bill's stage sittings or by the 16:45 same-day net; the note says which. Treat them all the same.

STEP 1, HAS HANSARD PUBLISHED IT? Run:
  python3 tools/debate_today.py
and find T in its listing (the "KEY DEBATE" line or a listed row; a bill committee's sitting is titled "<Bill> (Nth sitting)" and there may be two on one day: pack each that clears the floor, the morning one first). Note the ext id X, the speaker count and the "last heard" clock.
- If the debate is listed with 15 or more speakers (or N or more, when the WATCH line carries "min N"): continue.
- If it is listed with fewer than that floor: DM Christopher one line (house, title, speakers so far, last heard) saying the flagged debate looks small or unfinished and giving the by-hand command (python3 tools/debate_pack.py --date <today> --debate X --house H), then STOP.
- If it is not listed, or debate_today exits 2 (no sections yet) and it is before 21:00 London: create ONE new one-time scheduled task (the scheduled-tasks connector, fireAt 90 minutes from now, taskId debate-day-retry-<HHMM>, this same prompt verbatim) and stop. After 21:00: DM one line saying Hansard had not published the flagged debate by 21:00 and it must be packed by hand tomorrow, and stop.
Hansard publishes a long debate in parts: if the pack (STEP 3) has clearly fewer speakers than debate_today reported, or speeches.md has no closing speeches (no Minister, no winding-up), treat it as INCOMPLETE: delete the pack folder (rm -rf F), push nothing, and retry as above.

STEP 2, STORE SEQUENCING (one writer at a time). The pack build and the report record their spend in data/parl-monitor.db, so before STEP 3 run:
  set -o pipefail; python3 tools/db_state.py --pull && python3 tools/raw_state.py --pull
Never pipe db_state into tail or head. If db_state prints "SHA MISMATCH" or "THE STORE MOVED UNDER YOU" or exits non-zero, ABORT: DM Christopher one line saying the store pull failed and quoting the tool's first line, and stop.

STEP 3, the pack:
  python3 tools/debate_pack.py --date <today> --debate X --house H
It creates data/packs/<today>-<slug>/ with roundup.md, checklist.md (blank ONSIDE lines), speeches.md, quotes.md, shotlist.csv, pack.json (with the day's divisions, if any). Note the folder path F.

STEP 4, the checklist from the vote, when the debate ended in a division. pack.json "divisions" lists them with the question put. If a division decided the question (a Second or Third Reading, a Lords amendment, a new clause), and config/vote_tracker.yaml already lists that division id with our_side, run:
  python3 tools/debate_pack.py --pack F --apply --from-vote <division id>
If the tracker does not list it, DO NOT guess our side: leave the checklist blank and put the division in the DM with its result exactly as pack.json records it, so Christopher can add and sign it (our side is verified against the mover's own vote, never read off the title). If there was no division, leave the checklist blank.

STEP 5, the selector and the provisional sequence:
  python3 tools/pick_speeches.py --pack F --top 8 --write-sequence
It ranks the onside speeches (confirmed, or the pass read standing in) for campaign value in batches of eight, verifies each passage verbatim, and writes F/selection.md and F/sequence.md (PROVISIONAL when the checklist is blank). If it refuses (no onside speeches, or an empty selection), run python3 tools/social_cut.py --pack F --draft instead and note it.

STEP 6, the provisional report:
  python3 tools/debate_report.py --pack F --provisional
(without --provisional when STEP 4 filled the checklist from a vote). It writes F/report.md, F/social.md, F/report.json, runs its checks and sends Christopher the approval DM itself. If it errors, note the message; retry once at most.

STEP 7, publish the store and commit the pack BEFORE the long footage steps:
  set -o pipefail; python3 tools/db_state.py --push && python3 tools/raw_state.py --push
  git add data/parl-monitor.db.json data/raw.json F/*.md F/*.csv F/*.json
(never anything under F/clips). Commit "Debate pack: <T> (<today>): roundup, selection, provisional report" with the trailer "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>", then for i in 1 2 3; do git pull -q --rebase --autostash origin main && git push -q origin main && break; sleep 5; done. If db_state --push refuses, do not force it (no --accept-loss, no --force): say so in the DM. If git push fails, leave the commit local and say so.

STEP 8, footage (CPU only, no API spend; an hour or more; let it run):
  python3 tools/social_cut.py --pack F
  python3 tools/speech_cut.py --pack F
Both start with the footage clock self-check and stop if it fails (say so in the DM; do not override). social_cut renders the vertical reel from sequence.md; speech_cut cuts each sequence speaker's whole speech as one subtitled 16:9 clip (interventions merged). Do NOT pass --all. Afterwards git add F/social-cut.md F/speeches-cut.md F/selection.md (whichever exist), commit "Debate pack: <T>: provisional reels and full speeches" with the same trailer, and push as in STEP 7.

STEP 9, the closing DM to Christopher (DM only, plain text, under 1,500 characters; do not quote MPs beyond their names):
- house, title, the Hansard link (https://hansard.parliament.uk/<H>/<today>/debates/X/), speakers, and the watch note;
- how many speakers the pass read as with us, against and unclear (roundup.md), naming those with us;
- the sequence: how many speakers, provisional or from the vote;
- the report: that its approval DM was sent (or the error) and how many checks failed;
- reels and full speeches: how many rendered, total minutes, F/clips/final/, any whose trim fell back to Hansard time (F/speeches-cut.md), or the clock-check failure;
- any division: result exactly as pack.json records it and whether the tracker already lists it; if not, that it needs adding under the right issue and signing off before Monday's run;
- what he does next: 1) fill ONSIDE in F/checklist.md if no vote filled it, then python3 tools/debate_pack.py --pack F --apply; 2) re-run pick_speeches if the onside list changed, review F/sequence.md; 3) python3 tools/debate_report.py --pack F, then --preview; 4) only then --publish --with-clips, which puts the footage on Drive and posts the canvas;
- anything that failed, one line each.
End.