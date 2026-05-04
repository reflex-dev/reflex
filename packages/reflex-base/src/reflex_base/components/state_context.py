"""App-wrap components mounting the state and event-loop React providers.

These wrap children in the ``StateProvider`` / ``EventLoopProvider`` JS
functions emitted into ``utils/context.js`` by ``compile_contexts``. They are
attached to the VarData returned by :meth:`reflex_base.vars.base.VarData.from_state`
so the compiler picks them up through the generic Var-driven app-wrap pipeline,
rather than the JS Layout template hard-coding them around every app.
"""

from __future__ import annotations

from reflex_base.components.component import Component
from reflex_base.constants import Dirs
from reflex_base.constants.compiler import Hooks
from reflex_base.vars.base import VarData


class StateContextProvider(Component):
    """App wrap that mounts the React state-context provider around children."""

    library = f"$/{Dirs.CONTEXTS_PATH}"
    tag = "StateProvider"


class EventLoopContextProvider(Component):
    """App wrap that mounts the websocket event-loop provider around children."""

    library = f"$/{Dirs.CONTEXTS_PATH}"
    tag = "EventLoopProvider"


def get_event_app_wraps() -> tuple[tuple[int, Component], ...]:
    """Return state/event-loop providers required when events are dispatched.

    ``StateProvider`` (100) wraps further out than ``EventLoopProvider``
    (90) because the latter reads ``DispatchContext`` from the former.
    Providers are constructed fresh per call — module-level caching
    breaks because ``copy.deepcopy`` (used when assembling the app-root
    chain) carries ``_cached_render_result`` across compile runs.

    Returns:
        ``(priority, provider)`` entries deduped by the compiler.
    """
    return (
        (100, StateContextProvider.create()),
        (90, EventLoopContextProvider.create()),
    )


def get_events_hooks_var_data() -> VarData:
    """Build the VarData advertising the state/event-loop app wraps.

    Returns:
        A new VarData carrying both providers as app_wraps.
    """
    return VarData(
        position=Hooks.HookPosition.INTERNAL,
        app_wraps=get_event_app_wraps(),
    )
