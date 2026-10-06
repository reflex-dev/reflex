"""Audit saved observations without equating completed probes with passing behavior."""

import json
from pathlib import Path


def read(path: Path):
    """Read one JSON observation file.

    Args:
        path: The neutral observation file.

    Returns:
        The decoded diagnostic data.
    """
    return json.loads(path.read_text())


def main() -> None:
    """Assert the observed contrast and record every failed request separately."""
    root = Path.cwd()
    full = read(root / "logs/auth-stable-browser.json")
    focus = read(root / "logs/focused-reload.json")
    alpha = read(root / "narrow-alpha/logs/reload-alpha.json")
    stable = read(root / "narrow-stable/logs/reload-stable.json")
    minimum = read(root / "logs/auth-min-default-browser.json")
    assert len(full) == 22 and all(case["passed"] for case in full)
    assert len(focus) == 5 and all(case["passed"] for case in focus)
    assert len(alpha) == len(stable) == 3
    for cases, restored in ((alpha, False), (stable, True)):
        for case in cases:
            assert case["completed"]
            assert case["authenticated_dashboard"]["#async-view"] == "async-admin-data"
            assert case["async_restored"] is restored
            assert case["page_errors"] == case["http_errors"] == []
            for observation in case["after_reload"]:
                fields = observation["fields"]
                assert fields["#sync-view"] == "computed:initial-secret"
                assert fields["#user-name"] == "Alice Admin"
                expected = "async-admin-data" if restored else "async-admin-placeholder"
                assert fields["#async-view"] == expected
            assert case["after_reload"][-1]["elapsed_seconds"] >= 15
    assert len(minimum) == 4
    assert [case["case"] for case in minimum if not case["passed"]] == [
        "iframe_pending_event_replay"
    ]
    failed = minimum[-1]
    assert failed["frame_observations"][0]["url"].endswith("/login?redirect_to=%2F")
    assert "profile_state.reveal" in failed["frame_observations"][0]["pending_event"]
    diagnostics = {
        "console_errors": {
            case["case"]: [
                message["text"]
                for message in case["console"]
                if message["type"] == "error"
            ]
            for case in full
            if any(message["type"] == "error" for message in case["console"])
        },
        "page_errors": {
            case["case"]: case["page_errors"] for case in full if case["page_errors"]
        },
        "http_errors": {
            case["case"]: [
                response for response in case["responses"] if response["status"] >= 400
            ]
            for case in full
            if any(response["status"] >= 400 for response in case["responses"])
        },
        "failed_requests": {
            case["case"]: case["failed_requests"]
            for case in full
            if case["failed_requests"]
        },
    }
    result = {
        "observation_audit": "passed",
        "stable_full_auth_functional": {"passed": 22, "total": 22},
        "stable_full_auth_diagnostics": diagnostics,
        "stable_focus_functional": {"passed": 5, "total": 5},
        "tiny_alpha_functional": {"passed": 0, "total": 3},
        "tiny_stable_functional": {"passed": 3, "total": 3},
        "stable_auth_min_functional": {"passed": 3, "total": 4},
        "stable_auth_min_failure": failed,
    }
    (root / "logs/audit-results.json").write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                key: value
                for key, value in result.items()
                if key.endswith("functional") or key == "observation_audit"
            }
        )
    )


if __name__ == "__main__":
    main()
