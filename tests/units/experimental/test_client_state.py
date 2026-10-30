"""Tests for reflex.experimental.client_state."""

import json
import re
import shutil
import subprocess
from typing import Any, cast

import pytest
from reflex_base.event import EventChain, LambdaEventCallback, call_function, run_script
from reflex_base.vars.base import Var
from reflex_base.vars.function import FunctionVar

from reflex.experimental.client_state import ClientStateVar, NoValue
from reflex.state import BaseState


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is unavailable")
@pytest.mark.parametrize("wrapper", ["direct", "call_function", "run_script"])
@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("{event}?.clientX", 42),
        ("{event}.clientX", 42),
        ('{event}["clientX"]', 42),
        ("{event}?.target?.value", "changed"),
        ("{event}?.formData?.answer", 7),
        ("({event}?.clientX ?? 0) + 1", 43),
    ],
)
def test_set_value_captures_event_expression(expression, expected, wrapper) -> None:
    """Event expressions remain values when a client state callback runs.

    Args:
        expression: JavaScript expression returned by the trigger's args spec.
        expected: Value the client state setter should receive.
        wrapper: Optional event wrapper around the client state setter.
    """
    cs = ClientStateVar.create("captured", default=0)

    def handler(value):
        """Bind the client state expression through the selected event wrapper.

        Args:
            value: Expression produced by the event's args spec.

        Returns:
            The callback to execute on the frontend.
        """
        setter = cs.set_value(value)
        if wrapper == "call_function":
            return call_function(setter)
        if wrapper == "run_script":
            return run_script(setter.to(FunctionVar).call())
        return setter

    chain = EventChain.create(
        value=cast("LambdaEventCallback[Any]", handler),
        args_spec=lambda event: (Var(expression.format(event=event)),),
        key="on_click",
    )
    result = subprocess.run(
        [
            "node",
            "-e",
            """
const assert = require('node:assert/strict');
const input = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
const values = [];
const refs = { _client_state_setCaptured: value => values.push(value) };
const ReflexEvent = (name, payload) => ({ name, payload });
const addEvents = events => events.forEach(event => event.payload.function());
const callback = eval(input.callback);
callback({ clientX: 42, target: { value: 'changed' }, formData: { answer: 7 } });
assert.deepEqual(values, [input.expected]);
""",
        ],
        input=json.dumps({"callback": str(Var.create(chain)), "expected": expected}),
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("use_set_property", [True, False])
def test_global_setter_carries_client_state_hooks(use_set_property: bool) -> None:
    """A global setter Var must carry the hooks that initialize the client state.

    A component that only sets the value (e.g. a sibling button of the
    component rendering ``.value``) is compiled into its own memo body, so
    the setter must bring the ``useState`` and ``refs`` wiring with it.

    Args:
        use_set_property: Whether to use ``.set`` or ``.set_value(...)``.
    """
    cs = ClientStateVar.create("setter_hooks", default=0)
    setter = cs.set if use_set_property else cs.set_value(1)

    cs_var_data = cs._get_all_var_data()
    setter_var_data = setter._get_all_var_data()
    assert cs_var_data is not None
    assert setter_var_data is not None
    assert set(cs_var_data.hooks) <= set(setter_var_data.hooks)
    assert any("useState" in hook for hook in setter_var_data.hooks)


@pytest.mark.parametrize("use_set_property", [True, False])
def test_local_setter_does_not_carry_client_state_hooks(use_set_property: bool) -> None:
    """A local setter Var must not bring its own ``useState``.

    A local setter-only component with its own state copy would silently update
    state that no reader sees; leaving the hooks off keeps that a loud error.

    Args:
        use_set_property: Whether to use ``.set`` or ``.set_value(...)``.
    """
    cs = ClientStateVar.create("local_setter", default=0, global_ref=False)
    setter = cs.set if use_set_property else cs.set_value(1)

    setter_var_data = setter._get_all_var_data()
    assert setter_var_data is None or not any(
        "useState" in hook for hook in setter_var_data.hooks
    )


def test_setter_carries_backend_default_hooks() -> None:
    """A backend-derived default brings its state context hook to the setter.

    Regression: ``create`` merged only the default's own ``_var_data``, so a
    setter-only component compiled ``useState(<state>.field)`` without the
    ``useContext`` hook that defines ``<state>``, raising a ReferenceError.
    """

    class ClientStateDefaultState(BaseState):
        default_text: str = "hi"

    default = cast("Var", ClientStateDefaultState.default_text)
    default_var_data = default._get_all_var_data()
    assert default_var_data is not None

    cs = ClientStateVar.create("backend_default", default=default)
    for var in (cs, cs.value, cs.set, cs.set_value("changed")):
        var_data = var._get_all_var_data()
        assert var_data is not None
        assert var_data.state == default_var_data.state
        assert set(default_var_data.hooks) <= set(var_data.hooks)


@pytest.mark.parametrize(
    ("default", "initial_value"),
    [
        (0, "'_client_state_seeded' in refs ? refs['_client_state_seeded'] : (0)"),
        (
            "a",
            "'_client_state_seeded' in refs ? refs['_client_state_seeded'] : (\"a\")",
        ),
        (NoValue, "refs['_client_state_seeded']"),
    ],
)
def test_global_use_state_starts_from_shared_value(
    default: object, initial_value: str
) -> None:
    """A global client state's ``useState`` starts from the shared value.

    A component that mounts after the value was set renders the shared value, so
    its own state must match it: React skips a setter call equal to the current
    state, which would otherwise swallow setting the value back to the default.

    Args:
        default: The default passed to ``create``.
        initial_value: The expected ``useState`` argument.
    """
    cs = ClientStateVar.create("seeded", default=default)

    var_data = cs._get_all_var_data()
    assert var_data is not None
    assert f"const [seeded, setSeeded] = useState({initial_value})" in var_data.hooks


def test_global_use_state_checks_the_slot_it_reads() -> None:
    """The ``in refs`` check names the same ``refs`` slot that the value is read from.

    If the two drifted apart, the check would always be false and every reader
    mounting after a set would silently start from the default again.
    """
    cs = ClientStateVar.create("keyed", default=0)

    var_data = cs._get_all_var_data()
    assert var_data is not None
    use_state = next(hook for hook in var_data.hooks if "useState(" in hook)
    match = re.search(r"useState\((.+) in refs \? refs\[(.+)\] : \(0\)\)$", use_state)
    assert match is not None, use_state
    assert match.group(1) == match.group(2)


def test_local_use_state_starts_from_default() -> None:
    """A local client state has no shared value, so ``useState`` takes the default."""
    cs = ClientStateVar.create("local_seed", default=0, global_ref=False)

    var_data = cs._get_all_var_data()
    assert var_data is not None
    assert "const [local_seed, setLocal_seed] = useState(0)" in var_data.hooks


def test_push_keeps_the_value_without_a_mounted_component() -> None:
    """Before a component using the value mounts there is no setter to call.

    The push then stores the value in the shared slot, which the first component
    to mount starts its ``useState`` from.
    """
    cs = ClientStateVar.create("pushed", default="a")

    script = str(cs.push("b").args[0][1])
    assert (
        "(refs['_client_state_setPushed'] ?? ((pushed) => { "
        "refs['_client_state_pushed'] = pushed; }))(\"b\")"
    ) in script
