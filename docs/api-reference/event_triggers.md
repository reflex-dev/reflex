```python exec
from datetime import datetime

import reflex as rx

from pcweb.templates.docpage import docdemo, h1_comp, text_comp, docpage

SYNTHETIC_EVENTS = [
    {
        "name": "on_focus",
        "description": "The on_focus event handler is called when the element (or some element inside of it) receives focus. For example, it’s called when the user clicks on a text input.",
        "state": """class FocusState(rx.State):
    text = "Change Me!"

    def change_text(self, text):
        if self.text == "Change Me!":
            self.text = "Changed!"
        else:
            self.text = "Change Me!"
""",
        "example": """rx.chakra.input(value = FocusState.text, on_focus=FocusState.change_text)""",
    },
    {
        "name": "on_blur",
        "description": "The on_blur event handler is called when focus has left the element (or left some element inside of it). For example, it’s called when the user clicks outside of a focused text input.",
        "state": """class BlurState(rx.State):
    text = "Change Me!"

    def change_text(self, text):
        if self.text == "Change Me!":
            self.text = "Changed!"
        else:
            self.text = "Change Me!"
""",
        "example": """rx.chakra.input(value = BlurState.text, on_blur=BlurState.change_text)""",
    },
    {
        "name": "on_change",
        "description": "The on_change event handler is called when the value of an element has changed. For example, it’s called when the user types into a text input each keystoke triggers the on change.",
        "state": """class ChangeState(rx.State):
    checked: bool = False

""",
        "example": """rx.switch(on_change=ChangeState.set_checked)""",
    },
    {
        "name": "on_click",
        "description": "The on_click event handler is called when the user clicks on an element. For example, it’s called when the user clicks on a button.",
        "state": """class ClickState(rx.State):
    text = "Change Me!"

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
        "description": "The on_mount event handler is called after the component is rendered on the page. It is similar to a page on_load event, although it does not necessarily fire when navigating between pages.",
        "state": """class MountState(rx.State):
    events: list[str] = []

    def on_mount(self):
        self.events = self.events[-4:] + ["on_mount @ " + str(datetime.now())]
""",
        "example": """rx.vstack(rx.foreach(MountState.events, rx.text), on_mount=MountState.on_mount)""",
    },
    {
        "name": "on_unmount",
        "description": "The on_unmount event handler is called after removing the component from the page. However, on_unmount will only be called for internal navigation, not when following external links or refreshing the page.",
        "state": """class UnmountState(rx.State):
    events: list[str] = []

    def on_unmount(self):
        self.events = self.events[-4:] + ["on_unmount @ " + str(datetime.now())]
""",
        "example": """rx.vstack(rx.foreach(UnmountState.events, rx.text), on_unmount=UnmountState.on_unmount)""",
    },
    {
        "name": "on_mouse_up",
        "description": "The on_mouse_up event handler is called when the user releases a mouse button on an element. For example, it’s called when the user releases the left mouse button on a button.",
        "state": """class MouseUpState(rx.State):
    text = "Change Me!"

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

```python eval
rx.box(
     rx.chakra.divider(),
    component_grid(),
)
```
