"""Common styles for questions and answers."""

import reflex as rx

chat_margin = "15%"
message_style = {
    "padding": "0.75em 1em",
    "border_radius": "18px",
    "margin_y": "0.35em",
    "max_width": "30em",
    "display": "inline-block",
    "line_height": "1.5",
    "font_size": "0.95rem",
}

# Set specific styles for questions and answers.
question_style = message_style | {
    "background_color": rx.color("slate", 3),
    "color": rx.color("slate", 12),
    "border": f"1px solid {rx.color('slate', 4)}",
    "margin_left": chat_margin,
    "border_bottom_right_radius": "6px",
}
answer_style = message_style | {
    "background_color": rx.color("accent", 9),
    "color": "white",
    "margin_right": chat_margin,
    "border_bottom_left_radius": "6px",
}

# Styles for the action bar.
input_style = {"border_width": "1px", "width": "350px"}
button_style = {"background_color": rx.color("accent", 9)}
