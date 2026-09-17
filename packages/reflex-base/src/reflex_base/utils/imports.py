"""Import operations."""

from __future__ import annotations

import dataclasses
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence

# Absolute import paths beginning with one of these reserved ``.web``
# subdirectories are rewritten to ``$``-prefixed module specifiers.
ABSOLUTE_IMPORT_PREFIXES = (
    "/utils/",
    "/components/",
    "/styles/",
    "/public/",
    "/app_components/",
)


def _sort_key(var: ImportVar) -> tuple[bool | str, ...]:
    """Impose a total order on import vars, for batches that arrive unordered.

    Each optional field contributes whether it is set before it contributes its
    value, so `None` orders against a `str` or a `bool` rather than raising and
    without being flattened onto one. Stringifying instead would collide
    `tag=None` with `tag="None"`, and a stable sort would then leave that pair
    in whatever order the set produced.

    Distinct import vars always differ in a field, so this separates any two
    that a set can hold at once.

    Args:
        var: The import var to order.

    Returns:
        A tuple ordering this var against any other.
    """
    return (
        var.tag is None,
        var.tag or "",
        var.alias is None,
        var.alias or "",
        var.package_path,
        var.is_default is None,
        bool(var.is_default),
        var.install is None,
        bool(var.install),
        var.render is None,
        bool(var.render),
    )


def _as_import_vars(fields: Iterable[str | ImportVar]) -> list[ImportVar]:
    """Normalize a batch of imports, ordering it if it arrived unordered.

    A `set` iterates in an order that varies with PYTHONHASHSEED, and the
    merge preserves the order it is given, so a set reaching this untouched
    would put the hash seed back into the emitted imports and into every
    component hash derived from them.

    Args:
        fields: The tags or import vars to normalize.

    Returns:
        The import vars, sorted when the input had no order of its own.
    """
    converted = [
        ImportVar(field) if isinstance(field, str) else field for field in fields
    ]
    if isinstance(fields, (set, frozenset)):
        converted.sort(key=_sort_key)
    return converted


def _accumulate(
    all_imports: defaultdict[str, list[ImportVar]],
    seen: dict[str, set[ImportVar]],
    lib: str,
    fields: Iterable[ImportVar],
) -> None:
    """Add `fields` to `all_imports[lib]`, skipping ones already there.

    A library's first batch has nothing accumulated to collide with, so it only
    needs deduplicating against itself, and a batch of one cannot even do that.
    Most batches are one entry and so cost nothing. From the second batch
    onward the library earns a lookup set, which is what stops a tag shared
    across a subtree being carried once per node.

    Args:
        all_imports: The accumulator to add to, modified in place.
        seen: Per-library lookup sets, built on demand and modified in place.
        lib: The library the fields belong to.
        fields: The import vars to add.
    """
    existing = all_imports[lib]
    if not existing:
        if not isinstance(fields, (list, tuple)):
            fields = list(fields)
        # One entry cannot duplicate anything, and most batches are one entry.
        existing.extend(fields if len(fields) < 2 else dict.fromkeys(fields))
        return
    known = seen.get(lib)
    if known is None:
        known = seen[lib] = set(existing)
    for field in fields:
        if field not in known:
            known.add(field)
            existing.append(field)


def merge_parsed_imports(
    *imports: ImmutableParsedImportDict,
) -> ParsedImportDict:
    """Merge multiple parsed import dicts together.

    Args:
        *imports: The list of import dicts to merge.

    Returns:
        The merged import dicts.
    """
    all_imports: defaultdict[str, list[ImportVar]] = defaultdict(list)
    seen: dict[str, set[ImportVar]] = {}
    for import_dict in imports:
        for lib, fields in import_dict.items():
            _accumulate(all_imports, seen, lib, fields)
    return all_imports


def merge_imports(
    *imports: ImportDict | ParsedImportDict | ParsedImportTuple,
) -> ParsedImportDict:
    """Merge multiple import dicts together.

    Args:
        *imports: The list of import dicts to merge.

    Returns:
        The merged import dicts.
    """
    all_imports: defaultdict[str, list[ImportVar]] = defaultdict(list)
    seen: dict[str, set[ImportVar]] = {}
    for import_dict in imports:
        for lib, fields in (
            import_dict if isinstance(import_dict, tuple) else import_dict.items()
        ):
            # If the lib is an absolute path, we need to prefix it with a $
            lib = "$" + lib if lib.startswith(ABSOLUTE_IMPORT_PREFIXES) else lib
            if isinstance(fields, (list, tuple, set, frozenset)):
                _accumulate(all_imports, seen, lib, _as_import_vars(fields))
            else:
                _accumulate(
                    all_imports,
                    seen,
                    lib,
                    (ImportVar(fields) if isinstance(fields, str) else fields,),
                )
    return all_imports


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
        else _as_import_vars(maybe_tags)
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
            # dict.fromkeys, not set: set order varies with PYTHONHASHSEED, so
            # identical compiles would emit different memo names.
            list(dict.fromkeys(import_vars))
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
