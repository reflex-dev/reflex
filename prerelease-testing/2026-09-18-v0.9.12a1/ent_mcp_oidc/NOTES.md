# Cluster `ent_mcp_oidc` — reflex-enterprise 0.9.5 MCP plugin + OIDC auth on reflex 0.9.12a1

Session: 2026-09-19 (0.9.12a1 pre-release campaign). Everything installed from PyPI plus the
published `reflex_enterprise-0.9.5-py3-none-any.whl`; nothing from the `/home/user/reflex`
checkout. This directory reuses (and extends) the harness the 0.9.11a1 campaign built under
`prerelease-testing/2026-09-10-v0.9.11a1/ent_mcp_oidc/`.

## Headline

**reflex-enterprise 0.9.5 is completely broken on reflex 0.9.12a1.** Any app that uses
`rxe.AuthPlugin()` *or* `rxe.MCPPlugin()` (or imports anything from
`reflex_enterprise.auth.oidc`) dies with

```
TypeError: metaclass conflict: the metaclass of a derived class must be a
(non-strict) subclass of the metaclasses of all its bases
```

at `reflex_enterprise/auth/oidc/state.py:381`. This is a regression introduced by reflex
[#7136](https://github.com/reflex-dev/reflex/pull/7136) ("Validate reserved state names before
registration"), which changed `type(rx.State)` from `reflex_base.vars.base.BaseStateMeta` to the
new `reflex.istate.validation._StateMeta`. rxe declares

```python
class OIDCCookieMeta(BaseStateMeta): ...                       # reflex.vars.BaseStateMeta
class OIDCAuthState(ConfigMixin, rx.State, mixin=True, metaclass=OIDCCookieMeta): ...
```

and `OIDCCookieMeta` is no longer a (non-strict) subclass of `type(rx.State)`.

Once that one class definition is forced through (see the shim below), **everything else in the
MCP and OIDC surface still works**, so this is a single, well-localised break.

## Environments

```
$SB=/tmp/claude-0/-home-user-reflex/4bc251b7-1728-51b6-97f5-dc5c7f35130a/scratchpad
envs/ent       reflex 0.9.12a1 train + reflex-enterprise[mcp] 0.9.5   (see logs/freeze_ent_0.9.12a1.txt)
envs/entprev   reflex 0.9.11.post1 train + reflex-enterprise[mcp] 0.9.5 (logs/freeze_entprev_0.9.11.post1.txt)
envs/driver    playwright 1.63, chromium at /opt/pw-browsers/chromium
```

Recreate an equivalent env from a neutral cwd (never from the checkout):

```
cd $SB && uv venv $SB/envs/ent --python 3.11
uv pip install --python $SB/envs/ent/bin/python --prerelease=allow \
  'reflex==0.9.12a1' 'reflex-components-core==0.9.10a1' 'reflex-components-radix==0.9.10a1' \
  'reflex-components-code==0.9.6a1' 'reflex-components-dataeditor==0.9.3a1' \
  'reflex-components-gridjs==0.9.2a1' 'reflex-components-markdown==0.9.4a1' \
  'reflex-components-plotly==0.9.7a1' 'reflex-components-recharts==0.9.4a1' \
  'reflex-components-sonner==0.9.4a1' \
  "reflex-enterprise[mcp] @ file://$SB/wheels/reflex_enterprise-0.9.5-py3-none-any.whl"
```

Resolved `uv pip freeze | grep reflex` for the 0.9.12a1 env:

```
reflex==0.9.12a1
reflex-base==0.9.12a1
reflex-components-code==0.9.6a1
reflex-components-core==0.9.10a1
reflex-components-dataeditor==0.9.3a1
reflex-components-gridjs==0.9.2a1
reflex-components-lucide==1.0.4
reflex-components-markdown==0.9.4a1
reflex-components-moment==0.9.4
reflex-components-plotly==0.9.7a1
reflex-components-radix==0.9.10a1
reflex-components-react-player==0.9.2
reflex-components-recharts==0.9.4a1
reflex-components-sonner==0.9.4a1
reflex-enterprise @ file:///.../reflex_enterprise-0.9.5-py3-none-any.whl
reflex-hosting-cli==0.1.72
```

## What is in this directory

| Path | What it is |
| --- | --- |
| `apps/mcpapp/`, `apps/authapp/`, `apps/oidcdemo*/` | Unmodified apps from the 0.9.11a1 campaign (kept so the harness stays runnable as-is). |
| `apps12/mcpapp/`, `apps12/authapp/` | The same two apps **plus the metaclass shim import**, so the rest of the surface can be exercised on 0.9.12a1. |
| `apps12/authonly/` | `authapp` package with an `rxconfig.py` that enables **only** `rxe.AuthPlugin()` — proves AuthPlugin alone is enough to break. |
| `scripts2/oidc_meta_shim.py` | The workaround (points `reflex.vars.BaseStateMeta` at `_StateMeta` for the duration of the `reflex_enterprise.auth.oidc.state` import). **A test aid, not a suggested fix.** |
| `scripts2/meta_probe.py`, `blast.py`, `shimtest.py`, `mm.py`, `demo_import.py` | Root-cause / blast-radius probes. |
| `scripts2/drive_auth.py` | Previous campaign's browser driver, with the hardcoded IdP port and output path made configurable. |
| `scripts2/uncached_after_login.py` | **New.** Isolates ISSUE-2 (uncached protected computed var never re-sent after login). |
| `scripts2/twotab_uncached.py` | **New.** Two-tab probe; a negative result (reflex issues a per-tab token, so tabs do not share state) — kept so nobody re-derives it. |
| `scripts/*` | The 0.9.11a1 campaign's MCP drivers, used unchanged. |
| `idp/fake_idp.py` | Self-contained OIDC provider (PKCE S256, refresh, userinfo, RP-initiated logout). |
| `logs/`, `shots/` | This session's evidence (`a2_*`, `uncached_*`, `twotab_*`, `freeze_*`). |

## Exact rerun commands

Ports used this session: frontend 3660 (new) / 3661 (prev), backend 8660-8664, fake IdP 8670.

```
SB=/tmp/.../scratchpad ; A=$SB/apps/ent_mcp_oidc

# 0. root cause, no server needed
cd $A/scripts2 && CI=true $SB/envs/ent/bin/python meta_probe.py       # TypeError: metaclass conflict
cd $A/scripts2 && CI=true $SB/envs/entprev/bin/python meta_probe.py   # IMPORT OK
cd $A/scripts2 && CI=true $SB/envs/ent/bin/python blast.py            # GenericOIDCAuthState FAILs, AuthPlugin()/MCPPlugin()/App() still construct

# 1. ISSUE-1a: MCPPlugin-only app cannot start on 0.9.12a1
cd $A/apps/mcpapp && REFLEX_TELEMETRY_ENABLED=false CI=true \
  $SB/envs/ent/bin/reflex run --backend-only --backend-port 8660      # granian worker dies, /ping never answers
cd $A/apps/mcpapp && REFLEX_TELEMETRY_ENABLED=false CI=true \
  $SB/envs/entprev/bin/reflex run --backend-only --backend-port 8661  # /ping == 200

# 1b. AuthPlugin-only app cannot start either
cd $A/apps12/authonly && REFLEX_TELEMETRY_ENABLED=false CI=true OIDC_ISSUER_URI=http://localhost:8670 \
  OIDC_CLIENT_ID=test-client OIDC_CLIENT_SECRET=test-secret \
  $SB/envs/ent/bin/reflex run --backend-only --backend-port 8664      # -> logs/a2_authonly_new.log

# 2. everything else, with the shim, on 0.9.12a1
cd $A/idp && NO_PROXY=localhost,127.0.0.1 $SB/envs/ent/bin/python fake_idp.py 8670 &
cd $A/apps12/mcpapp && REFLEX_TELEMETRY_ENABLED=false CI=true $SB/envs/ent/bin/reflex run --backend-only --backend-port 8660 &
cd $A/scripts  && NO_PROXY=localhost,127.0.0.1 $SB/envs/ent/bin/python mcp_drive.py 8660
cd $A/scripts  && NO_PROXY=localhost,127.0.0.1 $SB/envs/ent/bin/python mcp_probe2.py 8660
cd $A/apps12/authapp && REFLEX_TELEMETRY_ENABLED=false CI=true OIDC_ISSUER_URI=http://localhost:8670 \
  OIDC_CLIENT_ID=test-client OIDC_CLIENT_SECRET=test-secret \
  $SB/envs/ent/bin/reflex run --frontend-port 3660 --backend-port 8662 &
cd $A/scripts2 && NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python drive_auth.py 3660 a2new 8670
cd $A/scripts2 && NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python uncached_after_login.py 3660 new 8670
cd $A/scripts  && NO_PROXY=localhost,127.0.0.1 $SB/envs/ent/bin/python mcp_auth_probe.py 8662

# baseline: same, but envs/entprev, apps/ (no shim), ports 3661/8663
```

## Issues

### ISSUE-1 (CRITICAL, regression) — reflex-enterprise 0.9.5 will not import or run on 0.9.12a1

`reflex_enterprise/auth/oidc/state.py:381` raises `TypeError: metaclass conflict` because
reflex #7136 made `reflex.istate.validation._StateMeta` the metaclass of `BaseState`, and
`OIDCCookieMeta` derives from `BaseStateMeta` only.

Blast radius, all verified on 0.9.12a1 vs 0.9.11.post1:

| Surface | 0.9.11.post1 | 0.9.12a1 |
| --- | --- | --- |
| `import reflex_enterprise.auth.oidc.state` | OK | `TypeError: metaclass conflict` |
| `from reflex_enterprise.auth import GenericOIDCAuthState` | OK | same TypeError (lazy loader re-raises) |
| App with `plugins=[rxe.MCPPlugin()]` — `reflex run` | `/ping` 200 | worker dies in `MCPPlugin.post_compile` -> `build_event_handler_index` -> `is_public_event_handler` -> `auth/enforcement.py:947 is_exempt()` -> imports oidc.state |
| App with `plugins=[rxe.AuthPlugin()]` only | starts | worker dies at the app module's `from reflex_enterprise.auth import ...` |
| shipped `reflex-enterprise/demos/oidc` (imports `reflex_enterprise.auth.oidc.state` directly) | would import | same TypeError |
| `rxe.App()`, `rxe.AuthPlugin()`, `rxe.MCPPlugin()` constructed in isolation; ag_grid / map / dnd / flow / mantine / highcharts / testing imports | OK | still OK (so only OIDC-touching paths break) |

Evidence: `logs/a2_mcpapp.log` (0.9.12a1, first attempt without shim — full traceback),
`logs/a2_authonly_new.log`, `logs/prev_mcpapp.log` (baseline starts),
`scripts2/meta_probe.py`, `scripts2/blast.py`.

Notes for whoever fixes it:
* The fix most plausibly belongs in reflex-enterprise (`OIDCCookieMeta` should derive from
  `type(rx.State)` rather than importing `BaseStateMeta`), but 0.9.5 is already published, so
  reflex 0.9.12 shipping as-is bricks every released reflex-enterprise for every user who
  upgrades. Either rxe needs a release, or #7136 needs to keep `type(BaseState)` == `BaseStateMeta`.
* PR #7136's description promises an escape hatch: *"Existing apps can temporarily set
  `REFLEX_STATE_ALLOW_RESERVED_NAMES=1` to retain legacy handling"*. **That environment variable
  does not exist anywhere in the published 0.9.12a1 or in the release branch source**
  (`grep -rn 'ALLOW_RESERVED' site-packages/reflex*/` and
  `git grep ALLOW_RESERVED origin/r/pre-2026.09.18-35410916948` both return nothing). Even if it
  existed it would not help here, because the metaclass is installed unconditionally.

### ISSUE-2 (MEDIUM, regression) — a withheld `cache=False` computed var is never re-sent after it becomes visible

reflex #6946 made `@rx.var(cache=False)` vars remember the last value they *sent*. That memory
is recorded even when the value is dropped from the delta downstream, so after the drop
condition clears the var is considered unchanged and never reaches the browser.

Observed with `rxe.AuthPlugin` and an `@rxe.var(auth=True, cache=False)` var over server-side
data (`PublicState.shared_label` in `apps/authapp`):

```
step                      0.9.11.post1              0.9.12a1
anon_initial              shared=default-shared     shared=default-shared
anon_after_poison_shared  shared=default-shared     shared=default-shared   (withheld, correct)
right_after_login         shared=SERVER-ONLY-SECRET shared=default-shared   <-- STALE
after_unrelated_event     shared=SERVER-ONLY-SECRET shared=default-shared   <-- still stale
after_second_event        shared=SERVER-ONLY-SECRET shared=default-shared   <-- still stale
after_reload              shared=SERVER-ONLY-SECRET shared=SERVER-ONLY-SECRET
```

Repro: `scripts2/uncached_after_login.py <frontend_port> <label> <idp_port>` against
`apps12/authapp` (0.9.12a1 + shim) and `apps/authapp` (0.9.11.post1).
Evidence: `logs/uncached_new.json`, `logs/uncached_prev.json`,
`shots/uncached_new.png`, `shots/uncached_prev.png`; also visible in the full driver run
(`logs/auth_a2new.json` vs `logs/auth_a2prev.json`, step `after_login_click`).

No console errors, no page errors, no HTTP >= 400 in either run — the UI is silently stale.
The generic hazard is "any consumer that filters or drops a var out of a delta after it was
computed", which is exactly what the enterprise auth delta filter does; a plain-reflex app has
no such filter, so this only bites apps with a delta filter (today: reflex-enterprise auth).
I looked for a pure-reflex repro via two browser tabs and could not build one: reflex issues a
**per-tab** client token (`logs/twotab_new.json` shows two different tokens), so tabs do not
share state.

## Behaviour changes that are NOT bugs (record, do not file)

* **Router split (#7068) is visible on the MCP surface.** `reflex://state/vars/State` and every
  `queue_event` delta now carry `rx_router_page`, `rx_router_url`, `rx_router_session`,
  `rx_router_headers`, `rx_router_route_id` instead of a single nested `router` object. Anything
  that parsed the MCP `state/vars` payload for `router` needs updating.
  (`logs/a2_drive_new.log` vs `logs/a2_drive_prev.log`.)
* **MCP-originated events now carry a real client token.** `rx_router_session.client_token` is a
  UUID on 0.9.12a1 where 0.9.11.post1 had `""`. Auth decisions over MCP were unchanged
  (`logs/a2_mcpauth_new.log` vs `..._prev.log`).
* **Uncached computed vars of untouched substates dropped from deltas.** 0.9.11.post1 attached
  `counter_state: {"uncached_marker": ...}` to deltas of events on *other* states; 0.9.12a1 does
  not. This is the intended half of #6946.
* **Delta key ordering** differs again (documented in the changelog under #7087).
* `/_reflex/cookies/sync` answers **405** on 0.9.12a1 and **404** on 0.9.11.post1 — either way
  the browser records two `net::ERR_ABORTED` for it per run. Pre-existing quirk (the
  0.9.11a1 campaign filed it); the status code change is cosmetic.
* `DeprecationWarning: console.debug has been deprecated in version 0.9.9` and
  `DeprecationWarning: @rx.memo on memo_row without explicit annotations` appear on **both**
  versions. Pre-existing.
* The 0.9.11a1 campaign's FINDING-031 / FINDING-032 (MCP resource naming; a withheld protected
  *field* served to an unauthorised MCP caller as its default) still reproduce on both
  versions — unchanged, still enterprise-side.

## Anomaly worth a line

`reflex run` prints `Backend running at: http://0.0.0.0:8664` and keeps running even though the
granian worker died on import and every request fails. The traceback scrolls past above the
"running" banner and the CLI never exits non-zero. Same behaviour on both versions when the app
module raises at import; it made ISSUE-1 look like a hang rather than a crash.
Evidence: `logs/a2_authonly_new.log`.

## Not covered this session

* Prod mode (`reflex run --env prod`) for the enterprise apps — skipped for time; ISSUE-1 blocks
  the stock configuration in either mode, and dev-mode behaviour under the shim was clean.
* The shipped `demos/oidc` app was only import-checked (`scripts2/demo_import.py`), not run:
  it imports `reflex_enterprise.auth.oidc.state` directly and therefore cannot start on
  0.9.12a1 without the shim.
* Enterprise ag-grid / map / dnd / flow / mantine were import-checked only (all OK); their
  end-to-end behaviour belongs to another cluster.
