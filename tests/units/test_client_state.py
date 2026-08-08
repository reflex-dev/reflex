"""Tests for experimental client state vars."""

from reflex.experimental.client_state import ClientStateVar


def _hooks(client_state_var: ClientStateVar) -> tuple[str, ...]:
    """Get all hook strings for a client state var.

    Returns:
        The normalized hook strings.
    """
    var_data = client_state_var._get_all_var_data()
    assert var_data is not None
    return var_data.hooks


def test_global_client_state_initializes_use_state_from_shared_ref():
    """Global client state should keep late-mounted components in sync."""
    flag = ClientStateVar.create("flag", default="")

    hooks = _hooks(flag)

    assert (
        """const [flag, setFlag] = useState(() => refs['_client_state_flag'] !== undefined ? refs['_client_state_flag'] : "")"""
        in hooks
    )
    assert """const [flag, setFlag] = useState("")""" not in hooks


def test_global_client_state_preserves_null_shared_ref():
    """Global client state should not replace explicit null with the default."""
    flag = ClientStateVar.create("flag", default="idle")

    assert (
        """const [flag, setFlag] = useState(() => refs['_client_state_flag'] !== undefined ? refs['_client_state_flag'] : "idle")"""
        in _hooks(flag)
    )


def test_global_client_state_without_default_uses_undefined_fallback():
    """Global client state without a default should still read the shared ref."""
    flag = ClientStateVar.create("flag")

    assert (
        "const [flag, setFlag] = useState(() => refs['_client_state_flag'] !== undefined ? refs['_client_state_flag'] : undefined)"
        in _hooks(flag)
    )


def test_local_client_state_keeps_plain_default_initializer():
    """Non-global client state should not read from the shared refs mirror."""
    flag = ClientStateVar.create("flag", default="", global_ref=False)

    hooks = _hooks(flag)

    assert """const [flag, setFlag] = useState("")""" in hooks
    assert not any("refs['_client_state_flag']" in hook for hook in hooks)
