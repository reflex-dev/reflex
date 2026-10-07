#!/usr/bin/env bash
# Copy ent_grid artifacts (apps without build outputs, scripts, trimmed logs, out/) into DEST.
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
W=$SB/apps/ent_grid
DEST=/home/user/reflex/prerelease_testing/2026-10-07/ent_grid
mkdir -p "$DEST/apps" "$DEST/scripts" "$DEST/out" "$DEST/logs"
for d in ag_grid dnd flow mantine highcharts tickets rxeapp core_rerender; do
  [ -d "$W/$d" ] || continue
  mkdir -p "$DEST/apps/$d"
  tar -C "$W/$d" --exclude=.web --exclude=node_modules --exclude=.states --exclude='*.db' --exclude=reflex.lock \
      --exclude=__pycache__ --exclude=assets/external --exclude='*.zip' --exclude=export_out -cf - . | tar -C "$DEST/apps/$d" -xf -
done
cp $W/scripts/*.py $W/scripts/*.sh "$DEST/scripts/" 2>/dev/null
# out: JSON reports + screenshots (jpg/txt < 900k; repeat runs *_run2/*_run3 keep JSON only)
(cd "$W/out" && { find . -type f \( -name '*.json' -o \( \( -name '*.jpg' -o -name '*.txt' \) -not -path './*_run2/*' -not -path './*_run3/*' \) \) -size -900k -print0; [ -f "$W/keep_png.txt" ] && tr '\n' '\0' < "$W/keep_png.txt"; } | tar --null -T - -cf -) | tar -C "$DEST/out" -xf -
find "$DEST/out" -path '*_run[23]/*.jpg' -delete
# logs: drop vite build-asset listing lines, then trim to 150KB head+tail
for f in "$W"/logs/*.log; do
  b=$(basename "$f")
  grep -v -E '^Debug: (build/|\.web/|  )|kB [│|] gzip' "$f" > "$DEST/logs/$b.tmp"
  sz=$(stat -c %s "$DEST/logs/$b.tmp")
  if [ "$sz" -gt 150000 ]; then { head -c 50000 "$DEST/logs/$b.tmp"; printf '\n\n[... trimmed, original %s bytes ...]\n\n' "$sz"; tail -c 100000 "$DEST/logs/$b.tmp"; } > "$DEST/logs/$b"; rm "$DEST/logs/$b.tmp"; else mv "$DEST/logs/$b.tmp" "$DEST/logs/$b"; fi
done
$SB/envs/driver/bin/python $W/scripts/compact_json.py "$DEST/out"
[ -f "$W/NOTES.md" ] && cp "$W/NOTES.md" "$DEST/NOTES.md"
du -sh "$DEST"
