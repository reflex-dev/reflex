"""Import operations."""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Optional

from reflex.base import Base
from reflex.constants.installer import PackageJson


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


def collapse_imports(imports: ImportDict) -> ImportDict:
    """Remove all duplicate ImportVar within an ImportDict.

    Args:
        imports: The import dict to collapse.

    Returns:
        The collapsed import dict.
    """
    return {lib: list(set(import_vars)) for lib, import_vars in imports.items()}


def split_library_name_version(library_fullname: str):
    """Split the name of a library from its version.

    Args:
        library_fullname: The fullname of the library.

    Returns:
        A tuple of the library name and version.
    """
    lib, at, version = library_fullname.rpartition("@")
    if not lib:
        lib = at + version
        version = None

    return lib, version


class ImportVar(Base):
    """An import var."""

    # The package name associated with the tag
    library: Optional[str]

    # The name of the import tag.
    tag: Optional[str]

    # whether the import is default or named.
    is_default: Optional[bool] = False

    # The tag alias.
    alias: Optional[str] = None

    # The following fields provide extra information about the import,
    # but are not factored in when considering hash or equality

    # The version of the package
    version: Optional[str]

    # Whether this import need to install the associated lib
    install: Optional[bool] = True

    # whether this import should be rendered or not
    render: Optional[bool] = True

    # whether this import package should be added to transpilePackages in next.config.js
    # https://nextjs.org/docs/app/api-reference/next-config-js/transpilePackages
    transpile: Optional[bool] = False

    def __init__(
        self,
        *,
        package: Optional[str] = None,
        **kwargs,
    ):
        """Create a new ImportVar.

        Args:
            package: The package to install for this import.
            **kwargs: The import var fields.

        Raises:
            ValueError: If the package is provided with library or version.
        """
        if package is not None:
            if (
                kwargs.get("library", None) is not None
                or kwargs.get("version", None) is not None
            ):
                raise ValueError(
                    "Cannot provide 'library' or 'version' as keyword arguments when "
                    "specifying 'package' as an argument"
                )
            kwargs["library"], kwargs["version"] = split_library_name_version(package)

        install = (
            package is not None
            # TODO: handle version conflicts
            and package not in PackageJson.DEPENDENCIES
            and package not in PackageJson.DEV_DEPENDENCIES
            and not any(package.startswith(prefix) for prefix in ["/", ".", "next/"])
            and package != ""
        )
        kwargs.setdefault("install", install)
        super().__init__(**kwargs)

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

    @property
    def package(self) -> str | None:
        """The package to install for this import.

        Returns:
            The library name and (optional) version to be installed by npm/bun.
        """
        if self.version:
            return f"{self.library}@{self.version}"
        return self.library

    def __hash__(self) -> int:
        """Define a hash function for the import var.

        Returns:
            The hash of the var.
        """
        return hash(
            (
                self.library,
                self.tag,
                self.is_default,
                self.alias,
            )
        )

    def __eq__(self, other: ImportVar) -> bool:
        """Define equality for the import var.

        Args:
            other: The other import var to compare.

        Returns:
            Whether the two import vars are equal.
        """
        if type(self) != type(other):
            return NotImplemented
        return (self.library, self.tag, self.is_default, self.alias) == (
            other.library,
            other.tag,
            other.is_default,
            other.alias,
        )

    def collapse(self, other_import_var: ImportVar) -> ImportVar:
        """Collapse two import vars together.

        Args:
            other_import_var: The other import var to collapse with.

        Returns:
            The collapsed import var with sticky props perserved.

        Raises:
            ValueError: If the two import vars have conflicting properties.
        """
        if self != other_import_var:
            raise ValueError("Cannot collapse two import vars with different hashes")

        if (
            self.version is not None
            and other_import_var.version is not None
            and self.version != other_import_var.version
        ):
            raise ValueError(
                "Cannot collapse two import vars with conflicting version specifiers: "
                f"{self} {other_import_var}"
            )

        return type(self)(
            library=self.library,
            version=self.version or other_import_var.version,
            tag=self.tag,
            is_default=self.is_default,
            alias=self.alias,
            install=self.install or other_import_var.install,
            render=self.render or other_import_var.render,
            transpile=self.transpile or other_import_var.transpile,
        )


class ImportList(List[ImportVar]):
    """A list of import vars."""

    def __init__(self, *args, **kwargs):
        """Create a new ImportList (wrapper over `list`).

        Any items that are not already `ImportVar` will be assumed as dicts to convert
        into an ImportVar.

        Args:
            *args: The args to pass to list.__init__
            **kwargs: The kwargs to pass to list.__init__
        """
        super().__init__(*args, **kwargs)
        for ix, value in enumerate(self):
            if not isinstance(value, ImportVar):
                # convert dicts to ImportVar
                self[ix] = ImportVar(**value)

    @classmethod
    def from_import_dict(
        cls, import_dict: ImportDict | Dict[str, set[ImportVar]]
    ) -> ImportList:
        """Create an import list from an import dict.

        Args:
            import_dict: The import dict to convert.

        Returns:
            The import list.
        """
        return cls(
            ImportVar(package=lib, **imp.dict())
            for lib, imps in import_dict.items()
            for imp in imps
        )

    def collapse(self) -> ImportDict:
        """When collapsing an import list, prefer packages with version specifiers.

        Returns:
            The collapsed import dict ({package_spec: [import_var1, ...]}).

        Raises:
            ValueError: If two imports have conflicting version specifiers.
        """
        collapsed: dict[str, dict[ImportVar, ImportVar]] = {}
        for imp in self:
            lib = imp.library or ""
            collapsed.setdefault(lib, {})
            if imp in collapsed[lib]:
                # Need to check if the current import has any special properties that need to
                # be preserved, like the version specifier, install, or transpile.
                existing_imp = collapsed[lib][imp]
                collapsed[lib][imp] = existing_imp.collapse(imp)
            else:
                collapsed[lib][imp] = imp

        # Check that all tags in the given library have the same version.
        deduped: ImportDict = {}
        for lib, imps in collapsed.items():
            packages = {imp.package for imp in imps if imp.version is not None}
            if len(packages) > 1:
                raise ValueError(
                    f"Imports from {lib} have conflicting version specifiers: "
                    f"{packages} {imps}"
                )
            package = lib
            if packages:
                package = packages.pop() or ""
            deduped[package] = list(imps.values())
        return deduped


ImportDict = Dict[str, List[ImportVar]]
