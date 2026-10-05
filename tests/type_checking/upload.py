"""Calling an upload handler with the upload spec reflex fills with the uploaded files."""

from reflex_base.event import EventCallback, event
from typing_extensions import assert_type

import reflex as rx
from reflex.state import State


class _UploadState(State):
    @event
    async def files(self, files: list[rx.UploadFile]) -> None: ...

    @event(background=True)
    async def chunks(self, chunks: rx.UploadChunkIterator) -> None: ...


# The upload spec stands in for the files, or the chunks, the handler receives.
assert_type(_UploadState.files(rx.upload_files(upload_id="upload")), EventCallback[()])
assert_type(
    _UploadState.chunks(rx.upload_files_chunk(upload_id="upload")),
    EventCallback[()],
)
