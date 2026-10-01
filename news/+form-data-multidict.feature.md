Form `on_submit` handlers can annotate their form data as `rx.MultiDict` to receive every value of fields that share a name, in submission order; a `dict` annotation still keeps each name's last value. In a `TypedDict` annotation, a `list[str]` field collects every value of its name and a `bool` field is `False` when nothing was submitted, such as for an unchecked checkbox; for `list[str] | None` and `bool | None` fields an unsubmitted value is `None`, or left out when `NotRequired`.

```python
@rx.event
def handle_submit(self, form_data: rx.MultiDict[str, str]):
    self.toppings = form_data.getlist("topping")
```
