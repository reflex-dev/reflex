# Generated from tests/units/reflex_build_sdk/_async/resources/test_deployments.py by packages/reflex-build-sdk/scripts/unasync.py. Do not edit.
from __future__ import annotations

import uuid
from collections.abc import Iterator
from pathlib import Path
from time import monotonic
from urllib.parse import parse_qs, urlsplit

import pytest
from reflex_build_sdk import (
    APIConnectionError,
    DeploymentFailedError,
    DeploymentTimeoutError,
    PermissionDeniedError,
    ReflexBuild,
)
from reflex_build_sdk.transports import Request, Response, TransportError
from reflex_build_sdk.types import DeploymentReport, MachineSize, Region

from tests.units.reflex_build_sdk.conftest import (
    MockAPI,
    MockTransport,
    json_body,
    reply,
)

APP_ID = "5f0c5e0e-8f6a-4d57-9a55-3c1c1d7b6a01"
FIRST_ID = "0e7b9d2c-5a4f-4c3b-8e1d-6f2a9b8c7d10"
SECOND_ID = "7a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d"
DEPLOYMENT_PATH = f"/api/v1/deployments/{FIRST_ID}"
STORAGE = "https://storage.example.com"

PENDING_REPORT = {
    "status": "Pending",
    "code": None,
    "fault": None,
    "reason": "",
    "guidance": "",
    "build_log_excerpt": None,
}


@pytest.fixture
def client(mock_api: MockAPI) -> Iterator[ReflexBuild]:
    """A client talking to the mock API.

    Args:
        mock_api: The mock API.

    Yields:
        The client.
    """
    with ReflexBuild(token="test-token", transport=MockTransport(mock_api)) as client:
        yield client


@pytest.fixture
def archives(tmp_path: Path) -> tuple[Path, Path]:
    """A build's backend and frontend archives.

    Args:
        tmp_path: A temporary directory for the archives.

    Returns:
        The backend and frontend archive paths.
    """
    backend = tmp_path / "backend.zip"
    frontend = tmp_path / "frontend.zip"
    backend.write_bytes(b"b" * 300_000)
    frontend.write_bytes(b"f" * 1_000)
    return backend, frontend


def _reservation(deployment_id: str) -> dict:
    return {
        "deployment_id": deployment_id,
        "backend": {
            "url": f"{STORAGE}/{deployment_id}/backend.zip?X-Amz-Signature=s",
            "headers": {"Content-Type": "application/zip"},
        },
        "frontend": {
            "url": f"{STORAGE}/{deployment_id}/frontend.zip?X-Amz-Signature=s",
            "headers": {"Content-Type": "application/zip"},
        },
        "expires_in": 1800,
    }


def _add_storage(mock_api: MockAPI, deployment_id: str, *handlers) -> None:
    for archive in ("backend.zip", "frontend.zip"):
        mock_api.add("PUT", f"/{deployment_id}/{archive}", *(handlers or (reply(200),)))


def test_create(client: ReflexBuild, mock_api: MockAPI, archives: tuple[Path, Path]):
    mock_api.add(
        "POST", "/api/v1/deployments/reserve", reply(200, json=_reservation(FIRST_ID))
    )
    _add_storage(mock_api, FIRST_ID)
    mock_api.add("POST", "/api/v1/deployments", reply(201, json=FIRST_ID))
    progress = []
    backend, frontend = archives

    deployment_id = client.deployments.create(
        APP_ID,
        backend=backend,
        frontend=str(frontend),
        regions={"sjc": 2},
        secrets={"KEY": "value"},
        packages=["libpq-dev"],
        strategy="rolling",
        python_version="3.13.1",
        on_upload_progress=lambda sent, total: progress.append((sent, total)),
    )

    assert deployment_id == uuid.UUID(FIRST_ID)
    reserve, *uploads, submit = mock_api.requests
    assert json_body(reserve) == {
        "app_id": APP_ID,
        "backend_size": 300_000,
        "frontend_size": 1_000,
    }
    for upload in uploads:
        assert upload.method == "PUT"
        assert "X-API-TOKEN" not in upload.headers
        assert upload.headers["Content-Type"] == "application/zip"
    assert {upload.url: upload.headers["Content-Length"] for upload in uploads} == {
        _reservation(FIRST_ID)["backend"]["url"]: "300000",
        _reservation(FIRST_ID)["frontend"]["url"]: "1000",
    }
    assert mock_api.uploads == {
        _reservation(FIRST_ID)["backend"]["url"]: backend.read_bytes(),
        _reservation(FIRST_ID)["frontend"]["url"]: frontend.read_bytes(),
    }
    assert progress[-1] == (301_000, 301_000)
    assert [sent for sent, _ in progress] == sorted(sent for sent, _ in progress)
    assert submit.headers["Content-Type"] == "application/x-www-form-urlencoded"
    assert isinstance(submit.content, bytes)
    form = {
        name: values[0] for name, values in parse_qs(submit.content.decode()).items()
    }
    assert form.pop("reflex_build_sdk_version")
    form.pop("reflex_version", None)
    assert form == {
        "reflex_hosting_cli_version": "0.1.71",
        "stored_build_id": FIRST_ID,
        "app_id": APP_ID,
        "regions": '{"sjc": 2}',
        "secrets": '{"KEY": "value"}',
        "packages": '["libpq-dev"]',
        "deployment_strategy": "rolling",
        "python_version": "3.13.1",
    }


@pytest.mark.parametrize(
    "sizing",
    [{"cpu": 2.0}, {"ram_mb": 4096}, {"vm_type": "c2m4", "cpu": 2.0, "ram_mb": 4096}],
)
def test_create_checks_sizing_before_uploading(
    client: ReflexBuild,
    mock_api: MockAPI,
    archives: tuple[Path, Path],
    sizing: dict,
):
    backend, frontend = archives
    with pytest.raises(ValueError, match="vm_type, or both cpu and ram_mb"):
        client.deployments.create(APP_ID, backend=backend, frontend=frontend, **sizing)
    assert not mock_api.requests


def test_create_uploads_with_the_client_timeout(
    mock_api: MockAPI, archives: tuple[Path, Path]
):
    mock_api.add(
        "POST", "/api/v1/deployments/reserve", reply(200, json=_reservation(FIRST_ID))
    )
    _add_storage(mock_api, FIRST_ID)
    mock_api.add("POST", "/api/v1/deployments", reply(201, json=FIRST_ID))
    backend, frontend = archives
    with ReflexBuild(
        token="test-token", transport=MockTransport(mock_api), timeout=7.0
    ) as client:
        client.deployments.create(APP_ID, backend=backend, frontend=frontend)
    uploads = [request for request in mock_api.requests if request.method == "PUT"]
    assert len(uploads) == 2
    assert all(upload.timeout == pytest.approx(7.0) for upload in uploads)


def test_create_reserves_again_when_upload_urls_expire(
    client: ReflexBuild, mock_api: MockAPI, archives: tuple[Path, Path]
):
    mock_api.add(
        "POST",
        "/api/v1/deployments/reserve",
        reply(200, json=_reservation(FIRST_ID)),
        reply(200, json=_reservation(SECOND_ID)),
    )
    _add_storage(
        mock_api, FIRST_ID, reply(403, text="<Error>Request has expired</Error>")
    )
    _add_storage(mock_api, SECOND_ID)
    mock_api.add("POST", "/api/v1/deployments", reply(201, json=SECOND_ID))
    backend, frontend = archives

    deployment_id = client.deployments.create(
        APP_ID, backend=backend, frontend=frontend
    )

    assert deployment_id == uuid.UUID(SECOND_ID)
    submit = mock_api.requests[-1]
    assert isinstance(submit.content, bytes)
    assert parse_qs(submit.content.decode())["stored_build_id"] == [SECOND_ID]


def test_create_gives_up_when_upload_urls_keep_expiring(
    client: ReflexBuild, mock_api: MockAPI, archives: tuple[Path, Path]
):
    mock_api.add(
        "POST",
        "/api/v1/deployments/reserve",
        reply(200, json=_reservation(FIRST_ID)),
        reply(200, json=_reservation(SECOND_ID)),
    )
    _add_storage(mock_api, FIRST_ID, reply(403))
    _add_storage(mock_api, SECOND_ID, reply(403))
    backend, frontend = archives

    with pytest.raises(PermissionDeniedError):
        client.deployments.create(APP_ID, backend=backend, frontend=frontend)
    assert not [r for r in mock_api.requests if r.url.endswith("/deployments")]


def test_create_does_not_retry_a_refused_reservation(
    client: ReflexBuild, mock_api: MockAPI, archives: tuple[Path, Path]
):
    mock_api.add(
        "POST",
        "/api/v1/deployments/reserve",
        reply(403, json={"detail": "user lacking deploy permission"}),
    )
    backend, frontend = archives

    with pytest.raises(PermissionDeniedError, match="lacking deploy permission"):
        client.deployments.create(APP_ID, backend=backend, frontend=frontend)
    assert len(mock_api.requests) == 1


def test_create_upload_connection_error(
    client: ReflexBuild, mock_api: MockAPI, archives: tuple[Path, Path]
):
    def drop(request: Request) -> Response:
        msg = "connection reset"
        raise TransportError(msg, request=request, sent=True)

    mock_api.add(
        "POST", "/api/v1/deployments/reserve", reply(200, json=_reservation(FIRST_ID))
    )
    _add_storage(mock_api, FIRST_ID, drop)
    backend, frontend = archives

    with pytest.raises(APIConnectionError, match="connection reset"):
        client.deployments.create(APP_ID, backend=backend, frontend=frontend)


@pytest.mark.parametrize(
    ("kwargs", "query"),
    [
        (
            {},
            {
                "app_name": ["dashboard"],
                "regions": [""],
                "vmtype": [""],
                "hostname": [""],
            },
        ),
        (
            {"regions": {"sjc": 2}, "vm_type": "c2m4", "hostname": "dash.reflex.run"},
            {
                "app_name": ["dashboard"],
                "regions": ['{"sjc": 2}'],
                "vmtype": ["c2m4"],
                "hostname": ["dash.reflex.run"],
            },
        ),
        (
            {"cpu": 2.0, "ram_mb": 4096},
            {
                "app_name": ["dashboard"],
                "regions": [""],
                "vmtype": [""],
                "hostname": [""],
                "cpu": ["2.0"],
                "ram_mb": ["4096"],
            },
        ),
    ],
)
def test_check(client: ReflexBuild, mock_api: MockAPI, kwargs: dict, query: dict):
    project_id = "b3c1e3f2-2d0a-4d8e-9a0e-7f7a1c2d3e4f"
    mock_api.add("GET", "/api/v1/deployments/validate_cli", reply(200, json=None))
    client.deployments.check(
        APP_ID, app_name="dashboard", project_id=project_id, **kwargs
    )
    (request,) = mock_api.requests
    sent = parse_qs(urlsplit(request.url).query, keep_blank_values=True)
    assert sent == {"app_id": [APP_ID], "project_id": [project_id], **query}


def test_status(client: ReflexBuild, mock_api: MockAPI):
    mock_api.add(
        "GET", f"{DEPLOYMENT_PATH}/status", reply(200, json="pending worker...")
    )
    assert client.deployments.status(FIRST_ID) == "pending worker..."


def test_report(client: ReflexBuild, mock_api: MockAPI):
    body = {
        "status": "Failed",
        "code": "build_failed",
        "fault": "customer",
        "reason": "the build failed",
        "guidance": "Your app failed to build.",
        "build_log_excerpt": "ModuleNotFoundError: foo",
        "build_log_unreadable": False,
    }
    mock_api.add("GET", f"{DEPLOYMENT_PATH}/failure", reply(200, json=body))
    assert client.deployments.report(FIRST_ID) == DeploymentReport(**body)


def test_build_logs(client: ReflexBuild, mock_api: MockAPI):
    mock_api.add("GET", f"{DEPLOYMENT_PATH}/build/logs", reply(200, json="step 1\n"))
    assert client.deployments.build_logs(FIRST_ID) == "step 1\n"


def _statuses(mock_api: MockAPI, *messages: str) -> None:
    mock_api.add(
        "GET",
        f"{DEPLOYMENT_PATH}/status",
        *(reply(200, json=message) for message in messages),
    )


def _reports(mock_api: MockAPI, *statuses: str, **fields) -> None:
    mock_api.add(
        "GET",
        f"{DEPLOYMENT_PATH}/failure",
        *(
            reply(200, json={**PENDING_REPORT, "status": status, **fields})
            for status in statuses
        ),
    )


def test_wait_until_live(client: ReflexBuild, mock_api: MockAPI):
    _statuses(
        mock_api,
        "pending worker...",
        "pending worker...",
        "Building backend application...",
        "Deployment completed successfully! app running at https://my-app.reflex.run",
    )
    _reports(mock_api, "Running")
    messages = []
    report = client.deployments.wait(
        FIRST_ID, poll_interval=0, on_status=messages.append
    )
    assert report.status == "Running"
    assert messages == [
        "pending worker...",
        "Building backend application...",
        "Deployment completed successfully! app running at https://my-app.reflex.run",
    ]


def test_wait_raises_on_failure(client: ReflexBuild, mock_api: MockAPI):
    _statuses(
        mock_api,
        f"failed: build error | run reflex cloud apps build-logs {FIRST_ID} for logs",
    )
    _reports(
        mock_api,
        "Failed",
        code="build_failed",
        reason="the build failed",
        build_log_excerpt="ModuleNotFoundError: foo",
    )
    with pytest.raises(
        DeploymentFailedError, match="failed: the build failed"
    ) as exc_info:
        client.deployments.wait(uuid.UUID(FIRST_ID), poll_interval=0)
    assert exc_info.value.deployment_id == uuid.UUID(FIRST_ID)
    assert exc_info.value.report.build_log_excerpt == "ModuleNotFoundError: foo"


@pytest.mark.parametrize("message", ["Rejected", "cancelled", "Deployment error: boom"])
def test_wait_raises_on_messages_ending_a_deployment(
    client: ReflexBuild, mock_api: MockAPI, message: str
):
    _statuses(mock_api, message)
    _reports(mock_api, "Rejected")
    with pytest.raises(DeploymentFailedError):
        client.deployments.wait(FIRST_ID, poll_interval=0)


def test_wait_returns_when_awaiting_approval(client: ReflexBuild, mock_api: MockAPI):
    _statuses(mock_api, "AwaitingApproval")
    _reports(mock_api, "AwaitingApproval")
    report = client.deployments.wait(FIRST_ID, poll_interval=0)
    assert report.status == "AwaitingApproval"


def test_wait_trusts_the_recorded_state_when_the_message_is_stale(
    client: ReflexBuild, mock_api: MockAPI
):
    stale = "bad response: could not read the deployment status; check the dashboard"
    _statuses(mock_api, stale, stale)
    _reports(mock_api, "Pending", "Running")
    report = client.deployments.wait(FIRST_ID, poll_interval=0)
    assert report.status == "Running"
    assert len([r for r in mock_api.requests if r.url.endswith("/failure")]) == 2


def test_wait_checks_the_recorded_state_periodically(
    client: ReflexBuild, mock_api: MockAPI, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        "reflex_build_sdk._sync.resources.deployments._REPORT_EVERY_POLLS", 3
    )
    # A running deployment is not live until its message says so.
    _statuses(mock_api, "Waiting for backend to be ready...")
    _reports(mock_api, "Running", "Superseded")
    with pytest.raises(DeploymentFailedError):
        client.deployments.wait(FIRST_ID, poll_interval=0)
    assert len([r for r in mock_api.requests if r.url.endswith("/status")]) == 6


def test_wait_stops_waiting_at_the_timeout(client: ReflexBuild, mock_api: MockAPI):
    _statuses(mock_api, "Building backend application...")
    started = monotonic()
    with pytest.raises(DeploymentTimeoutError):
        client.deployments.wait(FIRST_ID, timeout=0.05, poll_interval=60)
    # The last sleep is cut short at the deadline instead of lasting a whole interval.
    assert monotonic() - started < 5


def test_wait_timeout(client: ReflexBuild, mock_api: MockAPI):
    _statuses(mock_api, "Building backend application...")
    with pytest.raises(DeploymentTimeoutError, match="Building backend application"):
        client.deployments.wait(FIRST_ID, timeout=0, poll_interval=0)


def test_set_description(client: ReflexBuild, mock_api: MockAPI):
    mock_api.add(
        "POST",
        f"/api/v1/apps/{APP_ID}/deployments/{FIRST_ID}/description",
        reply(200, json=None),
    )
    client.deployments.set_description(APP_ID, FIRST_ID, "release 2")
    assert json_body(mock_api.requests[0]) == {"description": "release 2"}


def test_regions_and_vm_types_need_no_token(mock_api: MockAPI):
    mock_api.add(
        "GET",
        "/api/v1/deployments/regions",
        reply(200, json=[{"id": APP_ID, "name": "San Jose", "code": "sjc"}]),
    )
    mock_api.add(
        "GET",
        "/api/v1/deployments/vm_types",
        reply(
            200,
            json=[
                {
                    "id": "c1m1",
                    "name": "Single CPU Small",
                    "cpu": 1.0,
                    "ram": 1.024,
                    "cpu_kind": "SHARED",
                }
            ],
        ),
    )
    with ReflexBuild(transport=MockTransport(mock_api)) as client:
        assert client.deployments.regions() == [
            Region(id=uuid.UUID(APP_ID), name="San Jose", code="sjc")
        ]
        assert client.deployments.vm_types() == [
            MachineSize(
                id="c1m1",
                name="Single CPU Small",
                cpu=1.0,
                ram=1.024,
                cpu_kind="SHARED",
            )
        ]
    assert all("X-API-TOKEN" not in request.headers for request in mock_api.requests)
