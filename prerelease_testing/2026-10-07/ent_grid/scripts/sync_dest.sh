#!/usr/bin/env bash
# Copy ent_grid artifacts (apps without build outputs, scripts, trimmed logs, out/) into DEST.
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
W=$SB/apps/ent_grid
DEST=/home/user/reflex/prerelease_testing/2026-10-07/ent_grid
mkdir -p "$DEST/apps" "$DEST/scripts" "$DEST/out" "$DEST/logs"
for d in ag_grid dnd flow mantine highcharts tickets rxeapp; do
  [ -d "$W/$d" ] || continue
  mkdir -p "$DEST/apps/$d"
  tar -C "$W/$d" --exclude=.web --exclude=node_modules --exclude=.states --exclude='*.db' --exclude=reflex.lock \
      --exclude=__pycache__ --exclude=assets/external --exclude='*.zip' --exclude=export_out -cf - . | tar -C "$DEST/apps/$d" -xf -
done
cp $W/scripts/*.py $W/scripts/*.sh "$DEST/scripts/" 2>/dev/null
# out: JSON reports + screenshots (png only, skip huge ones)
(cd "$W/out" && find . -type f \( -name '*.json' -o -name '*.png' -o -name '*.txt' \) -size -900k -print0 | tar --null -T - -cf -) | tar -C "$DEST/out" -xf -
# logs: trim server logs to 400KB head+tail
for f in "$W"/logs/*.log; do
  b=$(basename "$f"); sz=$(stat -c %s "$f")
  if [ "$sz" -gt 400000 ]; then { head -c 150000 "$f"; printf '\n\n[... trimmed %s bytes ...]\n\n' "$sz"; tail -c 200000 "$f"; } > "$DEST/logs/$b"; else cp "$f" "$DEST/logs/$b"; fi
done
[ -f "$W/NOTES.md" ] && cp "$W/NOTES.md" "$DEST/NOTES.md"
du -sh "$DEST"
