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
from reflex.workflow.testing import WorkflowTestHarness

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


async def test_the_harness_starts_a_webhook_root_directly(paid_workflow):
    """In a test, the author is the provider; no HTTP required.

    The trigger gate exists so a webhook-only root is unreachable from the
    browser. Applying it to the harness made webhook workflows untestable
    except by crafting signed requests, which is not what a unit test wants.
    """
    async with WorkflowTestHarness(paid_workflow) as harness:
        result = await harness.start(
            paid_workflow.on_paid(Payment(id="pi_9", amount=700))
        )
        assert result.disposition == "started"
        assert result.run_id is not None
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.COMPLETED


async def test_a_payload_that_cannot_be_mapped_is_refused(
    monkeypatch, forked_registration_context
):
    """A body that cannot fill the root's parameters is a 400, not a doomed run.

    A root taking several named parameters can only be filled from a JSON
    object. Admitting a run from an array or a scalar dropped the payload
    silently and produced a run that failed on its first step, with the
    provider told nothing -- it received a 202 and moved on.
    """
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", SECRET)

    class MultiArg(rx.State):
        __workflow__ = WorkflowConfig(id="ingress.multiarg")
        seen: str = ""

        @rx.event(
            durable=True,
            effect="none",
            trigger=webhook(
                "multi",
                verify=hmac_signature(
                    secret_env="STRIPE_WEBHOOK_SECRET", header="X-Signature"
                ),
            ),
        )
        def on_event(self, first: str, second: int):
            """Take two named fields.

            Args:
                first: The first field.
                second: The second field.
            """
            self.seen = f"{first}:{second}"

    runtime = WorkflowRuntime(MemoryRunStore())
    runtime.register(MultiArg)
    await runtime.startup(start_worker=False)
    app = Starlette(
        routes=[Route(WEBHOOK_ROUTE, webhook_endpoint(runtime), methods=["POST"])]
    )
    try:
        with TestClient(app) as client:
            body = json.dumps([1, 2, 3]).encode()
            refused = client.post(
                "/_workflow/webhook/multi",
                content=body,
                headers={
                    "X-Signature": _sign(body),
                    "content-type": "application/json",
                },
            )
            assert refused.status_code == 400
            assert "object" in refused.json()["error"]

            good = json.dumps({"first": "a", "second": 2}).encode()
            accepted = client.post(
                "/_workflow/webhook/multi",
                content=good,
                headers={
                    "X-Signature": _sign(good),
                    "content-type": "application/json",
                },
            )
            assert accepted.status_code == 202, accepted.text
    finally:
        await runtime.shutdown()


class Invoices(rx.State):
    """One workflow serving two lifecycle topics for the same object."""

    __workflow__ = WorkflowConfig(id="ingress.invoices")
    outcome: str = ""

    @rx.event(
        durable=True,
        effect="none",
        trigger=webhook(
            "invoice_failed",
            dedupe_by="id",
            verify=hmac_signature(
                secret_env="STRIPE_WEBHOOK_SECRET", header="X-Signature"
            ),
        ),
    )
    def on_failed(self, id: str):
        """Record a failed invoice.

        Args:
            id: The invoice identifier.

        Returns:
            Completion.
        """
        self.outcome = "failed"
        return rx.complete(result={"invoice": id, "outcome": "failed"})

    @rx.event(
        durable=True,
        effect="none",
        trigger=webhook(
            "invoice_paid",
            dedupe_by="id",
            verify=hmac_signature(
                secret_env="STRIPE_WEBHOOK_SECRET", header="X-Signature"
            ),
        ),
    )
    def on_paid(self, id: str):
        """Record a paid invoice.

        Args:
            id: The invoice identifier.

        Returns:
            Completion.
        """
        self.outcome = "paid"
        return rx.complete(result={"invoice": id, "outcome": "paid"})


async def test_two_topics_sharing_a_dedupe_value_are_separate_events(
    monkeypatch, forked_registration_context
):
    """A provider numbers events per object, not per topic.

    `invoice_failed` and `invoice_paid` for one invoice carry the same id.
    Deduplicating on that alone makes the payment a redelivery of the failure
    and drops it, which is the one outcome a billing workflow must never have.
    """
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", SECRET)
    runtime = WorkflowRuntime(MemoryRunStore())
    runtime.register(Invoices)
    await runtime.startup(start_worker=False)
    app = Starlette(
        routes=[Route(WEBHOOK_ROUTE, webhook_endpoint(runtime), methods=["POST"])]
    )

    started: list[str] = []
    dispositions: list[str] = []
    with TestClient(app) as client:
        for topic in ("invoice_failed", "invoice_paid"):
            body = json.dumps({"id": "inv_1"}).encode()
            response = client.post(
                f"/_workflow/webhook/{topic}",
                content=body,
                headers={"x-signature": _sign(body)},
            )
            assert response.status_code == 202, response.text
            started.append(response.json()["run_id"])
            dispositions.append(response.json()["disposition"])

    assert dispositions == ["started", "started"], (
        "the payment was taken for a redelivery of the failure"
    )
    assert started[0] != started[1], "both lifecycle events must have their own run"
    await runtime.shutdown()


async def test_a_redelivery_admitted_under_the_old_key_still_deduplicates(
    monkeypatch, forked_registration_context
):
    """Changing the key format must not replay every event admitted before it.

    A run that exists under the unqualified key the older release wrote is
    still that event's run. Matching the old spelling on the way in is what
    keeps the provider's next redelivery from starting it a second time.
    """
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", SECRET)
    store = MemoryRunStore()
    runtime = WorkflowRuntime(store)
    runtime.register(Invoices)
    await runtime.startup(start_worker=False)

    # Exactly what the previous release recorded: the bare provider value.
    legacy = await runtime.kernel.start(
        Invoices.on_failed("inv_2"),
        request_key="inv_2",
        trigger_kind="webhook",
    )
    assert legacy.disposition == "started"

    app = Starlette(
        routes=[Route(WEBHOOK_ROUTE, webhook_endpoint(runtime), methods=["POST"])]
    )
    with TestClient(app) as client:
        body = json.dumps({"id": "inv_2"}).encode()
        response = client.post(
            "/_workflow/webhook/invoice_failed",
            content=body,
            headers={"x-signature": _sign(body)},
        )
    assert response.status_code == 202, response.text
    assert response.json()["disposition"] == "deduplicated"
    assert response.json()["run_id"] == legacy.run_id
    await runtime.shutdown()


async def test_a_legacy_key_only_matches_the_root_that_wrote_it(
    monkeypatch, forked_registration_context
):
    """The compatibility path must not undo the fix it exists to soften.

    The old key format was the bare provider value, which is exactly what
    collided across topics. Matching it without checking which root the
    existing run started lets `invoice_paid` deduplicate against a legacy
    `invoice_failed` run -- the same lost payment, arriving through the
    upgrade path instead.
    """
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", SECRET)
    runtime = WorkflowRuntime(MemoryRunStore())
    runtime.register(Invoices)
    await runtime.startup(start_worker=False)

    legacy = await runtime.kernel.start(
        Invoices.on_failed("inv_3"),
        request_key="inv_3",
        trigger_kind="webhook",
    )
    assert legacy.disposition == "started"

    app = Starlette(
        routes=[Route(WEBHOOK_ROUTE, webhook_endpoint(runtime), methods=["POST"])]
    )
    with TestClient(app) as client:
        body = json.dumps({"id": "inv_3"}).encode()
        paid = client.post(
            "/_workflow/webhook/invoice_paid",
            content=body,
            headers={"x-signature": _sign(body)},
        )
    assert paid.status_code == 202, paid.text
    assert paid.json()["disposition"] == "started", (
        "the payment deduplicated against a legacy failure run"
    )
    assert paid.json()["run_id"] != legacy.run_id
    await runtime.shutdown()


class Ships(rx.State):
    """A workflow whose provider identifies deliveries by header."""

    __workflow__ = WorkflowConfig(id="ingress.ships")

    @rx.event(
        durable=True,
        effect="none",
        trigger=webhook(
            "shipped",
            dedupe_by="header:X-GitHub-Delivery",
            verify=hmac_signature(
                secret_env="STRIPE_WEBHOOK_SECRET", header="X-Signature"
            ),
        ),
    )
    def on_shipped(self, sha: str):
        """Record a shipment.

        Args:
            sha: The commit that shipped.

        Returns:
            Completion.
        """
        return rx.complete(result=sha)


async def test_header_identity_separates_deliveries_the_payload_cannot(
    monkeypatch, forked_registration_context
):
    """GitHub's identity is the delivery GUID header, not any payload field.

    Two pushes of the same commit are two events with two GUIDs; keyed on a
    payload field they collapsed into one run and the second delivery was
    silently dropped. Keyed on the header, distinct GUIDs are distinct runs
    and a true redelivery -- same GUID -- still deduplicates.
    """
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", SECRET)
    runtime = WorkflowRuntime(MemoryRunStore())
    runtime.register(Ships)
    await runtime.startup(start_worker=False)
    app = Starlette(
        routes=[Route(WEBHOOK_ROUTE, webhook_endpoint(runtime), methods=["POST"])]
    )
    body = json.dumps({"sha": "abc123"}).encode()

    with TestClient(app) as client:
        first = client.post(
            "/_workflow/webhook/shipped",
            content=body,
            headers={"x-signature": _sign(body), "x-github-delivery": "guid-1"},
        )
        second = client.post(
            "/_workflow/webhook/shipped",
            content=body,
            headers={"x-signature": _sign(body), "x-github-delivery": "guid-2"},
        )
        redelivered = client.post(
            "/_workflow/webhook/shipped",
            content=body,
            headers={"x-signature": _sign(body), "x-github-delivery": "guid-1"},
        )
    assert first.json()["disposition"] == "started"
    assert second.json()["disposition"] == "started", (
        "a distinct delivery GUID is a distinct event"
    )
    assert redelivered.json()["disposition"] == "deduplicated"
    assert redelivered.json()["run_id"] == first.json()["run_id"]
    await runtime.shutdown()


async def test_a_delivery_missing_its_configured_identity_is_refused(
    monkeypatch, forked_registration_context
):
    """Configured dedupe that cannot be extracted must not silently vanish.

    Admitting anyway means every redelivery of this event executes again --
    the exact thing dedupe_by was configured to prevent -- and nobody is
    told. A 400 naming the missing field is a config problem someone sees.
    """
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", SECRET)
    runtime = WorkflowRuntime(MemoryRunStore())
    runtime.register(Ships)
    runtime.register(Invoices)
    await runtime.startup(start_worker=False)
    app = Starlette(
        routes=[Route(WEBHOOK_ROUTE, webhook_endpoint(runtime), methods=["POST"])]
    )
    with TestClient(app) as client:
        body = json.dumps({"sha": "abc123"}).encode()
        no_header = client.post(
            "/_workflow/webhook/shipped",
            content=body,
            headers={"x-signature": _sign(body)},
        )
        assert no_header.status_code == 400, no_header.text
        assert "X-GitHub-Delivery" in no_header.json()["error"]

        body = json.dumps({"amount": 5}).encode()
        no_field = client.post(
            "/_workflow/webhook/invoice_paid",
            content=body,
            headers={"x-signature": _sign(body)},
        )
        assert no_field.status_code == 400, no_field.text
        assert "'id'" in no_field.json()["error"]
    await runtime.shutdown()


async def test_github_form_encoded_deliveries_are_understood(
    monkeypatch, forked_registration_context
):
    """GitHub can be configured to send payload=<json> as a form body.

    The signature covers the raw form bytes and was already verified against
    them; only the JSON extraction changes. Refusing this mode as 'not JSON'
    forced users to reconfigure the provider to learn what was wrong.
    """
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", SECRET)
    runtime = WorkflowRuntime(MemoryRunStore())
    runtime.register(Ships)
    await runtime.startup(start_worker=False)
    app = Starlette(
        routes=[Route(WEBHOOK_ROUTE, webhook_endpoint(runtime), methods=["POST"])]
    )
    from urllib.parse import urlencode

    body = urlencode({"payload": json.dumps({"sha": "abc123"})}).encode()
    with TestClient(app) as client:
        response = client.post(
            "/_workflow/webhook/shipped",
            content=body,
            headers={
                "x-signature": _sign(body),
                "x-github-delivery": "guid-form-1",
                "content-type": "application/x-www-form-urlencoded",
            },
        )
    assert response.status_code == 202, response.text
    assert response.json()["disposition"] == "started"
    await runtime.kernel.run_until_idle()
    snapshot = await runtime.kernel.get_run(response.json()["run_id"])
    assert snapshot is not None
    assert snapshot.result == "abc123", (
        "the wrapped JSON is the payload, and a parameter annotated str "
        "receives its field, not the enclosing object"
    )
    await runtime.shutdown()


class Fulfil(rx.State):
    """A workflow whose channel is fed by a correlated provider webhook."""

    __workflow__ = WorkflowConfig(id="ingress.fulfil")

    shipped = rx.Signal(
        trigger=webhook(
            "carrier_shipped",
            dedupe_by="event_id",
            correlate_by="order_id",
            verify=hmac_signature(
                secret_env="STRIPE_WEBHOOK_SECRET", header="X-Signature"
            ),
        )
    )

    @rx.event(durable=True, trigger=manual(), effect="none")
    def begin(self):
        """Wait for the shipment.

        Returns:
            The wait.
        """
        return rx.wait_for(Fulfil.shipped, then=Fulfil.close, timeout=rx.never)

    @rx.event(durable=True, effect="none")
    def close(self, shipment):
        """Finish with the shipment.

        Args:
            shipment: The delivered payload.

        Returns:
            Completion.
        """
        return rx.complete(result=shipment)


async def test_a_correlated_webhook_reaches_its_run_exactly_once(
    monkeypatch, forked_registration_context
):
    """Early delivery, three sends, late run: one signal, over real HTTP.

    Args:
        monkeypatch: Used to install the webhook secret.
        forked_registration_context: Isolated state registry.
    """
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", SECRET)
    runtime = WorkflowRuntime(MemoryRunStore())
    runtime.register(Fulfil)
    await runtime.startup(start_worker=False)
    app = Starlette(
        routes=[Route(WEBHOOK_ROUTE, webhook_endpoint(runtime), methods=["POST"])]
    )
    body = json.dumps({
        "event_id": "evt_7",
        "order_id": "ord_7",
        "parcel": "P-7",
    }).encode()
    with TestClient(app) as client:
        first = client.post(
            "/_workflow/webhook/carrier_shipped",
            content=body,
            headers={"x-signature": _sign(body)},
        )
        assert first.status_code == 202, first.text
        assert first.json()["disposition"] == "parked"
        for _ in range(2):
            again = client.post(
                "/_workflow/webhook/carrier_shipped",
                content=body,
                headers={"x-signature": _sign(body)},
            )
            assert again.status_code == 202
            assert again.json()["disposition"] == "duplicate"

        keyless = json.dumps({"event_id": "evt_8", "parcel": "P-8"}).encode()
        refused = client.post(
            "/_workflow/webhook/carrier_shipped",
            content=keyless,
            headers={"x-signature": _sign(keyless)},
        )
        assert refused.status_code == 400
        assert "order_id" in refused.json()["error"]

    started = await runtime.kernel.start(Fulfil.begin(), request_key="ord_7")
    assert started.run_id is not None
    await runtime.kernel.run_until_idle()
    snapshot = await runtime.kernel.get_run(started.run_id)
    assert snapshot is not None
    assert snapshot.status is RunStatus.COMPLETED
    assert snapshot.result == {
        "event_id": "evt_7",
        "order_id": "ord_7",
        "parcel": "P-7",
    }
    parked = await runtime.kernel._store.list_parked()  # pyright: ignore[reportPrivateUsage]
    assert len(parked) == 1
    assert parked[0].status.value == "DELIVERED"
    await runtime.shutdown()


def test_a_channel_topic_cannot_collide_with_a_root_topic(
    monkeypatch, forked_registration_context
):
    """One topic, one target: a root and a channel cannot share it.

    Args:
        monkeypatch: Used to install the webhook secret.
        forked_registration_context: Isolated state registry.
    """
    from reflex.workflow.definition import compile_workflow
    from reflex.workflow.ingress import collect_webhook_routes

    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", SECRET)

    class Both(rx.State):
        __workflow__ = WorkflowConfig(id="ingress.both")

        colliding = rx.Signal(
            trigger=webhook(
                "shipped",
                dedupe_by="id",
                correlate_by="order",
                verify=hmac_signature(
                    secret_env="STRIPE_WEBHOOK_SECRET", header="X-Signature"
                ),
            )
        )

        @rx.event(
            durable=True,
            effect="none",
            trigger=webhook(
                "shipped",
                verify=hmac_signature(
                    secret_env="STRIPE_WEBHOOK_SECRET", header="X-Signature"
                ),
            ),
        )
        def on_shipped(self, event: dict):
            """Claim the same topic as the channel.

            Args:
                event: The payload.
            """

    with pytest.raises(WorkflowDefinitionError, match="shipped"):
        collect_webhook_routes((compile_workflow(Both),))
