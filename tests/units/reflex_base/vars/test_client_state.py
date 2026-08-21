from reflex_base.vars.client_state import ClientStateVar


def test_client_state_var_create_produces_use_state_hook() -> None:
    """A ClientStateVar declares a useState hook and exposes value/setter."""
    cs = ClientStateVar.create("my_value", default="hello")

    var_data = cs._get_all_var_data()
    assert var_data is not None
    hooks = " ".join(var_data.hooks)
    assert 'useState("hello")' in hooks
    assert "my_value" in str(cs.value)
    assert "setMy_value" in str(cs.set)


def test_client_state_var_reexported_from_experimental() -> None:
    """The legacy reflex.experimental import path keeps working."""
    from reflex.experimental.client_state import ClientStateVar as LegacyClientStateVar

    assert LegacyClientStateVar is ClientStateVar
