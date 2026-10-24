# enterprise — reflex-enterprise 0.9.8 on reflex 0.10.1a1 (vs 0.10.0)

Agent notes, written incrementally. SB=/tmp/claude-0/-home-user/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad/qa.
Fixtures copied to `$SB/apps/enterprise/src` (= `prerelease-testing/fixtures/enterprise`), runtime copies in
`$SB/apps/enterprise/work` (`WORK`), own apps/probes in `$SB/apps/enterprise/own` (copied here as `own/`).
Venvs: `new-ent` (reflex 0.10.1a1 + reflex-base 0.10.1a1 + reflex-enterprise[mcp] 0.9.8 + oidc-provider-mock 0.4.8),
`prev-ent` (reflex 0.10.0 + rxe 0.9.8), `driver` (playwright 1.64.1 + httpx + websockets); built for this item with
`own/build_venvs.sh`: `enterprise-drv` (ENT_DRV: reflex 0.10.1a1 + rxe[mcp] 0.9.8 + playwright 1.63 + pytest),
`enterprise-ctrl-a3` (reflex 0.10.0a3 + rxe 0.9.8: N-032 positive control), `enterprise-ctrl-rxe96` (reflex 0.10.0 +
rxe 0.9.6: N-025 positive control), `enterprise-demo-new` (reflex[db] 0.10.1a1 + rxe[mcp] 0.9.8 + faker/pandas/aiosqlite).
Enterprise demos / upstream test pieces come from the checkout `/home/user/reflex-enterprise` (HEAD d90408b =
r/pre-2026.10.05 @ v0.9.7a4; `git diff v0.9.8 HEAD -- demos` is empty, so the demos equal the v0.9.8 tag), copied by
`grid/bin/fetch_demos.sh` / `auth/a4auth/fetch_upstream.sh` into `$WORK` (never into the repo).

Shell preamble used for every command below:
```
export SB=/tmp/claude-0/-home-user/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad/qa
export WORK=$SB/apps/enterprise/work ENT_NEW=new-ent ENT_PREV=prev-ent PREV=prev DRV_VENV=driver ENT_DRV=enterprise-drv
F=$SB/apps/enterprise/src; cd $SB
```

## rxe 0.9.8 changelog (what changed in the enterprise package itself)
`git show v0.9.8:CHANGELOG.md`: ONE entry, #277 — OIDC sign-in failing with an app state mismatch when a login was
started twice in the same tab (double click); later starts reuse the tab's pending state/PKCE pair until a callback
consumes them, logout no longer overwrites them, a mismatch restarts the sign-in once and returns to the page the
sign-in started from. Source diff v0.9.7..v0.9.8: only `reflex_enterprise/auth/oidc/state.py` (+ tests).
Tested by `own/probes/pending_login.py` (see below).

## Results
