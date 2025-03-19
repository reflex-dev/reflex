"""Test states for upload-related tests."""

from pathlib import Path
from typing import ClassVar

import reflex as rx
from reflex.state import BaseState, State


class UploadState(BaseState):
    """The base state for uploading a file."""

    async def handle_upload1(self, files: list[rx.UploadFile]):
        """Handle the upload of a file.

        Args:
            files: The uploaded files.
        """
        pass


class BaseState(BaseState):
    """The test base state."""

    pass


class SubUploadState(BaseState):
    """The test substate."""

    img: str

    async def handle_upload(self, files: list[rx.UploadFile]):
        """Handle the upload of a file.

        Args:
            files: The uploaded files.
        """
        pass


class FileUploadState(State):
    """The base state for uploading a file."""

    img_list: list[str]
    _tmp_path: ClassVar[Path]

    async def handle_upload2(self, files):
        """Handle the upload of a file.

        Args:
            files: The uploaded files.
        """
        pass

    async def multi_handle_upload(self, files: list[rx.UploadFile]):
        """Handle the upload of a file.

        Args:
            files: The uploaded files.
        """
        for file in files:
            upload_data = await file.read()
            assert file.filename is not None
            outfile = self._tmp_path / file.filename

            # Save the file.
            outfile.write_bytes(upload_data)

            # Update the img var.
            self.img_list.append(file.filename)

    @rx.event(background=True)
    async def bg_upload(self, files: list[rx.UploadFile]):
        """Background task cannot be upload handler.

        Args:
            files: The uploaded files.
        """
        pass


class FileStateBase1(State):
    """The base state for a child FileUploadState."""

    pass


class ChildFileUploadState(FileStateBase1):
    """The child state for uploading a file."""

    img_list: list[str]
    _tmp_path: ClassVar[Path]

    async def handle_upload2(self, files):
        """Handle the upload of a file.

        Args:
            files: The uploaded files.
        """
        pass

    async def multi_handle_upload(self, files: list[rx.UploadFile]):
        """Handle the upload of a file.

        Args:
            files: The uploaded files.
        """
        for file in files:
            upload_data = await file.read()
            assert file.filename is not None
            outfile = self._tmp_path / file.filename

            # Save the file.
            outfile.write_bytes(upload_data)

            # Update the img var.
            self.img_list.append(file.filename)

    @rx.event(background=True)
    async def bg_upload(self, files: list[rx.UploadFile]):
        """Background task cannot be upload handler.

        Args:
            files: The uploaded files.
        """
        pass


class FileStateBase2(FileStateBase1):
    """The parent state for a grandchild FileUploadState."""

    pass


class GrandChildFileUploadState(FileStateBase2):
    """The child state for uploading a file."""

    img_list: list[str]
    _tmp_path: ClassVar[Path]

    async def handle_upload2(self, files):
        """Handle the upload of a file.

        Args:
            files: The uploaded files.
        """
        pass

    async def multi_handle_upload(self, files: list[rx.UploadFile]):
        """Handle the upload of a file.

        Args:
            files: The uploaded files.
        """
        for file in files:
            upload_data = await file.read()
            assert file.filename is not None
            outfile = self._tmp_path / file.filename

            # Save the file.
            outfile.write_bytes(upload_data)

            # Update the img var.
            self.img_list.append(file.filename)

    @rx.event(background=True)
    async def bg_upload(self, files: list[rx.UploadFile]):
        """Background task cannot be upload handler.

        Args:
            files: The uploaded files.
        """
        pass
