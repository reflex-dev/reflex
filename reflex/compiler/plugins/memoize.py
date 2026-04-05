"""MemoizeStatefulPlugin — auto-memoize stateful components with React.memo wrappers.

This plugin replaces the legacy ``StatefulComponent`` wrapping pass. It
participates in the normal single-pass walk via ``enter_component`` and inserts
a per-subtree ``{children}``-pass-through wrapper (``memo(({children}) => children)``)
at each eligible call-site. The wrapped subtree remains in the tree for the
normal walker descent, so downstream plugins (e.g. ``DefaultCollectorPlugin``)
see the original components and collect their imports/hooks as usual.

Each unique subtree shape (by ``_compute_memo_tag``) contributes:

- One ``const <Tag> = memo(({children}) => children)`` declaration, emitted as
  page-level custom code via ``MemoWrapperComponent._get_custom_code``.
- ``useCallback`` hook lines for each non-lifecycle event trigger, emitted into
  ``page_context.hooks`` so the declarations live at the top of the page body.

No shared-stateful-components file is produced.
"""

from __future__ import annotations

import contextlib
import dataclasses
from functools import cache
from typing import Any

from reflex_base.components.component import (
    BaseComponent,
    Component,
    _deterministic_hash,
    _hash_str,
)
from reflex_base.components.memoize_helpers import (
    fix_event_triggers_for_memo,
    invalidate_event_trigger_caches,
)
from reflex_base.constants.compiler import MemoizationDisposition
from reflex_base.plugins import ComponentAndChildren, PageContext
from reflex_base.plugins.base import Plugin
from reflex_base.utils import format
from reflex_base.utils.imports import ImportVar, ParsedImportDict
from reflex_base.vars.base import Var

# --------------------------------------------------------------------------- #
# Tag naming + memoize-eligibility                                            #
# --------------------------------------------------------------------------- #


def _child_var(child: Component) -> Var | Component:
    """Return the core Var of a structural child, for memoize-eligibility checks.

    For special wrappers (``Bare``/``Cond``/``Foreach``/``Match``) we peek at
    the contained Var instead of recursing into the wrapper component itself.

    Args:
        child: The child component to inspect.

    Returns:
        The contained Var if ``child`` is a special wrapper, else ``child``.
    """
    from reflex_components_core.base.bare import Bare
    from reflex_components_core.core.cond import Cond
    from reflex_components_core.core.foreach import Foreach
    from reflex_components_core.core.match import Match

    if isinstance(child, Bare):
        return child.contents
    if isinstance(child, Cond):
        return child.cond
    if isinstance(child, Foreach):
        return child.iterable
    if isinstance(child, Match):
        return child.cond
    return child


def _compute_memo_tag(component: Component) -> str | None:
    """Compute a stable tag name for a memoizable component.

    Returns ``None`` for components that render empty (non-visual components
    are never memoized).

    Args:
        component: The component to name.

    Returns:
        The stable tag name, or ``None`` if the component renders empty.
    """
    rendered_code = component.render()
    if not rendered_code:
        return None
    code_hash = _hash_str(_deterministic_hash(rendered_code))
    return format.format_state_name(
        f"{component.tag or 'Comp'}_{code_hash}"
    ).capitalize()


def _should_memoize(component: Component) -> bool:
    """Decide whether ``component`` is a candidate for auto-memoization.

    Checks for DIRECT triggers only (not walking into descendants): the
    component's own Vars with var_data, event_triggers, or special child
    types (Bare/Cond/Foreach/Match) whose probe Var carries var_data.

    Args:
        component: The candidate component.

    Returns:
        True if the component should be wrapped in a memo definition.
    """
    from reflex_components_core.core.foreach import Foreach

    if component._memoization_mode.disposition == MemoizationDisposition.NEVER:
        return False
    if component.tag is None:
        return False
    if component._memoization_mode.disposition == MemoizationDisposition.ALWAYS:
        return True

    # Direct Vars only (component's own props, style, class_name, id, etc.).
    for prop_var in component._get_vars(include_children=False):
        if prop_var._get_all_var_data():
            return True

    # Special-case structural children that are Var wrappers (Bare/Cond/
    # Foreach/Match). Foreach is always memoized because it produces dynamic
    # child trees that React must reconcile by key.
    for child in component.children:
        if not isinstance(child, Component):
            continue
        if isinstance(child, Foreach):
            return True
        probe = _child_var(child)
        if isinstance(probe, Var) and probe._get_all_var_data():
            return True

    # Components with event triggers are always memoized (to wrap callbacks).
    return bool(component.event_triggers)


# --------------------------------------------------------------------------- #
# MemoWrapperComponent + per-tag subclass factory                              #
# --------------------------------------------------------------------------- #


class MemoWrapperComponent(Component):
    """Call-site ``{children}``-pass-through memo wrapper.

    Renders as ``<{tag}>{children}</{tag}>`` where ``tag`` is a
    subtree-content hash. Emits ``const {tag} = memo(({children}) => children)``
    as page-level custom code and imports ``{memo}`` from react.
    """

    def _validate_component_children(self, children: list[Component]) -> None:
        """Skip parent/child validation — wrapper is transparent.

        The wrapped child's ``_valid_parents`` constraint is already satisfied
        by the original (pre-wrap) parent in the user-authored tree; the
        wrapper is inserted during compilation and should not interpose on
        that relationship.

        Args:
            children: The children of the component (ignored).
        """
        del children

    def _get_imports(self) -> ParsedImportDict:
        """Import ``memo`` from react for the wrapper declaration.

        Returns:
            The react import for ``memo``.
        """
        return {"react": [ImportVar(tag="memo")]}

    def _get_custom_code(self) -> str | None:
        """Emit the memo wrapper declaration for this tag.

        Returns:
            The one-line wrapper declaration.
        """
        return f"const {self.tag} = memo(({{ children }}) => children)"


@cache
def _get_memo_wrapper_class(tag: str) -> type[MemoWrapperComponent]:
    """Return a ``MemoWrapperComponent`` subclass with ``tag`` fixed at class level.

    Args:
        tag: The wrapper's JS identifier.

    Returns:
        A cached subclass whose ``tag`` attribute is the given tag name.
    """
    return type(
        f"MemoWrapper_{tag}",
        (MemoWrapperComponent,),
        {"__module__": __name__, "tag": tag},
    )


# --------------------------------------------------------------------------- #
# The plugin                                                                   #
# --------------------------------------------------------------------------- #


@dataclasses.dataclass(frozen=True, slots=True)
class MemoizeStatefulPlugin(Plugin):
    """Auto-memoize stateful components with ``{children}``-pass-through wrappers.

    Registered in ``default_page_plugins`` between ``ApplyStylePlugin`` and
    ``DefaultCollectorPlugin``. On ``enter_component`` it decides whether a
    component should be memoized, and if so wraps it in a
    ``MemoWrapperComponent`` whose single child is the original. The walker
    then descends into the original component normally so
    ``DefaultCollectorPlugin`` still sees its subtree.

    A ``_memoize_wrapped`` attribute marks the original component so the
    recursive visit doesn't re-wrap it.
    """

    _compiler_can_replace_enter_component = True
    _compiler_can_replace_leave_component = False

    def enter_component(
        self,
        comp: BaseComponent,
        /,
        *,
        page_context: PageContext,
        compile_context: Any,
        in_prop_tree: bool = False,
    ) -> BaseComponent | ComponentAndChildren | None:
        """Wrap eligible stateful components in a ``MemoWrapperComponent``.

        Args:
            comp: The component being visited.
            page_context: The active page context.
            compile_context: The active compile context.
            in_prop_tree: Whether the component is in a prop subtree.

        Returns:
            A ``(wrapper, (comp,))`` tuple replacement when ``comp`` is
            memoizable, else ``None``.
        """
        if in_prop_tree:
            return None
        if not isinstance(comp, Component):
            return None

        # Re-entry guard: when the walker descends into our wrapped child, it
        # calls enter_component on the original comp again. Clear the marker
        # and pass through.
        if getattr(comp, "_memoize_wrapped", False):
            with contextlib.suppress(AttributeError):
                del comp._memoize_wrapped  # pyright: ignore[reportAttributeAccessIssue]
            return None

        # Inside a MemoizationLeaf subtree, do not independently wrap
        # descendants (the leaf owns the wrapping decision for its subtree).
        if getattr(page_context, "_memoize_suppress_depth", 0) > 0:
            return None

        is_memoization_leaf = not comp._memoization_mode.recursive

        if not _should_memoize(comp):
            if is_memoization_leaf:
                # Leaf that wasn't memoized still suppresses descendants.
                page_context._memoize_suppress_depth = (  # type: ignore[attr-defined]
                    getattr(page_context, "_memoize_suppress_depth", 0) + 1
                )
                comp._memoize_pushed_suppression = True  # type: ignore[attr-defined]
            return None

        tag = _compute_memo_tag(comp)
        if tag is None:
            return None

        # Memoize event triggers, collect useCallback hooks for the page body.
        memo_trigger_hooks = fix_event_triggers_for_memo(comp)
        if memo_trigger_hooks:
            invalidate_event_trigger_caches(comp)
        for hook in memo_trigger_hooks:
            page_context.hooks[hook] = None

        compile_context.memoize_wrappers[tag] = None

        # If comp is a MemoizationLeaf that IS being wrapped, suppress
        # descendant wrapping for its subtree.
        if is_memoization_leaf:
            page_context._memoize_suppress_depth = (  # type: ignore[attr-defined]
                getattr(page_context, "_memoize_suppress_depth", 0) + 1
            )
            comp._memoize_pushed_suppression = True  # type: ignore[attr-defined]

        # Mark the original so the recursive re-enter skips wrapping.
        comp._memoize_wrapped = True  # type: ignore[attr-defined]

        wrapper_cls = _get_memo_wrapper_class(tag)
        wrapper = wrapper_cls._create(children=[comp])
        return (wrapper, (comp,))

    def leave_component(
        self,
        comp: BaseComponent,
        children: tuple[BaseComponent, ...],
        /,
        *,
        page_context: PageContext,
        compile_context: Any,
        in_prop_tree: bool = False,
    ) -> BaseComponent | ComponentAndChildren | None:
        """Pop the ``MemoizationLeaf`` suppression counter if we pushed one.

        Args:
            comp: The component being visited.
            children: Its compiled children (unused).
            page_context: The active page context.
            compile_context: The active compile context (unused).
            in_prop_tree: Whether the component is in a prop subtree (unused).

        Returns:
            Always ``None``.
        """
        del children, compile_context, in_prop_tree
        if getattr(comp, "_memoize_pushed_suppression", False):
            page_context._memoize_suppress_depth -= 1  # type: ignore[attr-defined]
            with contextlib.suppress(AttributeError):
                del comp._memoize_pushed_suppression  # pyright: ignore[reportAttributeAccessIssue]
        return None


__all__ = [
    "MemoWrapperComponent",
    "MemoizeStatefulPlugin",
]
