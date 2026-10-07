# Item `a3_hydration` — reverify_hydration suite + reflex#7493 boot-echo regressions on reflex 0.10.0a3

Date 2026-10-07 (evening). Under test: **reflex 0.10.0a3 / reflex-base 0.10.0a3** (PyPI) in the shared read-only venv
`$SB/envs/a3`. Baselines: `$SB/envs/alpha2` (0.10.0a2), `$SB/envs/stable` (0.9.12), positive controls on `$SB/envs/alpha`
(0.10.0a1, had F-002/F-003). Browser: Playwright + `/opt/pw-browsers/chromium` from `$SB/envs/driver`.
Nothing installed from / run inside a checkout: apps run from `$W/run/<name>` and assert that `reflex.__file__` is under
`/scratchpad/envs/$RVH_VENV/` (env var set by `scripts/srv.sh`). Ports: 3140-3159 / 8140-8159, redis 8149.

(INTERIM — being written while testing; sections marked TODO are not done yet.)

```bash
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; W=$SB/apps/a3_hydration
NP="env NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1"; DRV=$SB/envs/driver/bin/python
# W is a copy of this folder (cp -r src drivers scripts probes cv srv.sh into $W); scripts hard-code W.
```

## Layout
* `src/` — apps copied from `../../2026-10-07/reverify_hydration/src` (hydapp, f1combo, v2/f1combo, f1plain,
  mini_writeback, cvstore, csbox, google_auth_demo) + **new `src/bootecho`** (#7493 probe app, see §2).
* `scripts/srv.sh start <name> <venv> <dev|prod> <src> <FP> <BP> [ENV=VAL...]` / `stop <name>` (ports limited to my range).
  `scripts/run_f002.sh`, `run_be.sh`, `run_storm.sh`, `build_venvs.sh` — one-command runners (see sections).
* `drivers/` — reverify_hydration drivers (unchanged except redis port 8149) + new `bootecho_check.py`, `sync_race.py`.
* `results/` — JSON per run; `trimmed/` — trimmed server logs.

## Venvs (PyPI only, cwd=$SB, `uv --no-config`, Python 3.12) — `scripts/build_venvs.sh`
* `$SB/envs/a3_hydration-tp-a3`: `reflex[db]==0.10.0a3 reflex-base==0.10.0a3 reflex-local-auth==0.5.0 reflex-google-auth==0.2.0 'google-api-python-client>=2.184.0' 'pydantic<2.14'` (greenlet 3.5.6 came via the db extra)
* `$SB/envs/a3_hydration-tp-a2`: same with `reflex[db]==0.10.0a2 reflex-base==0.10.0a2 'greenlet>=3.3'`
* `$SB/envs/a3_hydration-tp-s912`: same with `reflex[db]==0.9.12 'greenlet>=3.3'`

## 0. Positive controls
| control | result |
|---|---|
| F-002 `f1_check.py` on f1combo prod, **0.10.0a1** (`$SB/envs/alpha`), fresh profile | **detects the bug**: LS `cu_ls,wt_ls,wu_ls,wu_sync`, SS `cu_ss,wu_ss`, cookies `cu_ck,wu_ck` written; root of boot delta without `is_hydrated_rx_state_` (`results/posctl/f1combo_a1_prod_fresh.json`) — identical to the 10-06 a1 row |
| same on a2 prod | nothing written (only `theme=system`) |

## 1. F-002 (first load persists client-storage defaults) on a3
`scripts/run_f002.sh <venv> <mode> <label> <FP> <BP>`: f1combo fresh ×2, returning visitor (same build), `f1_sync_tabs.py`,
restart with `src/v2/f1combo` (every default changed), returning visitor, fresh v2.

| check | a2 prod (rerun today) | **a3 prod** | a3 dev | 0.9.12 (10-06) |
|---|---|---|---|---|
| fresh ×2: storage written | nothing | **nothing** | TODO | nothing |
| v1 visit → v2 build → returning | all v2 values | **all v2 values** | TODO | v2 |
| `f1_sync_tabs.py` (B2 socket held 2.5 s) | converges `sync-from-tabA`, no revert | **same** | TODO | — |

Boot delta root carries `is_hydrated_rx_state_: false` on a3 (unchanged from a2).

## 2. #7493-specific: `src/bootecho` + `drivers/bootecho_check.py`
App: `Prefs` (LS sync=True `be_theme`, LS `be_note`, SS `be_sess`, Cookie `be_ck`, Cookie `be_ckopt` path=/ max_age=3600
same_site=strict, cached cv `theme_upper`, uncached cv `note_len`, cv `ck_combo`, logging `get_delta` override),
substate `SubPrefs` (LS + Cookie max_age 7200 lax, cv `sub_combo`, own override), `Guard` (LS `be_tok`; override
sanitises a `bad*` value to `""` in the delta = an auth-like filter), `Srv` (on_load page `/onload` sets LS+Cookie),
`/plainload` (no-op on_load), two `Box` ComponentState instances (LS + Cookie max_age, no `name`).
Every override call prints `BOOTTRACE GD {...}` with the tab token; the driver counts them per load.

Rerun: `$W/scripts/run_be.sh <venv> <dev|prod> <label> <FP> <BP> [ENV=VAL]` (label used: a3dev, a2dev, s912dev, ...).

| check (dev) | a2 | **a3** | 0.9.12 |
|---|---|---|---|
| fresh `/`, `/plainload`: written | nothing | **nothing** | nothing |
| fresh `/onload` | only the on_load values `be_srv`, `be_srv_ck` | same | same |
| returning user (all values set by events) reload: values kept | yes | yes | yes |
| boot inbound frames / deltas / bytes (returning user, `/`) | 4 f / 2 deltas / 3372 B | 4 f / 2 deltas / **4198 B** (+826 B: every browser value echoed once in the final `is_hydrated:true` delta) | 6 f / 4 deltas / 4866 B |
| `get_delta` override sees the browser's storage values at boot | **never** (N-032 mechanism) | **once** (in the final delta) | once (update_vars_internal delta) |
| sanitising override (`be_tok=bad-xyz`) reaches the browser | no (stays `bad-xyz`) | **yes** (`""`) | yes |
| cookie with max_age rewritten at boot (expiry slides) | no | **yes** (+5–8 s after a 3 s wait) | yes |
| on_load server value beats the browser's (`/onload`) | yes | yes (value sent 3×) | yes (3×) |
| computed vars over storage at first `H:yes` | correct | correct | correct |
| console errors / failed requests | none | none | none |

## 3. sync=True LocalStorage across tabs (`drivers/sync_race.py`)
Part R: tab B boots with its inbound websocket messages held 2.5 s (Playwright `route_web_socket`) while tab A changes
the synced value v1→v2. Part S: tab0 + 6 tabs loading concurrently while tab0 changes the value 5× (250 ms apart);
convergence + websocket traffic in a 2 s window 4 s later. Rerun: `$W/scripts/run_storm.sh <venv> dev <runs> 3142 8142 S 6`
or `R`.

| | a2 dev | **a3 dev** | 0.9.12 dev |
|---|---|---|---|
| R: A shows the stale v1 again after its own change | 0/2 (no storage event in A) | **1/2** (A: v2→v1→v2, 2 storage events, 2 extra update_vars_internal) | 2/2 (4 storage events in A) |
| S: endless ping-pong, tabs never converge | **0/10** (always `s5`, ~75 frames) | **6/9** (2–9k storage events per tab, 6–11k frames per 2 s, tabs stuck on mixed s2–s5) | 9/10 |

TODO: prod, longer observation, minimal tab count, mechanism.
