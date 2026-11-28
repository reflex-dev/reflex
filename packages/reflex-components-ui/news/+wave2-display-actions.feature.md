Add the display and action components to `rx.ui`: `button`, `icon_button`, `badge`, `card`, `callout` (with `callout.root`, `callout.icon` and `callout.text`), `avatar`, `skeleton`, `spinner`, `table` (with its parts), `data_list` (with its parts), `progress` and `scroll_area`. Each takes the arguments of the component of the same name in `rx` and looks the same, in every variant, size, color, radius and state.

```python
rx.ui.card(
    rx.ui.heading("Invoice", size="3"),
    rx.ui.badge("Paid", color_scheme="green"),
    rx.ui.button("Send", loading=State.sending, on_click=State.send),
)
```
