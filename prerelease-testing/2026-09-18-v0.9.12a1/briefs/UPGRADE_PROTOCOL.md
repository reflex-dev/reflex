# Upgrade-regression protocol (shared by the `up_*` clusters)

Users upgrade in place; that path has its own failure modes (lockfile migration, stale `.web/`,
state-key changes forcing a frontend recompile, redis pickles from the old schema). For EACH app:

0. Copy the app out of `/home/user/reflex-dev/reflex-examples/<app>` into `$SB/apps/<cluster>/<app>`.
   Read its `requirements.txt`; drop the `reflex...` line (you install reflex yourself) but KEEP the
   third-party packages (`reflex-local-auth`, `reflex-global-hotkey`, `pandas`, `lorem_text`, ...).
   Some apps need network services that are blocked here (yfinance, OpenAI, googletrans,
   launchdarkly, GitHub API) — stub them minimally and record the stub in NOTES.md, or pick the
   app's flows that do not need them.
1. **Baseline:** a fresh venv `uv pip install --python ... 'reflex==0.9.11.post1' <third-party>`
   (NO `--prerelease` flag so requirements resolve as a user's would). `reflex init` if needed,
   `reflex run` on your ports, drive the app's REAL user flows in Chromium (each app: 3–8 concrete
   interactions — add a todo, tick the clock timezone, upload a file, register+login, play a move,
   answer a quiz, etc.) with console/network/server-log capture and screenshots. Save
   `.web/package.json` and `reflex.lock/` listings.
2. **In-place upgrade of the SAME venv and SAME app dir**, preserving `.web/` and `reflex.lock/`:
   `uv pip install --python ... --upgrade --prerelease=allow 'reflex==0.9.12a1' 'reflex-components-core==0.9.10a1' 'reflex-components-radix==0.9.10a1' 'reflex-components-code==0.9.6a1' 'reflex-components-dataeditor==0.9.3a1' 'reflex-components-gridjs==0.9.2a1' 'reflex-components-markdown==0.9.4a1' 'reflex-components-plotly==0.9.7a1' 'reflex-components-recharts==0.9.4a1' 'reflex-components-sonner==0.9.4a1'`
   then ALSO record what a naive `uv pip install --upgrade --prerelease=allow 'reflex==0.9.12a1'`
   alone would have resolved (`--dry-run`) — the previous campaign found it leaves component
   packages at their stable versions. Run again; read the FIRST run's log closely (migration,
   lockfile changes, bun output, warnings). Re-drive the identical flows; compare. Diff
   `.web/package.json` before/after and list every dependency change.
3. **Cold run:** `rm -rf .web` (keep the venv), run again, re-drive; the result must match step 2.
4. Where the app persists state (sqlite db, `.states/`, redis if it uses one), keep the data from
   the baseline run through the upgrade and check it is still readable / migrations apply.
5. Prod mode once per app (`reflex run --env prod` on ONE port) on 0.9.12a1: page loads and one
   flow works.

Report per app: baseline result, upgrade result, cold result, package.json diff, anything the
first post-upgrade run logged. Anything that works on 0.9.11.post1 and not after the upgrade is a
REGRESSION (high). Anything broken on both is pre-existing (note it, lower severity). Remember
this train renamed the router state keys (#7068): a preserved `.web/` from 0.9.11.post1 MUST be
recompiled on the first 0.9.12a1 run — if the old frontend is served, state hydration will show a
version/schema mismatch; check the log and the browser console for exactly what a user would see.
