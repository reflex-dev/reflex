"""The standalone service: scoped auth, the run API, probes, and lifecycle.

The acceptance bar from the plan: ``workflows serve`` receives a signed
Stripe webhook with no ``rx.App`` and no frontend; shutdown drains before
losing anything; Python and HTTP signaling agree on dispositions.
"""

import hmac as hmac_mod
import json
import time

import pytest
from reflex_base.workflow import (
    Signal,
    WorkflowConfig,
    manual,
    stripe_signature,
    webhook,
)
from starlette.testclient import TestClient

import reflex as rx
from reflex.workflow import testing
from reflex.workflow.runtime import WorkflowRuntime
from reflex.workflow.serve import SCOPES, ScopedTokens, build_app

STRIPE_SECRET = "whsec_serve_test"


class Orders(rx.State):
    """A workflow with a manual root and a signal channel."""

    __workflow__ = WorkflowConfig(id="serve.orders")
    note: str = ""

    @rx.event(durable=True, effect="none", trigger=manual())
    def place(self, order_id: str):
        """Start an order and wait for its shipment.

        Args:
            order_id: The order.

        Returns:
            The wait.
        """
        self.note = order_id
        return rx.wait_for(Orders.shipped, then=Orders.close, timeout=rx.never)

    shipped = Signal()

    @rx.event(durable=True, effect="none")
    def close(self, payload):
        """Finish with the shipment payload.

        Args:
            payload: The delivered payload.

        Returns:
            Completion.
        """
        return rx.complete(result={"order": self.note, "shipment": payload})


def _tokens(**grants: str) -> ScopedTokens:
    """Build token scopes without touching the environment.

    Args:
        grants: token=scope pairs, scope "all" meaning every scope.

    Returns:
        The scope mapping.
    """
    return ScopedTokens(
        grants={
            token: frozenset(SCOPES) if scope == "all" else frozenset({scope})
            for token, scope in grants.items()
        }
    )


def _auth(token: str) -> dict[str, str]:
    """Bearer header for a token.

    Args:
        token: The token to present.

    Returns:
        The header mapping.
    """
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def service(forked_registration_context):
    """A served runtime over the parametrized store, with scoped tokens.

    Args:
        forked_registration_context: Isolated state registry.

    Yields:
        The entered test client.
    """
    runtime = WorkflowRuntime(testing.MemoryRunStore())
    runtime.register(Orders)
    app = build_app(
        runtime,
        worker=True,
        drain=0,
        tokens=_tokens(
            tk_all="all",
            tk_read="read",
            tk_start="start",
            tk_signal="signal",
            tk_operate="operate",
        ),
    )
    with TestClient(app) as client:
        yield client


def _start_order(client: TestClient, token: str = "tk_start") -> str:
    """Start one order run over HTTP.

    Args:
        client: The service client.
        token: The token to start with.

    Returns:
        The admitted run id.
    """
    response = client.post(
        "/runs",
        json={
            "workflow": "serve.orders",
            "handler": "place",
            "args": {"order_id": "o1"},
        },
        headers=_auth(token),
    )
    assert response.status_code == 202, response.text
    return response.json()["run_id"]


def test_every_scope_gates_exactly_its_routes(service):
    """Read cannot write, start cannot read, and nothing works tokenless.

    Args:
        service: The served client.
    """
    body = {"workflow": "serve.orders", "handler": "place", "args": {"order_id": "x"}}
    assert service.post("/runs", json=body).status_code == 401
    assert service.get("/runs").status_code == 401
    assert service.post("/runs", json=body, headers=_auth("tk_read")).status_code == 403
    assert service.get("/runs", headers=_auth("tk_start")).status_code == 403
    assert service.get("/metrics", headers=_auth("tk_signal")).status_code == 403
    assert service.get("/metrics", headers=_auth("tk_read")).status_code == 200
    run_id = _start_order(service)
    assert (
        service.post(f"/runs/{run_id}/cancel", headers=_auth("tk_signal")).status_code
        == 403
    )
    assert (
        service.post(
            f"/runs/{run_id}/signals/shipped",
            json={},
            headers=_auth("tk_operate"),
        ).status_code
        == 403
    )
    assert service.get(f"/runs/{run_id}", headers=_auth("tk_all")).status_code == 200


def test_the_run_lifecycle_works_end_to_end_over_http(service):
    """Start, list, read, signal, and read the result, all over the API.

    Args:
        service: The served client.
    """
    run_id = _start_order(service)
    listed = service.get(
        "/runs", params={"workflow": "serve.orders"}, headers=_auth("tk_read")
    )
    assert listed.status_code == 200
    assert any(run["run_id"] == run_id for run in listed.json()["runs"])

    delivered = service.post(
        f"/runs/{run_id}/signals/shipped",
        json={"parcel": "P-1"},
        headers={**_auth("tk_signal"), "Idempotency-Key": "evt_1"},
    )
    assert delivered.status_code == 202
    assert delivered.json()["disposition"] in ("resolved", "buffered")
    duplicate = service.post(
        f"/runs/{run_id}/signals/shipped",
        json={"parcel": "P-1"},
        headers={**_auth("tk_signal"), "Idempotency-Key": "evt_1"},
    )
    assert duplicate.json()["disposition"] == "duplicate"

    snapshot: dict = {}
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        snapshot = service.get(f"/runs/{run_id}", headers=_auth("tk_read")).json()
        if snapshot["status"] == "COMPLETED":
            break
        time.sleep(0.05)
    assert snapshot["status"] == "COMPLETED", snapshot
    assert snapshot["result"] == {"order": "o1", "shipment": {"parcel": "P-1"}}


def test_http_signals_share_python_signal_semantics(service):
    """The HTTP boundary maps kernel dispositions, never invents its own.

    Args:
        service: The served client.
    """
    missing = service.post(
        "/runs/nope/signals/shipped", json={}, headers=_auth("tk_signal")
    )
    assert missing.status_code == 404
    assert missing.json()["disposition"] == "unknown_run"

    run_id = _start_order(service)
    unknown_channel = service.post(
        f"/runs/{run_id}/signals/shiped", json={}, headers=_auth("tk_signal")
    )
    assert unknown_channel.status_code == 400
    assert "shiped" in unknown_channel.json()["error"]


def test_operator_actions_answer_404_and_409_precisely(service):
    """Unknown runs and wrong-state runs are different failures.

    Args:
        service: The served client.
    """
    assert (
        service.post("/runs/nope/cancel", headers=_auth("tk_operate")).status_code
        == 404
    )
    run_id = _start_order(service)
    retried = service.post(f"/runs/{run_id}/retry", headers=_auth("tk_operate"))
    assert retried.status_code == 409, "a healthy run does not accept retry"
    cancelled = service.post(f"/runs/{run_id}/cancel", headers=_auth("tk_operate"))
    assert cancelled.status_code == 202


def test_probes_and_openapi_need_no_token(service):
    """An orchestrator holds no credentials; probes must answer anyway.

    Args:
        service: The served client.
    """
    assert service.get("/healthz").json() == {"status": "ok"}
    assert service.get("/readyz").json() == {"status": "ready"}
    document = service.get("/openapi.json").json()
    assert document["openapi"].startswith("3.")
    assert "/runs/{run_id}/signals/{channel}" in document["paths"]


def test_readyz_reports_an_unreachable_store(forked_registration_context):
    """Ready means "can do useful work", and that means the store answers.

    Args:
        forked_registration_context: Isolated state registry.
    """
    runtime = WorkflowRuntime(testing.MemoryRunStore())
    runtime.register(Orders)
    app = build_app(runtime, worker=False, drain=0, tokens=_tokens(t="all"))
    with TestClient(app) as client:

        async def broken():  # noqa: RUF029
            msg = "store is down"
            raise ConnectionError(msg)

        runtime.kernel._store.epoch_time = broken  # pyright: ignore[reportAttributeAccessIssue]
        response = client.get("/readyz")
    assert response.status_code == 503
    assert "store is down" in response.json()["store"]


def test_worker_only_mode_serves_probes_and_nothing_else(
    forked_registration_context,
):
    """A pure worker still answers its orchestrator, but accepts no work.

    Args:
        forked_registration_context: Isolated state registry.
    """
    runtime = WorkflowRuntime(testing.MemoryRunStore())
    runtime.register(Orders)
    app = build_app(
        runtime, worker=True, ingress=False, drain=0, tokens=_tokens(t="all")
    )
    with TestClient(app) as client:
        assert client.get("/healthz").status_code == 200
        assert client.get("/metrics", headers=_auth("t")).status_code == 200
        assert client.post("/runs", json={}, headers=_auth("t")).status_code == 404
        assert client.get("/openapi.json").status_code == 404


def test_shutdown_drains_the_runtime(forked_registration_context):
    """Closing the server hands the drain budget to the runtime.

    Args:
        forked_registration_context: Isolated state registry.
    """
    runtime = WorkflowRuntime(testing.MemoryRunStore())
    runtime.register(Orders)
    seen: list = []
    original = runtime.shutdown

    async def spying_shutdown(drain=0):
        seen.append(drain)
        await original(drain=drain)

    runtime.shutdown = spying_shutdown  # pyright: ignore[reportAttributeAccessIssue]
    app = build_app(runtime, worker=True, drain="7s", tokens=_tokens(t="all"))
    with TestClient(app):
        pass
    assert seen == ["7s"], "shutdown must receive exactly the configured drain"


def test_a_signed_stripe_webhook_lands_with_no_rx_app(
    monkeypatch, forked_registration_context
):
    """The plan's acceptance scenario, minus uvicorn: serve takes a real
    provider delivery with no frontend anywhere.

    Args:
        monkeypatch: Used to install the Stripe secret.
        forked_registration_context: Isolated state registry.
    """
    monkeypatch.setenv("SERVE_STRIPE_SECRET", STRIPE_SECRET)

    class Billing(rx.State):
        __workflow__ = WorkflowConfig(id="serve.billing")

        @rx.event(
            durable=True,
            effect="none",
            trigger=webhook(
                "invoice_paid",
                dedupe_by="id",
                verify=stripe_signature(secret_env="SERVE_STRIPE_SECRET"),
            ),
        )
        def on_paid(self, id: str):
            """Record the invoice.

            Args:
                id: The invoice identifier.

            Returns:
                Completion.
            """
            return rx.complete(result=id)

    runtime = WorkflowRuntime(testing.MemoryRunStore())
    runtime.register(Billing)
    app = build_app(runtime, worker=True, drain=0, tokens=_tokens(t="all"))
    body = json.dumps({"id": "inv_9"}).encode()
    timestamp = int(time.time())
    digest = hmac_mod.new(
        STRIPE_SECRET.encode(), f"{timestamp}.".encode() + body, "sha256"
    ).hexdigest()
    with TestClient(app) as client:
        accepted = client.post(
            "/_workflow/webhook/invoice_paid",
            content=body,
            headers={"Stripe-Signature": f"t={timestamp},v1={digest}"},
        )
        assert accepted.status_code == 202, accepted.text
        forged = client.post(
            "/_workflow/webhook/invoice_paid",
            content=body,
            headers={"Stripe-Signature": f"t={timestamp},v1={'0' * 64}"},
        )
        assert forged.status_code == 401
        redelivered = client.post(
            "/_workflow/webhook/invoice_paid",
            content=body,
            headers={"Stripe-Signature": f"t={timestamp},v1={digest}"},
        )
        assert redelivered.json()["disposition"] == "deduplicated"


def test_business_keys_address_runs_without_run_ids(service):
    """`order_123` reaches the order's run; nobody stored a run id.

    Args:
        service: The served client.
    """
    started = service.post(
        "/runs",
        json={
            "workflow": "serve.orders",
            "handler": "place",
            "args": {"order_id": "o1"},
            "request_key": "order_123",
        },
        headers=_auth("tk_start"),
    )
    assert started.status_code == 202
    run_id = started.json()["run_id"]

    found = service.get(
        "/workflows/serve.orders/keys/order_123", headers=_auth("tk_read")
    )
    assert found.status_code == 200
    assert found.json()["run_id"] == run_id

    missing = service.get(
        "/workflows/serve.orders/keys/order_999", headers=_auth("tk_read")
    )
    assert missing.status_code == 404

    delivered = service.post(
        "/workflows/serve.orders/keys/order_123/signals/shipped",
        json={"parcel": "P-9"},
        headers={**_auth("tk_signal"), "Idempotency-Key": "evt_9"},
    )
    assert delivered.status_code == 202
    redelivered = service.post(
        "/workflows/serve.orders/keys/order_123/signals/shipped",
        json={"parcel": "P-9"},
        headers={**_auth("tk_signal"), "Idempotency-Key": "evt_9"},
    )
    assert redelivered.json()["disposition"] == "duplicate"
    unkeyed = service.post(
        "/workflows/serve.orders/keys/order_999/signals/shipped",
        json={},
        headers=_auth("tk_signal"),
    )
    assert unkeyed.status_code == 404
    assert unkeyed.json()["disposition"] == "unknown_key"
    unknown_workflow = service.get(
        "/workflows/serve.nope/keys/order_123", headers=_auth("tk_read")
    )
    assert unknown_workflow.status_code == 404


def test_dead_letters_are_visible_and_replayable_over_http(
    forked_registration_context,
):
    """The operator's dead-letter loop over serve: park, list, replay.

    Args:
        forked_registration_context: Isolated state registry.
    """

    class Freight(rx.State):
        __workflow__ = WorkflowConfig(id="serve.freight")

        arrived = Signal(
            trigger=webhook(
                "freight_arrived",
                dedupe_by="event_id",
                correlate_by="shipment_id",
                allow_unverified=True,
                unverified_reason="test-only channel",
            )
        )

        @rx.event(durable=True, effect="none", trigger=manual())
        def begin(self):
            """Wait for arrival.

            Returns:
                The wait.
            """
            return rx.wait_for(Freight.arrived, then=Freight.close, timeout=rx.never)

        @rx.event(durable=True, effect="none")
        def close(self, event):
            """Finish.

            Args:
                event: The delivered payload.

            Returns:
                Completion.
            """
            return rx.complete(result=event)

    runtime = WorkflowRuntime(testing.MemoryRunStore())
    runtime.register(Freight)
    app = build_app(
        runtime,
        worker=False,
        drain=0,
        tokens=_tokens(tk_read="read", tk_operate="operate"),
    )
    with TestClient(app) as client:
        assert (
            client.get("/deadletters?status=all", headers=_auth("tk_read")).json()[
                "deliveries"
            ]
            == []
        )
        parked = client.post(
            "/_workflow/webhook/freight_arrived",
            json={"event_id": "evt_d", "shipment_id": "ship_9"},
        )
        assert parked.status_code == 202, parked.text
        assert parked.json()["disposition"] == "parked"

        rows = client.get(
            "/deadletters?status=pending", headers=_auth("tk_read")
        ).json()["deliveries"]
        assert len(rows) == 1
        assert rows[0]["correlation_key"] == "ship_9"
        parked_id = rows[0]["parked_id"]

        forbidden = client.post(
            f"/deadletters/{parked_id}/replay", headers=_auth("tk_read")
        )
        assert forbidden.status_code == 403
        replayed = client.post(
            f"/deadletters/{parked_id}/replay", headers=_auth("tk_operate")
        )
        assert replayed.status_code == 202
        assert replayed.json()["disposition"] == "parked", "still no run to take it"
        missing = client.post("/deadletters/nope/replay", headers=_auth("tk_operate"))
        assert missing.status_code == 404


def test_operator_actions_record_who_and_why(forked_registration_context):
    """X-Actor and the body's reason land in the run's history.

    Args:
        forked_registration_context: Isolated state registry.
    """
    from reflex.workflow.records import HistoryEventType

    runtime = WorkflowRuntime(testing.MemoryRunStore())
    runtime.register(Orders)
    app = build_app(runtime, worker=False, drain=0, tokens=_tokens(tk="all"))
    with TestClient(app) as client:
        started = client.post(
            "/runs",
            json={
                "workflow": "serve.orders",
                "handler": "place",
                "args": {"order_id": "o-audit"},
            },
            headers=_auth("tk"),
        )
        run_id = started.json()["run_id"]
        cancelled = client.post(
            f"/runs/{run_id}/cancel",
            json={"reason": "duplicate order"},
            headers={**_auth("tk"), "X-Actor": "ops@example.com"},
        )
        assert cancelled.status_code == 202
        assert client.portal is not None
        events = client.portal.call(  # pyright: ignore[reportAttributeAccessIssue]
            runtime.kernel._store.get_history,  # pyright: ignore[reportPrivateUsage]
            run_id,
        )
    cancel_event = next(
        event for event in events if event.type is HistoryEventType.RUN_CANCEL_REQUESTED
    )
    assert cancel_event.data["actor"] == "ops@example.com"
    assert cancel_event.data["reason"] == "duplicate order"


def test_a_principal_bound_token_names_its_actor(
    monkeypatch, forked_registration_context
):
    """The credential names the actor; the header is only a fallback claim.

    Args:
        monkeypatch: Used to configure tokens and principals.
        forked_registration_context: Isolated state registry.
    """
    from reflex.workflow.records import HistoryEventType

    tokens = ScopedTokens(
        grants={
            "tok-start": frozenset({"start"}),
            "tok-bound": frozenset({"operate"}),
            "tok-anon": frozenset({"operate"}),
        },
        principals={"tok-bound": "deploy-bot"},
    )

    runtime = WorkflowRuntime(testing.MemoryRunStore())
    runtime.register(Orders)
    app = build_app(runtime, worker=False, drain=0, tokens=tokens)

    def start(client: TestClient, order: str) -> str:
        """Start one order.

        Args:
            client: The service client.
            order: The order id.

        Returns:
            The run id.
        """
        response = client.post(
            "/runs",
            json={
                "workflow": "serve.orders",
                "handler": "place",
                "args": {"order_id": order},
            },
            headers=_auth("tok-start"),
        )
        return response.json()["run_id"]

    with TestClient(app) as client:
        bound_run = start(client, "o-bound")
        anon_run = start(client, "o-anon")
        plain_run = start(client, "o-plain")
        client.post(
            f"/runs/{bound_run}/cancel",
            json={"reason": "rollout"},
            headers={**_auth("tok-bound"), "X-Actor": "spoofed"},
        )
        client.post(
            f"/runs/{anon_run}/cancel",
            headers={**_auth("tok-anon"), "X-Actor": "ops@example.com"},
        )
        client.post(f"/runs/{plain_run}/cancel", headers=_auth("tok-anon"))
        assert client.portal is not None
        store = runtime.kernel._store  # pyright: ignore[reportPrivateUsage]
        actors = {
            run_id: next(
                event.data.get("actor")
                for event in client.portal.call(store.get_history, run_id)
                if event.type is HistoryEventType.RUN_CANCEL_REQUESTED
            )
            for run_id in (bound_run, anon_run, plain_run)
        }
    assert actors[bound_run] == "deploy-bot", "the credential beats the header"
    assert actors[anon_run] == "ops@example.com", "unbound: the header's claim"
    assert actors[plain_run] == "api", "neither: name the surface"


def test_dead_letter_replay_is_audited_with_the_actor(forked_registration_context):
    """A replay has no run to carry history, so it lands in the audit log.

    Args:
        forked_registration_context: Isolated state registry.
    """

    class Parcel(rx.State):
        __workflow__ = WorkflowConfig(id="serve.parcel")

        arrived = Signal(
            trigger=webhook(
                "parcel_arrived",
                dedupe_by="event_id",
                correlate_by="parcel_id",
                allow_unverified=True,
                unverified_reason="test-only channel",
            )
        )

        @rx.event(durable=True, effect="none", trigger=manual())
        def begin(self):
            """Wait for arrival.

            Returns:
                The wait.
            """
            return rx.wait_for(Parcel.arrived, then=Parcel.close, timeout=rx.never)

        @rx.event(durable=True, effect="none")
        def close(self, event):
            """Finish.

            Args:
                event: The payload.

            Returns:
                Completion.
            """
            return rx.complete(result=event)

    tokens = ScopedTokens(
        grants={"tok-ops": frozenset({"read", "operate"})},
        principals={"tok-ops": "night-shift"},
    )
    runtime = WorkflowRuntime(testing.MemoryRunStore())
    runtime.register(Parcel)
    app = build_app(runtime, worker=False, drain=0, tokens=tokens)
    with TestClient(app) as client:
        client.post(
            "/_workflow/webhook/parcel_arrived",
            json={"event_id": "evt_a", "parcel_id": "p_1"},
        )
        parked_id = client.get(
            "/deadletters?status=pending", headers=_auth("tok-ops")
        ).json()["deliveries"][0]["parked_id"]
        replayed = client.post(
            f"/deadletters/{parked_id}/replay",
            json={"reason": "carrier fixed the feed"},
            headers=_auth("tok-ops"),
        )
        assert replayed.status_code == 202
        entries = client.get("/audit", headers=_auth("tok-ops")).json()["entries"]
        forbidden = client.get("/audit")
    assert forbidden.status_code == 401
    assert len(entries) == 1
    assert entries[0]["actor"] == "night-shift", "the bound principal, not a header"
    assert entries[0]["action"] == "replay_parked"
    assert entries[0]["target"] == parked_id
    assert entries[0]["reason"] == "carrier fixed the feed"
    assert entries[0]["detail"] == {"disposition": "parked"}
