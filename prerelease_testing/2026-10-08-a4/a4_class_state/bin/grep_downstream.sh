#!/bin/bash
# Unpack the downloaded third-party wheels and grep them (+ enterprise a5 + auth package sources) for class-level writes to state attributes.
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; W=$SB/apps/a4_class_state; U=$W/downstream/unz
mkdir -p $U; cd $U; for f in $SB/downloads/wheels/*.whl; do n=$(basename $f .whl); [ -d $n ] || (mkdir -p $n && cd $n && unzip -qo $f); done
DIRS="$(ls -d $U/*/ | grep -v 'reflex_components_\|reflex_enterprise-0.9.7a4\|reflex_hosting') $SB/downloads/enterprise_wheel_a5/x $SB/downloads/reflex-local-auth $SB/downloads/reflex-google-auth $SB/downloads/reflex-magic-link-auth"
echo "--- <Name>.<attr> = (class attribute writes)"; grep -rnE --include=*.py "^\s*[A-Z][A-Za-z0-9_]*\.[a-z_][A-Za-z0-9_]*\s*(\+|-|\|)?=[^=]" $DIRS | grep -v "self\." | sed "s|$SB/||"
echo "--- <x>.State.<attr> ="; grep -rnE --include=*.py "\.State\.[A-Za-z_]+\s*=[^=]" $DIRS | sed "s|$SB/||"
echo "--- cls.<attr> ="; grep -rnE --include=*.py "^\s*cls\.[A-Za-z_][A-Za-z0-9_]*\s*(\+|-)?=[^=]" $DIRS | sed "s|$SB/||"
echo "--- setattr/delattr on classes"; grep -rnE --include=*.py "(setattr|delattr)\((cls|type\(self\)|self\.__class__|[A-Z][A-Za-z0-9_]*)\b" $DIRS | sed "s|$SB/||"
echo "--- patch.object / monkeypatch"; grep -rnE --include=*.py "patch\.object|monkeypatch\.(setattr|delattr)" $DIRS | sed "s|$SB/||"
