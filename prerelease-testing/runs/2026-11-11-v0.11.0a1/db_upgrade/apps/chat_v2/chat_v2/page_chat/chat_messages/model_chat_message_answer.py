import reflex as rx

from .style import Style as AnswerStyle

ANSWER_STYLE: AnswerStyle = AnswerStyle()
ANSWER_STYLE.default.update(
    {
        "justify_items": "flex-start",
        "align_self": "flex-end",
        "padding": "24px",
        "background": rx.color(
            color="indigo",
            shade=2,
        ),
        "box_shadow": "0px 2px 4px rgba(25, 33, 61, 0.08)",
        "border": rx.color_mode_cond(
            light=f"2px solid {rx.color('indigo', 3)}",
            dark="",
        ),
    },
)
