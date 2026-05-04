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


def get_events_hooks_var_data() -> VarData:
    """Build the VarData attached to ``Hooks.EVENTS`` for event triggers.

    Higher priority wraps further out, so ``StateProvider`` (100) encloses
    ``EventLoopProvider`` (90) — the latter reads ``DispatchContext`` from
    the former. The returned providers are fresh per call: the compiler's
    ``app_wrap_components`` registry already dedupes by ``(priority, tag)``,
    and caching the instances burned us via ``copy.deepcopy`` carrying
    ``_cached_render_result`` from a prior compile run forward into the next.

    Returns:
        A new VarData carrying both providers as app_wraps.
    """
    return VarData(
        position=Hooks.HookPosition.INTERNAL,
        app_wraps=(
            (100, StateContextProvider.create()),
            (90, EventLoopContextProvider.create()),
        ),
    )
