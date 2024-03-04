---
components:
    - rx.fragment
---

# Fragment

```python exec
import reflex as rx
from pcweb import constants
```

A Fragment is a Component that allow you to group multiple Components without a wrapper node.

Refer to the React docs at [React/Fragment]({constants.FRAGMENT_COMPONENT_INFO_URL}) for more information on its use-case.

```python demo
rx.fragment(
    rx.text("Component1"), 
    rx.text("Component2")
)
```
