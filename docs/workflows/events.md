---
meta_description: Make a reflex-workflow run wait for an approval, webhook, or reply, with an optional deadline. Deliver events idempotently and handle events that arrive early or late.
---

# Waiting for Events

A run can pause until something outside it happens, such as a manager approving an expense, a payment provider calling a webhook, or a customer replying, and continue with the data that event carries. While it waits, the run is a row in the table; no worker or connection is held open, however long the wait.

## Wait for an event

Return `wait_for` from a step, naming the step the event should run:

```python
from datetime import timedelta
from typing import Literal

from reflex_workflow import Workflow, step, wait_for


class Expense(Base, Workflow):
    __tablename__ = "expense"

    id: Mapped[int] = mapped_column(primary_key=True)
    amount: Mapped[int]
    status: Mapped[str] = mapped_column(String(32), default="draft")
    decided_by: Mapped[str | None] = mapped_column(String(255), default=None)

    @step
    async def request_approval(self):
        await notify_manager(self.id)
        self.status = "pending"
        return wait_for(
            Expense.decide,
            timeout=timedelta(days=2),
            on_timeout=Expense.escalate,
        )

    @step
    async def decide(self, verdict: Literal["approve", "reject"], *, by: str):
        self.status = "approved" if verdict == "approve" else "rejected"
        self.decided_by = by

    @step
    async def escalate(self):
        await notify_finance(self.id)
        self.status = "escalated"
```

The step you wait on is the channel: an event addressed to `Expense.decide` ends this wait and runs `decide` with the event's arguments.

`timeout` and `on_timeout` are optional, and go together. With them, the run gives up waiting once the timeout passes and runs `on_timeout` instead. Without them, it waits indefinitely.

## Deliver an event

To deliver an event, address the runs it is for and call `deliver` with the step and its arguments:

```python
class ApprovalState(rx.State):
    manager_email: str = ""

    @rx.event
    async def approve(self, expense_id: int, request_id: str):
        accepted = await Expense.by(Expense.id == expense_id).deliver(
            Expense.decide("approve", by=self.manager_email),
            key=request_id,
        )
        if not accepted:
            return rx.toast("This expense is no longer waiting for approval.")
```

`deliver` returns how many runs accepted the event. A run accepts an event when it is waiting for that step, or when it hasn't reached its wait yet; see [Events that arrive early](#events-that-arrive-early). A run that is waiting for a different step, or has finished, refuses it.

The arguments are checked against the step's signature before anything is written, so a payload that doesn't fit the step raises instead of failing later in the run.

## Deliver each event once

Webhooks are retried and users double-click. Pass a `key` that identifies the event, such as the webhook's delivery ID, and a run accepts each key only once. This webhook is a route on a FastAPI app passed to Reflex as an [API transformer](/docs/api-routes/overview/):

```python
@fastapi_app.post("/webhooks/payments")
async def payment_webhook(event: PaymentEvent):
    await Invoice.by(Invoice.payment_id == event.payment_id).deliver(
        Invoice.paid(event.amount),
        key=event.id,
    )
    return {"ok": True}
```

A run remembers the last 16 keys it has accepted, and `deliver` returns `0` for a repeat. Without a key, every delivery counts as a new event.

## Events that arrive early

An event can arrive before the run starts waiting for it. For example, a payment webhook can arrive while the step that requested the payment is still running. The run holds the event, and applies it as soon as it waits for that step, so a fast reply is never lost.

A held event is discarded if the run instead goes on to wait for a different step, finishes, or moves to its next scheduled occurrence. In that case, whoever sent the event has to send it again. The key of a discarded event isn't remembered, so the resend is accepted.

A run holds at most one event. While it holds one, `deliver` refuses a second event and returns `0`, rather than replacing an answer that was already given.

## Deadlines

The deadline decides when a wait ends. Once it passes, the run refuses events and `deliver` returns `0`, even if no worker has run the timeout step yet. A sender that keeps retrying can't extend a deadline by racing the workers.

The deadline is compared with the time the delivery's database statement starts. A delivery that starts just before the deadline and then waits for a lock held by another transaction is accepted, even if it commits just after the deadline.

## Restart finished runs with an event

A finished run refuses events. For a run that should live as long as its events keep coming, such as a support conversation that closes after a quiet period, pass `restart=True`:

```python
await Conversation.by(Conversation.thread_id == thread_id).deliver(
    Conversation.reply(message.text),
    key=message.id,
    restart=True,
)
```

A waiting run takes the event as usual. A finished run starts again at the event's step, with the event's arguments.
