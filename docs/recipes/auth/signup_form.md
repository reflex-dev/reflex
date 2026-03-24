```python exec
import reflex as rx
from pcweb.constants import REFLEX_ASSETS_CDN
```

# Sign up Form

The sign up form is a common component in web applications. It allows users to create an account and access the application's features. This page provides a few examples of sign up forms that you can use in your application.
## Default

```python demo exec toggle
def signup_default() -> rx.Component:
	return rx.card(
		rx.vstack(
			rx.center(
				rx.image(src=f"{REFLEX_ASSETS_CDN}other/logo.jpg", width="2.5em", height="auto", border_radius="25%"),
				rx.heading("Create an account", size="6", as_="h2", text_align="center", width="100%"),
				direction="column",
				spacing="5",
				width="100%"
			),
			rx.vstack(
				rx.text("Email address", size="3", weight="medium", text_align="left", width="100%"),
				rx.input(placeholder="user@reflex.dev", type="email", size="3", width="100%"),
				justify="start",
				spacing="2",
				width="100%"
			),
			rx.vstack(
				rx.text("Password", size="3", weight="medium", text_align="left", width="100%"),
				rx.input(placeholder="Enter your password", type="password", size="3", width="100%"),
				justify="start",
				spacing="2",
				width="100%"
			),
			rx.box(
				rx.checkbox(
					"Agree to Terms and Conditions",
					default_checked=True,
					spacing="2"
				),
				width="100%"
			),
			rx.button("Register", size="3", width="100%"),
			rx.center(
				rx.text("Already registered?", size="3"),
				rx.link("Sign in", href="#", size="3"),
				opacity="0.8",
				spacing="2",
				direction="row"
			),
			spacing="6",
			width="100%"
		),
		size="4",
		max_width="28em",
		width="100%"
	)
```

## Icons

```python demo exec toggle
def signup_default_icons() -> rx.Component:
	return rx.card(
		rx.vstack(
			rx.center(
				rx.image(src=f"{REFLEX_ASSETS_CDN}other/logo.jpg", width="2.5em", height="auto", border_radius="25%"),
				rx.heading("Create an account", size="6", as_="h2", text_align="center", width="100%"),
				direction="column",
				spacing="5",
				width="100%"
			),
			rx.vstack(
				rx.text("Email address", size="3", weight="medium", text_align="left", width="100%"),
				rx.input(rx.input.slot(rx.icon("user")), placeholder="user@reflex.dev", type="email", size="3", width="100%"),
				justify="start",
				spacing="2",
				width="100%"
			),
			rx.vstack(
				rx.text("Password", size="3", weight="medium", text_align="left", width="100%"),
				rx.input(rx.input.slot(rx.icon("lock")), placeholder="Enter your password", type="password", size="3", width="100%"),
				justify="start",
				spacing="2",
				width="100%"
			),
			rx.box(
				rx.checkbox(
					"Agree to Terms and Conditions",
					default_checked=True,
					spacing="2"
				),
				width="100%"
			),
			rx.button("Register", size="3", width="100%"),
			rx.center(
				rx.text("Already registered?", size="3"),
				rx.link("Sign in", href="#", size="3"),
				opacity="0.8",
				spacing="2",
				direction="row",
				width="100%"
			),
			spacing="6",
			width="100%"
		),
		max_width="28em",
		size="4",
		width="100%"
	)
```

## Third-party auth


```python demo exec toggle
def signup_single_thirdparty() -> rx.Component:
	return rx.card(
		rx.vstack(
			rx.flex(
				rx.image(src=f"{REFLEX_ASSETS_CDN}other/logo.jpg", width="2.5em", height="auto", border_radius="25%"),
				rx.heading("Create an account", size="6", as_="h2", text_align="left", width="100%"),
				rx.hstack(
					rx.text("Already registered?", size="3", text_align="left"),
					rx.link("Sign in", href="#", size="3"),
					spacing="2",
					opacity="0.8",
					width="100%"
				),
				direction="column",
				justify="start",
				spacing="4",
				width="100%"
			),
			rx.vstack(
				rx.text("Email address", size="3", weight="medium", text_align="left", width="100%"),
				rx.input(rx.input.slot(rx.icon("user")), placeholder="user@reflex.dev", type="email", size="3", width="100%"),
				justify="start",
				spacing="2",
				width="100%"
			),
			rx.vstack(
				rx.text("Password", size="3", weight="medium", text_align="left", width="100%"),
				rx.input(rx.input.slot(rx.icon("lock")), placeholder="Enter your password", type="password", size="3", width="100%"),
				justify="start",
				spacing="2",
				width="100%"
			),
			rx.box(
				rx.checkbox(
					"Agree to Terms and Conditions",
					default_checked=True,
					spacing="2"
				),
				width="100%"
			),
			rx.button("Register", size="3", width="100%"),
			rx.hstack(
				rx.divider(margin="0"),
				rx.text("Or continue with", white_space="nowrap", weight="medium"),
				rx.divider(margin="0"),
				align="center",
				width="100%"
			),
			rx.button(
				rx.icon(tag="github"),
				"Sign in with Github",
				variant="outline",
				size="3",
				width="100%"
			),
			spacing="6",
			width="100%"
		),
		size="4",
		max_width="28em",
		width="100%"
	)
```

## Multiple third-party auth

```python demo exec toggle
def signup_multiple_thirdparty() -> rx.Component:
	return rx.card(
		rx.vstack(
			rx.flex(
				rx.image(src=f"{REFLEX_ASSETS_CDN}other/logo.jpg", width="2.5em", height="auto", border_radius="25%"),
				rx.heading("Create an account", size="6", as_="h2", width="100%"),
				rx.hstack(
					rx.text("Already registered?", size="3", text_align="left"),
					rx.link("Sign in", href="#", size="3"),
					spacing="2",
					opacity="0.8",
					width="100%"
				),
				justify="start",
				direction="column",
				spacing="4",
				width="100%"
			),
			rx.vstack(
				rx.text("Email address", size="3", weight="medium", text_align="left", width="100%"),
				rx.input(rx.input.slot(rx.icon("user")), placeholder="user@reflex.dev", type="email", size="3", width="100%"),
				justify="start",
				spacing="2",
				width="100%"
			),
			rx.vstack(
				rx.text("Password", size="3", weight="medium", text_align="left", width="100%"),
				rx.input(rx.input.slot(rx.icon("lock")), placeholder="Enter your password", type="password", size="3", width="100%"),
				justify="start",
				spacing="2",
				width="100%"
			),
			rx.box(
				rx.checkbox(
					"Agree to Terms and Conditions",
					default_checked=True,
					spacing="2"
				),
				width="100%"
			),
			rx.button("Register", size="3", width="100%"),
			rx.hstack(
				rx.divider(margin="0"),
				rx.text("Or continue with", white_space="nowrap", weight="medium"),
				rx.divider(margin="0"),
				align="center",
				width="100%"
			),
			rx.center(
                rx.icon_button(
                    rx.icon(tag="github"),
                    variant="soft",
                    size="3"
                ),
                rx.icon_button(
                    rx.icon(tag="facebook"),
                    variant="soft",
                    size="3"
                ),
                rx.icon_button(
                    rx.icon(tag="twitter"),
                    variant="soft",
                    size="3"
                ),
                spacing="4",
                direction="row",
                width="100%"
            ),
			spacing="6",
			width="100%"
		),
		size="4",
		max_width="28em",
		width="100%"
	)
```
