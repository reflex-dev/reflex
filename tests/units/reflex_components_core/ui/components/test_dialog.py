from reflex_base.vars.base import Var
from reflex_components_core.ui.components.dialog import (
    Dialog,
    close_dialog,
    open_dialog,
)

import reflex as rx


def test_dialog_renders_native_dialog_without_open_attr() -> None:
    """The dialog element renders without the non-modal open attribute."""
    dialog = Dialog.create(rx.ui.dialog.title("Hi"), id="dlg")

    rendered = dialog.render()
    assert rendered["name"] == '"dialog"'
    assert not any(prop.startswith("open:") for prop in rendered["props"])
    assert '"data-slot":"dialog"' in str(dialog)


def test_dialog_backdrop_dismiss_hook_added_by_default() -> None:
    """The backdrop mousedown hook is present unless dismissible=False."""
    dialog = Dialog.create(id="dlg")
    hooks = " ".join(map(str, dialog._get_all_hooks()))

    assert "mousedown" in hooks
    assert "close()" in hooks
    # Clicks on the dialog's own padding must not dismiss: the hook compares
    # the pointer position against the dialog's bounding box.
    assert "getBoundingClientRect" in hooks

    fixed = Dialog.create(id="dlg2", dismissible=False)
    assert "mousedown" not in " ".join(map(str, fixed._get_all_hooks()))


def test_dialog_open_var_syncs_modal_state() -> None:
    """A Var open prop drives showModal/close through a useEffect hook."""
    open_var = Var("state.show").to(bool)
    dialog = Dialog.create(id="dlg", open=open_var)
    hooks = " ".join(map(str, dialog._get_all_hooks()))

    assert "showModal()" in hooks
    assert "state.show" in hooks


def test_dialog_helpers_target_element_by_id() -> None:
    """open/close helpers call the dialog methods client side."""
    open_js = str(open_dialog("dlg").args[0][1])
    close_js = str(close_dialog("dlg").args[0][1])

    assert 'document.getElementById("dlg")?.showModal()' in open_js
    assert 'document.getElementById("dlg")?.close()' in close_js


def test_dialog_namespace_helpers() -> None:
    """The namespace exposes the client-side open/close helpers."""
    assert rx.ui.dialog.open is open_dialog
    assert rx.ui.dialog.close is close_dialog


def test_dialog_parts_render_slots() -> None:
    """Dialog parts carry their data-slot attributes."""
    rendered = str(
        rx.ui.dialog(
            rx.ui.dialog.header(
                rx.ui.dialog.title("T"),
                rx.ui.dialog.description("D"),
            ),
            rx.ui.dialog.footer(rx.ui.button("Close")),
            id="dlg",
        )
    )

    for slot in (
        "dialog",
        "dialog-header",
        "dialog-title",
        "dialog-description",
        "dialog-footer",
    ):
        assert f'"data-slot":"{slot}"' in rendered
