"""Compatibility shims and helpers."""
import sys
from pathlib import Path


def _patch_uvicorn_server_shutdown(source_code):
    needle = (
        "        for connection in list(self.server_state.connections):\n"
        "            connection.shutdown()\n"
    )
    patch = (
        "        for server in self.servers:\n"
        "            await server.wait_closed()\n"
    )
    marker = "  # PATCHED\n"

    def _patched(code):
        return code.rstrip("\n") + marker

    return source_code.replace(patch, "").replace(
        needle,
        _patched(needle) + _patched(patch),
    )


def patch_uvicorn_0_23_py312():
    """Fix shutdown ordering on py312 to avoid hang."""
    if sys.version_info < (3, 12):
        return  # nothing to do on older versions

    import uvicorn.server

    uvicorn_server_py = Path(uvicorn.server.__file__)
    uvicorn_server_py.write_text(
        _patch_uvicorn_server_shutdown(uvicorn_server_py.read_text()),
    )
