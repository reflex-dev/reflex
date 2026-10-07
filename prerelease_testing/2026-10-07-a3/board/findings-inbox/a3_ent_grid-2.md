ITEM: a3_ent_grid
KIND: reverify
REF: N-025 (the REFLEX_FRONTEND_LAZY_BUNDLED_LIBRARIES workaround caveat recorded in its verification)
TITLE: With REFLEX_FRONTEND_LAZY_BUNDLED_LIBRARIES=true, any prerendered page whose AG Grid Python-lambda renderer returns a Radix component still crashes with React #130 (a3 + enterprise a5); the flag is no longer needed for N-025
SEVERITY: low
STATUS: still-broken
REGRESSION_VS_0.9.12: no (the flag does not exist on 0.9.12; default mode works on every version)
REGRESSION_VS_0.10.0a2: no (identical on a2 + a4)
REPRO: SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; W=$SB/apps/a3_ent_grid (copy prerelease_testing/2026-10-07-a3/a3_ent_grid/{apps->src,bin,drivers,scripts}); cd $W
  RUNSUFFIX=_lazy bin/run.sh a3-ent entv prod 3313 entv_a3ent_prod_lazyflag --only s1,s8,s11,s12 -- REFLEX_FRONTEND_LAZY_BUNDLED_LIBRARIES=true
     -> s12 /renderer (literal column_defs, cell_renderer=lambda p: rx.badge(p.value)): "An error occurred while rendering this page", console "Minified React error #130 ... args[]=undefined"; s1/s8/s11 grids render (the #418 on s1/s2/s5 comes from the fixture's own __reflex probe).
  RUNSUFFIX=_lazy bin/run.sh a3-ent entr prod 3314 entr_a3ent_prod_lazyflag -- REFLEX_FRONTEND_LAZY_BUNDLED_LIBRARIES=true          # /lit and /var crash on load (#130); driver aborts at the toggle click
  RUNSUFFIX=_lazy bin/run.sh a3-ent entr prod 3314 entr_a3ent_prod_lazyflag_r34 --only r3,r4 -- REFLEX_FRONTEND_LAZY_BUNDLED_LIBRARIES=true   # /memo2 crashes on load; /detail2 crashes when a row with a lambda rx.badge detail renderer is expanded
  The same pages render fully without the flag (out/entr_a3ent_prod, out/entv_a3ent_prod).
EVIDENCE: prerelease_testing/2026-10-07-a3/a3_ent_grid/out/entv_a3ent_prod_lazyflag/s12_renderer_full_load.{json,jpg}, out/entr_a3ent_prod_lazyflag/r1_lit_full_load.{json,jpg}, out/entr_a3ent_prod_lazyflag_r34/r3_detail_expand.json (detail: "An error occurred while rendering this page"); NOTES.md §3.
ROOT_CAUSE_GUESS: reflex_enterprise/vars.py:174 compiles lambda bodies to `const X = __reflex['@radix-ui/themes']?.X` — with the lazy flag @radix-ui/themes moves to the lazy loader, so the lookup yields undefined at cell-render time (React #130 "element type is undefined"). Documented caveat of the flag; now only relevant to users who keep the flag on after upgrading enterprise (a5 makes it unnecessary for State-var column defs).
