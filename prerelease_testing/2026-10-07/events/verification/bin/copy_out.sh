#!/usr/bin/env bash
# copy reusable artifacts into the repo dir (plain cp/gzip; no git). usage: copy_out.sh
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
W=$SB/apps/verify_events_0
DEST=/home/user/reflex/prerelease_testing/2026-10-07/events/verification
mkdir -p $DEST/app/evv $DEST/driver $DEST/bin $DEST/out $DEST/logs
cp $W/app/rxconfig.py $DEST/app/; cp $W/app/evv/*.py $DEST/app/evv/
cp $W/driver/*.py $DEST/driver/
cp $W/bin/*.sh $DEST/bin/
rm -rf $DEST/out; mkdir -p $DEST/out
for d in $W/out/*/; do
  n=$(basename $d); mkdir -p $DEST/out/$n
  for r in $d/*_report.json; do
    [ -f "$r" ] || continue
    gzip -c "$r" > $DEST/out/$n/$(basename $r).gz
    (cd $W/driver && $SB/envs/driver/bin/python -I analyze.py "$r" > $DEST/out/$n/$(basename $r _report.json).analysis.txt 2>&1)
  done
  cp $d/*.png $DEST/out/$n/ 2>/dev/null
  for r in $d/*_rows.json; do [ -f "$r" ] && gzip -c "$r" > $DEST/out/$n/$(basename $r).gz; done
done
cp $W/out/*.txt $DEST/out/ 2>/dev/null
rm -rf $DEST/logs; mkdir -p $DEST/logs
for l in $W/logs/*.log; do
  n=$(basename $l .log)
  grep -n -E "EVV |Reflex Backend Exception|RuntimeError|LockExpired|Lock for|ERROR" $l | cut -c1-260 > $DEST/logs/$n.interesting.txt
  gzip -c $l > $DEST/logs/$n.log.gz
done
# restart-probe / extra outputs, if any
cp -r $W/out_extra $DEST/ 2>/dev/null
du -sh $DEST
