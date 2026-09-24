"""13 · Conversational agent with tools and confirmations.

A customer writes; the agent reads the conversation so far, calls a tool when it
needs a fact, replies, and waits for the next message. Every message -- the
customer's, the agent's, and what each tool and action returned -- is a row of
the transcript, so the agent sees every tool outcome on every later turn, and a
turn can be retried without losing or repeating any of it.

Moving money needs the customer's confirmation, and waiting for it must not stop
the conversation: the pending transfer is a run of its own, which asks, waits for
the confirmation, sends the money once, and writes the outcome back into the
transcript for the agent to report. A confirmation clicked twice is one transfer.

Messages are written to the transcript before the conversation is woken, so a
burst of them is never lost and is taken in the order it arrived, however busy
the conversation was. A customer who goes quiet gets one reminder; a reply that
lands while the reminder is going out either arrives first, and the reminder is
not sent, or arrives after it, and is answered as usual.

The model is a deterministic stand-in: it reads the transcript and decides the
next move, and its call goes through the fake provider so a test can fail it.
"""

from __future__ import annotations

import datetime
import re
from typing import Any

from reflex_workflow import Call, Wait, Workflow, step, wait_for
from reflex_workflow.engine.runtime import current
from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from examples.base import Base
from examples.services import world

# How long a quiet customer is given before a reminder, and after it before the
# conversation is closed. Tests shorten them.
REMIND_AFTER = datetime.timedelta(hours=4)
CLOSE_AFTER = datetime.timedelta(days=3)
# How long a transfer waits to be confirmed.
CONFIRM_WITHIN = datetime.timedelta(minutes=30)

RETRIES = 3
BACKOFF = datetime.timedelta(milliseconds=50)

# What the conversation reads as news: messages from outside its own steps.
INBOUND = ("customer", "action")
TRANSFER = re.compile(r"send (\d+) to (\w+)")


class Message(Base):
    """One entry in a conversation's transcript.

    ``customer`` and ``action`` rows come from outside the conversation's run and
    are what wakes it; ``agent`` and ``tool`` rows are written by its own steps.
    """

    __tablename__ = "example_message"
    __table_args__ = (UniqueConstraint("conversation", "key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation: Mapped[str] = mapped_column(
        String, ForeignKey("example_conversation.conversation"), index=True
    )
    # Identifies the message to whoever wrote it, so writing it twice is once.
    key: Mapped[str] = mapped_column(String)
    role: Mapped[str] = mapped_column(String)
    text: Mapped[str] = mapped_column(String, default="")
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


def arrival_lock(conversation: str) -> Any:
    """Build the lock that orders a message's arrival against a reminder.

    Args:
        conversation: The conversation.

    Returns:
        A select taking a transaction-scoped advisory lock for it.
    """
    return select(func.pg_advisory_xact_lock(func.hashtext(f"chat:{conversation}")))


async def write(
    session: AsyncSession,
    conversation: str,
    key: str,
    role: str,
    text: str = "",
    **data: Any,
) -> None:
    """Add a message to a transcript, unless one with this key is already there.

    Args:
        session: The transaction to write in.
        conversation: The conversation.
        key: The message's key within the conversation.
        role: Who it is from.
        text: What it says.
        **data: What a tool or action returned.
    """
    await session.execute(
        pg_insert(Message)
        .values(conversation=conversation, key=key, role=role, text=text, data=data)
        .on_conflict_do_nothing()
    )


async def arrive(
    conversation: str, key: str, role: str, text: str = "", **data: Any
) -> None:
    """Add an inbound entry -- a customer's message, an action's outcome.

    A turn takes the inbound entries up to the highest id it has seen, so they
    have to commit in the order their ids are handed out, or one committing late
    with a lower id would never be read. Each is written under the
    conversation's arrival lock, which also orders it against a reminder.

    Args:
        conversation: The conversation.
        key: The entry's key within the conversation.
        role: ``customer`` or ``action``.
        text: What it says.
        **data: What an action returned.
    """
    async with current().session_factory() as session, session.begin():
        await session.execute(arrival_lock(conversation))
        await write(session, conversation, key, role, text, **data)


async def transcript(conversation: str, seen: int) -> list[Message]:
    """Read what the agent may see: what arrived up to ``seen``, and its own work.

    Args:
        conversation: The conversation.
        seen: The last inbound message this turn took.

    Returns:
        The messages, oldest first.
    """
    async with current().session_factory() as session:
        return list(
            (
                await session.execute(
                    select(Message)
                    .where(
                        Message.conversation == conversation,
                        (Message.id <= seen) | Message.role.not_in(INBOUND),
                    )
                    .order_by(Message.id)
                )
            )
            .scalars()
            .all()
        )


async def unread(session: AsyncSession, conversation: str, seen: int) -> int | None:
    """Return the newest inbound message after ``seen``, if any.

    Args:
        session: The session to read with.
        conversation: The conversation.
        seen: The last inbound message already taken.

    Returns:
        Its id, or None when nothing new has arrived.
    """
    return await session.scalar(
        select(func.max(Message.id)).where(
            Message.conversation == conversation,
            Message.role.in_(INBOUND),
            Message.id > seen,
        )
    )


def respond(messages: list[Message], since: int, seen: int) -> dict[str, Any]:
    """Decide the agent's next move from the transcript, as a model would.

    This turn answers what arrived after ``since`` up to ``seen``: the customer's
    messages and the outcomes of actions. Tools already called are looked up by
    the message they answer. The first request still missing a fact asks for a
    tool; once none is, the agent replies.

    Args:
        messages: The transcript, oldest first.
        since: The last inbound message an earlier turn answered.
        seen: The last inbound message this turn answers.

    Returns:
        ``{"tool": ..., "ask": ...}``, ``{"confirm": ..., "ask": ...}`` or
        ``{"reply": ...}``.
    """
    turn = [m for m in messages if m.role in INBOUND and since < m.id <= seen]
    done = {
        (m.data["tool"], m.data["ask"]): m.data for m in messages if m.role == "tool"
    }
    lines = []
    for message in turn:
        if message.role == "action":
            outcome = message.data
            amount, to, status = outcome["amount"], outcome["to"], outcome["status"]
            lines.append(f"Transfer of {amount} to {to}: {status}.")
            continue
        text, ask = message.text.lower(), message.key
        if "balance" in text:
            if ("balance", ask) not in done:
                return {"tool": "balance", "ask": ask}
            lines.append(f"Your balance is {done['balance', ask]['amount']}.")
        elif match := TRANSFER.search(text):
            amount, to = int(match[1]), match[2]
            if ("propose", ask) not in done:
                return {"confirm": "transfer", "ask": ask, "amount": amount, "to": to}
            lines.append(f"Please confirm sending {amount} to {to}.")
        else:
            lines.append("I can check your balance or send money.")
    return {"reply": " ".join(lines)}


class Conversation(Base, Workflow):
    """One customer's conversation with the agent, for as long as it lasts."""

    __tablename__ = "example_conversation"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation: Mapped[str] = mapped_column(String, unique=True)
    customer: Mapped[str] = mapped_column(String)
    # The inbound messages the current turn answers: after ``since``, up to
    # ``seen``. Everything after ``seen`` is news for the next turn.
    since: Mapped[int] = mapped_column(Integer, default=0)
    seen: Mapped[int] = mapped_column(Integer, default=0)
    # Where the agent is, for whoever is watching the conversation.
    status: Mapped[str] = mapped_column(String, default="new")

    def waiting(self) -> Wait[Conversation]:
        """Wait for the customer, with a reminder if they go quiet.

        Returns:
            The wait.
        """
        self.status = "waiting for the customer"
        return wait_for(
            Conversation.turn, timeout=REMIND_AFTER, on_timeout=Conversation.remind
        )

    @step(retries=RETRIES, backoff=BACKOFF)
    async def turn(self) -> Call[Conversation] | Wait[Conversation]:
        """Take every message that has arrived since the last turn.

        Returns:
            The model's first call, or the wait again when nothing is new: a
            wake whose messages an earlier turn already took.
        """
        async with current().session_factory() as session:
            newest = await unread(session, self.conversation, self.seen)
        if newest is None:
            return self.waiting()
        self.since, self.seen = self.seen, newest
        return Conversation.think(0)

    @step(retries=RETRIES, backoff=BACKOFF)
    async def think(self, calls: int) -> Call[Conversation]:
        """Ask the model what to do next.

        Args:
            calls: How many tools this turn has called so far.

        Returns:
            A tool call, a proposal to confirm, or the reply.
        """
        self.status = "thinking"
        await world.call(
            "model.respond", key=f"{self.conversation}:{self.seen}:{calls}"
        )
        move = respond(
            await transcript(self.conversation, self.seen), self.since, self.seen
        )
        if "tool" in move:
            return Conversation.use_tool(move["tool"], move["ask"], calls)
        if "confirm" in move:
            return Conversation.propose(move["ask"], move["amount"], move["to"], calls)
        return Conversation.reply(move["reply"])

    @step(retries=RETRIES, backoff=BACKOFF)
    async def use_tool(self, tool: str, ask: str, calls: int) -> Call[Conversation]:
        """Call a tool and put what it returned in the transcript.

        Args:
            tool: The tool.
            ask: The message it answers.
            calls: How many tools this turn has called so far.

        Returns:
            The model again, now that it knows more.
        """
        self.status = f"checking {tool}"
        found = await world.call(
            f"bank.{tool}", key=f"{self.conversation}:{ask}", customer=self.customer
        )
        async with current().session_factory() as session, session.begin():
            await write(
                session,
                self.conversation,
                f"tool:{tool}:{ask}",
                "tool",
                tool=tool,
                ask=ask,
                **found,
            )
        return Conversation.think(calls + 1)

    @step(retries=RETRIES, backoff=BACKOFF)
    async def propose(
        self, ask: str, amount: int, to: str, calls: int
    ) -> Call[Conversation]:
        """Start a transfer that waits for the customer's confirmation.

        The transfer is a run of its own, so the conversation carries on while it
        waits.

        Args:
            ask: The message that asked for it.
            amount: How much.
            to: To whom.
            calls: How many tools this turn has called so far.

        Returns:
            The model again, which tells the customer to confirm.
        """
        key = f"{self.conversation}:{ask}"
        await Transfer(
            key=key,
            conversation=self.conversation,
            customer=self.customer,
            amount=amount,
            to=to,
        ).start(Transfer.ask)
        async with current().session_factory() as session, session.begin():
            await write(
                session,
                self.conversation,
                f"tool:propose:{ask}",
                "tool",
                tool="propose",
                ask=ask,
                transfer=key,
            )
        return Conversation.think(calls + 1)

    @step(retries=RETRIES, backoff=BACKOFF)
    async def reply(self, text: str) -> Wait[Conversation]:
        """Send the agent's reply, then wait for the customer.

        A message that arrived during the turn has already asked for the next one,
        and the engine holds that request until this wait arms.

        Args:
            text: What to say.

        Returns:
            The wait.
        """
        await world.call(
            "chat.send",
            key=f"reply:{self.conversation}:{self.seen}",
            to=self.customer,
            text=text,
        )
        async with current().session_factory() as session, session.begin():
            await write(session, self.conversation, f"reply:{self.seen}", "agent", text)
        return self.waiting()

    @step(retries=RETRIES, backoff=BACKOFF)
    async def remind(self) -> Call[Conversation] | Wait[Conversation]:
        """Nudge a customer who has gone quiet, unless they have just written.

        The check and the send hold the conversation's lock, which a message
        takes to arrive: a reply racing the reminder either lands first, and is
        seen here, or lands after the reminder went out.

        Returns:
            A turn for a message that just arrived, or a last, longer wait.
        """
        async with current().session_factory() as session, session.begin():
            await session.execute(arrival_lock(self.conversation))
            if await unread(session, self.conversation, self.seen) is not None:
                return Conversation.turn()
            text = "Is there anything else I can help with?"
            await world.call(
                "chat.send",
                key=f"remind:{self.conversation}:{self.seen}",
                to=self.customer,
                text=text,
            )
            # In the transcript too, so a later turn knows the customer was asked.
            await write(
                session, self.conversation, f"remind:{self.seen}", "agent", text
            )
        self.status = "reminded"
        return wait_for(
            Conversation.turn, timeout=CLOSE_AFTER, on_timeout=Conversation.close
        )

    @step
    async def close(self):
        """Close a conversation the customer walked away from."""
        self.status = "closed"


class Transfer(Base, Workflow):
    """Money the agent offered to send, waiting for the customer to confirm."""

    __tablename__ = "example_transfer"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String, unique=True)
    conversation: Mapped[str] = mapped_column(String, index=True)
    customer: Mapped[str] = mapped_column(String)
    amount: Mapped[int] = mapped_column(Integer)
    to: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="new")

    @step(retries=RETRIES, backoff=BACKOFF)
    async def ask(self):
        """Ask the customer to confirm, and wait for the answer.

        Returns:
            The wait for their confirmation.
        """
        await world.call(
            "chat.confirm",
            key=f"confirm:{self.key}",
            to=self.customer,
            text=f"Send {self.amount} to {self.to}?",
        )
        self.status = "awaiting confirmation"
        return wait_for(
            Transfer.confirm,
            timeout=CONFIRM_WITHIN,
            on_timeout=Transfer.report("expired"),
        )

    @step(retries=RETRIES, backoff=BACKOFF)
    async def confirm(self, answer: str):
        """Take the customer's answer.

        Args:
            answer: ``yes`` or ``no``.

        Returns:
            The transfer, or the report that it was declined.
        """
        if answer != "yes":
            return Transfer.report("declined")
        return Transfer.send

    @step(retries=RETRIES, backoff=BACKOFF)
    async def send(self):
        """Move the money, once, however often this step runs.

        Returns:
            The report that it was sent.
        """
        await world.call("bank.transfer", key=self.key, amount=self.amount, to=self.to)
        return Transfer.report("sent")

    @step(retries=RETRIES, backoff=BACKOFF)
    async def report(self, status: str):
        """Put the outcome in the transcript and tell the conversation.

        Args:
            status: ``sent``, ``declined`` or ``expired``.
        """
        self.status = status
        await arrive(
            self.conversation,
            f"action:{self.key}",
            "action",
            amount=self.amount,
            to=self.to,
            status=status,
        )
        await wake(self.conversation, f"action:{self.key}")


async def wake(conversation: str, key: str) -> None:
    """Tell a conversation the transcript entry ``key`` has arrived.

    A conversation that is waiting takes a turn now; one in the middle of a turn
    keeps the wake until it waits again; one that closed opens again. A
    conversation that has already read the entry is left alone, so a repeat of
    a wake that did land, or a redelivered message, costs nothing. And since the
    turn reads the transcript, a wake refused because another is already held
    loses nothing either.

    Args:
        conversation: The conversation.
        key: The transcript entry that arrived, which also keys the wake.
    """
    entry = (
        select(Message.id)
        .where(Message.conversation == conversation, Message.key == key)
        .scalar_subquery()
    )
    await Conversation.by(
        Conversation.conversation == conversation, Conversation.seen < entry
    ).deliver(Conversation.turn(), key=key, restart=True)


async def receive(conversation: str, customer: str, message: str, text: str) -> None:
    """Take a customer's message, from a webhook or the chat box.

    Args:
        conversation: Which conversation it belongs to.
        customer: Who sent it.
        message: The message's id at the channel, so a redelivery is one message.
        text: What it says.
    """
    # The conversation's row comes first, since the message belongs to it, and a
    # new conversation may take its first turn before the message is written;
    # the wake after the write is what makes sure a turn reads it.
    await Conversation(conversation=conversation, customer=customer).start(
        Conversation.turn
    )
    key = f"customer:{message}"
    await arrive(conversation, key, "customer", text)
    # A redelivery wakes the conversation too: the first delivery may have been
    # written and then lost before it woke anything.
    await wake(conversation, key)


async def confirm(transfer: str, answer: str, click: str) -> int:
    """Take the customer's answer to a confirmation, from the button they pressed.

    Args:
        transfer: The transfer's key.
        answer: ``yes`` or ``no``.
        click: The click's id; the same click delivered twice is one answer.

    Returns:
        How many transfers took the answer.
    """
    return await Transfer.by(Transfer.key == transfer).deliver(
        Transfer.confirm(answer), key=click
    )
