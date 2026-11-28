Add the form controls to `rx.ui`: `input` (also `text_field`), `text_area`, `checkbox`, `checkbox_group`, `checkbox_cards`, `radio` (also `radio_group`), `radio_cards`, `switch`, `slider`, `select`, `segmented_control` and `form`, with the members of each namespace. Each takes the arguments of the component of the same name in `rx` and looks the same. A control is the native element, drawn as Radix Themes draws its own, so it is in the page the server sends and works before JavaScript loads: a checkbox checks, a slider moves, a select opens.

```python
rx.ui.form.root(
    rx.ui.input(name="email", type="email", required=True),
    rx.ui.select(["Free", "Pro"], name="plan", default_value="Free"),
    rx.ui.checkbox("Send me updates", name="updates"),
    rx.ui.button("Sign up"),
    on_submit=State.sign_up,
)
```

The list of `rx.ui.select` is a native popover placed beside its trigger: it does not take the pointer off the rest of the page while it is open, and `position="item-aligned"` is placed as `"popper"` is.
