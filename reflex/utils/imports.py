"""Import operations."""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

from reflex.vars import ImportVar

ImportDict = Dict[str, List[ImportVar]]


def merge_imports(*imports) -> ImportDict:
    """Merge multiple import dicts together.

    Args:
        *imports: The list of import dicts to merge.

    Returns:
        The merged import dicts.
    """
    all_imports = defaultdict(list)
    for import_dict in imports:
        for lib, fields in import_dict.items():
            all_imports[lib].extend(fields)
    return all_imports
