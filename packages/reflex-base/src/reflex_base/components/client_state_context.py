"""App-wrap component mounting the client-state React provider.

Wraps children in the ``ClientStateProvider`` exported by
``utils/client_state.js``. It is attached to the ``VarData`` a
:class:`~reflex_base.client_state.ClientStateVar` carries, so the compiler picks
it up through the generic Var-driven app-wrap pipeline rather than the JS Layout
template hard-coding it around every app.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from reflex_base.components.component import Component
from reflex_base.constants import Dirs
from reflex_base.utils.imports import ImportVar
from reflex_base.vars.base import LiteralVar, Var, VarData
from reflex_base.vars.function import FunctionVar

# Inside ErrorBoundary (55) so a client-state error is caught, outside the
# theme/toaster/overlay wraps. It depends on neither StateProvider nor
# EventLoopProvider.
CLIENT_STATE_APP_WRAP_PRIORITY = 50


# The hook ``ClientStateVar.create`` emits for a local var ends with its quoted
# name; a global one ends with ``, true)`` instead.
_LOCAL_HOOK = re.compile(r'= useClientState\(.*, "([A-Za-z_$][A-Za-z0-9_$]*)"\)$')


def local_client_state_names(hooks: Iterable[str]) -> list[str]:
    """Get the local client state names a body's hooks use.

    Args:
        hooks: The hook strings of one compiled body.

    Returns:
        The names, sorted so the emitted code is stable.
    """
    return sorted({
        match.group(1)
        for hook in hooks
        if hook.endswith('")') and (match := _LOCAL_HOOK.search(hook))
    })


class ClientStateScope(Component):
    """A client state scope that claims the local names its body uses."""

    library = f"$/{Dirs.CLIENT_STATE_PATH}"
    tag = "ClientStateScope"

    # The local names used by this boundary's own body.
    owns: Var[list[str]]


def scope_page(component: Component) -> Component:
    """Make a page the owner of the local client state names its body uses.

    The page is the outermost boundary, so memos below it that use the same
    names share its slots, and the slots reset when the page unmounts.

    Args:
        component: The evaluated page component.

    Returns:
        The page wrapped in a scope, or unchanged when it uses no local names.
    """
    if owns := local_client_state_names(component._get_all_hooks()):
        return ClientStateScope.create(component, owns=owns)
    return component


def scoped_memo_wrapper(inner: Var | None, owns: list[str]) -> Var:
    """Compose a memo wrapper that also opens a client state scope.

    The scope has to sit *above* the component function: a component's hooks run
    before the elements it returns are mounted, so a provider inside its own
    output would leave its own ``useClientState`` calls resolving against the
    enclosing scope and sharing state across instances.

    Args:
        inner: The wrapper the definition would otherwise use, if any.
        owns: The local names used by the memo body.

    Returns:
        A function Var suitable for ``MemoComponentDefinition.wrapper``.
    """
    scope_import = VarData(
        imports={f"$/{Dirs.CLIENT_STATE_PATH}": [ImportVar(tag="withClientStateScope")]}
    )
    owns_js = LiteralVar.create(owns)
    if inner is None:
        return Var(
            _js_expr=f"((Component) => withClientStateScope(Component, {owns_js!s}))",
            _var_data=scope_import,
        ).to(FunctionVar)
    return Var(
        _js_expr=f"((Component) => withClientStateScope({inner!s}(Component), {owns_js!s}))",
        _var_data=VarData.merge(scope_import, inner._get_all_var_data()),
    ).to(FunctionVar)


class ClientStateContextProvider(Component):
    """App wrap that mounts the React client-state provider around children."""

    library = f"$/{Dirs.CLIENT_STATE_PATH}"
    tag = "ClientStateProvider"


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
            ClientStateContextProvider.create(),
        ),
    )
