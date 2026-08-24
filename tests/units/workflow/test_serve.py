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
    tokens = ScopedTokens.__new__(ScopedTokens)
    tokens.grants = {
        token: frozenset(SCOPES) if scope == "all" else frozenset({scope})
        for token, scope in grants.items()
    }
    return tokens


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
