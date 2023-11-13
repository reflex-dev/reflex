"""Welcome to Reflex! This file outlines the steps to create a basic app."""
from reflex.components.component import Component
from typing import Any, Dict, List, Union
from reflex.vars import Var
import reflex as rx
from .navbar import navbar

class State(rx.State):
    """The app state."""

    pass  

class Spline(rx.Component):
    """Spline component."""

    library = "@splinetool/react-spline"
    tag = "Spline"
    scene: Var[str] ="https://prod.spline.design/XJdSs4NvB17CiJis/scene.splinecode" 
    is_default = True

    lib_dependencies: list[str] = ["@splinetool/runtime"]

spline = Spline.create

def spline_example():
    return rx.center(
        spline(),
        width="100%",
        height="60em",
        position="fixed"
    )





def content_card(heading: str, text: str):
    return rx.vstack(
        rx.heading(heading, size="md", margin_bottom="0.5em"),
        rx.text(text),
        style={
            "background": "rgba(255, 255, 255, 0.06)",
            "borderRadius": "16px",
            "boxShadow": "0 4px 30px rgba(0, 0, 0, 0.1)",
            "backdropFilter": "blur(5px)",
            "WebkitBackdropFilter": "blur(5px)",  # Note the capital 'W' for the vendor prefix
            "border": "1px solid rgba(57, 55, 55, 0.3)",
            "_hover": {
                "box_shadow": "rgba(0, 0, 0, 0.05) 0px 6px 24px 0px, rgba(0, 0, 0, 0.08) 0px 0px 0px 1px;"
            }
        },
        align_items="left",
        padding="1em",
    )


def container(*children, **kwargs):
    kwargs = {"max_width": "1440px", "padding_x": ["1em", "2em", "3em"], **kwargs}
    return rx.container(
        *children,
        **kwargs,
    )

def content():
    return rx.vstack(
        container(
            height="8em",
            width="100%",
            background="radial-gradient(55.39% 67.5% at 50% 100%, rgba(255, 255, 255, 0.3) 0%, rgba(255, 255, 255, 0) 100%)",
            opacity="0.4;",
            transform="matrix(1, 0, 0, -1, 0, 0);",
        ),
        rx.hstack(
            content_card(
                "About",
                "I'm a software engineer and designer. I love to build things that make people's lives easier.",
            ),
            content_card(
                "Projects",
                "I've worked on a variety of projects, ranging from web apps to machine learning models.",
            ),
            padding="1em",
        ),
        rx.hstack(
            content_card(
                "About",
                "I'm a software engineer and designer. I love to build things that make people's lives easier.",
            ),
            content_card(
                "Projects",
                "I've worked on a variety of projects, ranging from web apps to machine learning models.",
            ),
            padding="1em",
        ),
        rx.hstack(
            content_card(
                "About",
                "I'm a software engineer and designer. I love to build things that make people's lives easier.",
            ),
            content_card(
                "Projects",
                "I've worked on a variety of projects, ranging from web apps to machine learning models.",
            ),
            padding="1em",
        ),
        bg="rgba(0, 0, 0, 0.95)",
        width="100%", 
        height="100vh",
        pointer_events="fill",
    )

def index() -> rx.Component:
    return rx.accordion(
    rx.accordion_item(
        rx.accordion_button(
            rx.accordion_icon(),
            rx.heading("Outer"),
        ),
        rx.accordion_panel(
            rx.accordion(
                rx.accordion_item(
                    rx.accordion_button(
                        rx.accordion_icon(),
                        rx.heading("Inner"),
                    ),
                    rx.accordion_panel(
                        rx.badge(
                            "Inner Panel",
                            variant="solid",
                            color_scheme="green",
                        ),
                    ),
                ),
                allow_multiple=True,
            ),
            
        ),
    ),
    width="100%",
)



# Add state and page to the app.
app = rx.App()
app.add_page(index)
app.compile()