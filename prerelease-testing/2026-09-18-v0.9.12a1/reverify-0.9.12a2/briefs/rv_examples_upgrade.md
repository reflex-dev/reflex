# rv_examples_upgrade — upgrade regression subset 0.9.11.post1 → 0.9.12a2 on reflex-examples apps
Ports: frontend 3260-3279 / backend 8260-8279. Scratch: $SB/reverify/rv_examples_upgrade/. Notes dir: reverify-0.9.12a2/rv_examples_upgrade/.
Protocol: `/home/user/reflex/prerelease-testing/2026-09-18-v0.9.12a1/briefs/UPGRADE_PROTOCOL.md` and the
`up_examples_a/b/c` NOTES.md (which apps, which flows, what drivers). Example sources: the campaign kept copies under
`up_examples_*/` (check) or clone `https://github.com/reflex-dev/reflex-examples` into scratch.

Pick three apps that span the surface, preferring ones the campaign already has drivers for:
(a) the `reflex-local-auth` app (third-party package + auth flows), (b) a `reflex[db]` / API app (e.g. the one with
sqlite + `/_reflex` REST or `customer_data_app`/`form-designer`), (c) `data_visualisation` (recharts/plotly/pandas,
the campaign's `/pandas` probe page).
For each: (1) fresh venv with the PREVIOUS stable (`reflex==0.9.11.post1`, no prerelease flag) + the app's requirements,
run, drive the real flows (baseline); (2) upgrade the SAME venv and SAME app dir in place to a2 with
`uv pip install --prerelease=allow reflex==0.9.12a2 reflex-base==0.9.12a2 <every component alpha named>` (see
RV_BRIEF.md), keep `.web/` and `reflex.lock/`, watch the first run's log (migration), re-drive the identical flows,
compare; (3) one cold run (`rm -rf .web`) for one of the apps; diff `.web/package.json` before/after.
Also run the mixed-version trap once deliberately (`uv pip install --upgrade reflex==0.9.12a2` without the flag) on a
throwaway venv and record what resolves — the release notes will need to tell users to name the component alphas (or
the final release will make this moot); report the resolved graph.
Any flow that passed on 0.9.11.post1 and fails on a2 is a regression → new issue with the four channels; known
example-app bugs from the campaign (form-designer `/form/<id>` crash, missing alembic dirs) are pre-existing.
Write the pass/fail table in NOTES.md and return it in the structured result.
