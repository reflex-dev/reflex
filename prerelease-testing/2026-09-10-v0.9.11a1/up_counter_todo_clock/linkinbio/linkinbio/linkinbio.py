import reflex as rx
from linkinbio.style import style

# add launchdarkly imports
import ldclient
from ldclient.config import Config
from ldclient import Context, LDClient
import os

# Initialize LD client (this should be done once, typically at app startup)
SDK_KEY: str | None = os.getenv("LD_SDK_KEY", None)

LD_CLIENT: LDClient | None = None
LD_CONTEXT: Context | None = None
if SDK_KEY is not None:
    ldclient.set_config(Config(SDK_KEY))
    LD_CLIENT = ldclient.get()

COUNTER = 0


class State(rx.State):
    # Create a LaunchDarkly context (formerly known as "user")
    ld_context_set: bool = False
    updating: bool = False

    def build_ld_context(
        self,
        context_key: str = "context-key-abc-123",
        context_name: str = "linkinbio-app",
    ) -> None:
        global LD_CONTEXT
        if LD_CLIENT is None:
            return

        LD_CONTEXT = (
            Context.builder(
                context_key,
            )
            .name(
                context_name,
            )
            .build()
        )
        self.ld_context_set = True

    @rx.var(cache=False)
    def get_feature_flag_bool(self) -> bool:
        global COUNTER
        if not self.ld_context_set:
            return False

        feature_flag_key = "toggle-bio"
        flag_value: bool = LD_CLIENT.variation(
            key=feature_flag_key,
            context=LD_CONTEXT,
            default=False,
        )
        COUNTER += 1
        return flag_value

    def on_update(
        self,
        date: str,
    ):
        print(f"{COUNTER} :: {date}")


def link_button(
    name: str,
    url: str,
    icon: str,
) -> rx.Component:
    icon_map = {
        "globe": "globe",
        "twitter": "twitter",
        "github": "github",
        "linkedin": "linkedin",
    }
    icon_tag = icon_map.get(
        icon.lower(),
        "link",
    )
    return rx.link(
        rx.button(
            rx.icon(
                tag=icon_tag,
            ),
            name,
            width="100%",
        ),
        href=url,
        is_external=True,
    )


def index_content(
    name: str,
    pronouns: str,
    bio: str,
    avatar_url: str,
    links: list[dict[str, str]],
    background: str,
):
    return rx.center(
        rx.vstack(
            rx.avatar(
                src=avatar_url,
                size="9",
            ),
            rx.heading(
                name,
                size="7",
            ),
            rx.text(
                pronouns,
                size="1",
            ),
            rx.text(bio),
            rx.vstack(
                rx.foreach(
                    links,
                    lambda link: link_button(link["name"], link["url"], link["icon"]),
                ),
                width="100%",
                spacing="2",
            ),
            padding="4",
            max_width="400px",
            width="100%",
            spacing="3",
        ),
        width="100%",
        height="100vh",
        background=background,
    )


def index() -> rx.Component:
    return rx.fragment(
        rx.cond(
            State.get_feature_flag_bool,
            index_content(
                name="Bio Page if True",
                pronouns="dub.link/pronouns",
                bio="insert bio here",
                avatar_url="https://avatars.githubusercontent.com/<your_username_here>",
                links=[
                    {"name": "Website", "url": "https://www.google.com"},
                    {"name": "Upcoming Events", "url": "lu.ma/launchdarkly"},
                    {"name": "Instagram", "url": "https://instagram.com/qtotherescue"},
                    {
                        "name": "Another Link here",
                        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                    },
                ],
                background="linear-gradient(45deg, #FFD700, #FF8C00, #FF4500)",
            ),
            index_content(
                name="Bio Page if False",
                pronouns="dub.link/pronouns",
                bio="< insert bio here >",
                avatar_url="https://avatars.githubusercontent.com/<your_username_here>",
                links=[
                    {
                        "name": "Website",
                        "url": "https://reflex.dev",
                        "icon": "globe",
                    },
                    {
                        "name": "Twitter",
                        "url": "https://twitter.com/getreflex",
                        "icon": "twitter",
                    },
                    {
                        "name": "GitHub",
                        "url": "https://github.com/reflex-dev/reflex-examples",
                        "icon": "github",
                    },
                    {
                        "name": "LinkedIn",
                        "url": "https://www.linkedin.com/company/reflex-dev",
                        "icon": "linkedin",
                    },
                ],
                background="radial-gradient(circle, var(--chakra-colors-purple-100), var(--chakra-colors-blue-100))",
            ),
        ),
        rx.moment(
            interval=3000,
            on_change=State.on_update,
            format="HH:mm:ss",
        ),
    )


app = rx.App(
    style=style,
)
app.add_page(
    index,
    on_load=State.build_ld_context,
)
