"""Workaround shim for the 0.9.12a1 enterprise OIDC metaclass conflict.

reflex 0.9.12a1 (PR #7136) makes `reflex.state.BaseState`'s metaclass
`reflex.istate.validation._StateMeta` (a subclass of BaseStateMeta).
reflex-enterprise 0.9.5 declares `OIDCCookieMeta(BaseStateMeta)` and then
`class OIDCAuthState(ConfigMixin, rx.State, mixin=True, metaclass=OIDCCookieMeta)`,
which now raises TypeError: metaclass conflict.

Import this module BEFORE anything that imports reflex_enterprise.auth.oidc.state
to point rxe's `BaseStateMeta` name at `_StateMeta` for the duration of that import,
so the rest of the enterprise surface can be exercised on 0.9.12a1.
"""

import reflex.vars as _rxvars

try:
    from reflex.istate.validation import _StateMeta as _NewMeta
except ImportError:  # 0.9.11.post1 and earlier: nothing to do
    _NewMeta = None

APPLIED = False
if _NewMeta is not None and _rxvars.BaseStateMeta is not _NewMeta:
    _orig = _rxvars.BaseStateMeta
    _rxvars.BaseStateMeta = _NewMeta
    try:
        import reflex_enterprise.auth.oidc.state  # noqa: F401
        APPLIED = True
    finally:
        _rxvars.BaseStateMeta = _orig
