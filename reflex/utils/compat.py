"""Compatibility hacks and helpers."""

from importlib.util import find_spec


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


if find_spec("pydantic") and find_spec("sqlmodel"):
    import contextlib
    import sys

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
            import pydantic.v1

            sys.modules["pydantic.fields"] = pydantic.v1.fields  # pyright: ignore [reportAttributeAccessIssue]
            sys.modules["pydantic.main"] = pydantic.v1.main  # pyright: ignore [reportAttributeAccessIssue]
            sys.modules["pydantic.errors"] = pydantic.v1.errors  # pyright: ignore [reportAttributeAccessIssue]
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
