#!/bin/bash
# Batch 2 (one server at a time): A3-11 explorer storm series (sync_race.py Part S, 6 tabs) and A3-12 /stamp series
# (stamp_storm.py, 6 tabs + /same control): a3 positive control first, then a5; dev then prod.
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; W=$SB/apps/a5_hydration_router
O=$W/results/p2; mkdir -p $O; S=$W/scripts
echo "== cv a1 dev s4 (positive control, rerun with space-separated variants)"; $S/run_cv.sh alpha dev a1dev-s4 3142 8142 "a b g" PYTHONHASHSEED=4 > $O/cv_a1dev_s4.txt 2>&1; cat $O/cv_a1dev_s4.txt
echo "== storm a3 dev";  $S/run_storm.sh a3 dev 4 3142 8142 S 6 2>&1 | tee $O/storm_a3_dev.txt
echo "== storm a5 dev";  $S/run_storm.sh a5 dev 5 3142 8142 S 6 2>&1 | tee $O/storm_a5_dev.txt
echo "== storm a3 prod"; $S/run_storm.sh a3 prod 3 3144 3144 S 6 2>&1 | tee $O/storm_a3_prod.txt
echo "== storm a5 prod"; $S/run_storm.sh a5 prod 4 3144 3144 S 6 2>&1 | tee $O/storm_a5_prod.txt
echo "== stamp a3 dev";  $S/run_stamp2.sh a3 dev 3142 8142 2 1 6 2>&1 | tee $O/stamp_a3_dev.txt
echo "== stamp a5 dev";  $S/run_stamp2.sh a5 dev 3142 8142 3 1 6 2>&1 | tee $O/stamp_a5_dev.txt
echo "== stamp a3 prod"; $S/run_stamp2.sh a3 prod 3144 3144 2 1 6 2>&1 | tee $O/stamp_a3_prod.txt
echo "== stamp a5 prod"; $S/run_stamp2.sh a5 prod 3144 3144 3 1 6 2>&1 | tee $O/stamp_a5_prod.txt
echo BATCH2_DONE
