"""Serve precompressed static assets when the client supports them."""

from __future__ import annotations

import errno
import os
import stat
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from mimetypes import guess_type
from pathlib import Path
from typing import TypeVar

from anyio import to_thread
from starlette.datastructures import URL, Headers
from starlette.exceptions import HTTPException
from starlette.responses import FileResponse, RedirectResponse, Response
from starlette.staticfiles import NotModifiedResponse, StaticFiles
from starlette.types import Scope


@dataclass(frozen=True, slots=True)
class _EncodingFormat:
    """Mapping between a configured format and its HTTP/static-file details."""

    name: str
    content_encoding: str
    suffix: str


_SUPPORTED_ENCODINGS = {
    "gzip": _EncodingFormat(
        name="gzip",
        content_encoding="gzip",
        suffix=".gz",
    ),
    "brotli": _EncodingFormat(
        name="brotli",
        content_encoding="br",
        suffix=".br",
    ),
    "zstd": _EncodingFormat(
        name="zstd",
        content_encoding="zstd",
        suffix=".zst",
    ),
}


@dataclass(frozen=True, slots=True)
class _ImageFormat:
    """Mapping between an image format and its HTTP/static-file details."""

    name: str
    media_type: str
    suffix: str


_SUPPORTED_IMAGE_FORMATS = {
    "webp": _ImageFormat(name="webp", media_type="image/webp", suffix=".webp"),
    "avif": _ImageFormat(name="avif", media_type="image/avif", suffix=".avif"),
}

# Extensions of image files that can have optimized format variants.
_OPTIMIZABLE_IMAGE_EXTENSIONS = frozenset({
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".bmp",
    ".tif",
    ".tiff",
})


_T = TypeVar("_T")


def _resolve_formats(
    names: Sequence[str],
    registry: Mapping[str, _T],
) -> tuple[_T, ...]:
    """Look up format objects by name. Config already validates inputs.

    Args:
        names: Validated format names from config.
        registry: Mapping of format name to format object.

    Returns:
        Format objects in the configured order.
    """
    return tuple(registry[n] for n in names if n in registry)


def _parse_quality_header(header_value: str | None) -> dict[str, float]:
    """Parse a ``token;q=value`` HTTP header (Accept, Accept-Encoding, etc.).

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
        image_formats: Sequence[str] = (),
        **kwargs,
    ):
        """Initialize the static file server.

        Args:
            *args: Passed through to ``StaticFiles``.
            encodings: Ordered list of supported precompressed formats.
            image_formats: Ordered list of optimized image formats to negotiate.
            **kwargs: Passed through to ``StaticFiles``.
        """
        super().__init__(*args, **kwargs)
        self._encodings = _resolve_formats(encodings, _SUPPORTED_ENCODINGS)
        self._encoding_suffixes = tuple(fmt.suffix for fmt in self._encodings)
        self._image_formats = _resolve_formats(image_formats, _SUPPORTED_IMAGE_FORMATS)

    def _find_precompressed_variant_sync(
        self,
        path: str,
        accepted_encodings: dict[str, float],
    ) -> tuple[_EncodingFormat, str, os.stat_result] | None:
        """Select the best matching precompressed sidecar for a request path.

        This performs blocking filesystem lookups and must be called via
        ``to_thread.run_sync`` from async contexts.

        Args:
            path: The requested relative file path.
            accepted_encodings: Parsed Accept-Encoding quality values.

        Returns:
            The selected encoding format, file path, and stat result, or ``None``.
        """
        best_match = None
        best_quality = 0.0

        for encoding in self._encodings:
            quality = accepted_encodings.get(
                encoding.content_encoding, accepted_encodings.get("*", 0.0)
            )
            if quality <= 0:
                continue

            full_path, stat_result = self.lookup_path(path + encoding.suffix)
            if stat_result is None or not stat.S_ISREG(stat_result.st_mode):
                continue

            if quality > best_quality:
                best_match = (encoding, full_path, stat_result)
                best_quality = quality
                if best_quality >= 1.0:
                    break

        return best_match

    def _find_image_format_variant_sync(
        self,
        path: str,
        accepted_types: dict[str, float],
    ) -> tuple[_ImageFormat, str, os.stat_result] | None:
        """Select the best matching optimized image variant for a request path.

        This performs blocking filesystem lookups and must be called via
        ``to_thread.run_sync`` from async contexts.

        Args:
            path: The requested relative file path.
            accepted_types: Parsed Accept header quality values.

        Returns:
            The selected image format, file path, and stat result, or ``None``.
        """
        best_match = None
        best_quality = 0.0

        # Strip the original extension to build sidecar paths.
        stem, _dot, _ext = path.rpartition(".")

        for fmt in self._image_formats:
            quality = accepted_types.get(fmt.media_type, accepted_types.get("*/*", 0.0))
            if quality <= 0:
                continue

            sidecar_path = f"{stem}{fmt.suffix}"
            full_path, stat_result = self.lookup_path(sidecar_path)
            if stat_result is None or not stat.S_ISREG(stat_result.st_mode):
                continue

            if quality > best_quality:
                best_match = (fmt, full_path, stat_result)
                best_quality = quality
                if best_quality >= 1.0:
                    break

        return best_match

    async def _build_file_response(
        self,
        *,
        path: str,
        full_path: str,
        stat_result: os.stat_result,
        scope: Scope,
        status_code: int = 200,
    ) -> Response:
        """Build a ``FileResponse`` with optional precompressed sidecar support.

        Args:
            path: The requested relative file path.
            full_path: The resolved on-disk path to the uncompressed file.
            stat_result: The stat result for the uncompressed file.
            scope: The ASGI request scope.
            status_code: The response status code to use.

        Returns:
            A file response that serves the best matching asset variant.
        """
        request_headers = Headers(scope=scope)
        response_headers = {}
        response_path = full_path
        response_stat = stat_result
        media_type = None
        vary_parts: list[str] = []

        # Image format negotiation via Accept header.
        if self._image_formats:
            ext = Path(path).suffix
            if ext.lower() in _OPTIMIZABLE_IMAGE_EXTENSIONS:
                accepted_types = _parse_quality_header(request_headers.get("accept"))
                if accepted_types:
                    matched_image = await to_thread.run_sync(
                        lambda: self._find_image_format_variant_sync(
                            path, accepted_types
                        )
                    )
                    if matched_image:
                        fmt, response_path, response_stat = matched_image
                        media_type = fmt.media_type
                vary_parts.append("Accept")

        # Encoding negotiation via Accept-Encoding header.
        # Skip if image format negotiation already changed the response — the
        # precompressed sidecars are keyed to the original path, and modern
        # image formats (WebP, AVIF) are already compressed.
        if (
            self._encodings
            and media_type is None
            and not path.endswith(self._encoding_suffixes)
        ):
            accepted_encodings = _parse_quality_header(
                request_headers.get("accept-encoding")
            )
            if accepted_encodings:
                matched_variant = await to_thread.run_sync(
                    lambda: self._find_precompressed_variant_sync(
                        path, accepted_encodings
                    )
                )
                if matched_variant:
                    encoding, response_path, response_stat = matched_variant
                    response_headers["Content-Encoding"] = encoding.content_encoding
                    media_type = guess_type(path)[0] or "text/plain"

        if self._encodings:
            vary_parts.append("Accept-Encoding")

        if vary_parts:
            response_headers["Vary"] = ", ".join(vary_parts)

        response = FileResponse(
            response_path,
            status_code=status_code,
            headers=response_headers or None,
            media_type=media_type,
            stat_result=response_stat,
        )
        if self.is_not_modified(response.headers, request_headers):
            return NotModifiedResponse(response.headers)
        return response

    async def get_response(self, path: str, scope: Scope) -> Response:
        """Return the best static response for ``path`` and ``scope``.

        Args:
            path: The requested relative file path.
            scope: The ASGI request scope.

        Returns:
            The resolved static response for the request.
        """
        if scope["method"] not in ("GET", "HEAD"):
            raise HTTPException(status_code=405)

        try:
            full_path, stat_result = await to_thread.run_sync(self.lookup_path, path)
        except PermissionError:
            raise HTTPException(status_code=401) from None
        except OSError as exc:
            if exc.errno == errno.ENAMETOOLONG:
                raise HTTPException(status_code=404) from None
            raise

        if stat_result and stat.S_ISREG(stat_result.st_mode):
            return await self._build_file_response(
                path=path,
                full_path=full_path,
                stat_result=stat_result,
                scope=scope,
            )

        if stat_result and stat.S_ISDIR(stat_result.st_mode) and self.html:
            index_path = str(Path(path) / "index.html")
            full_index_path, index_stat_result = await to_thread.run_sync(
                self.lookup_path, index_path
            )
            if index_stat_result is not None and stat.S_ISREG(
                index_stat_result.st_mode
            ):
                if not scope["path"].endswith("/"):
                    url = URL(scope=scope)
                    return RedirectResponse(url=url.replace(path=url.path + "/"))
                return await self._build_file_response(
                    path=index_path,
                    full_path=full_index_path,
                    stat_result=index_stat_result,
                    scope=scope,
                )

        if self.html:
            full_404_path, stat_404_result = await to_thread.run_sync(
                self.lookup_path, "404.html"
            )
            if stat_404_result and stat.S_ISREG(stat_404_result.st_mode):
                return await self._build_file_response(
                    path="404.html",
                    full_path=full_404_path,
                    stat_result=stat_404_result,
                    scope=scope,
                    status_code=404,
                )

        raise HTTPException(status_code=404)
