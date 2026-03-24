```python exec
import reflex as rx
from pcweb.constants import REFLEX_ASSETS_CDN
```

# Navigation Bar

A navigation bar, also known as a navbar, is a common UI element found at the top of a webpage or application.
It typically provides links or buttons to the main sections of a website or application, allowing users to easily navigate and access the different pages.

Navigation bars are useful for web apps because they provide a consistent and intuitive way for users to navigate through the app.
Having a clear and consistent navigation structure can greatly improve the user experience by making it easy for users to find the information they need and access the different features of the app.


```md video https://youtube.com/embed/ITOZkzjtjUA?start=2365&end=2627
# Video: Example of Using the Navbar Recipe
```

## Basic

```python demo exec toggle
def navbar_link(text: str, url: str) -> rx.Component:
	return rx.link(rx.text(text, size="4", weight="medium"), href=url)

def navbar() -> rx.Component:
	return rx.box(
		rx.desktop_only(
			rx.hstack(
				rx.hstack(
					rx.image(src=f"{REFLEX_ASSETS_CDN}other/logo.jpg", width="2.25em", height="auto", border_radius="25%"),
					rx.heading("Reflex", size="7", weight="bold"), align_items="center"),
				rx.hstack(
					navbar_link("Home", "/#"),
					navbar_link("About", "/#"),
					navbar_link("Pricing", "/#"),
					navbar_link("Contact", "/#"),
					justify="end",
					spacing="5"
				),
				justify="between",
				align_items="center"
			),
		),
		rx.mobile_and_tablet(
			rx.hstack(
				rx.hstack(
					rx.image(src=f"{REFLEX_ASSETS_CDN}other/logo.jpg", width="2em",
							 height="auto", border_radius="25%"),
					rx.heading("Reflex", size="6", weight="bold"), align_items="center"),
				rx.menu.root(
					rx.menu.trigger(rx.icon("menu", size=30)),
					rx.menu.content(
						rx.menu.item("Home"),
						rx.menu.item("About"),
						rx.menu.item("Pricing"),
						rx.menu.item("Contact"),
					),
					justify="end"
				),
				justify="between",
				align_items="center"
			),
		),
		bg=rx.color("accent", 3),
		padding="1em",
		# position="fixed",
		# top="0px",
		# z_index="5",
		width="100%"
	)
```


## Dropdown

```python demo exec toggle
def navbar_link(text: str, url: str) -> rx.Component:
	return rx.link(rx.text(text, size="4", weight="medium"), href=url)

def navbar_dropdown() -> rx.Component:
	return rx.box(
		rx.desktop_only(
			rx.hstack(
				rx.hstack(
					rx.image(src=f"{REFLEX_ASSETS_CDN}other/logo.jpg", width="2.25em", height="auto", border_radius="25%"),
					rx.heading("Reflex", size="7", weight="bold"), align_items="center"),
				rx.hstack(
					navbar_link("Home", "/#"),
					rx.menu.root(
						rx.menu.trigger(
							rx.button(rx.text("Services", size="4", weight="medium"), rx.icon(
								"chevron-down"), weight="medium", variant="ghost", size="3"),
						),
						rx.menu.content(
							rx.menu.item("Service 1"),
							rx.menu.item("Service 2"),
							rx.menu.item("Service 3"),
						),
					),
					navbar_link("Pricing", "/#"),
					navbar_link("Contact", "/#"),
					justify="end",
					spacing="5"
				),
				justify="between",
				align_items="center"
			),
		),
		rx.mobile_and_tablet(
			rx.hstack(
				rx.hstack(
					rx.image(src=f"{REFLEX_ASSETS_CDN}other/logo.jpg", width="2em", height="auto", border_radius="25%"),
					rx.heading("Reflex", size="6", weight="bold"), align_items="center"),
				rx.menu.root(
					rx.menu.trigger(rx.icon("menu", size=30)),
					rx.menu.content(
						rx.menu.item("Home"),
						rx.menu.sub(
							rx.menu.sub_trigger("Services"),
							rx.menu.sub_content(
								rx.menu.item("Service 1"),
								rx.menu.item("Service 2"),
								rx.menu.item("Service 3"),
							),
						),
						rx.menu.item("About"),
						rx.menu.item("Pricing"),
						rx.menu.item("Contact"),
					),
					justify="end",
				),
				justify="between",
				align_items="center"
			),
		),
		bg=rx.color("accent", 3),
		padding="1em",
		# position="fixed",
		# top="0px",
		# z_index="5",
		width="100%"
	)
```

## Search bar

```python demo exec toggle
def navbar_searchbar() -> rx.Component:
	return rx.box(
		rx.desktop_only(
			rx.hstack(
				rx.hstack(
					rx.image(src=f"{REFLEX_ASSETS_CDN}other/logo.jpg", width="2.25em", height="auto", border_radius="25%"),
					rx.heading("Reflex", size="7", weight="bold"), align_items="center"),
				rx.input(
					rx.input.slot(rx.icon("search")),
					placeholder="Search...",
					type="search", size="2",
					justify="end",
				),
				justify="between",
				align_items="center"
			),
		),
		rx.mobile_and_tablet(
			rx.hstack(
				rx.hstack(
					rx.image(src=f"{REFLEX_ASSETS_CDN}other/logo.jpg", width="2em", height="auto", border_radius="25%"),
					rx.heading("Reflex", size="6", weight="bold"), align_items="center"),
				rx.input(
					rx.input.slot(rx.icon("search")),
					placeholder="Search...",
					type="search", size="2",
					justify="end",
				),
				justify="between",
				align_items="center"
			),
		),
		bg=rx.color("accent", 3),
		padding="1em",
		# position="fixed",
		# top="0px",
		# z_index="5",
		width="100%"
	)
```

## Icons

```python demo exec toggle
def navbar_icons_item(text: str, icon: str, url: str) -> rx.Component:
	return rx.link(rx.hstack(rx.icon(icon), rx.text(text, size="4", weight="medium")), href=url)

def navbar_icons_menu_item(text: str, icon: str, url: str) -> rx.Component:
	return rx.link(rx.hstack(rx.icon(icon, size=16), rx.text(text, size="3", weight="medium")), href=url)

def navbar_icons() -> rx.Component:
	return rx.box(
		rx.desktop_only(
			rx.hstack(
				rx.hstack(
					rx.image(src=f"{REFLEX_ASSETS_CDN}other/logo.jpg", width="2.25em", height="auto", border_radius="25%"),
					rx.heading("Reflex", size="7", weight="bold"), align_items="center"),
				rx.hstack(
					navbar_icons_item("Home", "home", "/#"),
					navbar_icons_item("Pricing", "coins", "/#"),
					navbar_icons_item("Contact", "mail", "/#"),
					navbar_icons_item("Services", "layers", "/#"),
					spacing="6",
				),
				justify="between",
				align_items="center"
			),
		),
		rx.mobile_and_tablet(
			rx.hstack(
				rx.hstack(
					rx.image(src=f"{REFLEX_ASSETS_CDN}other/logo.jpg", width="2em", height="auto", border_radius="25%"),
					rx.heading("Reflex", size="6", weight="bold"), align_items="center"),
				rx.menu.root(
					rx.menu.trigger(rx.icon("menu", size=30)),
					rx.menu.content(
						navbar_icons_menu_item("Home", "home", "/#"),
						navbar_icons_menu_item("Pricing", "coins", "/#"),
						navbar_icons_menu_item("Contact", "mail", "/#"),
						navbar_icons_menu_item("Services", "layers", "/#"),
					),
					justify="end",
				),
				justify="between",
				align_items="center"
			),
		),
		bg=rx.color("accent", 3),
		padding="1em",
		# position="fixed",
		# top="0px",
		# z_index="5",
		width="100%"
	)
```

## Buttons

```python demo exec toggle
def navbar_link(text: str, url: str) -> rx.Component:
	return rx.link(rx.text(text, size="4", weight="medium"), href=url)

def navbar_buttons() -> rx.Component:
	return rx.box(
		rx.desktop_only(
			rx.hstack(
				rx.hstack(
					rx.image(src=f"{REFLEX_ASSETS_CDN}other/logo.jpg", width="2.25em", height="auto", border_radius="25%"),
					rx.heading("Reflex", size="7", weight="bold"), align_items="center"),
				rx.hstack(
					navbar_link("Home", "/#"),
					navbar_link("About", "/#"),
					navbar_link("Pricing", "/#"),
					navbar_link("Contact", "/#"),
					spacing="5",
				),
				rx.hstack(
					rx.button("Sign Up", size="3", variant="outline"),
					rx.button("Log In", size="3"),
					spacing="4",
					justify="end",
				),
				justify="between",
				align_items="center"
			),
		),
		rx.mobile_and_tablet(
			rx.hstack(
				rx.hstack(
					rx.image(src=f"{REFLEX_ASSETS_CDN}other/logo.jpg", width="2em", height="auto", border_radius="25%"),
					rx.heading("Reflex", size="6", weight="bold"), align_items="center"),
				rx.menu.root(
					rx.menu.trigger(rx.icon("menu", size=30)),
					rx.menu.content(
						rx.menu.item("Home"),
						rx.menu.item("About"),
						rx.menu.item("Pricing"),
						rx.menu.item("Contact"),
						rx.menu.separator(),
						rx.menu.item("Log in"),
						rx.menu.item("Sign up"),
					),
					justify="end",
				),
				justify="between",
				align_items="center"
			),
		),
		bg=rx.color("accent", 3),
		padding="1em",
		# position="fixed",
		# top="0px",
		# z_index="5",
		width="100%"
	)
```

## User profile

```python demo exec toggle
def navbar_link(text: str, url: str) -> rx.Component:
	return rx.link(rx.text(text, size="4", weight="medium"), href=url)

def navbar_user() -> rx.Component:
	return rx.box(
		rx.desktop_only(
			rx.hstack(
				rx.hstack(
					rx.image(src=f"{REFLEX_ASSETS_CDN}other/logo.jpg", width="2.25em", height="auto", border_radius="25%"),
					rx.heading("Reflex", size="7", weight="bold"), align_items="center"),
				rx.hstack(
					navbar_link("Home", "/#"),
					navbar_link("About", "/#"),
					navbar_link("Pricing", "/#"),
					navbar_link("Contact", "/#"),
					spacing="5",
				),
				rx.menu.root(
                    rx.menu.trigger(rx.icon_button(
                        rx.icon("user"), size="2", radius="full")),
                    rx.menu.content(
                        rx.menu.item("Settings"),
                        rx.menu.item("Earnings"),
                        rx.menu.separator(),
                        rx.menu.item("Log out"),
                    ),
                    justify="end",
                ),
				justify="between",
				align_items="center"
			),
		),
		rx.mobile_and_tablet(
			rx.hstack(
				rx.hstack(
					rx.image(src=f"{REFLEX_ASSETS_CDN}other/logo.jpg", width="2em", height="auto", border_radius="25%"),
					rx.heading("Reflex", size="6", weight="bold"), align_items="center"),
				rx.menu.root(
					rx.menu.trigger(rx.icon_button(
                        rx.icon("user"), size="2", radius="full")),
                    rx.menu.content(
                        rx.menu.item("Settings"),
                        rx.menu.item("Earnings"),
                        rx.menu.separator(),
                        rx.menu.item("Log out"),
                    ),
					justify="end",
				),
				justify="between",
				align_items="center"
			),
		),
		bg=rx.color("accent", 3),
		padding="1em",
		# position="fixed",
		# top="0px",
		# z_index="5",
		width="100%"
	)
```
