"""Event-trigger memoization helpers for auto-memoized and pseudo-stateful components.

These helpers wrap a component's non-lifecycle event triggers in ``useCallback``
so that React can skip re-renders of subtrees whose event handlers have stable
identities. They are used by both the compiler auto-memoization plugin (see
``reflex.compiler.plugins.memoize``) and by component-creation-time consumers
in ``reflex-components-core`` (e.g. ``WindowEventListener``, ``upload``).
"""

from __future__ import annotations

import contextlib
from hashlib import md5

from reflex_base.components.component import Component
from reflex_base.constants import EventTriggers
from reflex_base.event import EventChain, EventSpec
from reflex_base.utils.imports import ImportVar
from reflex_base.vars import VarData
from reflex_base.vars.base import LiteralVar, Var


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
) -> dict[str, tuple[Var, str]]:
    """Generate ``useCallback`` wrappers for the component's event triggers.

    Args:
        component: The component whose event triggers should be memoized.

    Returns:
        A dict mapping event trigger name to
        ``(memoized_var, useCallback_hook_line)``.
    """
    trigger_memo: dict[str, tuple[Var, str]] = {}
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
        rendered_chain = str(LiteralVar.create(event))

        chain_hash = md5(
            str(rendered_chain).encode("utf-8"), usedforsecurity=False
        ).hexdigest()
        memo_name = f"{event_trigger}_{chain_hash}"

        var_deps = ["addEvents", "ReflexEvent"]
        var_deps.extend(_get_deps_from_event_trigger(event))

        for arg in event_args:
            var_data = arg._get_all_var_data()
            if var_data is None:
                continue
            for hook in var_data.hooks:
                var_deps.extend(_get_hook_deps(hook))

        memo_var_data = VarData.merge(
            *[var._get_all_var_data() for var in event_args],
            VarData(imports={"react": [ImportVar(tag="useCallback")]}),
        )

        trigger_memo[event_trigger] = (
            Var(_js_expr=memo_name)._replace(
                _var_type=EventChain, merge_var_data=memo_var_data
            ),
            f"const {memo_name} = useCallback({rendered_chain}, [{', '.join(var_deps)}])",
        )
    return trigger_memo


def fix_event_triggers_for_memo(component: Component) -> list[str]:
    """Memoize ``component.event_triggers`` in place and return hook code.

    Replaces each (non-lifecycle) event-trigger value on ``component`` with a
    ``Var`` naming a memoized ``useCallback`` wrapper, and returns the
    ``useCallback`` hook lines in trigger order.

    Args:
        component: The component whose event triggers to memoize.

    Returns:
        The ``useCallback`` hook lines to emit at the top of the page body.
    """
    memo_event_triggers = tuple(get_memoized_event_triggers(component).items())
    memo_trigger_hooks: list[str] = []

    if memo_event_triggers:
        component.event_triggers = dict(
            component.event_triggers
        )  # isolate so original dict is not mutated
        for event_trigger, (memo_trigger, memo_trigger_hook) in memo_event_triggers:
            memo_trigger_hooks.append(memo_trigger_hook)
            component.event_triggers[event_trigger] = memo_trigger

    return memo_trigger_hooks


def invalidate_event_trigger_caches(component: Component) -> None:
    """Drop caches that depend on ``component.event_triggers``.

    After :func:`fix_event_triggers_for_memo` mutates the shared event-triggers
    dict, cached derivatives become stale.

    Args:
        component: The original (pre-mutation) component.
    """
    for attr in (
        "_cached_render_result",
        "_vars_cache",
        "_imports_cache",
        "_hooks_internal_cache",
    ):
        with contextlib.suppress(AttributeError):
            delattr(component, attr)


__all__ = [
    "fix_event_triggers_for_memo",
    "get_memoized_event_triggers",
    "invalidate_event_trigger_caches",
]
