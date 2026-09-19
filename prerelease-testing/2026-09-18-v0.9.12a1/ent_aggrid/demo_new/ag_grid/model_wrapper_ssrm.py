"""Demo of a customized ModelWrapper with auth state."""

import asyncio
from typing import Any

import reflex as rx

import reflex_enterprise as rxe
from reflex_enterprise.components.ag_grid.datasource import SSRMDatasourceRequestParams

from .common import demo
from .model_wrapper_customized import AuthState
from .model_wrapper_simple import Friend


class CustomDatasourceParams(SSRMDatasourceRequestParams):
    """Custom request parameters for SSRM."""

    sid: str


# When extending a ModelWrapper, you can override methods to customize the behavior.
class FriendModelWrapperSSRM(rxe.ModelWrapperSSRM[Friend]):
    """Customized ModelWrapper for the Friend model."""

    __get_data_kwargs__ = {
        **rxe.ModelWrapperSSRM.__get_data_kwargs__,
        "sid": lambda self: self.router.session.session_id,
    }
    __data_source_params_class__ = CustomDatasourceParams

    enable_advanced_filter: bool = False

    def _get_column_defs(self):
        """In this example, we remove the ability to filter and sort a particular field."""
        cols = super()._get_column_defs()
        for col in cols:
            if col.field == "spouse_is_annoying":
                col.filter = None
                col.sortable = False
        return cols

    @rx.event
    async def on_value_setter(
        self, row_data: dict[str, Any], field_name: str, value: Any
    ):
        """In this example, we prevent modifications to the data if the user is not logged in."""
        auth_state = await self.get_state(AuthState)
        if not auth_state.logged_in:
            return  # no modification for logged out users
        return await super().on_value_setter(row_data, field_name, value)

    async def _get_data(
        self,
        params: CustomDatasourceParams,
    ):
        print(f"_get_data: CustomDatasourceParams.sid = {params.sid}")  # noqa: T201
        auth_state = await self.get_state(AuthState)
        if not auth_state.logged_in:
            return []  # no records for logged out users
        await asyncio.sleep(0.2)
        return await super()._get_data(params)

    @rx.var
    def selected_items(self) -> list[Friend]:
        """Get the selected items from the grid."""
        # Normally selected items are backend-only, but we can provide
        # a computed var to render them in the UI.
        return self._selected_items

    @rx.event
    def set_enable_advanced_filter(self, v: bool):
        """Set whether to use the advanced filter."""
        self.enable_advanced_filter = v

    @classmethod
    def _default_grid_props(cls) -> dict[str, Any]:
        return {
            **super()._default_grid_props(),
            "enable_advanced_filter": cls.enable_advanced_filter,
        }


# Advanced example of an extended ModelWrapper with custom behavior
@demo(
    route="/model-ssrm",
    title="SSRM ModelWrapper",
    description="Extended SSRM ModelWrapper with custom behavior and auth.",
)
def model_page_ssrm():
    """Page for the customized ModelWrapper demo."""
    grid = FriendModelWrapperSSRM.create(
        model_class=Friend,
        row_selection={"mode": "multiRow"},
        on_filter_opened=rx.console_log,
        on_filter_changed=rx.console_log,
        on_filter_modified=rx.console_log,
        on_filter_ui_changed=rx.console_log,
        on_floating_filter_ui_changed=rx.console_log,
        on_advanced_filter_builder_visible_changed=rx.console_log,
        loading_cell_renderer=rx.vars.function.ArgsFunctionOperation.create(
            args_names=["params"],
            return_expr=rx.Var.create(
                rx.box(
                    rx.cond(
                        rx.Var("params.node.failedLoad"),
                        rx.hstack(
                            rx.icon("x"),
                            rx.text(
                                "Failed to load rows: ",
                                rx.Var("params.node.parent.failReason"),
                                align="center",
                            ),
                        ),
                        rx.hstack(
                            rx.spinner(), rx.text("Loading rows..."), align="center"
                        ),
                    ),
                    padding_x="5px",
                ),
            ),
        ),
    )
    return rx.vstack(
        rx.hstack(
            rx.cond(
                AuthState.logged_in,
                rx.button("Logout", on_click=AuthState.toggle_login),
                rx.button("Login", on_click=AuthState.toggle_login),
            ),
            rx.cond(
                AuthState.logged_in,
                rx.button("Generate Friends", on_click=AuthState.generate_friends(50)),
            ),
            rx.foreach(
                grid.State.selected_items,  # pyright: ignore [reportAttributeAccessIssue]
                lambda friend: rx.badge(friend.name),
            )
            if grid.State
            else (),
            rx.spacer(),
            rx.card(
                rx.hstack(
                    "Enable Advanced Filter",
                    rx.switch(
                        checked=grid.State.enable_advanced_filter,
                        on_change=grid.State.set_enable_advanced_filter,
                    ),
                ),
            ),
            align="center",
            width="100%",
        ),
        rx.box(
            grid,
            width="100%",
            height="65vh",
            padding_bottom="60px",  # for scroll bar and controls
        ),
    )
