```python exec
from datetime import datetime

import reflex as rx
```

# Event Triggers

Components can modify the state based on user events such as clicking a button or entering text in a field.
These events are triggered by event triggers.

Event triggers are component specific and are listed in the documentation for each component.

## Component Lifecycle Events

Reflex components have lifecycle events like `on_mount` and `on_unmount` that allow you to execute code at specific points in a component's existence. These events are crucial for initializing data, cleaning up resources, and creating dynamic user interfaces.

### When Lifecycle Events Are Activated

- **on_mount**: This event is triggered immediately after a component is rendered and attached to the DOM. It fires:
  - When a page containing the component is first loaded
  - When a component is conditionally rendered (appears after being hidden)
  - When navigating to a page containing the component using internal navigation
  - It does NOT fire when the page is refreshed or when following external links

- **on_unmount**: This event is triggered just before a component is removed from the DOM. It fires:
  - When navigating away from a page containing the component using internal navigation
  - When a component is conditionally removed from the DOM (e.g., via a condition that hides it)
  - It does NOT fire when refreshing the page, closing the browser tab, or following external links

## Page Load Events

In addition to component lifecycle events, Reflex also provides page-level events like `on_load` that are triggered when a page loads. The `on_load` event is useful for:

- Fetching data when a page first loads
- Checking authentication status
- Initializing page-specific state
- Setting default values for cookies or browser storage

You can specify an event handler to run when the page loads using the `on_load` parameter in the `@rx.page` decorator or `app.add_page()` method:

```python
class State(rx.State):
    data: dict = dict()

    @rx.event
    def get_data(self):
        # Fetch data when the page loads
        self.data = fetch_data()


@rx.page(on_load=State.get_data)
def index():
    return rx.text("Data loaded on page load")
```

This is particularly useful for authentication checks:

```python
class State(rx.State):
    authenticated: bool = False

    @rx.event
    def check_auth(self):
        # Check if user is authenticated
        self.authenticated = check_auth()
        if not self.authenticated:
            return rx.redirect("/login")


@rx.page(on_load=State.check_auth)
def protected_page():
    return rx.text("Protected content")
```

For more details on page load events, see the [page load events documentation](/docs/events/page_load_events).

# Event Reference

---

## on_focus

The on_focus event handler is called when the element (or some element inside of it) receives focus. For example, it's called when the user clicks on a text input.

```python demo exec
class FocusState(rx.State):
    text: str = "Change Me!"

    @rx.event
    def change_text(self, text):
        if self.text == "Change Me!":
            self.text = "Changed!"
        else:
            self.text = "Change Me!"


def focus_example():
    return rx.input(value=FocusState.text, on_focus=FocusState.change_text)
```

## on_blur

The on_blur event handler is called when focus has left the element (or left some element inside of it). For example, it's called when the user clicks outside of a focused text input.

```python demo exec
class BlurState(rx.State):
    text: str = "Change Me!"

    @rx.event
    def change_text(self, text):
        if self.text == "Change Me!":
            self.text = "Changed!"
        else:
            self.text = "Change Me!"


def blur_example():
    return rx.input(value=BlurState.text, on_blur=BlurState.change_text)
```

## on_change

The on_change event handler is called when the value of an element has changed. For example, it's called when the user types into a text input each keystroke triggers the on change.

```python demo exec
class ChangeState(rx.State):
    checked: bool = False

    @rx.event
    def set_checked(self):
        self.checked = not self.checked


def change_example():
    return rx.switch(on_change=ChangeState.set_checked)
```

## on_click

The on_click event handler is called when the user clicks on an element. For example, it's called when the user clicks on a button.

```python demo exec
class ClickState(rx.State):
    text: str = "Change Me!"

    @rx.event
    def change_text(self):
        if self.text == "Change Me!":
            self.text = "Changed!"
        else:
            self.text = "Change Me!"


def click_example():
    return rx.button(ClickState.text, on_click=ClickState.change_text)
```

## on_context_menu

The on_context_menu event handler is called when the user right-clicks on an element. For example, it's called when the user right-clicks on a button.

```python demo exec
class ContextState(rx.State):
    text: str = "Change Me!"

    @rx.event
    def change_text(self):
        if self.text == "Change Me!":
            self.text = "Changed!"
        else:
            self.text = "Change Me!"


def context_menu_example():
    return rx.button(ContextState.text, on_context_menu=ContextState.change_text)
```

## on_double_click

The on_double_click event handler is called when the user double-clicks on an element. For example, it's called when the user double-clicks on a button.

```python demo exec
class DoubleClickState(rx.State):
    text: str = "Change Me!"

    @rx.event
    def change_text(self):
        if self.text == "Change Me!":
            self.text = "Changed!"
        else:
            self.text = "Change Me!"


def double_click_example():
    return rx.button(
        DoubleClickState.text, on_double_click=DoubleClickState.change_text
    )
```

## on_mount

The on_mount event handler is called after the component is rendered on the page. It is similar to a page on_load event, although it does not necessarily fire when navigating between pages. This event is particularly useful for initializing data, making API calls, or setting up component-specific state when a component first appears.

```python demo exec
class MountState(rx.State):
    events: list[str] = []
    data: list[dict] = []
    loading: bool = False

    @rx.event
    def on_mount(self):
        self.events = self.events[-4:] + ["on_mount @ " + str(datetime.now())]

    @rx.event
    async def load_data(self):
        self.loading = True
        yield
        import asyncio

        await asyncio.sleep(1)
        self.data = [dict(id=1, name="Item 1"), dict(id=2, name="Item 2")]
        self.loading = False


def mount_example():
    return rx.vstack(
        rx.heading("Component Lifecycle Demo"),
        rx.foreach(MountState.events, rx.text),
        rx.cond(
            MountState.loading,
            rx.spinner(),
            rx.foreach(
                MountState.data,
                lambda item: rx.text(f"ID: {item['id']} - {item['name']}"),
            ),
        ),
        on_mount=MountState.on_mount,
    )
```

## on_unmount

The on_unmount event handler is called after removing the component from the page. However, on_unmount will only be called for internal navigation, not when following external links or refreshing the page. This event is useful for cleaning up resources, saving state, or performing cleanup operations before a component is removed from the DOM.

```python demo exec
class UnmountState(rx.State):
    events: list[str] = []
    resource_id: str = "resource-12345"
    status: str = "Resource active"

    @rx.event
    def on_unmount(self):
        self.events = self.events[-4:] + ["on_unmount @ " + str(datetime.now())]
        self.status = f"Resource {self.resource_id} cleaned up"

    @rx.event
    def initialize_resource(self):
        self.status = f"Resource {self.resource_id} initialized"


def unmount_example():
    return rx.vstack(
        rx.heading("Unmount Demo"),
        rx.foreach(UnmountState.events, rx.text),
        rx.text(UnmountState.status),
        rx.link(
            rx.button("Navigate Away (Triggers Unmount)"),
            href="/docs",
        ),
        on_mount=UnmountState.initialize_resource,
        on_unmount=UnmountState.on_unmount,
    )
```

## on_mouse_up

The on_mouse_up event handler is called when the user releases a mouse button on an element. For example, it's called when the user releases the left mouse button on a button.

```python demo exec
class MouseUpState(rx.State):
    text: str = "Change Me!"

    @rx.event
    def change_text(self):
        if self.text == "Change Me!":
            self.text = "Changed!"
        else:
            self.text = "Change Me!"


def mouse_up_example():
    return rx.button(MouseUpState.text, on_mouse_up=MouseUpState.change_text)
```

## on_mouse_down

The on_mouse_down event handler is called when the user presses a mouse button on an element. For example, it's called when the user presses the left mouse button on a button.

```python demo exec
class MouseDownState(rx.State):
    text: str = "Change Me!"

    @rx.event
    def change_text(self):
        if self.text == "Change Me!":
            self.text = "Changed!"
        else:
            self.text = "Change Me!"


def mouse_down_example():
    return rx.button(MouseDownState.text, on_mouse_down=MouseDownState.change_text)
```

## on_mouse_enter

The on_mouse_enter event handler is called when the user's mouse enters an element. For example, it's called when the user's mouse enters a button.

```python demo exec
class MouseEnterState(rx.State):
    text: str = "Change Me!"

    @rx.event
    def change_text(self):
        if self.text == "Change Me!":
            self.text = "Changed!"
        else:
            self.text = "Change Me!"


def mouse_enter_example():
    return rx.button(MouseEnterState.text, on_mouse_enter=MouseEnterState.change_text)
```

## on_mouse_leave

The on_mouse_leave event handler is called when the user's mouse leaves an element. For example, it's called when the user's mouse leaves a button.

```python demo exec
class MouseLeaveState(rx.State):
    text: str = "Change Me!"

    @rx.event
    def change_text(self):
        if self.text == "Change Me!":
            self.text = "Changed!"
        else:
            self.text = "Change Me!"


def mouse_leave_example():
    return rx.button(MouseLeaveState.text, on_mouse_leave=MouseLeaveState.change_text)
```

## on_mouse_move

The on_mouse_move event handler is called when the user moves the mouse over an element. For example, it's called when the user moves the mouse over a button.

```python demo exec
class MouseMoveState(rx.State):
    text: str = "Change Me!"

    @rx.event
    def change_text(self):
        if self.text == "Change Me!":
            self.text = "Changed!"
        else:
            self.text = "Change Me!"


def mouse_move_example():
    return rx.button(MouseMoveState.text, on_mouse_move=MouseMoveState.change_text)
```

## on_mouse_out

The on_mouse_out event handler is called when the user's mouse leaves an element. For example, it's called when the user's mouse leaves a button.

```python demo exec
class MouseOutState(rx.State):
    text: str = "Change Me!"

    @rx.event
    def change_text(self):
        if self.text == "Change Me!":
            self.text = "Changed!"
        else:
            self.text = "Change Me!"


def mouse_out_example():
    return rx.button(MouseOutState.text, on_mouse_out=MouseOutState.change_text)
```

## on_mouse_over

The on_mouse_over event handler is called when the user's mouse enters an element. For example, it's called when the user's mouse enters a button.

```python demo exec
class MouseOverState(rx.State):
    text: str = "Change Me!"

    @rx.event
    def change_text(self):
        if self.text == "Change Me!":
            self.text = "Changed!"
        else:
            self.text = "Change Me!"


def mouse_over_example():
    return rx.button(MouseOverState.text, on_mouse_over=MouseOverState.change_text)
```

## on_scroll

The on_scroll event handler is called when the user scrolls the page. For example, it's called when the user scrolls the page down.

```python demo exec
class ScrollState(rx.State):
    text: str = "Change Me!"

    @rx.event
    def change_text(self):
        if self.text == "Change Me!":
            self.text = "Changed!"
        else:
            self.text = "Change Me!"


def scroll_example():
    return rx.vstack(
        rx.text("Scroll to make the text below change."),
        rx.text(ScrollState.text),
        rx.text("Scroll to make the text above change."),
        on_scroll=ScrollState.change_text,
        overflow="auto",
        height="3em",
        width="100%",
    )
```
