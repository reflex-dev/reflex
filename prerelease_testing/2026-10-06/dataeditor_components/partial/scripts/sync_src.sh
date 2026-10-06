#!/bin/bash
# Copy the shared app source into app-alpha/ and app-stable/ (keeps their .web/).
W="$(cd "$(dirname "$0")/.." && pwd)"
for v in alpha stable; do
  mkdir -p "$W/app-$v/cluster_app" "$W/app-$v/assets"
  cp "$W/src/rxconfig.py" "$W/app-$v/rxconfig.py"
  rm -f "$W/app-$v/cluster_app/"*.py
  cp "$W/src/cluster_app/"*.py "$W/app-$v/cluster_app/"
  cp "$W/src/assets/"* "$W/app-$v/assets/"
done
echo synced
