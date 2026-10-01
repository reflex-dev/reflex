Form `on_submit` handlers can annotate their form data as `starlette.datastructures.MultiDict` or `ImmutableMultiDict` to receive every value of fields that share a name, in submission order. `dict` annotations still keep each name's last value.

```python
@rx.event
def handle_submit(self, form_data: MultiDict):
    self.toppings = form_data.getlist("topping")
```
