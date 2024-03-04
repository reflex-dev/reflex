```python exec
import reflex as rx
```

# Page Load Events

You can also specify a function to run when the page loads. This can be useful for fetching data once vs on every render or state change.
In this example, we fetch data when the page loads:

```python
class State(rx.State):
    data: Dict[str, Any]

    def get_data(self):
        # Fetch data
        self.data = fetch_data()

@rx.page(on_load=State.get_data)
def index():
    return rx.text('A Beautiful App')
```
