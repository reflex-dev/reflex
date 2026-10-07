#!/usr/bin/env bash
# Copies a3_ent_grid apps (sources only), drivers, scripts, bin, outputs (PNG -> JPEG) and trimmed logs to DEST.
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
W=$SB/apps/a3_ent_grid
DEST=/home/user/reflex/prerelease_testing/2026-10-07-a3/a3_ent_grid
mkdir -p $DEST/apps $DEST/drivers $DEST/bin $DEST/scripts $DEST/out $DEST/logs
EXCL=(--exclude=.web --exclude=node_modules --exclude=.states --exclude=assets/external --exclude='*.db' --exclude=reflex.lock --exclude=__pycache__ --exclude=uploaded_files)
( cd $W/src && tar "${EXCL[@]}" -cf - . ) | ( cd $DEST/apps && tar -xf - )
cp -r $W/drivers/. $DEST/drivers/; cp -r $W/scripts/. $DEST/scripts/; cp -r $W/bin/. $DEST/bin/
rm -rf $DEST/drivers/__pycache__ $DEST/scripts/__pycache__
# outputs: JSON + JPEG only (PNG converted, quality 60)
( cd $W/out && find . -type f \( -name "*.json" -o -name "*.md" -o -name "*.txt" -o -name "*.jpg" \) | tar -cf - -T - ) | ( cd $DEST/out && tar -xf - )
( cd $W/out && find . -name "*.png" ) | while read -r f; do
  t="$DEST/out/${f%.png}.jpg"; [ -f "$t" ] && [ "$t" -nt "$W/out/$f" ] && continue
  mkdir -p "$(dirname "$t")"; convert "$W/out/$f" -quality 60 "$t"
done
for f in $W/logs/*.log; do
  grep -vE "gzip:|^Debug: build/client/assets|^\s*$|^Debug: Copying|^\.web/build/client/" "$f" | head -c 200000 > $DEST/logs/$(basename $f)
done
du -sh $DEST
