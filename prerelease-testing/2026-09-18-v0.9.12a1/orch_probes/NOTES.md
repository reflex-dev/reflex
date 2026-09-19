# orch_probes — orchestrator's own probes (2026-09-19)

All probes run against PyPI-installed packages in isolated venvs (never the checkout):

- `$SB/envs/ent`     : reflex 0.9.12a1 train (all component alphas) + `reflex-enterprise[mcp]==0.9.5`
  installed from the published offline wheel (`reflex_enterprise-0.9.5-py3-none-any.whl`).
- `$SB/envs/entprev` : reflex 0.9.11.post1 (stable component packages) + the same wheel.

## Probe 1 — enterprise module import sweep (`ent_import_probe.py`, `ent_import_probe_prev.py`)

Command (from a neutral cwd):

    REFLEX_TELEMETRY_ENABLED=false $SB/envs/ent/bin/python ent_import_probe.py
    REFLEX_TELEMETRY_ENABLED=false $SB/envs/entprev/bin/python ent_import_probe_prev.py

Result on 0.9.12a1: 22 of 23 modules import; **`reflex_enterprise.auth.oidc.state` fails**:

    File ".../reflex_enterprise/auth/oidc/state.py", line 381, in <module>
      class OIDCAuthState(ConfigMixin, rx.State, mixin=True, metaclass=OIDCCookieMeta):
    TypeError: metaclass conflict: the metaclass of a derived class must be a (non-strict)
    subclass of the metaclasses of all its bases

Result on 0.9.11.post1: all 23 modules import (BAD = 0). → **regression, downstream-breaking**.

Mechanism (release source, read-only):
- reflex 0.9.12a1 `reflex/state.py:629`: `class BaseState(EvenMoreBasicBaseState, metaclass=_StateMeta)`;
  0.9.11.post1 had `class BaseState(EvenMoreBasicBaseState)` (metaclass inherited: `BaseStateMeta`).
- `_StateMeta` is defined in `reflex/istate/validation.py:90` as `class _StateMeta(BaseStateMeta)` —
  introduced by #7136 ("Validate reserved state names before registration"; commit message:
  "flatten the validating metaclass").
- reflex-enterprise 0.9.5 `auth/oidc/state.py:26,347`: `from reflex.vars import BaseStateMeta` /
  `class OIDCCookieMeta(BaseStateMeta)`, used as `metaclass=OIDCCookieMeta` on a class whose base
  `rx.State` now has metaclass `_StateMeta`. `OIDCCookieMeta` and `_StateMeta` are sibling
  subclasses of `BaseStateMeta`, so Python cannot pick a most-derived metaclass.

Blast radius: anything importing `reflex_enterprise.auth.oidc` (the `AuthPlugin` OIDC flow, the
`demos/oidc` app, `rxe.auth.*` lazy attributes that resolve into that module). The `ent_mcp_oidc`
cluster measures it end to end. Any third-party package deriving a metaclass from
`reflex.vars.BaseStateMeta` for use on a State subclass is broken the same way.

## Probe 2 — `reflex-build-sdk` 0.0.2 rename and URL precedence (`buildsdk_probe.py`, `buildsdk_probe.log`)

Venv `$SB/envs/buildsdk` = the train + `reflex-build-sdk==0.0.2`. `from reflex_build_sdk import
ReflexBuild, AsyncReflexBuild, ReflexBuildError` works; none of the pre-rename names
(`ReflexCloud`, `AsyncReflexCloud`, `ReflexCloudError`, `Client`, ...) survive as aliases — consistent with
the 0.0.2 "Breaking Changes" entry (#7201); a user of 0.0.1 gets a plain `AttributeError`/`ImportError`.
`REFLEX_BUILD_BACKEND_URL` wins over `REFLEX_CLOUD_BACKEND_URL` (client `base_url` = the BUILD value) — matches
the changelog. The package's loggers (`reflex_build_sdk`, `._base`, `.credentials`) are plain stdlib loggers
propagating to root when reflex's logging is not configured; whether `reflex run` routes them through the
Reflex logger (#7166) is checked by the `dev_server_cli` cluster.

## Probe 3 — `reflex-hosting-cli` 0.1.72 non-interactive defaults

`reflex cloud apps list --json` with stdout piped and no token: exit 1, stdout empty, stderr
`Token is required for non-interactive mode.` / `Unable to list deployments` — the documented 0.1.72
behavior (#6917). Same without `--json`. `reflex deploy --help` shows `--json` and
`-i, --interactive / --no-interactive`.

## Probe 4 — framework-only repro of the metaclass conflict (`metaclass_probe.py`)

    $SB/envs/shared/bin/python metaclass_probe.py   # 0.9.12a1
    $SB/envs/prev/bin/python metaclass_probe.py     # 0.9.11.post1

| declaration | 0.9.11.post1 | 0.9.12a1 |
|---|---|---|
| `type(rx.State)` | `reflex_base.vars.base.BaseStateMeta` (is `BaseStateMeta`) | `reflex.istate.validation._StateMeta` (subclass of `BaseStateMeta`) |
| `class M(BaseStateMeta)` + `class S(rx.State, metaclass=M)` | OK | **`TypeError: metaclass conflict`** |
| same with `mixin=True` (the enterprise shape) | OK | **`TypeError: metaclass conflict`** |
| `class M(type(rx.State))` + `class S(rx.State, metaclass=M)` | OK | OK |

So the break is in reflex itself, independent of enterprise: `reflex.vars.BaseStateMeta` was, through
0.9.11.post1, the metaclass of `rx.State`, and deriving from it was the natural (and only documented-by-
example) way to add class-creation behavior to a state. Any downstream metaclass written that way is
incompatible with 0.9.12a1. `type(rx.State)`-derived metaclasses keep working on both versions, which is
the forward-compatible spelling for downstream code; a framework-side fix that keeps published
reflex-enterprise 0.9.5 working would be to perform #7136's validation inside `BaseStateMeta.__new__`
(guarded on "some base is a BaseState") instead of introducing a second metaclass, or to have
`_StateMeta.__new__`/`BaseStateMeta` resolve the most-derived metaclass automatically.
