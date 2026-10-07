# Cluster `ent_grid` — finish the enterprise demos on 0.10.0a2 + offline enterprise wheel (dnd, flow, mantine, highcharts, tickets, AG Grid prod leads)

Ports: frontend 3300-3319, backend 8300-8319. Work dir: $SB/apps/ent_grid/. DEST: /home/user/reflex/prerelease_testing/2026-10-07/ent_grid/
Venv: $SB/envs/alpha2-ent (alpha2 + OFFLINE enterprise 0.9.7a4 wheel [mcp]). Baselines when something fails: reflex 0.9.12 + the same
offline wheel (make $SB/envs/ent_grid-s912 with `'reflex[db]==0.9.12'` + the wheel file), and $SB/envs/alpha (0.10.0a1) + wheel.
Run everything with CI=true REFLEX_TELEMETRY_ENABLED=false; the offline wheel should not need a login — if a login gate still
appears, record exactly what it says.

Read first: $SB/CAMPAIGN_STATE.md, /home/user/reflex/prerelease_testing/2026-10-06/FINDINGS.md "Partial clusters → ent_demos", /home/user/reflex/prerelease_testing/2026-10-06/briefs/ent_demos.md (the original
assignment), /home/user/reflex/prerelease_testing/2026-10-06/ent_demos/partial/README.md and reuse its drivers/apps (copy out). The previous campaign's enterprise drivers
are under /home/user/reflex/prerelease_testing/2026-10-05/enterprise/ (read-only).

## Do
1. AG Grid: re-run the feature pages (master-detail, pivot, tree, cell selection, fill handle, aligned grids, integrated
   charts, memo/props QA grids) in dev AND PROD, re-examining the four prod-only not-ok checks from the partial run
   (`master_detail: scenario completed`, clipboard Ctrl+C/V change event, `memo grid: column defs from State.fields.foreach`
   rendering empty, `qa_memo`): are they real (reproduce 3×, read the console) or driver timing? The model-wrapper pages
   (/model, /model-auth, SSRM, infinite) are covered by `reverify_core` — just confirm they load here, then focus on the
   SSRM/infinite filter-count and add-dialog mismatches (also seen on the mixed graph → classify pre-existing vs driver).
2. dnd, flow, mantine, highcharts, tickets demos (copy from /home/user/reflex-enterprise/demos/<name>, install their extra
   requirements into your own venv built like alpha2-ent): dev + prod, drive every interaction the demo offers (real pointer
   drag for dnd/flow), reload, second tab; console/network/server-log capture.
3. `rxe.App` specifics: google_font head, badge, `reflex export` of one demo (zip sanity).
Report per demo: pass/fail/anomaly with baseline classification. Copy artifacts to DEST as you go.
