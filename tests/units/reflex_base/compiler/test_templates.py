"""Tests for reflex_base.compiler.templates."""

from reflex_base.compiler.templates import (
    _merge_state_hooks,
    _render_hooks,
    vite_config_template,
)
from reflex_base.constants.state import FIELD_MARKER
from reflex_base.plugins import VitePluginEntry
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
    assert rendered == "\n".join([
        f'const {state_var} = useStateContext("{FieldHookState.get_full_name()}", {fields})',
        f"const parentRead = {state_var}.a{FIELD_MARKER}",
        f"const childValue = {state_var}.b{FIELD_MARKER}",
    ])


_VITE_CONFIG_KWARGS = {
    "base": "/",
    "hmr": True,
    "force_full_reload": False,
    "experimental_hmr": False,
    "sourcemap": False,
}
_VITE_IMPORTS_ANCHOR = (
    'import safariCacheBustPlugin from "./vite-plugin-safari-cachebust.js";\n'
)
_VITE_PLUGINS_ANCHOR = "    reactRouter(),\n"


def _vite_config_with(
    imports: str, calls: str, *, after_imports: str = _VITE_IMPORTS_ANCHOR, **kwargs
) -> str:
    """Build the expected vite.config.js from the one rendered without plugins.

    Args:
        imports: The import lines the plugins add.
        calls: The lines the plugins add to the ``plugins`` array.
        after_imports: The line of the plugin-free file the imports follow.
        kwargs: Template arguments on top of the defaults.

    Returns:
        The plugin-free file with ``imports`` and ``calls`` inserted.
    """
    baseline = vite_config_template(**_VITE_CONFIG_KWARGS, **kwargs)
    head, imports_anchor, rest = baseline.partition(after_imports)
    body, plugins_anchor, tail = rest.partition(_VITE_PLUGINS_ANCHOR)
    assert imports_anchor
    assert plugins_anchor
    assert _VITE_PLUGINS_ANCHOR not in tail
    return head + imports_anchor + imports + body + calls + plugins_anchor + tail


def test_vite_config_template_without_vite_plugins_is_unchanged():
    """No entries render the same file as omitting the argument."""
    assert vite_config_template(
        **_VITE_CONFIG_KWARGS, vite_plugins=[]
    ) == vite_config_template(**_VITE_CONFIG_KWARGS)


def test_vite_config_template_one_vite_plugin():
    """An entry's imports follow the built-in ones; its call precedes reactRouter()."""
    rendered = vite_config_template(
        **_VITE_CONFIG_KWARGS,
        vite_plugins=[
            VitePluginEntry(
                imports=[
                    'import stylex from "./reflex-ui/vite-plugin-stylex.js"',
                    'import { Features } from "lightningcss";',
                ],
                call="""stylex({
  useCSSLayers: true,
  lightningcssOptions: { minify: true, exclude: Features.LightDark },
})""",
            )
        ],
    )
    assert rendered == _vite_config_with(
        'import stylex from "./reflex-ui/vite-plugin-stylex.js";\n'
        'import { Features } from "lightningcss";\n',
        """    stylex({
  useCSSLayers: true,
  lightningcssOptions: { minify: true, exclude: Features.LightDark },
}),
""",
    )


def test_vite_config_template_two_vite_plugins():
    """Entries keep their order, after React Compiler; a shared import is written once."""
    rendered = vite_config_template(
        **_VITE_CONFIG_KWARGS,
        react_compiler=True,
        vite_plugins=[
            VitePluginEntry(
                imports=[
                    'import { Features } from "lightningcss"',
                    'import second from "second-plugin"',
                ],
                call="second({ exclude: Features.LightDark })",
            ),
            VitePluginEntry(
                imports=[
                    'import first from "first-plugin";',
                    '  import { Features } from "lightningcss" ;\n',
                ],
                call="  [first(), first.extra(Features.Nesting)]\n",
            ),
            VitePluginEntry(call='{ name: "inline", config: () => ({}) }'),
        ],
    )
    assert rendered == _vite_config_with(
        'import { Features } from "lightningcss";\n'
        'import second from "second-plugin";\n'
        'import first from "first-plugin";\n',
        "    second({ exclude: Features.LightDark }),\n"
        "    [first(), first.extra(Features.Nesting)],\n"
        '    { name: "inline", config: () => ({}) },\n',
        after_imports='import reactCompiler from "./vite-plugin-react-compiler.js";\n',
        react_compiler=True,
    )
