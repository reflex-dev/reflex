"""The build upload protocol and status reading shared by the sync and async clients."""

from __future__ import annotations

import asyncio
import threading
import uuid
from collections.abc import AsyncIterator, Callable, Iterator, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from reflex_sdk._base import connection_error, user_agent
from reflex_sdk._errors import status_error_from_response
from reflex_sdk.transports._base import Request, Response, TransportError

if TYPE_CHECKING:
    from reflex_sdk.transports._base import AsyncTransport, Transport

# The deployment protocol these clients speak: build archives uploaded to storage
# before the deployment is submitted. The control plane gates submissions on it
# under the hosting CLI's version field, and 0.1.71 is the first CLI release that
# speaks it.
DEPLOY_PROTOCOL_VERSION = "0.1.71"

# Archives are read and sent 256 KiB at a time, so memory use stays flat whatever
# their size, and upload progress is reported that often.
UPLOAD_CHUNK_SIZE = 256 * 1024

# How many times the archives are uploaded before giving up. The signed upload URLs
# expire 30 minutes after they are reserved, and a second reservation recovers
# from an upload that outlasted them.
UPLOAD_ATTEMPTS = 2

# Called with the bytes uploaded so far and the total, across both archives.
ProgressCallback = Callable[[int, int], None]

Outcome = Literal["succeeded", "failed", "awaiting_approval"]


@dataclass(frozen=True, slots=True, kw_only=True)
class UploadTarget:
    """Where to upload one archive."""

    # The signed URL to PUT the archive to.
    url: str
    # Headers the signature covers, which the upload must send.
    headers: dict[str, str]


@dataclass(frozen=True, slots=True, kw_only=True)
class UploadReservation:
    """A deployment id, and where its build archives go."""

    deployment_id: uuid.UUID
    backend: UploadTarget
    frontend: UploadTarget


# Status messages the approval flow publishes when a build never runs, and the one
# for a deployment cancelled mid-flight. They carry no error wording.
_FAILED_STATUS_MESSAGES = frozenset({"Rejected", "Expired", "Superseded", "cancelled"})
_FAILURE_MARKERS = ("error", "unable to find status for given id")


def status_message_outcome(message: str) -> Outcome | None:
    """Read whether a deployment status message reports a final outcome.

    The message is free text written by the deployment pipeline; these are the
    markers the control plane documents for it.

    Args:
        message: The status message.

    Returns:
        The outcome, or None while the deployment is in progress or the message
        does not say.
    """
    if "completed successfully" in message:
        return "succeeded"
    if message == "AwaitingApproval":
        return "awaiting_approval"
    if message in _FAILED_STATUS_MESSAGES or any(
        marker in message for marker in _FAILURE_MARKERS
    ):
        return "failed"
    return None


def report_outcome(status: str) -> Outcome | None:
    """Read whether a deployment's recorded status is final.

    Args:
        status: The status from the deployment's report.

    Returns:
        The outcome, or None while the deployment is pending.
    """
    if status == "Pending":
        return None
    if status == "Running":
        return "succeeded"
    if status == "AwaitingApproval":
        return "awaiting_approval"
    # Failed, Rejected, Expired, Superseded, and a deployment that was stopped,
    # paused or replaced, or ran out of memory, before its deploy finished.
    return "failed"


class _Progress:
    """Adds up the bytes uploaded across archives and reports the total."""

    def __init__(self, total: int, callback: ProgressCallback | None) -> None:
        self.sent = 0
        self.total = total
        self.callback = callback
        # Synchronous uploads report from worker threads.
        self.lock = threading.Lock()

    def advance(self, size: int) -> None:
        if self.callback is None:
            return
        with self.lock:
            self.sent += size
            self.callback(self.sent, self.total)


def _upload_request(
    target: UploadTarget,
    size: int,
    content: Iterator[bytes] | AsyncIterator[bytes],
    timeout: float | None,
) -> Request:
    return Request(
        method="PUT",
        url=target.url,
        # The signature covers the exact length, so it is sent rather than left to
        # chunked encoding. No access token: the signature is the credential.
        headers={
            **target.headers,
            "Content-Length": str(size),
            "User-Agent": user_agent(),
        },
        content=content,
        timeout=timeout,
    )


def _check_upload(response: Response) -> None:
    if not response.is_success:
        # A 403 from storage usually means the signed URL expired.
        raise status_error_from_response(response)


class _UploadAbandonedError(Exception):
    """Another archive's upload failed, so finishing this one buys nothing."""


class AsyncArchiveUploader:
    """Uploads a build's archives concurrently through an asynchronous transport."""

    def __init__(
        self,
        transport: AsyncTransport,
        on_progress: ProgressCallback | None,
        timeout: float | None,
    ) -> None:
        """Bind the uploader to a transport.

        Args:
            transport: The transport to send the uploads with.
            on_progress: Called with the bytes uploaded so far and the total.
            timeout: The timeout of each network operation in seconds, or None for
                the transport's defaults.
        """
        self._transport = transport
        self._on_progress = on_progress
        self._timeout = timeout

    async def upload(self, archives: Sequence[tuple[Path, int, UploadTarget]]) -> None:
        """Upload archives to their targets, stopping every upload if one fails.

        Args:
            archives: Each archive's path, size in bytes, and target.
        """
        progress = _Progress(sum(size for _, size, _ in archives), self._on_progress)
        tasks = [
            asyncio.ensure_future(self._put(path, size, target, progress))
            for path, size, target in archives
        ]
        try:
            await asyncio.gather(*tasks)
        except BaseException:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            raise

    async def _put(
        self, path: Path, size: int, target: UploadTarget, progress: _Progress
    ) -> None:
        try:
            response = await self._transport.send(
                _upload_request(
                    target, size, self._chunks(path, progress), self._timeout
                )
            )
        except TransportError as ex:
            raise connection_error(ex) from ex
        _check_upload(response)

    @staticmethod
    async def _chunks(path: Path, progress: _Progress) -> AsyncIterator[bytes]:
        # Local reads of this size return quickly enough not to hold up the loop.
        with path.open("rb") as archive:
            while chunk := archive.read(UPLOAD_CHUNK_SIZE):
                yield chunk
                progress.advance(len(chunk))


class ArchiveUploader:
    """Uploads a build's archives concurrently through a synchronous transport.

    Each archive is sent from its own thread, so the transport must be thread-safe,
    as the httpx transport is, and the progress callback is called from those threads.
    """

    def __init__(
        self,
        transport: Transport,
        on_progress: ProgressCallback | None,
        timeout: float | None,
    ) -> None:
        """Bind the uploader to a transport.

        Args:
            transport: The transport to send the uploads with.
            on_progress: Called with the bytes uploaded so far and the total.
            timeout: The timeout of each network operation in seconds, or None for
                the transport's defaults.
        """
        self._transport = transport
        self._on_progress = on_progress
        self._timeout = timeout

    def upload(self, archives: Sequence[tuple[Path, int, UploadTarget]]) -> None:
        """Upload archives to their targets, stopping every upload if one fails.

        Args:
            archives: Each archive's path, size in bytes, and target.

        Raises:
            BaseException: The first error an upload failed with.
        """
        progress = _Progress(sum(size for _, size, _ in archives), self._on_progress)
        abandoned = threading.Event()
        failures: list[BaseException] = []

        def put(path: Path, size: int, target: UploadTarget) -> None:
            try:
                self._put(path, size, target, progress, abandoned)
            except _UploadAbandonedError:
                pass
            except BaseException as ex:
                failures.append(ex)
                abandoned.set()

        with ThreadPoolExecutor(max_workers=len(archives)) as pool:
            for path, size, target in archives:
                pool.submit(put, path, size, target)
        if failures:
            raise failures[0]

    def _put(
        self,
        path: Path,
        size: int,
        target: UploadTarget,
        progress: _Progress,
        abandoned: threading.Event,
    ) -> None:
        try:
            response = self._transport.send(
                _upload_request(
                    target,
                    size,
                    self._chunks(path, progress, abandoned),
                    self._timeout,
                )
            )
        except TransportError as ex:
            if abandoned.is_set():
                raise _UploadAbandonedError from ex
            raise connection_error(ex) from ex
        _check_upload(response)

    @staticmethod
    def _chunks(
        path: Path, progress: _Progress, abandoned: threading.Event
    ) -> Iterator[bytes]:
        with path.open("rb") as archive:
            while chunk := archive.read(UPLOAD_CHUNK_SIZE):
                if abandoned.is_set():
                    raise _UploadAbandonedError
                yield chunk
                progress.advance(len(chunk))
