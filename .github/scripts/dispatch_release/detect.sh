#!/usr/bin/env bash
set -euo pipefail

declare -A MAP=(
  [hatch_reflex_pyi]=hatch-reflex-pyi
  [reflex_base]=reflex-base
  [reflex_components_code]=reflex-components-code
  [reflex_components_core]=reflex-components-core
  [reflex_components_dataeditor]=reflex-components-dataeditor
  [reflex_components_gridjs]=reflex-components-gridjs
  [reflex_components_lucide]=reflex-components-lucide
  [reflex_components_markdown]=reflex-components-markdown
  [reflex_components_moment]=reflex-components-moment
  [reflex_components_plotly]=reflex-components-plotly
  [reflex_components_radix]=reflex-components-radix
  [reflex_components_react_player]=reflex-components-react-player
  [reflex_components_recharts]=reflex-components-recharts
  [reflex_components_sonner]=reflex-components-sonner
  [reflex_docgen]=reflex-docgen
  [reflex_hosting_cli]=reflex-hosting-cli
  [reflex_otel]=reflex-otel
  [reflex_release]=reflex-release
)
ORDER=(hatch_reflex_pyi reflex_base reflex_components_code reflex_components_core reflex_components_dataeditor reflex_components_gridjs reflex_components_lucide reflex_components_markdown reflex_components_moment reflex_components_plotly reflex_components_radix reflex_components_react_player reflex_components_recharts reflex_components_sonner reflex_docgen reflex_hosting_cli reflex_otel reflex_release)

PACKAGES=()
for key in "${ORDER[@]}"; do
  if [[ "${!key:-false}" == "true" ]]; then
    PACKAGES+=("\"${MAP[$key]}\"")
  fi
done

if [[ ${#PACKAGES[@]} -eq 0 ]]; then
  # No explicit selection: the plan step auto-detects packages with pending
  # news fragments (or, for release-from-prerelease, packages whose changelog
  # is topped by an alpha).
  echo "No packages checked; deferring to auto-detection in the plan step."
fi

JOINED=$(IFS=,; echo "${PACKAGES[*]:-}")
echo "packages=[$JOINED]" >> "$GITHUB_OUTPUT"
