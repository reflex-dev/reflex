---
components:
    - rx.chakra.Alert
    - rx.chakra.AlertIcon
    - rx.chakra.AlertTitle
    - rx.chakra.AlertDescription
---

```python exec
import reflex as rx
```

# Alert

Alerts are used to communicate a state that affects a system, feature or page.
An example of the different alert statuses is shown below.

```python demo
rx.chakra.vstack(
    rx.chakra.alert(
        rx.chakra.alert_icon(),
        rx.chakra.alert_title("Error Reflex version is out of date."),
        status="error",
    ),
    rx.chakra.alert(
        rx.chakra.alert_icon(),
        rx.chakra.alert_title("Warning Reflex version is out of date."),
        status="warning",
    ),
    rx.chakra.alert(
        rx.chakra.alert_icon(),
        rx.chakra.alert_title("Reflex version is up to date."),
        status="success",
    ),
    rx.chakra.alert(
        rx.chakra.alert_icon(),
        rx.chakra.alert_title("Reflex version is 0.1.32."),
        status="info",
    ),
    width="100%",
)
```

Along with different status types, alerts can also have different style variants and an optional description.
By default the variant is 'subtle'.

```python demo
rx.chakra.vstack(
    rx.chakra.alert(
        rx.chakra.alert_icon(),
        rx.chakra.alert_title("Reflex version is up to date."),
        rx.chakra.alert_description("No need to update."),
        status="success",
        variant="subtle",
    ),
    rx.chakra.alert(
        rx.chakra.alert_icon(),
        rx.chakra.alert_title("Reflex version is up to date."),
        status="success",
        variant="solid",
    ),
    rx.chakra.alert(
        rx.chakra.alert_icon(),
        rx.chakra.alert_title("Reflex version is up to date."),
        status="success",
        variant="top-accent",
    ),
    width="100%",
)
```
