"""Regression tests for the state.js frontend template."""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

STATE_JS_TEMPLATE = (
    Path(__file__).parents[3]
    / "packages/reflex-base/src/reflex_base/.templates/web/utils/state.js"
)

ADD_EVENTS_ALIAS = "const addEvents = (...args) => eventLoop.addEvents(...args);"

USER_CODE_EVALS = (
    "eval(event.payload.callback)",
    "eval(event.payload.javascript_code)",
    "eval(event.payload.function)",
)

TOP_LEVEL_FUNCTION = re.compile(
    r"^(?:export )?const (\w+) = (?:async )?\(", re.MULTILINE
)


def _enclosing_function(content: str, index: int) -> tuple[str, str]:
    """Find the top-level function containing the given offset.

    Args:
        content: The state.js source.
        index: An offset inside one of its top-level functions.

    Returns:
        The enclosing function's name and source text.
    """
    declaration = [
        m for m in TOP_LEVEL_FUNCTION.finditer(content) if m.start() < index
    ][-1]
    return declaration.group(1), content[
        declaration.start() : content.index("\n};\n", index)
    ]


def test_result_callback_dispatches_through_current_event_loop() -> None:
    """Serialized callbacks can dispatch after extraction into their own helper."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is needed to execute the callback")
    content = STATE_JS_TEMPLATE.read_text()
    helper = content[
        content.index("const applyResultCallback =") : content.index(
            "export const applyEvent ="
        )
    ]
    subprocess.run(
        [
            node,
            "--input-type=module",
            "--eval",
            """
import assert from 'node:assert/strict';
const calls = [];
const eventLoop = {addEvents: (events) => calls.push(events)};
"""
            + helper
            + """
const event = {payload: {callback: '(value) => addEvents([value])'}};
await applyResultCallback(event, Promise.resolve('first'), null, null, null);
eventLoop.addEvents = (events) => calls.push(['remounted', ...events]);
await applyResultCallback(event, 'second', null, null, null);
assert.deepEqual(calls, [['first'], ['remounted', 'second']]);
""",
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def test_state_js_does_not_register_deprecated_unload_listener() -> None:
    """The template must not register the deprecated `unload` event listener.

    Regression for https://github.com/reflex-dev/reflex/issues/6195: Chrome
    emits a deprecation warning when pages register `unload` handlers. The
    `pagehide` listener already covers the cases `unload` was being used for
    (tab close, navigation, bfcache), so the deprecated listener must not be
    re-introduced.
    """
    content = STATE_JS_TEMPLATE.read_text()

    assert 'addEventListener("unload"' not in content, (
        "state.js registers a deprecated `unload` listener; use `pagehide` instead."
    )
    assert 'removeEventListener("unload"' not in content, (
        "state.js still removes a `unload` listener that should no longer be registered."
    )


def test_state_js_still_handles_page_lifecycle_disconnect() -> None:
    """The template must still disconnect on page lifecycle events.

    Replacing the deprecated `unload` listener with `pagehide` is the
    recommended Web Page Lifecycle pattern; verify the replacement listeners
    remain wired so the socket is closed when the user navigates away.
    """
    content = STATE_JS_TEMPLATE.read_text()

    assert 'addEventListener("pagehide"' in content, (
        "state.js should register a `pagehide` listener to disconnect the socket."
    )
    assert 'addEventListener("beforeunload"' in content, (
        "state.js should keep its `beforeunload` listener as a disconnect fallback."
    )


def test_every_user_code_eval_can_reach_add_events() -> None:
    """Every scope that evals user code must declare the `addEvents` alias.

    A direct `eval` resolves names from its own scope chain, so the alias has to
    be declared in each function holding one. Moving it, or extracting an `eval`
    into a new helper without it, leaves the eval'd code -- serialized callbacks,
    `_call_script`, and the handlers `_call_function` returns -- referencing an
    undefined `addEvents`.
    """
    content = STATE_JS_TEMPLATE.read_text()

    for snippet in USER_CODE_EVALS:
        eval_at = content.index(snippet)
        name, body = _enclosing_function(content, eval_at)
        assert ADD_EVENTS_ALIAS in body, (
            f"`{name}` evals user code via `{snippet}` but does not declare the "
            "addEvents alias, so the eval'd code cannot resolve it."
        )
        assert body.index(ADD_EVENTS_ALIAS) < body.index(snippet), (
            f"`{name}` declares the addEvents alias after `{snippet}`."
        )
