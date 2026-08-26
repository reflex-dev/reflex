"""Regression tests for the generated context.js frontend template."""

import re

from reflex_base.compiler.templates import context_template


def _event_loop_provider_body() -> str:
    """Render context.js and return the ``EventLoopProvider`` function body.

    Returns:
        The source of the generated ``EventLoopProvider`` component.
    """
    rendered = context_template(
        is_dev_mode=False,
        default_color_mode="light",
        initial_state={"state": {}},
        state_name="state",
    )
    start = rendered.index("export function EventLoopProvider")
    end = rendered.index("export function StateProvider", start)
    return rendered[start:end]


def test_event_loop_provider_memoizes_its_element() -> None:
    """``EventLoopProvider`` must return a memoized provider element.

    ``useEventLoop`` subscribes to router state (``useLocation``,
    ``useNavigate``), so the provider re-renders on every navigation even
    though ``addEvents`` and ``connectErrors`` are stable. Returning the same
    element object lets React bail out instead of re-rendering the entire app
    subtree below the provider.
    """
    body = _event_loop_provider_body()

    assert re.search(r"return useMemo\(\s*\(\) =>\s*createElement\(", body), (
        "EventLoopProvider should return a useMemo'd createElement call."
    )
    assert "[addEventsLocal, connectErrors, children]" in body, (
        "EventLoopProvider's useMemo must depend on the dispatchers and children."
    )


def test_event_loop_provider_still_publishes_module_dispatchers() -> None:
    """The module-level dispatchers must be assigned outside the memo.

    JSX literals built outside the React-tree path reach ``addEvents`` through
    the module-level dispatchers, so those assignments have to run on every
    render, not only when the memoized element is recomputed.
    """
    body = _event_loop_provider_body()

    assign_index = body.index("_addEventsImpl = addEventsLocal;")
    memo_index = body.index("return useMemo(")
    assert assign_index < memo_index, (
        "module-level dispatchers must be published before the memoized return."
    )
    assert "_connectErrorsImpl = connectErrors;" in body[:memo_index]
