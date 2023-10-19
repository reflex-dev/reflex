"""Compatibility shims and helpers."""
import importlib.metadata
import sys


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

    for f_path in importlib.metadata.files("uvicorn"):
        if f_path.name == "server.py":
            f_path.locate().write_text(
                _patch_uvicorn_server_shutdown(f_path.read_text()),
            )
            break
