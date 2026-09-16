from __future__ import annotations

import asyncio
import threading
from pathlib import Path

import pytest
from reflex_sdk import InternalServerError, PermissionDeniedError
from reflex_sdk._deploy import (
    UPLOAD_CHUNK_SIZE,
    ArchiveUploader,
    AsyncArchiveUploader,
    UploadTarget,
    _Progress,
    _UploadAbandonedError,
    report_outcome,
    status_message_outcome,
)
from reflex_sdk.transports import Request, Response

from tests.units.reflex_sdk.conftest import reply


@pytest.mark.parametrize(
    ("message", "outcome"),
    [
        ("pending worker...", None),
        ("Building backend application...", None),
        ("deployment status: Pending", None),
        (
            "bad response: the deployment reports Running, but its status cache is unavailable",
            None,
        ),
        ("Deployment failed: boom", None),
        (
            "Deployment completed successfully! app running at https://a.reflex.run",
            "succeeded",
        ),
        ("AwaitingApproval", "awaiting_approval"),
        ("failed: build error | run reflex cloud apps build-logs x for logs", "failed"),
        ("Deployment error: the app ran out of memory", "failed"),
        ("deployment error: the build was rejected", "failed"),
        ("Internal server error occurred", "failed"),
        ("unable to find status for given id. could be an old deployment.", "failed"),
        ("Rejected", "failed"),
        ("Expired", "failed"),
        ("Superseded", "failed"),
        ("cancelled", "failed"),
    ],
)
def test_status_message_outcome(message: str, outcome: str | None):
    assert status_message_outcome(message) == outcome


@pytest.mark.parametrize(
    ("status", "outcome"),
    [
        ("Pending", None),
        ("Running", "succeeded"),
        ("AwaitingApproval", "awaiting_approval"),
        ("Failed", "failed"),
        ("Rejected", "failed"),
        ("Stopped", "failed"),
        ("Error: Out of Memory", "failed"),
    ],
)
def test_report_outcome(status: str, outcome: str | None):
    assert report_outcome(status) == outcome


def _archives(tmp_path: Path) -> list[tuple[Path, int, UploadTarget]]:
    archives = []
    for name, size in (("backend.zip", 3 * UPLOAD_CHUNK_SIZE), ("frontend.zip", 10)):
        path = tmp_path / name
        path.write_bytes(b"x" * size)
        target = UploadTarget(url=f"https://storage.example.com/{name}", headers={})
        archives.append((path, size, target))
    return archives


def test_upload_raises_the_first_failure(tmp_path: Path):
    class Storage:
        def send(self, request: Request) -> Response:
            if request.url.endswith("frontend.zip"):
                return reply(403)(request)
            assert not isinstance(request.content, bytes | None)
            for _ in request.content:  # pyright: ignore[reportGeneralTypeIssues]
                pass
            return reply(200)(request)

        def close(self) -> None:
            pass

    with pytest.raises(PermissionDeniedError):
        ArchiveUploader(Storage(), None).upload(_archives(tmp_path))


def test_upload_chunks_stop_once_abandoned(tmp_path: Path):
    (path, _, _), _ = _archives(tmp_path)
    abandoned = threading.Event()
    chunks = ArchiveUploader._chunks(path, _Progress(0, None), abandoned)
    next(chunks)
    # Another archive failed: the next chunk is not read.
    abandoned.set()
    with pytest.raises(_UploadAbandonedError):
        next(chunks)


def test_upload_reports_progress(tmp_path: Path):
    class Storage:
        def send(self, request: Request) -> Response:
            assert not isinstance(request.content, bytes | None)
            b"".join(request.content)  # pyright: ignore[reportArgumentType]
            return reply(200)(request)

        def close(self) -> None:
            pass

    progress = []
    ArchiveUploader(
        Storage(), lambda sent, total: progress.append((sent, total))
    ).upload(_archives(tmp_path))
    total = 3 * UPLOAD_CHUNK_SIZE + 10
    assert progress[-1] == (total, total)
    assert len(progress) == 4


async def test_async_upload_cancels_other_archives_after_a_failure(tmp_path: Path):
    backend_cancelled = asyncio.Event()

    class Storage:
        async def send(self, request: Request) -> Response:
            if request.url.endswith("frontend.zip"):
                return reply(500)(request)
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                backend_cancelled.set()
                raise
            return reply(200)(request)

        async def aclose(self) -> None:
            pass

    with pytest.raises(InternalServerError):
        await AsyncArchiveUploader(Storage(), None).upload(_archives(tmp_path))
    assert backend_cancelled.is_set()
