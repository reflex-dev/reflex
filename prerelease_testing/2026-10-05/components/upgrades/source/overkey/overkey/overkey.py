"""Welcome to Reflex! This file outlines the steps to create a basic app."""

import asyncio
import dataclasses
import enum
import random
from pathlib import Path

import reflex as rx
from reflex.experimental.client_state import ClientStateVar
from reflex.vars.number import NumberVar
from reflex.vars.sequence import StringVar


@dataclasses.dataclass(frozen=True)
class LanguageOption:
    """A language option for the user to select."""

    code: str
    name: str
    is_advanced: bool


language_options = [
    LanguageOption("bg", "български", False),
    LanguageOption("cs", "čeština", False),
    LanguageOption("da", "dansk", False),
    LanguageOption("de_CH", "Deutsch (Schweiz)", False),
    LanguageOption("de", "Deutsch", False),
    LanguageOption("en", "English", False),
    LanguageOption("es", "español", False),
    LanguageOption("fr", "français", False),
    LanguageOption("hu", "magyar", False),
    LanguageOption("it", "italiano", False),
    LanguageOption("ko", "한국어", False),
    LanguageOption("nb", "norsk bokmål", False),
    LanguageOption("nn", "nynorsk", False),
    LanguageOption("oc", "occitan", False),
    LanguageOption("pl", "polski", False),
    LanguageOption("pt", "português", True),
    LanguageOption("pt", "português", False),
    LanguageOption("ru", "русский", False),
    LanguageOption("rw", "Kinyarwanda", False),
    LanguageOption("sv", "svenska", False),
    LanguageOption("sw", "Kiswahili", False),
    LanguageOption("tr", "Türkçe", False),
    LanguageOption("uk", "українська", False),
]

english_language_option = LanguageOption("en", "English", False)


def load_language(language_option: LanguageOption) -> list[str]:
    """Load the word list for the given language option."""
    return (
        Path(
            f"word_lists/{language_option.code}{'_advanced' if language_option.is_advanced else ''}.txt"
        )
        .read_text()
        .splitlines()
    )


def get_random_words(language_option: LanguageOption, count: int) -> list[str]:
    """Get random words from the word list for the given language option."""
    return random.choices(
        load_language(language_option),
        k=count,
    )


class Correctness(enum.Enum):
    """The correctness of the user's input."""

    CORRECT = "correct"
    INCORRECT = "incorrect"
    INCOMPLETE = "incomplete"


user_input_state = ClientStateVar.create("user_input", default="")


@dataclasses.dataclass
class DisplayLetter:
    """A letter to display in the Overkey app."""

    letter: str
    correctness: Correctness
    is_last: bool


class OverkeyState(rx.State):
    """The state of the Overkey app."""

    language_option: rx.Field[LanguageOption] = rx.field(english_language_option)
    time_limit: rx.Field[int] = rx.field(30)
    is_reset: rx.Field[bool] = rx.field(False)
    wpm: rx.Field[float] = rx.field(0)
    accuracy: rx.Field[float] = rx.field(0)

    current_time: rx.Field[int | None] = rx.field(None)

    @rx.var(cache=True)
    def words(self) -> list[str]:
        """Get the words for the user to complete."""
        if self.is_hydrated:
            return [
                word + " "
                for word in get_random_words(self.language_option, self.time_limit * 5)
            ]
        return []

    @rx.var(cache=True)
    def cumulative_word_lengths(self) -> list[int]:
        """Get the cumulative word lengths for the words."""
        words_lengths = [len(word) for word in self.words]
        cumulative_word_lengths = [0]
        for word_length in words_lengths:
            cumulative_word_lengths.append(word_length + cumulative_word_lengths[-1])
        return cumulative_word_lengths

    @rx.event
    def set_language_option(self, language_option: str):
        """Set the language option for the user to play with."""
        is_advanced = language_option.endswith(" (advanced)")
        language_name = language_option.removesuffix(" (advanced)")
        self.language_option = next(
            language_option
            for language_option in language_options
            if language_option.name == language_name
            and language_option.is_advanced == is_advanced
        )

    @rx.var(cache=True)
    def selected_language_option(self) -> str:
        """Get the selected language option for the user to play with."""
        return self.language_option.name + (
            " (advanced)" if self.language_option.is_advanced else ""
        )

    @rx.var(cache=True)
    def selected_time_limit(self) -> str:
        """Get the selected time limit for the user to complete the words."""
        if self.time_limit > 60:
            return f"{self.time_limit // 60} minutes"
        if self.time_limit == 60:
            return "1 minute"
        if self.time_limit > 1:
            return f"{self.time_limit} seconds"
        return f"{self.time_limit} second"

    @rx.event
    def set_time_limit(self, time_limit: str):
        """Set the time limit for the user to complete the words."""
        if time_limit.endswith(" minutes"):
            self.time_limit = int(time_limit.removesuffix(" minutes")) * 60
        elif time_limit.endswith(" minute"):
            self.time_limit = 60
        elif time_limit.endswith(" seconds"):
            self.time_limit = int(time_limit.removesuffix(" seconds"))
        elif time_limit.endswith(" second"):
            self.time_limit = 1

    @rx.event
    @rx.event(background=True)
    async def tick(self):
        """Tick the timer for the user to complete the words."""
        await asyncio.sleep(1)
        async with self:
            if self.current_time is not None:
                self.current_time -= 1
                new_value = self.current_time
            else:
                new_value = 0

        if new_value > 0:
            return OverkeyState.tick

    @rx.event
    def start_timer(self):
        """Start the timer for the user to complete the words."""
        if self.current_time is None:
            self.current_time = self.time_limit
            return OverkeyState.tick

    @rx.event
    def on_load(self):
        """Load the initial state of the Overkey app."""
        self.current_time = None

    @rx.event
    def receive_user_input(self, user_input: str):
        """Receive the user's input."""
        if not user_input:
            return
        current_paragraph = "".join(self.words)
        correct_letters_count = sum(
            letter == expected_letter
            for letter, expected_letter in zip(user_input, current_paragraph)
        )
        self.wpm = (correct_letters_count / self.time_limit) * 60 / 5
        self.accuracy = correct_letters_count / len(user_input)

    @rx.var(cache=True)
    def accuracy_display(self) -> str:
        """Get the accuracy of the user's input."""
        return f"{self.accuracy:.2%}"

    @rx.event
    def restart(self):
        """Restart the Overkey app."""
        self.current_time = None
        self.language_option = self.language_option
        self.is_reset = True
        return OverkeyState.witness_is_reset

    @rx.event
    def witness_is_reset(self):
        """Witness the reset of the Overkey app."""
        self.is_reset = False


def render_letter(letter: StringVar, letter_index: NumberVar) -> rx.Component:
    """Render a letter for the user to complete."""
    user_input_length = user_input_state.value.length()
    in_bounds = letter_index < user_input_length
    in_bounds_and_incorrect = in_bounds & (
        user_input_state.value.to(str)[letter_index] != letter
    )
    last_character = letter_index == user_input_length

    return rx.el.div(
        letter,
        opacity=rx.cond(in_bounds, 1, 0.5),
        color=rx.cond(in_bounds_and_incorrect, "#C13629", "inherit"),
        background_color=rx.cond(in_bounds_and_incorrect, "pink", "transparent"),
        border_inline_start="2px solid transparent",
        class_name=rx.cond(
            last_character,
            "letter blink",
            "letter",
        ),
        flex="1",
        width="1ch",
        height="100%",
    )


def render_word(word: StringVar, word_index: NumberVar) -> rx.Component:
    """Render a word for the user to complete."""
    return rx.hstack(
        rx.foreach(
            word.split(),
            lambda letter, letter_index: render_letter(
                letter, letter_index + OverkeyState.cumulative_word_lengths[word_index]
            ),
        ),
        class_name="word",
        width=f"{word.length()}ch",
        spacing="0",
    )


@rx.memo
def time_is_up():
    """Render a message when time is up."""
    return rx.flex(
        "Time's up!",
        position="absolute",
        top=0,
        left=0,
        width="100%",
        height="100%",
        align="center",
        justify="center",
        font_size="3em",
        font_weight="900",
        backdrop_filter="blur(2px)",
        on_mount=OverkeyState.receive_user_input(user_input_state.value),
    )


@rx.memo
def witness_is_reset():
    """Render a witness for the reset of the Overkey app."""
    return rx.el.div(
        on_mount=user_input_state.set_value(""),
    )


def index() -> rx.Component:
    """Render the Overkey app."""
    return rx.center(
        rx.vstack(
            rx.hstack(
                rx.cond(
                    OverkeyState.current_time.is_not_none(),
                    rx.fragment(
                        rx.icon_button(
                            "rotate-ccw",
                            variant="outline",
                            color_scheme="gray",
                            on_click=OverkeyState.restart,
                        ),
                        rx.flex(
                            rx.cond(
                                OverkeyState.current_time == 0,
                                f"{OverkeyState.wpm} WPM, {OverkeyState.accuracy_display} accuracy",
                                OverkeyState.current_time,
                            ),
                            flex="1",
                            align="center",
                            justify="center",
                        ),
                    ),
                    rx.fragment(
                        rx.cond(OverkeyState.is_reset, witness_is_reset()),
                        rx.select(
                            [
                                language.name
                                + (" (advanced)" if language.is_advanced else "")
                                for language in language_options
                            ],
                            value=OverkeyState.selected_language_option,
                            on_change=OverkeyState.set_language_option,
                        ),
                        rx.select(
                            [
                                "5 seconds",
                                "15 seconds",
                                "30 seconds",
                                "1 minute",
                            ],
                            value=OverkeyState.selected_time_limit,
                            on_change=OverkeyState.set_time_limit,
                        ),
                    ),
                ),
                justify="center",
                align="center",
                width="100%",
                spacing="6",
            ),
            rx.vstack(
                user_input_state,
                rx.flex(
                    rx.foreach(OverkeyState.words, render_word),
                    id="words",
                    wrap="wrap",
                    font_family="monospace",
                    font_size="1.5em",
                    max_width="60ch",
                ),
                rx.fragment(
                    rx.cond(
                        OverkeyState.current_time == 0,
                        time_is_up(),
                        rx.el.input(
                            value=user_input_state.value,
                            on_change=user_input_state.set_value,
                            on_key_down=lambda _: rx.cond(
                                user_input_state.value == "",
                                OverkeyState.start_timer(),
                                rx.console_log("Timer already started"),
                            ),
                            opacity=0,
                            position="absolute",
                            top=0,
                            left=0,
                            width="100%",
                            height="100%",
                        ),
                    )
                ),
                position="relative",
                padding="1em 0.25em",
            ),
            rx.text(
                "Credit of word lists: ",
                rx.link(
                    "keypunch",
                    href="https://github.com/bragefuglseth/keypunch",
                ),
                align="center",
                font_size="0.75em",
                color="gray",
            ),
        ),
        padding="1em",
    )


app = rx.App(
    style={
        "@keyframes blink": {
            "0%": {"border_inline_start_color": "transparent"},
            "50%": {"border_inline_start_color": "currentColor"},
            "100%": {"border_inline_start_color": "transparent"},
        },
        "#words:has(+ input:focus-within) .blink": {
            "border_inline_start": "2px solid",
            "animation": "blink 850ms step-start infinite",
        },
    }
)
app.add_page(index, on_load=OverkeyState.on_load)
