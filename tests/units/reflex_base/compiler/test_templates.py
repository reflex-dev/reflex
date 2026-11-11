"""Tests for reflex_base.compiler.templates."""

from reflex_base.compiler.templates import _merge_state_hooks, _render_hooks
from reflex_base.constants.state import FIELD_MARKER
from reflex_base.utils.format import format_state_name
from reflex_base.vars.base import Var, VarData
from reflex_components_core.el.elements.typography import Div

import reflex as rx


class FieldHookState(rx.State):
    """A state whose fields are read by separate hooks."""

    a: int = 1
    b: int = 2


class _ReadsA(Div):
    """Reads ``FieldHookState.a`` in an ``add_hooks`` Var."""

    def add_hooks(self):
        """Read one field of the state.

        Returns:
            The hook that reads the field.
        """
        return [Var(f"const parentRead = {FieldHookState.a}")]


def test_merge_state_hooks_merges_field_subscriptions_per_state():
    """Each state gets one hook that lists every field the component reads."""
    merged = _merge_state_hooks(
        dict.fromkeys([
            'const s = useStateContext("s", ["a"])',
            'const t = useStateContext("t", ["x"])',
            'const s = useStateContext("s", ["b", "a"])',
            "const other = useOther()",
        ])
    )
    assert list(merged) == [
        'const s = useStateContext("s", ["a", "b"])',
        'const t = useStateContext("t", ["x"])',
        "const other = useOther()",
    ]


def test_merge_state_hooks_whole_substate_subscription_wins():
    """A hook without a field list reads the whole substate, in either order."""
    for hooks in (
        ['const s = useStateContext("s", ["a"])', 'const s = useStateContext("s")'],
        ['const s = useStateContext("s")', 'const s = useStateContext("s", ["a"])'],
    ):
        assert list(_merge_state_hooks(dict.fromkeys(hooks))) == [
            'const s = useStateContext("s")'
        ]


def test_render_hooks_declares_a_merged_state_hook_before_its_readers():
    """Two fields read by different hooks merge into the first subscription.

    The parent's added hook reads ``a`` and a child's hook reads ``b``, so the
    merged subscription has to come before both readers.
    """
    b = Var.create(FieldHookState.b)
    child_value = Var(
        _js_expr="childValue",
        _var_data=VarData(hooks={f"const childValue = {b!s}": b._get_all_var_data()}),
    )
    rendered = _render_hooks(
        _ReadsA.create(Div.create(id=child_value))._get_all_hooks()
    )

    state_var = format_state_name(FieldHookState.get_full_name())
    fields = f'["a{FIELD_MARKER}", "b{FIELD_MARKER}"]'
    lines = [line.strip() for line in rendered.splitlines() if line.strip()]
    assert [line for line in lines if state_var in line] == [
        f'const {state_var} = useStateContext("{FieldHookState.get_full_name()}", {fields})',
        f"const parentRead = {state_var}.a{FIELD_MARKER}",
        f"const childValue = {state_var}.b{FIELD_MARKER}",
    ]
