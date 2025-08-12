from __future__ import annotations

import reflex as rx

from chat_v2.templates.input_box import input_box
from chat_v2.templates.pop_up import LibraryPrompt
from chat_v2.templates.top_bar import nav_bar

from .chat_body import chat_body
from .chat_state import ChatState
from .style import Style

STYLE: Style = Style()


def _chat_box(
    chat_state: ChatState,
    input_box_id: str,
) -> rx.Component:
    return rx.box(
        rx.vstack(
            nav_bar(
                on_create_new_chat=chat_state.create_new_chat,
            ),
            chat_body(
                chat_interactions=chat_state.chat_interactions,
                has_token=chat_state.has_token,
                divider_title_text=chat_state.timestamp_formatted,
            ),
            input_box(
                input_box_text_value=chat_state.prompt,
                input_prompt_is_loading=chat_state.ai_loading,
                input_prompt_on_change=chat_state.set_prompt,
                send_button_on_click=chat_state.submit_prompt(),
                library_prompt=LibraryPrompt,
                input_box_id=input_box_id,
            ),
            **STYLE.body,
        ),
        **STYLE.parent,
    )


def chat_page(
    chat_state: ChatState,
    input_box_id: str,
):
    return _chat_box(
        chat_state=chat_state,
        input_box_id=input_box_id,
    )
