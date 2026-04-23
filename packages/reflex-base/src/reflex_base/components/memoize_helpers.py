"""Event-trigger memoization helpers for auto-memoized and pseudo-stateful components.

These helpers wrap a component's non-lifecycle event triggers in ``useCallback``
so that React can skip re-renders of subtrees whose event handlers have stable
identities. They are used by both the compiler auto-memoization plugin (see
``reflex.compiler.plugins.memoize``) and by component-creation-time consumers
in ``reflex-components-core`` (e.g. ``WindowEventListener``, ``upload``).
"""

from __future__ import annotations

from hashlib import md5
from typing import TYPE_CHECKING

from reflex_base.components.component import Component
from reflex_base.constants import EventTriggers
from reflex_base.event import EventChain, EventSpec
from reflex_base.utils.imports import ImportVar
from reflex_base.vars import VarData
from reflex_base.vars.base import LiteralVar, Var

if TYPE_CHECKING:
    from reflex_base.plugins.compiler import PageContext


def _get_hook_deps(hook: str) -> list[str]:
    """Extract Var deps from a hook declaration line.

    Args:
        hook: The hook line (e.g. ``"const foo = useState(...)"``).

    Returns:
        The names of variables created by the declaration.
    """
    var_decl = hook.partition("=")[0].strip()
    if not any(var_decl.startswith(kw) for kw in ["const ", "let ", "var "]):
        return []
    _, _, var_name = var_decl.partition(" ")
    var_name = var_name.strip()
    if var_name.startswith(("[", "{")):
        return [v.strip().replace("...", "") for v in var_name.strip("[]{}").split(",")]
    return [var_name]


def _get_deps_from_event_trigger(
    event: EventChain | EventSpec | Var,
) -> dict[str, None]:
    """Get the dependencies accessed by an event trigger value.

    Args:
        event: The event trigger value.

    Returns:
        Dependency names, insertion-ordered.
    """
    events: list = [event]
    deps: dict[str, None] = {}

    if isinstance(event, EventChain):
        events.extend(event.events)

    for ev in events:
        if isinstance(ev, EventSpec):
            for arg in ev.args:
                for a in arg:
                    var_datas = VarData.merge(a._get_all_var_data())
                    if var_datas and var_datas.deps is not None:
                        deps |= {str(dep): None for dep in var_datas.deps}
    return deps


def get_memoized_event_triggers(
    component: Component,
) -> dict[str, Var]:
    """Generate ``useCallback`` wrappers for the component's event triggers.

    Args:
        component: The component whose event triggers should be memoized.

    Returns:
        A dict mapping event trigger name to memoized_triger.
    """
    trigger_memo: dict[str, Var] = {}
    for event_trigger, event_args in component._get_vars_from_event_triggers(
        component.event_triggers
    ):
        if event_trigger in {
            EventTriggers.ON_MOUNT,
            EventTriggers.ON_UNMOUNT,
            EventTriggers.ON_SUBMIT,
        }:
            # Do not memoize lifecycle or submit events.
            continue

        event = component.event_triggers[event_trigger]
        rendered_chain = LiteralVar.create(event)

        chain_hash = md5(
            str(rendered_chain).encode("utf-8"), usedforsecurity=False
        ).hexdigest()
        memo_name = f"{event_trigger}_{chain_hash}"

        var_deps = ["addEvents", "ReflexEvent"]
        var_deps.extend(_get_deps_from_event_trigger(event))

        event_var_data = []
        for arg in event_args:
            var_data = arg._get_all_var_data()
            if var_data is None:
                continue
            event_var_data.append(var_data)
            for hook in var_data.hooks:
                var_deps.extend(_get_hook_deps(hook))

        memo_var_data = VarData.merge(
            *event_var_data,
            rendered_chain._get_all_var_data(),
            VarData(
                hooks=[
                    f"const {memo_name} = useCallback({rendered_chain!s}, [{', '.join(var_deps)}])"
                ],
                imports={"react": [ImportVar(tag="useCallback")]},
            ),
        )

        trigger_memo[event_trigger] = Var(
            _js_expr=memo_name, _var_type=EventChain, _var_data=memo_var_data
        )
    return trigger_memo


def fix_event_triggers_for_memo(
    component: Component, page_context: PageContext
) -> Component:
    """Return a component whose event triggers reference memoized ``useCallback``s.

    Replaces each (non-lifecycle) event-trigger value with a ``Var`` naming a
    memoized ``useCallback`` wrapper. The original is never mutated — a
    page-local clone is taken via ``page_context.own`` on first write.

    Args:
        component: The component whose event triggers to memoize.
        page_context: The active page context, used to obtain a page-local
            clone before rewriting ``event_triggers``.

    Returns:
        Either ``component`` (when nothing needed rewriting) or a page-local
        clone with the rewritten ``event_triggers``.
    """
    memo_event_triggers = tuple(get_memoized_event_triggers(component).items())
    if not memo_event_triggers:
        return component
    owned = page_context.own(component)
    owned.event_triggers = {
        **component.event_triggers,
        **dict(memo_event_triggers),
    }
    return owned


def is_snapshot_boundary(component: Component) -> bool:
    """Whether ``component`` owns its subtree for memoization purposes.

    Snapshot boundaries (``MemoizationLeaf``-style components with
    ``_memoization_mode.recursive=False``) encapsulate internal machinery as
    their own structural children. The auto-memoize compiler pass must wrap
    them whole and not walk or independently memoize that subtree.

    The check is the behavioral flag, not ``isinstance(MemoizationLeaf)``, so
    components that opt into non-recursive memoization without subclassing
    ``MemoizationLeaf`` are handled identically.

    Args:
        component: The component to classify.

    Returns:
        ``True`` iff descendants of ``component`` must not be independently
        memoized and the memo wrapper must carry the full subtree snapshot.
    """
    return not component._memoization_mode.recursive


__all__ = [
    "fix_event_triggers_for_memo",
    "get_memoized_event_triggers",
    "is_snapshot_boundary",
]
