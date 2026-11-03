import logging

import pytest
from reflex_base.constants.state import FIELD_MARKER
from reflex_base.registry import RegistrationContext

import reflex as rx
from reflex.state import State, _apply_client_storage_vars


@pytest.mark.parametrize("default", ["", "light"])
async def test_removed_client_storage_resets_declared_default(
    default: str,
    caplog: pytest.LogCaptureFixture,
    clean_registration_context: RegistrationContext,
):
    """Removing synced browser storage restores its declared string default.

    Args:
        default: The declared default for the storage var.
        caplog: Captured log records.
        clean_registration_context: An isolated state registry.
    """

    class RemovedStorageState(State):
        local: str = rx.LocalStorage(default, sync=True)

    root = State()
    state = await root.get_state(RemovedStorageState)
    state.local = "saved"
    with caplog.at_level(logging.ERROR):
        applied = await _apply_client_storage_vars(
            root, {f"{RemovedStorageState.get_full_name()}.local{FIELD_MARKER}": None}
        )
    assert applied == [(state, "local")]
    assert state.local == default
    assert "local" in state.dirty_vars
    assert not caplog.records
