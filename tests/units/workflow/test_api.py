"""Tests for the HTTP surface that starts and reads runs.

This is the endpoint a Django view or a Go service calls to say "this
happened" without importing the workflow package. It can start arbitrary
workflows, so most of these are about the token: what it refuses, and that
the surface does not exist at all without one.
"""

import json

import pytest
from reflex_base.workflow import WorkflowConfig, manual
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.testclient import TestClient

import reflex as rx
from reflex.workflow.api import (
    METRICS_ROUTE,
    RUN_ROUTE,
    START_ROUTE,
    TOKEN_ENV,
    api_token,
    metrics_endpoint,
    render_prometheus,
    run_endpoint,
    start_endpoint,
)
from reflex.workflow.runtime import WorkflowRuntime
from reflex.workflow.store import MemoryRunStore

TOKEN = "wf_" + "t" * 32


class Orders(rx.State):
    """A workflow an outside service starts."""

    __workflow__ = WorkflowConfig(id="api.orders")
    order: str = ""

    @rx.event(durable=True, trigger=manual(), effect="none", id="accept_order")
    def place(self, order: str):
        """Record the order.

        Args:
            order: The order identifier.

        Returns:
            Completion.
        """
        self.order = order
        return rx.complete(result={"order": order})


@pytest.fixture
async def client(forked_registration_context):
    """A client wired to the API endpoints of a live runtime.

    Yields:
        The test client.
    """
    runtime = WorkflowRuntime(MemoryRunStore())
    runtime.register(Orders)
    await runtime.startup(start_worker=False)
    app = Starlette(
        routes=[
            Route(START_ROUTE, start_endpoint(runtime, TOKEN), methods=["POST"]),
            Route(RUN_ROUTE, run_endpoint(runtime, TOKEN), methods=["GET"]),
            Route(METRICS_ROUTE, metrics_endpoint(runtime, TOKEN), methods=["GET"]),
        ]
    )
    with TestClient(app) as ready:
        yield ready
    await runtime.shutdown()


def _auth() -> dict[str, str]:
    """Build the authorization header.

    Returns:
        Headers carrying the bearer token.
    """
    return {"authorization": f"Bearer {TOKEN}"}


def test_a_service_can_start_and_read_a_run(client):
    """The two verbs an outside caller needs, over HTTP."""
    started = client.post(
        START_ROUTE,
        content=json.dumps({
            "workflow": "api.orders",
            "handler": "place",
            "args": {"order": "ord-1"},
        }),
        headers=_auth(),
    )
    assert started.status_code == 202, started.text
    run_id = started.json()["run_id"]
    assert started.json()["disposition"] == "started"

    read = client.get(f"/_workflow/api/runs/{run_id}", headers=_auth())
    assert read.status_code == 200
    assert read.json()["workflow"] == "api.orders"
    assert read.json()["steps"][0]["handler"] == "accept_order", (
        "the read surface reports the stable id, which is why the write "
        "surface has to accept it"
    )


def test_an_idempotency_key_returns_the_same_run(client):
    """A retrying caller must not create a second run."""
    body = json.dumps({
        "workflow": "api.orders",
        "handler": "place",
        "args": {"order": "ord-2"},
        "request_key": "invoice-77",
    })
    first = client.post(START_ROUTE, content=body, headers=_auth())
    second = client.post(START_ROUTE, content=body, headers=_auth())
    assert first.json()["run_id"] == second.json()["run_id"]
    assert second.json()["disposition"] == "deduplicated"


@pytest.mark.parametrize(
    "headers",
    [{}, {"authorization": "Bearer wrong"}, {"authorization": TOKEN}],
    ids=["missing", "wrong-token", "no-scheme"],
)
def test_every_route_requires_the_token(client, headers):
    """An endpoint that starts arbitrary workflows is never open.

    Args:
        client: The test client.
        headers: The authorization headers under test.
    """
    body = json.dumps({"workflow": "api.orders", "handler": "place"})
    assert client.post(START_ROUTE, content=body, headers=headers).status_code == 401
    assert (
        client.get("/_workflow/api/runs/whatever", headers=headers).status_code == 401
    )
    assert client.get(METRICS_ROUTE, headers=headers).status_code == 401


def test_unknown_targets_are_refused(client):
    """A caller naming something that does not exist is told which part."""
    for body, status in [
        ({"workflow": "api.nope", "handler": "place"}, 404),
        ({"workflow": "api.orders", "handler": "nope"}, 404),
        ({"workflow": "api.orders"}, 400),
        ({"workflow": "api.orders", "handler": "place", "args": [1]}, 400),
    ]:
        response = client.post(START_ROUTE, content=json.dumps(body), headers=_auth())
        assert response.status_code == status, (body, response.text)

    assert (
        client.post(START_ROUTE, content=b"<not json>", headers=_auth()).status_code
        == 400
    )
    assert client.get("/_workflow/api/runs/missing", headers=_auth()).status_code == 404


def test_the_api_is_absent_without_a_configured_token(monkeypatch):
    """No token means no surface, rather than a surface anyone can call."""
    monkeypatch.delenv(TOKEN_ENV, raising=False)
    assert api_token() is None
    monkeypatch.setenv(TOKEN_ENV, "")
    assert api_token() is None
    monkeypatch.setenv(TOKEN_ENV, TOKEN)
    assert api_token() == TOKEN


def test_metrics_are_scrapeable_after_a_run(client):
    """A collector reads what this process did, in the format it already speaks.

    Args:
        client: The test client.
    """
    body = json.dumps({
        "workflow": "api.orders",
        "handler": "place",
        "args": {"order": "o-1"},
    })
    assert client.post(START_ROUTE, content=body, headers=_auth()).status_code == 202

    response = client.get(METRICS_ROUTE, headers=_auth())
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    text = response.text
    assert "# TYPE reflex_workflow_runs_started_total counter" in text
    assert "reflex_workflow_runs_started_total 1" in text
    assert 'reflex_workflow_runs_started_total{workflow="api.orders"} 1' in text


def test_prometheus_rendering_escapes_label_values():
    """A workflow id is developer data; the exposition format still has to hold."""
    text = render_prometheus({
        "totals": {"runs_started": 1},
        "by_workflow": {'we"ird\\flow': {"runs_started": 1}},
    })
    assert 'workflow="we\\"ird\\\\flow"' in text
    assert text.endswith("\n")


def test_the_stable_handler_id_starts_a_run(client):
    """What a run reads back as its handler must be what the API accepts.

    Args:
        client: The test client.
    """
    body = json.dumps({
        "workflow": "api.orders",
        "handler": "accept_order",
        "args": {"order": "o-id"},
    })
    response = client.post(START_ROUTE, content=body, headers=_auth())
    assert response.status_code == 202, response.text
    run_id = response.json()["run_id"]
    read = client.get(f"/_workflow/api/runs/{run_id}", headers=_auth())
    assert read.json()["steps"][0]["handler"] == "accept_order"


def test_the_python_name_still_works(client):
    """Accepting the stable id must not break callers using the method name.

    Args:
        client: The test client.
    """
    body = json.dumps({
        "workflow": "api.orders",
        "handler": "place",
        "args": {"order": "o-name"},
    })
    assert client.post(START_ROUTE, content=body, headers=_auth()).status_code == 202


def test_missing_required_arguments_are_refused(client):
    """A run that cannot possibly run is not admitted.

    Args:
        client: The test client.
    """
    body = json.dumps({"workflow": "api.orders", "handler": "place"})
    response = client.post(START_ROUTE, content=body, headers=_auth())
    assert response.status_code == 400, response.text
    assert "order" in response.json()["error"]


def test_a_falsey_non_object_args_is_refused(client):
    """`args: []` is a caller mistake, not an empty payload.

    Args:
        client: The test client.
    """
    body = json.dumps({"workflow": "api.orders", "handler": "place", "args": []})
    response = client.post(START_ROUTE, content=body, headers=_auth())
    assert response.status_code == 400, response.text
    assert "JSON object" in response.json()["error"]


def test_a_mistyped_argument_is_refused_at_the_boundary(client):
    """A payload the signature refuses is the caller's 400, not a poison run.

    Args:
        client: The test client.
    """
    body = json.dumps({
        "workflow": "api.orders",
        "handler": "place",
        "args": {"order": {"nested": "object"}},
    })
    response = client.post(START_ROUTE, content=body, headers=_auth())
    assert response.status_code == 400, response.text
    assert "'order'" in response.json()["error"]
