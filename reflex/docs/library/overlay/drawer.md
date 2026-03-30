---
components:
  - rx.drawer.root
  - rx.drawer.trigger
  - rx.drawer.overlay
  - rx.drawer.portal
  - rx.drawer.content
  - rx.drawer.close

only_low_level:
  - True

DrawerRoot: |
  lambda **props: rx.drawer.root(
      rx.drawer.trigger(rx.button("Open Drawer")),
      rx.drawer.overlay(z_index="5"),
      rx.drawer.portal(
          rx.drawer.content(
              rx.flex(
                  rx.drawer.close(rx.button("Close")),
              ),
              height="100%",
              width="20em",
              background_color="#FFF"
          ),
      ),
      **props,
  )
---

```python exec
import reflex as rx
```

# Drawer

```python demo
rx.drawer.root(
        rx.drawer.trigger(
            rx.button("Open Drawer")
        ),
        rx.drawer.overlay(
            z_index="5"
        ),
        rx.drawer.portal(
            rx.drawer.content(
                rx.flex(
                    rx.drawer.close(rx.box(rx.button("Close"))),
                    align_items="start",
                    direction="column",
                ),
                top="auto",
                right="auto",
                height="100%",
                width="20em",
                padding="2em",
                background_color="#FFF"
                #background_color=rx.color("green", 3)
            )
        ),
        direction="left",
)
```

## Sidebar Menu with a Drawer and State

This example shows how to create a sidebar menu with a drawer. The drawer is opened by clicking a button. The drawer contains links to different sections of the page. When a link is clicked the drawer closes and the page scrolls to the section.

The `rx.drawer.root` component has an `open` prop that is set by the state variable `is_open`. Setting the `modal` prop to `False` allows the user to interact with the rest of the page while the drawer is open and allows the page to be scrolled when a user clicks one of the links.

```python demo exec
class DrawerState(rx.State):
    is_open: bool = False

    @rx.event
    def toggle_drawer(self):
        self.is_open = not self.is_open

def drawer_content():
    return rx.drawer.content(
        rx.flex(
            rx.drawer.close(rx.button("Close", on_click=DrawerState.toggle_drawer)),
            rx.link("Link 1", href="#test1", on_click=DrawerState.toggle_drawer),
            rx.link("Link 2", href="#test2", on_click=DrawerState.toggle_drawer),
            align_items="start",
            direction="column",
        ),
        height="100%",
        width="20%",
        padding="2em",
        background_color=rx.color("grass", 7),
    )


def lateral_menu():
    return rx.drawer.root(
        rx.drawer.trigger(rx.button("Open Drawer", on_click=DrawerState.toggle_drawer)),
        rx.drawer.overlay(),
        rx.drawer.portal(drawer_content()),
        open=DrawerState.is_open,
        direction="left",
        modal=False,
    )

def drawer_sidebar():
    return rx.vstack(
        lateral_menu(),
        rx.section(
            rx.heading("Test1", size="8"),
            id='test1',
            height="400px",
        ),
        rx.section(
            rx.heading("Test2", size="8"),
            id='test2',
            height="400px",
        )
    )
```
