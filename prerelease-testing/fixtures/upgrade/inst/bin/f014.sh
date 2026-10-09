#!/usr/bin/env bash
# F-014: every `reflex component` form on $NEW. Expected (0.10.x): each prints "`reflex component` was removed in Reflex 0.10.
# Wrap React components directly in your app (https://reflex.dev/docs/wrapping-react/overview/) and start reusable component
# packages from the component template: https://github.com/reflex-dev/component-template" to stderr, rc 1 (`--help` forms rc 0),
# and `component` is absent from `reflex --help`. Runs in an empty scratch dir (inst/run/cli_neutral).
set -u; . "$(dirname "$0")/../../bin/env.sh"; I=$(cd "$(dirname "$0")/.." && pwd); D=$I/run/cli_neutral; mkdir -p "$D"; cd "$D"
R=$SB/envs/$NEW/bin/reflex
for a in "component" "component init" "component build --loglevel debug" "component share" "component install" "component publish --token x" "component --help" "component init --help"; do
  out=$($R $a 2>&1); rc=$?
  echo "reflex $a -> rc=$rc | $(echo "$out" | tr '\n' ' ' | cut -c1-160)"
done
echo "component listed in reflex --help: $($R --help 2>&1 | grep -cE '^\s+component\b')"
