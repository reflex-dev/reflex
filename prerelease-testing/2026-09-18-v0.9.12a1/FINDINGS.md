# Findings — reflex 0.9.12a1 pre-release testing (2026-09-19)

Independent end-to-end exploration of the `r/pre-2026.09.18-35410916948` release train. All installs
PyPI-only in isolated uv venvs (never from a checkout); every sample app run for real (`reflex run`, dev
and prod) and driven in headless Chromium via Playwright with server-log / console / network / websocket
capture; claimed issues re-reproduced by independent adversarial verifier agents from the written repro
alone. Baselines against the previous stable, reflex 0.9.11.post1. Orchestrator + 15 explorer agents +
one verifier per cluster with claims (Opus 5, xhigh effort), two at a time.

**Campaign status: IN PROGRESS** — this file is updated as clusters finish. Sections marked _(pending)_
are not yet written.

## Versions under test (all published on PyPI, verified with check_release_versions.py)

New in this train (alphas): reflex 0.9.12a1, reflex-base 0.9.12a1, reflex-components-code 0.9.6a1,
-core 0.9.10a1, -dataeditor 0.9.3a1, -gridjs 0.9.2a1, -markdown 0.9.4a1, -plotly 0.9.7a1, -radix 0.9.10a1,
-recharts 0.9.4a1, -sonner 0.9.4a1. Already stable, unchanged: moment 0.9.4, lucide 1.0.4, react-player
0.9.2, docgen 0.9.5, hosting-cli 0.1.72, otel 0.1.0, release 0.1.1, build-sdk 0.0.2 (first release of the
renamed SDK). Published reflex-enterprise: 0.9.5 (requires `reflex[db]>=0.9.6`).

Environment: Linux container (Ubuntu 24.04), 4 CPU / 15 GB, Node v22.22.2, reflex-managed Bun 1.4.0
(system bun 1.3.11 ignored as below the minimum), Python 3.11.15 primary (3.10/3.12/3.13/3.14 and
3.15.0rc2 via uv), Chromium via Playwright 1.63, redis-server 7.0, outbound via an egress proxy.

## Executive summary

_(pending — written when the clusters finish)_

Confirmed so far:
- **FINDING-001 (HIGH, regression, downstream-breaking, CONFIRMED by orchestrator on both versions):**
  `rx.State` gained a new metaclass (`reflex.istate.validation._StateMeta`, from #7136), so any metaclass
  derived from `reflex.vars.BaseStateMeta` — the metaclass `rx.State` had through 0.9.11.post1 — can no
  longer be applied to a State subclass. Published reflex-enterprise 0.9.5 does exactly that in
  `auth/oidc/state.py`, so `import reflex_enterprise.auth.oidc.state` raises `TypeError: metaclass
  conflict` on 0.9.12a1 and imports cleanly on 0.9.11.post1.

Verified changelog claims (orchestrator, not findings): all 19 packages published with wheel + sdist;
122 `.pyi` stubs ship identically in wheel and sdist; the wheel pins `reflex-base==0.9.12a1` exactly and
`reflex-components-moment>=0.9.4`; blank app dev and prod are clean with react-router 8.4.0 (#7202) and
mergician 2.0.2 (#6850) in the generated `package.json`; `reflex-build-sdk` 0.0.2 exposes the renamed
clients and honors `REFLEX_BUILD_BACKEND_URL` over `REFLEX_CLOUD_BACKEND_URL` (#7201); `reflex cloud`
refuses non-interactive use without a token (0.1.72, #6917); reflex-local-auth 0.5.0 and
reflex-global-hotkey 1.2.3 import surfaces resolve on 0.9.12a1.

Index:
- FINDING-001: State metaclass change breaks downstream metaclasses derived from `BaseStateMeta` — reflex-enterprise OIDC auth cannot import (HIGH, regression) — CONFIRMED

## FINDING-001: State metaclass change breaks downstream metaclasses derived from `BaseStateMeta` (HIGH, regression)

- Cluster: `orch_probes` (found by the orchestrator's enterprise import sweep before the fan-out; the
  `ent_mcp_oidc` cluster measures the user-facing blast radius) | Regression vs 0.9.11.post1: **yes** |
  Verifier: orchestrator, both versions, framework-only and enterprise repro
- Repro (framework-only, no enterprise needed) — `orch_probes/metaclass_probe.py`:
  ```
  cd $SB && uv venv envs/shared --python 3.11 && uv pip install --python envs/shared/bin/python --prerelease=allow 'reflex==0.9.12a1'
  envs/shared/bin/python metaclass_probe.py
  ```
  ```python
  from reflex.vars import BaseStateMeta
  class CookieMeta(BaseStateMeta): ...
  class S(rx.State, metaclass=CookieMeta): x: int = 0
  # 0.9.12a1: TypeError: metaclass conflict: the metaclass of a derived class must be a (non-strict)
  #           subclass of the metaclasses of all its bases
  # 0.9.11.post1: works (type(rx.State) is BaseStateMeta)
  ```
  Enterprise repro — `orch_probes/ent_import_probe.py` in a venv with the train +
  `reflex-enterprise[mcp]==0.9.5`: `import reflex_enterprise.auth.oidc.state` → the same TypeError at
  `reflex_enterprise/auth/oidc/state.py:381` (`class OIDCAuthState(ConfigMixin, rx.State, mixin=True,
  metaclass=OIDCCookieMeta)`, with `class OIDCCookieMeta(BaseStateMeta)` at line 347). 22 other enterprise
  modules import fine. `ent_import_probe_prev.py` on 0.9.11.post1: 23/23 import.
- Evidence: `orch_probes/NOTES.md` (probes 1 and 4), the two probe scripts.
- Root cause: #7136 ("Validate reserved state names before registration") made
  `reflex/state.py:629` read `class BaseState(EvenMoreBasicBaseState, metaclass=_StateMeta)` with
  `_StateMeta(BaseStateMeta)` defined in `reflex/istate/validation.py:90`. Two sibling subclasses of
  `BaseStateMeta` cannot both be the metaclass of one class. Deriving from `type(rx.State)` works on
  both versions, but no published downstream code does that today.
- Impact: reflex-enterprise 0.9.5 OIDC auth (`AuthPlugin` OIDC flow, `demos/oidc`) is unusable on
  0.9.12a1; any third-party State metaclass written the same way breaks. Nothing in the changelog
  announces the metaclass change.
- Suggested fix shape (for the maintainers, not applied here): perform the #7136 validation inside
  `BaseStateMeta.__new__` (guarded on "a base is a BaseState") so `rx.State` keeps `BaseStateMeta` as its
  metaclass, or make the validating metaclass compose with sibling `BaseStateMeta` subclasses; and add a
  changelog note either way. Enterprise can independently switch to `class OIDCCookieMeta(type(rx.State))`.

## Refuted / reclassified claims

_(pending)_

## Cluster summaries

### `smoke` (pass 6, anomaly 0, fail 0)
Blank app on the published train: `reflex init` clean; dev server 200 in 10 s with reflex's own Bun 1.4.0;
prod build served in 4 s; zero console/page/network anomalies in both modes; generated `package.json`
carries react-router 8.4.0, mergician v2.0.2, isbot 5.2.2, lucide-react 1.26.0. `smoke/NOTES.md`.

### `packaging` (pass 6, anomaly 1, fail 0)
19/19 packages published; 122 stubs identical in wheel and sdist; pins match the changelog
(`reflex-base==0.9.12a1`, `moment>=0.9.4`); identical all-alpha resolution on Python 3.10–3.14;
third-party import surfaces resolve. Anomaly (pre-existing, issue #7088): the reflex sdist cannot be
built by uv because it still carries the workspace `[tool.uv.sources]`; pip installs it fine.
`packaging/NOTES.md`.

### `orch_probes`
Enterprise import sweep (FINDING-001), build-sdk rename/URL precedence, hosting-cli non-interactive
defaults. `orch_probes/NOTES.md`.

_(other clusters pending)_
