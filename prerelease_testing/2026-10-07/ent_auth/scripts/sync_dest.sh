#!/usr/bin/env bash
# Copy reusable artifacts (no build output / venvs / state) into the repo's DEST dir (tar with excludes; no rsync here).
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
W=$SB/apps/ent_auth2
DEST=/home/user/reflex/prerelease_testing/2026-10-07/ent_auth
mkdir -p $DEST/apps $DEST/scripts $DEST/logs $DEST/screenshots
EXC="--exclude=.web --exclude=node_modules --exclude=.states --exclude=./assets/external --exclude=*/assets/external --exclude=*.db --exclude=reflex.lock --exclude=__pycache__ --exclude=uploaded_files --exclude=.gitignore"
for a in entauth mapsapp; do mkdir -p $DEST/apps/$a; tar -C $W/$a -cf - $EXC . | tar -C $DEST/apps/$a -xf -; done
# a4auth: the 10-05 auth matrix apps + drivers re-pointed to this cluster's ports (10-05 reference JSON left out)
mkdir -p $DEST/apps/a4auth
(cd $W/a4auth && find . \( -path ./reference -o -name .web -o -name node_modules -o -name .states -o -name __pycache__ \) -prune -o -type f \( -name '*.py' -o -name '*.md' -o -path './logs/a2/*' \) -print | grep -v __pycache__ | tar -cf - -T -) | tar -C $DEST/apps/a4auth -xf -
tar -C $W/scripts -cf - --exclude=__pycache__ . | tar -C $DEST/scripts -xf -
tar -C $W/logs -cf - . | tar -C $DEST/logs -xf -
tar -C $W/screenshots -cf - . | tar -C $DEST/screenshots -xf -
# keep the tree small: big logs / raw event JSON are stored gzipped (zcat / zless to read)
find $DEST/logs $DEST/apps/a4auth/logs -type f \( -name "*.json" -o -name "*.log" -o -name "*.out" \) -size +40k -exec gzip -f {} +
du -sh $DEST
