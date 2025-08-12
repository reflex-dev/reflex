"""Welcome to Reflex! This file outlines the steps to create a basic app."""

import reflex as rx

from datetime import datetime
from googletrans import Translator
from googletrans.constants import LANGUAGES


LANGUAGE_CODE_TO_NAME = {k: v.title() for k, v in LANGUAGES.items()}
LANGUAGE_NAMES = list(LANGUAGE_CODE_TO_NAME.values())

trans = Translator()


class Message(rx.Base):
    original_text: str
    text: str
    created_at: str
    to_lang: str


class State(rx.State):
    """The app state."""

    text: str
    messages: list[Message] = []
    lang: str = LANGUAGE_CODE_TO_NAME["zh-cn"]

    @rx.var
    def input_missing(self) -> bool:
        return not self.text.strip()

    @rx.var
    def output(self) -> str:
        if self.input_missing:
            return "Translations will appear here."
        # The destination language `dest` is case insensitive, `translate` API call accepts both language names and codes.
        translated = trans.translate(self.text, dest=self.lang)
        return translated.text

    def post(self, form_data: dict[str, str]):
        if not (text := form_data.get("text")):
            return
        # Insert the message at the top of the list.
        self.messages.insert(
            0,
            Message(
                original_text=text,
                text=self.output,
                created_at=datetime.now().strftime("%B %d, %Y %I:%M %p"),
                to_lang=self.lang,
            ),
        )
        # Manually reset the form input, since input in this app is fully controlled, it does not reset on submit.
        self.text = ""


# Define views.


def header() -> rx.Component:
    """The header and the description."""
    return rx.box(
        rx.heading("Translator 🗺", size="8"),
        rx.text(
            "Translate things and post them as messages!",
            color_scheme="gray",
        ),
        margin_bottom="1rem",
    )


def down_arrow() -> rx.Component:
    return rx.vstack(
        rx.icon(
            tag="arrow_down",
            color="gray",
        ),
        align="center",
    )


def text_box(text) -> rx.Component:
    return rx.text(
        text,
        background_color="white",
        padding="1rem",
        border_radius="8px",
    )


def past_translation(message: Message) -> rx.Component:
    """A layout that contains a past translation."""
    return rx.box(
        rx.vstack(
            text_box(message.original_text),
            down_arrow(),
            text_box(message.text),
            rx.hstack(
                rx.text(message.to_lang),
                rx.text("·"),
                rx.text(message.created_at),
                spacing="2",
                font_size="0.8rem",
                color=rx.color("gray", 11),
            ),
            spacing="2",
            align="stretch",
        ),
        background_color=rx.color("gray", 3),
        padding="1rem",
        border_radius="8px",
    )


def smallcaps(text: str, **props):
    """A smallcaps text component."""
    return rx.text(
        text,
        font_size="0.7rem",
        font_weight="bold",
        text_transform="uppercase",
        letter_spacing="0.05rem",
        **props,
    )


def output():
    """The output layout that contains the translated text."""
    return rx.stack(
        smallcaps(
            "Output",
            color=rx.color("gray", 9),
            background_color="white",
            position="absolute",
            top="-0.5rem",
        ),
        rx.text(State.output, size="4"),
        padding="1rem",
        border="1px solid",
        border_color=rx.color("gray", 7),
        border_radius="8px",
        position="relative",
    )


def translation_form() -> rx.Component:
    """This is a form that contains:
    - Text input: what to translate
    - Select: the destination language
    - Output: the translation
    - Submit button: to post the text input as part of the past translations view
    """
    return rx.form(
        rx.flex(
            rx.input(
                placeholder="Text to translate",
                value=State.text,
                on_change=State.set_text,
                debounce_timeout=300,
                size="3",
                name="text",
            ),
            rx.select(
                placeholder="Select a language",
                items=LANGUAGE_NAMES,
                value=State.lang,
                on_change=State.set_lang,
                margin_top="1rem",
                size="3",
                width="100%",
            ),
            output(),
            rx.button(
                "Post",
                size="3",
                disabled=State.input_missing,
            ),
            direction="column",
            spacing="4",
        ),
        # setting `reset_on_submit` here will not work since the input is fully controlled
        on_submit=State.post,
    )


def past_translations_timeline() -> rx.Component:
    """A layout that contains the timeline of posted past translations."""
    return rx.flex(
        rx.foreach(State.messages, past_translation),
        margin_top="2rem",
        spacing="4",
        direction="column",
    )


def index():
    """The main view."""
    return rx.container(
        header(),
        translation_form(),
        past_translations_timeline(),
        padding="2rem",
        max_width="600px",
        margin="auto",
    )


app = rx.App(
    theme=rx.theme(
        appearance="light", has_background=True, radius="large", accent_color="blue"
    ),
)
app.add_page(index, title="Translator")
