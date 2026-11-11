#!/usr/bin/env bash
# `.web/package.json` / reflex.lock diff tooling for in-place upgrades.
#   web_pkg.sh snap <appdir> <prefix>   -> <prefix>.web.package.json, <prefix>.web.files (file list minus build output),
#                                          <prefix>.reflex.lock.ls (mtimes + sha256 of reflex.lock/*)
#   web_pkg.sh diff <prefix-a> <prefix-b> -> <prefix-b>.from-<a>.package.diff; prints the changed dependency lines,
#                                          whether the file lists match and whether reflex.lock/package.json == .web/package.json
set -u
case "$1" in
snap)
  A=$2; P=$3
  cp "$A/.web/package.json" "$P.web.package.json"
  (cd "$A" && find .web -path .web/node_modules -prune -o -type f -print | grep -v -E '\.web/(build|\.react-router|backend)/' | sort) > "$P.web.files"
  (ls -la --time-style=+%T "$A/reflex.lock" 2>/dev/null; sha256sum "$A"/reflex.lock/* 2>/dev/null) > "$P.reflex.lock.ls"
  if [ -f "$A/reflex.lock/package.json" ]; then cmp -s "$A/reflex.lock/package.json" "$A/.web/package.json" && echo "reflex.lock/package.json == .web/package.json" || echo "reflex.lock/package.json DIFFERS from .web/package.json"; fi ;;
diff)
  A=$2; B=$3; out="$B.from-$(basename "$A").package.diff"
  diff "$A.web.package.json" "$B.web.package.json" > "$out"
  echo "package.json $(basename "$A") -> $(basename "$B"): $(grep -E '^[<>]' "$out" | tr -s ' ' | tr '\n' ' ')"
  [ -s "$out" ] || echo "package.json identical"
  diff -q "$A.web.files" "$B.web.files" > /dev/null && echo ".web file list identical" || { echo ".web file list differs:"; diff "$A.web.files" "$B.web.files" | head -8; } ;;
*) echo "usage: web_pkg.sh snap <appdir> <prefix> | diff <prefix-a> <prefix-b>"; exit 2 ;;
esac
