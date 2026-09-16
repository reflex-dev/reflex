# Generated from packages/reflex-sdk/src/reflex_sdk/_async/resources/security_reviews.py by packages/reflex-sdk/scripts/unasync.py. Do not edit.
"""The security review endpoints."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from time import monotonic
from typing import TYPE_CHECKING

from reflex_sdk._base import path_segment
from reflex_sdk._deploy import ArchiveUploader, UploadTarget
from reflex_sdk._errors import SecurityReviewFailedError, SecurityReviewTimeoutError
from reflex_sdk.types import SecurityReviewJob, SecurityReviewResult

if TYPE_CHECKING:
    from reflex_sdk._sync._client import ReflexCloud

# How often wait() checks a security review, in seconds.
_POLL_INTERVAL = 3.0


def _file_size(path: Path) -> int:
    # Synchronous on purpose: stat-ing a local file returns immediately.
    return path.stat().st_size


@dataclass(frozen=True, slots=True, kw_only=True)
class _UploadUrl:
    """Where to upload an archive for a security review."""

    # Names the uploaded archive when submitting the review.
    key: str
    url: str
    headers: dict[str, str]


class SecurityReviews:
    """Review an app's source code for security and logic issues."""

    def __init__(self, client: ReflexCloud) -> None:
        """Bind the resource to a client.

        Args:
            client: The client that sends the requests.
        """
        self._client = client

    def submit(self, archive: str | os.PathLike[str]) -> str:
        """Upload a zip of an app's source code and start reviewing it.

        Needs an organization on the Pro or Enterprise plan. Follow the review with
        ``wait``.

        Args:
            archive: The path of the zip file, at most 50 MB. Dependencies and
                build output are skipped, as are files over 1 MB.

        Returns:
            The id of the review.
        """
        path = Path(archive)
        size = _file_size(path)
        upload = self._client._request(
            "POST",
            "agents/security-review/jobs/upload-url",
            _UploadUrl,
            json={"content_length": size, "content_type": "application/zip"},
        )
        ArchiveUploader(self._client._transport, None, self._client._timeout).upload([
            (path, size, UploadTarget(url=upload.url, headers=upload.headers))
        ])
        job = self._client._request(
            "POST",
            "agents/security-review/jobs",
            dict[str, str],
            json={"key": upload.key},
        )
        return job["job_id"]

    def get(self, job_id: str) -> SecurityReviewJob:
        """Get a security review and, once it has finished, its result.

        Args:
            job_id: The review.

        Returns:
            The review.
        """
        return self._client._request(
            "GET",
            f"agents/security-review/jobs/{path_segment(job_id)}",
            SecurityReviewJob,
        )

    def wait(
        self,
        job_id: str,
        *,
        timeout: float | None = None,
        poll_interval: float = _POLL_INTERVAL,
    ) -> SecurityReviewResult:
        """Wait for a security review to finish.

        Args:
            job_id: The review.
            timeout: How long to wait, in seconds. Defaults to no limit.
            poll_interval: How long to wait between checks, in seconds.

        Returns:
            What the review found.

        Raises:
            SecurityReviewFailedError: If the review could not be completed.
            SecurityReviewTimeoutError: If the review was still running when
                ``timeout`` passed.
        """
        deadline = None if timeout is None else monotonic() + timeout
        while True:
            job = self.get(job_id)
            if job.status == "complete" and job.result is not None:
                return job.result
            if job.status == "error":
                raise SecurityReviewFailedError(job_id, job.error)
            delay = poll_interval
            if deadline is not None:
                remaining = deadline - monotonic()
                if remaining <= 0:
                    msg = f"security review {job_id} was still running"
                    raise SecurityReviewTimeoutError(msg)
                delay = min(delay, remaining)
            time.sleep(delay)
