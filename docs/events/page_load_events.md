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
    return rx.text("A Beautiful App")
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
            return rx.redirect("/login")


@rx.page(on_load=State.check_auth)
def index():
    return rx.text("A Beautiful App")
```

## Handling Loading and Errors

Avoid heavy synchronous work directly in an `on_load` handler — the page renders before the handler finishes, so a slow handler leaves the user staring at stale or empty data with no feedback. Instead:

- Use an async handler for network or database calls so the event loop is not blocked.
- Set a loading flag and `yield` to send it to the frontend immediately, then render a spinner or placeholder with `rx.cond`.
- Wrap the work in `try`/`except` so a failure surfaces as an error message instead of a page that never finishes loading.

```python
class DataState(rx.State):
    data: dict = {}
    loading: bool = False
    error: str = ""

    @rx.event
    async def load_initial_data(self):
        self.loading = True
        yield  # Send the loading state to the frontend immediately.
        try:
            self.data = await fetch_data()
        except Exception as e:
            self.error = str(e)
        finally:
            self.loading = False


@rx.page(on_load=DataState.load_initial_data)
def index():
    return rx.cond(
        DataState.loading,
        rx.spinner(),
        rx.cond(
            DataState.error != "",
            rx.text(f"Error: {DataState.error}"),
            rx.text(f"Data loaded: {DataState.data}"),
        ),
    )
```
