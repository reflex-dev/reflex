from __future__ import annotations

import datetime

import pytz
import sqlmodel


class ChatInteraction(
    sqlmodel.SQLModel,
    table=True,
):
    """A table for questions and answers in the database."""

    id: int | None = sqlmodel.Field(default=None, primary_key=True)
    prompt: str
    answer: str
    chat_participant_user_name: str
    timestamp: datetime.datetime = datetime.datetime.now(
        tz=pytz.timezone(
            "US/Pacific",
        ),
    )
    chat_participant_user_avatar_url: str = "/avatar-default.png"

    chat_participant_assistant_name: str = "Reflex Bot"
    chat_participant_assistant_avatar_url: str = "/reflex-avatar.png"
