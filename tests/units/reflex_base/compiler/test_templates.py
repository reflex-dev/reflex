"""Tests for reflex_base.compiler.templates."""

from reflex_base.compiler.templates import _sort_hooks
from reflex_base.constants import Hooks
from reflex_base.vars.base import VarData

_INTERNAL = VarData(position=Hooks.HookPosition.INTERNAL)


def test_sort_hooks_merges_field_subscriptions_per_state():
    """Each state gets one hook that lists every field the component reads."""
    internal, _, _ = _sort_hooks({
        'const s = useStateContext("s", ["a"])': _INTERNAL,
        'const t = useStateContext("t", ["x"])': _INTERNAL,
        'const s = useStateContext("s", ["b", "a"])': _INTERNAL,
        "const other = useOther()": _INTERNAL,
    })
    assert internal == [
        'const s = useStateContext("s", ["a", "b"])',
        'const t = useStateContext("t", ["x"])',
        "const other = useOther()",
    ]


def test_sort_hooks_whole_substate_subscription_wins():
    """A hook without a field list reads the whole substate, in either order."""
    for hooks in (
        ['const s = useStateContext("s", ["a"])', 'const s = useStateContext("s")'],
        ['const s = useStateContext("s")', 'const s = useStateContext("s", ["a"])'],
    ):
        internal, _, _ = _sort_hooks(dict.fromkeys(hooks, _INTERNAL))
        assert internal == ['const s = useStateContext("s")']
