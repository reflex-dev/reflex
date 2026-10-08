# a4_upgrade_ent — upgrade, third-party and enterprise spot check on reflex 0.10.0a4 (2026-10-08)

Agent `a4_upgrade_ent`. Spot check that the three a4 changes (#7505 state.js storage echo, #7516 metaclass refuses class-level
assignment over a state var, #7513 docs) do not break real apps. Everything installed from PyPI (uv `--no-config`, cwd `$SB`) or,
for enterprise, from the offline a5 wheel by file path. Nothing was installed from or run inside `/home/user/reflex` or
`/home/user/reflex-enterprise`. Every app config / driver carries a venv guard (`QA_EXPECT_VENV` / `TP_EXPECT_VENV` in rxconfig,
`VENV_GUARD` banner in enterprise start scripts, `/scratchpad/envs/driver/` assertion in every Playwright driver).
Host: 4-CPU container shared with `a4_hydration`; one app server set at a time.

```bash
export SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
export W=$SB/apps/a4_upgrade_ent          # this DEST dir mirrors $W (minus .web, dbs, run dirs, pngs); tools/sync_dest.sh copies
```
Ports: upgrades 3600/8600 (form-designer), 3604/8604 + GraphQL stub 8608 (github-stats), 3612 prod (twitter 0.9.12->a4),
3614 prod (twitter a3->a4), redis 8609; third-party 3463/8463 dev, 8467 prod, redis 8469; enterprise auth 3620-3627/8620-8627,
redis 8629, mock IdP 8638 (the a3_ent_auth ports + 280); AG Grid / demos 3470-3479/8470-8479.

Layout: `up/` (upgrades: `bin/`, `scripts/` = a3_upgrade drivers unchanged, app sources with a venv guard added to rxconfig,
`logs/`, `freeze/`, `pkg/`, `shots/`), `tp/` (third-party: `bin/`, `drivers/`, `apps/`, `probes/`, `logs/`, `out/`),
`ent/auth/` (a3_ent_auth copy, ports remapped: `bin/ drivers/ scripts/ src/ a4auth/ logs/ shots/`), `ent/grid/` (a3_ent_grid copy,
ports remapped: `bin/ drivers/ scripts/ src/ out/ logs/`), `tools/`.

## 1. In-place upgrades (reflex-examples apps; a3_upgrade drivers and QA patches, unchanged)

Venvs (`up/bin/build_base_venvs.sh`, freezes `up/freeze/<k>-base.txt`): `$SB/envs/a4_upgrade_ent-{fd,gh,twr}` = Python 3.12,
`-r requirements.txt 'reflex==0.9.12'` (+ `'sqlalchemy<2.1'` for the db apps, exactly as the a3 pass); `a4_upgrade_ent-twa3` = what an
a3 tester had: `--prerelease=allow 'reflex[db]==0.10.0a3' 'pydantic<2.14'`.
Upgrade in place (same venv, app dir, `.web/`, `reflex.lock/`, `reflex.db`, persistent Chromium profile; `up/bin/common.sh upgrade()`):
`uv --no-config pip install --python <venv> --prerelease=allow -U 'reflex[db]==0.10.0a4'` (0.9.12 paths, NO pydantic pin: a user's
graph; pydantic 2.14.0 is now a stable release and the 0.9.12 venvs already resolved it) and `... -U 'reflex[db]==0.10.0a4' 'pydantic<2.14'`
for a3 -> a4 (keeps the a3 tester's graph so only the train packages can move). Note: the a3 pass pinned `pydantic<2.14` on every
upgrade, so these a4 runs differ from the a3 runs by pydantic 2.14.0 vs 2.13.5 on the 0.9.12 paths.

Rerun (one server at a time; each script prints a summary, details in `up/logs/`, `up/shots/<k>/*.json`):
```bash
$W/up/bin/build_base_venvs.sh
$W/up/bin/seq_fd.sh  > $W/up/logs/seq-fd.txt    # form-designer (reflex[db] + reflex-local-auth): 3600/8600; prod 3600
$W/up/bin/seq_gh.sh  > $W/up/logs/seq-gh.txt    # github-stats (+ GraphQL stub up/scripts/github_stub.py on 8608): 3604/8604
$W/up/bin/seq_twr.sh > $W/up/logs/seq-twr.txt   # twitter prod + Redis 8609, 0.9.12 -> a4 (+ rollback to 0.9.12): 3612
$W/up/bin/seq_twa3.sh > $W/up/logs/seq-twa3.txt # twitter prod + Redis 8609, a3 -> a4: 3614
# (up/bin/chain_rest.sh ran gh, twr, twa3 back to back after fd)
```
#7516 static check first: `up/logs/grep_examples_class_writes.txt` — no `<State>.<var> =`, `cls.<var> =`, `type(self).<var> =` or
`setattr(<StateClass>, ...)` anywhere in the 27 reflex-examples apps (commit ebe19ff), so no example app can hit the new TypeError at import.

Freeze diff 0.9.12 -> a4 (every app, `up/freeze/<k>-base-to-up.diff`): reflex/reflex-base 0.10.0a4, reflex-build-sdk 0.1.0a1 (new), components
code/core/gridjs/markdown/moment/plotly/radix/recharts 0.10.0a2, dataeditor/react-player/sonner 0.10.0a1, lucide 1.1.0a1, hosting-cli 0.2.0a1,
sqlalchemy 2.0.54 -> 2.1.4, wrapt 2.5.0 (github-stats had no `[db]` before: + alembic, greenlet 3.5.6, sqlmodel, ...) = the a3 diff with reflex/reflex-base at a4.
`uv pip check` clean. `.web/package.json` diff after the first a4 run (`up/pkg/<k>-base-to-up.package.diff`) is byte-identical to the a3 pass's
for form-designer and github-stats (react 19.2.8->19.3.0, react-error-boundary 6.1.6, socket.io-client 4.8.4, autoprefixer 10.6.1, postcss 8.5.29,
vite 8.3.2, + moment 2.31.0 in form-designer). Cold rebuild (`rm -rf .web`) = identical package.json and file list.

| app / run | a4 result (pass/fail/anomaly) | a3 pass (same flow) | notes |
|---|---|---|---|
| form-designer 0.9.12 `full` / `entry` | 18/0/2 / (entry run on a4 only) | 18/0/2 | anomalies = app's login auto-redirect (pre-existing) |
| form-designer a4 in place `up` / `entry` | **12/0/1 / 14/0/1** | 12/0/1 / 14/0/1 | protected editor rendered from the 0.9.12-written `_auth_token` (local-auth LocalStorage) without login |
| form-designer a4 prod `up` / `entry` | **12/0/1 / 15/0/0** | 12/0/1 / 15/0/0 | prod routes `/edit/form/1` `/form/1` `/responses/1` 200, `/nope` 404, `/login` 307 (same) |
| form-designer a4 cold `up` | **12/0/1** | 12/0/1 | |
| github-stats 0.9.12 `fresh` | 14/0/2 | 14/0/2 | anomalies pre-existing (widget dark appearance, React value-without-onChange) |
| github-stats a4 in place `persist` | **12/0/2** | 12/0/2 | users + stats restored from 0.9.12-written LocalStorage |
| github-stats a4 prod `persist` / cold `fresh` | **13/0/1 / 14/0/2** | 13/0/1 / 14/0/2 | |
| twitter prod+Redis 0.9.12 `base` | 19/0/2 | 19/0/2 | anomalies = app's `bg.svg` 404s (pre-existing) |
| twitter stale tab across stop -> upgrade -> a4 | **8/0/3** | 8/0/3 | old tab keeps working against a4, session kept; F-019 log-only version warning |
| twitter a4 prod `up` with the 0.9.12 tokens | **12/0/2** | 12/0/2 | **0.9.12-pickled Redis sessions load on a4** (alice, bob logged in without re-login, rows intact) |
| twitter a4 prod `base` (new users) | **19/0/2** | 19/0/2 | |
| twitter rollback to 0.9.12 on the same Redis | 11/1/2 | 11/1/2 | same as a3: a4-modified session discarded silently, the FAIL is the driver's "every session resets" expectation |

Storage on the first a4 load of the 0.9.12-written profiles (`storage_probe.py --forbid-writes`): 0 changing app writes in both apps;
form-designer: 1 idempotent `setItem _auth_token` (same value); github-stats: idempotent rewrites of `selected_users_json` x1, widget
`user_stats_json` x1, `last_fetch` x1 and `user_stats_json` x292 in 8 s (app's refetch loop for the unknown user `ghost1`; a3 pass 208, a2 147)
— identical in kind to a3 (O-3). Expected: #7505 only suppresses echo writes for `sync=True` LocalStorage vars and every LocalStorage var in
these apps (local-auth `auth_token`, github-stats' four) is `sync=False`, which a4 writes exactly as a3 did.
Server logs: same signatures as the a3 pass (form-designer pydantic serializer UserWarning from the app's model + vite console relays; github-stats
`Attempting to send delta to disconnected client` 579 in the in-place dev run vs a3 359 — scales with the refetch-loop count above —,
`RouterData.page` deprecation; twitter: granian's 9-workers-on-4-CPUs warning (O-4), F-019 `Frontend version 0.9.12 ... does not match`).
0 tracebacks, 0 TypeError in any a4 log (no #7516 hit). Shutdown: a4 exits 2-3 s after SIGTERM, ports free; 0.9.12 dev leaves the node
process on the frontend port (known, fixed since a1).
