"""The deprecated reflex.experimental.client_state path still resolves."""

import pytest

import reflex as rx


def test_experimental_import_is_the_promoted_class() -> None:
    """``reflex.experimental.client_state`` re-exports the reflex-base class."""
    from reflex.experimental.client_state import ClientStateVar

    assert ClientStateVar is rx.ClientStateVar


def test_experimental_namespace_factory_still_works() -> None:
    """``rx._x.client_state`` keeps building the same vars."""
    # The shim keeps the original positional signature.
    assert rx._x.client_state("legacy", 0)._state_name == "legacy"


def test_promoted_names_are_reachable_from_rx() -> None:
    """The lazy-loader wiring only fails at attribute access, so assert it."""
    assert rx.client_state(0, name="promoted")._state_name == "promoted"
    assert isinstance(rx.client_state(0, name="typed"), rx.ClientStateVar)
    # Exported so `.set` can be named in a type annotation.
    assert isinstance(rx.client_state(0, name="setter").set, rx.ClientStateSetter)


def test_legacy_named_var_is_global() -> None:
    """The old positional form keeps naming -- and therefore globalizing -- vars."""
    cs = rx._x.client_state("legacy_named", 0)
    assert cs._state_name == "legacy_named"
    assert cs._is_global


def test_legacy_global_ref_false_drops_the_name() -> None:
    """``global_ref=False`` meant anonymous, which is now a dropped name.

    The name was never a store key in that mode, so discarding it reproduces the
    old behavior exactly under the new scoping rules.
    """
    cs = rx._x.client_state("is_copied", False, False)
    assert cs._state_name != "is_copied"
    assert not cs._is_global


def test_legacy_path_warns(capsys: pytest.CaptureFixture) -> None:
    """All the deprecation noise lives on the old entry point, not the new API."""
    rx._x.client_state("warned", 0)
    assert "rx._x.client_state" in capsys.readouterr().out

    rx.client_state(0, name="quiet")
    assert "deprecat" not in capsys.readouterr().out.lower()
