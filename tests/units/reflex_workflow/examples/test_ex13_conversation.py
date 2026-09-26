"""13 · Conversational agent with tools and confirmations.

Pass condition: a conversation survives a worker restart and a late response; a
duplicated confirmation does not repeat the action; tool outcomes remain visible
to the agent.

Acceptance checks: pause for a reply, restart the workers, then send several
messages in quick succession; deliver a confirmation twice around the action; fail
a later model call without repeating the tool call before it; fire a reminder
concurrently with a customer's reply without sending an obsolete one.
"""

from __future__ import annotations

import asyncio
import datetime
import uuid

import pytest
from examples import ex13_conversation
from examples.ex13_conversation import (
    Conversation,
    Message,
    Transfer,
    arrival_lock,
    confirm,
    receive,
    wake,
    write,
)
from examples.services import world
from reflex_workflow import connect_workflows
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .conftest import eventually, worker

pytestmark = pytest.mark.asyncio(loop_scope="module")

QUICKLY = datetime.timedelta(milliseconds=300)


def new_conversation() -> str:
    """Name a fresh conversation.

    Returns:
        The conversation's id, which is also its customer's.
    """
    return uuid.uuid4().hex


def plan_balance(conversation: str, message: str, balance: int = 120) -> None:
    """Decide what the bank answers when a message asks for the balance.

    Args:
        conversation: The conversation.
        message: The customer's message id.
        balance: What the bank reports.
    """
    world.plan(
        "bank.balance", f"{conversation}:customer:{message}", {"amount": balance}
    )


def replies(conversation: str) -> list[str]:
    """Return what the agent has said to a customer, in order, once each.

    Args:
        conversation: The conversation, whose id is also its customer's.

    Returns:
        Every reply and reminder sent to them.
    """
    return [
        sent["text"]
        for sent in world.effects("chat.send")
        if sent["to"] == conversation
    ]


def reminders(conversation: str) -> list[str]:
    """Return the keys of the reminders a conversation sent.

    Args:
        conversation: The conversation.

    Returns:
        One key per reminder sent.
    """
    return [
        key
        for action, key in world.records
        if action == "chat.send" and key.startswith(f"remind:{conversation}:")
    ]


def said(conversation: str, *fragments: str):
    """Build a check that the agent has said each of these, in this order.

    Args:
        conversation: The conversation.
        *fragments: What the replies must contain, in order.

    Returns:
        A predicate.
    """

    def check() -> bool:
        """Tell whether the agent has said each fragment, in order.

        Returns:
            Whether it has.
        """
        spoken = " ".join(replies(conversation))
        position = 0
        for fragment in fragments:
            position = spoken.find(fragment, position)
            if position < 0:
                return False
            position += len(fragment)
        return True

    return check


def transfer_is(key: str, status: str):
    """Build a check that a transfer has reached a status.

    Args:
        key: The transfer's key.
        status: The status to wait for.

    Returns:
        An async predicate.
    """

    async def check() -> bool:
        """Tell whether the transfer has reached the status.

        Returns:
            Whether it has.
        """
        row = await Transfer.by(Transfer.key == key).get()
        return row is not None and row.status == status

    return check


def conversation_is(conversation: str, status: str):
    """Build a check that a conversation has reached a status.

    Args:
        conversation: The conversation.
        status: The status to wait for.

    Returns:
        An async predicate.
    """

    async def check() -> bool:
        """Tell whether the conversation has reached the status.

        Returns:
            Whether it has.
        """
        row = await Conversation.by(Conversation.conversation == conversation).get()
        return row is not None and row.status == status

    return check


async def transfer_of(conversation: str) -> list[Transfer]:
    """Load a conversation's transfers, oldest first.

    Args:
        conversation: The conversation.

    Returns:
        Its transfers.
    """
    rows = await Transfer.by(Transfer.conversation == conversation).all()
    return sorted(rows, key=lambda row: row.id)


async def transcript_of(
    factory: async_sessionmaker[AsyncSession], conversation: str
) -> list[Message]:
    """Read a conversation's transcript directly.

    Args:
        factory: The session factory for the test database.
        conversation: The conversation.

    Returns:
        Its messages, oldest first.
    """
    async with factory() as session:
        return list(
            (
                await session.execute(
                    select(Message)
                    .where(Message.conversation == conversation)
                    .order_by(Message.id)
                )
            )
            .scalars()
            .all()
        )


async def test_a_question_is_answered_with_what_the_tool_found(database):
    conversation = new_conversation()
    plan_balance(conversation, "m1", 120)
    async with worker(database):
        await receive(conversation, conversation, "m1", "What's my balance?")
        await eventually(said(conversation, "Your balance is 120."))

    # The tool's answer is in the transcript, where every later turn reads it.
    rows = await transcript_of(database, conversation)
    tools = [m for m in rows if m.role == "tool"]
    assert [(m.data["tool"], m.data["amount"]) for m in tools] == [("balance", 120)]


async def test_a_redelivered_message_is_answered_once(database):
    conversation = new_conversation()
    plan_balance(conversation, "m1")
    async with worker(database):
        await receive(conversation, conversation, "m1", "What's my balance?")
        await receive(conversation, conversation, "m1", "What's my balance?")
        await eventually(said(conversation, "Your balance is"))
        await asyncio.sleep(0.5)

    rows = await transcript_of(database, conversation)
    assert [m.role for m in rows] == ["customer", "tool", "agent"]
    assert len(replies(conversation)) == 1


async def test_a_confirmed_transfer_is_sent_once_however_often_it_is_confirmed(
    database,
):
    conversation = new_conversation()
    async with worker(database):
        await receive(conversation, conversation, "m1", "Please send 50 to amy")
        await eventually(said(conversation, "Please confirm sending 50 to amy."))
        [transfer] = await transfer_of(conversation)
        await eventually(transfer_is(transfer.key, "awaiting confirmation"))

        # The bank is slow to answer, so the transfer is still being made while
        # the same click arrives twice at once, again a moment later, and a
        # second click after that.
        sending = world.hold("bank.transfer")
        taken = await asyncio.gather(
            confirm(transfer.key, "yes", "click-1"),
            confirm(transfer.key, "yes", "click-1"),
        )
        assert sorted(taken) == [0, 1]
        await eventually(lambda: world.attempts("bank.transfer") == 1)
        assert await confirm(transfer.key, "yes", "click-1") == 0
        await confirm(transfer.key, "yes", "click-2")
        sending.set()

        await eventually(said(conversation, "Transfer of 50 to amy: sent."))
        assert await confirm(transfer.key, "yes", "click-3") == 0

    assert world.attempts("bank.transfer") == 1


async def test_the_conversation_carries_on_while_a_transfer_waits(database):
    conversation = new_conversation()
    plan_balance(conversation, "m2", 80)
    async with worker(database):
        await receive(conversation, conversation, "m1", "send 5 to bo")
        await eventually(said(conversation, "Please confirm sending 5 to bo."))

        await receive(conversation, conversation, "m2", "and my balance?")
        await eventually(said(conversation, "Your balance is 80."))
        [transfer] = await transfer_of(conversation)
        assert transfer.status == "awaiting confirmation"

        assert await confirm(transfer.key, "no", "click-1") == 1
        await eventually(said(conversation, "Transfer of 5 to bo: declined."))
    assert not world.effects("bank.transfer")


async def test_a_failing_model_call_does_not_repeat_the_tool_before_it(database):
    conversation = new_conversation()
    plan_balance(conversation, "m1", 42)
    # Nothing runs yet, so the message's id is known before any turn takes it,
    # and the model's second call of that turn can be made to fail.
    async with connect_workflows(database):
        await receive(conversation, conversation, "m1", "balance please")
    [message] = await transcript_of(database, conversation)
    world.break_next("model.respond", times=2, key=f"{conversation}:{message.id}:1")

    async with worker(database):
        await eventually(said(conversation, "Your balance is 42."))

    assert world.attempts("bank.balance") == 1
    # Once for the tool, then the failing call twice and the one that worked.
    assert world.attempts("model.respond") == 4


async def test_a_message_that_arrives_during_a_turn_gets_the_next_one(database):
    conversation = new_conversation()
    async with connect_workflows(database):
        await receive(conversation, conversation, "m1", "send 4 to fa")
    [first] = await transcript_of(database, conversation)
    # The model is slow to answer the first message, and the second arrives while
    # the turn that answers the first is still thinking.
    thinking = world.hold("model.respond", key=f"{conversation}:{first.id}:0")

    async with worker(database):
        await eventually(lambda: world.attempts("model.respond") == 1)
        await receive(conversation, conversation, "m2", "send 6 to gu")
        thinking.set()
        await eventually(
            said(
                conversation,
                "Please confirm sending 4 to fa.",
                "Please confirm sending 6 to gu.",
            )
        )


async def test_a_burst_after_a_restart_is_answered_in_order(database):
    conversation = new_conversation()
    async with worker(database):
        await receive(conversation, conversation, "m1", "hello")
        await eventually(said(conversation, "I can check your balance"))
        await eventually(conversation_is(conversation, "waiting for the customer"))

    # The workers are down, and the customer writes three times in a row.
    plan_balance(conversation, "m2", 300)
    async with connect_workflows(database):
        await receive(conversation, conversation, "m2", "what's my balance")
        await receive(conversation, conversation, "m3", "send 5 to amy")
        await receive(conversation, conversation, "m4", "send 7 to bo")

    async with worker(database):
        await eventually(
            said(
                conversation,
                "Your balance is 300.",
                "Please confirm sending 5 to amy.",
                "Please confirm sending 7 to bo.",
            )
        )
        # And more, while it is running again.
        await receive(conversation, conversation, "m5", "send 1 to cy")
        await receive(conversation, conversation, "m6", "send 2 to di")
        await eventually(
            said(
                conversation,
                "Please confirm sending 1 to cy.",
                "Please confirm sending 2 to di.",
            )
        )

    async with connect_workflows(database):
        transfers = await transfer_of(conversation)
        row = await Conversation.by(Conversation.conversation == conversation).get()
    assert [(t.amount, t.to) for t in transfers] == [
        (5, "amy"),
        (7, "bo"),
        (1, "cy"),
        (2, "di"),
    ]
    # Every message was taken, and none twice.
    rows = await transcript_of(database, conversation)
    customers = [m for m in rows if m.role == "customer"]
    assert row is not None
    assert row.seen == customers[-1].id


async def test_a_quiet_customer_is_reminded_once_closed_and_can_come_back(
    database, monkeypatch
):
    monkeypatch.setattr(ex13_conversation, "REMIND_AFTER", QUICKLY)
    monkeypatch.setattr(ex13_conversation, "CLOSE_AFTER", QUICKLY)
    conversation = new_conversation()
    plan_balance(conversation, "m2", 15)
    async with worker(database):
        await receive(conversation, conversation, "m1", "hello")
        await eventually(conversation_is(conversation, "closed"))
        assert len(reminders(conversation)) == 1
        # The reminder is in the transcript, where a later turn can see it.
        rows = await transcript_of(database, conversation)
        assert [m.text for m in rows if m.key.startswith("remind:")] == [
            "Is there anything else I can help with?"
        ]

        # The customer comes back days later, and the conversation opens again.
        await receive(conversation, conversation, "m2", "what's my balance")
        await eventually(said(conversation, "Your balance is 15."))


async def test_a_reply_racing_the_reminder_stops_it(database, monkeypatch):
    monkeypatch.setattr(ex13_conversation, "REMIND_AFTER", QUICKLY)
    conversation = new_conversation()

    async def reminder_has_started() -> bool:
        # Started and still running, or already sent: a reminder that did not
        # wait for the lock is done before a poll would see it running.
        """Tell whether the reminder step is running or has sent its reminder.

        Returns:
            Whether it has.
        """
        async with database() as session:
            row = (
                await session.execute(
                    select(
                        Conversation.next_step,
                        Conversation.claimed_until,
                        Conversation.status,
                    ).where(Conversation.conversation == conversation)
                )
            ).one()
        running = row.next_step == "remind" and row.claimed_until is not None
        return running or row.status == "reminded"

    async with worker(database):
        await receive(conversation, conversation, "m1", "hello")
        await eventually(conversation_is(conversation, "waiting for the customer"))

        # The customer's reply is being accepted as the reminder goes out: its
        # transaction holds the conversation's lock when the reminder starts, and
        # the message is written, and committed, a moment after -- long enough
        # for a reminder that did not wait for the lock to have been sent.
        async with database() as session, session.begin():
            await session.execute(arrival_lock(conversation))
            await eventually(reminder_has_started)
            await asyncio.sleep(0.3)
            await write(
                session, conversation, "customer:m2", "customer", "send 3 to ed"
            )
        await wake(conversation, "customer:m2")

        await eventually(said(conversation, "Please confirm sending 3 to ed."))
    assert reminders(conversation) == []


async def test_a_redelivered_message_whose_wake_was_lost_is_answered(
    database, monkeypatch
):
    monkeypatch.setattr(ex13_conversation, "REMIND_AFTER", QUICKLY)
    monkeypatch.setattr(ex13_conversation, "CLOSE_AFTER", QUICKLY)
    conversation = new_conversation()
    async with worker(database):
        await receive(conversation, conversation, "m1", "hello")
        await eventually(conversation_is(conversation, "closed"))

        # The first delivery of m2 was written, then its process died before it
        # woke anything. The channel delivers it again.
        async with database() as session, session.begin():
            await write(
                session, conversation, "customer:m2", "customer", "send 9 to hu"
            )
        await receive(conversation, conversation, "m2", "send 9 to hu")
        await eventually(said(conversation, "Please confirm sending 9 to hu."))


async def test_an_outcome_waits_its_turn_behind_a_message_being_written(database):
    conversation = new_conversation()

    async def outcome_waits() -> bool:
        """Tell whether the outcome is waiting for the conversation's lock.

        Returns:
            Whether it is.
        """
        async with database() as session:
            return bool(
                await session.scalar(
                    text(
                        "SELECT count(*) FROM pg_locks WHERE locktype = 'advisory'"
                        " AND NOT granted"
                        " AND objid::bigint = hashtext(:lock)::bigint & 4294967295"
                    ),
                    {"lock": f"chat:{conversation}"},
                )
            )

    async with worker(database):
        await receive(conversation, conversation, "m1", "send 8 to ivy")
        await eventually(said(conversation, "Please confirm sending 8 to ivy."))
        [transfer] = await transfer_of(conversation)
        await eventually(transfer_is(transfer.key, "awaiting confirmation"))

        # A customer's message is being accepted, holding the conversation's
        # lock. The transfer's outcome arrives meanwhile, and must not take an id
        # after the message's and commit before it: it waits for the lock.
        async with database() as session, session.begin():
            await session.execute(arrival_lock(conversation))
            assert await confirm(transfer.key, "yes", "click-1") == 1
            await eventually(outcome_waits)
            rows = await transcript_of(database, conversation)
            assert [m for m in rows if m.role == "action"] == []

        await eventually(said(conversation, "Transfer of 8 to ivy: sent."))
