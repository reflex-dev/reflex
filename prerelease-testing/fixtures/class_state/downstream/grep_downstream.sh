#!/bin/bash
# Grep downstream code for class-level writes to state attributes (now a TypeError for state vars; ClassVar targets are fine).
# Usage: downstream/grep_downstream.sh [dir...]
#   default: unpack every $SB/downloads/wheels/*.whl into $W/downstream/unz (skips reflex_components_*, reflex_hosting*), plus
#   $SB/downloads/{enterprise_wheel*/x,reflex-local-auth,reflex-google-auth,reflex-magic-link-auth,reflex-examples} when present.
. "$(cd "$(dirname "$0")/.." && pwd)/env.sh"
if [ $# -gt 0 ]; then DIRS="$*"; else
  U=$W/downstream/unz; mkdir -p "$U"
  for f in "$SB"/downloads/wheels/*.whl; do n=$(basename "$f" .whl); [ -d "$U/$n" ] || (mkdir -p "$U/$n" && cd "$U/$n" && unzip -qo "$f"); done
  DIRS="$(ls -d "$U"/*/ | grep -v 'reflex_components_\|reflex_hosting')"
  for x in "$SB"/downloads/enterprise_wheel*/x "$SB"/downloads/reflex-local-auth "$SB"/downloads/reflex-google-auth "$SB"/downloads/reflex-magic-link-auth "$SB"/downloads/reflex-examples; do
    [ -d "$x" ] && DIRS="$DIRS $x"; done
fi
echo "--- <Name>.<attr> = (class attribute writes)"; grep -rnE --include=*.py "^\s*[A-Z][A-Za-z0-9_]*\.[a-z_][A-Za-z0-9_]*\s*(\+|-|\|)?=[^=]" $DIRS | grep -v "self\." | sed "s|$SB/||"
echo "--- <x>.State.<attr> ="; grep -rnE --include=*.py "\.State\.[A-Za-z_]+\s*=[^=]" $DIRS | sed "s|$SB/||"
echo "--- cls.<attr> ="; grep -rnE --include=*.py "^\s*cls\.[A-Za-z_][A-Za-z0-9_]*\s*(\+|-)?=[^=]" $DIRS | sed "s|$SB/||"
echo "--- setattr/delattr on classes"; grep -rnE --include=*.py "(setattr|delattr)\((cls|type\(self\)|self\.__class__|[A-Z][A-Za-z0-9_]*)\b" $DIRS | sed "s|$SB/||"
echo "--- patch.object / monkeypatch"; grep -rnE --include=*.py "patch\.object|monkeypatch\.(setattr|delattr)" $DIRS | sed "s|$SB/||"
echo "--- add_var / add_field / _create_setter calls (A4-01/A4-02 reach)"; grep -rnE --include=*.py "\.(add_var|add_field|_create_setter)\(" $DIRS | sed "s|$SB/||"
echo "--- state defaults bound to a module-level name the module later mutates (A5-01 reach)"; python3 -I "$CS/downstream/grep_late.py" $DIRS
