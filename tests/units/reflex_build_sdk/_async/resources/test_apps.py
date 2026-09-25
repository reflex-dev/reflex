from __future__ import annotations

import datetime
import uuid
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest
from reflex_build_sdk import APIResponseValidationError, AsyncReflexBuild
from reflex_build_sdk.transports import Request, Response
from reflex_build_sdk.types import (
    App,
    AppDeployment,
    AppMove,
    AppSummary,
    CustomDomain,
    DeploymentRecord,
    DnsRecord,
    FullDeployChange,
    HostnameReservation,
    InstanceBoundsChange,
    LogRecord,
    ProviderChange,
    RunningDeployment,
    ServiceNameChange,
    User,
    VmType,
)

from tests.units.reflex_build_sdk.conftest import (
    AsyncMockTransport,
    MockAPI,
    json_body,
    reply,
)

APP_ID = "5f0c5e0e-8f6a-4d57-9a55-3c1c1d7b6a01"
PROJECT_ID = "b3c1e3f2-2d0a-4d8e-9a0e-7f7a1c2d3e4f"
DEPLOYMENT_ID = "0e7b9d2c-5a4f-4c3b-8e1d-6f2a9b8c7d10"
PREVIOUS_DEPLOYMENT_ID = "1f8c0e3d-6b5a-4d4c-9f2e-7a3b0c9d8e21"
USER_ID = "8b0f4a52-3a8a-4c43-9d7e-2f0c7d2a4b11"
APP_PATH = f"/api/v1/apps/{APP_ID}"
UTC = datetime.timezone.utc

APP_SUMMARY = {
    "id": APP_ID,
    "name": "dashboard",
    "description": "",
    "project_id": PROJECT_ID,
    "provider": "fly",
    "disable_secrets": False,
}

# Shaped like the control plane's responses, including fields the SDK does not model.
APP_INFO = {
    **APP_SUMMARY,
    "org_id": None,
    "source_thread_id": APP_ID,
    "full_deploy": False,
    "weekly_report_enabled": True,
    "min_instances": None,
    "max_instances": 3,
    "unreleased_provider": None,
    "backend_url": "https://dashboard-api.reflex.run",
    "has_deployments": True,
    "latest_deployment": {
        "id": DEPLOYMENT_ID,
        "hostname": "dashboard.reflex.run",
        "url": "https://dashboard.reflex.run",
        "vm_type_name": "c1m1",
        "vm_type_ram": 1.0,
        "vm_type_cpu": 1.0,
        "status": "Running",
        "pause_reason": None,
        "reflex_version": "0.9.11",
        "python_version": "3.13",
        "timestamp": "2026-09-16T10:00:00Z",
        "regions": ["ams", "sjc"],
        "persist": True,
        "strategy": "immediate",
        "last_updated": None,
        "last_updated_by": {"id": USER_ID, "username": "dev"},
        "screenshot_uri": None,
    },
    "any_environment_live": True,
    "any_environment_stopped": False,
    "any_environment_paused": False,
    "any_environment_credit_paused": False,
}


@pytest.fixture
async def client(mock_api: MockAPI) -> AsyncIterator[AsyncReflexBuild]:
    """A client talking to the mock API.

    Args:
        mock_api: The mock API.

    Yields:
        The client.
    """
    async with AsyncReflexBuild(
        token="test-token", transport=AsyncMockTransport(mock_api)
    ) as client:
        yield client


def _query(request: Request) -> dict[str, list[str]]:
    return parse_qs(urlsplit(request.url).query)


async def test_list(client: AsyncReflexBuild, mock_api: MockAPI):
    mock_api.add("GET", "/api/v1/apps", reply(200, json=[APP_SUMMARY]))
    assert await client.apps.list(project_id=uuid.UUID(PROJECT_ID)) == [
        AppSummary(
            id=uuid.UUID(APP_ID),
            name="dashboard",
            description="",
            project_id=uuid.UUID(PROJECT_ID),
            provider="fly",
            disable_secrets=False,
        )
    ]
    assert _query(mock_api.requests[0]) == {"project": [PROJECT_ID]}


async def test_search(client: AsyncReflexBuild, mock_api: MockAPI):
    mock_api.add("GET", "/api/v1/apps/search", reply(200, json=[APP_SUMMARY]))
    (app,) = await client.apps.search("dashboard")
    assert app.name == "dashboard"
    assert _query(mock_api.requests[0]) == {"app_name": ["dashboard"]}


async def test_get(client: AsyncReflexBuild, mock_api: MockAPI):
    mock_api.add("GET", APP_PATH, reply(200, json=APP_INFO))
    assert await client.apps.get(APP_ID) == App(
        id=uuid.UUID(APP_ID),
        name="dashboard",
        description="",
        project_id=uuid.UUID(PROJECT_ID),
        org_id=None,
        provider="fly",
        full_deploy=False,
        min_instances=None,
        max_instances=3,
        disable_secrets=False,
        weekly_report_enabled=True,
        source_thread_id=uuid.UUID(APP_ID),
        unreleased_provider=None,
        has_deployments=True,
        backend_url="https://dashboard-api.reflex.run",
        latest_deployment=AppDeployment(
            id=uuid.UUID(DEPLOYMENT_ID),
            url="https://dashboard.reflex.run",
            status="Running",
            pause_reason=None,
            reflex_version="0.9.11",
            python_version="3.13",
            created_at=datetime.datetime(2026, 9, 16, 10, tzinfo=UTC),
            regions=["ams", "sjc"],
            vm_type_name="c1m1",
            vm_type_cpu=1.0,
            vm_type_ram=1.0,
            strategy="immediate",
            persistent=True,
            screenshot_uri=None,
            updated_at=None,
            updated_by=User(id=uuid.UUID(USER_ID), username="dev"),
        ),
        any_environment_live=True,
        any_environment_stopped=False,
        any_environment_paused=False,
        any_environment_credit_paused=False,
    )


async def test_create(client: AsyncReflexBuild, mock_api: MockAPI):
    created = {
        key: APP_SUMMARY[key] for key in ("id", "name", "description", "project_id")
    }
    mock_api.add(
        "POST",
        "/api/v1/apps",
        reply(201, json={**created, "disable_secrets": False, "is_deleted": False}),
    )
    mock_api.add("GET", APP_PATH, reply(200, json=APP_INFO))
    app = await client.apps.create("dashboard", project_id=uuid.UUID(PROJECT_ID))
    assert app.id == uuid.UUID(APP_ID)
    create_request, get_request = mock_api.requests
    assert json_body(create_request) == {"name": "dashboard", "project": PROJECT_ID}
    assert get_request.method == "GET"


@pytest.mark.parametrize(
    ("method_name", "value", "suffix", "body"),
    [
        ("rename", "analytics", "/update_name", {"name": "analytics"}),
        ("set_description", "", "/update_description", {"description": ""}),
        ("set_weekly_report", False, "/weekly_report", {"enabled": False}),
    ],
)
async def test_update_field(
    client: AsyncReflexBuild,
    mock_api: MockAPI,
    method_name: str,
    value: Any,
    suffix: str,
    body: dict[str, Any],
):
    # update_name and update_description answer null; weekly_report echoes the value.
    mock_api.add("POST", APP_PATH + suffix, reply(200, json={"ignored": True}))
    assert await getattr(client.apps, method_name)(APP_ID, value) is None
    assert json_body(mock_api.requests[0]) == body


async def test_move(client: AsyncReflexBuild, mock_api: MockAPI):
    thread_id = "6a1d2c3b-4e5f-4a6b-8c7d-9e0f1a2b3c4d"
    mock_api.add(
        "POST",
        f"{APP_PATH}/move",
        reply(
            200,
            json={
                "message": "App moved",
                "app_id": APP_ID,
                "project_id": PROJECT_ID,
                "copied_integrations": ["Supabase"],
                "repo_tokens_withheld": [thread_id],
                "repo_tokens_failed": [],
                "repo_token_notices": ["Reconnect GitHub to push."],
            },
        ),
    )
    move = await client.apps.move(APP_ID, uuid.UUID(PROJECT_ID), copy_integrations=True)
    assert move == AppMove(
        project_id=uuid.UUID(PROJECT_ID),
        copied_integrations=["Supabase"],
        repo_tokens_withheld=[uuid.UUID(thread_id)],
        repo_tokens_failed=[],
        repo_token_notices=["Reconnect GitHub to push."],
    )
    assert json_body(mock_api.requests[0]) == {
        "target_project_id": PROJECT_ID,
        "copy_integrations": True,
    }


@pytest.mark.parametrize(
    ("method_name", "value", "changed"),
    [
        ("set_persistent", True, {"persist": True}),
        ("set_rollout_strategy", "bluegreen", {"strategy": "bluegreen"}),
    ],
)
async def test_update_settings(
    client: AsyncReflexBuild,
    mock_api: MockAPI,
    method_name: str,
    value: Any,
    changed: dict[str, Any],
):
    mock_api.add("POST", f"{APP_PATH}/settings", reply(200, json=None))
    assert await getattr(client.apps, method_name)(APP_ID, value) is None
    # Every setting is sent; null leaves the others unchanged.
    assert json_body(mock_api.requests[0]) == {
        "name": None,
        "description": None,
        "persist": None,
        "strategy": None,
        **changed,
    }


async def test_set_service_name(client: AsyncReflexBuild, mock_api: MockAPI):
    mock_api.add(
        "POST",
        f"{APP_PATH}/service_name",
        reply(200, json={"service_name": "dashboard", "stopped": True}),
    )
    assert await client.apps.set_service_name(APP_ID, "dashboard") == ServiceNameChange(
        service_name="dashboard", stopped=True
    )
    assert json_body(mock_api.requests[0]) == {"service_name": "dashboard"}


async def test_status(client: AsyncReflexBuild, mock_api: MockAPI):
    mock_api.add(
        "GET",
        f"{APP_PATH}/status",
        reply(200, json="Application stopped successfully"),
    )
    assert await client.apps.status(APP_ID) == "Application stopped successfully"


RUNNING_DEPLOYMENT = {
    "id": DEPLOYMENT_ID,
    "app_id": APP_ID,
    "environment_id": None,
    "promoted_from_deployment_id": None,
    "hostname": "dashboard",
    "url": "https://dashboard.reflex.run",
    "exported_url": "https://dashboard.reflex.run",
    "backend_url": "https://dashboard-api.reflex.run",
    "deployment_ts": "2026-09-16T10:00:00+00:00",
    "backend_image_uri": "registry.fly.io/dashboard:abc",
    "reflex_version": "0.9.11",
    "python_version": "3.13",
    "vmtype_id": "c1m1",
    "status": "Running",
    "pause_reason": None,
    "manually_paused": False,
    "strategy": "immediate",
    "persist": False,
    "deployment_user": USER_ID,
    "screenshot_uri": None,
    "description": None,
}


async def test_current_deployment(client: AsyncReflexBuild, mock_api: MockAPI):
    mock_api.add("GET", f"{APP_PATH}/deployment", reply(200, json=RUNNING_DEPLOYMENT))
    assert await client.apps.current_deployment(
        APP_ID, environment_id="env"
    ) == RunningDeployment(
        id=uuid.UUID(DEPLOYMENT_ID),
        app_id=uuid.UUID(APP_ID),
        environment_id=None,
        promoted_from_id=None,
        url="https://dashboard.reflex.run",
        backend_url="https://dashboard-api.reflex.run",
        reflex_version="0.9.11",
        python_version="3.13",
        vm_type_id="c1m1",
        strategy="immediate",
        persistent=False,
        description=None,
        created_at=datetime.datetime(2026, 9, 16, 10, tzinfo=UTC),
        deployed_by_id=uuid.UUID(USER_ID),
    )
    assert _query(mock_api.requests[0]) == {"environment_id": ["env"]}


async def test_current_deployment_when_nothing_runs(
    client: AsyncReflexBuild, mock_api: MockAPI
):
    # The route answers "not found" with a 200.
    mock_api.add(
        "GET",
        f"{APP_PATH}/deployment",
        reply(200, json={"detail": "no running deployment found"}),
    )
    assert await client.apps.current_deployment(APP_ID) is None


@pytest.mark.parametrize(
    ("method_name", "http_method", "suffix"),
    [
        ("delete", "DELETE", "/delete"),
        ("start", "POST", "/start"),
        ("stop", "POST", "/stop"),
        ("pause", "POST", "/pause"),
    ],
)
async def test_lifecycle(
    client: AsyncReflexBuild,
    mock_api: MockAPI,
    method_name: str,
    http_method: str,
    suffix: str,
):
    mock_api.add(http_method, APP_PATH + suffix, reply(200, json=None))
    assert await getattr(client.apps, method_name)(APP_ID) is None
    assert mock_api.requests[0].content is None


@pytest.mark.parametrize(
    ("kwargs", "body"),
    [
        ({"vm_type": "c2m4"}, {"type": "size", "size": "c2m4"}),
        ({"cpu": 2.0, "ram_mb": 4096}, {"type": "size", "cpu": 2.0, "ram_mb": 4096}),
        (
            {"regions": {"sjc": 2, "ams": 1}},
            {"type": "region", "regions": {"sjc": 2, "ams": 1}},
        ),
    ],
)
async def test_scale(
    client: AsyncReflexBuild,
    mock_api: MockAPI,
    kwargs: dict[str, Any],
    body: dict[str, Any],
):
    mock_api.add("POST", f"{APP_PATH}/scale", reply(200, json=None))
    await client.apps.scale(APP_ID, **kwargs)
    assert json_body(mock_api.requests[0]) == body


@pytest.mark.parametrize(
    "kwargs",
    [
        {},
        {"cpu": 2.0},
        {"ram_mb": 4096},
        {"vm_type": "c2m4", "cpu": 2.0, "ram_mb": 4096},
        {"vm_type": "c2m4", "regions": {"sjc": 1}},
        {"cpu": 2.0, "ram_mb": 4096, "regions": {"sjc": 1}},
    ],
)
async def test_scale_rejects_ambiguous_arguments(
    client: AsyncReflexBuild, mock_api: MockAPI, kwargs: dict[str, Any]
):
    with pytest.raises(ValueError, match="exactly one of"):
        await client.apps.scale(APP_ID, **kwargs)
    assert not mock_api.requests


async def test_set_provider(client: AsyncReflexBuild, mock_api: MockAPI):
    account_id = "2b7c9d1e-3f4a-4b5c-8d6e-7f8091a2b3c4"
    mock_api.add(
        "POST",
        f"{APP_PATH}/provider",
        reply(
            200,
            json={"provider": "gcp", "released": True, "unreleased_provider": None},
        ),
    )
    change = await client.apps.set_provider(
        APP_ID,
        "gcp",
        provider_account_id=uuid.UUID(account_id),
        service_name="dashboard",
        expected_project_id=PROJECT_ID,
    )
    assert change == ProviderChange(provider="gcp", released=True)
    (request,) = mock_api.requests
    assert json_body(request) == {
        "provider": "gcp",
        "provider_account_id": account_id,
        "service_name": "dashboard",
    }
    assert _query(request) == {"expected_project_id": [PROJECT_ID]}


async def test_set_full_deploy(client: AsyncReflexBuild, mock_api: MockAPI):
    mock_api.add(
        "POST",
        f"{APP_PATH}/full_deploy",
        reply(200, json={"full_deploy": True, "stopped": True, "stop_confirmed": True}),
    )
    assert await client.apps.set_full_deploy(APP_ID, True) == FullDeployChange(
        full_deploy=True, stopped=True, stop_confirmed=True
    )
    assert json_body(mock_api.requests[0]) == {"full_deploy": True}


@pytest.mark.parametrize(
    ("body", "change"),
    [
        (
            {"status": "ok", "applied_now": True},
            InstanceBoundsChange(status="ok", applied_now=True),
        ),
        ({"status": "unchanged"}, InstanceBoundsChange(status="unchanged")),
    ],
)
async def test_set_instance_bounds(
    client: AsyncReflexBuild,
    mock_api: MockAPI,
    body: dict,
    change: InstanceBoundsChange,
):
    mock_api.add("POST", f"{APP_PATH}/instance_bounds", reply(200, json=body))
    result = await client.apps.set_instance_bounds(
        APP_ID, min_instances=1, max_instances=None
    )
    assert result == change
    # Both bounds are always sent: the server replaces both.
    assert json_body(mock_api.requests[0]) == {
        "min_instances": 1,
        "max_instances": None,
    }


async def test_reserve_hostname(client: AsyncReflexBuild, mock_api: MockAPI):
    mock_api.add(
        "POST",
        "/api/v1/apps/reserve",
        reply(
            200,
            json={
                "hostname": "https://dashboard.reflex.run",
                "server": "https://dashboard-api.reflex.run",
            },
        ),
    )
    assert await client.apps.reserve_hostname(
        APP_ID, "dashboard", hostname="dashboard"
    ) == HostnameReservation(
        frontend_url="https://dashboard.reflex.run",
        backend_url="https://dashboard-api.reflex.run",
    )
    assert json_body(mock_api.requests[0]) == {
        "app_id": APP_ID,
        "app_name": "dashboard",
        "hostname": "dashboard",
    }


async def test_rollback(client: AsyncReflexBuild, mock_api: MockAPI):
    mock_api.add(
        "POST",
        f"{APP_PATH}/deployments/{DEPLOYMENT_ID}/rollback",
        reply(200, json=None),
    )
    await client.apps.rollback(APP_ID, DEPLOYMENT_ID)
    assert len(mock_api.requests) == 1


async def test_history(client: AsyncReflexBuild, mock_api: MockAPI):
    record = {
        "id": DEPLOYMENT_ID,
        "hostname": "dashboard.reflex.run",
        "url": "https://dashboard.reflex.run",
        "backend_url": "https://dashboard-api.reflex.run",
        "timestamp": "2026-09-16T10:00:00Z",
        "reflex_version": "0.9.11",
        "python_version": "3.13",
        "status": "Running",
        "pause_reason": None,
        "failure_code": None,
        "failure_reason": None,
        "description": "release",
        "last_updated": "2026-09-16T11:00:00Z",
        "deployment_user": {"id": USER_ID, "username": "dev"},
        "last_updated_by": {"id": USER_ID, "username": "dev"},
        # Machine size ids are names, although the schema declares a UUID.
        "vm_type": {"id": "c1m1", "name": "c1m1", "ram": 1.0, "cpu": 1.0},
        "environment_id": None,
        "environment_name": None,
        "promoted_from_deployment_id": PREVIOUS_DEPLOYMENT_ID,
        "can_rollback": True,
    }
    mock_api.add("GET", f"{APP_PATH}/history", reply(200, json=[record]))
    assert await client.apps.history(APP_ID) == [
        DeploymentRecord(
            id=uuid.UUID(DEPLOYMENT_ID),
            url="https://dashboard.reflex.run",
            backend_url="https://dashboard-api.reflex.run",
            status="Running",
            pause_reason=None,
            failure_code=None,
            failure_reason=None,
            description="release",
            reflex_version="0.9.11",
            python_version="3.13",
            created_at=datetime.datetime(2026, 9, 16, 10, tzinfo=UTC),
            updated_at=datetime.datetime(2026, 9, 16, 11, tzinfo=UTC),
            deployed_by=User(id=uuid.UUID(USER_ID), username="dev"),
            updated_by=User(id=uuid.UUID(USER_ID), username="dev"),
            vm_type=VmType(id="c1m1", name="c1m1", cpu=1.0, ram=1.0),
            environment_id=None,
            environment_name=None,
            promoted_from_id=uuid.UUID(PREVIOUS_DEPLOYMENT_ID),
            can_rollback=True,
        )
    ]
    assert not _query(mock_api.requests[0])


def _log(ns: int, message: str | dict[str, Any] = "line") -> dict[str, Any]:
    return {
        "ns": ns,
        "timestamp": "2026-09-16T10:00:00+00:00",
        "name": "dashboard",
        "message": message,
        "details": None,
        "log_level": "info",
        "region": "sjc",
        "event_id": f"event-{ns}",
        "stream_id": "app",
    }


def _log_page(*pages: tuple[list[dict[str, Any]], str | None]):
    """Build a handler answering successive log requests with successive pages.

    Args:
        pages: The entries and cursor of each page.

    Returns:
        The handler.
    """
    remaining = list(pages)

    def handle(request: Request) -> Response:
        entries, cursor = remaining.pop(0)
        return reply(200, json=[entries, cursor])(request)

    return handle


async def test_logs_follow_cursor_until_empty_page(
    client: AsyncReflexBuild, mock_api: MockAPI
):
    # Fly-hosted apps keep returning a cursor, and an empty page ends the logs.
    mock_api.add(
        "GET",
        f"{APP_PATH}/logsv2",
        _log_page(
            ([_log(1), _log(2, {"event": "start"})], "2"),
            ([_log(3)], "3"),
            ([], "3"),
        ),
    )
    start = datetime.datetime(2026, 9, 16, 10, tzinfo=UTC)
    records = [
        record
        async for record in client.apps.logs(
            APP_ID, start=start, order="newest_first", page_size=50
        )
    ]
    assert [record.ns for record in records] == [1, 2, 3]
    assert records[1] == LogRecord(
        ns=2,
        timestamp="2026-09-16T10:00:00+00:00",
        name="dashboard",
        message={"event": "start"},
        log_level="info",
        region="sjc",
        event_id="event-2",
        stream_id="app",
    )
    first, second, third = (_query(request) for request in mock_api.requests)
    assert first == {
        "start": [str(int(start.timestamp()))],
        "order": ["newest_first"],
        "limit": ["50"],
    }
    # Later pages keep the filters and add the cursor.
    assert second == {**first, "cursor": ["2"]}
    assert third == {**first, "cursor": ["3"]}


@pytest.mark.parametrize("bound", ["start", "end"])
async def test_logs_reject_naive_datetimes(
    client: AsyncReflexBuild, mock_api: MockAPI, bound: str
):
    naive: dict[str, Any] = {bound: datetime.datetime(2026, 9, 16, 10)}
    with pytest.raises(ValueError, match="timezone-aware"):
        async for _ in client.apps.logs(APP_ID, **naive):
            pass
    assert not mock_api.requests


async def test_logs_stop_without_cursor(client: AsyncReflexBuild, mock_api: MockAPI):
    # Google Cloud apps mark the last page with a null cursor.
    mock_api.add("GET", f"{APP_PATH}/logsv2", _log_page(([_log(1)], None)))
    records = [record async for record in client.apps.logs(APP_ID)]
    assert len(records) == 1
    assert len(mock_api.requests) == 1


async def test_secrets_list(client: AsyncReflexBuild, mock_api: MockAPI):
    mock_api.add("GET", f"{APP_PATH}/secrets", reply(200, json=["API_KEY"]))
    assert await client.apps.secrets.list(APP_ID, environment_id="env") == ["API_KEY"]
    assert _query(mock_api.requests[0]) == {"environment_id": ["env"]}


async def test_secrets_get(client: AsyncReflexBuild, mock_api: MockAPI):
    mock_api.add("GET", f"{APP_PATH}/secrets/API%2FKEY", reply(200, json="value"))
    assert await client.apps.secrets.get(APP_ID, "API/KEY") == "value"


async def test_secrets_get_named_all(client: AsyncReflexBuild, mock_api: MockAPI):
    # A secret named __all__ shares its path with the route reading every secret.
    mock_api.add(
        "GET",
        f"{APP_PATH}/secrets/__all__",
        reply(200, json={"__all__": "value", "OTHER": "x"}),
        reply(200, json={"OTHER": "x"}),
    )
    assert await client.apps.secrets.get(APP_ID, "__all__") == "value"
    with pytest.raises(KeyError):
        await client.apps.secrets.get(APP_ID, "__all__", environment_id="env")
    assert _query(mock_api.requests[1]) == {"environment_id": ["env"]}


async def test_secrets_get_all(client: AsyncReflexBuild, mock_api: MockAPI):
    mock_api.add(
        "GET", f"{APP_PATH}/secrets/__all__", reply(200, json={"API_KEY": "value"})
    )
    assert await client.apps.secrets.get_all(APP_ID) == {"API_KEY": "value"}


async def test_secrets_set(client: AsyncReflexBuild, mock_api: MockAPI):
    mock_api.add("POST", f"{APP_PATH}/secrets", reply(200, json=None))
    await client.apps.secrets.set(APP_ID, {"API_KEY": "value"}, reboot=True)
    (request,) = mock_api.requests
    assert json_body(request) == {"secrets": {"API_KEY": "value"}}
    assert _query(request) == {"reboot": ["true"]}


async def test_secrets_delete(client: AsyncReflexBuild, mock_api: MockAPI):
    mock_api.add("DELETE", f"{APP_PATH}/secrets/API_KEY", reply(200, json=None))
    await client.apps.secrets.delete(APP_ID, "API_KEY")
    assert _query(mock_api.requests[0]) == {"reboot": ["false"]}


async def test_domains_get(client: AsyncReflexBuild, mock_api: MockAPI):
    mock_api.add(
        "GET",
        f"{APP_PATH}/custom_domain",
        reply(
            200,
            json={
                "domain": "app.example.com",
                "verified": False,
                "dns_records": {
                    "DNS_RECORD_CNAME": {
                        "type": "CNAME",
                        "name": "app.example.com",
                        "value": "reflex.run",
                        "status": "wrong",
                        "observed": "other.example.net",
                    }
                },
                "status": "pointing_elsewhere",
                "status_detail": "The domain points somewhere else.",
                "checked_at": "2026-09-16T10:00:00Z",
            },
        ),
    )
    assert await client.apps.domains.get(APP_ID) == CustomDomain(
        domain="app.example.com",
        verified=False,
        dns_records={
            "DNS_RECORD_CNAME": DnsRecord(
                type="CNAME",
                name="app.example.com",
                value="reflex.run",
                status="wrong",
                observed="other.example.net",
            )
        },
        status="pointing_elsewhere",
        status_detail="The domain points somewhere else.",
        checked_at=datetime.datetime(2026, 9, 16, 10, tzinfo=UTC),
    )


async def test_domains_get_without_a_domain(
    client: AsyncReflexBuild, mock_api: MockAPI
):
    mock_api.add("GET", f"{APP_PATH}/custom_domain", reply(200, json={}))
    assert await client.apps.domains.get(APP_ID) is None


@pytest.mark.parametrize("body", [{"domain": "example.com"}, {"domain": None}])
async def test_domains_get_rejects_an_unexpected_domain(
    client: AsyncReflexBuild, mock_api: MockAPI, body: dict
):
    mock_api.add("GET", f"{APP_PATH}/custom_domain", reply(200, json=body))
    with pytest.raises(APIResponseValidationError):
        await client.apps.domains.get(APP_ID)


async def test_domains_add(client: AsyncReflexBuild, mock_api: MockAPI):
    mock_api.add(
        "POST",
        f"{APP_PATH}/custom_domain",
        reply(
            200,
            json={
                "dns_records": {
                    "DNS_RECORD_A": {
                        "type": "A",
                        "name": "example.com",
                        "value": "203.0.113.7",
                    }
                }
            },
        ),
    )
    assert await client.apps.domains.add(APP_ID, "example.com") == {
        "DNS_RECORD_A": DnsRecord(type="A", name="example.com", value="203.0.113.7")
    }
    assert json_body(mock_api.requests[0]) == {"domain": "example.com"}


async def test_domains_remove(client: AsyncReflexBuild, mock_api: MockAPI):
    mock_api.add(
        "DELETE",
        f"{APP_PATH}/custom_domain/app.example.com",
        reply(200, json={"message": "Successfully deleted app.example.com"}),
    )
    assert await client.apps.domains.remove(APP_ID, "app.example.com") is None
