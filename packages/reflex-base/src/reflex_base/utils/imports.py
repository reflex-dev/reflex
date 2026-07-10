"""Import operations."""

from __future__ import annotations

import dataclasses
from collections import defaultdict
from collections.abc import Mapping, Sequence

# Absolute import paths beginning with one of these reserved ``.web``
# subdirectories are rewritten to ``$``-prefixed module specifiers.
ABSOLUTE_IMPORT_PREFIXES = (
    "/utils/",
    "/components/",
    "/styles/",
    "/public/",
    "/app_components/",
)


def _as_import_lists(
    deduped: defaultdict[str, dict[ImportVar, None]],
) -> ParsedImportDict:
    """Convert per-lib dedup dicts into the list-valued merge result.

    Args:
        deduped: The merged imports with per-lib insertion-ordered dedup dicts.

    Returns:
        The merged import dict with list values.
    """
    merged: defaultdict[str, list[ImportVar]] = defaultdict(list)
    for lib, fields in deduped.items():
        merged[lib] = list(fields)
    return merged


def merge_parsed_imports(
    *imports: ImmutableParsedImportDict,
) -> ParsedImportDict:
    """Merge multiple parsed import dicts together.

    Duplicate ``ImportVar`` entries are dropped (keeping first-seen order) so
    repeated merges stay linear instead of growing with every level of
    nesting.

    Args:
        *imports: The list of import dicts to merge.

    Returns:
        The merged import dicts.
    """
    all_imports: defaultdict[str, dict[ImportVar, None]] = defaultdict(dict)
    for import_dict in imports:
        for lib, fields in import_dict.items():
            bucket = all_imports[lib]
            for field in fields:
                bucket[field] = None
    return _as_import_lists(all_imports)


def merge_imports(
    *imports: ImportDict | ParsedImportDict | ParsedImportTuple,
) -> ParsedImportDict:
    """Merge multiple import dicts together.

    Duplicate ``ImportVar`` entries are dropped (keeping first-seen order) so
    repeated merges stay linear instead of growing with every level of
    nesting — e.g. chained var operations merge the same operand imports via
    both ``_args`` and ``_return``.

    Args:
        *imports: The list of import dicts to merge.

    Returns:
        The merged import dicts.
    """
    all_imports: defaultdict[str, dict[ImportVar, None]] = defaultdict(dict)
    for import_dict in imports:
        for lib, fields in (
            import_dict if isinstance(import_dict, tuple) else import_dict.items()
        ):
            # If the lib is an absolute path, we need to prefix it with a $
            lib = "$" + lib if lib.startswith(ABSOLUTE_IMPORT_PREFIXES) else lib
            bucket = all_imports[lib]
            if isinstance(fields, (list, tuple, set)):
                for field in fields:
                    bucket[ImportVar(field) if isinstance(field, str) else field] = None
            else:
                bucket[ImportVar(fields) if isinstance(fields, str) else fields] = None
    return _as_import_lists(all_imports)


def parse_imports(
    imports: ImmutableImportDict | ImmutableParsedImportDict,
) -> ParsedImportDict:
    """Parse the import dict into a standard format.

    Args:
        imports: The import dict to parse.

    Returns:
        The parsed import dict.
    """
    return {
        package: [maybe_tags]
        if isinstance(maybe_tags, ImportVar)
        else [ImportVar(tag=maybe_tags)]
        if isinstance(maybe_tags, str)
        else [ImportVar(tag=tag) if isinstance(tag, str) else tag for tag in maybe_tags]
        for package, maybe_tags in imports.items()
    }


def collapse_imports(
    imports: ParsedImportDict | ParsedImportTuple,
) -> ParsedImportDict:
    """Remove all duplicate ImportVar within an ImportDict.

    Args:
        imports: The import dict to collapse.

    Returns:
        The collapsed import dict.
    """
    return {
        lib: (
            list(set(import_vars))
            if isinstance(import_vars, list)
            else list(import_vars)
        )
        for lib, import_vars in (
            imports if isinstance(imports, tuple) else imports.items()
        )
    }


@dataclasses.dataclass(frozen=True)
class ImportVar:
    """An import var."""

    # The name of the import tag.
    tag: str | None

    # whether the import is default or named.
    is_default: bool | None = False

    # The tag alias.
    alias: str | None = None

    # Whether this import need to install the associated lib
    install: bool | None = True

    # whether this import should be rendered or not
    render: bool | None = True

    # The path of the package to import from.
    package_path: str = "/"

    @property
    def name(self) -> str:
        """The name of the import.

        Returns:
            The name(tag name with alias) of tag.
        """
        if self.alias:
            return (
                self.alias
                if self.is_default and self.tag != "*"
                else (self.tag + " as " + self.alias if self.tag else self.alias)
            )
        return self.tag or ""


ImportTypes = str | ImportVar | list[str | ImportVar] | list[ImportVar]
ImmutableImportTypes = str | ImportVar | Sequence[str | ImportVar]
ImportDict = dict[str, ImportTypes]
ImmutableImportDict = Mapping[str, ImmutableImportTypes]
ParsedImportDict = dict[str, list[ImportVar]]
ImmutableParsedImportDict = Mapping[str, Sequence[ImportVar]]
ParsedImportTuple = tuple[tuple[str, tuple[ImportVar, ...]], ...]
