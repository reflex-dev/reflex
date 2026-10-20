Form `on_submit` handlers can annotate their form data as `rx.form.FormData` to receive every value of fields that share a name, in submission order; a `dict` annotation still keeps each name's last value. In a `TypedDict` annotation, a `list[str]` field collects every value of its name and a `bool` field is `False` when nothing was submitted, such as for an unchecked checkbox, or when the value is false-like, such as `"false"`, `"off"` or `"0"`; for `list[str] | None` and `bool | None` fields an unsubmitted value is `None`, and an unsubmitted `NotRequired` field is left out. In a `TypedDict`, a list field `range` also collects the `range[]` values a two-thumb `rx.slider(name="range")` submits.

```python
@rx.event
def handle_submit(self, form_data: rx.form.FormData[str, str]):
    self.toppings = form_data.getlist("topping")
```
