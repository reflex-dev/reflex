# Campaign state (compact context) — re-verification on train r/pre-2026.10.06-37579583012

## Trains
- Previous train (tested 10-05/10-06): reflex 0.10.0a1 + components 0.10.0a1 + enterprise 0.9.7a4 (PyPI).
- NEW train `origin/r/pre-2026.10.06-37579583012` (all 20 packages published, wheel+sdist): reflex/reflex-base
  0.10.0a2; components code/core/gridjs/markdown/moment/plotly/radix/recharts 0.10.0a2; dataeditor 0.10.0a1;
  react-player 0.10.0a1; sonner 0.10.0a1; lucide 1.1.0a1; docgen 0.10.0a2; hosting-cli 0.2.0a1 (supersedes
  0.1.73a1, which reflex now excludes with `!= 0.1.73a1`); build-sdk 0.1.0a1; release 0.2.0a1; otel 0.2.0a1
  (requires reflex-base 0.10); hatch-reflex-pyi 0.10.0a1. **Python 3.10 dropped (requires >=3.11).**
  Sibling floors now point at the new train (reflex requires components-* >= their 0.10 alphas).
  `sqlmodel` cap lifted (`sqlmodel >=0.0.24`, #7462 — NOTE: no changelog fragment mentions #7462).
- Enterprise: user-supplied OFFLINE wheel `reflex_enterprise-0.9.7a4` (bypasses the login gate) at
  `$SB/downloads/enterprise_wheel/reflex_enterprise-0.9.7a4-py3-none-any.whl` — use it instead of PyPI.
  It still contains `_compat.py`; the enterprise source checkout at /home/user/reflex-enterprise is on
  `r/pre-2026.10.05` (read-only reference).
- Fix commits in the new train aimed at our findings: #7460 (boot-hydration client-storage writes +
  computed-var writes delivered), #7461 (class-default assignment preserves descriptors; ComponentState
  `cls.count = 10` defaults), #7465 (double-underscore names are plain attributes unless `rx.field()`),
  #7456 (`BackendVarFormatError` when a backend var is formatted into a string), #7462 (SQLModel UTC
  datetime migrations without downgrades), #7464 (sibling floors), #7449 (drop 3.10), #7359 (AppHarness
  forgets states of all app modules), plus a documented breaking-change entry for class-level backend var
  reads returning `Field` (#7312 misc entry).

## Findings from the 10-06 campaign to re-verify (full text: /home/user/reflex/prerelease_testing/2026-10-06/FINDINGS.md)
| id | sev | status on a1 | expected on a2 | repro assets (under prerelease_testing/2026-10-06/) |
|---|---|---|---|---|
| F-001 class-level backend var read → Field; enterprise AG Grid model wrapper 500 (`wrapper.py:153 __data_source_params_class__`) | HIGH | confirmed regression | core semantics KEPT but documented; dunder names now plain attrs (#7465) so enterprise /model should work; formatting into f-string → BackendVarFormatError (#7456) | thirdparty/verification/classattr/scripts/derive_a.py, e2e_app; ent_demos/partial (ag_grid demo, out/ag_grid_dev_alpha/ag_grid-smoke.json) |
| F-002 first-load client-storage default write-back | HIGH | confirmed regression | fixed by #7460 | hydration/verification/f1-client-storage-defaults/apps/f1combo + drivers/f1_check.py; hydration/mini_writeback + scripts/mini.sh |
| F-003 computed-var rewrite of client storage during hydration dropped | MED | confirmed (partial regression) | fixed by #7460 ("deliver changes ... made by computed vars during hydration") | thirdparty/verification/clientstorage-hydrate/apps/cvstore, bin/start.sh, drivers/drive_cvstore.py; apps/google_auth_demo + drivers/drive_google_auth.py |
| F-004 class-level assignment to declared backend var replaces descriptor | MED | confirmed regression | fixed by #7461 | thirdparty/verification/classattr/scripts/derive_b.py, derive_b_reset.py |
| F-005 sqlmodel<0.0.45 cap | MED | confirmed regression | cap lifted (#7462); migrations with UTCDateTime must work | upgrades_a/verification/sqlmodel-datetime/ (dt_matrix_probe.py, dtapp); pymatrix_install/apps/dbmig |
| F-006 component floors unchanged | MED | release-eng | fixed by #7464 (floors) — verify `pip install -U --pre reflex==0.10.0a2` pulls components | pymatrix_install/freeze/*, apps/formapp + scripts/drive_form.py |
| F-007 reflex run under npm hangs on SIGTERM | MED | pre-existing, unverified | unknown | pymatrix_install/scripts/npm_sigterm_repro.sh |
| F-008 >1MB client storage reconnect storm | MED | pre-existing | unknown | hydration/hydapp, drivers/hyd_driver.py --only s5 |
| F-010 pre-connect nav runs old page on_load | LOW | pre-existing race | unknown | hydration/drivers/prenav_test.py; verification/f6-prenav-onload |
| F-011 forward-ref annotation cryptic TypeError | LOW | regression | unknown | pymatrix_install/apps/fwdref_app, scripts/fwdref_tb.py |
| F-012 PageContext.get() bare LookupError | LOW | not regression | unknown | thirdparty/verification/classattr/scripts/derive_c.py |
| F-013 rx.Model deprecation warning location | LOW | not regression | unknown | thirdparty/verification/classattr/scripts/derive_d/derive_d.py |
| F-014 `reflex component` message | LOW | — | unknown | `reflex component --help` |
| F-015 #7093 notice printed twice | LOW | — | unknown | pymatrix_install/logs/3a-npm-run2-plain.log repro |
| F-016 ty 0-arg / 5-arg typing | LOW | — | unknown | pymatrix_install/apps/typing_fixture |
| F-017 redis restart token loss after granian panic | LOW | 1/9 | unknown | hydration/drivers/reconnect_driver.py |
| F-018 React 19.3 extra console error | LOW | — | unknown | thirdparty/apps/tp_components /clerk |
| F-019/020 stale frontend signal; upgrade under running server | LOW | pre-existing | n/a | — |
Partial-cluster leads (unverified): see FINDINGS.md "Partial clusters" (ent_demos, dataeditor_components, events_vars, ent_auth_mcp_redis) and each cluster's `partial/` dir.

## Environment
- SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad (old path; still used; writable)
- venvs (read-only shared): $SB/envs/alpha2 (reflex[db]==0.10.0a2 + hosting-cli 0.2.0a1, py3.12),
  $SB/envs/alpha2-ent (alpha2 + offline enterprise wheel [mcp] + oidc-provider-mock), $SB/envs/alpha
  (0.10.0a1, previous train, for before/after), $SB/envs/stable (0.9.12), $SB/envs/driver (playwright).
- Artifact root for this phase: /home/user/reflex/prerelease_testing/2026-10-07/ (branch claude/reflex-prerelease-testing-t0sd90).
