#!/bin/bash

set -e

NODE_AND_FRIENDS=(node npm nvm bun)

for n in "${NODE_AND_FRIENDS[@]}"; do
  echo "checking for $n"
  if which "$n" >/dev/null 2>&1; then
    echo "$n found in system path"
    for f in $(which -a "$n"); do
      echo "- Deleting $f"
      rm -f "$f"
    done
  else
    echo "$n not found (great!)"
  fi
done

for n in "${NODE_AND_FRIENDS[@]}"; do
  if which "$n" >/dev/null 2>&1; then
    echo "$n STILL found in system path after attempt to delete them"
    exit 1
  fi
done
