# a3_events_tp — events suite + third-party sweep on reflex 0.10.0a3 (2026-10-07, a3 pass)

Status: IN PROGRESS (this file is updated after every sub-test; another session can continue from it).

Versions: under test `$SB/envs/a3` (reflex/reflex-base 0.10.0a3); comparisons `$SB/envs/alpha2` (0.10.0a2 + greenlet),
`$SB/envs/stable` (0.9.12 + greenlet). Driver venv `$SB/envs/driver` (Playwright, Chromium /opt/pw-browsers/chromium).
`SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad`
Ports: evapp dev FE 3460 / BE 8460 / proxy 8462; evapp prod 8465 (FE=BE) / proxy 8466; mini dev 3470/8470/proxy 8472;
mini prod 8475 / proxy 8476; redis 8469. Third-party apps: see section 3.

## 1. Events suite (copied from `../../2026-10-07/events/`, work dir `$SB/apps/a3_events_tp/events`)
Changes vs the a2 copy: paths (`apps/events2` -> `apps/a3_events_tp/events`), redis port 8479 -> 8469, a venv guard in
`src/evapp/evapp/evapp.py` and `src/mini/mini/mini.py` (asserts `/scratchpad/envs/$EV_EXPECT_VENV/` in `reflex.__file__`;
`bin/start.sh` exports `EV_EXPECT_VENV=<venv>`; the server log prints `VENV_GUARD ok venv=...`), `bin/suite.sh` takes an
optional 5th argument (comma list of test functions, e.g. `t_deco,t_bind`).

### Rerun
```bash
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
W=$SB/apps/a3_events_tp/events   # copy of DEST/events (src driver tools bin probes)
bash $W/bin/start.sh a3 dev a3_dev evapp && bash $W/bin/wait_up.sh http://localhost:3460/
bash $W/bin/suite.sh a3_dev http://localhost:3460 8460      # all groups
bash $W/bin/stop.sh a3_dev
bash $W/bin/start.sh a3 prod a3_prod evapp && bash $W/bin/wait_up.sh http://localhost:8465/
bash $W/bin/suite.sh a3_prod http://localhost:8465 8465 && bash $W/bin/stop.sh a3_prod
```

### Results so far
(pending)
