from __future__ import annotations

from enum import Enum

import reflex as rx

from chat_v2.components.avatars import chat_message_avatar
from chat_v2.components.dividers import chat_date_divider
from chat_v2.components.typography import msg_header
from chat_v2.page_chat.chat_messages.model_chat_interaction import ChatInteraction
from chat_v2.page_chat.chat_messages.model_chat_message_answer import ANSWER_STYLE
from chat_v2.page_chat.chat_messages.model_chat_message_question import (
    QUESTION_STYLE,
)
from chat_v2.templates.pop_up import dialog_library


class MessageType(Enum):
    QUESTION = "question"
    ANSWER = "answer"


def message_wrapper(
    chat_interaction: ChatInteraction,
    has_token: bool,
):
    def _get_message_question():
        return rx.hstack(
            rx.vstack(
                chat_message_avatar(
                    src=chat_interaction.chat_participant_user_avatar_url,
                ),
            ),
            rx.vstack(
                msg_header(
                    header_title=chat_interaction.chat_participant_user_name,
                    date=chat_interaction.timestamp,
                ),
                rx.markdown(
                    chat_interaction.prompt,
                    color=rx.color(
                        "slate",
                        11,
                    ),
                    overflow_wrap="break_word",
                    width="100%",
                ),
                # gap="24px",
                **QUESTION_STYLE.default,
            ),
        )

    def _get_message_answer(
        has_token: bool,
    ):
        return rx.hstack(
            rx.vstack(
                chat_message_avatar(
                    src=chat_interaction.chat_participant_assistant_avatar_url,
                ),
            ),
            rx.vstack(
                msg_header(
                    header_title=chat_interaction.chat_participant_assistant_name,
                    date=chat_interaction.timestamp,
                ),
                rx.markdown(
                    chat_interaction.answer,
                    color=rx.color(
                        color="slate",
                        shade=11,
                    ),
                ),
                overflow_wrap="break_word",
                width="100%",
            ),
            # action_bar(
            #     has_token=has_token,
            # ),
            **ANSWER_STYLE.default,
        )

    return rx.fragment(
        _get_message_question(),
        _get_message_answer(
            has_token=has_token,
        ),
    )


def chat_body(
    chat_interactions: list[ChatInteraction],
    divider_title_text: str,
    has_token: bool,
):
    return rx.vstack(
        chat_date_divider(
            divider_title_text=divider_title_text,
        ),
        rx.scroll_area(
            rx.vstack(
                rx.foreach(
                    chat_interactions,
                    lambda chat_interaction: message_wrapper(
                        chat_interaction=chat_interaction,
                        has_token=has_token,
                    ),
                ),
                gap="2em",
            ),
            scrollbars="vertical",
            type="scroll",
        ),
        dialog_library(),
        width="100%",
        overflow="scroll",
        scrollbar_width="none",
        gap="40px",
    )
