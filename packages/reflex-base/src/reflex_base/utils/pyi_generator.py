"""The pyi generator module."""

from __future__ import annotations

import ast
import contextlib
import importlib
import inspect
import logging
import multiprocessing
import os
import re
import subprocess
import sys
import typing
from collections import deque
from collections.abc import Callable, Iterable, Mapping, Sequence
from concurrent.futures import ProcessPoolExecutor
from functools import cache
from hashlib import md5
from inspect import getfullargspec
from itertools import chain
from pathlib import Path
from types import MappingProxyType, ModuleType, SimpleNamespace, UnionType
from typing import Any, ClassVar, get_args, get_origin

from reflex_base.components.component import DEFAULT_TRIGGERS_AND_DESC, Component
from reflex_base.environment import interpret_boolean_env
from reflex_base.utils.format import orjson_dumps, orjson_loads
from reflex_base.vars.base import Var


def _is_union(cls: Any) -> bool:
    origin = getattr(cls, "__origin__", None)
    if origin is typing.Union:
        return True
    return origin is None and isinstance(cls, UnionType)


def _is_optional(cls: Any) -> bool:
    return (
        cls is None
        or cls is type(None)
        or (_is_union(cls) and type(None) in get_args(cls))
    )


def _is_literal(cls: Any) -> bool:
    return getattr(cls, "__origin__", None) is typing.Literal


def _safe_issubclass(cls: Any, cls_check: Any | tuple[Any, ...]) -> bool:
    try:
        return issubclass(cls, cls_check)
    except TypeError:
        return False


logger = logging.getLogger("pyi_generator")

PWD = Path.cwd()

PYI_HASHES = "pyi_hashes.json"

EXCLUDED_FILES = [
    "app.py",
    "component.py",
    "bare.py",
    "foreach.py",
    "cond.py",
    "match.py",
    "multiselect.py",
    "literals.py",
]

# These props exist on the base component, but should not be exposed in create methods.
EXCLUDED_PROPS = [
    "alias",
    "children",
    "event_triggers",
    "library",
    "lib_dependencies",
    "tag",
    "is_default",
    "special_props",
    "_is_tag_in_global_scope",
    "_invalid_children",
    "_memoization_mode",
    "_rename_props",
    "_valid_children",
    "_valid_parents",
    "State",
]

OVERWRITE_TYPES = {
    "style": "Sequence[Mapping[str, Any]] | Mapping[str, Any] | Var[Mapping[str, Any]] | Breakpoints | None",
}

DEFAULT_TYPING_IMPORTS = {
    "Any",
    "Dict",
    "Literal",
    "Optional",
    "Union",
    "Annotated",
}

# TODO: fix import ordering and unused imports with ruff later
DEFAULT_IMPORTS = {
    "collections.abc": ["Callable", "Mapping", "Sequence"],
    "typing": sorted(DEFAULT_TYPING_IMPORTS),
    "reflex_components_core.core.breakpoints": ["Breakpoints"],
    "reflex_base.event": [
        "EventChain",
        "EventHandler",
        "EventSpec",
        "EventType",
        "KeyInputInfo",
        "PointerEventInfo",
    ],
    "reflex_base.style": ["Style"],
    "reflex_base.vars.base": ["Var"],
}
# These pre-0.9 imports might be present in the file and should be removed since the pyi generator will handle them separately.
EXCLUDED_IMPORTS = {
    "typing": ["Callable", "Mapping", "Sequence"],  # moved to collections.abc
    "reflex.components.core.breakpoints": ["Breakpoints"],
    "reflex.event": [
        "EventChain",
        "EventHandler",
        "EventSpec",
        "EventType",
        "KeyInputInfo",
        "PointerEventInfo",
    ],
    "reflex.style": ["Style"],
    "reflex.vars.base": ["Var"],
}


def _walk_files(path: str | Path):
    """Walk all files in a path.
    This can be replaced with Path.walk() in python3.12.

    Args:
        path: The path to walk.

    Yields:
        The next file in the path.
    """
    for p in Path(path).iterdir():
        if p.is_dir():
            yield from _walk_files(p)
            continue
        yield p.resolve()


def _relative_to_pwd(path: Path) -> Path:
    """Get the relative path of a path to the current working directory.

    Args:
        path: The path to get the relative path for.

    Returns:
        The relative path.
    """
    if path.is_absolute():
        return path.relative_to(PWD)
    return path


def _get_type_hint(
    value: Any, type_hint_globals: dict, is_optional: bool = True
) -> str:
    """Resolve the type hint for value.

    Args:
        value: The type annotation as a str or actual types/aliases.
        type_hint_globals: The globals to use to resolving a type hint str.
        is_optional: Whether the type hint should be wrapped in Optional.

    Returns:
        The resolved type hint as a str.

    Raises:
        TypeError: If the value name is not visible in the type hint globals.
    """
    res = ""
    args = get_args(value)

    if value is type(None) or value is None:
        return "None"

    if _is_union(value):
        if type(None) in value.__args__:
            res_args = [
                _get_type_hint(arg, type_hint_globals, _is_optional(arg))
                for arg in value.__args__
                if arg is not type(None)
            ]
            res_args.sort()
            if len(res_args) == 1:
                return f"{res_args[0]} | None"
            res = f"{' | '.join(res_args)}"
            return f"{res} | None"

        res_args = [
            _get_type_hint(arg, type_hint_globals, _is_optional(arg))
            for arg in value.__args__
        ]
        res_args.sort()
        return f"{' | '.join(res_args)}"

    if args:
        inner_container_type_args = (
            sorted(repr(arg) for arg in args)
            if _is_literal(value)
            else [
                _get_type_hint(arg, type_hint_globals, is_optional=False)
                for arg in args
                if arg is not type(None)
            ]
        )

        if (
            value.__module__ not in ["builtins", "__builtins__"]
            and value.__name__ not in type_hint_globals
        ):
            msg = (
                f"{value.__module__ + '.' + value.__name__} is not a default import, "
                "add it to DEFAULT_IMPORTS in pyi_generator.py"
            )
            raise TypeError(msg)

        res = f"{value.__name__}[{', '.join(inner_container_type_args)}]"

        if value.__name__ == "Var":
            args = list(
                chain.from_iterable([
                    get_args(arg) if _is_union(arg) else [arg] for arg in args
                ])
            )

            # For Var types, Union with the inner args so they can be passed directly.
            types = [res] + [
                _get_type_hint(arg, type_hint_globals, is_optional=False)
                for arg in args
                if arg is not type(None)
            ]
            if len(types) > 1:
                res = " | ".join(sorted(types))

    elif isinstance(value, str):
        ev = eval(value, type_hint_globals)
        if _is_optional(ev):
            return _get_type_hint(ev, type_hint_globals, is_optional=False)

        if _is_union(ev):
            res = [
                _get_type_hint(arg, type_hint_globals, _is_optional(arg))
                for arg in ev.__args__
            ]
            return f"{' | '.join(res)}"
        res = (
            _get_type_hint(ev, type_hint_globals, is_optional=False)
            if ev.__name__ == "Var"
            else value
        )
    elif isinstance(value, list):
        res = [
            _get_type_hint(arg, type_hint_globals, _is_optional(arg)) for arg in value
        ]
        return f"[{', '.join(res)}]"
    elif (visible_name := _get_visible_type_name(value, type_hint_globals)) is not None:
        res = visible_name
    else:
        # Best effort to find a submodule path in the globals.
        for ix, part in enumerate(value.__module__.split(".")):
            if part in type_hint_globals:
                res = ".".join([
                    part,
                    *value.__module__.split(".")[ix + 1 :],
                    value.__name__,
                ])
                break
        else:
            # Fallback to the type name.
            res = value.__name__
    if is_optional and not res.startswith("Optional") and not res.endswith("| None"):
        res = f"{res} | None"
    return res


@cache
def _get_source(obj: Any) -> str:
    """Get and cache the source for a Python object.

    Args:
        obj: The object whose source should be retrieved.

    Returns:
        The source code for the object.
    """
    return inspect.getsource(obj)


@cache
def _get_class_prop_comments(clz: type[Component]) -> Mapping[str, tuple[str, ...]]:
    """Parse and cache prop comments for a component class.

    Args:
        clz: The class to extract prop comments from.

    Returns:
        An immutable mapping of prop name to comment lines.
    """
    props_comments: dict[str, tuple[str, ...]] = {}
    comments = []
    last_prop = ""
    in_docstring = False
    docstring_lines: list[str] = []
    for line in _get_source(clz).splitlines():
        stripped = line.strip()

        # Handle triple-quoted docstrings after prop definitions.
        # This must be checked before the `def ` boundary so that
        # docstring prose containing "def " doesn't break the loop.
        if in_docstring:
            if '"""' in stripped or "'''" in stripped:
                # End of multi-line docstring.
                if '"""' in stripped:
                    end_text = stripped.partition('"""')[0].strip()
                else:
                    end_text = stripped.partition("'''")[0].strip()
                if end_text:
                    docstring_lines.append(end_text)
                if last_prop and docstring_lines:
                    props_comments[last_prop] = tuple(docstring_lines)
                in_docstring = False
                docstring_lines = []
                last_prop = ""
            else:
                docstring_lines.append(stripped)
            continue

        reached_functions = re.search(r"def ", line)
        if reached_functions:
            # We've reached the functions, so stop.
            break

        # Check for start of a docstring right after a prop.
        if last_prop and (stripped.startswith(('"""', "'''"))):
            quote = '"""' if stripped.startswith('"""') else "'''"
            content_after_open = stripped[3:]
            if quote in content_after_open:
                # Single-line docstring: """text"""
                doc_text = content_after_open.partition(quote)[0].strip()
                if doc_text:
                    props_comments[last_prop] = (doc_text,)
                last_prop = ""
            else:
                # Multi-line docstring starts here.
                in_docstring = True
                docstring_lines = []
                first_line = content_after_open.strip()
                if first_line:
                    docstring_lines.append(first_line)
            continue

        if line == "":
            # We hit a blank line, so clear comments to avoid commented out prop appearing in next prop docs.
            comments.clear()
            last_prop = ""
            continue

        # Get comments for prop
        if stripped.startswith("#"):
            # Remove noqa from the comments.
            line = line.partition(" # noqa")[0]
            comments.append(line)
            last_prop = ""
            continue

        # Check if this line has a prop.
        match = re.search(r"\w+:", line)
        if match is None:
            # This line doesn't have a var, so continue.
            last_prop = ""
            continue

        # Get the prop.
        prop = match.group(0).strip(":")
        if comments:
            props_comments[prop] = tuple(
                comment.strip().lstrip("#").strip() for comment in comments
            )
        comments.clear()
        last_prop = prop

    return MappingProxyType(props_comments)


@cache
def _get_full_argspec(func: Callable) -> inspect.FullArgSpec:
    """Get and cache the full argspec for a callable.

    Args:
        func: The callable to inspect.

    Returns:
        The full argument specification.
    """
    return getfullargspec(func)


@cache
def _get_signature_return_annotation(func: Callable) -> Any:
    """Get and cache a callable's return annotation.

    Args:
        func: The callable to inspect.

    Returns:
        The callable's return annotation.
    """
    return inspect.signature(func).return_annotation


@cache
def _get_module_star_imports(module_name: str) -> Mapping[str, Any]:
    """Resolve names imported by `from module import *`.

    Args:
        module_name: The module to inspect.

    Returns:
        An immutable mapping of imported names to values.
    """
    module = importlib.import_module(module_name)
    exported_names = getattr(module, "__all__", None)
    if exported_names is not None:
        return MappingProxyType({
            name: getattr(module, name) for name in exported_names
        })
    return MappingProxyType({
        name: value for name, value in vars(module).items() if not name.startswith("_")
    })


@cache
def _get_module_selected_imports(
    module_name: str, imported_names: tuple[str, ...]
) -> Mapping[str, Any]:
    """Resolve a set of imported names from a module.

    Args:
        module_name: The module to import from.
        imported_names: The names to resolve.

    Returns:
        An immutable mapping of imported names to values.
    """
    module = importlib.import_module(module_name)
    return MappingProxyType({name: getattr(module, name) for name in imported_names})


@cache
def _get_class_annotation_globals(target_class: type) -> Mapping[str, Any]:
    """Get globals needed to resolve class annotations.

    Args:
        target_class: The class whose annotation globals should be resolved.

    Returns:
        An immutable mapping of globals for the class MRO.
    """
    available_vars: dict[str, Any] = {}
    for module_name in {cls.__module__ for cls in target_class.__mro__}:
        available_vars.update(sys.modules[module_name].__dict__)
    return MappingProxyType(available_vars)


@cache
def _get_class_event_triggers(target_class: type) -> frozenset[str]:
    """Get and cache event trigger names for a class.

    Args:
        target_class: The class to inspect.

    Returns:
        The event trigger names defined on the class.
    """
    return frozenset(target_class.get_event_triggers())


def _generate_imports(
    typing_imports: Iterable[str],
) -> list[ast.ImportFrom | ast.Import]:
    """Generate the import statements for the stub file.

    Args:
        typing_imports: The typing imports to include.

    Returns:
        The list of import statements.
    """
    return [
        *[
            ast.ImportFrom(module=name, names=[ast.alias(name=val) for val in values])  # pyright: ignore [reportCallIssue]
            for name, values in DEFAULT_IMPORTS.items()
        ],
        ast.Import([ast.alias("reflex")]),
    ]


def _maybe_default_event_handler_docstring(
    prop_name: str, fallback: str = "no description"
) -> tuple[str, ...]:
    """Add a docstring for default event handler prop.

    Args:
        prop_name: The name of the prop.
        fallback: The fallback docstring to use if the prop is not a default event handler and has no description.

    Returns:
        The event handler description or the fallback if the prop is not a default event handler.
    """
    try:
        return (DEFAULT_TRIGGERS_AND_DESC[prop_name].description,)
    except KeyError:
        return (fallback,)


def _generate_docstrings(clzs: list[type[Component]], props: list[str]) -> str:
    """Generate the docstrings for the create method.

    Args:
        clzs: The classes to generate docstrings for.
        props: The props to generate docstrings for.

    Returns:
        The docstring for the create method.
    """
    props_comments = {}
    for clz in clzs:
        for prop, comment_lines in _get_class_prop_comments(clz).items():
            if prop in props:
                props_comments[prop] = list(comment_lines)
        for prop, field in clz._fields.items():
            if prop in props and field.doc:
                props_comments[prop] = [field.doc]
    clz = clzs[0]
    new_docstring = []
    for line in (clz.create.__doc__ or "").splitlines():
        if "**" in line:
            indent = line.split("**")[0]
            new_docstring.extend([
                f"{indent}{prop_name}: {' '.join(props_comments.get(prop_name, _maybe_default_event_handler_docstring(prop_name)))}"
                for prop_name in props
            ])
        new_docstring.append(line)
    return "\n".join(new_docstring)


def _extract_func_kwargs_as_ast_nodes(
    func: Callable,
    type_hint_globals: dict[str, Any],
) -> list[tuple[ast.arg, ast.Constant | None]]:
    """Get the kwargs already defined on the function.

    Args:
        func: The function to extract kwargs from.
        type_hint_globals: The globals to use to resolving a type hint str.

    Returns:
        The list of kwargs as ast arg nodes.
    """
    spec = _get_full_argspec(func)
    kwargs = []

    for kwarg in spec.kwonlyargs:
        arg = ast.arg(arg=kwarg)
        if kwarg in spec.annotations:
            arg.annotation = ast.Name(
                id=_get_type_hint(spec.annotations[kwarg], type_hint_globals)
            )
        default = None
        if spec.kwonlydefaults is not None and kwarg in spec.kwonlydefaults:
            default = ast.Constant(value=spec.kwonlydefaults[kwarg])
        kwargs.append((arg, default))
    return kwargs


def _extract_class_props_as_ast_nodes(
    func: Callable,
    clzs: list[type],
    type_hint_globals: dict[str, Any],
    extract_real_default: bool = False,
) -> Sequence[tuple[ast.arg, ast.Constant | None]]:
    """Get the props defined on the class and all parents.

    Args:
        func: The function that kwargs will be added to.
        clzs: The classes to extract props from.
        type_hint_globals: The globals to use to resolving a type hint str.
        extract_real_default: Whether to extract the real default value from the
            pydantic field definition.

    Returns:
        The sequence of props as ast arg nodes
    """
    spec = _get_full_argspec(func)
    func_kwonlyargs = set(spec.kwonlyargs)
    all_props: set[str] = set()
    kwargs = deque()
    for target_class in reversed(clzs):
        event_triggers = _get_class_event_triggers(target_class)
        # Import from the target class to ensure type hints are resolvable.
        type_hint_globals.update(_get_module_star_imports(target_class.__module__))
        annotation_globals = {
            **type_hint_globals,
            **_get_class_annotation_globals(target_class),
        }
        # State attr isn't really a prop and cannot be resolved, so pop it off.
        target_class.__annotations__.pop("State", None)
        type_hints = typing.get_type_hints(target_class, globalns=annotation_globals)
        for name, value in reversed(type_hints.items()):
            if (
                name in func_kwonlyargs
                or name in EXCLUDED_PROPS
                or name in all_props
                or name in event_triggers
                or get_origin(value) is ClassVar
            ):
                continue
            all_props.add(name)

            default = None
            if extract_real_default:
                # TODO: This is not currently working since the default is not type compatible
                #       with the annotation in some cases.
                with contextlib.suppress(AttributeError, KeyError):
                    # Try to get default from pydantic field definition.
                    default = target_class.__fields__[name].default
                    if isinstance(default, Var):
                        default = default._decode()

            kwargs.appendleft((
                ast.arg(
                    arg=name,
                    annotation=ast.Name(
                        id=OVERWRITE_TYPES.get(
                            name,
                            _get_type_hint(
                                value,
                                annotation_globals,
                            ),
                        )
                    ),
                ),
                ast.Constant(value=default),  # pyright: ignore [reportArgumentType]
            ))
    return kwargs


def _get_visible_type_name(
    typ: Any, type_hint_globals: Mapping[str, Any] | None
) -> str | None:
    """Get a visible identifier for a type in the current module.

    Args:
        typ: The type annotation to resolve.
        type_hint_globals: The globals visible in the current module.

    Returns:
        The visible identifier if one exists, otherwise None.
    """
    if type_hint_globals is None:
        return None

    type_module = getattr(typ, "__module__", None)
    type_name = getattr(typ, "__name__", None)

    if type_name is not None and (
        type_hint_globals.get(type_name) is typ
        or type_name in DEFAULT_IMPORTS.get(str(type_module), set())
        or type_name in EXCLUDED_IMPORTS.get(str(type_module), set())
    ):
        return type_name

    for name, value in type_hint_globals.items():
        if name.isidentifier() and value is typ:
            return name

    return None


def type_to_ast(
    typ: Any,
    cls: type,
    type_hint_globals: Mapping[str, Any] | None = None,
) -> ast.expr:
    """Converts any type annotation into its AST representation.
    Handles nested generic types, unions, etc.

    Args:
        typ: The type annotation to convert.
        cls: The class where the type annotation is used.
        type_hint_globals: The globals visible where the annotation is used.

    Returns:
        The AST representation of the type annotation.
    """
    if typ is type(None) or typ is None:
        return ast.Name(id="None")

    origin = get_origin(typ)
    if origin is typing.Literal:
        return ast.Subscript(
            value=ast.Name(id="Literal"),
            slice=ast.Tuple(
                elts=[ast.Constant(value=val) for val in get_args(typ)], ctx=ast.Load()
            ),
            ctx=ast.Load(),
        )
    if origin is UnionType:
        origin = typing.Union

    # Handle plain types (int, str, custom classes, etc.)
    if origin is None:
        if hasattr(typ, "__name__"):
            if typ.__module__.startswith("reflex."):
                typ_parts = typ.__module__.split(".")
                cls_parts = cls.__module__.split(".")

                zipped = list(zip(typ_parts, cls_parts, strict=False))

                if all(a == b for a, b in zipped) and len(typ_parts) == len(cls_parts):
                    return ast.Name(id=typ.__name__)
                if visible_name := _get_visible_type_name(typ, type_hint_globals):
                    return ast.Name(id=visible_name)
                return ast.Name(id=typ.__module__ + "." + typ.__name__)
            return ast.Name(id=typ.__name__)
        if hasattr(typ, "_name"):
            return ast.Name(id=typ._name)
        return ast.Name(id=str(typ))

    # Get the base type name (List, Dict, Optional, etc.)
    base_name = getattr(origin, "_name", origin.__name__)

    # Get type arguments
    args = get_args(typ)

    # Handle empty type arguments
    if not args:
        return ast.Name(id=base_name)

    # Convert all type arguments recursively
    arg_nodes = [type_to_ast(arg, cls, type_hint_globals) for arg in args]

    # Special case for single-argument types (like list[T] or Optional[T])
    if len(arg_nodes) == 1:
        slice_value = arg_nodes[0]
    else:
        slice_value = ast.Tuple(elts=arg_nodes, ctx=ast.Load())

    return ast.Subscript(
        value=ast.Name(id=base_name),
        slice=slice_value,
        ctx=ast.Load(),
    )


@cache
def _get_parent_imports(func: Callable) -> Mapping[str, tuple[str, ...]]:
    """Get parent imports needed to resolve forwarded type hints.

    Args:
        func: The callable whose annotations are being analyzed.

    Returns:
        An immutable mapping of module names to imported symbol names.
    """
    imports_: dict[str, set[str]] = {"reflex_base.vars": {"Var"}}
    module_dir = set(dir(importlib.import_module(func.__module__)))
    for type_hint in inspect.get_annotations(func).values():
        try:
            match = re.match(r"\w+\[([\w\d]+)\]", type_hint)
        except TypeError:
            continue
        if match:
            type_hint = match.group(1)
            if type_hint in module_dir:
                imports_.setdefault(func.__module__, set()).add(type_hint)
    return MappingProxyType({
        module_name: tuple(sorted(imported_names))
        for module_name, imported_names in imports_.items()
    })


def _generate_component_create_functiondef(
    clz: type[Component],
    type_hint_globals: dict[str, Any],
    lineno: int,
    decorator_list: Sequence[ast.expr] = (ast.Name(id="classmethod"),),
) -> ast.FunctionDef:
    """Generate the create function definition for a Component.

    Args:
        clz: The Component class to generate the create functiondef for.
        type_hint_globals: The globals to use to resolving a type hint str.
        lineno: The line number to use for the ast nodes.
        decorator_list: The list of decorators to apply to the create functiondef.

    Returns:
        The create functiondef node for the ast.

    Raises:
        TypeError: If clz is not a subclass of Component.
    """
    if not issubclass(clz, Component):
        msg = f"clz must be a subclass of Component, not {clz!r}"
        raise TypeError(msg)

    # add the imports needed by get_type_hint later
    type_hint_globals.update({
        name: getattr(typing, name) for name in DEFAULT_TYPING_IMPORTS
    })

    if clz.__module__ != clz.create.__module__:
        imports_ = _get_parent_imports(clz.create)
        for name, values in imports_.items():
            type_hint_globals.update(_get_module_selected_imports(name, values))

    kwargs = _extract_func_kwargs_as_ast_nodes(clz.create, type_hint_globals)

    # kwargs associated with props defined in the class and its parents
    all_classes = [c for c in clz.__mro__ if issubclass(c, Component)]
    prop_kwargs = _extract_class_props_as_ast_nodes(
        clz.create, all_classes, type_hint_globals
    )
    all_props = [arg[0].arg for arg in prop_kwargs]
    kwargs.extend(prop_kwargs)

    def figure_out_return_type(annotation: Any):
        if isinstance(annotation, type) and issubclass(annotation, inspect._empty):
            return ast.Name(id="EventType[Any]")

        if not isinstance(annotation, str) and get_origin(annotation) is tuple:
            arguments = get_args(annotation)

            arguments_without_var = [
                get_args(argument)[0] if get_origin(argument) == Var else argument
                for argument in arguments
            ]

            # Convert each argument type to its AST representation
            type_args = [
                type_to_ast(arg, cls=clz, type_hint_globals=type_hint_globals)
                for arg in arguments_without_var
            ]

            # Get all prefixes of the type arguments
            all_count_args_type = [
                ast.Name(
                    f"EventType[{', '.join([ast.unparse(arg) for arg in type_args[:i]])}]"
                )
                if i > 0
                else ast.Name("EventType[()]")
                for i in range(len(type_args) + 1)
            ]

            # Create EventType using the joined string
            return ast.Name(id=f"{' | '.join(map(ast.unparse, all_count_args_type))}")

        if isinstance(annotation, str) and annotation.lower().startswith("tuple["):
            inside_of_tuple = (
                annotation
                .removeprefix("tuple[")
                .removeprefix("Tuple[")
                .removesuffix("]")
            )

            if inside_of_tuple == "()":
                return ast.Name(id="EventType[()]")

            arguments = [""]

            bracket_count = 0

            for char in inside_of_tuple:
                if char == "[":
                    bracket_count += 1
                elif char == "]":
                    bracket_count -= 1

                if char == "," and bracket_count == 0:
                    arguments.append("")
                else:
                    arguments[-1] += char

            arguments = [argument.strip() for argument in arguments]

            arguments_without_var = [
                argument.removeprefix("Var[").removesuffix("]")
                if argument.startswith("Var[")
                else argument
                for argument in arguments
            ]

            all_count_args_type = [
                ast.Name(f"EventType[{', '.join(arguments_without_var[:i])}]")
                if i > 0
                else ast.Name("EventType[()]")
                for i in range(len(arguments) + 1)
            ]

            return ast.Name(id=f"{' | '.join(map(ast.unparse, all_count_args_type))}")
        return ast.Name(id="EventType[Any]")

    event_triggers = clz.get_event_triggers()

    # event handler kwargs
    kwargs.extend(
        (
            ast.arg(
                arg=trigger,
                annotation=ast.Subscript(
                    ast.Name("Optional"),
                    ast.Name(
                        id=ast.unparse(
                            figure_out_return_type(
                                _get_signature_return_annotation(event_specs)
                            )
                            if not isinstance(
                                event_specs := event_triggers[trigger], Sequence
                            )
                            else ast.Subscript(
                                ast.Name("Union"),
                                ast.Tuple([
                                    figure_out_return_type(
                                        _get_signature_return_annotation(event_spec)
                                    )
                                    for event_spec in event_specs
                                ]),
                            )
                        )
                    ),
                ),
            ),
            ast.Constant(value=None),
        )
        for trigger in sorted(event_triggers)
    )

    logger.debug(f"Generated {clz.__name__}.create method with {len(kwargs)} kwargs")
    create_args = ast.arguments(
        args=[ast.arg(arg="cls")],
        posonlyargs=[],
        vararg=ast.arg(arg="children"),
        kwonlyargs=[arg[0] for arg in kwargs],
        kw_defaults=[arg[1] for arg in kwargs],
        kwarg=ast.arg(arg="props"),
        defaults=[],
    )

    return ast.FunctionDef(  # pyright: ignore [reportCallIssue]
        name="create",
        args=create_args,
        body=[
            ast.Expr(
                value=ast.Constant(
                    value=_generate_docstrings(
                        all_classes, [*all_props, *event_triggers]
                    )
                ),
            ),
            ast.Expr(
                value=ast.Constant(value=Ellipsis),
            ),
        ],
        decorator_list=list(decorator_list),
        lineno=lineno,
        returns=ast.Constant(value=clz.__name__),
    )


def _generate_staticmethod_call_functiondef(
    node: ast.ClassDef,
    clz: type[Component] | type[SimpleNamespace],
    type_hint_globals: dict[str, Any],
) -> ast.FunctionDef | None:
    fullspec = _get_full_argspec(clz.__call__)

    call_args = ast.arguments(
        args=[
            ast.arg(
                name,
                annotation=ast.Name(
                    id=_get_type_hint(
                        anno := fullspec.annotations[name],
                        type_hint_globals,
                        is_optional=_is_optional(anno),
                    )
                ),
            )
            for name in fullspec.args
        ],
        posonlyargs=[],
        kwonlyargs=[],
        kw_defaults=[],
        kwarg=ast.arg(arg="props"),
        defaults=(
            [ast.Constant(value=default) for default in fullspec.defaults]
            if fullspec.defaults
            else []
        ),
    )
    return ast.FunctionDef(  # pyright: ignore [reportCallIssue]
        name="__call__",
        args=call_args,
        body=[
            ast.Expr(value=ast.Constant(value=clz.__call__.__doc__)),
            ast.Expr(
                value=ast.Constant(...),
            ),
        ],
        decorator_list=[ast.Name(id="staticmethod")],
        lineno=node.lineno,
        returns=ast.Constant(
            value=_get_type_hint(
                typing.get_type_hints(clz.__call__).get("return", None),
                type_hint_globals,
                is_optional=False,
            )
        ),
    )


def _generate_namespace_call_functiondef(
    node: ast.ClassDef,
    clz_name: str,
    classes: dict[str, type[Component] | type[SimpleNamespace]],
    type_hint_globals: dict[str, Any],
) -> ast.FunctionDef | None:
    """Generate the __call__ function definition for a SimpleNamespace.

    Args:
        node: The existing __call__ classdef parent node from the ast
        clz_name: The name of the SimpleNamespace class to generate the __call__ functiondef for.
        classes: Map name to actual class definition.
        type_hint_globals: The globals to use to resolving a type hint str.

    Returns:
        The create functiondef node for the ast.
    """
    # add the imports needed by get_type_hint later
    type_hint_globals.update({
        name: getattr(typing, name) for name in DEFAULT_TYPING_IMPORTS
    })

    clz = classes[clz_name]

    if not hasattr(clz.__call__, "__self__"):
        return _generate_staticmethod_call_functiondef(node, clz, type_hint_globals)

    # Determine which class is wrapped by the namespace __call__ method
    component_clz = clz.__call__.__self__

    if clz.__call__.__func__.__name__ != "create":  # pyright: ignore [reportFunctionMemberAccess]
        return None

    if not issubclass(component_clz, Component):
        return None

    definition = _generate_component_create_functiondef(
        clz=component_clz,
        type_hint_globals=type_hint_globals,
        lineno=node.lineno,
        decorator_list=[],
    )
    definition.name = "__call__"

    # Turn the definition into a staticmethod
    del definition.args.args[0]  # remove `cls` arg
    definition.decorator_list = [ast.Name(id="staticmethod")]

    return definition


class StubGenerator(ast.NodeTransformer):
    """A node transformer that will generate the stubs for a given module."""

    def __init__(
        self,
        module: ModuleType,
        classes: dict[str, type[Component | SimpleNamespace]],
    ):
        """Initialize the stub generator.

        Args:
            module: The actual module object module to generate stubs for.
            classes: The actual Component class objects to generate stubs for.
        """
        super().__init__()
        # Dict mapping class name to actual class object.
        self.classes = classes
        # Track the last class node that was visited.
        self.current_class = None
        # These imports will be included in the AST of stub files.
        self.typing_imports = DEFAULT_TYPING_IMPORTS.copy()
        # Whether those typing imports have been inserted yet.
        self.inserted_imports = False
        # This dict is used when evaluating type hints.
        self.type_hint_globals = module.__dict__.copy()

    @staticmethod
    def _remove_docstring(
        node: ast.Module | ast.ClassDef | ast.FunctionDef,
    ) -> ast.Module | ast.ClassDef | ast.FunctionDef:
        """Removes any docstring in place.

        Args:
            node: The node to remove the docstring from.

        Returns:
            The modified node.
        """
        if (
            node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
        ):
            node.body.pop(0)
        return node

    def _current_class_is_component(self) -> type[Component] | None:
        """Check if the current class is a Component.

        Returns:
            Whether the current class is a Component.
        """
        if (
            self.current_class is not None
            and self.current_class in self.classes
            and issubclass((clz := self.classes[self.current_class]), Component)
        ):
            return clz
        return None

    def visit_Module(self, node: ast.Module) -> ast.Module:
        """Visit a Module node and remove docstring from body.

        Args:
            node: The Module node to visit.

        Returns:
            The modified Module node.
        """
        self.generic_visit(node)
        return self._remove_docstring(node)  # pyright: ignore [reportReturnType]

    def visit_Import(
        self, node: ast.Import | ast.ImportFrom
    ) -> ast.Import | ast.ImportFrom | list[ast.Import | ast.ImportFrom]:
        """Collect import statements from the module.

        If this is the first import statement, insert the typing imports before it.

        Args:
            node: The import node to visit.

        Returns:
            The modified import node(s).
        """
        # Drop any imports in the EXCLUDED_IMPORTS mapping since they are supplied by DEFAULT_IMPORTS.
        if isinstance(node, ast.ImportFrom) and node.module in EXCLUDED_IMPORTS:
            node.names = [
                alias
                for alias in node.names
                if alias.name not in EXCLUDED_IMPORTS[node.module]
            ]
        if not self.inserted_imports:
            self.inserted_imports = True
            default_imports = _generate_imports(self.typing_imports)
            return [*default_imports, *([node] if node.names else ())]
        if not node.names:
            return []
        return node

    def visit_ImportFrom(
        self, node: ast.ImportFrom
    ) -> ast.Import | ast.ImportFrom | list[ast.Import | ast.ImportFrom] | None:
        """Visit an ImportFrom node.

        Remove any `from __future__ import *` statements, and hand off to visit_Import.

        Args:
            node: The ImportFrom node to visit.

        Returns:
            The modified ImportFrom node.
        """
        if node.module == "__future__":
            return None  # ignore __future__ imports: https://docs.astral.sh/ruff/rules/future-annotations-in-stub/
        return self.visit_Import(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.ClassDef:
        """Visit a ClassDef node.

        Remove all assignments in the class body, and add a create functiondef
        if one does not exist.

        Args:
            node: The ClassDef node to visit.

        Returns:
            The modified ClassDef node.
        """
        self.current_class = node.name
        self._remove_docstring(node)

        # Define `__call__` as a real function so the docstring appears in the stub.
        call_definition = None
        for child in node.body[:]:
            found_call = False
            if (
                isinstance(child, ast.AnnAssign)
                and isinstance(child.target, ast.Name)
                and child.target.id.startswith("_")
            ):
                node.body.remove(child)
            if isinstance(child, ast.Assign):
                for target in child.targets[:]:
                    if isinstance(target, ast.Name) and target.id == "__call__":
                        child.targets.remove(target)
                        found_call = True
                if not found_call:
                    continue
                if not child.targets[:]:
                    node.body.remove(child)
                call_definition = _generate_namespace_call_functiondef(
                    node,
                    self.current_class,
                    self.classes,
                    type_hint_globals=self.type_hint_globals,
                )
                break

        self.generic_visit(node)  # Visit child nodes.

        if (
            not any(
                isinstance(child, ast.FunctionDef) and child.name == "create"
                for child in node.body
            )
            and (clz := self._current_class_is_component()) is not None
        ):
            # Add a new .create FunctionDef since one does not exist.
            node.body.append(
                _generate_component_create_functiondef(
                    clz=clz,
                    type_hint_globals=self.type_hint_globals,
                    lineno=node.lineno,
                )
            )
        if call_definition is not None:
            node.body.append(call_definition)
        if not node.body:
            # We should never return an empty body.
            node.body.append(ast.Expr(value=ast.Constant(value=Ellipsis)))
        self.current_class = None
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        """Visit a FunctionDef node.

        Special handling for `.create` functions to add type hints for all props
        defined on the component class.

        Remove all private functions and blank out the function body of the
        remaining public functions.

        Args:
            node: The FunctionDef node to visit.

        Returns:
            The modified FunctionDef node (or None).
        """
        if (
            node.name == "create"
            and self.current_class in self.classes
            and issubclass((clz := self.classes[self.current_class]), Component)
        ):
            node = _generate_component_create_functiondef(
                clz=clz,
                type_hint_globals=self.type_hint_globals,
                lineno=node.lineno,
                decorator_list=node.decorator_list,
            )
        else:
            if node.name.startswith("_") and node.name != "__call__":
                return None  # remove private methods

            if node.body[-1] != ast.Expr(value=ast.Constant(value=Ellipsis)):
                # Blank out the function body for public functions.
                node.body = [ast.Expr(value=ast.Constant(value=Ellipsis))]
        return node

    def visit_Assign(self, node: ast.Assign) -> ast.Assign | None:
        """Remove non-annotated assignment statements.

        Args:
            node: The Assign node to visit.

        Returns:
            The modified Assign node (or None).
        """
        # Special case for assignments to `typing.Any` as fallback.
        if (
            node.value is not None
            and isinstance(node.value, ast.Name)
            and node.value.id == "Any"
        ):
            return node

        if self._current_class_is_component():
            # Remove annotated assignments in Component classes (props)
            return None

        # remove dunder method assignments for lazy_loader.attach
        for target in node.targets:
            if isinstance(target, ast.Tuple):
                for name in target.elts:
                    if isinstance(name, ast.Name) and name.id.startswith("_"):
                        return None

        return node

    def visit_Expr(self, node: ast.Expr) -> ast.Expr | None:
        """Remove bare string expressions (attribute docstrings) in component classes.

        Args:
            node: The Expr node to visit.

        Returns:
            The modified Expr node (or None).
        """
        if (
            self._current_class_is_component()
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            return None
        return node

    def visit_AnnAssign(self, node: ast.AnnAssign) -> ast.AnnAssign | None:
        """Visit an AnnAssign node (Annotated assignment).

        Remove private target and remove the assignment value in the stub.

        Args:
            node: The AnnAssign node to visit.

        Returns:
            The modified AnnAssign node (or None).
        """
        # skip ClassVars
        if (
            isinstance(node.annotation, ast.Subscript)
            and isinstance(node.annotation.value, ast.Name)
            and node.annotation.value.id == "ClassVar"
        ):
            return node
        if isinstance(node.target, ast.Name) and node.target.id.startswith("_"):
            return None
        if self._current_class_is_component():
            # Remove annotated assignments in Component classes (props)
            return None
        # Blank out assignments in type stubs.
        node.value = None
        return node


class InitStubGenerator(StubGenerator):
    """A node transformer that will generate the stubs for a given init file."""

    def visit_Import(
        self, node: ast.Import | ast.ImportFrom
    ) -> ast.Import | ast.ImportFrom | list[ast.Import | ast.ImportFrom]:
        """Collect import statements from the init module.

        Args:
            node: The import node to visit.

        Returns:
                The modified import node(s).
        """
        return [node]


def _path_to_module_name(path: Path) -> str:
    """Convert a file path to a dotted module name.

    Args:
        path: The file path to convert.

    Returns:
        The dotted module name.
    """
    return _relative_to_pwd(path).with_suffix("").as_posix().replace("/", ".")


def _write_pyi_file(module_path: Path, source: str) -> str:
    relpath = str(_relative_to_pwd(module_path)).replace("\\", "/")
    pyi_content = (
        "\n".join([
            f'"""Stub file for {relpath}"""',
            "# ------------------- DO NOT EDIT ----------------------",
            "# This file was generated by `reflex/utils/pyi_generator.py`!",
            "# ------------------------------------------------------",
            "",
        ])
        + source
    )

    pyi_path = module_path.with_suffix(".pyi")
    pyi_path.write_text(pyi_content)
    logger.info(f"Wrote {relpath}")
    return md5(pyi_content.encode()).hexdigest()


# Mapping from component subpackage name to its target Python package.
_COMPONENT_SUBPACKAGE_TARGETS: dict[str, str] = {
    # reflex-components (base package)
    "base": "reflex_components_core.base",
    "core": "reflex_components_core.core",
    "datadisplay": "reflex_components_core.datadisplay",
    "el": "reflex_components_core.el",
    "gridjs": "reflex_components_gridjs",
    "lucide": "reflex_components_lucide",
    "moment": "reflex_components_moment",
    # Deep overrides (datadisplay split)
    "datadisplay.code": "reflex_components_code.code",
    "datadisplay.shiki_code_block": "reflex_components_code.shiki_code_block",
    "datadisplay.dataeditor": "reflex_components_dataeditor.dataeditor",
    # Standalone packages
    "markdown": "reflex_components_markdown",
    "plotly": "reflex_components_plotly",
    "radix": "reflex_components_radix",
    "react_player": "reflex_components_react_player",
    "react_router": "reflex_components_core.react_router",
    "recharts": "reflex_components_recharts",
    "sonner": "reflex_components_sonner",
}


def _rewrite_component_import(module: str, is_reflex_package: bool) -> str:
    """Rewrite a lazy-loader module path to the correct absolute package import.

    Args:
        module: The module path from ``_SUBMOD_ATTRS`` (e.g. ``"components.radix.themes.base"``).
        is_reflex_package: Whether the module is part of the Reflex package.

    Returns:
        An absolute import path (``"reflex_components_radix.themes.base"``) for moved
        components, or a relative path (``".components.component"``) for everything else.
    """
    if is_reflex_package and module == "components":
        # "components": ["el", "radix", ...] — these are re-exported submodules.
        # Can't map to a single package, but the pyi generator handles each attr individually.
        return "reflex_components_core"
    if is_reflex_package and module.startswith("components."):
        rest = module[len("components.") :]
        # Try progressively deeper matches (e.g. "datadisplay.code" before "datadisplay").
        parts = rest.split(".")
        for depth in range(min(len(parts), 2), 0, -1):
            key = ".".join(parts[:depth])
            target = _COMPONENT_SUBPACKAGE_TARGETS.get(key)
            if target is not None:
                remainder = ".".join(parts[depth:])
                return f"{target}.{remainder}" if remainder else target
    return f".{module}"


def _get_init_lazy_imports(mod: ModuleType, new_tree: ast.AST):
    # retrieve the _SUBMODULES and _SUBMOD_ATTRS from an init file if present.
    sub_mods: set[str] | None = getattr(mod, "_SUBMODULES", None)
    sub_mod_attrs: dict[str, list[str | tuple[str, str]]] | None = getattr(
        mod, "_SUBMOD_ATTRS", None
    )
    extra_mappings: dict[str, str] | None = getattr(mod, "_EXTRA_MAPPINGS", None)

    if not sub_mods and not sub_mod_attrs and not extra_mappings:
        return None
    sub_mods_imports = []
    sub_mod_attrs_imports = []
    extra_mappings_imports = []

    if sub_mods:
        sub_mods_imports = [f"from . import {mod}" for mod in sorted(sub_mods)]
        sub_mods_imports.append("")

    is_reflex_package = bool(mod.__name__.partition(".")[0] == "reflex")

    if sub_mod_attrs:
        flattened_sub_mod_attrs = {
            imported: module
            for module, attrs in sub_mod_attrs.items()
            for imported in attrs
        }
        # construct the import statement and handle special cases for aliases
        for imported, module in flattened_sub_mod_attrs.items():
            # For "components": ["el", "radix", ...], resolve each attr to its package.
            if (
                is_reflex_package
                and module == "components"
                and isinstance(imported, str)
                and imported in _COMPONENT_SUBPACKAGE_TARGETS
            ):
                target = _COMPONENT_SUBPACKAGE_TARGETS[imported]
                sub_mod_attrs_imports.append(f"import {target} as {imported}")
                continue

            rewritten = _rewrite_component_import(module, is_reflex_package)
            if isinstance(imported, tuple):
                suffix = (
                    (imported[0] + " as " + imported[1])
                    if imported[0] != imported[1]
                    else imported[0]
                )
            else:
                suffix = imported
            sub_mod_attrs_imports.append(f"from {rewritten} import {suffix}")
        sub_mod_attrs_imports.append("")

    if extra_mappings:
        for alias, import_path in extra_mappings.items():
            if "." not in import_path:
                # Handle simple module imports (e.g. "import reflex_components_markdown as markdown").
                extra_mappings_imports.append(f"import {import_path} as {alias}")
                continue
            module_name, import_name = import_path.rsplit(".", 1)
            extra_mappings_imports.append(
                f"from {module_name} import {import_name} as {alias}"
            )

    text = (
        "\n"
        + "\n".join([
            *sub_mods_imports,
            *sub_mod_attrs_imports,
            *extra_mappings_imports,
        ])
        + "\n"
    )
    text += ast.unparse(new_tree) + "\n\n"
    text += f"__all__ = {getattr(mod, '__all__', [])!r}\n"
    return text


def _scan_file(module_path: Path) -> tuple[str, str] | None:
    """Process a single Python file and generate its .pyi stub.

    Args:
        module_path: Path to the Python source file.

    Returns:
        Tuple of (pyi_path, content_hash) or None if no stub needed.
    """
    module_import = _path_to_module_name(module_path)
    module = importlib.import_module(module_import)
    logger.debug(f"Read {module_path}")
    class_names = {
        name: obj
        for name, obj in vars(module).items()
        if isinstance(obj, type)
        and (_safe_issubclass(obj, Component) or _safe_issubclass(obj, SimpleNamespace))
        and obj != Component
        and inspect.getmodule(obj) == module
    }
    is_init_file = _relative_to_pwd(module_path).name == "__init__.py"
    if not class_names and not is_init_file:
        return None

    if is_init_file:
        new_tree = InitStubGenerator(module, class_names).visit(
            ast.parse(_get_source(module))
        )
        init_imports = _get_init_lazy_imports(module, new_tree)
        if not init_imports:
            return None
        content_hash = _write_pyi_file(module_path, init_imports)
    else:
        new_tree = StubGenerator(module, class_names).visit(
            ast.parse(_get_source(module))
        )
        content_hash = _write_pyi_file(module_path, ast.unparse(new_tree))
    return str(module_path.with_suffix(".pyi").resolve()), content_hash


class PyiGenerator:
    """A .pyi file generator that will scan all defined Component in Reflex and
    generate the appropriate stub.
    """

    modules: list = []
    root: str = ""
    current_module: Any = {}
    written_files: list[tuple[str, str]] = []

    def _scan_files(self, files: list[Path]):
        max_workers = min(multiprocessing.cpu_count() or 1, len(files), 8)
        use_parallel = (
            max_workers > 1 and "fork" in multiprocessing.get_all_start_methods()
        )

        if not use_parallel:
            # Serial fallback: _scan_file handles its own imports.
            for file in files:
                result = _scan_file(file)
                if result is not None:
                    self.written_files.append(result)
            return

        raise_on_failed_imports_key = "PYI_GENERATOR_RAISE_FAILED_IMPORTS"
        raise_on_failed_imports = os.getenv(raise_on_failed_imports_key)

        raise_if_failed_imports = (
            interpret_boolean_env(raise_on_failed_imports, raise_on_failed_imports_key)
            if raise_on_failed_imports is not None
            else False
        )

        # Pre-import all modules sequentially to populate sys.modules
        # so forked workers inherit the cache and skip redundant imports.
        importable_files: list[Path] = []
        for file in files:
            module_import = _path_to_module_name(file)
            try:
                importlib.import_module(module_import)
                importable_files.append(file)
            except Exception:
                logger.exception(f"Failed to import {module_import}")
                if raise_if_failed_imports:
                    raise

        # Generate stubs in parallel using forked worker processes.
        ctx = multiprocessing.get_context("fork")
        with ProcessPoolExecutor(max_workers=max_workers, mp_context=ctx) as executor:
            self.written_files.extend(
                r for r in executor.map(_scan_file, importable_files) if r is not None
            )

    def scan_all(
        self,
        targets: list,
        changed_files: list[Path] | None = None,
        use_json: bool = False,
    ):
        """Scan all targets for class inheriting Component and generate the .pyi files.

        Args:
            targets: the list of file/folders to scan.
            changed_files (optional): the list of changed files since the last run.
            use_json: whether to use json to store the hashes.
        """
        file_targets = []
        for target in targets:
            target_path = Path(target)
            if (
                target_path.is_file()
                and target_path.suffix == ".py"
                and target_path.name not in EXCLUDED_FILES
            ):
                file_targets.append(target_path)
                continue
            if not target_path.is_dir():
                continue
            for file_path in _walk_files(target_path):
                relative = _relative_to_pwd(file_path)
                if relative.name in EXCLUDED_FILES or file_path.suffix != ".py":
                    continue
                if (
                    changed_files is not None
                    and _relative_to_pwd(file_path) not in changed_files
                ):
                    continue
                file_targets.append(file_path)

        # check if pyi changed but not the source
        if changed_files is not None:
            for changed_file in changed_files:
                if changed_file.suffix != ".pyi":
                    continue
                py_file_path = changed_file.with_suffix(".py")
                if not py_file_path.exists() and changed_file.exists():
                    changed_file.unlink()
                if py_file_path in file_targets:
                    continue
                subprocess.run(["git", "checkout", changed_file])

        self._scan_files(file_targets)

        file_paths, hashes = (
            [f[0] for f in self.written_files],
            [f[1] for f in self.written_files],
        )

        # Fix generated pyi files with ruff.
        if file_paths:
            subprocess.run(["ruff", "format", *file_paths])
            subprocess.run(["ruff", "check", "--fix", *file_paths])

        if use_json:
            if file_paths and changed_files is None:
                file_paths = list(map(Path, file_paths))
                top_dir = file_paths[0].parent
                for file_path in file_paths:
                    file_parent = file_path.parent
                    while len(file_parent.parts) > len(top_dir.parts):
                        file_parent = file_parent.parent
                    while len(top_dir.parts) > len(file_parent.parts):
                        top_dir = top_dir.parent
                    while not file_parent.samefile(top_dir):
                        file_parent = file_parent.parent
                        top_dir = top_dir.parent

                while (
                    not top_dir.samefile(top_dir.parent)
                    and not (top_dir / PYI_HASHES).exists()
                ):
                    top_dir = top_dir.parent

                pyi_hashes_file = top_dir / PYI_HASHES

                if pyi_hashes_file.exists():
                    pyi_hashes_file.write_text(
                        orjson_dumps(
                            dict(
                                zip(
                                    [
                                        f.relative_to(pyi_hashes_file.parent).as_posix()
                                        for f in file_paths
                                    ],
                                    hashes,
                                    strict=True,
                                )
                            ),
                            indent=2,
                            sort_keys=True,
                        )
                        + "\n",
                    )
            elif file_paths:
                file_paths = list(map(Path, file_paths))
                pyi_hashes_parent = file_paths[0].parent
                while (
                    not pyi_hashes_parent.samefile(pyi_hashes_parent.parent)
                    and not (pyi_hashes_parent / PYI_HASHES).exists()
                ):
                    pyi_hashes_parent = pyi_hashes_parent.parent

                pyi_hashes_file = pyi_hashes_parent / PYI_HASHES
                if pyi_hashes_file.exists():
                    pyi_hashes = orjson_loads(pyi_hashes_file.read_bytes())
                    for file_path, hashed_content in zip(
                        file_paths, hashes, strict=False
                    ):
                        formatted_path = file_path.relative_to(
                            pyi_hashes_parent
                        ).as_posix()
                        pyi_hashes[formatted_path] = hashed_content

                    pyi_hashes_file.write_text(
                        orjson_dumps(pyi_hashes, indent=2, sort_keys=True) + "\n"
                    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate .pyi stub files")
    parser.add_argument(
        "targets",
        nargs="*",
        default=["reflex/components", "reflex/experimental", "reflex/__init__.py"],
        help="Target directories/files to process",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    logging.getLogger("blib2to3.pgen2.driver").setLevel(logging.INFO)

    gen = PyiGenerator()
    gen.scan_all(args.targets, None, use_json=True)
