from __future__ import annotations

import dataclasses
import io
import json
import logging
import zipfile
from pathlib import Path

import pytest
from click.testing import CliRunner
from pytest_mock import MockFixture
from reflex_build_sdk import (
    AuthenticationError,
    SecurityReviewFailedError,
    SecurityReviewTimeoutError,
)
from reflex_build_sdk.types import SecurityReviewResult, SecurityViolation
from reflex_cli.v2.deployments import hosting_cli
from reflex_cli.v2.scan import _POLL_INTERVAL_SECONDS, _POLL_TIMEOUT_SECONDS

from .utils import api_error, as_click_command, fake_client

hosting_cli = as_click_command(hosting_cli)

runner = CliRunner()

_CLIENT = fake_client()

_RESULT = SecurityReviewResult(
    summary="Looks mostly fine.",
    violations=[
        SecurityViolation(
            rule_id="exposed-setter",
            category="security",
            file_path="app/state.py",
            line=12,
            severity="high",
            snippet="self.is_admin = value",
            message="Client can flip auth.",
            recommendation="Validate server-side.",
        )
    ],
)


def _write_app(directory: Path) -> None:
    """Write a minimal reviewable file plus a skipped directory."""
    (directory / "app.py").write_text("import reflex as rx\n")
    skipped = directory / ".web" / "nested"
    skipped.mkdir(parents=True)
    (skipped / "bundle.js").write_text("// build artifact\n")


def _mock_auth(mocker: MockFixture):
    """Patch the client lookup and hand back a client with a fresh API mock.

    Args:
        mocker: The pytest-mock fixture.

    Returns:
        The client the command under test will receive.
    """
    _CLIENT.api.reset_mock(return_value=True, side_effect=True)
    _CLIENT.api.security_reviews.submit.return_value = "job123"
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client", return_value=_CLIENT
    )
    return _CLIENT


def test_scan_success_with_violations(mocker: MockFixture, tmp_path: Path):
    """A completed review with findings prints them and exits non-zero by default."""
    _write_app(tmp_path)
    client = _mock_auth(mocker)
    client.api.security_reviews.wait.return_value = _RESULT

    result = runner.invoke(hosting_cli, ["scan", str(tmp_path)])

    assert result.exit_code == 1, result.output
    client.api.security_reviews.submit.assert_called_once()
    client.api.security_reviews.wait.assert_called_once()
    assert client.api.security_reviews.wait.call_args.args[0] == "job123"


def test_scan_zip_excludes_build_dirs(mocker: MockFixture, tmp_path: Path):
    """The uploaded archive contains source but not skipped build directories."""
    _write_app(tmp_path)
    client = _mock_auth(mocker)
    client.api.security_reviews.wait.return_value = _RESULT
    submitted: list[bytes] = []

    def capture(archive: Path) -> str:
        # The archive is a temporary file, gone by the time the command returns.
        submitted.append(Path(archive).read_bytes())
        return "job123"

    client.api.security_reviews.submit.side_effect = capture

    runner.invoke(hosting_cli, ["scan", str(tmp_path)])

    with zipfile.ZipFile(io.BytesIO(submitted[0])) as archive:
        names = archive.namelist()
    assert "app.py" in names
    assert not any(".web" in name for name in names)


def test_scan_no_files(
    mocker: MockFixture, tmp_path: Path, caplog: pytest.LogCaptureFixture
):
    """An empty project errors out without contacting the server.

    Args:
        mocker: Pytest mocker fixture.
        tmp_path: Temporary directory path.
        caplog: Pytest log capture fixture.
    """
    client = _mock_auth(mocker)

    result = runner.invoke(hosting_cli, ["scan", str(tmp_path)])

    assert result.exit_code == 1
    client.api.security_reviews.submit.assert_not_called()
    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert len(errors) == 1


def test_scan_renders_findings_with_markup_chars(mocker: MockFixture, tmp_path: Path):
    """Findings whose text contains brackets render without crashing Rich."""
    _write_app(tmp_path)
    client = _mock_auth(mocker)
    client.api.security_reviews.wait.return_value = SecurityReviewResult(
        summary="Check [this] and config[key].",
        violations=[
            SecurityViolation(
                rule_id="exposed-setter",
                category="security",
                file_path="app/state[0].py",
                line=3,
                severity="critical",
                snippet="x = data[key]",
                message="Indexing data[key] is unsafe.",
                recommendation="Use data.get([key]).",
            )
        ],
    )

    result = runner.invoke(hosting_cli, ["scan", str(tmp_path), "--fail-on", "none"])

    assert result.exit_code == 0, result.output
    assert result.exception is None


def test_scan_clean_exits_zero(mocker: MockFixture, tmp_path: Path):
    """A review with no violations exits zero."""
    _write_app(tmp_path)
    client = _mock_auth(mocker)
    client.api.security_reviews.wait.return_value = SecurityReviewResult(
        summary="All good.", violations=[]
    )

    result = runner.invoke(hosting_cli, ["scan", str(tmp_path)])

    assert result.exit_code == 0, result.output


def test_scan_fail_on_none_exits_zero(mocker: MockFixture, tmp_path: Path):
    """With --fail-on none, findings are reported but the command exits zero."""
    _write_app(tmp_path)
    client = _mock_auth(mocker)
    client.api.security_reviews.wait.return_value = _RESULT

    result = runner.invoke(hosting_cli, ["scan", str(tmp_path), "--fail-on", "none"])

    assert result.exit_code == 0, result.output


def test_scan_fail_on_critical_ignores_high(mocker: MockFixture, tmp_path: Path):
    """--fail-on critical does not trip on a high-severity finding."""
    _write_app(tmp_path)
    client = _mock_auth(mocker)
    client.api.security_reviews.wait.return_value = _RESULT

    result = runner.invoke(
        hosting_cli, ["scan", str(tmp_path), "--fail-on", "critical"]
    )

    assert result.exit_code == 0, result.output


def test_scan_json_output(mocker: MockFixture, tmp_path: Path):
    """--json prints the raw result payload."""
    _write_app(tmp_path)
    client = _mock_auth(mocker)
    client.api.security_reviews.wait.return_value = _RESULT
    result = runner.invoke(
        hosting_cli, ["scan", str(tmp_path), "--json", "--fail-on", "none"]
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == dataclasses.asdict(_RESULT)


def test_scan_waits_for_the_review(mocker: MockFixture, tmp_path: Path):
    """The CLI hands the wait to the SDK with a timeout it chooses."""
    _write_app(tmp_path)
    client = _mock_auth(mocker)
    client.api.security_reviews.wait.return_value = _RESULT

    result = runner.invoke(hosting_cli, ["scan", str(tmp_path), "--fail-on", "none"])

    assert result.exit_code == 0, result.output
    # Polling is the SDK's; the CLI states the window it is willing to wait.
    assert client.api.security_reviews.wait.call_args.kwargs == {
        "timeout": _POLL_TIMEOUT_SECONDS,
        "poll_interval": _POLL_INTERVAL_SECONDS,
    }


def test_scan_server_error(
    mocker: MockFixture, tmp_path: Path, caplog: pytest.LogCaptureFixture
):
    """An errored job surfaces the server error and exits non-zero.

    Args:
        mocker: Pytest mocker fixture.
        tmp_path: Temporary directory path.
        caplog: Pytest log capture fixture.
    """
    _write_app(tmp_path)
    client = _mock_auth(mocker)
    client.api.security_reviews.wait.side_effect = SecurityReviewFailedError(
        "job123", "Security review failed."
    )

    result = runner.invoke(hosting_cli, ["scan", str(tmp_path)])

    assert result.exit_code == 1
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert errors == ["security review job123 failed: Security review failed."]


def test_scan_submit_error(
    mocker: MockFixture, tmp_path: Path, caplog: pytest.LogCaptureFixture
):
    """A refusal on submit surfaces the server detail verbatim.

    Args:
        mocker: Pytest mocker fixture.
        tmp_path: Temporary directory path.
        caplog: Pytest log capture fixture.
    """
    _write_app(tmp_path)
    client = _mock_auth(mocker)
    client.api.security_reviews.submit.side_effect = api_error(403, "server says no")

    result = runner.invoke(hosting_cli, ["scan", str(tmp_path)])

    assert result.exit_code == 1
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert errors == ["server says no"]


def test_scan_not_authenticated(
    mocker: MockFixture, tmp_path: Path, caplog: pytest.LogCaptureFixture
):
    """An unauthenticated client produces the standard login prompt.

    Args:
        mocker: Pytest mocker fixture.
        tmp_path: Temporary directory path.
        caplog: Pytest log capture fixture.
    """
    _write_app(tmp_path)
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        side_effect=AuthenticationError(
            "401", response=api_error(401, "expired").response, detail="expired"
        ),
    )

    result = runner.invoke(hosting_cli, ["scan", str(tmp_path)])

    assert result.exit_code == 1
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert errors == ["You are not authenticated. Run `reflex login` to authenticate."]


def test_scan_times_out(
    mocker: MockFixture, tmp_path: Path, caplog: pytest.LogCaptureFixture
):
    """A review still running when the wait ends says to try again later.

    Args:
        mocker: Pytest mocker fixture.
        tmp_path: Temporary directory path.
        caplog: Pytest log capture fixture.
    """
    _write_app(tmp_path)
    client = _mock_auth(mocker)
    client.api.security_reviews.wait.side_effect = SecurityReviewTimeoutError("slow")

    result = runner.invoke(hosting_cli, ["scan", str(tmp_path)])

    assert result.exit_code == 1
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert errors == ["Security review timed out. Try again later."]
