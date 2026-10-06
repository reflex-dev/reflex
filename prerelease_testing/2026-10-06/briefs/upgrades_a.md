# Cluster `upgrades_a` — in-place upgrade regression, reflex-examples (set A: third-party + client storage)

Ports: frontend 3140-3159, backend 8140-8159. Work dir: $SB/apps/upgrades_a/. DEST: /home/user/reflex/prerelease_testing/2026-10-06/upgrades_a/

## Why this cluster exists
Users upgrade in place; that path has its own failure modes (lockfile migration, pruned packages, stale
`.web/`, state pickles). The previous campaign upgraded only todo, overkey and basic_crud. The
reflex-examples repo has historically been the richest source of upgrade regressions. Your apps
(copy each from `$SB/downloads/reflex-examples/<app>` into `$SB/apps/upgrades_a/<app>`):

1. **form-designer** — `reflex[db]` + `reflex-local-auth>=0.5.0`, 10 pages, `rx.Cookie`, `rx.call_script`,
   `rx.markdown`, `rx.moment`, `rx.toast`. Flows: register, login, create a form, add fields of several
   types, preview/fill/submit a response, view responses, logout. Known pre-existing app breakages were
   documented in `/home/user/reflex/prerelease-testing/2026-08-27-v0.9.9a1/up_lorem_form/NOTES.md` —
   read it so you don't re-report them as regressions, but DO re-check whether they changed.
2. **reflexle** — `reflex-global-hotkey>=1.2.2`, `rx.memo`, `rx.toast`: play a few guesses with the keyboard.
3. **github-stats** — `rx.LocalStorage`, `rx.recharts`, 2 pages: enter a username (network to GitHub may
   or may not work through the proxy — if not, note it and test what you can: the LocalStorage-backed
   state surviving reload is the important part given the hydration change #7064).
4. **clock** — `rx.Cookie` for timezone; change timezone, reload, verify it sticks.
5. If time permits: **counter**, **traversal**, **json-tree**.

Drivers from older campaigns exist for several of these (`/home/user/reflex/prerelease-testing/2026-09-18-v0.9.12a1/up_examples_{a,b}/scripts/`
and `/home/user/reflex/prerelease-testing/2026-08-27-v0.9.9a1/up_*/drive_*.py`) — copy and adapt them.

## Procedure per app (do not skip steps)
1. Own venv per app: `uv --no-config venv --python 3.12 $SB/envs/upgrades_a-<app>` then
   `uv --no-config pip install --python ... -r requirements.txt 'reflex==0.9.12'` (NO prerelease flag:
   resolve as a stable user would). Record `uv pip freeze`.
2. Run on 0.9.12 (`--loglevel debug`, log to file), drive all core flows in Chromium, capture console +
   failed requests + screenshots as the baseline; save `.web/package.json` and `reflex.lock/` listing.
3. In-place upgrade of the SAME venv and SAME app dir (`.web/`, `reflex.lock/`, `.states/`, sqlite db kept):
   `uv --no-config pip install --python ... --prerelease=allow -U 'reflex==0.10.0a1'`. Record the
   freeze diff (which component packages moved; did pydantic jump to a beta? that is a resolver artifact
   of --prerelease=allow — note it, and ALSO try the user-realistic `pip`-style upgrade in a copy of the venv:
   `uv --no-config pip install --python ... 'reflex==0.10.0a1'` with no prerelease flag, see what resolves).
   Re-run; watch the FIRST run's log closely (that is where the lockfile/bun migration happens);
   re-drive the identical flows; diff `.web/package.json` before/after and list unexpected dependency changes.
4. Cold run: `rm -rf .web` and run again; re-drive; confirm it converges to the same `package.json`.
5. For db apps: confirm existing rows survive and `reflex db migrate` is a no-op or works.

Also exercise, in at least one app, a browser tab that stayed open across the upgrade (stale frontend
talking to new backend): what does the user see? (A version-mismatch prompt is expected; a hang or
silent failure is a finding.)

Report every difference between 0.9.12 and 0.10.0a1 as at least an anomaly. Only-on-alpha = regression.
