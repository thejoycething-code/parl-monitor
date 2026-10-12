---
name: debate-day-net
description: Every weekday at 16:45 run tools/debate_watch.py net: flag in config/debate_watch.yaml any debate on our ground that Hansard already shows with 8+ speakers and no watch covers, commit and push the file; then run tools/country_debate_today.py --all for the new countries that publish the same day (NL, CH, FR, BE); DM Christopher one line only when something was flagged or a country has a key debate. Nothing: stop silently.
---

You are working in the CitizenGO UK Parliamentary Monitor repo at /Users/chrisjoyce/parl-monitor (private GitHub repo thejoycething-code/parl-monitor). Christopher (cjoyce@citizengo.net; Slack DM recipient configured in config/secrets.yaml as slack_dm_user_id) set this up on 17 September 2026 as the SAME-DAY NET for the standing evening task "Debate day" (18:30 weekdays), which packs only the debates flagged in config/debate_watch.yaml. This task's one job is to flag, by 17:00, a debate on our ground that nobody saw coming: an urgent question that grew, a statement that became a debate, a Westminster Hall day the week-ahead did not name. Read docs/debate-pack-social.md ("The standing evening task", the Flagging paragraphs) if anything is unclear. Today's date is the London date when this runs.

STANDING RULES. Never post to any Slack channel: Slack contact is a DM to Christopher only, sent with publish.slack_dm (python3 -c "import sys; sys.path.insert(0,'.'); from src import publish; publish.slack_dm(publish.load_secrets(), open('/tmp/dm.txt').read())"). Never build a pack, never run debate_pack.py, pick_speeches.py, social_cut.py, speech_cut.py or debate_report.py: the evening task does that. Never touch data/parl-monitor.db, never run db_state.py or raw_state.py. Never print or paste config/secrets.yaml, config/google-service-account.json or any secret. Never invent a parliamentarian's name. No Anthropic API spend at all: the net reads Hansard titles and speaker counts only. Write any git commit message to a file and commit with -F (quotes in -m broke the shell on 9 Sept). If a tool refuses or fails, do not work around it by hand: DM one line saying what failed and stop.

STEP 1. From the repo root:
  cd /Users/chrisjoyce/parl-monitor && git pull -q --rebase --autostash origin main && python3 tools/debate_watch.py net
The tool prints ONE line starting "NET:".
- "NET: nothing to flag for <date> ..." : no commit; go to STEP 1B.
- If Hansard has no sections yet for today (the tool may say so, or list 0 on our ground on a sitting day): the same, go to STEP 1B. The Houses may not be sitting; that is normal.
- "NET: flagged N for <date>: ..." : do STEP 1B, then STEP 2.

STEP 1B (added 10 October 2026: the new countries). From the repo root:
  python3 tools/country_debate_today.py --all --quiet
It reads the Netherlands, Switzerland, France and Belgium (the countries whose chamber publishes the day's speeches the same day; docs/debate-pack-social.md, "New countries") into a throwaway in-memory store: it never writes data/parl-monitor.db and only reads it. It prints one block per country, each ending in a line "KEY DEBATE: <cc> | ...". Keep only the KEY DEBATE lines that are not "| none" (a "none (agenda names a watched point: ...)" line counts too: keep it). A "[gap]" line means a source did not answer: mention it in the DM only if you are sending one anyway. Never run tools/country_live_debate.py here and never name what any member said or how they voted: that is a manual step.
If the NET found nothing AND no country has a key debate: STOP. No DM.

STEP 2. Commit and push the watch file so the evening task (which pulls before it reads) and the record have it:
  printf 'Debate watch: same-day net flagged %s (%s)\n\nCo-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>\n' "<the flagged titles, comma-separated>" "<today>" > /tmp/msg.txt
  git add config/debate_watch.yaml && git commit -q -F /tmp/msg.txt
  for i in 1 2 3; do git pull -q --rebase --autostash origin main && git push -q origin main && break; sleep 5; done
If the push fails, leave the commit local and say so in the DM; the evening task runs on this same Mac and reads the file directly.

STEP 3. DM Christopher, plain text, under 900 characters. If the NET flagged something: ONE line with the NET line's content (house, title, speakers so far for each flagged debate), that the 18:30 Debate day task will pack it if Hansard shows it with 8 or more speakers by then, and "remove with: python3 tools/debate_watch.py remove <today> \"<title>\"" if he does not want it. Then, for each country with a key debate, ONE line: "<country>: <title> (<N> speakers on our ground so far); live read: python3 tools/country_live_debate.py <cc> --debate <id>". End.