#!/bin/bash
# Batch 1 (one server at a time): reflex-local-auth a5 dev / a4 dev / a5 prod; F-003 cvstore a1 control then a5 dev/prod;
# reflex-google-auth bogus-token (F-003) a5 dev/prod + 0.9.12 control.
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; W=$SB/apps/a5_hydration_router
O=$W/results/p2; mkdir -p $O
S=$W/scripts
echo "== la a5 dev";  $S/run_la.sh a5_hydration_router-tp-a5 dev a5dev 3150 8150 > $O/la_a5dev.txt 2>&1; tail -14 $O/la_a5dev.txt
echo "== la a4 dev";  $S/run_la.sh a4_hydration-tp-a4 dev a4dev 3150 8150 > $O/la_a4dev.txt 2>&1; tail -14 $O/la_a4dev.txt
echo "== la a5 prod"; $S/run_la.sh a5_hydration_router-tp-a5 prod a5prod 3152 3152 > $O/la_a5prod.txt 2>&1; tail -14 $O/la_a5prod.txt
echo "== cv a1 dev s4 (positive control)"; $S/run_cv.sh alpha dev a1dev-s4 3142 8142 a,b,g PYTHONHASHSEED=4 > $O/cv_a1dev_s4.txt 2>&1; cat $O/cv_a1dev_s4.txt
echo "== cv a5 dev s4"; $S/run_cv.sh a5 dev a5dev-s4 3142 8142 all PYTHONHASHSEED=4 > $O/cv_a5dev_s4.txt 2>&1; cat $O/cv_a5dev_s4.txt
echo "== cv a5 dev s0"; $S/run_cv.sh a5 dev a5dev-s0 3142 8142 all PYTHONHASHSEED=0 > $O/cv_a5dev_s0.txt 2>&1; cat $O/cv_a5dev_s0.txt
echo "== cv a5 prod s4"; $S/run_cv.sh a5 prod a5prod-s4 3144 3144 all PYTHONHASHSEED=4 > $O/cv_a5prod_s4.txt 2>&1; cat $O/cv_a5prod_s4.txt
echo "== gauth a5 dev s4"; $S/run_gauth.sh a5_hydration_router-tp-a5 dev a5dev-s4 3142 8142 4 > $O/ga_a5dev.txt 2>&1; cat $O/ga_a5dev.txt
echo "== gauth 0.9.12 dev s4 (control)"; $S/run_gauth.sh a3_hydration-tp-s912 dev s912dev-s4 3142 8142 4 > $O/ga_s912dev.txt 2>&1; cat $O/ga_s912dev.txt
echo "== gauth a5 prod s4"; $S/run_gauth.sh a5_hydration_router-tp-a5 prod a5prod-s4 3144 3144 4 > $O/ga_a5prod.txt 2>&1; cat $O/ga_a5prod.txt
echo BATCH1_DONE
