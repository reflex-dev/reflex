"""Compatibility hacks and helpers."""

import contextlib
import sys


async def windows_hot_reload_lifespan_hack():
    """[REF-3164] A hack to fix hot reload on Windows.

    Uvicorn has an issue stopping itself on Windows after detecting changes in
    the filesystem.

    This workaround repeatedly prints and flushes null characters to stderr,
    which seems to allow the uvicorn server to exit when the CTRL-C signal is
    sent from the reloader process.

    Don't ask me why this works, I discovered it by accident - masenf.
    """
    import asyncio
    import sys

    try:
        while True:
            sys.stderr.write("\0")
            sys.stderr.flush()
            await asyncio.sleep(0.5)
    except asyncio.CancelledError:
        pass


@contextlib.contextmanager
def pydantic_v1_patch():
    """A context manager that patches the Pydantic module to mimic v1 behaviour.

    Yields:
        None when the Pydantic module is patched.
    """
    import pydantic

    if pydantic.__version__.startswith("1."):
        # pydantic v1 is already installed
        yield
        return

    patched_modules = [
        "pydantic",
        "pydantic.fields",
        "pydantic.errors",
        "pydantic.main",
    ]
    originals = {module: sys.modules.get(module) for module in patched_modules}
    try:
        import pydantic.v1  # type: ignore

        sys.modules["pydantic.fields"] = pydantic.v1.fields  # type: ignore
        sys.modules["pydantic.main"] = pydantic.v1.main  # type: ignore
        sys.modules["pydantic.errors"] = pydantic.v1.errors  # type: ignore
        sys.modules["pydantic"] = pydantic.v1
        yield
    except (ImportError, AttributeError):
        # pydantic v1 is already installed
        yield
    finally:
        # Restore the original Pydantic module
        for k, original in originals.items():
            if k in sys.modules:
                if original:
                    sys.modules[k] = original
                else:
                    del sys.modules[k]


with pydantic_v1_patch():
    import sqlmodel as sqlmodel


def sqlmodel_field_has_primary_key(field) -> bool:
    """Determines if a field is a priamary.

    Args:
        field: a rx.model field

    Returns:
        If field is a primary key (Bool)
    """
    if getattr(field.field_info, "primary_key", None) is True:
        return True
    if getattr(field.field_info, "sa_column", None) is None:
        return False
    if getattr(field.field_info.sa_column, "primary_key", None) is True:
        return True
    return False
