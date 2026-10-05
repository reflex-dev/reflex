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

## Probe 5 — #7136 reserved names: downstream scan and behavior matrix (`reserved_scan.py`, `reserved_names_probe.py`, `mixin_get_delta_probe.py`, `reserved_names.log`)

`reserved_scan.py` walks every `class X(...State)` in reflex-examples, the enterprise demos and the
enterprise package with `ast` and intersects declared members with `reflex.istate.validation._reserved_state_members()`
(92 names on 0.9.12a1). **One hit in all of downstream:** `reflex_enterprise/auth/oidc/state.py`
`OIDCAuthState.get_delta` — and that override is decorated with reflex's private
`@rx.state._override_base_method`, which `_validate_state_name` honors, so it passes (verified with an
enterprise-shaped mixin in `mixin_get_delta_probe.py`: unmarked override → `EventHandlerShadowsBuiltInStateMethodError`
on both versions; marked → OK). No `deps=["router"]` and no `rx_router_*` declarations anywhere downstream.
So FINDING-001 is purely the metaclass conflict; note that enterprise depends on the private
`_override_base_method` helper staying importable from `reflex.state`.

Behavior matrix (`reserved_names_probe.py`), 0.9.11.post1 → 0.9.12a1:

| declaration on an `rx.State` subclass | 0.9.11.post1 | 0.9.12a1 |
|---|---|---|
| `def get_delta(self)` unmarked | `EventHandlerShadowsBuiltInStateMethodError` | same |
| `def get_delta` with `__override_base_method__` | OK | OK |
| `_get_was_touched: bool = False` | OK (but persistence silently stopped — #7132) | **`StateValueError: State name `_get_was_touched` is reserved by BaseState`** |
| `def process(self)` | OK | OK (not a framework member) |
| `dirty_vars: list[str] = []` | OK (silently shadowed bookkeeping) | `StateValueError ... reserved` |
| `def get_value(self)` | shadows error | same |
| `router: str = "x"` | OK (silently shadowed) | `StateValueError: State name `router` is reserved` |
| `@rx.var def router` | `ComputedVarShadowsBaseVarsError` | `StateValueError ... reserved` |
| `def add_field(self)` | OK | `EventHandlerShadowsBuiltInStateMethodError` |
| `substates: int = 0` | OK (silently shadowed) | `StateValueError ... reserved` |
| `def set(self)` / `def dict(self)` | shadows error | same |

All new rejections are clear, name the offending member and say to rename it — consistent with the
#7136 breaking-change entry. The one inconsistency is #7132's bug-fix entry ("Keep saving state to disk
and Redis when a state defines a var named `_get_was_touched`"): on the published 0.9.12a1 such a state
cannot be declared at all, so the entry describes unreachable behavior (FINDING-002).
