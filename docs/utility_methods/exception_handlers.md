# Exception handlers

_Added in v0.5.7_

Exceptions handlers are functions that can be assigned to your app to handle exceptions that occur during the application runtime.
They are useful for customizing the response when an error occurs, logging errors, and performing cleanup tasks.

## Types

Reflex support two type of exception handlers `frontend_exception_handler` and `backend_exception_handler`.

They are used to handle exceptions that occur in the `frontend` and `backend` respectively.

The `frontend` errors are coming from the JavaScript side of the application, while `backend` errors are coming from the the event handlers on the Python side.

## Register an Exception Handler

To register an exception handler, assign it to `app.frontend_exception_handler` or `app.backend_exception_handler` to assign a function that will handle the exception.

The expected signature for an error handler is `def handler(exception: Exception)`.

```md alert warning
# Only named functions are supported as exception handler.
```

## Examples

```python
import reflex as rx

def custom_frontend_handler(exception: Exception) -> None:
    # My custom logic for frontend errors
    print("Frontend Error: " + str(exception))

def custom_backend_handler(exception: Exception) -> Optional[rx.event.EventSpec]:
    # My custom logic for backend errors
    print("Backend Error: " + str(exception))

app = rx.App(
    frontend_exception_handler = custom_frontend_handler,
    backend_exception_handler = custom_backend_handler
    )
```