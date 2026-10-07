ITEM: a3_ent_grid
KIND: reverify
REF: N-025
TITLE: Prod AG Grid with State-var column_defs / detail_cell_renderer_params renders no columns on prerendered routes — FIXED by reflex-enterprise 0.9.7a5 (on reflex 0.10.0a3 and 0.10.0a2); still broken with enterprise 0.9.7a4 on reflex 0.10.0a3
SEVERITY: high
STATUS: fixed
REGRESSION_VS_0.9.12: no
REGRESSION_VS_0.10.0a2: no
REPRO: SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; W=$SB/apps/a3_ent_grid (copy prerelease_testing/2026-10-07-a3/a3_ent_grid/{apps->src,bin,drivers,scripts} there); cd $W
  bin/run.sh a3-ent    entv prod 3306 entv_a3ent_prod                 # a3 + a5: every scenario s1-s13 renders (2h/6c, detail Count,Value)
  bin/run.sh a3-ent    entv dev  3307 entv_a3ent_dev                  # same
  bin/run.sh a3-ent-a4 entv prod 3308 entv_a3enta4_prod --only s1,s11,s8   # a3 + OLD a4 wheel: state grid 0h/0c on load/reload/unrelated event, memo grids empty, detail headers []
  bin/run.sh alpha2-ent entv prod 3300 entv_alpha2ent_prod --only s1,s11   # positive control (a2 + a4): broken, as in the a2 pass
  bin/run.sh alpha2-ent-a5 entv prod 3301 entv_alpha2enta5_prod       # a2 + a5: fixed (fix is enterprise-only)
  bin/run.sh s912-ent-a5 entv prod 3303 entv_s912enta5_prod           # 0.9.12 + a5: still fine
  bin/run.sh a3-ent aggrid_min prod 3309 aggrid_min_a3ent_prod ; bin/run.sh a3-ent-a4 aggrid_min prod 3310 aggrid_min_a3enta4_prod   # explorer's probe: 4/4 vs 2/4
  $SB/envs/driver/bin/python drivers/summarize.py out ; $SB/envs/driver/bin/python drivers/anomalies.py out/entv_a3ent_prod
EVIDENCE: prerelease_testing/2026-10-07-a3/a3_ent_grid/NOTES.md §1 (matrix next to the a2-pass numbers) and §4 (enterprise ag_grid demo on a3+a5 prod: probe_state_coldefs 7/7 — /master-detail State grid, /qa-grid-memo memo + 2 ComponentState grids, /formatters State tab — vs 3/7 on a2 prod; out/ag_prod_a3/); out/entv_a3ent_prod/*.json + s2_reload.jpg, s11_detail_expand.jpg; out/entv_a3enta4_prod/s2_reload.jpg (empty state grid), out/entv_alpha2ent_prod (control); out/aggrid_min_a3ent_prod*.json vs out/aggrid_min_a3enta4_prod*.json. Boot frames on a3 unchanged (hydrate_and_load; deltas carry only the root state; window.__reflex still assigned in the ReflexProviders effect) — the fix is entirely in enterprise's formatColumnDefs. Page errors 0, no non-benign console output.
REGRESSION HUNT (enterprise#273): no regression — NOTES §3 (entr fixture: literal + Var-valued column defs with Python lambdas, memo cells, master/detail, pinned rows, row grouping, rx.cond; prod full load/reload/client nav + dev; a3, a2, 0.9.12): 0 page errors, 0 ReferenceError/#130/#185/#418 in default mode, 0 of 583 traced renderer calls before window.__reflex. Core side unchanged on a3 (corev c1: render-time __reflex readers of unchanged substates stay NO_REFLEX in prod, out/corev_a3_prod).
ROOT_CAUSE_GUESS: fixed in reflex_enterprise/components/ag_grid/aggrid.py:2286-2297 (0.9.7a5: guard is now only `typeof window === "undefined"`). Users on reflex 0.10 MUST upgrade reflex-enterprise to >= 0.9.7a5: reflex 0.10.0a3 itself did not change the render-before-window.__reflex ordering, so enterprise <= 0.9.7a4 stays broken on 0.10 prod (any other render-time reader of window.__reflex on a prerendered prod page of an unchanged substate is still affected, as on a2).
