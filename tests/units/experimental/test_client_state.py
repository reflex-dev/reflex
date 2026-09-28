"""Tests for reflex.experimental.client_state."""

from typing import cast

import pytest
from reflex_base.vars.base import Var

from reflex.experimental.client_state import ClientStateVar
from reflex.state import BaseState


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
