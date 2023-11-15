"""Test states for upload-related tests."""
from pathlib import Path
from typing import ClassVar, List

import nextpy as xt


class UploadState(xt.State):
    """The base state for uploading a file."""

    async def handle_upload1(self, files: List[xt.UploadFile]):
        """Handle the upload of a file.

        Args:
            files: The uploaded files.
        """
        pass


class BaseState(xt.State):
    """The test base state."""

    pass


class SubUploadState(BaseState):
    """The test substate."""

    img: str

    async def handle_upload(self, files: List[xt.UploadFile]):
        """Handle the upload of a file.

        Args:
            files: The uploaded files.
        """
        pass


class FileUploadState(xt.State):
    """The base state for uploading a file."""

    img_list: List[str]
    _tmp_path: ClassVar[Path]

    async def handle_upload2(self, files):
        """Handle the upload of a file.

        Args:
            files: The uploaded files.
        """
        for file in files:
            upload_data = await file.read()
            outfile = f"{self._tmp_path}/{file.filename}"

            # Save the file.
            with open(outfile, "wb") as file_object:
                file_object.write(upload_data)

            # Update the img var.
            self.img_list.append(file.filename)

    async def multi_handle_upload(self, files: List[xt.UploadFile]):
        """Handle the upload of a file.

        Args:
            files: The uploaded files.
        """
        for file in files:
            upload_data = await file.read()
            outfile = f"{self._tmp_path}/{file.filename}"

            # Save the file.
            with open(outfile, "wb") as file_object:
                file_object.write(upload_data)

            # Update the img var.
            assert file.filename is not None
            self.img_list.append(file.filename)


class FileStateBase1(xt.State):
    """The base state for a child FileUploadState."""

    pass


class ChildFileUploadState(FileStateBase1):
    """The child state for uploading a file."""

    img_list: List[str]
    _tmp_path: ClassVar[Path]

    async def handle_upload2(self, files):
        """Handle the upload of a file.

        Args:
            files: The uploaded files.
        """
        for file in files:
            upload_data = await file.read()
            outfile = f"{self._tmp_path}/{file.filename}"

            # Save the file.
            with open(outfile, "wb") as file_object:
                file_object.write(upload_data)

            # Update the img var.
            self.img_list.append(file.filename)

    async def multi_handle_upload(self, files: List[xt.UploadFile]):
        """Handle the upload of a file.

        Args:
            files: The uploaded files.
        """
        for file in files:
            upload_data = await file.read()
            outfile = f"{self._tmp_path}/{file.filename}"

            # Save the file.
            with open(outfile, "wb") as file_object:
                file_object.write(upload_data)

            # Update the img var.
            assert file.filename is not None
            self.img_list.append(file.filename)


class FileStateBase2(FileStateBase1):
    """The parent state for a grandchild FileUploadState."""

    pass


class GrandChildFileUploadState(FileStateBase2):
    """The child state for uploading a file."""

    img_list: List[str]
    _tmp_path: ClassVar[Path]

    async def handle_upload2(self, files):
        """Handle the upload of a file.

        Args:
            files: The uploaded files.
        """
        for file in files:
            upload_data = await file.read()
            outfile = f"{self._tmp_path}/{file.filename}"

            # Save the file.
            with open(outfile, "wb") as file_object:
                file_object.write(upload_data)

            # Update the img var.
            self.img_list.append(file.filename)

    async def multi_handle_upload(self, files: List[xt.UploadFile]):
        """Handle the upload of a file.

        Args:
            files: The uploaded files.
        """
        for file in files:
            upload_data = await file.read()
            outfile = f"{self._tmp_path}/{file.filename}"

            # Save the file.
            with open(outfile, "wb") as file_object:
                file_object.write(upload_data)

            # Update the img var.
            assert file.filename is not None
            self.img_list.append(file.filename)
