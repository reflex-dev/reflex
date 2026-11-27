"""What the harness checks, one module per component.

A module declares ``MATRIX``, the cells whose look is compared, and
``CONTRACT``, the behaviour both systems must show. Either may be absent.
"""

from __future__ import annotations

import importlib
import pkgutil

from ui_parity.contract import Contract
from ui_parity.matrix import Matrix


def _declared(attribute: str) -> dict:
    """Collect one declaration from every component module.

    Args:
        attribute: The name the modules declare it under.

    Returns:
        The declarations by component name, in name order.
    """
    found = {}
    for info in sorted(pkgutil.iter_modules(__path__), key=lambda info: info.name):
        module = importlib.import_module(f"{__name__}.{info.name}")
        declared = getattr(module, attribute, None)
        if declared is not None:
            found[declared.component] = declared
    return found


MATRICES: dict[str, Matrix] = _declared("MATRIX")
CONTRACTS: dict[str, Contract] = _declared("CONTRACT")
