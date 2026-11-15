"""The `__lazy_modules__` declarations keep their imports lazy on Python 3.15+ (PEP 810)."""

import json
import subprocess
import sys

import pytest

pytestmark = pytest.mark.skipif(
    sys.version_info < (3, 15), reason="PEP 810 lazy imports need Python 3.15+"
)

# Lists the names in the module's namespace that are still unresolved lazy imports.
_LIST_LAZY_NAMES = (
    "import importlib, json, sys, types; "
    "module = importlib.import_module(sys.argv[1]); "
    "print(json.dumps(sorted(name for name, value in vars(module).items() "
    "if type(value) is types.LazyImportType)))"
)


@pytest.mark.parametrize(
    ("module", "lazy_names"),
    [
        (
            "reflex_base.plugins.sitemap",
            ["Element", "SubElement", "indent", "tostring"],
        ),
        (
            "reflex_base.utils.console",
            [
                "MofNCompleteColumn",
                "Progress",
                "Prompt",
                "Table",
                "TaskID",
                "TimeElapsedColumn",
            ],
        ),
    ],
)
def test_lazy_modules_are_not_imported_by_the_module_itself(
    module: str, lazy_names: list[str]
):
    """Importing the module leaves the imports of its `__lazy_modules__` unresolved.

    Each module runs in a fresh interpreter: an import of a module that is
    already loaded binds the real object instead of a lazy proxy.

    Args:
        module: The module that declares `__lazy_modules__`.
        lazy_names: The names its imports of those modules bind.
    """
    result = subprocess.run(
        [sys.executable, "-c", _LIST_LAZY_NAMES, module],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(result.stdout) == lazy_names
