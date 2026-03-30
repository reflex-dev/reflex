---
components:
  - rx.tabs.root
  - rx.tabs.list
  - rx.tabs.trigger
  - rx.tabs.content

only_low_level:
  - True

TabsRoot: |
  lambda **props: rx.tabs.root(
      rx.tabs.list(
          rx.tabs.trigger("Account", value="account"),
          rx.tabs.trigger("Documents", value="documents"),
          rx.tabs.trigger("Settings", value="settings"),
      ),
      rx.box(
          rx.tabs.content(
              rx.text("Make changes to your account"),
              value="account",
          ),
          rx.tabs.content(
              rx.text("Update your documents"),
              value="documents",
          ),
          rx.tabs.content(
              rx.text("Edit your personal profile"),
              value="settings",
          ),
      ),
      **props,
  )

TabsList: |
  lambda **props: rx.tabs.root(
      rx.tabs.list(
          rx.tabs.trigger("Account", value="account"),
          rx.tabs.trigger("Documents", value="documents"),
          rx.tabs.trigger("Settings", value="settings"),
          **props,
      ),
      rx.box(
          rx.tabs.content(
              rx.text("Make changes to your account"),
              value="account",
          ),
          rx.tabs.content(
              rx.text("Update your documents"),
              value="documents",
          ),
          rx.tabs.content(
              rx.text("Edit your personal profile"),
              value="settings",
          ),
      ),
  )

TabsTrigger: |
  lambda **props: rx.tabs.root(
      rx.tabs.list(
          rx.tabs.trigger("Account", value="account", **props,),
          rx.tabs.trigger("Documents", value="documents"),
          rx.tabs.trigger("Settings", value="settings"),
      ),
      rx.box(
          rx.tabs.content(
              rx.text("Make changes to your account"),
              value="account",
          ),
          rx.tabs.content(
              rx.text("Update your documents"),
              value="documents",
          ),
          rx.tabs.content(
              rx.text("Edit your personal profile"),
              value="settings",
          ),
      ),
  )

TabsContent: |
  lambda **props: rx.tabs.root(
      rx.tabs.list(
          rx.tabs.trigger("Account", value="account"),
          rx.tabs.trigger("Documents", value="documents"),
          rx.tabs.trigger("Settings", value="settings"),
      ),
      rx.box(
          rx.tabs.content(
              rx.text("Make changes to your account"),
              value="account",
              **props,
          ),
          rx.tabs.content(
              rx.text("Update your documents"),
              value="documents",
              **props,
          ),
          rx.tabs.content(
              rx.text("Edit your personal profile"),
              value="settings",
              **props,
          ),
      ),
  )
---

```python exec
import reflex as rx
```

# Tabs

Tabs are a set of layered sections of content—known as tab panels that are displayed one at a time.
They facilitate the organization and navigation between sets of content that share a connection and exist at a similar level of hierarchy.

## Basic Example

```python demo
rx.tabs.root(
    rx.tabs.list(
        rx.tabs.trigger("Tab 1", value="tab1"),
        rx.tabs.trigger("Tab 2", value="tab2")
    ),
    rx.tabs.content(
        rx.text("item on tab 1"),
        value="tab1",
    ),
    rx.tabs.content(
        rx.text("item on tab 2"),
        value="tab2",
    ),
)

```

The `tabs` component is made up of a `rx.tabs.root` which groups `rx.tabs.list` and `rx.tabs.content` parts.

## Styling

### Default value

We use the `default_value` prop to set a default active tab, this will select the specified tab by default.

```python demo
rx.tabs.root(
    rx.tabs.list(
        rx.tabs.trigger("Tab 1", value="tab1"),
        rx.tabs.trigger("Tab 2", value="tab2")
    ),
    rx.tabs.content(
        rx.text("item on tab 1"),
        value="tab1",
    ),
    rx.tabs.content(
        rx.text("item on tab 2"),
        value="tab2",
    ),
    default_value="tab2",
)
```

### Orientation

We use `orientation` prop to set the orientation of the tabs component to `vertical` or `horizontal`. By default, the orientation
will be set to `horizontal`. Setting this value will change both the visual orientation and the functional orientation.

```md alert info
The functional orientation means for `vertical`, the `up` and `down` arrow keys moves focus between the next or previous tab,
while for `horizontal`, the `left` and `right` arrow keys moves focus between tabs.
```

```md alert warning
# When using vertical orientation, make sure to assign a tabs.content for each trigger.

Defining triggers without content will result in a visual bug where the width of the triggers list isn't constant.
```

```python demo
rx.tabs.root(
    rx.tabs.list(
        rx.tabs.trigger("Tab 1", value="tab1"),
        rx.tabs.trigger("Tab 2", value="tab2")
    ),
    rx.tabs.content(
        rx.text("item on tab 1"),
        value="tab1",
    ),
    rx.tabs.content(
        rx.text("item on tab 2"),
        value="tab2",
    ),
    default_value="tab1",
    orientation="vertical",
)
```

```python demo
rx.tabs.root(
    rx.tabs.list(
        rx.tabs.trigger("Tab 1", value="tab1"),
        rx.tabs.trigger("Tab 2", value="tab2")
    ),
    rx.tabs.content(
        rx.text("item on tab 1"),
        value="tab1",
    ),
    rx.tabs.content(
        rx.text("item on tab 2"),
        value="tab2",
    ),
    default_value="tab1",
    orientation="horizontal",
)
```

### Value

We use the `value` prop to specify the controlled value of the tab that we want to activate. This property should be used in conjunction with the `on_change` event argument.

```python demo exec
class TabsState(rx.State):
    """The app state."""

    value = "tab1"
    tab_selected = ""

    @rx.event
    def change_value(self, val):
        self.tab_selected = f"{val} clicked!"
        self.value = val


def index() -> rx.Component:
    return rx.container(
        rx.flex(
            rx.text(f"{TabsState.value}  clicked !"),
            rx.tabs.root(
                rx.tabs.list(
                    rx.tabs.trigger("Tab 1", value="tab1"),
                    rx.tabs.trigger("Tab 2", value="tab2"),
                ),
                rx.tabs.content(
                        rx.text("items on tab 1"),
                    value="tab1",
                ),
                rx.tabs.content(
                    rx.text("items on tab 2"),
                    value="tab2",
                ),
                default_value="tab1",
                value=TabsState.value,
                on_change=lambda x: TabsState.change_value(x),
            ),
            direction="column",
            spacing="2",
        ),
        padding="2em",
        font_size="2em",
        text_align="center",
    )
```

## Tablist

The Tablist is used to list the respective tabs to the tab component

## Tab Trigger

This is the button that activates the tab's associated content. It is typically used in the `Tablist`

## Styling

### Value

We use the `value` prop to assign a unique value that associates the trigger with content.

```python demo
rx.tabs.root(
    rx.tabs.list(
        rx.tabs.trigger("Tab 1", value="tab1"),
        rx.tabs.trigger("Tab 2", value="tab2"),
        rx.tabs.trigger("Tab 3", value="tab3")
    ),
)
```

### Disable

We use the `disabled` prop to disable the tab.

```python demo
rx.tabs.root(
    rx.tabs.list(
        rx.tabs.trigger("Tab 1", value="tab1"),
        rx.tabs.trigger("Tab 2", value="tab2"),
        rx.tabs.trigger("Tab 3", value="tab3", disabled=True)
    ),
)
```

## Tabs Content

Contains the content associated with each trigger.

## Styling

### Value

We use the `value` prop to assign a unique value that associates the content with a trigger.

```python
rx.tabs.root(
    rx.tabs.list(
        rx.tabs.trigger("Tab 1", value="tab1"),
        rx.tabs.trigger("Tab 2", value="tab2")
    ),
    rx.tabs.content(
        rx.text("item on tab 1"),
        value="tab1",
    ),
    rx.tabs.content(
        rx.text("item on tab 2"),
        value="tab2",
    ),
    default_value="tab1",
    orientation="vertical",
)
```
