"""Test states for upload-related tests."""

from pathlib import Path
from typing import BinaryIO

import reflex as rx
from reflex.state import BaseState, State


class UploadBaseState(BaseState):
    """The base state for uploading a file."""


class UploadState(BaseState):
    """The base state for uploading a file."""

    async def handle_upload1(self, files: list[rx.UploadFile]):
        """Handle the upload of a file.

        Args:
            files: The uploaded files.
        """


class SubUploadState(UploadBaseState):
    """The test substate."""

    img: str

    async def handle_upload(self, files: list[rx.UploadFile]):
        """Handle the upload of a file.

        Args:
            files: The uploaded files.
        """


class _FileUploadMixin(BaseState, mixin=True):
    """Common fields and handlers for upload state tests."""

    img_list: list[str]
    _tmp_path: Path = Path()

    async def handle_upload2(self, files):
        """Handle the upload of a file.

        Args:
            files: The uploaded files.
        """

    async def multi_handle_upload(self, files: list[rx.UploadFile]):
        """Handle the upload of a file.

        Args:
            files: The uploaded files.
        """
        for file in files:
            upload_data = await file.read()
            assert file.name is not None
            outfile = self._tmp_path / file.name

            # Save the file.
            outfile.write_bytes(upload_data)

            # Update the img var.
            self.img_list.append(file.name)
            yield

    async def upload_alias_handler(self, uploads: list[rx.UploadFile]):
        """Handle uploaded files with a non-default parameter name."""
        self.img_list = [f"count:{len(uploads)}"]

    @rx.event(background=True)
    async def bg_upload(self, files: list[rx.UploadFile]):
        """Background task cannot be upload handler.

        Args:
            files: The uploaded files.
        """


class FileUploadState(_FileUploadMixin, State):
    """The base state for uploading a file."""


class _ChunkUploadMixin(BaseState, mixin=True):
    """Common fields and handlers for chunk upload tests."""

    chunk_records: list[str]
    completed_files: list[str]
    _tmp_path: Path = Path()

    @rx.event(background=True)
    async def chunk_handle_upload(self, chunk_iter: rx.UploadChunkIterator):
        """Handle a chunked upload in the background."""
        file_handles: dict[str, BinaryIO] = {}

        try:
            async for chunk in chunk_iter:
                outfile = self._tmp_path / chunk.filename
                outfile.parent.mkdir(parents=True, exist_ok=True)

                fh = file_handles.get(chunk.filename)
                if fh is None:
                    fh = outfile.open("r+b") if outfile.exists() else outfile.open("wb")
                    file_handles[chunk.filename] = fh

                fh.seek(chunk.offset)
                fh.write(chunk.data)

                async with self:
                    self.chunk_records.append(
                        f"{chunk.filename}:{chunk.offset}:{len(chunk.data)}:{chunk.content_type}"
                    )
        finally:
            for fh in file_handles.values():
                fh.close()

        async with self:
            self.completed_files = sorted(file_handles)

    async def chunk_handle_upload_not_background(
        self, chunk_iter: rx.UploadChunkIterator
    ):
        """Invalid streaming upload handler used for compile-time validation tests."""

    @rx.event(background=True)
    async def chunk_handle_upload_missing_annotation(self, chunk_iter):
        """Invalid streaming upload handler missing the iterator annotation."""

    @rx.event(background=True)
    async def chunk_handle_upload_alias(self, stream: rx.UploadChunkIterator):
        """Handle streamed upload chunks with a non-default parameter name."""
        chunk_count = 0
        async for _chunk in stream:
            chunk_count += 1

        async with self:
            self.completed_files = [f"chunks:{chunk_count}"]


class ChunkUploadState(_ChunkUploadMixin, State):
    """The base state for streaming chunk uploads."""


class FileStateBase1(State):
    """The base state for a child FileUploadState."""


class ChildFileUploadState(_FileUploadMixin, FileStateBase1):
    """The child state for uploading a file."""


class FileStateBase2(FileStateBase1):
    """The parent state for a grandchild FileUploadState."""


class GrandChildFileUploadState(_FileUploadMixin, FileStateBase2):
    """The child state for uploading a file."""
