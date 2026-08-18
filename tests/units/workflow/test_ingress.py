"""Tests for the webhook ingress endpoint."""

import hmac
import json

import pytest
from pydantic import BaseModel
from reflex_base.utils.exceptions import WorkflowDefinitionError
from reflex_base.workflow import WorkflowConfig, hmac_signature, manual, webhook
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.testclient import TestClient

import reflex as rx
from reflex.workflow.definition import compile_workflow
from reflex.workflow.ingress import (
    WEBHOOK_ROUTE,
    collect_webhook_routes,
    webhook_endpoint,
)
from reflex.workflow.records import RunStatus
from reflex.workflow.runtime import WorkflowRuntime
from reflex.workflow.store import MemoryRunStore

SECRET = "whsec_test"


class Payment(BaseModel):
    """Typed webhook payload."""

    id: str
    amount: int


def _sign(body: bytes) -> str:
    """Sign a body the way the provider would.

    Args:
        body: The exact bytes that will be sent.

    Returns:
        The hex digest to put in the signature header.
    """
    return hmac.new(SECRET.encode(), body, "sha256").hexdigest()


@pytest.fixture
def paid_workflow(monkeypatch, forked_registration_context):
    """A workflow with one verified webhook root.

    Args:
        monkeypatch: Fixture used to set the shared secret.
        forked_registration_context: Isolates state registration.

    Returns:
        The workflow class.
    """
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", SECRET)

    class PaidFlow(rx.State):
        __workflow__ = WorkflowConfig(id="ingress.paid")
        payment_id: str = ""
        amount: int = 0

        @rx.event(
            durable=True,
            effect="none",
            trigger=webhook(
                "stripe.payment_succeeded",
                model=Payment,
                verify=hmac_signature(
                    secret_env="STRIPE_WEBHOOK_SECRET", header="X-Signature"
                ),
                dedupe_by="id",
            ),
        )
        def on_paid(self, payment: Payment):
            self.payment_id = payment.id
            self.amount = payment.amount

    return PaidFlow


@pytest.fixture
async def client(paid_workflow):
    """A test client wired to the webhook endpoint of a live runtime.

    Args:
        paid_workflow: The registered workflow class.

    Yields:
        The client and the runtime behind it.
    """
    runtime = WorkflowRuntime(MemoryRunStore())
    runtime.register(paid_workflow)
    await runtime.startup(start_worker=False)
    app = Starlette(
        routes=[Route(WEBHOOK_ROUTE, webhook_endpoint(runtime), methods=["POST"])]
    )
    with TestClient(app) as test_client:
        yield test_client, runtime
    await runtime.shutdown()


async def test_signed_webhook_starts_a_run(client):
    test_client, runtime = client
    body = json.dumps({"id": "pay_1", "amount": 4200}).encode()
    response = test_client.post(
        "/_workflow/webhook/stripe.payment_succeeded",
        content=body,
        headers={"X-Signature": _sign(body)},
    )
    assert response.status_code == 202
    assert response.json()["disposition"] == "started"
    run_id = response.json()["run_id"]

    await runtime.kernel.run_until_idle()
    snapshot = await runtime.kernel.get_run(run_id)
    assert snapshot is not None
    assert snapshot.status is RunStatus.COMPLETED
    assert snapshot.state == {"payment_id": "pay_1", "amount": 4200}


async def test_redelivery_is_deduplicated(client):
    test_client, runtime = client
    body = json.dumps({"id": "pay_2", "amount": 1}).encode()
    headers = {"X-Signature": _sign(body)}
    first = test_client.post(
        "/_workflow/webhook/stripe.payment_succeeded", content=body, headers=headers
    )
    second = test_client.post(
        "/_workflow/webhook/stripe.payment_succeeded", content=body, headers=headers
    )
    assert first.json()["disposition"] == "started"
    assert second.json()["disposition"] == "deduplicated"
    assert second.json()["run_id"] == first.json()["run_id"]
    assert len(await runtime.kernel.list_runs()) == 1


async def test_bad_signature_is_rejected_and_admits_nothing(client):
    test_client, runtime = client
    body = json.dumps({"id": "pay_3", "amount": 1}).encode()
    response = test_client.post(
        "/_workflow/webhook/stripe.payment_succeeded",
        content=body,
        headers={"X-Signature": "deadbeef"},
    )
    assert response.status_code == 401
    assert await runtime.kernel.list_runs() == ()


async def test_missing_signature_is_rejected(client):
    test_client, runtime = client
    body = json.dumps({"id": "pay_4", "amount": 1}).encode()
    response = test_client.post(
        "/_workflow/webhook/stripe.payment_succeeded", content=body
    )
    assert response.status_code == 401
    assert await runtime.kernel.list_runs() == ()


async def test_payload_not_matching_the_model_is_rejected(client):
    test_client, runtime = client
    body = json.dumps({"id": "pay_5"}).encode()
    response = test_client.post(
        "/_workflow/webhook/stripe.payment_succeeded",
        content=body,
        headers={"X-Signature": _sign(body)},
    )
    assert response.status_code == 400
    assert await runtime.kernel.list_runs() == ()


async def test_malformed_json_is_rejected(client):
    test_client, runtime = client
    body = b"{not json"
    response = test_client.post(
        "/_workflow/webhook/stripe.payment_succeeded",
        content=body,
        headers={"X-Signature": _sign(body)},
    )
    assert response.status_code == 400
    assert await runtime.kernel.list_runs() == ()


async def test_unknown_topic_is_not_found(client):
    test_client, runtime = client
    body = b"{}"
    response = test_client.post(
        "/_workflow/webhook/nope.nothing",
        content=body,
        headers={"X-Signature": _sign(body)},
    )
    assert response.status_code == 404
    assert await runtime.kernel.list_runs() == ()


def test_duplicate_topics_are_rejected(forked_registration_context, monkeypatch):
    """Two roots on one topic would make delivery ambiguous."""
    monkeypatch.setenv("S", SECRET)
    verifier = hmac_signature(secret_env="S", header="X-Signature")

    class FirstClaim(rx.State):
        __workflow__ = WorkflowConfig(id="ingress.first")

        @rx.event(durable=True, effect="none", trigger=webhook("dup", verify=verifier))
        def go(self):
            pass

    class SecondClaim(rx.State):
        __workflow__ = WorkflowConfig(id="ingress.second")

        @rx.event(durable=True, effect="none", trigger=webhook("dup", verify=verifier))
        def go(self):
            pass

    definitions = (compile_workflow(FirstClaim), compile_workflow(SecondClaim))
    with pytest.raises(WorkflowDefinitionError, match="claimed by both"):
        collect_webhook_routes(definitions)


async def test_webhook_root_cannot_be_started_by_application_code(paid_workflow):
    """A provider-triggered root is not a manual root."""
    from reflex_base.utils.exceptions import WorkflowRuntimeError

    runtime = WorkflowRuntime(MemoryRunStore())
    runtime.register(paid_workflow)
    await runtime.startup(start_worker=False)
    try:
        with pytest.raises(WorkflowRuntimeError, match="cannot be started here"):
            await runtime.kernel.start(paid_workflow.on_paid(Payment(id="x", amount=1)))
    finally:
        await runtime.shutdown()


def test_manual_root_is_not_reachable_over_http(
    forked_registration_context, monkeypatch
):
    """A manual root has no webhook route at all."""

    class ManualOnly(rx.State):
        __workflow__ = WorkflowConfig(id="ingress.manual_only")

        @rx.event(durable=True, effect="none", trigger=manual())
        def go(self):
            pass

    assert collect_webhook_routes((compile_workflow(ManualOnly),)) == {}
