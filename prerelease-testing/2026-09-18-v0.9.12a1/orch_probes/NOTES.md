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
