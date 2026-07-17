```python exec
import reflex as rx
```

# Sign in with Google

Google authentication is added with the `reflex-google-auth` package. Manage your OAuth2 credentials (`GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`) in the [Google Cloud credentials console](https://console.developers.google.com/apis/credentials).

## Installation

```bash
pip install reflex-google-auth
```

## Environment variables

- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`

You do not need to check the client ID or client secret yourself — set them in the environment.

## Integrate with your Reflex app

Subclass `GoogleAuthState`. It provides a `token_is_valid` var that should be checked before returning any protected content, and a `tokeninfo` dict that contains the user's profile information.

```python
from reflex_google_auth import GoogleAuthState


class State(GoogleAuthState):
    @rx.var(cache=True)
    def protected_content(self) -> str:
        if self.token_is_valid:
            return f"This content can only be viewed by a logged in user. Nice to see you {self.tokeninfo['name']}"
        return "Not logged in."
```

To uniquely identify a user, use `GoogleAuthState.tokeninfo['sub']`.

## Displaying the login button

The `require_google_login` decorator wraps an existing component and shows the "Sign in with Google" button if the user is not already authenticated. It can be used on a page function or any subcomponent function of the page:

```python
from reflex_google_auth import require_google_login


@require_google_login
def protected_page():
    return rx.text("This content is only shown to authenticated users.")
```

The "Sign in with Google" button can also be displayed directly via `google_login()`, wrapped in a `google_oauth_provider`:

```python
from reflex_google_auth import google_login, google_oauth_provider


def page():
    return rx.el.div(
        google_oauth_provider(
            google_login(),
        ),
    )
```

## API reference

The following API is provided by `reflex_google_auth`:

```python
class TokenCredential(TypedDict, total=False):
    iss: str
    azp: str
    aud: str
    sub: str
    hd: str
    email: str
    email_verified: bool
    nbf: int
    name: str
    picture: str
    given_name: str
    family_name: str
    iat: int
    exp: int
    jti: str


class GoogleAuthState(rx.State):
    id_token_json: str = rx.LocalStorage()

    @rx.var(cache=True)
    def client_id(self) -> str: ...

    @rx.var(cache=True)
    def tokeninfo(self) -> TokenCredential: ...

    @rx.event
    def logout(self): ...

    @rx.var(cache=False)
    def token_is_valid(self) -> bool: ...

    @rx.var(cache=True)
    def user_name(self) -> str: ...

    @rx.var(cache=True)
    def user_email(self) -> str: ...


# Shows the "Sign in with Google" button.
def google_login(**props) -> rx.Component: ...


# Provides the Google OAuth context; wrap `google_login()` in this.
def google_oauth_provider(*children, **props) -> rx.Component: ...


# Decorator that gates a page/component behind Google login.
def require_google_login(
    page: Callable[[], rx.Component] | None = None,
    *,
    button: rx.Component | None = None,
) -> Callable: ...
```
