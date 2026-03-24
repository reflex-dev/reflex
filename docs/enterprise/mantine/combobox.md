---
title: Combobox
---

```python exec
import reflex as rx
import reflex_enterprise as rxe
from pcweb.pages.docs import enterprise
```

# Combobox

`rxe.mantine.combobox` is a wrapping of the mantine component [Combobox](https://mantine.dev/core/combobox/). It is a simple component that can be used to display a list of options, and allows the user to select one or more options from the list. It can be used in various contexts, such as in a form or as a standalone component.

```python
import reflex as rx
import reflex_enterprise as rxe

def combobox_page():
    """Combobox demo."""
    return rxe.mantine.combobox(
        rxe.mantine.combobox.target(
            rx.input(type="button"),
        ),
        rxe.mantine.combobox.dropdown(
            rxe.mantine.combobox.options(
                rxe.mantine.combobox.option("Option 1"),
                rxe.mantine.combobox.option("Option 2"),
                rxe.mantine.combobox.option("Option 3"),
            ),
        ),
        label="Combobox",
        placeholder="Select a value",
    )
```

