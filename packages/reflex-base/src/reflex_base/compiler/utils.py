"""Common utility functions used in the compiler."""

from typing import TypedDict

from reflex_base.utils import format, imports


def validate_imports(import_dict: imports.ParsedImportDict):
    """Verify that the same Tag is not used in multiple import.

    Args:
        import_dict: The dict of imports to validate

    Raises:
        ValueError: if a conflict on "tag/alias" is detected for an import.
    """
    used_tags = {}
    for lib, imported_items in import_dict.items():
        for imported_item in imported_items:
            import_name = (
                f"{imported_item.tag}/{imported_item.alias}"
                if imported_item.alias
                else imported_item.tag
            )
            if import_name in used_tags:
                already_imported = used_tags[import_name]
                if (already_imported[0] == "$" and already_imported[1:] == lib) or (
                    lib[0] == "$" and lib[1:] == already_imported
                ):
                    used_tags[import_name] = lib if lib[0] == "$" else already_imported
                    continue
                msg = f"Can not compile, the tag {import_name} is used multiple time from {lib} and {used_tags[import_name]}"
                raise ValueError(msg)
            if import_name is not None:
                used_tags[import_name] = lib


def compile_import_statement(fields: list[imports.ImportVar]) -> tuple[str, list[str]]:
    """Compile an import statement.

    Args:
        fields: The set of fields to import from the library.

    Returns:
        The libraries for default and rest.
        default: default library. When install "import def from library".
        rest: rest of libraries. When install "import {rest1, rest2} from library"

    Raises:
        ValueError: If there is more than one default import.
    """
    # ignore the ImportVar fields with render=False during compilation
    fields_set = {field for field in fields if field.render}

    # Check for default imports.
    defaults = {field for field in fields_set if field.is_default}
    if len(defaults) >= 2:
        msg = "Only one default import is allowed."
        raise ValueError(msg)

    # Get the default import, and the specific imports.
    default = next(iter({field.name for field in defaults}), "")
    rest = {field.name for field in fields_set - defaults}

    return default, sorted(rest)


class ImportDict(TypedDict):
    """TypedDict for compiled import information.

    Attributes:
        lib: The library name.
        default: The default import name.
        rest: List of non-default import names.
    """

    lib: str
    default: str
    rest: list[str]


def compile_imports(import_dict: imports.ParsedImportDict) -> list[ImportDict]:
    """Compile an import dict.

    Args:
        import_dict: The import dict to compile.

    Returns:
        The list of import dict.

    Raises:
        ValueError: If an import in the dict is invalid.
    """
    collapsed_import_dict: imports.ParsedImportDict = imports.collapse_imports(
        import_dict
    )
    validate_imports(collapsed_import_dict)
    import_dicts: list[ImportDict] = []
    for lib, fields in collapsed_import_dict.items():
        # prevent lib from being rendered on the page if all imports are non rendered kind
        if not any(f.render for f in fields):
            continue

        lib_paths: dict[str, list[imports.ImportVar]] = {}

        for field in fields:
            lib_paths.setdefault(field.package_path, []).append(field)

        compiled = {
            path: compile_import_statement(fields) for path, fields in lib_paths.items()
        }

        for path, (default, rest) in compiled.items():
            if not lib:
                if default:
                    msg = "No default field allowed for empty library."
                    raise ValueError(msg)
                if rest is None or len(rest) == 0:
                    msg = "No fields to import."
                    raise ValueError(msg)
                import_dicts.extend(get_import_dict(module) for module in sorted(rest))
                continue

            # remove the version before rendering the package imports
            formatted_lib = format.format_library_name(lib) + (
                path if path != "/" else ""
            )

            import_dicts.append(get_import_dict(formatted_lib, default, rest))
    return import_dicts


def get_import_dict(
    lib: str, default: str = "", rest: list[str] | None = None
) -> ImportDict:
    """Get dictionary for import template.

    Args:
        lib: The importing react library.
        default: The default module to import.
        rest: The rest module to import.

    Returns:
        A dictionary for import template.
    """
    return ImportDict(
        lib=lib,
        default=default,
        rest=rest or [],
    )
