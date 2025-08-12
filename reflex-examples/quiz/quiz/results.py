import reflex as rx
import reflex_chakra as rc

from .styles import base_style as answer_style
from .styles import page_background


def render_answer(State, index):
    return rx.table.row(
        rx.table.cell(index + 1),
        rx.table.cell(
            rx.cond(
                State.answers[index].to_string() == State.answer_key[index].to_string(),
                rx.icon(tag="check", color="green"),
                rx.icon(tag="x", color="red"),
            )
        ),
        rx.table.cell(State.answers[index].to_string()),
        rx.table.cell(State.answer_key[index].to_string()),
    )


def results(State):
    """The results view."""

    def centered_item(item):
        return rx.center(item, width="100%")

    return rx.center(
        rx.vstack(
            rx.heading("Results"),
            rx.text("Below are the results of the quiz."),
            rx.divider(),
            centered_item(
                rc.circular_progress(
                    label=State.percent_score, value=State.score, size="3em"
                )
            ),
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell("#"),
                        rx.table.column_header_cell("Result"),
                        rx.table.column_header_cell("Your Answer"),
                        rx.table.column_header_cell("Correct Answer"),
                    ),
                ),
                rx.table.body(
                    rx.foreach(State.answers, lambda _, i: render_answer(State, i)),
                ),
            ),
            centered_item(
                rx.link(rx.button("Take Quiz Again"), href="/"),
            ),
            style=answer_style,
        ),
        bg=page_background,
        min_height="100vh",
    )
