from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from reflex_sdk import (
    AsyncReflexCloud,
    SecurityReviewFailedError,
    SecurityReviewTimeoutError,
)
from reflex_sdk.types import SecurityReviewJob, SecurityReviewResult, SecurityViolation

from tests.units.reflex_sdk.conftest import (
    AsyncMockTransport,
    MockAPI,
    json_body,
    reply,
)

JOB_ID = "9f8e7d6c5b4a"
JOB_PATH = f"/api/v1/agents/security-review/jobs/{JOB_ID}"
UPLOAD_URL = "https://storage.example.com/staging/review.zip?X-Amz-Signature=s"

VIOLATION = {
    "rule_id": "hardcoded-secret",
    "category": "security",
    "file_path": "app/app.py",
    "line": 12,
    "severity": "high",
    "snippet": "API_KEY = 'sk-live'",
    "message": "A secret is committed to the source.",
    "recommendation": "Read it from a secret instead.",
}


@pytest.fixture
async def client(mock_api: MockAPI) -> AsyncIterator[AsyncReflexCloud]:
    """A client talking to the mock API.

    Args:
        mock_api: The mock API.

    Yields:
        The client.
    """
    async with AsyncReflexCloud(
        token="test-token", transport=AsyncMockTransport(mock_api)
    ) as client:
        yield client


async def test_submit(client: AsyncReflexCloud, mock_api: MockAPI, tmp_path: Path):
    archive = tmp_path / "source.zip"
    archive.write_bytes(b"z" * 1234)
    mock_api.add(
        "POST",
        "/api/v1/agents/security-review/jobs/upload-url",
        reply(
            200,
            json={
                "key": "staging/security-review/u/abc.zip",
                "url": UPLOAD_URL,
                "headers": {"Content-Type": "application/zip"},
            },
        ),
    )
    mock_api.add("PUT", "/staging/review.zip", reply(200))
    mock_api.add(
        "POST",
        "/api/v1/agents/security-review/jobs",
        reply(202, json={"job_id": JOB_ID}),
    )

    assert await client.security_reviews.submit(archive) == JOB_ID

    upload_url, upload, submit = mock_api.requests
    assert json_body(upload_url) == {
        "content_length": 1234,
        "content_type": "application/zip",
    }
    assert upload.url == UPLOAD_URL
    assert upload.headers["Content-Length"] == "1234"
    assert upload.headers["Content-Type"] == "application/zip"
    assert "X-API-TOKEN" not in upload.headers
    assert mock_api.uploads[UPLOAD_URL] == archive.read_bytes()
    assert json_body(submit) == {"key": "staging/security-review/u/abc.zip"}


def _job(status: str, **fields) -> dict:
    return {"job_id": JOB_ID, "status": status, "result": None, "error": None, **fields}


async def test_get(client: AsyncReflexCloud, mock_api: MockAPI):
    mock_api.add(
        "GET",
        JOB_PATH,
        reply(
            200,
            json=_job(
                "complete", result={"summary": "One issue.", "violations": [VIOLATION]}
            ),
        ),
    )
    assert await client.security_reviews.get(JOB_ID) == SecurityReviewJob(
        job_id=JOB_ID,
        status="complete",
        result=SecurityReviewResult(
            summary="One issue.", violations=[SecurityViolation(**VIOLATION)]
        ),
    )


async def test_wait(client: AsyncReflexCloud, mock_api: MockAPI):
    mock_api.add(
        "GET",
        JOB_PATH,
        reply(200, json=_job("pending")),
        reply(200, json=_job("complete", result={"summary": "No issues."})),
    )
    result = await client.security_reviews.wait(JOB_ID, poll_interval=0)
    assert result == SecurityReviewResult(summary="No issues.")
    assert len(mock_api.requests) == 2


async def test_wait_raises_when_the_review_fails(
    client: AsyncReflexCloud, mock_api: MockAPI
):
    mock_api.add(
        "GET", JOB_PATH, reply(200, json=_job("error", error="Security review failed."))
    )
    with pytest.raises(
        SecurityReviewFailedError, match="Security review failed"
    ) as exc:
        await client.security_reviews.wait(JOB_ID, poll_interval=0)
    assert exc.value.job_id == JOB_ID


async def test_wait_timeout(client: AsyncReflexCloud, mock_api: MockAPI):
    mock_api.add("GET", JOB_PATH, reply(200, json=_job("pending")))
    with pytest.raises(SecurityReviewTimeoutError):
        await client.security_reviews.wait(JOB_ID, timeout=0.05, poll_interval=60)
