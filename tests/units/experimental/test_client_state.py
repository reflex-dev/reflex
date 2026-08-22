"""The deprecated reflex.experimental.client_state path still resolves."""

import reflex as rx


def test_experimental_import_is_the_promoted_class() -> None:
    """``reflex.experimental.client_state`` re-exports the reflex-base class."""
    from reflex.experimental.client_state import ClientStateVar

    assert ClientStateVar is rx.ClientStateVar


def test_experimental_namespace_factory_still_works() -> None:
    """``rx._x.client_state`` keeps building the same vars."""
    assert rx._x.client_state("legacy", default=0)._state_name == "legacy"


def test_promoted_names_are_reachable_from_rx() -> None:
    """The lazy-loader wiring only fails at attribute access, so assert it."""
    assert rx.client_state("promoted", default=0)._state_name == "promoted"
    assert isinstance(rx.client_state("typed", default=0), rx.ClientStateVar)
