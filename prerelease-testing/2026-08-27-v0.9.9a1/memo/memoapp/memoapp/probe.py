"""Render-count instrumentation helpers.

A "probe" is a span whose rendering domain (page function, @rx.memo body, or
auto-memo wrapper) increments ``globalThis.__renders[name]`` every time that
function component renders. The increment is attached as a VarData hook, so it
is hoisted into whichever compiled function the var ends up rendered in.

``probe()`` opts out of auto-memoization (MemoizationDisposition.NEVER) so the
probe itself is never extracted into its own wrapper — its hook stays in the
enclosing rendering domain, which is exactly what we want to count.
"""

import reflex as rx
from reflex_base.constants.compiler import MemoizationDisposition, MemoizationMode
from reflex_base.vars import VarData


def probe_var(name: str) -> rx.Var[str]:
    """A string var whose hook bumps globalThis.__renders[name] per render.

    Args:
        name: The counter key.

    Returns:
        A Var evaluating to ``name`` carrying the counting hook.
    """
    hook = (
        "globalThis.__renders = globalThis.__renders || {}; "
        f"globalThis.__renders[{name!r}] = (globalThis.__renders[{name!r}] || 0) + 1;"
    )
    return rx.Var(f'"{name}"', _var_data=VarData(hooks={hook: None})).to(str)


def probe(name: str) -> rx.Component:
    """A span that counts renders of its enclosing rendering domain.

    Args:
        name: The counter key.

    Returns:
        A non-memoizable span carrying the counting hook.
    """
    comp = rx.el.span(custom_attrs={"data-probe": probe_var(name)})
    comp._memoization_mode = MemoizationMode(disposition=MemoizationDisposition.NEVER)
    return comp
