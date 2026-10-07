"""Wire models and contract assertions reused from the 2026-10-05 hosting campaign."""

import json

APP_ID = "11111111-1111-4111-8111-111111111111"

PROJECT_ID = "22222222-2222-4222-8222-222222222222"

ROLE_ID = "33333333-3333-4333-8333-333333333333"

DEPLOYMENT_ID = "44444444-4444-4444-8444-444444444444"

SECRET_VALUES = (
    "sentinel-only-for-fixture",
    "fixture=a=b",
    "file-only-value",
    "ignored-cli-value",
)

TIMESTAMP = "2026-10-05T12:34:56+00:00"


def deployment() -> dict:
    """Return a complete real SDK history wire record.

    Returns:
        A deployment record with nullable metadata and a VM type.
    """
    return {
        "id": DEPLOYMENT_ID,
        "url": "https://qa.example.test",
        "backend_url": "https://api.example.test",
        "status": "Running",
        "pause_reason": None,
        "failure_code": None,
        "failure_reason": None,
        "description": "Promoted release",
        "reflex_version": "0.10.0a1",
        "python_version": "3.13.7",
        "timestamp": TIMESTAMP,
        "last_updated": None,
        "deployment_user": None,
        "last_updated_by": None,
        "vm_type": {"id": "c2m4", "name": "Two cores / 4 GB", "cpu": 2.0, "ram": 4.0},
        "environment_id": None,
        "environment_name": "production",
        "promoted_from_deployment_id": None,
        "can_rollback": True,
    }


def app_document() -> dict:
    """Return a complete app with its production deployment wire aliases.

    Returns:
        An app inspect response.
    """
    return {
        "id": APP_ID,
        "name": "qa-app",
        "description": "Local fixture",
        "project_id": PROJECT_ID,
        "org_id": APP_ID,
        "provider": "gcp",
        "full_deploy": True,
        "min_instances": 1,
        "max_instances": 4,
        "disable_secrets": False,
        "weekly_report_enabled": False,
        "source_thread_id": None,
        "unreleased_provider": None,
        "has_deployments": True,
        "backend_url": "https://api.example.test",
        "any_environment_live": True,
        "any_environment_stopped": False,
        "any_environment_paused": False,
        "any_environment_credit_paused": False,
        "latest_deployment": {
            "id": DEPLOYMENT_ID,
            "url": "https://qa.example.test",
            "status": "Running",
            "pause_reason": None,
            "reflex_version": "0.10.0a1",
            "python_version": "3.13.7",
            "timestamp": TIMESTAMP,
            "regions": ["sjc", "lhr"],
            "vm_type_name": "Two cores / 4 GB",
            "vm_type_cpu": 2.0,
            "vm_type_ram": 4.0,
            "strategy": "rolling",
            "persist": True,
            "screenshot_uri": None,
            "last_updated": TIMESTAMP,
            "last_updated_by": {"id": APP_ID, "username": "qa@example.test"},
        },
    }


def verify(name: str, result: dict) -> None:
    """Verify CLI outputs against the new contracts and request boundaries.

    Args:
        name: Scenario name.
        result: CLI output and captured requests.
    """
    expected_failure = name in (
        "token-invalid-duration",
        "secrets-refused",
        "invalid-project",
        "missing-project",
    )
    assert (result["returncode"] != 0) == expected_failure, result
    requests = result["requests"]
    if name == "token-invalid-duration":
        assert not requests
    elif name == "invalid-project":
        assert len(requests) == 2
        assert requests[-1]["path"].endswith("not-a-project-uuid")
        assert "Fixture project does not exist" in result["stderr"]
        assert "Compiling:" not in result["stdout"]
    elif name == "missing-project":
        assert len(requests) == 2
        assert requests[-1]["path"].endswith(PROJECT_ID)
        assert "Fixture project does not exist" in result["stderr"]
        assert "Compiling:" not in result["stdout"]
    elif name == "secrets-refused":
        assert not result["stdout"].strip()
        assert "Fixture request is forbidden" in result["stderr"]
    elif name == "secrets-human":
        assert "Updated 2 secrets" in result["stdout"] + result["stderr"]
        assert "Not rebooting" in result["stdout"] + result["stderr"]
    elif name == "secrets-empty-list":
        assert "This app has no secrets" in result["stdout"]
    else:
        document = json.loads(result["stdout"])
        result["document"] = document
        if name.startswith("history"):
            if name == "history-empty":
                assert document == []
            else:
                assert document[0]["timestamp"] == TIMESTAMP
                assert document[0]["url"] == (
                    None if name == "history-nullable" else "https://qa.example.test"
                )
                assert document[0]["vm type"] == (
                    None if name == "history-nullable" else "Two cores / 4 GB"
                )
                assert document[0]["description"] == (
                    "" if name == "history-nullable" else "Promoted release"
                )
        elif name.startswith("inspect"):
            assert document["id"] == APP_ID
            if name == "inspect-nullable":
                assert document["latest_deployment"] is None
                assert document["backend_url"] is None
            else:
                nested = document["latest_deployment"]
                assert nested["timestamp"] == TIMESTAMP
                assert nested["persist"] is True
                assert nested["vm_type_name"] == "Two cores / 4 GB"
                assert "created_at" not in nested
                assert "persistent" not in nested
        elif name.startswith("token"):
            assert document["name"] == "server-renamed-token"
            assert document["expires_at"] == (
                None if name == "token-nullable" else "2026-10-12T12:34:56+00:00"
            )
            assert requests[-1]["body"] == {"name": "requested-token", "expiration": 90}
        elif name.startswith("secrets"):
            expected = (
                ["EMPTY", "FILE_ONLY"]
                if name == "secrets-envfile"
                else ["ALPHA", "EMPTY", "EQUALS"]
            )
            assert document == {
                "app_id": APP_ID,
                "updated": expected,
                "rebooted": name == "secrets-json",
            }
            sent = requests[-1]["body"]["secrets"]
            assert sorted(sent) == expected
            assert sent["EMPTY"] == ""
        elif name.startswith("permissions"):
            assert document == (
                []
                if name == "permissions-nullable"
                else ["can_deploy", "can_view_secret_keys"]
            )
    if name.startswith("secrets"):
        for value in SECRET_VALUES:
            assert value not in result["stdout"] + result["stderr"], result
