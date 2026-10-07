#!/usr/bin/env bash
# Copies the verifier's apps (sources only), drivers, scripts, outputs and trimmed logs to DEST.
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
W=$SB/apps/verify_ent_grid_0
DEST=/home/user/reflex/prerelease_testing/2026-10-07/ent_grid/verification
mkdir -p $DEST/apps $DEST/drivers $DEST/bin $DEST/out $DEST/logs
( cd $W/src && tar --exclude=.web --exclude=node_modules --exclude=.states --exclude=assets/external --exclude='*.db' --exclude=reflex.lock --exclude=__pycache__ -cf - . ) | ( cd $DEST/apps && tar -xf - )
cp -r $W/drivers/. $DEST/drivers/; rm -rf $DEST/drivers/__pycache__
cp -r $W/bin/. $DEST/bin/
cp -r $W/out/. $DEST/out/
for f in $W/logs/*.log; do
  grep -vE "gzip:|^Debug: build/client/assets|^\s*$" "$f" | head -c 300000 > $DEST/logs/$(basename $f)
done
du -sh $DEST
# screenshots: ship JPEG (quality 70) instead of PNG to keep DEST small
find $DEST/out -name "*.png" | while read -r f; do convert "$f" -quality 70 "${f%.png}.jpg" && rm -f "$f"; done
du -sh $DEST
