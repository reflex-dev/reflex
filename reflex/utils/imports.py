"""Import operations."""

from collections import defaultdict
from typing import Dict, Set

from reflex.vars import ImportVar

ImportDict = Dict[str, Set[ImportVar]]


def merge_imports(*imports) -> ImportDict:
    """Merge two import dicts together.

    Args:
        *imports: The list of import dicts to merge.

    Returns:
        The merged import dicts.
    """
    all_imports = defaultdict(set)
    for import_dict in imports:
        for lib, fields in import_dict.items():
            for field in fields:
                all_imports[lib].add(field)
    return all_imports
