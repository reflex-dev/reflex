"""Competitor saga examples expressed with Reflex Workflows.

Official sources:

* https://github.com/temporalio/money-transfer-project-template-python
* https://docs.restate.dev/guides/sagas

The examples intentionally keep provider calls as ordinary Python functions.
``rx.step`` is the durable activity boundary and the provider-facing key from
``rx.current_run`` closes the small crash window before a step result records.
"""

from __future__ import annotations

from typing import Any

from reflex_base.workflow import Retry, WorkflowConfig, manual

import reflex as rx
from reflex.workflow.records import RunStatus
from reflex.workflow.testing import WorkflowTestHarness

MONEY_EFFECTS: list[tuple[str, str]] = []
TRAVEL_EFFECTS: list[tuple[str, str]] = []


class DepositRejected(Exception):
    """The target bank rejected a deposit permanently."""


class HotelUnavailable(Exception):
    """The hotel cannot satisfy this booking request."""


def _money_effect(
    operation: str,
    account: str,
    amount: int,
    reference_id: str,
    idempotency_key: str,
) -> dict[str, Any]:
    """Simulate an idempotent banking API call.

    Args:
        operation: Banking operation being performed.
        account: Account affected by the operation.
        amount: Amount transferred in cents.
        reference_id: Business transfer identifier.
        idempotency_key: Provider-facing request identity.

    Returns:
        A JSON-compatible provider receipt.
    """
    MONEY_EFFECTS.append((f"{operation}:{account}", idempotency_key))
    return {
        "operation": operation,
        "account": account,
        "amount": amount,
        "reference_id": reference_id,
        "idempotency_key": idempotency_key,
    }


def _withdraw(
    account: str, amount: int, reference_id: str, idempotency_key: str
) -> dict[str, Any]:
    """Withdraw money from the source account.

    Args:
        account: Source account.
        amount: Amount in cents.
        reference_id: Business transfer identifier.
        idempotency_key: Provider-facing request identity.

    Returns:
        The withdrawal receipt.
    """
    return _money_effect("withdraw", account, amount, reference_id, idempotency_key)


def _deposit(
    account: str,
    amount: int,
    reference_id: str,
    idempotency_key: str,
    reject: bool,
) -> dict[str, Any]:
    """Deposit money, optionally simulating a permanent rejection.

    Args:
        account: Target account.
        amount: Amount in cents.
        reference_id: Business transfer identifier.
        idempotency_key: Provider-facing request identity.
        reject: Whether the target bank rejects this deposit.

    Returns:
        The deposit receipt.

    Raises:
        DepositRejected: When ``reject`` is true.
    """
    receipt = _money_effect("deposit", account, amount, reference_id, idempotency_key)
    if reject:
        msg = f"target account {account} rejected transfer {reference_id}"
        raise DepositRejected(msg)
    return receipt


def _refund(
    account: str, amount: int, reference_id: str, idempotency_key: str
) -> dict[str, Any]:
    """Compensate a successful withdrawal.

    Args:
        account: Source account receiving its money back.
        amount: Amount in cents.
        reference_id: Business transfer identifier.
        idempotency_key: Provider-facing request identity.

    Returns:
        The refund receipt.
    """
    return _money_effect("refund", account, amount, reference_id, idempotency_key)


class TemporalMoneyTransfer(rx.State):
    """Temporal's withdraw/deposit/refund tutorial as a Reflex workflow."""

    __workflow__ = WorkflowConfig(id="examples.temporal.money_transfer")

    reference_id: str = ""
    phase: str = "new"

    @rx.event(
        durable=True,
        trigger=manual(),
        effect="idempotent_write",
        retry=Retry(max_attempts=3, initial_delay="1s", jitter="none"),
    )
    async def transfer(
        self,
        source_account: str,
        target_account: str,
        amount: int,
        reference_id: str,
        reject_deposit: bool = False,
    ):
        """Withdraw, deposit, and refund the withdrawal if deposit fails.

        Args:
            source_account: Account money leaves.
            target_account: Account money enters.
            amount: Amount in cents.
            reference_id: Stable business transfer identifier.
            reject_deposit: Simulate a terminal target-bank rejection.

        Returns:
            Completion on success, or a compensated business failure.
        """
        context = rx.current_run()
        if context is None:
            msg = "money transfer must run inside a durable attempt"
            raise RuntimeError(msg)

        self.reference_id = reference_id
        self.phase = "withdrawing"
        withdrawal = await rx.step(
            "withdraw",
            _withdraw,
            source_account,
            amount,
            reference_id,
            context.idempotency_key(scope="withdraw"),
        )

        try:
            self.phase = "depositing"
            deposit = await rx.step(
                "deposit",
                _deposit,
                target_account,
                amount,
                reference_id,
                context.idempotency_key(scope="deposit"),
                reject_deposit,
            )
        except DepositRejected as error:
            self.phase = "refunding"
            refund = await rx.step(
                "refund",
                _refund,
                source_account,
                amount,
                reference_id,
                context.idempotency_key(scope="refund"),
            )
            self.phase = "refunded"
            return rx.fail(
                "deposit_rejected",
                details={"message": str(error), "refund": refund},
            )

        self.phase = "completed"
        return rx.complete(result={"withdrawal": withdrawal, "deposit": deposit})


def _travel_effect(
    operation: str, customer_id: str, idempotency_key: str
) -> dict[str, str]:
    """Simulate an idempotent travel-provider operation.

    Args:
        operation: Reservation or compensation being performed.
        customer_id: Customer owning the itinerary.
        idempotency_key: Provider-facing request identity.

    Returns:
        A JSON-compatible provider receipt.
    """
    TRAVEL_EFFECTS.append((operation, idempotency_key))
    return {
        "operation": operation,
        "customer_id": customer_id,
        "reservation_id": f"{operation}-{customer_id}",
        "idempotency_key": idempotency_key,
    }


def _book_flight(customer_id: str, idempotency_key: str) -> dict[str, str]:
    """Reserve the flight leg.

    Returns:
        The flight receipt.
    """
    return _travel_effect("book_flight", customer_id, idempotency_key)


def _book_car(customer_id: str, idempotency_key: str) -> dict[str, str]:
    """Reserve the rental car.

    Returns:
        The car receipt.
    """
    return _travel_effect("book_car", customer_id, idempotency_key)


def _book_hotel(
    customer_id: str, idempotency_key: str, unavailable: bool
) -> dict[str, str]:
    """Reserve the hotel, optionally simulating a terminal failure.

    Args:
        customer_id: Customer owning the itinerary.
        idempotency_key: Provider-facing request identity.
        unavailable: Whether the hotel is fully booked.

    Returns:
        The hotel receipt.

    Raises:
        HotelUnavailable: When ``unavailable`` is true.
    """
    receipt = _travel_effect("book_hotel", customer_id, idempotency_key)
    if unavailable:
        msg = f"hotel is unavailable for customer {customer_id}"
        raise HotelUnavailable(msg)
    return receipt


def _cancel_hotel(customer_id: str, idempotency_key: str) -> dict[str, str]:
    """Compensate the hotel reservation.

    Returns:
        The cancellation receipt.
    """
    return _travel_effect("cancel_hotel", customer_id, idempotency_key)


def _cancel_car(customer_id: str, idempotency_key: str) -> dict[str, str]:
    """Compensate the car reservation.

    Returns:
        The cancellation receipt.
    """
    return _travel_effect("cancel_car", customer_id, idempotency_key)


def _cancel_flight(customer_id: str, idempotency_key: str) -> dict[str, str]:
    """Compensate the flight reservation.

    Returns:
        The cancellation receipt.
    """
    return _travel_effect("cancel_flight", customer_id, idempotency_key)


class RestateTravelBooking(rx.State):
    """Restate's flight/car/hotel saga as a Reflex workflow."""

    __workflow__ = WorkflowConfig(id="examples.restate.travel_booking")

    customer_id: str = ""
    phase: str = "new"

    @rx.event(
        durable=True,
        trigger=manual(),
        effect="idempotent_write",
        retry=Retry(max_attempts=3, initial_delay="1s", jitter="none"),
    )
    async def book(self, customer_id: str, hotel_unavailable: bool = False):
        """Book flight, car, and hotel, compensating in reverse on failure.

        Args:
            customer_id: Customer owning the itinerary.
            hotel_unavailable: Simulate a terminal hotel failure.

        Returns:
            Completion on success, or a compensated business failure.
        """
        context = rx.current_run()
        if context is None:
            msg = "travel booking must run inside a durable attempt"
            raise RuntimeError(msg)

        self.customer_id = customer_id
        self.phase = "booking_flight"
        flight = await rx.step(
            "book-flight",
            _book_flight,
            customer_id,
            context.idempotency_key(scope="book-flight"),
        )
        self.phase = "booking_car"
        car = await rx.step(
            "book-car",
            _book_car,
            customer_id,
            context.idempotency_key(scope="book-car"),
        )

        try:
            self.phase = "booking_hotel"
            hotel = await rx.step(
                "book-hotel",
                _book_hotel,
                customer_id,
                context.idempotency_key(scope="book-hotel"),
                hotel_unavailable,
            )
        except HotelUnavailable as error:
            # Restate registers each compensation before its booking attempt.
            # Even an ambiguous hotel failure is therefore cancelled first,
            # followed by the earlier successful reservations in reverse.
            self.phase = "cancelling_hotel"
            cancelled_hotel = await rx.step(
                "cancel-hotel",
                _cancel_hotel,
                customer_id,
                context.idempotency_key(scope="cancel-hotel"),
            )
            self.phase = "cancelling_car"
            cancelled_car = await rx.step(
                "cancel-car",
                _cancel_car,
                customer_id,
                context.idempotency_key(scope="cancel-car"),
            )
            self.phase = "cancelling_flight"
            cancelled_flight = await rx.step(
                "cancel-flight",
                _cancel_flight,
                customer_id,
                context.idempotency_key(scope="cancel-flight"),
            )
            self.phase = "compensated"
            return rx.fail(
                "hotel_unavailable",
                details={
                    "message": str(error),
                    "compensated": [
                        cancelled_hotel["operation"],
                        cancelled_car["operation"],
                        cancelled_flight["operation"],
                    ],
                },
            )

        self.phase = "completed"
        return rx.complete(result={"flight": flight, "car": car, "hotel": hotel})


def _operations(effects: list[tuple[str, str]]) -> list[str]:
    """Return the provider operation names in execution order.

    Args:
        effects: Recorded provider calls.

    Returns:
        Operation names without their idempotency keys.
    """
    return [operation for operation, _ in effects]


def _assert_scoped_keys(effects: list[tuple[str, str]]) -> None:
    """Assert every provider call received a distinct stable key scope.

    Args:
        effects: Recorded provider calls.
    """
    keys = [key for _, key in effects]
    assert all(len(key) == 32 for key in keys)
    assert len(keys) == len(set(keys))


async def test_temporal_money_transfer_happy_path(
    forked_registration_context,
):
    """A successful withdrawal and deposit complete the transfer."""
    MONEY_EFFECTS.clear()
    async with WorkflowTestHarness(TemporalMoneyTransfer) as harness:
        started = await harness.start(
            TemporalMoneyTransfer.transfer(  # pyright: ignore[reportCallIssue]
                "alice", "bob", 5000, "tx-1"
            )
        )
        assert started.run_id is not None
        snapshot = await harness.get_run(started.run_id)

    assert snapshot is not None
    assert snapshot.status is RunStatus.COMPLETED
    assert snapshot.state["phase"] == "completed"
    assert snapshot.result["withdrawal"]["account"] == "alice"
    assert snapshot.result["deposit"]["account"] == "bob"
    assert _operations(MONEY_EFFECTS) == ["withdraw:alice", "deposit:bob"]
    _assert_scoped_keys(MONEY_EFFECTS)


async def test_temporal_money_transfer_refunds_after_deposit_failure(
    forked_registration_context,
):
    """A rejected deposit durably refunds the successful withdrawal."""
    MONEY_EFFECTS.clear()
    async with WorkflowTestHarness(TemporalMoneyTransfer) as harness:
        started = await harness.start(
            TemporalMoneyTransfer.transfer(  # pyright: ignore[reportCallIssue]
                "alice", "bob", 5000, "tx-2", reject_deposit=True
            )
        )
        assert started.run_id is not None
        snapshot = await harness.get_run(started.run_id)

    assert snapshot is not None
    assert snapshot.status is RunStatus.FAILED
    assert snapshot.state["phase"] == "refunded"
    assert snapshot.error is not None
    assert snapshot.error["reason"] == "deposit_rejected"
    assert snapshot.error["details"]["refund"]["account"] == "alice"
    assert _operations(MONEY_EFFECTS) == [
        "withdraw:alice",
        "deposit:bob",
        "refund:alice",
    ]
    _assert_scoped_keys(MONEY_EFFECTS)


async def test_restate_travel_booking_happy_path(
    forked_registration_context,
):
    """Flight, car, and hotel all remain booked on success."""
    TRAVEL_EFFECTS.clear()
    async with WorkflowTestHarness(RestateTravelBooking) as harness:
        started = await harness.start(
            RestateTravelBooking.book(  # pyright: ignore[reportCallIssue]
                "customer-1"
            )
        )
        assert started.run_id is not None
        snapshot = await harness.get_run(started.run_id)

    assert snapshot is not None
    assert snapshot.status is RunStatus.COMPLETED
    assert snapshot.state["phase"] == "completed"
    assert snapshot.result["flight"]["operation"] == "book_flight"
    assert snapshot.result["car"]["operation"] == "book_car"
    assert snapshot.result["hotel"]["operation"] == "book_hotel"
    assert _operations(TRAVEL_EFFECTS) == [
        "book_flight",
        "book_car",
        "book_hotel",
    ]
    _assert_scoped_keys(TRAVEL_EFFECTS)


async def test_restate_travel_booking_compensates_in_reverse_order(
    forked_registration_context,
):
    """A terminal hotel failure cancels hotel, car, and then flight."""
    TRAVEL_EFFECTS.clear()
    async with WorkflowTestHarness(RestateTravelBooking) as harness:
        started = await harness.start(
            RestateTravelBooking.book(  # pyright: ignore[reportCallIssue]
                "customer-2", hotel_unavailable=True
            )
        )
        assert started.run_id is not None
        snapshot = await harness.get_run(started.run_id)

    assert snapshot is not None
    assert snapshot.status is RunStatus.FAILED
    assert snapshot.state["phase"] == "compensated"
    assert snapshot.error is not None
    assert snapshot.error["reason"] == "hotel_unavailable"
    assert snapshot.error["details"]["compensated"] == [
        "cancel_hotel",
        "cancel_car",
        "cancel_flight",
    ]
    assert _operations(TRAVEL_EFFECTS) == [
        "book_flight",
        "book_car",
        "book_hotel",
        "cancel_hotel",
        "cancel_car",
        "cancel_flight",
    ]
    _assert_scoped_keys(TRAVEL_EFFECTS)
