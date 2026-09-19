"""Demo of a customized ModelWrapper with auth state."""

from typing import Any

import reflex as rx

import reflex_enterprise as rxe
from reflex_enterprise.components.ag_grid.datasource import DatasourceParams

from .common import demo
from .model_wrapper_simple import Friend


# This bogus auth state demonstrates how an extended ModelWrapper can check
# against values in another state before returning/modifying the data.
class AuthState(rx.State):
    """State for the auth demo."""

    _logged_in: bool = False

    @rx.var
    def logged_in(self) -> bool:
        """Whether the user is logged in."""
        return self._logged_in

    @rx.event
    def toggle_login(self):
        """Toggle the login state."""
        self._logged_in = not self._logged_in
        return self._refresh_grid()

    def _refresh_grid(self):
        from .model_wrapper_ssrm import FriendModelWrapperSSRM

        return [
            cls.on_mount
            for cls in FriendModelWrapper.__subclasses__()
            + FriendModelWrapperSSRM.__subclasses__()
        ]

    @rx.event
    async def generate_friends(self, n: int):
        """If only it were that easy..."""
        from .model_wrapper_ssrm import FriendModelWrapperSSRM

        if not self._logged_in:
            yield rx.toast.error("You must be logged in to generate friends.")
            return
        with rx.session() as session:
            for f in Friend.generate_fakes(n):
                session.add(f)
            session.commit()
        yield rx.toast.info(f"Created {n} friends.")
        for cls in (
            FriendModelWrapper.__subclasses__()
            + FriendModelWrapperSSRM.__subclasses__()
        ):
            inst = await self.get_state(cls)
            yield cls._grid_component.api.set_row_count(await inst._row_count())


# When extending a ModelWrapper, you can override methods to customize the behavior.
class FriendModelWrapper(rxe.ModelWrapper[Friend]):
    """Customized ModelWrapper for the Friend model."""

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
        params: DatasourceParams,
    ) -> list[Friend]:
        auth_state = await self.get_state(AuthState)
        if not auth_state.logged_in:
            return []  # no records for logged out users
        return await super()._get_data(params)

    @rx.var
    def selected_items(self) -> list[Friend]:
        """Get the selected items from the grid."""
        # Normally selected items are backend-only, but we can provide
        # a computed var to render them in the UI.
        return self._selected_items


# Advanced example of an extended ModelWrapper with custom behavior
@demo(
    route="/model-auth",
    title="Customized ModelWrapper",
    description="Extended infinite-row ModelWrapper with custom behavior and auth.",
)
def model_page_auth():
    """Page for the customized ModelWrapper demo."""
    grid = FriendModelWrapper.create(
        model_class=Friend,
        row_selection={"mode": "multiRow"},
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
        ),
        rx.box(
            grid,
            width="100%",
            height="65vh",
            padding_bottom="60px",  # for scroll bar and controls
        ),
    )
