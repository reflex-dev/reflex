"""Compatibility hacks and helpers."""

import contextlib
import sys


@contextlib.contextmanager
def pydantic_v1_patch():
    """A context manager that patches the Pydantic module to mimic v1 behaviour.

    Yields:
        None when the Pydantic module is patched.
    """
    patched_modules = [
        "pydantic",
        "pydantic.fields",
        "pydantic.errors",
        "pydantic.main",
    ]
    originals = {module: sys.modules.get(module) for module in patched_modules}
    try:
        import pydantic.v1  # type: ignore

        if pydantic.__version__.startswith("1."):
            # pydantic v1 is already installed
            yield
            return

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
