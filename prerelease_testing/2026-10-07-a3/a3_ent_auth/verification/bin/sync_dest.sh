#!/usr/bin/env bash
# Copy sources, trimmed logs, driver outputs (gzipped) and screenshots to the repo DEST (no .web/venvs/db).
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; W=$SB/apps/verify_ent_auth
D=/home/user/reflex/prerelease_testing/2026-10-07-a3/a3_ent_auth/verification
mkdir -p $D/app $D/bin $D/drivers $D/scripts $D/logs $D/out $D/shots
rm -rf $D/app; mkdir -p $D/app; (cd $W/vea_src && tar --exclude=.web --exclude=__pycache__ --exclude="*.db" --exclude=.states --exclude=reflex.lock -cf - .) | (cd $D/app && tar -xf -)
cp $W/bin/*.sh $D/bin/; cp $W/drivers/*.py $D/drivers/; cp $W/scripts/*.py $D/scripts/ 2>/dev/null
for f in $W/out/*.json; do gzip -c $f > $D/out/$(basename $f).gz; done
for f in $W/logs/*.server.log; do
  { head -2 $f; grep -E "VEA_|Traceback|Error|ERROR|WARNING|Warning|Started worker|405|Exception" $f | grep -v "^Debug: \s*$" | head -400; } > $D/logs/$(basename $f .log).trimmed.log
done
cp $W/shots/*.jpg $D/shots/ 2>/dev/null
du -sh $D
mkdir -p $D/drivers_explorer_copy $D/out_vdrv
cp $W/drivers_explorer/*.py $D/drivers_explorer_copy/
for f in $W/out_vdrv/*.json; do gzip -c $f > $D/out_vdrv/$(basename $f).gz; done
cp $W/out/*.txt $W/out/*.out $D/out/ 2>/dev/null
du -sh $D
