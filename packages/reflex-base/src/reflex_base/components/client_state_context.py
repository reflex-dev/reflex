"""App-wrap component mounting the client-state React provider.

Wraps children in the ``ClientStateProvider`` exported by
``utils/client_state.js``. It is attached to the ``VarData`` a
:class:`~reflex_base.client_state.ClientStateVar` carries, so the compiler picks
it up through the generic Var-driven app-wrap pipeline rather than the JS Layout
template hard-coding it around every app.
"""

from __future__ import annotations

from typing import Any

from reflex_base.components.component import Component
from reflex_base.constants import Dirs
from reflex_base.utils.imports import ImportVar
from reflex_base.vars.base import Var, VarData

# Inside ErrorBoundary (55) so a client-state error is caught, outside the
# theme/toaster/overlay wraps. It depends on neither StateProvider nor
# EventLoopProvider.
CLIENT_STATE_APP_WRAP_PRIORITY = 50

# The global object backend-evaluated code reaches the store through. Passed to
# the provider as a prop rather than imported by ``client_state.js``, so this
# side owns where the store is published and the javascript stays independent
# of it.
refs_var = Var(
    _js_expr="refs",
    _var_data=VarData(imports={f"$/{Dirs.STATE_PATH}": [ImportVar(tag="refs")]}),
)


class ClientStateContextProvider(Component):
    """App wrap that mounts the React client-state provider around children."""

    library = f"$/{Dirs.CLIENT_STATE_PATH}"
    tag = "ClientStateProvider"

    # Object the provider publishes its store on, keyed by CLIENT_STATE_REF.
    registry: Var[dict[str, Any]]


def get_client_state_app_wraps() -> tuple[tuple[int, Component], ...]:
    """Build the app-wrap entry advertising the client-state provider.

    Returns a fresh instance per call so render-cache state can't leak across
    compile runs via ``copy.deepcopy``. Entries are deduped by
    ``(priority, tag)``, and equal instances collapse to one wrapper, so any
    number of client state vars on a page yield a single provider.

    Returns:
        A single ``(priority, provider)`` entry.
    """
    return (
        (
            CLIENT_STATE_APP_WRAP_PRIORITY,
            ClientStateContextProvider.create(registry=refs_var),
        ),
    )
