"""Import operations."""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Optional, Tuple, Union

from reflex.base import Base


def merge_imports(
    *imports: ImportDict | ParsedImportDict | ImmutableParsedImportDict,
) -> ParsedImportDict:
    """Merge multiple import dicts together.

    Args:
        *imports: The list of import dicts to merge.

    Returns:
        The merged import dicts.
    """
    all_imports = defaultdict(list)
    for import_dict in imports:
        for lib, fields in (
            import_dict if isinstance(import_dict, tuple) else import_dict.items()
        ):
            all_imports[lib].extend(fields)
    return all_imports


def parse_imports(imports: ImportDict | ParsedImportDict) -> ParsedImportDict:
    """Parse the import dict into a standard format.

    Args:
        imports: The import dict to parse.

    Returns:
        The parsed import dict.
    """

    def _make_list(value: ImportTypes) -> list[str | ImportVar] | list[ImportVar]:
        if isinstance(value, (str, ImportVar)):
            return [value]
        return value

    return {
        package: [
            ImportVar(tag=tag) if isinstance(tag, str) else tag
            for tag in _make_list(maybe_tags)
        ]
        for package, maybe_tags in imports.items()
    }


def collapse_imports(
    imports: ParsedImportDict | ImmutableParsedImportDict,
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


class ImportVar(Base):
    """An import var."""

    # The name of the import tag.
    tag: Optional[str]

    # whether the import is default or named.
    is_default: Optional[bool] = False

    # The tag alias.
    alias: Optional[str] = None

    # Whether this import need to install the associated lib
    install: Optional[bool] = True

    # whether this import should be rendered or not
    render: Optional[bool] = True

    # whether this import package should be added to transpilePackages in next.config.js
    # https://nextjs.org/docs/app/api-reference/next-config-js/transpilePackages
    transpile: Optional[bool] = False

    @property
    def name(self) -> str:
        """The name of the import.

        Returns:
            The name(tag name with alias) of tag.
        """
        if self.alias:
            return (
                self.alias if self.is_default else " as ".join([self.tag, self.alias])  # type: ignore
            )
        else:
            return self.tag or ""

    def __lt__(self, other: ImportVar) -> bool:
        """Compare two ImportVar objects.

        Args:
            other: The other ImportVar object to compare.

        Returns:
            Whether this ImportVar object is less than the other.
        """
        return (
            self.tag,
            self.is_default,
            self.alias,
            self.install,
            self.render,
            self.transpile,
        ) < (
            other.tag,
            other.is_default,
            other.alias,
            other.install,
            other.render,
            other.transpile,
        )

    def __eq__(self, other: ImportVar) -> bool:
        """Check if two ImportVar objects are equal.

        Args:
            other: The other ImportVar object to compare.

        Returns:
            Whether the two ImportVar objects are equal.
        """
        return (
            self.tag,
            self.is_default,
            self.alias,
            self.install,
            self.render,
            self.transpile,
        ) == (
            other.tag,
            other.is_default,
            other.alias,
            other.install,
            other.render,
            other.transpile,
        )

    def __hash__(self) -> int:
        """Hash the ImportVar object.

        Returns:
            The hash of the ImportVar object.
        """
        return hash(
            (
                self.tag,
                self.is_default,
                self.alias,
                self.install,
                self.render,
                self.transpile,
            )
        )


ImportTypes = Union[str, ImportVar, List[Union[str, ImportVar]], List[ImportVar]]
ImportDict = Dict[str, ImportTypes]
ParsedImportDict = Dict[str, List[ImportVar]]
ImmutableParsedImportDict = Tuple[Tuple[str, Tuple[ImportVar, ...]], ...]
