# Cluster `upgrades_b` — in-place upgrade regression, reflex-examples (set B: db, uploads, streaming, custom components)

Ports: frontend 3180-3199, backend 8180-8199. Work dir: $SB/apps/upgrades_b/. DEST: /home/user/reflex/prerelease_testing/2026-10-06/upgrades_b/

## Why this cluster exists
Same rationale as `upgrades_a` (users upgrade in place; reflex-examples finds regressions). Your apps
(copy each from `$SB/downloads/reflex-examples/<app>` into `$SB/apps/upgrades_b/<app>`), in priority order:

1. **twitter** — `reflex[db]`, 3 pages, its own user/session auth in State, follows/tweets in sqlite.
   Flows: sign up, log in, post tweets, follow another user (second browser context), log out, reload.
2. **upload** — `rx.upload` with progress/cancel/clear; upload several files incl. a hostile filename
   (`../x.txt`, unicode, spaces) and a multi-MB file; check the saved files and the UI list.
3. **lorem-stream** — background/yield-heavy concurrent streaming; start several streams, pause/kill,
   reload mid-stream, open a second tab.
4. **local-component** — a locally wrapped React component (the pattern the "wrap React libraries
   directly" breaking change points users to); check it still compiles/bundles (`.web` custom code) in
   dev AND prod (`reflex run --env prod`).
5. **nba** — pandas + plotly (`rx.plotly`): pick filters, check the figure re-renders; plotly titles
   were normalized in 0.10.0a1 (#7226) — inspect the title renders. pandas/scipy/statsmodels are heavy;
   install them once and reuse the venv. If the pinned pandas/scipy fail to install on 3.12, relax the pins
   and note it.
6. **quiz** — `rx.code_block`, 2 pages; **snakegame** — keyboard-driven timer game; drive them if time permits.

Drivers from older campaigns exist for several of these
(`/home/user/reflex/prerelease-testing/2026-09-18-v0.9.12a1/up_examples_{a,b,c}/scripts/`,
`/home/user/reflex/prerelease-testing/2026-08-27-v0.9.9a1/up_*/drive_*.py`) — copy and adapt them.

## Procedure per app (do not skip steps)
1. Own venv per app (or per compatible group): `uv --no-config venv --python 3.12 $SB/envs/upgrades_b-<app>`
   then `uv --no-config pip install --python ... -r requirements.txt 'reflex==0.9.12'` (NO prerelease
   flag). Record `uv pip freeze`.
2. Run on 0.9.12 (`--loglevel debug`, log to file), drive all core flows in Chromium, capture console +
   failed requests + screenshots as the baseline; save `.web/package.json`.
3. In-place upgrade of the SAME venv and SAME app dir (`.web/`, `reflex.lock/`, `.states/`, sqlite kept):
   `uv --no-config pip install --python ... --prerelease=allow -U 'reflex==0.10.0a1'`. Record freeze diff.
   Re-run; watch the FIRST run's log; re-drive identical flows; diff `.web/package.json`.
4. Cold run: `rm -rf .web`, run again, re-drive; confirm convergence.
5. For twitter: confirm existing users/tweets survive and the session cookie/login still works after
   upgrade WITHOUT re-logging in (the hydration/client-storage path changed in #7064).
6. For at least local-component and one other app: also run `reflex run --env prod` on the alpha and
   drive the same flows; then `reflex export` and check the zip contents sanity (frontend + backend).

Report every difference between 0.9.12 and 0.10.0a1 as at least an anomaly. Only-on-alpha = regression.
