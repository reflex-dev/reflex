"""Integration tests for durable workflows inside a real app process.

Every other workflow test drives the runtime through harnesses. These start
an actual ``reflex run`` server and prove the pieces only a real process can:
the app lifespan starts the worker, a browser event can start a run, a
durable timer fires on the wall clock, the webhook endpoint accepts a signed
request over real HTTP, and the store resolves from the environment the way
a deployment would configure it.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Generator

import httpx
import pytest
from playwright.sync_api import Page, expect
from reflex_base.config import get_config

from reflex.testing import AppHarness

WEBHOOK_SECRET = "whsec_integration"


def WorkflowApp():
    """App with one workflow, started from a page and from a webhook."""
    import reflex as rx

    def stamp(order_id: str) -> dict:
        return {"stamped": order_id}

    class OrderFlow(rx.State):
        __workflow__ = rx.WorkflowConfig(id="integration.order")
        order_id: str = ""

        @rx.event(durable=True, trigger=rx.manual(), effect="idempotent_write")
        async def start(self, order_id: str):
            self.order_id = order_id
            await rx.step("stamp", stamp, order_id)
            return rx.after("2s", OrderFlow.finish)

        @rx.event(durable=True, effect="none")
        def finish(self):
            return rx.complete(result={"order": self.order_id})

        @rx.event(
            durable=True,
            effect="idempotent_write",
            trigger=rx.webhook(
                "orders.placed",
                verify=rx.hmac_signature(
                    secret_env="ORDERS_WEBHOOK_SECRET", header="X-Signature"
                ),
                dedupe_by="order_id",
            ),
        )
        def from_hook(self, payload: dict):
            self.order_id = str(payload.get("order_id", ""))
            return rx.complete(result={"via": "webhook"})

    class Dash(rx.State):
        run_id: str = ""
        status: str = ""

        @rx.event
        async def launch(self):
            result = await rx.workflows.start(OrderFlow.start("ord-77"))
            self.run_id = result.run_id or ""

        @rx.event
        async def refresh(self):
            if not self.run_id:
                return
            snapshot = await rx.workflows.get_run(self.run_id)
            self.status = snapshot.status.value if snapshot else "missing"

    @rx.page("/")
    def index():
        return rx.box(
            rx.button("launch", on_click=Dash.launch, id="launch"),
            rx.button("refresh", on_click=Dash.refresh, id="refresh"),
            rx.text(Dash.run_id, id="run-id"),
            rx.text(Dash.status, id="status"),
        )

    app = rx.App()
    app.add_workflow(OrderFlow)


@pytest.fixture(scope="module")
def workflow_app(
    app_harness_env: type[AppHarness],
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[AppHarness, None, None]:
    """Run WorkflowApp in dev or prod mode, store resolved from the environment.

    Args:
        app_harness_env: AppHarness (dev) or AppHarnessProd (prod).
        tmp_path_factory: pytest fixture for creating temporary directories.

    Yields:
        Running AppHarness instance.
    """
    db_dir = tmp_path_factory.mktemp("workflow_store")
    name = f"workflow_app_{app_harness_env.__name__.lower()}"
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("REFLEX_WORKFLOW_DATABASE", str(db_dir / "runs.db"))
        mp.setenv("ORDERS_WEBHOOK_SECRET", WEBHOOK_SECRET)
        with app_harness_env.create(
            root=tmp_path_factory.mktemp(name),
            app_name=name,
            app_source=WorkflowApp,
        ) as harness:
            assert harness.app_instance is not None, "app is not running"
            yield harness


def test_a_browser_event_starts_a_run_that_completes(
    workflow_app: AppHarness, page: Page
):
    """The full production path: click, durable timer, completion.

    One click proves the lifespan started the worker in the real server, the
    page handler reached the runtime, the substep recorded, the two-second
    timer fired on the wall clock, and the run completed into the SQLite file
    the environment named.
    """
    assert workflow_app.frontend_url is not None
    page.goto(workflow_app.frontend_url)
    page.locator("#launch").click()
    expect(page.locator("#run-id")).not_to_be_empty(timeout=10_000)

    def completed() -> bool:
        page.locator("#refresh").click()
        return page.locator("#status").inner_text() == "COMPLETED"

    assert AppHarness._poll_for(completed, timeout=20, step=0.5), (
        f"run never completed; last status {page.locator('#status').inner_text()!r}"
    )


def test_the_webhook_endpoint_accepts_a_signed_request(workflow_app: AppHarness):
    """A provider's signed delivery starts a run over real HTTP, exactly once."""
    base = get_config().api_url.rstrip("/")
    body = json.dumps({"order_id": "hook-1", "amount": 5}).encode()
    signature = hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()

    first = httpx.post(
        f"{base}/_workflow/webhook/orders.placed",
        content=body,
        headers={"X-Signature": signature, "content-type": "application/json"},
    )
    # 202: the run is durably admitted before the provider is acknowledged.
    assert first.status_code == 202, first.text
    run_id = first.json()["run_id"]

    # A redelivery reaches the same run rather than starting a second one.
    second = httpx.post(
        f"{base}/_workflow/webhook/orders.placed",
        content=body,
        headers={"X-Signature": signature, "content-type": "application/json"},
    )
    assert second.status_code == 202
    assert second.json()["run_id"] == run_id
    assert second.json()["disposition"] == "deduplicated"

    # An unsigned delivery is refused outright.
    forged = httpx.post(
        f"{base}/_workflow/webhook/orders.placed",
        content=body,
        headers={"X-Signature": "0" * 64, "content-type": "application/json"},
    )
    assert forged.status_code in (400, 401, 403)
