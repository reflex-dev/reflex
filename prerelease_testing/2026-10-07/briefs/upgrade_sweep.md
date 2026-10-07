# Cluster `upgrade_sweep` — 0.9.12 → 0.10.0a2 in-place upgrades (regression sweep) + stock-install smoke

Ports: frontend 3140-3159, backend 8140-8159. Work dir: $SB/apps/upgrade_sweep/. DEST: /home/user/reflex/prerelease_testing/2026-10-07/upgrade_sweep/
Read first: $SB/CAMPAIGN_STATE.md, /home/user/reflex/prerelease_testing/2026-10-06/upgrades_a/NOTES.md and /home/user/reflex/prerelease_testing/2026-10-06/upgrades_b/NOTES.md (procedures + drivers; reuse by copying).

## Do
1. Pick form-designer (reflex[db] + reflex-local-auth, Cookie/LocalStorage), github-stats (LocalStorage), twitter (db +
   session state in Redis) and clock (Cookie) from /home/user/reflex/prerelease_testing/2026-10-06/upgrades_a/ and /home/user/reflex/prerelease_testing/2026-10-06/upgrades_b/ (their copied sources + drivers), and
   repeat the procedure: fresh venv 'reflex==0.9.12' + requirements → drive → in-place upgrade to
   `--prerelease=allow -U 'reflex==0.10.0a2' 'pydantic<2.14'` → drive the identical flows → cold rebuild → drive. This time
   ALSO compare the alpha2 run against the saved 0.10.0a1 results in the 10-06 dirs: anything that was fine on a1 and breaks
   on a2 is a new regression. Watch the first run after upgrade for the lockfile migration and the package.json diff
   (every component package should now move, per #7464).
2. Because #7460 touched client-storage hydration: for github-stats/clock/form-designer confirm that the LocalStorage/Cookie
   values written under 0.9.12 are restored after the upgrade AND that no default values are newly written to storage on
   first load (inspect localStorage/cookies after the first alpha2 load).
3. Stock-install smoke, as a brand-new user would: `uv venv --python 3.12` + `uv pip install --prerelease=allow reflex==0.10.0a2`,
   `reflex init --template blank`, `reflex run` (dev) and `reflex run --env prod`, drive in Chromium; record the resolved
   graph (`uv pip freeze`) and the generated .web/package.json pins.
Copy artifacts to DEST as you go.
