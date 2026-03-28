```python exec
import reflex as rx
```

# Page Load Events

You can also specify a function to run when the page loads. This can be useful for fetching data once vs on every render or state change.
In this example, we fetch data when the page loads:

```python
class State(rx.State):
    data: Dict[str, Any]

    @rx.event
    def get_data(self):
        # Fetch data
        self.data = fetch_data()

@rx.page(on_load=State.get_data)
def index():
    return rx.text('A Beautiful App')
```

Another example would be checking if the user is authenticated when the page loads. If the user is not authenticated, we redirect them to the login page. If they are authenticated, we don't do anything, letting them access the page. This `on_load` event would be placed on every page that requires authentication to access.

```python
class State(rx.State):
    authenticated: bool

    @rx.event
    def check_auth(self):
        # Check if user is authenticated
        self.authenticated = check_auth()
        if not self.authenticated:
            return rx.redirect('/login')

@rx.page(on_load=State.check_auth)
def index():
    return rx.text('A Beautiful App')
```
