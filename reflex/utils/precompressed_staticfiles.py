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
        """Build a FileResponse, swapping in a precompressed sidecar when possible.

        Args:
            full_path: The resolved on-disk path to the uncompressed file.
            stat_result: The stat result for the uncompressed file.
            scope: The ASGI request scope.
            status_code: The response status code to use.

        Returns:
            A file response that serves the best matching asset variant.
        """
        response_path: str | PathLike[str] = full_path
        response_stat = stat_result
        response_headers: dict[str, str] = {}
        media_type: str | None = None

        if self._encodings:
            response_headers["Vary"] = "Accept-Encoding"
            sidecar = self._select_sidecar(full_path, scope)
            if sidecar is not None:
                content_encoding, response_path, response_stat = sidecar
                response_headers["Content-Encoding"] = content_encoding
                media_type = guess_type(os.fspath(full_path))[0] or "text/plain"

        response = FileResponse(
            response_path,
            status_code=status_code,
            headers=response_headers or None,
            media_type=media_type,
            stat_result=response_stat,
        )
        if self.is_not_modified(response.headers, Headers(scope=scope)):
            return NotModifiedResponse(response.headers)
        return response

    async def get_response(self, path: str, scope: Scope) -> Response:
        """Serve ``path``, re-routing the 404.html fallback through ``file_response``.

        Args:
            path: The requested relative file path.
            scope: The ASGI request scope.

        Returns:
            The resolved static response for the request.
        """
        response = await super().get_response(path, scope)
        # Starlette's get_response builds the 404.html fallback with bare FileResponse,
        # bypassing file_response. Re-route it so the sidecar/Vary handling applies.
        if (
            self._encodings
            and self.html
            and isinstance(response, FileResponse)
            and response.status_code == 404
            and response.stat_result is not None
        ):
            return self.file_response(
                response.path, response.stat_result, scope, status_code=404
            )
        return response
