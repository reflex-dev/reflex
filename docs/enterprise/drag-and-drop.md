---
title: Drag and Drop
---

```python exec
import reflex as rx
import reflex_enterprise as rxe
from pcweb.pages.docs import enterprise
```

# Drag and Drop

Reflex Enterprise provides comprehensive drag and drop functionality for creating interactive UI elements using the `rxe.dnd` module. Built on top of react-dnd, it offers both high-level components for common use cases and low-level hooks for advanced scenarios.

```md alert warning
# Important: Always decorate functions defining `rxe.dnd.draggable` components with `@rx.memo` to avoid compilation errors.
```

## Basic Usage

### Simple Drag and Drop

Here's a basic example showing how to create a draggable item and drop target:

```python demo exec
import reflex as rx
import reflex_enterprise as rxe

class BasicDndState(rx.State):
    drop_count: int = 0

    def increment_drop_count(self):
        self.drop_count += 1


@rx.memo
def draggable_card():
    return rxe.dnd.draggable(
        rx.card(
            rx.text("Drag me!", weight="bold"),
            rx.text("I can be moved around"),
            bg="blue.500",
            color="white",
            p=4,
            cursor="grab",
            width="200px",
            height="100px"
        ),
        type="BasicCard",
        item={"message": "Hello from draggable!"},
    )

def basic_drag_drop():
    return rx.vstack(
        rx.text(f"Items dropped: {BasicDndState.drop_count}"),
        rx.hstack(
            draggable_card(),
            rxe.dnd.drop_target(
                rx.box(
                    "Drop Zone",
                    bg="gray.100",
                    border="2px dashed gray",
                    min_height="150px",
                    min_width="200px",
                    display="flex",
                    align_items="center",
                    justify_content="center",
                    font_weight="bold"
                ),
                accept=["BasicCard"],
                on_drop=BasicDndState.increment_drop_count,
            ),
            spacing="4",
            align="start"
        ),
        spacing="4"
    )
```

### Multi-Position Drag and Drop

Create a draggable item that can be moved between multiple drop targets:

```python demo exec
import reflex as rx
import reflex_enterprise as rxe

class MultiPositionState(rx.State):
    card_position: int = 0

    def set_card_position(self, position: int):
        self.card_position = position


@rx.memo
def movable_card():
    return rxe.dnd.draggable(
        rx.card(
            rx.text("Movable Card", weight="bold"),
            rx.text("Position: " + MultiPositionState.card_position.to_string()),
            bg="purple.500",
            color="white",
            p=4,
            width="180px",
            height="120px"
        ),
        type="MovableCard",
        border="2px solid purple",
    )

def drop_zone(position: int):
    params = rxe.dnd.DropTarget.collected_params
    return rxe.dnd.drop_target(
        rx.cond(
            MultiPositionState.card_position == position,
            movable_card(),
            rx.box(
                f"Drop Zone {position}",
                color="gray.600",
                font_weight="bold"
            )
        ),
        width="200px",
        height="200px",
        border="2px solid red",
        border_color=rx.cond(params.is_over, "green.500", "red.500"),
        bg=rx.cond(params.is_over, "green.100", "blue.100"),
        accept=["MovableCard"],
        on_drop=lambda _: MultiPositionState.set_card_position(position),
        display="flex",
        align_items="center",
        justify_content="center"
    )

def multi_position_example():
    return rx.vstack(
        rx.text("Drag the card between positions", weight="bold"),
        rx.grid(
            drop_zone(0),
            drop_zone(1),
            drop_zone(2),
            drop_zone(3),
            columns="2",
            spacing="4"
        ),
        spacing="4"
    )
```

## Advanced Features

### State Tracking with Collected Parameters

Access drag and drop state information using collected parameters:

```python demo exec
import reflex as rx
import reflex_enterprise as rxe

class StateTrackingState(rx.State):
    drag_info: str = "No drag activity"

    def set_drag_info(self, value: str):
        self.drag_info = value

@rx.memo
def tracked_draggable():
    drag_params = rxe.dnd.Draggable.collected_params
    return rxe.dnd.draggable(
        rx.card(
            rx.text("Tracked Draggable"),
            rx.text(rx.cond(drag_params.is_dragging, "Dragging...", "Ready to drag")),
            bg=rx.cond(drag_params.is_dragging, "orange.500", "blue.500"),
            color="white",
            p=4,
            opacity=rx.cond(drag_params.is_dragging, 0.5, 1.0)
        ),
        type="TrackedItem",
        on_end=StateTrackingState.set_drag_info("Drag ended")
    )

def tracked_drop_target():
    drop_params = rxe.dnd.DropTarget.collected_params
    return rxe.dnd.drop_target(
        rx.box(
            rx.text("Smart Drop Zone"),
            rx.text(rx.cond(drop_params.is_over, "Ready to receive!", "Waiting...")),
            bg=rx.cond(drop_params.is_over, "green.200", "gray.100"),
            border=rx.cond(drop_params.is_over, "2px solid green", "2px dashed gray"),
            p=4,
            min_height="150px",
            display="flex",
            flex_direction="column",
            align_items="center",
            justify_content="center"
        ),
        accept=["TrackedItem"],
        on_drop=StateTrackingState.set_drag_info("Item successfully dropped!"),
        on_hover=StateTrackingState.set_drag_info("Item hovering over drop zone")
    )

def state_tracking_example():
    return rx.vstack(
        rx.text(f"Status: {StateTrackingState.drag_info}"),
        rx.hstack(
            tracked_draggable(),
            tracked_drop_target(),
            spacing="4"
        ),
        spacing="4"
    )
```

### Dynamic Lists with Drag and Drop

Create dynamic draggable lists using `rx.foreach`:

```python demo exec
import reflex as rx
import reflex_enterprise as rxe

class ListItem(rx.Base):
    id: str
    text: str
    list_id: str

class DynamicListState(rx.State):
    list_a: list[ListItem] = [
        ListItem(id="1", text="Item 1", list_id="A"),
        ListItem(id="2", text="Item 2", list_id="A"),
        ListItem(id="3", text="Item 3", list_id="A"),
    ]
    list_b: list[ListItem] = [
        ListItem(id="4", text="Item 4", list_id="B"),
        ListItem(id="5", text="Item 5", list_id="B"),
    ]

    def move_item(self, item_data: dict, target_list: str):
        item_id = item_data.get("id")
        source_list = item_data.get("list_id")

        if not item_id or not source_list:
            return

        # Find the item in the source list
        source_items = getattr(self, f"list_{source_list.lower()}")
        item_to_move = None
        for item in source_items:
            if item.id == item_id:
                item_to_move = item
                break

        if not item_to_move:
            return

        # Remove from source list only
        if source_list == "A":
            self.list_a = [item for item in self.list_a if item.id != item_id]
        else:
            self.list_b = [item for item in self.list_b if item.id != item_id]

        # Create new item for target list
        new_item = ListItem(
            id=item_id,
            text=item_to_move.text,
            list_id=target_list
        )

        # Add to target list
        if target_list == "A":
            self.list_a.append(new_item)
        else:
            self.list_b.append(new_item)

@rx.memo
def draggable_list_item(item: ListItem):
    return rxe.dnd.draggable(
        rx.card(
            rx.text(item.text, weight="bold"),
            rx.text(f"From List {item.list_id}", size="2", color="gray.600"),
            p=3,
            cursor="grab",
            _hover={"bg": "gray.50"}
        ),
        type="ListItem",
        item={"id": item.id, "text": item.text, "list_id": item.list_id},
    )

def droppable_list(title: str, items: list[ListItem], list_id: str):
    return rxe.dnd.drop_target(
        rx.vstack(
            rx.text(title, weight="bold", size="5"),
            rx.vstack(
                rx.foreach(items, lambda item, index: draggable_list_item(item=item)),
                spacing="2",
                min_height="200px",
                width="100%"
            ),
            bg="gray.50",
            p=4,
            border_radius="md",
            border="2px dashed gray",
            width="250px"
        ),
        accept=["ListItem"],
        on_drop=lambda item: DynamicListState.move_item(item, list_id)
    )

def dynamic_list_example():
    return rx.hstack(
        droppable_list("List A", DynamicListState.list_a, "A"),
        droppable_list("List B", DynamicListState.list_b, "B"),
        spacing="6",
        align="start"
    )
```

## Core Components

### Draggable

The `rxe.dnd.draggable` component makes any element draggable:

**Key Properties:**
- `type`: String identifier for drag type matching
- `item`: Data object passed to drop handlers
- `on_end`: Called when drag operation ends

### Drop Target

The `rxe.dnd.drop_target` component creates areas that accept draggable items:

**Key Properties:**
- `accept`: List of drag types this target accepts
- `on_drop`: Called when item is dropped
- `on_hover`: Called when item hovers over target

### Collected Parameters

Access real-time drag/drop state:

**Draggable Parameters (`rxe.dnd.Draggable.collected_params`):**
- `is_dragging`: Boolean indicating if item is being dragged

**Drop Target Parameters (`rxe.dnd.DropTarget.collected_params`):**
- `is_over`: Boolean indicating if draggable is hovering
- `can_drop`: Boolean indicating if drop is allowed

# API Reference

### rxe.dnd.draggable

Creates a draggable component that can be moved around the interface.

**Parameters:**

- **`type`** (str, required): String identifier that must match the `accept` list of drop targets
- **`item`** (dict | Callable): Data object passed to drop handlers. Can be a static dictionary or a function that receives a `DragSourceMonitor` and returns data
- **`preview_options`** (dict): Configuration for the drag preview appearance
- **`options`** (dict): Additional drag source options like `dropEffect`
- **`on_end`** (EventHandler): Event handler called when drag operation completes
- **`can_drag`** (Callable): Function that determines if the item can be dragged
- **`is_dragging`** (Callable): Function to override the default dragging state detection
- **`collect`** (Callable): Function to collect custom properties from the drag monitor

### rxe.dnd.drop_target

Creates a drop target that can receive draggable items.

**Parameters:**

- **`accept`** (str | list[str], required): Drag type(s) this target accepts
- **`options`** (dict): Additional drop target configuration options
- **`on_drop`** (EventHandler): Event handler called when an item is dropped, receives the `item` data
- **`on_hover`** (EventHandler): Event handler called when an item hovers over the target
- **`can_drop`** (Callable): Function that determines if a specific item can be dropped
- **`collect`** (Callable): Function to collect custom properties from the drop monitor

## Monitor Classes

### DragSourceMonitor

Provides information about the drag operation state:

- **`is_dragging()`**: Returns `True` if this item is currently being dragged
- **`can_drag()`**: Returns `True` if the item can be dragged
- **`get_item()`**: Returns the item data being dragged
- **`get_item_type()`**: Returns the drag type string
- **`get_drop_result()`**: Returns the drop result (available in `on_end`)
- **`did_drop()`**: Returns `True` if the item was successfully dropped

### DropTargetMonitor

Provides information about the drop target state:

- **`is_over()`**: Returns `True` if a draggable item is hovering over this target
- **`can_drop()`**: Returns `True` if the hovering item can be dropped
- **`get_item()`**: Returns the item data of the hovering draggable
- **`get_item_type()`**: Returns the drag type of the hovering item

## Default Collected Parameters

### Draggable.collected_params

```python
{
    "is_dragging": bool,  # True when this item is being dragged
    "can_drag": bool      # True when this item can be dragged
}
```

### DropTarget.collected_params

```python
{
    "is_over": bool,           # True when a draggable is hovering
    "can_drop": bool,          # True when the hovering item can be dropped
    "item": dict | None        # Data from the hovering draggable item
}
```

## Advanced Usage Examples

### Data Passing with Item Parameter

The `item` parameter allows you to pass data from draggable components to drop handlers:

```python demo exec toggle
import reflex as rx
import reflex_enterprise as rxe

class SimpleState(rx.State):
    message: str = "No items dropped yet"

    def set_message_from_item(self, item: dict):
        self.message = f"Dropped: {item['name']}"

def simple_draggable():
    return rxe.dnd.draggable(
        rx.box(
            "Drag me!",
            p=4,
            bg="blue.100",
            border="1px solid blue",
            cursor="grab"
        ),
        type="simple",
        item={"name": "test_item", "value": 42}
    )

def simple_drop_target():
    return rxe.dnd.drop_target(
        rx.box(
            rx.text(SimpleState.message),
            p=4,
            bg="gray.100",
            border="2px dashed gray",
            min_height="100px"
        ),
        accept=["simple"],
        on_drop=SimpleState.set_message_from_item
    )

def item_data_example():
    return rx.vstack(
        simple_draggable(),
        simple_drop_target(),
        spacing="4"
    )
```

### Custom Collect Functions

The `collect` parameter allows you to access drag and drop state information in real-time:

```python demo exec toggle
import reflex as rx
import reflex_enterprise as rxe

class CollectState(rx.State):
    drag_info: str = "No drag activity"
    drop_info: str = "No drop activity"

    def handle_drop(self, item: dict):
        self.drop_info = f"Dropped: {item.get('name', 'Unknown')}"
        return rx.toast(f"Successfully dropped {item.get('name', 'item')}")



def collect_draggable():
    params = rxe.dnd.Draggable.collected_params
    return rxe.dnd.draggable(
        rx.box(
            rx.vstack(
                rx.text("Drag me!", weight="bold"),
                rx.text(f"Dragging: {params.is_dragging}", size="2"),
                rx.text(f"Can drag: {params.can_drag}", size="2"),
                spacing="1"
            ),
            p=4,
            bg=rx.cond(params.is_dragging, "blue.200", "blue.100"),
            border="1px solid blue",
            cursor=rx.cond(params.is_dragging, "grabbing", "grab"),
            opacity=rx.cond(params.is_dragging, 0.7, 1.0)
        ),
        type="collect_item",
        item={"id": "collect_test", "name": "Test Item"}
    )

def collect_drop_target():
    params = rxe.dnd.DropTarget.collected_params
    return rxe.dnd.drop_target(
        rx.box(
            rx.vstack(
                rx.text("Drop Zone", weight="bold"),
                rx.text(f"Is over: {params.is_over}", size="2"),
                rx.text(f"Can drop: {params.can_drop}", size="2"),
                rx.cond(
                    params.item,
                    rx.text(f"Hovering item: {params.item.get('name', 'Unknown')}", size="2"),
                    rx.text("No item hovering", size="2")
                ),
                spacing="1"
            ),
            p=4,
            bg=rx.cond(
                params.is_over & params.can_drop,
                "green.200",
                rx.cond(params.is_over, "yellow.200", "gray.100")
            ),
            border=rx.cond(
                params.is_over & params.can_drop,
                "2px solid green",
                rx.cond(params.is_over, "2px solid yellow", "2px dashed gray")
            ),
            min_height="120px"
        ),
        accept=["collect_item"],
        on_drop=CollectState.handle_drop,
    )

def custom_collect_example():
    return rx.vstack(
        rx.text("Real-time Monitor State", weight="bold", size="4"),
        rx.hstack(
            collect_draggable(),
            collect_drop_target(),
            spacing="6",
            align="start"
        ),
        rx.text(CollectState.drop_info, size="2", color="gray.600"),
        spacing="4"
    )
```

## Provider

Drag and drop functionality requires the `rxe.dnd.provider` component to wrap your app. The provider is automatically added when using `draggable` or `drop_target` components.

For manual control:

```python
def app():
    return rxe.dnd.provider(
        # Your app content
        your_app_content(),
        backend="HTML5"  # or "Touch" for mobile
    )
```

## Best Practices

1. **Always use `@rx.memo`** on functions containing draggable components
2. **Use descriptive type names** for better debugging
3. **Handle edge cases** in drop handlers (invalid items, etc.)
4. **Provide visual feedback** using collected parameters
5. **Test on mobile devices** with touch backend
6. **Keep item data lightweight** for better performance

---

[← Back to main documentation]({enterprise.overview.path})
