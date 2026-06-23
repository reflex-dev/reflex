from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

from click.testing import CliRunner
from pytest_mock import MockFixture
from reflex_cli.utils import hosting
from reflex_cli.utils.exceptions import NotAuthenticatedError
from reflex_cli.v2.deployments import hosting_cli
from typer.main import Typer, get_command

hosting_cli = (
    get_command(hosting_cli) if isinstance(hosting_cli, Typer) else hosting_cli
)

runner = CliRunner()

_CLIENT = hosting.AuthenticatedClient(token="fake-token", validated_data={"foo": "bar"})

_RESULT = {
    "summary": "Looks mostly fine.",
    "violations": [
        {
            "rule_id": "exposed-setter",
            "category": "security",
            "file_path": "app/state.py",
            "line": 12,
            "severity": "high",
            "snippet": "self.is_admin = value",
            "message": "Client can flip auth.",
            "recommendation": "Validate server-side.",
        }
    ],
}


def _write_app(directory: Path) -> None:
    """Write a minimal reviewable file plus a skipped directory."""
    (directory / "app.py").write_text("import reflex as rx\n")
    skipped = directory / ".web" / "nested"
    skipped.mkdir(parents=True)
    (skipped / "bundle.js").write_text("// build artifact\n")


def _mock_auth(mocker: MockFixture) -> None:
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client", return_value=_CLIENT
    )


def test_scan_success_with_violations(mocker: MockFixture, tmp_path: Path):
    """A completed review with findings prints them and exits non-zero by default."""
    _write_app(tmp_path)
    _mock_auth(mocker)
    mock_submit = mocker.patch(
        "reflex_cli.utils.hosting.submit_security_review", return_value="job123"
    )
    mock_get = mocker.patch(
        "reflex_cli.utils.hosting.get_security_review",
        return_value={"job_id": "job123", "status": "complete", "result": _RESULT},
    )

    result = runner.invoke(hosting_cli, ["scan", str(tmp_path)])

    assert result.exit_code == 1, result.output
    mock_submit.assert_called_once()
    assert mock_submit.call_args.kwargs["client"] == _CLIENT
    mock_get.assert_called_once_with(job_id="job123", client=_CLIENT)


def test_scan_zip_excludes_build_dirs(mocker: MockFixture, tmp_path: Path):
    """The uploaded archive contains source but not skipped build directories."""
    _write_app(tmp_path)
    _mock_auth(mocker)
    mock_submit = mocker.patch(
        "reflex_cli.utils.hosting.submit_security_review", return_value="job123"
    )
    mocker.patch(
        "reflex_cli.utils.hosting.get_security_review",
        return_value={"job_id": "job123", "status": "complete", "result": _RESULT},
    )

    runner.invoke(hosting_cli, ["scan", str(tmp_path)])

    zip_bytes = mock_submit.call_args.kwargs["zip_bytes"]
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        names = archive.namelist()
    assert "app.py" in names
    assert not any(".web" in name for name in names)


def test_scan_no_files(mocker: MockFixture, tmp_path: Path):
    """An empty project errors out without contacting the server."""
    _mock_auth(mocker)
    mock_submit = mocker.patch("reflex_cli.utils.hosting.submit_security_review")
    mock_error = mocker.patch("reflex_cli.utils.console.error")

    result = runner.invoke(hosting_cli, ["scan", str(tmp_path)])

    assert result.exit_code == 1
    mock_submit.assert_not_called()
    mock_error.assert_called_once()


def test_scan_renders_findings_with_markup_chars(mocker: MockFixture, tmp_path: Path):
    """Findings whose text contains brackets render without crashing Rich."""
    _write_app(tmp_path)
    _mock_auth(mocker)
    mocker.patch(
        "reflex_cli.utils.hosting.submit_security_review", return_value="job123"
    )
    bracketed = {
        "summary": "Check [this] and config[key].",
        "violations": [
            {
                "rule_id": "exposed-setter",
                "category": "security",
                "file_path": "app/state[0].py",
                "line": 3,
                "severity": "critical",
                "snippet": "x = data[key]",
                "message": "Indexing data[key] is unsafe.",
                "recommendation": "Use data.get([key]).",
            }
        ],
    }
    mocker.patch(
        "reflex_cli.utils.hosting.get_security_review",
        return_value={"job_id": "job123", "status": "complete", "result": bracketed},
    )

    result = runner.invoke(hosting_cli, ["scan", str(tmp_path), "--fail-on", "none"])

    assert result.exit_code == 0, result.output
    assert result.exception is None


def test_scan_clean_exits_zero(mocker: MockFixture, tmp_path: Path):
    """A review with no violations exits zero."""
    _write_app(tmp_path)
    _mock_auth(mocker)
    mocker.patch(
        "reflex_cli.utils.hosting.submit_security_review", return_value="job123"
    )
    mocker.patch(
        "reflex_cli.utils.hosting.get_security_review",
        return_value={
            "job_id": "job123",
            "status": "complete",
            "result": {"summary": "All good.", "violations": []},
        },
    )

    result = runner.invoke(hosting_cli, ["scan", str(tmp_path)])

    assert result.exit_code == 0, result.output


def test_scan_fail_on_none_exits_zero(mocker: MockFixture, tmp_path: Path):
    """With --fail-on none, findings are reported but the command exits zero."""
    _write_app(tmp_path)
    _mock_auth(mocker)
    mocker.patch(
        "reflex_cli.utils.hosting.submit_security_review", return_value="job123"
    )
    mocker.patch(
        "reflex_cli.utils.hosting.get_security_review",
        return_value={"job_id": "job123", "status": "complete", "result": _RESULT},
    )

    result = runner.invoke(hosting_cli, ["scan", str(tmp_path), "--fail-on", "none"])

    assert result.exit_code == 0, result.output


def test_scan_fail_on_critical_ignores_high(mocker: MockFixture, tmp_path: Path):
    """--fail-on critical does not trip on a high-severity finding."""
    _write_app(tmp_path)
    _mock_auth(mocker)
    mocker.patch(
        "reflex_cli.utils.hosting.submit_security_review", return_value="job123"
    )
    mocker.patch(
        "reflex_cli.utils.hosting.get_security_review",
        return_value={"job_id": "job123", "status": "complete", "result": _RESULT},
    )

    result = runner.invoke(
        hosting_cli, ["scan", str(tmp_path), "--fail-on", "critical"]
    )

    assert result.exit_code == 0, result.output


def test_scan_json_output(mocker: MockFixture, tmp_path: Path):
    """--json prints the raw result payload."""
    _write_app(tmp_path)
    _mock_auth(mocker)
    mocker.patch(
        "reflex_cli.utils.hosting.submit_security_review", return_value="job123"
    )
    mocker.patch(
        "reflex_cli.utils.hosting.get_security_review",
        return_value={"job_id": "job123", "status": "complete", "result": _RESULT},
    )
    mock_print = mocker.patch("reflex_cli.utils.console.print")

    result = runner.invoke(
        hosting_cli, ["scan", str(tmp_path), "--json", "--fail-on", "none"]
    )

    assert result.exit_code == 0, result.output
    mock_print.assert_called_once_with(json.dumps(_RESULT))


def test_scan_polls_until_complete(mocker: MockFixture, tmp_path: Path):
    """Pending statuses are polled until the review finishes."""
    _write_app(tmp_path)
    _mock_auth(mocker)
    mocker.patch(
        "reflex_cli.utils.hosting.submit_security_review", return_value="job123"
    )
    mock_get = mocker.patch(
        "reflex_cli.utils.hosting.get_security_review",
        side_effect=[
            {"job_id": "job123", "status": "pending"},
            {"job_id": "job123", "status": "complete", "result": _RESULT},
        ],
    )
    mocker.patch("reflex_cli.v2.scan.time.sleep")

    result = runner.invoke(hosting_cli, ["scan", str(tmp_path), "--fail-on", "none"])

    assert result.exit_code == 0, result.output
    assert mock_get.call_count == 2


def test_scan_server_error(mocker: MockFixture, tmp_path: Path):
    """An errored job surfaces the server error and exits non-zero."""
    _write_app(tmp_path)
    _mock_auth(mocker)
    mocker.patch(
        "reflex_cli.utils.hosting.submit_security_review", return_value="job123"
    )
    mocker.patch(
        "reflex_cli.utils.hosting.get_security_review",
        return_value={
            "job_id": "job123",
            "status": "error",
            "error": "Security review failed.",
        },
    )
    mock_error = mocker.patch("reflex_cli.utils.console.error")

    result = runner.invoke(hosting_cli, ["scan", str(tmp_path)])

    assert result.exit_code == 1
    mock_error.assert_called_once_with(
        "Security review failed: Security review failed."
    )


def test_scan_submit_error(mocker: MockFixture, tmp_path: Path):
    """A SecurityReviewError on submit surfaces the server detail verbatim."""
    _write_app(tmp_path)
    _mock_auth(mocker)
    mocker.patch(
        "reflex_cli.utils.hosting.submit_security_review",
        side_effect=hosting.SecurityReviewError("server says no"),
    )
    mock_error = mocker.patch("reflex_cli.utils.console.error")

    result = runner.invoke(hosting_cli, ["scan", str(tmp_path)])

    assert result.exit_code == 1
    mock_error.assert_called_once_with("Security review failed: server says no")


def test_scan_not_authenticated(mocker: MockFixture, tmp_path: Path):
    """An unauthenticated client produces the standard login prompt."""
    _write_app(tmp_path)
    mocker.patch(
        "reflex_cli.utils.hosting.get_authenticated_client",
        side_effect=NotAuthenticatedError("not authenticated"),
    )
    mock_error = mocker.patch("reflex_cli.utils.console.error")

    result = runner.invoke(hosting_cli, ["scan", str(tmp_path)])

    assert result.exit_code == 1
    mock_error.assert_called_once_with(
        "You are not authenticated. Run `reflex login` to authenticate."
    )
