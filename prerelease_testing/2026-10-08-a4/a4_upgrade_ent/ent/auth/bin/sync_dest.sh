#!/usr/bin/env bash
# Copy reusable artifacts (sources, drivers, trimmed logs, jpg screenshots) into the repo DEST dir. No git.
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
W=$SB/apps/a4_upgrade_ent/ent/auth
DEST=/home/user/reflex/prerelease_testing/2026-10-07-a3/a3_ent_auth
mkdir -p $DEST/apps $DEST/bin $DEST/drivers $DEST/scripts $DEST/logs $DEST/shots
EXC="--exclude=.web --exclude=node_modules --exclude=.states --exclude=assets/external --exclude=*.db --exclude=reflex.lock --exclude=__pycache__ --exclude=uploaded_files"
for a in vauth_src coregd_src entauth_src mapsapp_src; do
  [ -d $W/$a ] || continue; mkdir -p $DEST/apps/${a%_src}; tar -C $W/$a -cf - $EXC . | tar -C $DEST/apps/${a%_src} -xf -
done
mkdir -p $DEST/apps/a4auth; tar -C $W/a4auth -cf - $EXC --exclude=./screenshots . | tar -C $DEST/apps/a4auth -xf -
tar -C $W/bin -cf - --exclude=__pycache__ . | tar -C $DEST/bin -xf -
tar -C $W/drivers -cf - --exclude=__pycache__ . | tar -C $DEST/drivers -xf -
tar -C $W/scripts -cf - --exclude=__pycache__ . | tar -C $DEST/scripts -xf -
# logs: copy, gzip anything > 40 KB
tar -C $W/logs -cf - --exclude='*.pid' . | tar -C $DEST/logs -xf -
find $DEST/logs $DEST/apps/a4auth/logs -type f ! -name '*.gz' -size +40k -exec gzip -f {} + 2>/dev/null
# screenshots -> jpg (quality 60, max 1100 px wide)
for d in shots screenshots a4auth/screenshots; do
  [ -d $W/$d ] || continue
  for f in $W/$d/*.png; do
    [ -f "$f" ] || continue
    out=$DEST/shots/$(basename "${f%.png}").jpg
    [ -f "$out" ] && [ "$out" -nt "$f" ] && continue
    convert "$f" -resize '1100x>' -quality 60 "$out"
  done
done
du -sh $DEST
