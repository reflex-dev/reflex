# Cluster `dataeditor` — finish dataeditor/component interactions on 0.10.0a2 (dataeditor 0.10.0a1) with 0.9.12 baselines

Ports: frontend 3420-3439, backend 8420-8439. Work dir: $SB/apps/dataeditor/. DEST: /home/user/reflex/prerelease_testing/2026-10-07/dataeditor/
Venv: $SB/envs/alpha2; baselines $SB/envs/stable (0.9.12 + dataeditor 0.9.3.post1) and $SB/envs/alpha (0.10.0a1).

Read first: $SB/CAMPAIGN_STATE.md, /home/user/reflex/prerelease_testing/2026-10-06/FINDINGS.md "Partial clusters → dataeditor_components", /home/user/reflex/prerelease_testing/2026-10-06/briefs/dataeditor_components.md,
/home/user/reflex/prerelease_testing/2026-10-06/dataeditor_components/partial/ (src/cluster_app, scripts, runs/*/results.json — reuse the app and drivers; copy out).

## Do (every lead needs a 0.9.12 baseline before it is called a regression)
1. Data editor: `first_edit_fast_typing_keeps_all_chars` (typed fast into a cell on first edit → got "ed"), delete-key
   on_delete payload, bool single-click toggle, `foreach_editors_render` (data editors inside rx.foreach rendered 0
   canvases — real bug or driver?), overlay close-on-Escape, theme application (flaky?), ComponentState edit isolation,
   big-grid long tasks; image preview overlay carousel styles (#7081) on 0.10.0a1 dataeditor.
2. Forms (#7227): `rx.select` with `name` absent from the submitted payload (f_select), dialog form submit reaching the outer
   form, id-backed controls present when unset — on alpha2 AND 0.9.12 AND 0.10.0a1; print exact payloads.
3. Recharts tick-formatter checks (12/15 not-ok with empty detail): fix the driver selector first (ticks are SVG <text>
   inside .recharts-cartesian-axis-tick), then decide real vs driver. Plotly/radix/code/download/match/memo-name groups:
   re-run once on alpha2 to confirm still green.
4. New in this train for components: dataeditor 0.10.0a1, react-player 0.10.0a1, sonner 0.10.0a1, lucide 1.1.0a1 — smoke each
   (render + one interaction) and diff their wheels against the previous versions (`pip download` both, unzip, diff the .py)
   to see whether anything beyond the Python floor changed.
Copy artifacts to DEST as you go.
