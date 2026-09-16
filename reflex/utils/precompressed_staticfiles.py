"""Serve precompressed static assets when the client supports them."""

from __future__ import annotations

import os
import stat
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from mimetypes import guess_type
from os import PathLike
from pathlib import Path

import anyio.to_thread
from starlette.datastructures import Headers
from starlette.responses import FileResponse, Response
from starlette.staticfiles import NotModifiedResponse, StaticFiles
from starlette.types import Scope


@dataclass(frozen=True, slots=True)
class _EncodingFormat:
    content_encoding: str
    suffix: str


_SUPPORTED_ENCODINGS: dict[str, _EncodingFormat] = {
    "gzip": _EncodingFormat(content_encoding="gzip", suffix=".gz"),
    "brotli": _EncodingFormat(content_encoding="br", suffix=".br"),
    "zstd": _EncodingFormat(content_encoding="zstd", suffix=".zst"),
}


@lru_cache(maxsize=64)
def _parse_accept_encoding(header_value: str | None) -> dict[str, float]:
    """Parse an ``Accept-Encoding`` header into a token-to-quality mapping.

    Args:
        header_value: The raw header value.

    Returns:
        A mapping of tokens to their quality values.
    """
    if not header_value:
        return {}

    parsed: dict[str, float] = {}
    for entry in header_value.split(","):
        token, *params = entry.split(";")
        token = token.strip().lower()
        if not token:
            continue

        quality = 1.0
        for param in params:
            key, _, value = param.strip().partition("=")
            if key.lower() != "q" or not value:
                continue
            try:
                quality = float(value)
            except ValueError:
                quality = 0.0
            break

        parsed[token] = max(parsed.get(token, 0.0), quality)
    return parsed


class PrecompressedStaticFiles(StaticFiles):
    """StaticFiles that prefers matching precompressed sidecar files."""

    def __init__(
        self,
        *args,
        encodings: Sequence[str] = (),
        **kwargs,
    ):
        """Initialize the static file server.

        Args:
            *args: Passed through to ``StaticFiles``.
            encodings: Ordered list of supported precompressed formats.
            **kwargs: Passed through to ``StaticFiles``.
        """
        super().__init__(*args, **kwargs)
        self._encodings = tuple(_SUPPORTED_ENCODINGS[name] for name in encodings)

    def _select_sidecar(
        self, full_path: str | PathLike[str], scope: Scope
    ) -> tuple[str, str, os.stat_result] | None:
        """Pick the best Accept-Encoding sidecar that exists alongside ``full_path``.

        Args:
            full_path: The resolved on-disk path to the uncompressed file.
            scope: The ASGI request scope.

        Returns:
            ``(content_encoding, sidecar_path, sidecar_stat)`` or ``None``.
        """
        path_str = os.fspath(full_path)
        if any(path_str.endswith(fmt.suffix) for fmt in self._encodings):
            return None
        accepted = _parse_accept_encoding(Headers(scope=scope).get("accept-encoding"))
        if not accepted:
            return None

        best: tuple[str, str, os.stat_result] | None = None
        best_quality = 0.0
        for encoding in self._encodings:
            quality = accepted.get(encoding.content_encoding, accepted.get("*", 0.0))
            if quality <= best_quality:
                continue
            candidate = path_str + encoding.suffix
            try:
                sidecar_stat = Path(candidate).stat()
            except OSError:
                continue
            if not stat.S_ISREG(sidecar_stat.st_mode):
                continue
            best = (encoding.content_encoding, candidate, sidecar_stat)
            best_quality = quality
            if best_quality >= 1.0:
                break
        return best

    def file_response(
        self,
        full_path: str | PathLike[str],
        stat_result: os.stat_result,
        scope: Scope,
        status_code: int = 200,
    ) -> Response:
        """Build the FileResponse for the uncompressed file.

        With sidecar encodings configured this response is provisional:
        ``get_response`` picks the sidecar off the event loop and finishes the
        response (``Vary``/``Content-Encoding`` and the conditional check).

        Args:
            full_path: The resolved on-disk path to the uncompressed file.
            stat_result: The stat result for the uncompressed file.
            scope: The ASGI request scope.
            status_code: The response status code to use.

        Returns:
            A file response for the uncompressed file.
        """
        media_type = (
            "text/javascript"
            if Path(full_path).suffix.lower() in {".js", ".mjs"}
            else guess_type(os.fspath(full_path))[0]
        )
        response = FileResponse(
            full_path,
            status_code=status_code,
            media_type=media_type,
            stat_result=stat_result,
        )
        if self._encodings:
            return response
        return self._conditional(response, scope)

    def _conditional(self, response: FileResponse, scope: Scope) -> Response:
        """Turn ``response`` into a 304 when the client's cached copy is current.

        Args:
            response: The file response about to be served.
            scope: The ASGI request scope.

        Returns:
            ``response`` or a ``NotModifiedResponse`` carrying its headers.
        """
        if self.is_not_modified(response.headers, Headers(scope=scope)):
            return NotModifiedResponse(response.headers)
        return response

    async def get_response(self, path: str, scope: Scope) -> Response:
        """Serve ``path``, swapping in a precompressed sidecar when possible.

        The sidecar lookup stats files, so it runs in a worker thread like
        Starlette's own path lookup. This also covers the 404.html fallback,
        which Starlette builds with a bare FileResponse.

        Args:
            path: The requested relative file path.
            scope: The ASGI request scope.

        Returns:
            The resolved static response for the request.
        """
        response = await super().get_response(path, scope)
        if (
            not self._encodings
            or not isinstance(response, FileResponse)
            or response.stat_result is None
        ):
            return response
        sidecar = await anyio.to_thread.run_sync(
            self._select_sidecar, response.path, scope
        )
        headers = {"Vary": "Accept-Encoding"}
        response_path: str | PathLike[str] = response.path
        response_stat = response.stat_result
        if sidecar is not None:
            content_encoding, response_path, response_stat = sidecar
            headers["Content-Encoding"] = content_encoding
        return self._conditional(
            FileResponse(
                response_path,
                status_code=response.status_code,
                headers=headers,
                media_type=response.media_type,
                stat_result=response_stat,
            ),
            scope,
        )
