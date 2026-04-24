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
)
ORDER=(hatch_reflex_pyi reflex_base reflex_components_code reflex_components_core reflex_components_dataeditor reflex_components_gridjs reflex_components_lucide reflex_components_markdown reflex_components_moment reflex_components_plotly reflex_components_radix reflex_components_react_player reflex_components_recharts reflex_components_sonner reflex_docgen reflex_hosting_cli)

PACKAGES=()
for key in "${ORDER[@]}"; do
  if [[ "${!key:-false}" == "true" ]]; then
    PACKAGES+=("\"${MAP[$key]}\"")
  fi
done

if [[ ${#PACKAGES[@]} -eq 0 ]]; then
  echo "Error: select at least one package"
  exit 1
fi

JOINED=$(IFS=,; echo "${PACKAGES[*]}")
echo "packages=[$JOINED]" >> "$GITHUB_OUTPUT"
