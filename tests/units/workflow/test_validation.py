"""One validation semantics at every boundary that accepts run data.

The acceptance bar, per boundary: an invalid payload is refused before
anything exists (webhook and HTTP -> 400 with zero runs; Python starts and
signals -> an exception at the call site), and dispatch -- judging payloads
recorded before a redeploy -- suspends without consuming retry attempts.
"""

import hashlib
import hmac as hmac_mod
import json

import pytest
from pydantic import BaseModel
from reflex_base.utils.exceptions import WorkflowDefinitionError
from reflex_base.workflow import Signal, WorkflowConfig, hmac_signature, manual, webhook
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.testclient import TestClient

import reflex as rx
from reflex.workflow.definition import channels_of, compile_workflow
from reflex.workflow.ingress import WEBHOOK_ROUTE, webhook_endpoint
from reflex.workflow.records import RunQuery, RunStatus
from reflex.workflow.runtime import WorkflowRuntime
from reflex.workflow.store import MemoryRunStore
from reflex.workflow.testing import WorkflowTestHarness

SECRET = "whsec_validation"


class Shipment(BaseModel):
    """A provider event with a coercible field and a defaulted one."""

    order_id: str
    parcels: int
    carrier: str = "ups"


def _sign(body: bytes) -> str:
    """Sign a body the way the HMAC verifier expects.

    Args:
        body: The raw request body.

    Returns:
        The hex signature.
    """
    return hmac_mod.new(SECRET.encode(), body, hashlib.sha256).hexdigest()


def _shipping_flow():
    """Build a webhook workflow whose root declares a payload model.

    Returns:
        The workflow class.
    """

    class Shipping(rx.State):
        __workflow__ = WorkflowConfig(id="validation.shipping")
        seen: str = ""

        @rx.event(
            durable=True,
            effect="none",
            trigger=webhook(
                "shipped",
                model=Shipment,
                verify=hmac_signature(
                    secret_env="VALIDATION_WEBHOOK_SECRET", header="X-Signature"
                ),
            ),
        )
        def on_shipped(self, event: dict):
            """Record the canonical event.

            Args:
                event: The validated payload.

            Returns:
                Completion.
            """
            return rx.complete(result=event)

    return Shipping


async def _webhook_client(monkeypatch, flow):
    """Stand up a runtime and a webhook test client for one workflow.

    Args:
        monkeypatch: Used to install the webhook secret.
        flow: The workflow class to register.

    Returns:
        The runtime and the entered test client.
    """
    monkeypatch.setenv("VALIDATION_WEBHOOK_SECRET", SECRET)
    runtime = WorkflowRuntime(MemoryRunStore())
    runtime.register(flow)
    await runtime.startup(start_worker=False)
    app = Starlette(
        routes=[Route(WEBHOOK_ROUTE, webhook_endpoint(runtime), methods=["POST"])]
    )
    return runtime, TestClient(app)


async def test_an_invalid_webhook_payload_is_refused_with_zero_runs(
    monkeypatch, forked_registration_context
):
    """The acceptance bar itself: 400 out, nothing admitted.

    Args:
        monkeypatch: Used to install the webhook secret.
        forked_registration_context: Isolated state registry.
    """
    runtime, client = await _webhook_client(monkeypatch, _shipping_flow())
    with client:
        body = json.dumps({"order_id": "o1", "parcels": "not-a-number"}).encode()
        response = client.post(
            "/_workflow/webhook/shipped",
            content=body,
            headers={"x-signature": _sign(body)},
        )
    assert response.status_code == 400, response.text
    assert await runtime.kernel._store.count_runs(RunQuery()) == 0  # pyright: ignore[reportPrivateUsage]
    await runtime.shutdown()


async def test_the_validated_canonical_payload_is_what_goes_onward(
    monkeypatch, forked_registration_context
):
    """Validation must change what the handler receives, not just gatekeep.

    "5" coerces to 5 and the absent carrier fills with its default; a
    boundary that validated and then forwarded the raw payload dropped both,
    so the handler saw something subtly different from what the model
    promised.

    Args:
        monkeypatch: Used to install the webhook secret.
        forked_registration_context: Isolated state registry.
    """
    runtime, client = await _webhook_client(monkeypatch, _shipping_flow())
    with client:
        body = json.dumps({"order_id": "o1", "parcels": "5"}).encode()
        response = client.post(
            "/_workflow/webhook/shipped",
            content=body,
            headers={"x-signature": _sign(body)},
        )
        assert response.status_code == 202, response.text
        run_id = response.json()["run_id"]
        await runtime.kernel.run_until_idle()
    snapshot = await runtime.kernel.get_run(run_id)
    assert snapshot is not None
    assert snapshot.result == {"order_id": "o1", "parcels": 5, "carrier": "ups"}
    await runtime.shutdown()


async def test_a_missing_webhook_argument_is_refused_not_defaulted_to_none(
    monkeypatch, forked_registration_context
):
    """A multi-parameter root refuses an object that cannot fill it.

    Absent fields used to arrive as None and fail inside the handler, on a
    run that already existed and burned attempts on an unfixable payload.

    Args:
        monkeypatch: Used to install the webhook secret.
        forked_registration_context: Isolated state registry.
    """

    class TwoArg(rx.State):
        __workflow__ = WorkflowConfig(id="validation.twoarg")

        @rx.event(
            durable=True,
            effect="none",
            trigger=webhook(
                "pair",
                verify=hmac_signature(
                    secret_env="VALIDATION_WEBHOOK_SECRET", header="X-Signature"
                ),
            ),
        )
        def on_pair(self, left: str, right: str):
            """Take two named fields.

            Args:
                left: One field.
                right: The other.

            Returns:
                Completion.
            """
            return rx.complete(result=[left, right])

    runtime, client = await _webhook_client(monkeypatch, TwoArg)
    with client:
        body = json.dumps({"left": "only"}).encode()
        response = client.post(
            "/_workflow/webhook/pair",
            content=body,
            headers={"x-signature": _sign(body)},
        )
    assert response.status_code == 400, response.text
    assert "right" in response.json()["error"]
    assert await runtime.kernel._store.count_runs(RunQuery()) == 0  # pyright: ignore[reportPrivateUsage]
    await runtime.shutdown()


def test_a_single_typed_parameter_receives_its_field_not_the_object(
    forked_registration_context,
):
    """``def go(self, order_id: str)`` gets the string, never the dict.

    Before types were consulted, the whole event object landed in the lone
    parameter and nothing ever said so.

    Args:
        forked_registration_context: Isolated state registry.
    """
    from reflex.workflow.ingress import _root_args

    class OneField(rx.State):
        __workflow__ = WorkflowConfig(id="validation.onefield")

        @rx.event(durable=True, effect="none", trigger=manual())
        def go(self, order_id: str):
            """Take one typed field.

            Args:
                order_id: The order.
            """

    defn = compile_workflow(OneField)
    handler = next(iter(defn.handlers.values()))
    assert _root_args(handler, {"order_id": "o1", "noise": 1}) == {"order_id": "o1"}
    assert _root_args(handler, "o1") == {"order_id": "o1"}


async def test_a_python_start_with_bad_arguments_creates_nothing(
    forked_registration_context,
):
    """The Python boundary refuses at the call site, like every other.

    Args:
        forked_registration_context: Isolated state registry.
    """

    class Typed(rx.State):
        __workflow__ = WorkflowConfig(id="validation.typed")

        @rx.event(durable=True, effect="none", trigger=manual())
        def begin(self, count: int):
            """Start with a typed argument.

            Args:
                count: A number.

            Returns:
                Completion.
            """
            return rx.complete(result=count)

    store = MemoryRunStore()
    async with WorkflowTestHarness(Typed, store=store) as harness:
        with pytest.raises(WorkflowDefinitionError, match="count"):
            await harness.start(
                Typed.begin("not-a-number")  # pyright: ignore[reportArgumentType]
            )
        with pytest.raises(WorkflowDefinitionError, match="missing required"):
            await harness.start(Typed.begin())
        assert await store.count_runs(RunQuery()) == 0
        result = await harness.start(Typed.begin(3))
        assert result.disposition == "started"


async def test_an_unknown_channel_is_rejected_at_the_sender(
    forked_registration_context,
):
    """A typo'd channel must fail the sender, not buffer forever.

    Args:
        forked_registration_context: Isolated state registry.
    """
    from reflex_base.workflow import ChannelDelivery

    class Waits(rx.State):
        __workflow__ = WorkflowConfig(id="validation.waits")
        approved = Signal()

        @rx.event(durable=True, effect="none", trigger=manual())
        def begin(self):
            """Wait for approval.

            Returns:
                The wait.
            """
            return rx.wait_for(Waits.approved, then=Waits.done, timeout=rx.never)

        @rx.event(durable=True, effect="none")
        def done(self, decision):
            """Finish.

            Args:
                decision: The delivered payload.

            Returns:
                Completion.
            """
            return rx.complete(result=decision)

    async with WorkflowTestHarness(Waits) as harness:
        result = await harness.start(Waits.begin())
        assert result.run_id is not None
        await harness.run_until_idle()
        with pytest.raises(WorkflowDefinitionError, match="no_such_channel"):
            await harness.kernel.signal(
                result.run_id, ChannelDelivery(channel="no_such_channel", payload=None)
            )
        assert (
            await harness.kernel.signal(result.run_id, Waits.approved(None))
            == "resolved"
        )


async def test_channel_payloads_are_validated_on_every_route_in(
    forked_registration_context,
):
    """A raw ChannelDelivery cannot smuggle past the declared model.

    Signal.__call__ validates, but approvals and future HTTP senders build
    ChannelDelivery directly; the kernel is where every route converges, so
    the kernel enforces the model and forwards the canonical form.

    Args:
        forked_registration_context: Isolated state registry.
    """
    from reflex_base.workflow import ChannelDelivery

    class Modeled(rx.State):
        __workflow__ = WorkflowConfig(id="validation.modeled")
        shipped = Signal(Shipment)

        @rx.event(durable=True, effect="none", trigger=manual())
        def begin(self):
            """Wait for the shipment.

            Returns:
                The wait.
            """
            return rx.wait_for(Modeled.shipped, then=Modeled.done, timeout=rx.never)

        @rx.event(durable=True, effect="none")
        def done(self, shipment):
            """Finish with the delivered payload.

            Args:
                shipment: The canonical shipment.

            Returns:
                Completion.
            """
            return rx.complete(result=shipment)

    async with WorkflowTestHarness(Modeled) as harness:
        result = await harness.start(Modeled.begin())
        assert result.run_id is not None
        await harness.run_until_idle()
        with pytest.raises(WorkflowDefinitionError, match="Shipment"):
            await harness.kernel.signal(
                result.run_id,
                ChannelDelivery(channel="shipped", payload={"parcels": "x"}),
            )
        disposition = await harness.kernel.signal(
            result.run_id,
            ChannelDelivery(
                channel="shipped", payload={"order_id": "o1", "parcels": "2"}
            ),
        )
        assert disposition == "resolved"
        await harness.run_until_idle()
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.result == {"order_id": "o1", "parcels": 2, "carrier": "ups"}


def test_two_declarations_sharing_a_channel_name_refuse_to_compile(
    forked_registration_context,
):
    """A delivery could not say which declaration it means.

    Args:
        forked_registration_context: Isolated state registry.
    """

    class Ambiguous(rx.State):
        __workflow__ = WorkflowConfig(id="validation.ambiguous")
        first = Signal(name="decision")
        second = Signal(name="decision")

        @rx.event(durable=True, effect="none", trigger=manual())
        def begin(self):
            """Start."""

    with pytest.raises(WorkflowDefinitionError, match="decision"):
        channels_of(Ambiguous)


def test_a_schedule_root_with_required_parameters_refuses_to_compile(
    forked_registration_context,
):
    """A schedule fires with no caller; every occurrence would suspend.

    Args:
        forked_registration_context: Isolated state registry.
    """
    from reflex_base.workflow import schedule

    class Nightly(rx.State):
        __workflow__ = WorkflowConfig(id="validation.nightly")

        @rx.event(durable=True, effect="none", trigger=schedule("0 3 * * *"))
        def run_report(self, region: str):
            """Demand an argument no schedule can supply.

            Args:
                region: Unfillable.
            """

    with pytest.raises(WorkflowDefinitionError, match="region"):
        compile_workflow(Nightly)


async def test_a_retyped_parameter_suspends_without_consuming_attempts(
    forked_registration_context,
):
    """Schema incompatibility is a redeploy problem, never a retry burn.

    The payload was valid when recorded; the code changed underneath it.
    Retrying cannot change what the code declares, so the run suspends with
    the argument named and its attempt budget untouched.

    Args:
        forked_registration_context: Isolated state registry.
    """
    store = MemoryRunStore()

    def _first():
        class Retyped(rx.State):
            __workflow__ = WorkflowConfig(id="validation.retyped")

            @rx.event(durable=True, effect="none", trigger=manual())
            def begin(self):
                """Schedule the finish with an int.

                Returns:
                    The deferral.
                """
                return rx.after("1h", Retyped.finish(5))

            @rx.event(durable=True, effect="read")
            def finish(self, count: int):
                """Finish with a count.

                Args:
                    count: The recorded number.
                """

        return Retyped

    first_cls = _first()
    async with WorkflowTestHarness(first_cls, store=store) as harness:
        result = await harness.start(first_cls.begin())
        assert result.run_id is not None
        run_id, resume_at = result.run_id, harness.now

    class Retyped(rx.State):
        __workflow__ = WorkflowConfig(id="validation.retyped")

        @rx.event(durable=True, effect="none", trigger=manual())
        def begin(self):
            """Unchanged root.

            Returns:
                The deferral.
            """
            return rx.after(
                "1h",
                Retyped.finish(5),  # pyright: ignore[reportArgumentType]
            )

        @rx.event(durable=True, effect="read")
        def finish(self, count: Shipment):
            """Now demand a model where an int was recorded.

            Args:
                count: The retyped parameter.
            """

    async with WorkflowTestHarness(
        Retyped, store=store, start_time=resume_at + 3600
    ) as harness:
        await harness.run_until_idle()
        snapshot = await harness.get_run(run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.NEEDS_ATTENTION
        assert snapshot.error is not None
        assert snapshot.error["reason"] == "incompatible_payload"
        assert "count" in snapshot.error["detail"]
        steps = await store.get_steps(run_id)
        pending = [s for s in steps if s.handler_id.endswith("finish")]
        assert pending
        assert pending[0].attempts == 0, (
            "suspension must not consume the attempt budget"
        )


async def test_python_by_key_lookup_and_signal(forked_registration_context):
    """The Python forms of business-key addressing mirror the HTTP ones.

    Args:
        forked_registration_context: Isolated state registry.
    """

    class Keyed(rx.State):
        __workflow__ = WorkflowConfig(id="validation.keyed")
        go = Signal()

        @rx.event(durable=True, effect="none", trigger=manual())
        def begin(self):
            """Wait for the go signal.

            Returns:
                The wait.
            """
            return rx.wait_for(Keyed.go, then=Keyed.done, timeout=rx.never)

        @rx.event(durable=True, effect="none")
        def done(self, payload):
            """Finish.

            Args:
                payload: The delivered payload.

            Returns:
                Completion.
            """
            return rx.complete(result=payload)

    async with WorkflowTestHarness(Keyed) as harness:
        result = await harness.start(Keyed.begin(), request_key="order_7")
        assert result.run_id is not None
        await harness.run_until_idle()

        assert await harness.kernel.find_by_key(Keyed, "order_7") == result.run_id
        assert await harness.kernel.find_by_key("validation.keyed", "order_7") == (
            result.run_id
        )
        assert await harness.kernel.find_by_key(Keyed, "order_8") is None
        assert (
            await harness.kernel.signal_by_key(
                Keyed, "order_8", Keyed.go(None), key="e1"
            )
            == "unknown_key"
        )
        assert (
            await harness.kernel.signal_by_key(
                Keyed, "order_7", Keyed.go(None), key="e1"
            )
            == "resolved"
        )
        with pytest.raises(Exception, match="not registered"):
            await harness.kernel.find_by_key("validation.nope", "order_7")
