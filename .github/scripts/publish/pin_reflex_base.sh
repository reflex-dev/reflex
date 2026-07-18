#!/usr/bin/env bash
set -euo pipefail

: "${VERSION:?}"

if ! grep -q '"reflex-base >= ' pyproject.toml; then
  echo "Error: expected 'reflex-base >= ...' dependency in pyproject.toml"
  exit 1
fi
sed -i 's|"reflex-base >= [^"]*"|"reflex-base == '"$VERSION"'"|' pyproject.toml
grep '"reflex-base' pyproject.toml
