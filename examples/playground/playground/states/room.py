"""A room's visitor: the name it shows and the events it sends to the room's board."""

import random
import re

import reflex as rx

from playground.state import BoardState
from playground.states import route_arg

BURST = 10
# Shared state tokens cannot contain underscores.
_NOT_TOKEN = re.compile(r"[^a-z0-9-]+")


def room_token(text: str) -> str:
    """Turn a room name into a board token.

    Args:
        text: What the URL or the input says.

    Returns:
        Lowercase letters, digits and dashes; ``lobby`` when nothing is left.
    """
    return _NOT_TOKEN.sub("-", text.lower()).strip("-") or "lobby"


class RoomState(rx.State):
    """This session's name, room and sent events; the room itself is BoardState."""

    name: str = ""
    room: str = ""
    token_draft: str = ""
    sent: int = 0
    # Backend only: the client number sent with broadcasts.
    _client: int = 0

    @rx.event
    def enter(self):
        """Join the room the URL names: the room page's on_load.

        Returns:
            The event linking the board and showing this session's name.
        """
        if not self.name:
            self._client = random.randrange(1000, 10_000)
            self.name = f"guest-{self._client}"
        self.room = room_token(route_arg(self.router.url.path))
        return BoardState.enter_room(self.room, self.name)

    @rx.event
    def leave(self):
        """Leave the room.

        Returns:
            The event unlinking the board.
        """
        self.room = ""
        return BoardState.leave_room(self.name)

    @rx.event
    def broadcast(self):
        """Send one event every linked session receives: the fan-out shape.

        Returns:
            The shared state event.
        """
        self.sent += 1
        return BoardState.set_seq_shared(self.sent, self._client)

    @rx.event
    def burst(self):
        """Increment the shared counter ten times at once: the contention shape.

        Returns:
            The ten increments.
        """
        return [BoardState.increment for _ in range(BURST)]

    @rx.event
    def set_token_draft(self, value: str):
        """Keep the board token typed on the board page.

        Args:
            value: The input's value.
        """
        self.token_draft = value

    @rx.event
    def join_draft(self):
        """Link the board page to the typed token.

        Returns:
            The join event of the board.
        """
        return BoardState.join(room_token(self.token_draft))
