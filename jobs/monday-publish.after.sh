#!/bin/bash
# After the Mac Mini's Monday publish has committed: start GitHub's Deploy
# tracker, which rebuilds the vote tracker, runs the suite as its gate and
# deploys the committed partner_site/ with the Vercel token GitHub holds.
# tools/mini_run.sh runs this only when the publish pushed a commit.
set -eo pipefail
gh workflow run deploy-tracker.yml -R thejoycething-code/parl-monitor --ref main
echo "  Deploy tracker started on GitHub (it deploys the committed partner_site/)"
