```python exec
import reflex as rx
```

# Login Form

The login form is a common component in web applications. It allows users to authenticate themselves and access their accounts. This recipe provides examples of login forms with different elements, such as third-party authentication providers.

## Default

```python demo exec
def login_default() -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.center(
                rx.image(
                    src="https://web.reflex-assets.dev/other/logo.jpg",
                    alt="Reflex logo",
                    width="2.5em",
                    height="auto",
                    border_radius="25%",
                ),
                rx.heading(
                    "Sign in to your account",
                    size="6",
                    as_="h2",
                    text_align="center",
                    width="100%",
                ),
                direction="column",
                spacing="5",
                width="100%",
            ),
            rx.vstack(
                rx.text(
                    "Email address",
                    size="3",
                    weight="medium",
                    text_align="left",
                    width="100%",
                ),
                rx.input(
                    placeholder="user@reflex.dev", type="email", size="3", width="100%"
                ),
                justify="start",
                spacing="2",
                width="100%",
            ),
            rx.vstack(
                rx.hstack(
                    rx.text("Password", size="3", weight="medium"),
                    rx.link("Forgot password?", href="#", size="3"),
                    justify="between",
                    width="100%",
                ),
                rx.input(
                    placeholder="Enter your password",
                    type="password",
                    size="3",
                    width="100%",
                ),
                spacing="2",
                width="100%",
            ),
            rx.button("Sign in", size="3", width="100%"),
            rx.center(
                rx.text("New here?", size="3"),
                rx.link("Sign up", href="#", size="3"),
                opacity="0.8",
                spacing="2",
                direction="row",
            ),
            spacing="6",
            width="100%",
        ),
        size="4",
        max_width="28em",
        width="100%",
    )
```

```python test
def test_login_form(demo):
    view = demo.get_by_role("tabpanel", name="View")
    expect(view.get_by_role("heading")).to_have_text("Sign in to your account")
    expect(view.get_by_placeholder("user@reflex.dev")).to_have_attribute(
        "type", "email"
    )
    expect(view.get_by_placeholder("Enter your password")).to_have_attribute(
        "type", "password"
    )
    expect(view.get_by_role("button")).to_have_text(["Sign in"])
    expect(view.get_by_role("link")).to_have_text(["Forgot password?", "Sign up"])
```

## Icons

```python demo exec
def login_default_icons() -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.center(
                rx.image(
                    src="https://web.reflex-assets.dev/other/logo.jpg",
                    alt="Reflex logo",
                    width="2.5em",
                    height="auto",
                    border_radius="25%",
                ),
                rx.heading(
                    "Sign in to your account",
                    size="6",
                    as_="h2",
                    text_align="center",
                    width="100%",
                ),
                direction="column",
                spacing="5",
                width="100%",
            ),
            rx.vstack(
                rx.text(
                    "Email address",
                    size="3",
                    weight="medium",
                    text_align="left",
                    width="100%",
                ),
                rx.input(
                    rx.input.slot(rx.icon("user")),
                    placeholder="user@reflex.dev",
                    type="email",
                    size="3",
                    width="100%",
                ),
                spacing="2",
                width="100%",
            ),
            rx.vstack(
                rx.hstack(
                    rx.text("Password", size="3", weight="medium"),
                    rx.link("Forgot password?", href="#", size="3"),
                    justify="between",
                    width="100%",
                ),
                rx.input(
                    rx.input.slot(rx.icon("lock")),
                    placeholder="Enter your password",
                    type="password",
                    size="3",
                    width="100%",
                ),
                spacing="2",
                width="100%",
            ),
            rx.button("Sign in", size="3", width="100%"),
            rx.center(
                rx.text("New here?", size="3"),
                rx.link("Sign up", href="#", size="3"),
                opacity="0.8",
                spacing="2",
                direction="row",
                width="100%",
            ),
            spacing="6",
            width="100%",
        ),
        max_width="28em",
        size="4",
        width="100%",
    )
```

```python test
def test_login_form_with_icons(demo):
    view = demo.get_by_role("tabpanel", name="View")
    expect(view.get_by_role("heading")).to_have_text("Sign in to your account")
    expect(view.locator("svg.lucide-user")).to_have_count(1)
    expect(view.locator("svg.lucide-lock")).to_have_count(1)
    view.get_by_placeholder("user@reflex.dev").fill("user@reflex.dev")
    expect(view.get_by_placeholder("user@reflex.dev")).to_have_value("user@reflex.dev")
    expect(view.get_by_role("button")).to_have_text(["Sign in"])
```

## Third-party auth

```python demo exec
def login_single_thirdparty() -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.flex(
                rx.image(
                    src="https://web.reflex-assets.dev/other/logo.jpg",
                    alt="Reflex logo",
                    width="2.5em",
                    height="auto",
                    border_radius="25%",
                ),
                rx.heading(
                    "Sign in to your account",
                    size="6",
                    as_="h2",
                    text_align="left",
                    width="100%",
                ),
                rx.hstack(
                    rx.text("New here?", size="3", text_align="left"),
                    rx.link("Sign up", href="#", size="3"),
                    spacing="2",
                    opacity="0.8",
                    width="100%",
                ),
                direction="column",
                justify="start",
                spacing="4",
                width="100%",
            ),
            rx.vstack(
                rx.text(
                    "Email address",
                    size="3",
                    weight="medium",
                    text_align="left",
                    width="100%",
                ),
                rx.input(
                    rx.input.slot(rx.icon("user")),
                    placeholder="user@reflex.dev",
                    type="email",
                    size="3",
                    width="100%",
                ),
                justify="start",
                spacing="2",
                width="100%",
            ),
            rx.vstack(
                rx.hstack(
                    rx.text("Password", size="3", weight="medium"),
                    rx.link("Forgot password?", href="#", size="3"),
                    justify="between",
                    width="100%",
                ),
                rx.input(
                    rx.input.slot(rx.icon("lock")),
                    placeholder="Enter your password",
                    type="password",
                    size="3",
                    width="100%",
                ),
                spacing="2",
                width="100%",
            ),
            rx.button("Sign in", size="3", width="100%"),
            rx.hstack(
                rx.divider(margin="0"),
                rx.text("Or continue with", white_space="nowrap", weight="medium"),
                rx.divider(margin="0"),
                align="center",
                width="100%",
            ),
            rx.button(
                rx.text("GH", weight="bold"),
                "Sign in with GitHub",
                variant="outline",
                size="3",
                width="100%",
            ),
            spacing="6",
            width="100%",
        ),
        size="4",
        max_width="28em",
        width="100%",
    )
```

```python test
def test_login_form_with_github(demo):
    view = demo.get_by_role("tabpanel", name="View")
    expect(view.get_by_role("heading")).to_have_text("Sign in to your account")
    expect(view.get_by_text("Or continue with")).to_be_visible()
    expect(view.get_by_role("button")).to_have_text([
        "Sign in",
        "GHSign in with GitHub",
    ])
```

## Multiple third-party auth

```python demo exec
def login_multiple_thirdparty() -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.flex(
                rx.image(
                    src="https://web.reflex-assets.dev/other/logo.jpg",
                    alt="Reflex logo",
                    width="2.5em",
                    height="auto",
                    border_radius="25%",
                ),
                rx.heading("Sign in to your account", size="6", as_="h2", width="100%"),
                rx.hstack(
                    rx.text("New here?", size="3", text_align="left"),
                    rx.link("Sign up", href="#", size="3"),
                    spacing="2",
                    opacity="0.8",
                    width="100%",
                ),
                justify="start",
                direction="column",
                spacing="4",
                width="100%",
            ),
            rx.vstack(
                rx.text(
                    "Email address",
                    size="3",
                    weight="medium",
                    text_align="left",
                    width="100%",
                ),
                rx.input(
                    rx.input.slot(rx.icon("user")),
                    placeholder="user@reflex.dev",
                    type="email",
                    size="3",
                    width="100%",
                ),
                spacing="2",
                justify="start",
                width="100%",
            ),
            rx.vstack(
                rx.hstack(
                    rx.text("Password", size="3", weight="medium"),
                    rx.link("Forgot password?", href="#", size="3"),
                    justify="between",
                    width="100%",
                ),
                rx.input(
                    rx.input.slot(rx.icon("lock")),
                    placeholder="Enter your password",
                    type="password",
                    size="3",
                    width="100%",
                ),
                spacing="2",
                width="100%",
            ),
            rx.button("Sign in", size="3", width="100%"),
            rx.hstack(
                rx.divider(margin="0"),
                rx.text("Or continue with", white_space="nowrap", weight="medium"),
                rx.divider(margin="0"),
                align="center",
                width="100%",
            ),
            rx.center(
                rx.icon_button(rx.text("GH", weight="bold"), variant="soft", size="3"),
                rx.icon_button(rx.text("f", weight="bold"), variant="soft", size="3"),
                rx.icon_button(rx.text("X", weight="bold"), variant="soft", size="3"),
                spacing="4",
                direction="row",
                width="100%",
            ),
            spacing="6",
            width="100%",
        ),
        size="4",
        max_width="28em",
        width="100%",
    )
```

```python test
def test_login_form_with_providers(demo):
    view = demo.get_by_role("tabpanel", name="View")
    expect(view.get_by_role("heading")).to_have_text("Sign in to your account")
    expect(view.get_by_text("Or continue with")).to_be_visible()
    expect(view.get_by_role("button")).to_have_text(["Sign in", "GH", "f", "X"])
```
