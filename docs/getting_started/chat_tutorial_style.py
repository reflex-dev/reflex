# Common styles for questions and answers.
import reflex as rx

shadow = "rgba(0, 0, 0, 0.15) 0px 2px 8px"
chat_margin = "20%"
message_style = {
    "padding": "1em",
    "border_radius": "5px",
    "margin_y": "0.5em",
    "box_shadow": shadow,
    "max_width": "30em",
    "display": "inline-block",
}

# Set specific styles for questions and answers.
question_style = message_style | {
    "background_color": rx.color("gray", 4),
    "margin_left": chat_margin,
}
answer_style = message_style | {
    "background_color": rx.color("accent", 8),
    "margin_right": chat_margin,
}

# Styles for the action bar.
input_style = {"border_width": "1px", "box_shadow": shadow, "width": "350px"}
button_style = {"background_color": rx.color("accent", 10), "box_shadow": shadow}
