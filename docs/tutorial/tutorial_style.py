# Common styles for questions and answers.
shadow = "rgba(0, 0, 0, 0.15) 0px 2px 8px"
chat_margin = "20%"
message_style = dict(
    padding="1em",
    border_radius="5px",
    margin_y="0.5em",
    box_shadow=shadow,
    max_width="30em",
    display="inline-block",
)

# Set specific styles for questions and answers.
question_style = message_style | dict(bg="#F5EFFE", margin_left=chat_margin)
answer_style = message_style | dict(bg="#DEEAFD", margin_right=chat_margin)

# Styles for the action bar.
input_style = dict(border_width="1px", padding="1em", box_shadow=shadow)
button_style = dict(bg="#CEFFEE", box_shadow=shadow)
