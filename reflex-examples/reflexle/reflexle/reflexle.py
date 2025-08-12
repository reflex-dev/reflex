"""Mockup of a Wordle game."""

import asyncio
import enum
import random
from dataclasses import dataclass

import reflex as rx
from reflex.vars.base import Var

from reflex_global_hotkey import global_hotkey_watcher
from .words import possible_solution, valid_guess

small_cap_letters = "abcdefghijklmnopqrstuvwxyz"
big_cap_letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


class Correctness(enum.Enum):
    """Enum for correctness."""

    UNKNOWN = 0
    INCORRECT = 1
    WRONG_POSITION = 2
    CORRECT = 3


class GameStatus(enum.Enum):
    """Enum for game status."""

    ONGOING = 0
    WON = 1
    LOST = 2


WORD_LENGTH = 5

CORRECT_COLOR = "#538D4E"
CORRECT_COLOR_HIGH_CONTRAST = "#F5793A"
WRONG_POSITION_COLOR = "#B59F3B"
WRONG_POSITION_COLOR_HIGH_CONTRAST = "#85C0F9"


@dataclass(init=False)
class ReflexleGame:
    """Wordle game class."""

    correct_word: str
    guesses: list[str]

    def __init__(self):
        """Initialize the Wordle game."""
        self.correct_word = random.choice(possible_solution)
        self.guesses = []

    def guess(self, word: str):
        """Make a guess."""
        if word not in valid_guess:
            return rx.toast("Invalid word.")
        if word in self.guesses:
            return rx.toast("You already guessed this word.")
        self.guesses.append(word)

    def is_correct(self):
        """Check if the current guesses are correct."""
        return self.guesses and self.guesses[-1] == self.correct_word

    def game_status(self) -> GameStatus:
        """Get the game status."""
        if self.is_correct():
            return GameStatus.WON
        if len(self.guesses) >= 6:
            return GameStatus.LOST
        return GameStatus.ONGOING

    def correctness(self) -> list[list[Correctness]]:
        """Get the correctness of the guesses."""
        result = []
        for guess in self.guesses:
            correctness = []
            for i, letter in enumerate(guess):
                if letter in self.correct_word:
                    if self.correct_word[i] == letter:
                        correctness.append(Correctness.CORRECT)
                    else:
                        letters_in_correct_position_count = sum(
                            guess_letter == correct_letter == letter
                            for guess_letter, correct_letter in zip(
                                guess, self.correct_word
                            )
                        )
                        letters_count = self.correct_word.count(letter)

                        letters_already_wrong_position = sum(
                            guess_letter == letter
                            and correctness == Correctness.WRONG_POSITION
                            for guess_letter in guess[:i]
                        )

                        if (
                            letters_in_correct_position_count
                            + letters_already_wrong_position
                            < letters_count
                        ):
                            correctness.append(Correctness.WRONG_POSITION)
                        else:
                            correctness.append(Correctness.INCORRECT)
                else:
                    correctness.append(Correctness.INCORRECT)
            result.append(correctness)
        return result


class Reflexle(rx.State):
    """State for the Wordle game."""

    _word: ReflexleGame = ReflexleGame()

    current_guess: rx.Field[str] = rx.field("")

    is_wrong_guess: rx.Field[bool] = rx.field(False)

    high_contrast: rx.Field[bool] = rx.field(False)

    @rx.event
    def on_load(self):
        """On load event."""
        if not self.current_guess and not self._word.guesses:
            self.current_guess = ""
            self.is_wrong_guess = False
            self._word = ReflexleGame()

    @rx.var
    def guesses(self) -> list[list[tuple[str, Correctness]]]:
        """Get the guesses."""
        already_guessed = [
            list(zip(guess, correctness))
            for guess, correctness in zip(self._word.guesses, self._word.correctness())
        ]

        if len(already_guessed) >= 6:
            return already_guessed[:6]

        return (
            already_guessed
            + [
                [
                    (letter, Correctness.UNKNOWN)
                    for letter in self.current_guess.ljust(WORD_LENGTH, " ")
                ]
            ]
            + [[(" ", Correctness.UNKNOWN) for _ in range(WORD_LENGTH)]]
            * (6 - len(already_guessed) - 1)
        )

    @rx.event
    def received_letter(self, letter: str):
        """Receive a letter."""
        if self.game_status != GameStatus.ONGOING or self.is_wrong_guess:
            return
        if letter == "Backspace":
            self.current_guess = self.current_guess[:-1]
        elif letter == "Ctrl+Backspace":
            self.current_guess = ""
        elif letter == "Enter":
            if len(self.current_guess) < WORD_LENGTH:
                return rx.toast("Word must be 5 characters long.")
            current_guess = self.current_guess
            event = self._word.guess(current_guess)
            if event is not None:
                self.is_wrong_guess = True
                return type(self).set_is_wrong_guess_false
            else:
                self.current_guess = ""
                return
        else:
            if len(self.current_guess) >= WORD_LENGTH:
                return
            if letter in big_cap_letters:
                letter = letter.lower()
            self.current_guess += letter

    @rx.event(background=True)
    async def set_is_wrong_guess_false(self):
        """Set is wrong guess to false."""
        await asyncio.sleep(0.3)
        async with self:
            self.is_wrong_guess = False
            self.current_guess = ""

    @rx.var
    def game_status(self) -> GameStatus:
        """Get the game status."""
        return self._word.game_status()

    @rx.event
    def reset_game(self):
        """Reset the game."""
        self._word = ReflexleGame()
        self.current_guess = ""

    @rx.var
    def correct_word(self) -> str | None:
        """Get the correct word."""
        return (
            self._word.correct_word if self.game_status != GameStatus.ONGOING else None
        )

    @rx.var
    def guesses_count(self) -> int:
        """Get the guesses count."""
        return len(self._word.guesses) + bool(self.current_guess)

    @rx.var
    def letters(self) -> list[list[tuple[str, Correctness]]]:
        """Get the letters."""
        query = [
            ["q", "w", "e", "r", "t", "y", "u", "i", "o", "p"],
            ["a", "s", "d", "f", "g", "h", "j", "k", "l", "Backspace"],
            ["z", "x", "c", "v", "b", "n", "m", "Enter"],
        ]

        guesses = self.guesses
        flattened_guesses = [
            (letter, correctness) for guess in guesses for letter, correctness in guess
        ]

        return [
            [
                (
                    letter,
                    Correctness.CORRECT
                    if (letter, Correctness.CORRECT) in flattened_guesses
                    else (
                        Correctness.WRONG_POSITION
                        if (letter, Correctness.WRONG_POSITION) in flattened_guesses
                        else (
                            Correctness.INCORRECT
                            if (letter, Correctness.INCORRECT) in flattened_guesses
                            else Correctness.UNKNOWN
                        )
                    ),
                )
                for letter in row
            ]
            for row in query
        ]

    @rx.event
    def toggle_high_contrast(self):
        """Toggle high contrast."""
        self.high_contrast = not self.high_contrast


def icon_button(icon, **kwargs):
    """Icon button."""
    return rx.button(
        icon,
        bg_color="transparent",
        padding="0.5em",
        height="auto",
        border="2px solid #AAAAAAA0",
        color="#AAAAAA",
        cursor="pointer",
        **kwargs,
    )


def play_again():
    """Play again button."""
    return icon_button(
        rx.icon("refresh-cw"),
        on_click=[Reflexle.reset_game, rx.set_focus("guesses")],
        style=rx.cond(
            Reflexle.game_status == GameStatus.ONGOING,
            {
                "border": "2px solid #AAAAAAA0",
                "color": "#AAAAAAA0",
            },
            {
                "border": "2px solid #AAAAAA",
                "color": "#AAAAAA",
            },
        ),
    )


@rx.memo
def character_box(letter: str, correctness: Correctness, index: int):
    """Character box."""
    return rx.flex(
        rx.box(
            letter,
            font_size=rx.cond(
                letter == " ",
                "0",
                "1em",
            ),
            transition="font-size 0.2s",
        ),
        width="2em",
        height="2em",
        align="center",
        justify="center",
        bg_color=rx.match(
            correctness,
            (
                Correctness.CORRECT,
                rx.cond(
                    Reflexle.high_contrast,
                    CORRECT_COLOR_HIGH_CONTRAST,
                    CORRECT_COLOR,
                ),
            ),
            (
                Correctness.WRONG_POSITION,
                rx.cond(
                    Reflexle.high_contrast,
                    WRONG_POSITION_COLOR_HIGH_CONTRAST,
                    WRONG_POSITION_COLOR,
                ),
            ),
            (Correctness.INCORRECT, "#AAAAAA40"),
            "transparent",
        ),
        border=rx.cond(
            correctness == Correctness.UNKNOWN,
            rx.cond(
                letter == " ",
                "2px solid #AAAAAA40",
                "2px solid #AAAAAAA0",
            ),
            "0px solid #AAAAAA40",
        ),
        color=rx.match(
            correctness,
            (Correctness.CORRECT, "white"),
            (Correctness.WRONG_POSITION, "white"),
            "inherit",
        ),
        transition_property="background-color, border-width, color",
        transition_duration="0.3s",
        transition_delay=f"{0.3 * index}s",
        transition_timing_function="linear",
        font_weight="bold",
        border_radius="0.25em",
        text_transform="uppercase",
    )


@rx.memo
def keyboard_button(letter: Var[str], correctness: Var[Correctness]):
    """Keyboard button."""
    return rx.button(
        rx.match(
            letter,
            ("Backspace", "⌫"),
            ("Enter", "↵"),
            letter,
        ),
        width="2em",
        max_width="7vw",
        padding="0.5em",
        height="2em",
        align="center",
        font_size="inherit",
        justify="center",
        bg_color=rx.match(
            correctness,
            (
                Correctness.CORRECT,
                rx.cond(
                    Reflexle.high_contrast,
                    CORRECT_COLOR_HIGH_CONTRAST,
                    CORRECT_COLOR,
                ),
            ),
            (
                Correctness.WRONG_POSITION,
                rx.cond(
                    Reflexle.high_contrast,
                    WRONG_POSITION_COLOR_HIGH_CONTRAST,
                    WRONG_POSITION_COLOR,
                ),
            ),
            (Correctness.INCORRECT, "#AAAAAA20"),
            "#AAAAAA80",
        ),
        color=rx.match(
            correctness,
            (Correctness.CORRECT, "white"),
            (Correctness.WRONG_POSITION, "white"),
            "inherit",
        ),
        cursor="pointer",
        font_weight="bold",
        border_radius="0.25em",
        text_transform="uppercase",
        on_click=Reflexle.received_letter(letter),
    )


def index():
    """Index page."""
    return rx.center(
        global_hotkey_watcher(
            on_key_down=lambda key: rx.cond(
                rx.Var.create(
                    [
                        *small_cap_letters,
                        *big_cap_letters,
                        "Backspace",
                        "Enter",
                        "Ctrl+Backspace",
                    ]
                ).contains(key),
                Reflexle.received_letter(key),
                rx.noop(),
            ),
        ),
        rx.hstack(
            rx.heading("Reflexle", size="8"),
            rx.hstack(
                play_again(),
                icon_button(
                    rx.icon("contrast"),
                    on_click=Reflexle.toggle_high_contrast,
                ),
                icon_button(
                    rx.color_mode_cond(
                        rx.icon("moon"),
                        rx.icon("sun"),
                    ),
                    on_click=rx.toggle_color_mode,
                ),
            ),
            width="100%",
            justify="between",
            padding="1em",
        ),
        rx.cond(
            Reflexle.game_status == GameStatus.LOST,
            rx.hstack(
                rx.text(
                    f"Word is {Reflexle.correct_word}",
                    text_transform="uppercase",
                ),
                align="center",
                justify="center",
                font_size="2em",
                font_weight="bold",
            ),
        ),
        rx.vstack(
            rx.foreach(
                Reflexle.guesses,
                lambda guess, guess_index: rx.hstack(
                    rx.foreach(
                        guess,
                        lambda letter, i: character_box(
                            letter=letter[0], correctness=letter[1], index=i
                        ),
                    ),
                    style=rx.cond(
                        Reflexle.is_wrong_guess
                        & (guess_index == Reflexle.guesses_count - 1),
                        {
                            "animation": "shake 0.3s",
                            "filter": "invert(21%) sepia(76%) saturate(7088%) hue-rotate(356deg) brightness(82%) contrast(117%)",
                        },
                        {},
                    ),
                ),
            ),
            font_size="min(2em, 7vw)",
        ),
        rx.vstack(
            rx.foreach(
                Reflexle.letters,
                lambda row: rx.box(
                    rx.hstack(
                        rx.foreach(
                            row,
                            lambda letter: keyboard_button(
                                letter=letter[0], correctness=letter[1]
                            ),
                        ),
                        gap="min(0.5em, 2vw)",
                        padding_inline="min(0.5em, 2vw)",
                    ),
                    margin_inline="auto",
                ),
            ),
            margin_block="1em",
            font_size="min(2em, 5vw)",
        ),
        rx.button(
            on_click=Reflexle.received_letter("Enter"),
            opacity=0,
            id="guesses",
        ),
        direction="column",
        gap="1em",
        font_family='"Open Sans"',
    )


app = rx.App(
    head_components=[
        rx.el.link(
            rel="preconnect",
            href="https://fonts.googleapis.com",
        ),
        rx.el.link(
            rel="preconnect",
            href="https://fonts.gstatic.com",
            crossorigin="",
        ),
        rx.el.link(
            href="https://fonts.googleapis.com/css2?family=Open+Sans:ital,wght@0,300..800;1,300..800&display=swap",
            rel="stylesheet",
        ),
    ],
    stylesheets=["style.css"],
)
app.add_page(index, route="/", title="Reflexle", on_load=Reflexle.on_load)
