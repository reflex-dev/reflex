"""A modal dialog built on the native dialog element.

Uses ``showModal()`` for focus trapping, ESC dismissal, and top-layer
stacking -- no JavaScript framework required. Open it client side with
``rx.ui.dialog.open(id)`` or drive it from state with the ``open`` prop.
"""

from __future__ import annotations

from typing import ClassVar

from reflex_base.components.component import ComponentNamespace, field
from reflex_base.event import EventHandler, EventSpec, no_args_event_spec, run_script
from reflex_base.vars.base import LiteralVar, Var, VarData, get_unique_variable_name

from reflex_components_core.el.elements import other
from reflex_components_core.el.elements.sectioning import H2
from reflex_components_core.el.elements.typography import Div, P
from reflex_components_core.ui.base import UIComponent

DIALOG_CLASS_NAME = (
    "m-auto w-full max-w-[calc(100%-2rem)] sm:max-w-lg "
    "max-h-[calc(100vh-2rem)] overflow-y-auto "
    "rounded-lg border border-border bg-background text-foreground "
    "p-6 shadow-lg outline-none open:grid gap-4 backdrop:bg-black/50"
)

DIALOG_HEADER_CLASS_NAME = "flex flex-col gap-2 text-center sm:text-left"

DIALOG_TITLE_CLASS_NAME = "text-lg leading-none font-semibold"

DIALOG_DESCRIPTION_CLASS_NAME = "text-muted-foreground text-sm"

DIALOG_FOOTER_CLASS_NAME = "flex flex-col-reverse gap-2 sm:flex-row sm:justify-end"


def _dialog_method(dialog_id: str | Var[str], method: str) -> EventSpec:
    """Build a client-side event calling a method on a dialog element.

    Args:
        dialog_id: The id of the dialog element.
        method: The dialog method to invoke.

    Returns:
        The event spec running the call in the browser.
    """
    id_var = LiteralVar.create(dialog_id)
    return run_script(
        Var(
            _js_expr=f"document.getElementById({id_var!s})?.{method}()",
            _var_data=id_var._get_all_var_data(),
        )
    )


def open_dialog(dialog_id: str | Var[str]) -> EventSpec:
    """Open the dialog with the given id, entirely client side.

    Args:
        dialog_id: The id of the dialog element.

    Returns:
        The event spec opening the dialog.
    """
    return _dialog_method(dialog_id, "showModal")


def close_dialog(dialog_id: str | Var[str]) -> EventSpec:
    """Close the dialog with the given id, entirely client side.

    Args:
        dialog_id: The id of the dialog element.

    Returns:
        The event spec closing the dialog.
    """
    return _dialog_method(dialog_id, "close")


class Dialog(other.Dialog, UIComponent):
    """A themable modal dialog built on the native dialog element.

    When driving the dialog from state via ``open``, handle ``on_close`` to
    keep the state in sync when the user dismisses the dialog.
    """

    _slot: ClassVar[str | None] = "dialog"

    open: Var[bool] = field(
        doc="Drive the modal state from a Var; pair with on_close to stay in sync."
    )

    dismissible: Var[bool] = field(
        doc="Close the dialog when clicking the backdrop. Defaults to True."
    )

    on_close: EventHandler[no_args_event_spec] = field(
        doc="Fired when the dialog closes, including ESC and backdrop dismissal."
    )

    @classmethod
    def create(cls, *children, **props):
        """Create a dialog.

        Args:
            *children: The children of the component.
            **props: The props of the component.

        Returns:
            The dialog component.

        Raises:
            TypeError: If dismissible is not a static bool.
        """
        props.setdefault("id", f"dialog-{get_unique_variable_name()}")
        props.setdefault("aria_modal", "true")
        dismissible = props.get("dismissible")
        if isinstance(dismissible, Var) and not isinstance(
            getattr(dismissible, "_var_value", None), bool
        ):
            msg = "The dismissible prop must be a static bool, not a Var."
            raise TypeError(msg)
        cls._apply_class_name(DIALOG_CLASS_NAME, props)
        return super().create(*children, **props)

    def _is_dismissible(self) -> bool:
        """Resolve the static dismissible flag.

        Returns:
            Whether backdrop clicks close the dialog.
        """
        return (
            self.dismissible is None
            or getattr(self.dismissible, "_var_value", True) is not False
        )

    def add_imports(self) -> dict[str, str | list[str]]:
        """Add the imports for the dialog hooks.

        Returns:
            The imports for the dialog hooks.
        """
        return {"react": ["useEffect"]}

    def add_hooks(self) -> list[str | Var]:
        """Sync the modal state with the open prop and handle backdrop clicks.

        Returns:
            The hooks for the dialog element.
        """
        ref_name = self.get_ref()
        hooks: list[str | Var] = []
        if self._is_dismissible():
            # A click on the ::backdrop targets the dialog element itself, but
            # so does a click on the dialog's own padding -- only dismiss when
            # the pointer is outside the dialog's box.
            hooks.append(f"""
useEffect(() => {{
    const dialog = {ref_name}.current;
    if (!dialog) return;
    const handleMouseDown = (event) => {{
        if (event.target !== dialog) return;
        const rect = dialog.getBoundingClientRect();
        const inDialog = (
            rect.top <= event.clientY && event.clientY <= rect.bottom
            && rect.left <= event.clientX && event.clientX <= rect.right
        );
        if (!inDialog) dialog.close();
    }};
    dialog.addEventListener("mousedown", handleMouseDown);
    return () => dialog.removeEventListener("mousedown", handleMouseDown);
}}, []);
""")
        open_var = self.open
        if open_var is not None:
            hook_var_data = VarData.merge(
                open_var._get_all_var_data() if isinstance(open_var, Var) else None
            )
            open_expr = str(LiteralVar.create(open_var))
            hooks.append(
                Var(
                    _js_expr=f"""
useEffect(() => {{
    const dialog = {ref_name}.current;
    if (!dialog) return;
    if ({open_expr}) {{
        if (!dialog.open) dialog.showModal();
    }} else if (dialog.open) {{
        dialog.close();
    }}
}}, [{open_expr}]);
""",
                    _var_data=hook_var_data,
                )
            )
        return hooks

    def _exclude_props(self) -> list[str]:
        # The open attribute must not be rendered: it would show the dialog
        # non-modally. The modal state is driven by showModal()/close().
        return [
            *super()._exclude_props(),
            "open",
            "dismissible",
        ]


class DialogHeader(Div, UIComponent):
    """The header section of a dialog."""

    _slot: ClassVar[str | None] = "dialog-header"

    @classmethod
    def create(cls, *children, **props):
        """Create a dialog header.

        Args:
            *children: The children of the component.
            **props: The props of the component.

        Returns:
            The dialog header component.
        """
        cls._apply_class_name(DIALOG_HEADER_CLASS_NAME, props)
        return super().create(*children, **props)


class DialogTitle(H2, UIComponent):
    """The title of a dialog."""

    _slot: ClassVar[str | None] = "dialog-title"

    @classmethod
    def create(cls, *children, **props):
        """Create a dialog title.

        Args:
            *children: The children of the component.
            **props: The props of the component.

        Returns:
            The dialog title component.
        """
        cls._apply_class_name(DIALOG_TITLE_CLASS_NAME, props)
        return super().create(*children, **props)


class DialogDescription(P, UIComponent):
    """The description of a dialog."""

    _slot: ClassVar[str | None] = "dialog-description"

    @classmethod
    def create(cls, *children, **props):
        """Create a dialog description.

        Args:
            *children: The children of the component.
            **props: The props of the component.

        Returns:
            The dialog description component.
        """
        cls._apply_class_name(DIALOG_DESCRIPTION_CLASS_NAME, props)
        return super().create(*children, **props)


class DialogFooter(Div, UIComponent):
    """The footer section of a dialog."""

    _slot: ClassVar[str | None] = "dialog-footer"

    @classmethod
    def create(cls, *children, **props):
        """Create a dialog footer.

        Args:
            *children: The children of the component.
            **props: The props of the component.

        Returns:
            The dialog footer component.
        """
        cls._apply_class_name(DIALOG_FOOTER_CLASS_NAME, props)
        return super().create(*children, **props)


class DialogNamespace(ComponentNamespace):
    """Namespace for dialog components."""

    root = staticmethod(Dialog.create)
    header = staticmethod(DialogHeader.create)
    title = staticmethod(DialogTitle.create)
    description = staticmethod(DialogDescription.create)
    footer = staticmethod(DialogFooter.create)
    open = staticmethod(open_dialog)
    close = staticmethod(close_dialog)
    __call__ = staticmethod(Dialog.create)


dialog = DialogNamespace()
