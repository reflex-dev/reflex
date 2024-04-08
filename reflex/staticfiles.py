"""Classes for staticfiles served by Reflex backend."""

from fastapi.staticfiles import StaticFiles
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import Scope


class UploadedFiles(StaticFiles):
    """Static files with download headers."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        """Get the response for a static file with download headers.

        Args:
            path: The path of the static file.
            scope: The request scope.

        Returns:
            The response for the static file with download headers.
        """
        req = Request(scope)
        if "filename" in req.query_params:
            filename = req.query_params["filename"]
            content_disposition = f'attachment; filename="{filename}"'
        else:
            content_disposition = "attachment"
        response = await super().get_response(path, scope)
        response.headers["Content-Disposition"] = content_disposition
        return response
