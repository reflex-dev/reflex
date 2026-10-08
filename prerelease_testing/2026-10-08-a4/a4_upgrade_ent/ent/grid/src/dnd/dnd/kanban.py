"""Kanban Drag n Drop."""

import dataclasses
import json
import uuid
from typing import Any, Callable, Mapping

import reflex as rx

import reflex_enterprise as rxe
from reflex_enterprise.components.dnd import DropTargetMonitor

from .common import demo

COL_MIN_WIDTH = "300px"
COL_HEIGHT = "80vh"


@dataclasses.dataclass
class KanbanColumn:
    """Kanban column."""

    __drag_type__ = "KanbanDraggableColumn"

    id: str
    title: str
    description: str
    order: int


@dataclasses.dataclass
class ItemInfo:
    """Item information."""

    __drag_type__ = "KanbanDraggableItemInfo"

    id: str
    title: str
    description: str = ""
    order: int = 0
    column_id: str = ""


UnknownItem = ItemInfo(id="unknown", title="Error")


class KanbanState(rx.State):
    _columns: dict[str, KanbanColumn] = {}
    _items: dict[str, ItemInfo] = {}

    kanban_data_json: str = rx.LocalStorage()

    @rx.event
    def on_load(self):
        """Load the kanban data from local storage."""
        if self.kanban_data_json:
            try:
                data = json.loads(self.kanban_data_json)
            except ValueError:
                self.kanban_data_json = ""
                return rx.toast("Could not load your data from browser storage, sorry.")

            for col_data in data.get("columns", []):
                col = KanbanColumn(**col_data)
                self._columns[col.id] = col

            for item_data in data.get("items", []):
                item = ItemInfo(**item_data)
                self._items[item.id] = item

    @rx.event
    def on_save(self):
        """Save the kanban data to local storage."""
        data = {
            "columns": [dataclasses.asdict(col) for col in self._columns.values()],
            "items": [dataclasses.asdict(item) for item in self._items.values()],
        }
        self.kanban_data_json = json.dumps(data)

    @rx.var
    def items(self) -> dict[str, ItemInfo]:
        """Get items."""
        return self._items

    @rx.var
    def ordered_items_by_column_id(self) -> dict[str, list[ItemInfo]]:
        """Get items ordered by column."""
        items_by_column = {}
        for item in self._items.values():
            items_by_column.setdefault(item.column_id, []).append(item)
        return {
            col_id: sorted(items, key=lambda x: x.order)
            for col_id, items in items_by_column.items()
        }

    @rx.var
    def columns(self) -> dict[str, KanbanColumn]:
        """Get columns."""
        return self._columns

    @rx.var
    def ordered_columns(self) -> list[KanbanColumn]:
        """Get columns ordered by order."""
        columns = list(self._columns.values())
        columns.sort(key=lambda x: x.order)
        return columns

    @rx.event
    def on_item_drop(
        self,
        column_id: str,
        replace_position: int,
        dropped_item_data: dict[str, Any],
    ):
        """Handle item drop."""
        dropped_item_id = dropped_item_data.get("id")
        if not dropped_item_id:
            return
        dropped_item = self._items.get(dropped_item_id)
        if not dropped_item:
            return
        new_items = self.ordered_items_by_column_id.get(column_id, [])
        try:
            ix_prior_to_drop = new_items.index(dropped_item)
            # When the item is moving to a higher position in the same column,
            # decrement the replace_position to account for the item being removed
            if ix_prior_to_drop < replace_position:
                replace_position -= 1
        except ValueError:
            # The item is not in the new column, so we don't need to adjust the position
            pass
        dropped_item.column_id = column_id
        new_items = [
            item
            for item in self.ordered_items_by_column_id.get(column_id, [])
            if item.id != dropped_item.id
        ]
        if replace_position < 0:
            new_items.append(dropped_item)
        else:
            new_items.insert(replace_position, dropped_item)
        # Update the order for all items in the column
        for ix, item in enumerate(new_items):
            item.order = ix
            self._items[item.id] = item
        self.on_save()

    @rx.event
    def on_column_drop(
        self,
        replace_position: int,
        dropped_column_data: dict[str, Any],
    ):
        """Handle column drop."""
        dropped_column_id = dropped_column_data.get("id")
        if not dropped_column_id:
            return
        dropped_column = self._columns.get(dropped_column_id)
        if not dropped_column:
            return
        new_columns = self.ordered_columns
        try:
            ix_prior_to_drop = new_columns.index(dropped_column)
            # When the column is moving to a higher position, decrement the
            # replace_position to account for the column being removed
            if ix_prior_to_drop < replace_position:
                replace_position -= 1
        except ValueError:
            pass
        new_columns.remove(dropped_column)
        if replace_position < 0:
            new_columns.append(dropped_column)
        else:
            new_columns.insert(replace_position, dropped_column)
        # Update the order for all columns
        for ix, col in enumerate(new_columns):
            col.order = ix
            self._columns[col.id] = col
        self.on_save()

    @rx.event
    def new_column(self, form_data: dict[str, Any]):
        """Create a new column."""
        name = form_data.get("name")
        if not name:
            return
        col = KanbanColumn(
            id=str(uuid.uuid4()),
            title=name,
            description="",
            order=len(self._columns),
        )
        self._columns[col.id] = col
        self.on_save()

    @rx.event
    def new_item(self, form_data: dict[str, Any]):
        """Create a new item."""
        column_id = form_data.get("column_id")
        name = form_data.get("name")
        if not column_id or not name:
            return
        item = ItemInfo(
            id=str(uuid.uuid4()),
            title=name,
            description="",
            order=len(self.ordered_items_by_column_id.get(column_id, [])),
            column_id=column_id,
        )
        self._items[item.id] = item
        self.on_save()

    @classmethod
    def can_drop_item(
        cls,
        column_id: rx.vars.StringVar[str] | str,
        replace_position: rx.vars.NumberVar[int] | int,
    ) -> Callable[[rx.Var[Any], DropTargetMonitor], rx.Var[bool]]:
        n_items_in_column = KanbanState.ordered_items_by_column_id.get(
            column_id, []
        ).length()

        @rxe.static
        def _can_drop(
            item: rx.vars.ObjectVar[Mapping[str, str]], monitor: DropTargetMonitor
        ) -> rx.Var[bool]:
            dragged_item = cls.item_by_id(item.id)
            return (dragged_item.column_id != column_id) | ~rx.Var.create(
                [dragged_item.order, dragged_item.order.to(int) + 1]
            ).contains(
                rx.cond(
                    replace_position < 0,
                    n_items_in_column,
                    replace_position,
                )
            )

        return _can_drop

    @classmethod
    def item_by_id(cls, item_id: rx.Var[str]) -> rx.vars.ObjectVar[ItemInfo]:
        """Get an item by its ID."""
        return cls.items.get(item_id.to(str), UnknownItem).to(ItemInfo)

    @classmethod
    def can_drop_column(
        cls,
        replace_position: rx.vars.NumberVar[int] | int,
    ) -> Callable[[rx.Var[Any], DropTargetMonitor], rx.Var[bool]]:
        n_columns = KanbanState.ordered_columns.length()

        @rxe.static
        def _can_drop(
            item: rx.vars.ObjectVar[Mapping[str, str]], monitor: DropTargetMonitor
        ) -> rx.Var[bool]:
            dragged_column = cls.columns[item.id]
            return ~rx.Var.create(
                [dragged_column.order, dragged_column.order.to(int) + 1]
            ).contains(
                rx.cond(
                    replace_position < 0,
                    n_columns,
                    replace_position,
                )
            )

        return _can_drop


@rx.memo
def item_card(item: ItemInfo, dragging: bool = False):
    return rx.card(
        rx.text(item.title),
        rx.text(item.order, size="1"),
        width="100%",
        background_color=rx.cond(dragging, "green", "inherit"),
    )


@rx.memo
def item_card_drop_target(item: ItemInfo):
    return item_drop_target(
        column_id=item.column_id,
        replace_position=item.order,
        child_after=rxe.dnd.draggable(
            item_card(item=item),
            item={"id": item.id},
            type=ItemInfo.__drag_type__,
            width="100%",
            cursor=rx.cond(
                rxe.dnd.Draggable.collected_params.is_dragging,
                "grabbing",
                "grab",
            ),
            on_end=lambda item: rx.toast(f"You dropped {item.id}"),
        ),
    )


@rx.memo
def item_drop_target(
    column_id: str,
    replace_position: int,
    child_before: rx.Component = rx.fragment(),
    child_after: rx.Component = rx.fragment(),
):
    params = rxe.dnd.DropTarget.collected_params
    dragged_item = KanbanState.item_by_id(params.item.id)
    return rxe.dnd.drop_target(
        rx.vstack(
            child_before,
            rx.cond(
                params.is_over & params.can_drop,
                item_card(item=dragged_item, dragging=True),
            ),
            child_after,
            padding="var(--space-2)",
            width="100%",
        ),
        accept=[ItemInfo.__drag_type__],
        can_drop=KanbanState.can_drop_item(
            column_id=column_id,
            replace_position=replace_position,
        ),
        on_drop=KanbanState.on_item_drop(column_id, replace_position),
        width="100%",
    )


@rx.memo
def column_drop_target(
    replace_position: int,
    child_before: rx.Component = rx.fragment(),
    child_after: rx.Component = rx.fragment(),
):
    params = rxe.dnd.DropTarget.collected_params
    dragged_column = KanbanState.columns.get(params.item.id.to(str), None)
    return rxe.dnd.drop_target(
        rx.hstack(
            child_before,
            rx.cond(
                params.is_over & params.can_drop,
                kanban_column(
                    col=dragged_column,
                    dragging=True,
                ),
                rx.cond(params.is_over, kanban_column(col=dragged_column)),
            ),
            child_after,
            padding="var(--space-1)",
            width="100%",
        ),
        accept=[KanbanColumn.__drag_type__],
        can_drop=KanbanState.can_drop_column(
            replace_position=replace_position,
        ),
        on_drop=KanbanState.on_column_drop(replace_position),
        width="100%",
        height=COL_HEIGHT,
    )


@rx.memo
def kanban_column(
    col: KanbanColumn,
    dragging: bool = False,
):
    """Render a kanban column."""
    return rx.card(
        rx.vstack(
            item_drop_target(
                column_id=col.id,
                replace_position=0,
                child_before=rx.heading(col.title, width="100%"),
            ),
            rx.foreach(
                KanbanState.ordered_items_by_column_id.get(col.id, []),
                lambda item: item_card_drop_target(
                    item=item,
                    key=item.id,
                ),
            ),
            item_drop_target(
                column_id=col.id,
                replace_position=-1,
                child_after=rx.form(
                    rx.hstack(
                        rx.input(placeholder="New Item", name="name", flex_grow="1"),
                        rx.el.input(type="hidden", name="column_id", value=col.id),
                        rx.button("Add"),
                        width="100%",
                    ),
                    on_submit=KanbanState.new_item,
                    reset_on_submit=True,
                    width="100%",
                    cursor="default",
                ),
            ),
            width="100%",
            spacing="0",
        ),
        min_width=COL_MIN_WIDTH,
        background_color=rx.cond(dragging, "green", "inherit"),
        margin_x="0",
    )


@rx.memo
def kanban_column_drop_target(col: KanbanColumn):
    return column_drop_target(
        replace_position=col.order,
        child_after=rxe.dnd.draggable(
            rx.el.div(
                kanban_column(col=col),
                width="100%",
                style={
                    "&": rx.cond(
                        rxe.dnd.Draggable.collected_params.is_dragging,
                        {"display": "none", "cursor": "grabbing"},
                        {"cursor": "move"},
                    )
                },
            ),
            item={"id": col.id},
            type=KanbanColumn.__drag_type__,
        ),
    )


@demo(
    route="/kanban",
    title="Kanban Board Demo",
    description="A multi-draggable UI for task management.",
    on_load=KanbanState.on_load,
)
def kanban_page() -> rx.Component:
    # Welcome Page (Index)
    return rx.container(
        rx.hstack(
            rx.foreach(
                KanbanState.ordered_columns,
                lambda col: kanban_column_drop_target(
                    col=col,
                    key=col.id,
                ),
            ),
            column_drop_target(
                replace_position=-1,
                child_after=rx.form(
                    rx.hstack(
                        rx.input(placeholder="New Column", name="name"),
                        rx.button("Add"),
                        min_width=COL_MIN_WIDTH,
                    ),
                    on_submit=KanbanState.new_column,
                    reset_on_submit=True,
                ),
            ),
            spacing="0",
        ),
    )
