```python exec
from datetime import datetime

import reflex as rx

from pcweb.templates.docpage import docdemo, h1_comp, text_comp, docpage
from pcweb.pages.docs import events

SYNTHETIC_EVENTS = [
    {
        "name": "on_focus",
        "description": "The on_focus event handler is called when the element (or some element inside of it) receives focus. For example, it’s called when the user clicks on a text input.",
        "state": """class FocusState(rx.State):
    text = "Change Me!"

    @rx.event
    def change_text(self, text):
        if self.text == "Change Me!":
            self.text = "Changed!"
        else:
            self.text = "Change Me!"
""",
        "example": """rx.input(value=FocusState.text, on_focus=FocusState.change_text)""",
    },
    {
        "name": "on_blur",
        "description": "The on_blur event handler is called when focus has left the element (or left some element inside of it). For example, it’s called when the user clicks outside of a focused text input.",
        "state": """class BlurState(rx.State):
    text = "Change Me!"

    @rx.event
    def change_text(self, text):
        if self.text == "Change Me!":
            self.text = "Changed!"
        else:
            self.text = "Change Me!"
""",
        "example": """rx.input(value=BlurState.text, on_blur=BlurState.change_text)""",
    },
    {
        "name": "on_change",
        "description": "The on_change event handler is called when the value of an element has changed. For example, it’s called when the user types into a text input each keystroke triggers the on change.",
        "state": """class ChangeState(rx.State):
    checked: bool = False

    @rx.event
    def set_checked(self):
        self.checked = not self.checked

""",
        "example": """rx.switch(on_change=ChangeState.set_checked)""",
    },
    {
        "name": "on_click",
        "description": "The on_click event handler is called when the user clicks on an element. For example, it’s called when the user clicks on a button.",
        "state": """class ClickState(rx.State):
    text = "Change Me!"

    @rx.event
    def change_text(self):
        if self.text == "Change Me!":
            self.text = "Changed!"
        else:
            self.text = "Change Me!"
""",
        "example": """rx.button(ClickState.text, on_click=ClickState.change_text)""",
    },
    {
        "name": "on_context_menu",
        "description": "The on_context_menu event handler is called when the user right-clicks on an element. For example, it’s called when the user right-clicks on a button.",
        "state": """class ContextState(rx.State):
    text = "Change Me!"

    @rx.event
    def change_text(self):
        if self.text == "Change Me!":
            self.text = "Changed!"
        else:
            self.text = "Change Me!"
""",
        "example": """rx.button(ContextState.text, on_context_menu=ContextState.change_text)""",
    },
    {
        "name": "on_double_click",
        "description": "The on_double_click event handler is called when the user double-clicks on an element. For example, it’s called when the user double-clicks on a button.",
        "state": """class DoubleClickState(rx.State):
    text = "Change Me!"

    @rx.event
    def change_text(self):
        if self.text == "Change Me!":
            self.text = "Changed!"
        else:
            self.text = "Change Me!"
""",
        "example": """rx.button(DoubleClickState.text, on_double_click=DoubleClickState.change_text)""",
    },
    {
        "name": "on_mount",
        "description": "The on_mount event handler is called after the component is rendered on the page. It is similar to a page on_load event, although it does not necessarily fire when navigating between pages. This event is particularly useful for initializing data, making API calls, or setting up component-specific state when a component first appears.",
        "state": """class MountState(rx.State):
    events: list[str] = []
    data: list[dict] = []
    loading: bool = False

    @rx.event
    def on_mount(self):
        self.events = self.events[-4:] + ["on_mount @ " + str(datetime.now())]

    @rx.event
    async def load_data(self):
        # Common pattern: Set loading state, yield to update UI, then fetch data
        self.loading = True
        yield
        # Simulate API call
        import asyncio
        await asyncio.sleep(1)
        self.data = [dict(id=1, name="Item 1"), dict(id=2, name="Item 2")]
        self.loading = False
""",
        "example": """rx.vstack(
    rx.heading("Component Lifecycle Demo"),
    rx.foreach(MountState.events, rx.text),
    rx.cond(
        MountState.loading,
        rx.spinner(),
        rx.foreach(
            MountState.data,
            lambda item: rx.text(f"ID: {item['id']} - {item['name']}")
        )
    ),
    on_mount=MountState.on_mount,
)""",
    },
    {
        "name": "on_unmount",
        "description": "The on_unmount event handler is called after removing the component from the page. However, on_unmount will only be called for internal navigation, not when following external links or refreshing the page. This event is useful for cleaning up resources, saving state, or performing cleanup operations before a component is removed from the DOM.",
        "state": """class UnmountState(rx.State):
    events: list[str] = []
    resource_id: str = "resource-12345"
    status: str = "Resource active"

    @rx.event
    def on_unmount(self):
        self.events = self.events[-4:] + ["on_unmount @ " + str(datetime.now())]
        # Common pattern: Clean up resources when component is removed
        self.status = f"Resource {self.resource_id} cleaned up"

    @rx.event
    def initialize_resource(self):
        self.status = f"Resource {self.resource_id} initialized"
""",
        "example": """rx.vstack(
    rx.heading("Unmount Demo"),
    rx.foreach(UnmountState.events, rx.text),
    rx.text(UnmountState.status),
    rx.link(
        rx.button("Navigate Away (Triggers Unmount)"),
        href="/docs",
    ),
    on_mount=UnmountState.initialize_resource,
    on_unmount=UnmountState.on_unmount,
)""",
    },
    {
        "name": "on_mouse_up",
        "description": "The on_mouse_up event handler is called when the user releases a mouse button on an element. For example, it’s called when the user releases the left mouse button on a button.",
        "state": """class MouseUpState(rx.State):
    text = "Change Me!"

    @rx.event
    def change_text(self):
        if self.text == "Change Me!":
            self.text = "Changed!"
        else:
            self.text = "Change Me!"
""",
        "example": """rx.button(MouseUpState.text, on_mouse_up=MouseUpState.change_text)""",
    },
    {
        "name": "on_mouse_down",
        "description": "The on_mouse_down event handler is called when the user presses a mouse button on an element. For example, it’s called when the user presses the left mouse button on a button.",
        "state": """class MouseDown(rx.State):
    text = "Change Me!"

    @rx.event
    def change_text(self):
        if self.text == "Change Me!":
            self.text = "Changed!"
        else:
            self.text = "Change Me!"
""",
        "example": """rx.button(MouseDown.text, on_mouse_down=MouseDown.change_text)""",
    },
    {
        "name": "on_mouse_enter",
        "description": "The on_mouse_enter event handler is called when the user’s mouse enters an element. For example, it’s called when the user’s mouse enters a button.",
        "state": """class MouseEnter(rx.State):
    text = "Change Me!"

    @rx.event
    def change_text(self):
        if self.text == "Change Me!":
            self.text = "Changed!"
        else:
            self.text = "Change Me!"
""",
        "example": """rx.button(MouseEnter.text, on_mouse_enter=MouseEnter.change_text)""",
    },
    {
        "name": "on_mouse_leave",
        "description": "The on_mouse_leave event handler is called when the user’s mouse leaves an element. For example, it’s called when the user’s mouse leaves a button.",
        "state": """class MouseLeave(rx.State):
    text = "Change Me!"

    @rx.event
    def change_text(self):
        if self.text == "Change Me!":
            self.text = "Changed!"
        else:
            self.text = "Change Me!"
""",
        "example": """rx.button(MouseLeave.text, on_mouse_leave=MouseLeave.change_text)""",
    },
    {
        "name": "on_mouse_move",
        "description": "The on_mouse_move event handler is called when the user moves the mouse over an element. For example, it’s called when the user moves the mouse over a button.",
        "state": """class MouseMove(rx.State):
    text = "Change Me!"

    @rx.event
    def change_text(self):
        if self.text == "Change Me!":
            self.text = "Changed!"
        else:
            self.text = "Change Me!"
""",
        "example": """rx.button(MouseMove.text, on_mouse_move=MouseMove.change_text)""",
    },
    {
        "name": "on_mouse_out",
        "description": "The on_mouse_out event handler is called when the user’s mouse leaves an element. For example, it’s called when the user’s mouse leaves a button.",
        "state": """class MouseOut(rx.State):
    text = "Change Me!"

    @rx.event
    def change_text(self):
        if self.text == "Change Me!":
            self.text = "Changed!"
        else:
            self.text = "Change Me!"
""",
        "example": """rx.button(MouseOut.text, on_mouse_out=MouseOut.change_text)""",
    },
    {
        "name": "on_mouse_over",
        "description": "The on_mouse_over event handler is called when the user’s mouse enters an element. For example, it’s called when the user’s mouse enters a button.",
        "state": """class MouseOver(rx.State):
    text = "Change Me!"

    @rx.event
    def change_text(self):
        if self.text == "Change Me!":
            self.text = "Changed!"
        else:
            self.text = "Change Me!"
""",
        "example": """rx.button(MouseOver.text, on_mouse_over=MouseOver.change_text)""",
    },
    {
        "name": "on_scroll",
        "description": "The on_scroll event handler is called when the user scrolls the page. For example, it’s called when the user scrolls the page down.",
        "state": """class ScrollState(rx.State):
    text = "Change Me!"

    @rx.event
    def change_text(self):
        if self.text == "Change Me!":
            self.text = "Changed!"
        else:
            self.text = "Change Me!"
""",
        "example": """rx.vstack(
            rx.text("Scroll to make the text below change."),
            rx.text(ScrollState.text),
            rx.text("Scroll to make the text above change."),
            on_scroll=ScrollState.change_text,
            overflow = "auto",
            height = "3em",
            width = "100%",
        )""",
    },
]
for i in SYNTHETIC_EVENTS:
    exec(i["state"])

def component_grid():
    events = []
    for event in SYNTHETIC_EVENTS:
        events.append(
            rx.vstack(
                h1_comp(text=event["name"]),
                text_comp(text=event["description"]),
                docdemo(
                    event["example"], state=event["state"], comp=eval(event["example"])
                ),
                align_items="left",
            )
        )

    return rx.box(*events)
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
    return rx.text('Data loaded on page load')
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
            return rx.redirect('/login')

@rx.page(on_load=State.check_auth)
def protected_page():
    return rx.text('Protected content')
```

For more details on page load events, see the [page load events documentation]({events.page_load_events.path}).

# Event Reference

```python eval
rx.box(
    rx.divider(),
    component_grid(),
)
```
