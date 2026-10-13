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
    frontend_exception_handler=custom_frontend_handler,
    backend_exception_handler=custom_backend_handler,
)
```

## Frontend and backend state mismatch

The compiled frontend and the backend can come from different builds of the app: a backend deploy changes the state while a browser keeps the old page, two backend versions run behind one load balancer during a rolling deploy, or `api_url` points at a backend that did not serve the frontend. The frontend then holds states, vars and event handlers the backend does not know, or the other way around.

Reflex detects this when the frontend connects. The compiled frontend carries a hash of the state tree it was built for (the state names, their frontend vars with types, and their event handler names) and sends it with every socket connect and reconnect. The backend computes the same hash over its own state tree and compares the two. Defaults and values are not part of the hash, so changing a default value does not count as a mismatch.

On a mismatch:

- In production, the page reloads once to fetch the new frontend. The reload shares the `REFLEX_AUTO_RELOAD_COOLDOWN` (default 10 seconds) with the automatic reload on frontend errors, so a page never reloads in a loop. When a reload already happened inside the cooldown (the reload landed on the same mismatch, for example a cached page or mixed backend versions) the page shows a banner saying a new version of the app is available, with a reload button, and keeps working as well as it can.
- In development, the frontend only logs a warning in the browser console. A backend hot reload can reconnect before the frontend dev server serves the rebuilt page, which gives a short-lived mismatch that resolves on its own.

The backend logs one warning per mismatched connection. A state update that names a state the frontend does not know is still reported through the `frontend_exception_handler`, as before.

```md alert warning
# Load balancers need sticky sessions.
When several backend versions run behind one load balancer, each reconnect can land on a different version, and the frontend cannot match all of them. Pin each client to one backend (sticky sessions) or to one deployment during a rollout; the framework cannot work around this.
```
