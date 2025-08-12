"""Welcome to Reflex! This file outlines the steps to create a basic app."""

import copy
from typing import Any, List

import reflex as rx

from .results import results
from .styles import question_style, page_background


class State(rx.State):
    """The app state."""

    default_answers = [None, None, [False, False, False, False, False]]
    answers: List[Any]
    answer_key = ["False", "[10, 20, 30, 40]", [False, False, True, True, True]]
    score: int

    def onload(self):
        self.answers = copy.deepcopy(self.default_answers)

    def set_answers(self, answer, index, sub_index=None):
        if sub_index is None:
            self.answers[index] = answer
        else:
            self.answers[index][sub_index] = answer

    def submit(self):
        total, correct = 0, 0
        for i in range(len(self.answers)):
            if self.answers[i] == self.answer_key[i]:
                correct += 1
            total += 1
        self.score = int(correct / total * 100)
        return rx.redirect("/result")

    @rx.var
    def percent_score(self) -> str:
        return f"{self.score}%"


def header():
    return rx.vstack(
        rx.heading("Python Quiz"),
        rx.divider(),
        rx.text("Here is an example of a quiz made in Reflex."),
        rx.text("Once submitted the results will be shown in the results page."),
        style=question_style,
    )


def question1():
    """The main view."""
    return rx.vstack(
        rx.heading("Question #1"),
        rx.text(
            "In Python 3, the maximum value for an integer is 26",
            rx.el.sup("3"),
            " - 1",
        ),
        rx.divider(),
        rx.radio(
            items=["True", "False"],
            default_value=State.default_answers[0],
            default_checked=True,
            on_change=lambda answer: State.set_answers(answer, 0),
        ),
    )


def question2():
    return rx.vstack(
        rx.heading("Question #2"),
        rx.text("What is the output of the following addition (+) operator?"),
        rx.code_block(
            """a = [10, 20]
b = a
b += [30, 40]
print(a)""",
            language="python",
        ),
        rx.radio(
            items=["[10, 20, 30, 40]", "[10, 20]"],
            default_value=State.default_answers[1],
            default_check=True,
            on_change=lambda answer: State.set_answers(answer, 1),
        ),
    )


def question3():
    def answer_checkbox(answer, index):
        return rx.checkbox(
            text=rx.code(answer),
            on_change=lambda answer: State.set_answers(answer, 2, index),
        )

    return rx.vstack(
        rx.heading("Question #3"),
        rx.text(
            "Which of the following are valid ways to specify the string literal ",
            rx.code("foo'bar"),
            " in Python:",
        ),
        rx.vstack(
            answer_checkbox("foo'bar", 0),
            answer_checkbox("'foo''bar'", 1),
            answer_checkbox("'foo\\\\'bar'", 2),
            answer_checkbox('"""foo\'bar"""', 3),
            answer_checkbox('"foo\'bar"', 4),
        ),
    )


def index():
    """The main view."""
    return rx.color_mode.button(position="top-right"), rx.center(
        rx.vstack(
            header(),
            rx.vstack(
                question1(),
                rx.divider(),
                question2(),
                rx.divider(),
                question3(),
                rx.center(
                    rx.button("Submit", width="6em", on_click=State.submit),
                    width="100%",
                ),
                style=question_style,
                spacing="5",
            ),
            align="center",
        ),
        bg=page_background,
        padding_y="2em",
        min_height="100vh",
    )


def result():
    return rx.color_mode.button(position="top-right"), results(State)


app = rx.App(
    theme=rx.theme(
        has_background=True, radius="none", accent_color="orange", appearance="light"
    ),
)
app.add_page(index, title="Quiz - Reflex", on_load=State.onload)
app.add_page(result, title="Quiz Results")
