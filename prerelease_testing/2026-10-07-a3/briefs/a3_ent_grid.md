# Item `a3_ent_grid` — N-025 on reflex 0.10.0a3 + enterprise 0.9.7a5, and AG Grid / enterprise demo regressions from enterprise#273

Ports: frontend 3300-3319, backend 8300-8319 (prod single port inside 3300-3319). Work dir: $SB/apps/a3_ent_grid/.
DEST: /home/user/reflex/prerelease_testing/2026-10-07-a3/a3_ent_grid/
Venvs: $SB/envs/a3-ent (under test), $SB/envs/a3-ent-a4 (reflex a3 + OLD a4 wheel), $SB/envs/s912-ent-a5 (0.9.12 + a5),
$SB/envs/alpha2-ent (a2 + a4, the a2-pass state), $SB/envs/a3 / alpha2 / stable (core-only fixtures). CI=true REFLEX_TELEMETRY_ENABLED=false.

Read first: ../CAMPAIGN_STATE.md, ../AGENT_BRIEF.md, ../../2026-10-07/FINDINGS.md "N-025", ../../2026-10-07/ent_grid/verification/NOTES.md
(fixtures entv/corev, driver drivers/drive.py that traps the `window.__reflex` setter, bin/start.sh/stop.sh, summarize.py — COPY them
to your work dir and adjust ports/venv names), ../../2026-10-07/ent_grid/NOTES.md §1a (explorer's apps/aggrid_min + scripts/probe_aggrid_min.py).
The a5 diff is only the `formatColumnDefs` guard: compare `$SB/downloads/enterprise_wheel{,_a5}/x/reflex_enterprise/components/ag_grid/aggrid.py`.

## Do
1. Re-run the verifier's `entv` matrix (all scenarios s1–s13) on a3-ent PROD and DEV, and the explorer's aggrid_min probe. Expected fixed:
   state grid headers/cells on full load, reload, second context, `@rx.memo` grids, `/onload`, `/detail` expanded detail grid
   (Var-valued `detail_cell_renderer_params`), `/renderer`. Report header/cell counts per scenario next to the a2-pass numbers.
2. Version matrix (prod, entv s1+s11 at least): a3-ent (a3+a5), a3-ent-a4 (expected still EMPTY: reflex did not change, the fix is
   enterprise-only — confirm and say so plainly: users must upgrade enterprise too), s912-ent-a5 (enterprise a5 on 0.9.12 must
   still render everything), alpha2-ent + a5 if cheap (make your own venv).
3. Regression hunt for enterprise#273 (column defs now formatted before `window.__reflex` exists): Python-lambda `cell_renderer`,
   `value_formatter`, `value_getter`, `cell_class_rules`, tooltip/header components, `rx.badge`/`rx.icon`/`rx.link` returned from a
   lambda, `@rx.memo` components in cells, master/detail with lambda renderers in the detail grid, pinned rows, row grouping —
   on a prerendered PROD route full load + reload and in DEV, Var-valued and literal column defs. Watch the console for
   `ReferenceError: __reflex is not defined`, React #130/#185 and blank cells. Check the order of events with the setter trap
   (first cell-render vs `window.__reflex` assignment). Also `REFLEX_FRONTEND_LAZY_BUNDLED_LIBRARIES=true` (was a documented
   workaround with a React #130 caveat for lambdas returning Radix components: is it still broken?).
4. Broad AG Grid smoke on a3-ent dev + prod with the enterprise ag_grid demo (copy /home/user/reflex/prerelease_testing/2026-10-07/ent_grid/
   apps or /home/user/reflex-enterprise/demos/ag_grid): feature pages, /model, /model-auth, SSRM, infinite (F-001 enterprise half
   must still hold), memo/props QA grids; compare with the a2-pass counts (dev 20/20 smoke, 46/47 features, 24/29 model).
5. Quick smoke (dev + prod, one pass each) of dnd, flow, mantine and maps demos on a3-ent: #7493/#7495 touched boot and class
   assignment; anything that differs from the a2-pass results needs a 0.9.12+a5 baseline.
Write one inbox file per finding (N-025 reverify + anything new). Copy artifacts to DEST as you go; commit per the protocol.
