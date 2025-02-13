"""The pyi generator module."""

from __future__ import annotations

import ast
import contextlib
import importlib
import inspect
import logging
import re
import subprocess
import typing
from fileinput import FileInput
from inspect import getfullargspec
from itertools import chain
from multiprocessing import Pool, cpu_count
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any, Callable, Iterable, Sequence, Type, get_args, get_origin

from reflex.components.component import Component
from reflex.utils import types as rx_types
from reflex.vars.base import Var

logger = logging.getLogger("pyi_generator")

PWD = Path.cwd()

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
    "_invalid_children",
    "_memoization_mode",
    "_rename_props",
    "_valid_children",
    "_valid_parents",
    "State",
]

DEFAULT_TYPING_IMPORTS = {
    "overload",
    "Any",
    "Callable",
    "Dict",
    # "List",
    "Literal",
    "Optional",
    "Union",
}

# TODO: fix import ordering and unused imports with ruff later
DEFAULT_IMPORTS = {
    "typing": sorted(DEFAULT_TYPING_IMPORTS),
    "reflex.components.core.breakpoints": ["Breakpoints"],
    "reflex.event": [
        "EventChain",
        "EventHandler",
        "EventSpec",
        "EventType",
        "KeyInputInfo",
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

    if value is type(None):
        return "None"

    if rx_types.is_union(value):
        if type(None) in value.__args__:
            res_args = [
                _get_type_hint(arg, type_hint_globals, rx_types.is_optional(arg))
                for arg in value.__args__
                if arg is not type(None)
            ]
            res_args.sort()
            if len(res_args) == 1:
                return f"Optional[{res_args[0]}]"
            else:
                res = f"Union[{', '.join(res_args)}]"
                return f"Optional[{res}]"

        res_args = [
            _get_type_hint(arg, type_hint_globals, rx_types.is_optional(arg))
            for arg in value.__args__
        ]
        res_args.sort()
        return f"Union[{', '.join(res_args)}]"

    if args:
        inner_container_type_args = (
            sorted((repr(arg) for arg in args))
            if rx_types.is_literal(value)
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
            raise TypeError(
                f"{value.__module__ + '.' + value.__name__} is not a default import, "
                "add it to DEFAULT_IMPORTS in pyi_generator.py"
            )

        res = f"{value.__name__}[{', '.join(inner_container_type_args)}]"

        if value.__name__ == "Var":
            args = list(
                chain.from_iterable(
                    [get_args(arg) if rx_types.is_union(arg) else [arg] for arg in args]
                )
            )

            # For Var types, Union with the inner args so they can be passed directly.
            types = [res] + [
                _get_type_hint(arg, type_hint_globals, is_optional=False)
                for arg in args
                if arg is not type(None)
            ]
            if len(types) > 1:
                res = ", ".join(sorted(types))
                res = f"Union[{res}]"
    elif isinstance(value, str):
        ev = eval(value, type_hint_globals)
        if rx_types.is_optional(ev):
            return _get_type_hint(ev, type_hint_globals, is_optional=False)

        if rx_types.is_union(ev):
            res = [
                _get_type_hint(arg, type_hint_globals, rx_types.is_optional(arg))
                for arg in ev.__args__
            ]
            return f"Union[{', '.join(res)}]"
        res = (
            _get_type_hint(ev, type_hint_globals, is_optional=False)
            if ev.__name__ == "Var"
            else value
        )
    else:
        res = value.__name__
    if is_optional and not res.startswith("Optional"):
        res = f"Optional[{res}]"
    return res


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


def _generate_docstrings(clzs: list[Type[Component]], props: list[str]) -> str:
    """Generate the docstrings for the create method.

    Args:
        clzs: The classes to generate docstrings for.
        props: The props to generate docstrings for.

    Returns:
        The docstring for the create method.
    """
    props_comments = {}
    comments = []
    for clz in clzs:
        for line in inspect.getsource(clz).splitlines():
            reached_functions = re.search("def ", line)
            if reached_functions:
                # We've reached the functions, so stop.
                break

            if line == "":
                # We hit a blank line, so clear comments to avoid commented out prop appearing in next prop docs.
                comments.clear()
                continue

            # Get comments for prop
            if line.strip().startswith("#"):
                # Remove noqa from the comments.
                line = line.partition(" # noqa")[0]
                comments.append(line)
                continue

            # Check if this line has a prop.
            match = re.search("\\w+:", line)
            if match is None:
                # This line doesn't have a var, so continue.
                continue

            # Get the prop.
            prop = match.group(0).strip(":")
            if prop in props:
                if not comments:  # do not include undocumented props
                    continue
                props_comments[prop] = [
                    comment.strip().strip("#") for comment in comments
                ]
            comments.clear()
    clz = clzs[0]
    new_docstring = []
    for line in (clz.create.__doc__ or "").splitlines():
        if "**" in line:
            indent = line.split("**")[0]
            new_docstring.extend(
                [f"{indent}{n}:{' '.join(c)}" for n, c in props_comments.items()]
            )
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
    spec = getfullargspec(func)
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
    clzs: list[Type],
    type_hint_globals: dict[str, Any],
    extract_real_default: bool = False,
) -> list[tuple[ast.arg, ast.Constant | None]]:
    """Get the props defined on the class and all parents.

    Args:
        func: The function that kwargs will be added to.
        clzs: The classes to extract props from.
        type_hint_globals: The globals to use to resolving a type hint str.
        extract_real_default: Whether to extract the real default value from the
            pydantic field definition.

    Returns:
        The list of props as ast arg nodes
    """
    spec = getfullargspec(func)
    all_props = []
    kwargs = []
    for target_class in clzs:
        event_triggers = target_class().get_event_triggers()
        # Import from the target class to ensure type hints are resolvable.
        exec(f"from {target_class.__module__} import *", type_hint_globals)
        for name, value in target_class.__annotations__.items():
            if (
                name in spec.kwonlyargs
                or name in EXCLUDED_PROPS
                or name in all_props
                or name in event_triggers
                or (isinstance(value, str) and "ClassVar" in value)
            ):
                continue
            all_props.append(name)

            default = None
            if extract_real_default:
                # TODO: This is not currently working since the default is not type compatible
                #       with the annotation in some cases.
                with contextlib.suppress(AttributeError, KeyError):
                    # Try to get default from pydantic field definition.
                    default = target_class.__fields__[name].default
                    if isinstance(default, Var):
                        default = default._decode()

            kwargs.append(
                (
                    ast.arg(
                        arg=name,
                        annotation=ast.Name(
                            id=_get_type_hint(value, type_hint_globals)
                        ),
                    ),
                    ast.Constant(value=default),
                )
            )
    return kwargs


def type_to_ast(typ: Any, cls: type) -> ast.AST:
    """Converts any type annotation into its AST representation.
    Handles nested generic types, unions, etc.

    Args:
        typ: The type annotation to convert.
        cls: The class where the type annotation is used.

    Returns:
        The AST representation of the type annotation.
    """
    if typ is type(None):
        return ast.Name(id="None")

    origin = get_origin(typ)

    # Handle plain types (int, str, custom classes, etc.)
    if origin is None:
        if hasattr(typ, "__name__"):
            if typ.__module__.startswith("reflex."):
                typ_parts = typ.__module__.split(".")
                cls_parts = cls.__module__.split(".")

                zipped = list(zip(typ_parts, cls_parts, strict=False))

                if all(a == b for a, b in zipped) and len(typ_parts) == len(cls_parts):
                    return ast.Name(id=typ.__name__)

                return ast.Name(id=typ.__module__ + "." + typ.__name__)
            return ast.Name(id=typ.__name__)
        elif hasattr(typ, "_name"):
            return ast.Name(id=typ._name)
        return ast.Name(id=str(typ))

    # Get the base type name (List, Dict, Optional, etc.)
    base_name = origin._name if hasattr(origin, "_name") else origin.__name__

    # Get type arguments
    args = get_args(typ)

    # Handle empty type arguments
    if not args:
        return ast.Name(id=base_name)

    # Convert all type arguments recursively
    arg_nodes = [type_to_ast(arg, cls) for arg in args]

    # Special case for single-argument types (like List[T] or Optional[T])
    if len(arg_nodes) == 1:
        slice_value = arg_nodes[0]
    else:
        slice_value = ast.Tuple(elts=arg_nodes, ctx=ast.Load())  # pyright: ignore [reportArgumentType]

    return ast.Subscript(
        value=ast.Name(id=base_name),
        slice=ast.Index(value=slice_value),  # pyright: ignore [reportArgumentType]
        ctx=ast.Load(),
    )


def _get_parent_imports(func: Callable):
    _imports = {"reflex.vars": ["Var"]}
    for type_hint in inspect.get_annotations(func).values():
        try:
            match = re.match(r"\w+\[([\w\d]+)\]", type_hint)
        except TypeError:
            continue
        if match:
            type_hint = match.group(1)
            if type_hint in importlib.import_module(func.__module__).__dir__():
                _imports.setdefault(func.__module__, []).append(type_hint)
    return _imports


def _generate_component_create_functiondef(
    node: ast.FunctionDef | None,
    clz: type[Component] | type[SimpleNamespace],
    type_hint_globals: dict[str, Any],
) -> ast.FunctionDef:
    """Generate the create function definition for a Component.

    Args:
        node: The existing create functiondef node from the ast
        clz: The Component class to generate the create functiondef for.
        type_hint_globals: The globals to use to resolving a type hint str.

    Returns:
        The create functiondef node for the ast.

    Raises:
        TypeError: If clz is not a subclass of Component.
    """
    if not issubclass(clz, Component):
        raise TypeError(f"clz must be a subclass of Component, not {clz!r}")

    # add the imports needed by get_type_hint later
    type_hint_globals.update(
        {name: getattr(typing, name) for name in DEFAULT_TYPING_IMPORTS}
    )

    if clz.__module__ != clz.create.__module__:
        _imports = _get_parent_imports(clz.create)
        for name, values in _imports.items():
            exec(f"from {name} import {','.join(values)}", type_hint_globals)

    kwargs = _extract_func_kwargs_as_ast_nodes(clz.create, type_hint_globals)

    # kwargs associated with props defined in the class and its parents
    all_classes = [c for c in clz.__mro__ if issubclass(c, Component)]
    prop_kwargs = _extract_class_props_as_ast_nodes(
        clz.create, all_classes, type_hint_globals
    )
    all_props = [arg[0].arg for arg in prop_kwargs]
    kwargs.extend(prop_kwargs)

    def figure_out_return_type(annotation: Any):
        if inspect.isclass(annotation) and issubclass(annotation, inspect._empty):
            return ast.Name(id="EventType[Any]")

        if not isinstance(annotation, str) and get_origin(annotation) is tuple:
            arguments = get_args(annotation)

            arguments_without_var = [
                get_args(argument)[0] if get_origin(argument) == Var else argument
                for argument in arguments
            ]

            # Convert each argument type to its AST representation
            type_args = [type_to_ast(arg, cls=clz) for arg in arguments_without_var]

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
            return ast.Name(
                id=f"Union[{', '.join(map(ast.unparse, all_count_args_type))}]"
            )

        if isinstance(annotation, str) and annotation.startswith("Tuple["):
            inside_of_tuple = annotation.removeprefix("Tuple[").removesuffix("]")

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

            return ast.Name(
                id=f"Union[{', '.join(map(ast.unparse, all_count_args_type))}]"
            )
        return ast.Name(id="EventType[Any]")

    event_triggers = clz().get_event_triggers()

    # event handler kwargs
    kwargs.extend(
        (
            ast.arg(
                arg=trigger,
                annotation=ast.Subscript(
                    ast.Name("Optional"),
                    ast.Index(  # pyright: ignore [reportArgumentType]
                        value=ast.Name(
                            id=ast.unparse(
                                figure_out_return_type(
                                    inspect.signature(event_specs).return_annotation
                                )
                                if not isinstance(
                                    event_specs := event_triggers[trigger], Sequence
                                )
                                else ast.Subscript(
                                    ast.Name("Union"),
                                    ast.Tuple(
                                        [
                                            figure_out_return_type(
                                                inspect.signature(
                                                    event_spec
                                                ).return_annotation
                                            )
                                            for event_spec in event_specs
                                        ]
                                    ),
                                )
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

    definition = ast.FunctionDef(  # pyright: ignore [reportCallIssue]
        name="create",
        args=create_args,
        body=[  # pyright: ignore [reportArgumentType]
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
        decorator_list=[
            ast.Name(id="overload"),
            *(
                node.decorator_list
                if node is not None
                else [ast.Name(id="classmethod")]
            ),
        ],
        lineno=node.lineno if node is not None else None,  # pyright: ignore [reportArgumentType]
        returns=ast.Constant(value=clz.__name__),
    )
    return definition


def _generate_staticmethod_call_functiondef(
    node: ast.FunctionDef | None,
    clz: type[Component] | type[SimpleNamespace],
    type_hint_globals: dict[str, Any],
) -> ast.FunctionDef | None:
    ...

    fullspec = getfullargspec(clz.__call__)

    call_args = ast.arguments(
        args=[
            ast.arg(
                name,
                annotation=ast.Name(
                    id=_get_type_hint(
                        anno := fullspec.annotations[name],
                        type_hint_globals,
                        is_optional=rx_types.is_optional(anno),
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
    definition = ast.FunctionDef(  # pyright: ignore [reportCallIssue]
        name="__call__",
        args=call_args,
        body=[
            ast.Expr(value=ast.Constant(value=clz.__call__.__doc__)),
            ast.Expr(
                value=ast.Constant(...),
            ),
        ],
        decorator_list=[ast.Name(id="staticmethod")],
        lineno=node.lineno if node is not None else None,  # pyright: ignore [reportArgumentType]
        returns=ast.Constant(
            value=_get_type_hint(
                typing.get_type_hints(clz.__call__).get("return", None),
                type_hint_globals,
                is_optional=False,
            )
        ),
    )
    return definition


def _generate_namespace_call_functiondef(
    node: ast.ClassDef | None,
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
    type_hint_globals.update(
        {name: getattr(typing, name) for name in DEFAULT_TYPING_IMPORTS}
    )

    clz = classes[clz_name]

    if not hasattr(clz.__call__, "__self__"):
        return _generate_staticmethod_call_functiondef(node, clz, type_hint_globals)  # pyright: ignore [reportArgumentType]

    # Determine which class is wrapped by the namespace __call__ method
    component_clz = clz.__call__.__self__

    if clz.__call__.__func__.__name__ != "create":  # pyright: ignore [reportFunctionMemberAccess]
        return None

    definition = _generate_component_create_functiondef(
        node=None,
        clz=component_clz,  # pyright: ignore [reportArgumentType]
        type_hint_globals=type_hint_globals,
    )
    definition.name = "__call__"

    # Turn the definition into a staticmethod
    del definition.args.args[0]  # remove `cls` arg
    definition.decorator_list = [ast.Name(id="staticmethod")]

    return definition


class StubGenerator(ast.NodeTransformer):
    """A node transformer that will generate the stubs for a given module."""

    def __init__(
        self, module: ModuleType, classes: dict[str, Type[Component | SimpleNamespace]]
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
        # Collected import statements from the module.
        self.import_statements: list[str] = []
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

    def _current_class_is_component(self) -> bool:
        """Check if the current class is a Component.

        Returns:
            Whether the current class is a Component.
        """
        return (
            self.current_class is not None
            and self.current_class in self.classes
            and issubclass(self.classes[self.current_class], Component)
        )

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
        self.import_statements.append(ast.unparse(node))
        if not self.inserted_imports:
            self.inserted_imports = True
            default_imports = _generate_imports(self.typing_imports)
            self.import_statements.extend(ast.unparse(i) for i in default_imports)
            return [*default_imports, node]
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
            return None  # ignore __future__ imports
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
        exec("\n".join(self.import_statements), self.type_hint_globals)
        self.current_class = node.name
        self._remove_docstring(node)

        # Define `__call__` as a real function so the docstring appears in the stub.
        call_definition = None
        for child in node.body[:]:
            found_call = False
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
            and self._current_class_is_component()
        ):
            # Add a new .create FunctionDef since one does not exist.
            node.body.append(
                _generate_component_create_functiondef(
                    node=None,
                    clz=self.classes[self.current_class],
                    type_hint_globals=self.type_hint_globals,
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
        if node.name == "create" and self.current_class in self.classes:
            node = _generate_component_create_functiondef(
                node, self.classes[self.current_class], self.type_hint_globals
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
                        return

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
        if self.current_class in self.classes:
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


class PyiGenerator:
    """A .pyi file generator that will scan all defined Component in Reflex and
    generate the appropriate stub.
    """

    modules: list = []
    root: str = ""
    current_module: Any = {}
    written_files: list[str] = []

    def _write_pyi_file(self, module_path: Path, source: str):
        relpath = str(_relative_to_pwd(module_path)).replace("\\", "/")
        pyi_content = (
            "\n".join(
                [
                    f'"""Stub file for {relpath}"""',
                    "# ------------------- DO NOT EDIT ----------------------",
                    "# This file was generated by `reflex/utils/pyi_generator.py`!",
                    "# ------------------------------------------------------",
                    "",
                ]
            )
            + source
        )

        pyi_path = module_path.with_suffix(".pyi")
        pyi_path.write_text(pyi_content)
        logger.info(f"Wrote {relpath}")

    def _get_init_lazy_imports(self, mod: tuple | ModuleType, new_tree: ast.AST):
        # retrieve the _SUBMODULES and _SUBMOD_ATTRS from an init file if present.
        sub_mods = getattr(mod, "_SUBMODULES", None)
        sub_mod_attrs = getattr(mod, "_SUBMOD_ATTRS", None)
        pyright_ignore_imports = getattr(mod, "_PYRIGHT_IGNORE_IMPORTS", [])

        if not sub_mods and not sub_mod_attrs:
            return
        sub_mods_imports = []
        sub_mod_attrs_imports = []

        if sub_mods:
            sub_mods_imports = [
                f"from . import {mod} as {mod}" for mod in sorted(sub_mods)
            ]
            sub_mods_imports.append("")

        if sub_mod_attrs:
            sub_mod_attrs = {
                attr: mod for mod, attrs in sub_mod_attrs.items() for attr in attrs
            }
            # construct the import statement and handle special cases for aliases
            sub_mod_attrs_imports = [
                f"from .{path} import {mod if not isinstance(mod, tuple) else mod[0]} as {mod if not isinstance(mod, tuple) else mod[1]}"
                + (
                    "  # type: ignore"
                    if mod in pyright_ignore_imports
                    else "  # noqa: F401"  # ignore ruff formatting here for cases like rx.list.
                    if isinstance(mod, tuple)
                    else ""
                )
                for mod, path in sub_mod_attrs.items()
            ]
            sub_mod_attrs_imports.append("")

        text = "\n" + "\n".join([*sub_mods_imports, *sub_mod_attrs_imports])
        text += ast.unparse(new_tree) + "\n"
        return text

    def _scan_file(self, module_path: Path) -> str | None:
        module_import = (
            _relative_to_pwd(module_path)
            .with_suffix("")
            .as_posix()
            .replace("/", ".")
            .replace("\\", ".")
        )
        module = importlib.import_module(module_import)
        logger.debug(f"Read {module_path}")
        class_names = {
            name: obj
            for name, obj in vars(module).items()
            if inspect.isclass(obj)
            and (issubclass(obj, Component) or issubclass(obj, SimpleNamespace))
            and obj != Component
            and inspect.getmodule(obj) == module
        }
        is_init_file = _relative_to_pwd(module_path).name == "__init__.py"
        if not class_names and not is_init_file:
            return

        if is_init_file:
            new_tree = InitStubGenerator(module, class_names).visit(
                ast.parse(inspect.getsource(module))
            )
            init_imports = self._get_init_lazy_imports(module, new_tree)
            if not init_imports:
                return
            self._write_pyi_file(module_path, init_imports)
        else:
            new_tree = StubGenerator(module, class_names).visit(
                ast.parse(inspect.getsource(module))
            )
            self._write_pyi_file(module_path, ast.unparse(new_tree))
        return str(module_path.with_suffix(".pyi").resolve())

    def _scan_files_multiprocess(self, files: list[Path]):
        with Pool(processes=cpu_count()) as pool:
            self.written_files.extend(f for f in pool.map(self._scan_file, files) if f)

    def _scan_files(self, files: list[Path]):
        for file in files:
            pyi_path = self._scan_file(file)
            if pyi_path:
                self.written_files.append(pyi_path)

    def scan_all(self, targets: list, changed_files: list[Path] | None = None):
        """Scan all targets for class inheriting Component and generate the .pyi files.

        Args:
            targets: the list of file/folders to scan.
            changed_files (optional): the list of changed files since the last run.
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

        if cpu_count() == 1 or len(file_targets) < 5:
            self._scan_files(file_targets)
        else:
            self._scan_files_multiprocess(file_targets)

        # Fix generated pyi files with ruff.
        subprocess.run(["ruff", "format", *self.written_files])
        subprocess.run(["ruff", "check", "--fix", *self.written_files])

        # For some reason, we need to format the __init__.pyi files again after fixing...
        init_files = [f for f in self.written_files if "/__init__.pyi" in f]
        subprocess.run(["ruff", "format", *init_files])

        # Post-process the generated pyi files to add hacky type: ignore comments
        for file_path in self.written_files:
            with FileInput(file_path, inplace=True) as f:
                for line in f:
                    # Hack due to ast not supporting comments in the tree.
                    if (
                        "def create(" in line
                        or "Var[Figure]" in line
                        or "Var[Template]" in line
                    ):
                        line = line.rstrip() + "  # type: ignore\n"
                    print(line, end="")  # noqa: T201
