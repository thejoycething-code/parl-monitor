#!/bin/bash
# The government documents step of a country weekly (16 October 2026): the
# country's government consultations and publications on our ground,
# tools/country_gov_docs.py (src/gov_docs.py, src/gov_doc_sources/<cc>.py),
# read into gov_docs after the collector and the petitions step and before
# the edition, so the countdown's DEADLINE rows are this week's.
#
#     bash tools/gov_docs_step.sh <cc>
#
# FAILING LOUD, NEVER FATAL. Each source that failed or answered with
# nothing parsable is a [gap] line and a gaps row ('<cc>-govdocs-<source>'),
# and its gov_doc_runs row says ok=0 (the coverage line names it). The step
# itself never costs the store, the edition or the publish.
cc="${1:?usage: gov_docs_step.sh <cc>}"
rc=0
python3 tools/country_gov_docs.py "$cc" || rc=$?
case "$rc" in
  0) ;;
  3) echo "  [gap] ${cc}-govdocs: read with gaps (see the [gap] lines above); what was read is stored" ;;
  *) echo "  [gap] ${cc}-govdocs exited ${rc}; last week's rows stand, the store and edition go on" ;;
esac
exit 0
