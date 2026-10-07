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
  case $n in
    alpha2_dev_disk)   keep="direct_t1 direct_t2 spinner_t1 spinner_t2 gen_t1 gen_t3 sup_split_t3";;
    alpha2_dev_redis)  keep="direct_t3 gen_t1 gen_t3 spinner_t2 spinner_t3 sup_split_t1 sup_split_t3 bg_inside_t1 bg_inside_t3";;
    alpha2_prod_disk)  keep="direct_t1 spinner_t1";;
    alpha2_prod_redis) keep="gen_t1 gen_t3 spinner_t2";;
    *) keep="";;
  esac
  for k in $keep; do cp $d/$k.png $DEST/out/$n/ 2>/dev/null; done
  case $n in alpha2_dev_disk|alpha2_dev_redis) for r in $d/*_rows.json; do [ -f "$r" ] && gzip -c "$r" > $DEST/out/$n/$(basename $r).gz; done;; esac
done
cp $W/out/*.txt $W/out/*.md $DEST/out/ 2>/dev/null
rm -rf $DEST/logs; mkdir -p $DEST/logs
for l in $W/logs/*.log; do
  n=$(basename $l .log)
  grep -n -E "EVV |Reflex Backend Exception|RuntimeError|LockExpired|Lock for|ERROR" $l | cut -c1-260 > $DEST/logs/$n.interesting.txt
  gzip -c $l > $DEST/logs/$n.log.gz
done
# probes, their-driver outputs
cp -r $W/out_extra $DEST/ 2>/dev/null
mkdir -p $DEST/theirs_driver_on_my_ports
for d in $W/theirs/out/*/; do n=$(basename $d); for r in $d/*_report.json; do [ -f "$r" ] && gzip -c "$r" > $DEST/theirs_driver_on_my_ports/$(basename $r).gz; done; done
du -sh $DEST
