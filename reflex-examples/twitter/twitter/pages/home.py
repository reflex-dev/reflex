"""The home page. This file includes examples abstracting complex UI into smaller components."""

import reflex as rx
from twitter.state.base import State
from twitter.state.home import HomeState

from ..components import container


def avatar(name: str):
    return rx.avatar(fallback=name[:2], size="4")


def tab_button(name, href):
    """A tab switcher button."""
    return rx.link(
        rx.flex(rx.icon(tag="star"), margin_right="1rem"),
        name,
        display="inline-flex",
        align_items="center",
        padding="0.75rem",
        href=href,
        border="1px solid #eaeaea",
        font_weight="semibold",
        border_radius="2rem",
    )


def tabs():
    """The tab switcher displayed on the left."""
    return rx.box(
        rx.vstack(
            rx.heading("PySocial", size="5"),
            tab_button("Home", "/"),
            rx.box(
                rx.heading("Followers", size="3"),
                rx.foreach(
                    HomeState.followers,
                    lambda follow: rx.vstack(
                        rx.hstack(
                            avatar(follow.follower_username),
                            rx.text(follow.follower_username),
                        ),
                        padding="1em",
                    ),
                ),
                padding="2rem",
                border_radius="0.5rem",
                border="1px solid #eaeaea",
            ),
            rx.button("Sign out", on_click=State.logout, size="3"),
            align_items="left",
            spacing="4",
        ),
        padding_top="2rem",
        padding_bottom="2rem",
    )


def sidebar(HomeState):
    """The sidebar displayed on the right."""
    return rx.vstack(
        rx.input(
            on_change=HomeState.set_friend,
            placeholder="Search users",
            width="100%",
        ),
        rx.foreach(
            HomeState.search_users,
            lambda user: rx.vstack(
                rx.hstack(
                    avatar(user.username),
                    rx.text(user.username),
                    rx.spacer(),
                    rx.button(
                        rx.icon(tag="plus"),
                        on_click=lambda: HomeState.follow_user(user.username),
                    ),
                    width="100%",
                ),
                padding_top="1rem",
                padding_bottom="1rem",
                width="100%",
            ),
        ),
        rx.box(
            rx.heading("Following", size="3"),
            rx.foreach(
                HomeState.following,
                lambda follow: rx.vstack(
                    rx.hstack(
                        avatar(follow.followed_username),
                        rx.text(follow.followed_username),
                    ),
                    padding="1em",
                ),
            ),
            padding="2rem",
            border_radius="0.5rem",
            border="1px solid #eaeaea",
            width="100%",
        ),
        align_items="start",
        spacing="4",
        height="100%",
        padding_top="2rem",
        padding_bottom="2rem",
    )


def feed_header(HomeState):
    """The header of the feed."""
    return rx.hstack(
        rx.heading("Home", size="5"),
        rx.input(on_change=HomeState.set_search, placeholder="Search tweets"),
        justify="between",
        padding="1.5rem",
        border_bottom="1px solid #ededed",
    )


def composer(HomeState):
    """The composer for new tweets."""
    return rx.grid(
        rx.vstack(
            avatar(State.user.username),
            padding="1.5rem",
        ),
        rx.box(
            rx.flex(
                rx.text_area(
                    width="100%",
                    placeholder="What's happening?",
                    resize="none",
                    _focus={"border": 0, "outline": 0, "boxShadow": "none"},
                    on_blur=HomeState.set_tweet,
                ),
                padding_y="1.5rem",
                padding_right="1.5rem",
            ),
            rx.hstack(
                rx.button(
                    "Tweet",
                    on_click=HomeState.post_tweet,
                    radius="full",
                    size="3",
                ),
                justify_content="flex-end",
                border_top="1px solid #ededed",
                padding_inline_start="1.5em",
                padding_inline_end="1.5em",
                padding_top="0.75rem",
                padding_bottom="0.75rem",
            ),
        ),
        grid_template_columns="1fr 5fr",
        border_bottom="1px solid #ededed",
    )


def tweet(tweet):
    """Display for an individual tweet in the feed."""
    return rx.grid(
        rx.vstack(
            avatar(tweet.author),
        ),
        rx.box(
            rx.vstack(
                rx.text("@" + tweet.author, font_weight="bold"),
                rx.text(tweet.content, width="100%"),
                align_items="left",
            ),
        ),
        grid_template_columns="1fr 5fr",
        padding="1.5rem",
        spacing="1",
        border_bottom="1px solid #ededed",
    )


def feed(HomeState):
    """The feed."""
    return rx.box(
        feed_header(HomeState),
        composer(HomeState),
        rx.cond(
            HomeState.tweets,
            rx.foreach(
                HomeState.tweets,
                tweet,
            ),
            rx.vstack(
                rx.button(
                    rx.icon(
                        tag="rotate-cw",
                    ),
                    rx.text("Click to load tweets"),
                    on_click=HomeState.get_tweets,
                ),
                padding="1.5rem",
            ),
        ),
        border_left="1px solid #ededed",
        border_right="1px solid #ededed",
        height="100%",
    )


def home():
    """The home page."""
    return container(
        rx.grid(
            tabs(),
            feed(HomeState),
            sidebar(HomeState),
            grid_template_columns="1fr 2fr 1fr",
            height="100vh",
            spacing="4",
        ),
        max_width="1300px",
    )
