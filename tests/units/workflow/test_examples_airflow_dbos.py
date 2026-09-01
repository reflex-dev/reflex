"""Executable Reflex translations of canonical Airflow and DBOS examples.

Official sources:

* https://airflow.apache.org/docs/apache-airflow/stable/tutorial_taskflow_api.html
* https://docs.dbos.dev/python/examples/outbox
"""

import pytest
from reflex_base.workflow import (
    Retry,
    TransientWorkflowError,
    WorkflowConfig,
    complete,
    manual,
)

import reflex as rx
from reflex.workflow.records import RunStatus
from reflex.workflow.testing import WorkflowTestHarness

AIRFLOW_LOADS: list[float] = []


class AirflowTaskFlowETL(rx.State):
    """Airflow's TaskFlow tutorial: extract, transform, then load order data."""

    __workflow__ = WorkflowConfig(id="examples.airflow_taskflow_etl")

    orders: dict[str, float] = {}
    total_order_value: float = 0.0

    @rx.event(durable=True, trigger=manual(), effect="read")
    def extract(self):
        """Extract the tutorial's hard-coded orders.

        Returns:
            The transform step.
        """
        self.orders = {"1001": 301.27, "1002": 433.21, "1003": 502.22}
        return AirflowTaskFlowETL.transform

    @rx.event(durable=True, effect="none")
    def transform(self):
        """Compute the same aggregate as the TaskFlow transform task.

        Returns:
            The load step.
        """
        self.total_order_value = sum(self.orders.values())
        return AirflowTaskFlowETL.load

    @rx.event(durable=True, effect="idempotent_write")
    def load(self):
        """Stand in for loading the aggregate into an analytics sink.

        Returns:
            Completion containing the aggregate.
        """
        AIRFLOW_LOADS.append(self.total_order_value)
        return complete(result={"total_order_value": self.total_order_value})


async def test_airflow_taskflow_etl_translates_to_durable_handlers(
    forked_registration_context,
):
    """The TaskFlow tutorial maps directly to three persisted transitions."""
    AIRFLOW_LOADS.clear()

    async with WorkflowTestHarness(AirflowTaskFlowETL) as harness:
        started = await harness.start(AirflowTaskFlowETL.extract)
        assert started.run_id is not None

        run = await harness.get_run(started.run_id)
        assert run is not None
        assert run.status is RunStatus.COMPLETED
        assert run.result["total_order_value"] == pytest.approx(1236.70)
        assert [pytest.approx(1236.70)] == AIRFLOW_LOADS
        assert [step.handler_id for step in run.steps] == [
            "extract",
            "transform",
            "load",
        ]


DBOS_INSERTS: list[str] = []
DBOS_NOTIFICATIONS: list[str] = []
DBOS_NOTIFICATION_ATTEMPTS: list[str] = []


def _insert_order(customer: str, item: str, quantity: int) -> str:
    """Simulate DBOS's transactional order insert.

    Returns:
        The inserted order ID.
    """
    order_id = f"order-{customer}-{item}-{quantity}"
    DBOS_INSERTS.append(order_id)
    return order_id


def _send_order_notification(order_id: str) -> None:
    """Fail the first delivery, like a temporarily unavailable broker."""
    DBOS_NOTIFICATION_ATTEMPTS.append(order_id)
    if len(DBOS_NOTIFICATION_ATTEMPTS) == 1:
        msg = "notification broker unavailable"
        raise TransientWorkflowError(msg)
    DBOS_NOTIFICATIONS.append(order_id)


class DBOSTransactionalOutbox(rx.State):
    """Best available translation of DBOS's transactional-outbox workflow."""

    __workflow__ = WorkflowConfig(id="examples.dbos_transactional_outbox")

    @rx.event(
        durable=True,
        trigger=manual(),
        effect="idempotent_write",
        retry=Retry(max_attempts=2, initial_delay="1s", jitter="none"),
    )
    async def place_order(self, customer: str, item: str, quantity: int):
        """Checkpoint the insert before attempting the notification.

        This recreates DBOS's authoring shape, but not its atomic guarantee:
        ``rx.step`` records after the callable returns, so the real insert
        must still be idempotent across a crash between commit and recording.

        Returns:
            Completion containing the order ID.
        """
        order_id = await rx.step(
            "insert_order", _insert_order, customer, item, quantity
        )
        await rx.step("send_order_notification", _send_order_notification, order_id)
        return complete(result={"order_id": order_id, "notified": True})


async def test_dbos_outbox_shape_replays_the_insert_after_notification_failure(
    forked_registration_context,
):
    """A recorded Reflex substep is not repeated by a later handler retry."""
    DBOS_INSERTS.clear()
    DBOS_NOTIFICATIONS.clear()
    DBOS_NOTIFICATION_ATTEMPTS.clear()

    async with WorkflowTestHarness(DBOSTransactionalOutbox) as harness:
        started = await harness.start(
            DBOSTransactionalOutbox.place_order("alice", "book", 2)
        )
        assert started.run_id is not None

        retrying = await harness.get_run(started.run_id)
        assert retrying is not None
        assert retrying.status is RunStatus.RETRYING
        assert len(DBOS_INSERTS) == 1

        await harness.advance("1s")
        completed = await harness.get_run(started.run_id)
        assert completed is not None
        assert completed.status is RunStatus.COMPLETED
        assert completed.result == {
            "order_id": "order-alice-book-2",
            "notified": True,
        }
        assert DBOS_INSERTS == ["order-alice-book-2"]
        assert DBOS_NOTIFICATION_ATTEMPTS == [
            "order-alice-book-2",
            "order-alice-book-2",
        ]
        assert DBOS_NOTIFICATIONS == ["order-alice-book-2"]
