ITEM: a3_hydration
KIND: reverify
REF: F-003
TITLE: Computed-var rewrite of client storage during hydration — still fixed on 0.10.0a3 (all cvstore variants a-j, seeds 0/4, dev, prod, prod+redis; google-auth bogus token cleared)
SEVERITY: medium
STATUS: fixed
REGRESSION_VS_0.9.12: no
REGRESSION_VS_0.10.0a2: no
REPRO: SB=<scratch>; W=$SB/apps/a3_hydration.
  Positive control: $W/scripts/run_cv.sh alpha dev a1-dev-seed4 3143 8143 "a b g" PYTHONHASHSEED=4   -> a/b/g FAIL exactly as on 10-06.
  NAV=1 $W/scripts/run_cv.sh a3 dev a3-dev-seed0 3143 8143 all PYTHONHASHSEED=0 ; run_cv.sh a3 dev a3-dev-seed4 ... PYTHONHASHSEED=4
  run_cv.sh a3 prod a3-prod-seed{0,4} 3144 3144 all PYTHONHASHSEED={0,4} ; redis-server --port 8149 --save '' --appendonly no; run_cv.sh a3 prod a3-prod-redis-seed0 3144 3144 all PYTHONHASHSEED=0 REFLEX_REDIS_URL=redis://localhost:8149
  google-auth: $W/scripts/run_gauth.sh a3_hydration-tp-a3 dev a3-dev-seed{0,4,10} 3145 8145 {0,4,10}; run_gauth.sh a3_hydration-tp-a3 prod a3-prod-seed4 3146 3146 4 full
EVIDENCE: a3_hydration/results/f003/a1-dev-seed4.summary.txt (control, identical to the saved 10-06/a2-pass a1 run), a3-dev-seed{0,4}.summary.txt,
  a3-prod-seed{0,4}.summary.txt, a3-prod-redis-seed0.summary.txt: line-for-line identical to the a2 pass summaries for a-g (diff only adds i/j, which pass);
  a3-dev-seed0.cvnav.txt: client-side-navigation path still seed-dependent (a/b/e/f/g FAIL on seed 0) — identical to a2 (N-015, pre-existing);
  (b) still shows the uncached cv's hydrate-time value until the next reload (N-016, pre-existing). results/gauth/*.json: bogus token cleared on
  the first reload on seeds 0/4/10 dev and prod seed 4 (0.9.12 seed 4 rerun today keeps BOGUS; a2 seed 4 clears); full google-auth report 12/13 = a2.
ROOT_CAUSE_GUESS: fixed by #7460; #7493's re-marking of applied vars carries the post-snapshot (corrected) value, so the correction still reaches storage.
