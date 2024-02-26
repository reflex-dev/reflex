```python exec
import reflex as rx
```

# Substates

Substates allow you to break up your state into multiple classes to make it more manageable. This is useful as your app grows, as it allows you to think about each page as a separate entity. Substates also allow you to share common state resources, such as variables or event handlers.

## Multiple States

One common pattern is to create a substate for each page in your app.
This allows you to think about each page as a separate entity, and makes it easier to manage your code as your app grows.

To create a substate, simply inherit from `rx.State` multiple times:

```python
# index.py
import reflex as rx

class IndexState(rx.State):
    """Define your main state here."""
    data: str = "Hello World"


@rx.page()
def index():
    return rx.box(rx.text(IndexState.data)

# signup.py
import reflex as rx


class SignupState(rx.State):
    """Define your signup state here."""
    username: str = ""
    password: str = ""

    def signup(self):
        ...


@rx.page()
def signup_page():
    return rx.box(
        rx.chakra.input(value=SignupState.username),
        rx.chakra.input(value=SignupState.password),
    )

# login.py
import reflex as rx

class LoginState(rx.State):
    """Define your login state here."""
    username: str = ""
    password: str = ""

    def login(self):
        ...

@rx.page()
def login_page():
    return rx.box(
        rx.chakra.input(value=LoginState.username),
        rx.chakra.input(value=LoginState.password),
    )
```

Separating the states is purely a matter of organization. You can still access the state from other pages by importing the state class.

```python
# index.py

import reflex as rx

from signup import SignupState

...

def index():
    return rx.box(
        rx.text(IndexState.data),
        rx.chakra.input(value=SignupState.username),
        rx.chakra.input(value=SignupState.password),
    )
```

## State Inheritance

A substate can also inherit from another substate other than `rx.State`, allowing you to create a hierarchy of states.

For example, you can create a base state that defines variables and event handlers that are common to all pages in your app, such as the current logged in user.

```python
class BaseState(rx.State):
    """Define your base state here."""

    current_user: str = ""

    def logout(self):
        self.current_user = ""


class LoginState(BaseState):
    """Define your login state here."""

    username: str = ""
    password: str = ""

    def login(self, username, password):
        # authenticate
        authenticate(...)

        # Set the var on the parent state. 
        self.current_user = username
```

You can access the parent state properties from a child substate, however you
cannot access the child properties from the parent state.
