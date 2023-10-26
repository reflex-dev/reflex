"""The pyi generator module."""

import ast
import importlib
import inspect
import os
import re
import sys
import textwrap
from _ast import ClassDef, FunctionDef, Import, ImportFrom
from inspect import getfullargspec
from pathlib import Path
from types import ModuleType
from typing import Any, Iterable, Type, get_args

import black

from reflex.components.component import Component
from reflex.utils import types as rx_types

EXCLUDED_FILES = [
    "__init__.py",
    "component.py",
    "bare.py",
    "foreach.py",
    "cond.py",
    "multiselect.py",
]

# These props exist on the base component, but should not be exposed in create methods.
EXCLUDED_PROPS = [
    "alias",
    "children",
    "event_triggers",
    "invalid_children",
    "library",
    "lib_dependencies",
    "tag",
    "is_default",
    "special_props",
    "valid_children",
]

DEFAULT_TYPING_IMPORTS = {
    "overload",
    "Any",
    "Dict",
    "List",
    "Literal",
    "Optional",
    "Union",
}

STUBS_FOLDER = "stubs"


def _get_type_hint(value, type_hint_globals, is_optional=True) -> str:
    """Resolve the type hint for value.

    Args:
        value: The type annotation as a str or actual types/aliases.
        type_hint_globals: The globals to use to resolving a type hint str.
        is_optional: Whether the type hint should be wrapped in Optional.

    Returns:
        The resolved type hint as a str.
    """
    res = ""
    args = get_args(value)
    if args:
        inner_container_type_args = (
            [repr(arg) for arg in args]
            if rx_types.is_literal(value)
            else [
                _get_type_hint(arg, type_hint_globals, is_optional=False)
                for arg in args
                if arg is not type(None)
            ]
        )
        res = f"{value.__name__}[{', '.join(inner_container_type_args)}]"

        if value.__name__ == "Var":
            # For Var types, Union with the inner args so they can be passed directly.
            types = [res] + [
                _get_type_hint(arg, type_hint_globals, is_optional=False)
                for arg in args
                if arg is not type(None)
            ]
            if len(types) > 1:
                res = ", ".join(types)
                res = f"Union[{res}]"
    elif isinstance(value, str):
        ev = eval(value, type_hint_globals)
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


def _generate_imports(typing_imports: Iterable[str]) -> list[ast.ImportFrom]:
    """Generate the import statements for the stub file.

    Args:
        typing_imports: The typing imports to include.

    Returns:
    The list of import statements.
    """
    return [
        ast.ImportFrom(
            module="typing", names=[ast.alias(name=imp) for imp in typing_imports]
        ),
        *ast.parse(
            textwrap.dedent(
                """
                from reflex.vars import Var, BaseVar, ComputedVar
                from reflex.event import EventChain, EventHandler, EventSpec
                from reflex.style import Style"""
            )
        ).body,
    ]


class StubGenerator(ast.NodeTransformer):
    def __init__(self, module: ModuleType, classes: dict[str, Type], *args, **kwargs):
        self.classes = classes
        self.current_class = None
        self.inserted_imports = False
        self.typing_imports = DEFAULT_TYPING_IMPORTS  # | _get_typing_import(module)
        self.import_statements = []
        self.type_hint_globals = module.__dict__.copy()
        super().__init__(*args, **kwargs)

    def visit_Import(self, node: Import) -> Any:
        self.import_statements.append(ast.unparse(node))
        if not self.inserted_imports:
            self.inserted_imports = True
            return _generate_imports(self.typing_imports) + [node]
        return node

    def visit_ImportFrom(self, node: ImportFrom) -> Any:
        if node.module == "__future__":
            return None  # ignore __future__ imports
        return self.visit_Import(node)

    def visit_ClassDef(self, node: ClassDef) -> Any:
        exec("\n".join(self.import_statements), self.type_hint_globals)
        self.current_class = node.name
        for child in node.body[:]:
            # Remove all assignments in the class body
            if isinstance(child, (ast.AnnAssign, ast.Assign)):
                node.body.remove(child)
        self.generic_visit(node)
        if (
            not any(
                isinstance(child, ast.FunctionDef) and child.name == "create"
                for child in node.body
            )
            and self.current_class in self.classes
        ):
            node.body.append(
                self._generate_pyi_class(
                    None, self.classes[self.current_class], self.type_hint_globals
                )
            )
        return node

    def visit_FunctionDef(self, node: FunctionDef) -> Any:
        if node.name == "create":
            node = self._generate_pyi_class(
                node, self.classes[self.current_class], self.type_hint_globals
            )
        else:
            if node.name.startswith("_"):
                return None  # remove private methods
            # blank out the function body
            if isinstance(node.body[0], ast.Expr) and isinstance(
                node.body[0].value, ast.Constant
            ):
                node.body = node.body[:1]  # only keep the docstring
            else:
                node.body = [ast.Ellipsis()]
        self.generic_visit(node)
        return node

    def _generate_pyi_class(
        self,
        node: ast.FunctionDef,
        _class: type[Component],
        type_hint_globals: dict[str, Any],
    ):
        create_spec = getfullargspec(_class.create)

        kwargs = []

        # kwargs already defined on the create function
        for kwarg in create_spec.kwonlyargs:
            arg = ast.arg(arg=kwarg)
            if kwarg in create_spec.annotations:
                arg.annotation = ast.Name(
                    id=_get_type_hint(create_spec.annotations[kwarg], type_hint_globals)
                )
            default = None
            if kwarg in create_spec.kwonlydefaults:
                default = ast.Constant(value=create_spec.kwonlydefaults[kwarg])
            kwargs.append((arg, default))

        # kwargs associated with props defined in the class and its parents
        all_classes = [c for c in _class.__mro__ if issubclass(c, Component)]
        all_props = []
        for target_class in all_classes:
            exec(f"from {target_class.__module__} import *", type_hint_globals)
            for name, value in target_class.__annotations__.items():
                if (
                    name in create_spec.kwonlyargs
                    or name in EXCLUDED_PROPS
                    or name in all_props
                ):
                    continue
                all_props.append(name)

                if isinstance(value, str):
                    print(
                        f"Class {_class.__qualname__} is using future annotations: {value}."
                    )
                else:
                    print(
                        f"Class {_class.__qualname__} is NOT using future annotations: {value}."
                    )

                kwargs.append(
                    (
                        ast.arg(
                            arg=name,
                            annotation=ast.Name(
                                id=_get_type_hint(value, type_hint_globals)
                            ),
                        ),
                        ast.Constant(value=None),
                    )
                )

        # event handler kwargs
        kwargs.extend(
            [
                (
                    ast.arg(
                        arg=trigger,
                        annotation=ast.Name(
                            id="Optional[Union[EventHandler, EventSpec, List, function, BaseVar]]"
                        ),
                    ),
                    ast.Constant(value=None),
                )
                for trigger in sorted(_class().get_event_triggers().keys())
            ]
        )
        create_args = ast.arguments(
            args=[ast.arg(arg="cls")],
            posonlyargs=[],
            vararg=ast.arg(arg="children"),
            kwonlyargs=[arg[0] for arg in kwargs],
            kw_defaults=[arg[1] for arg in kwargs],
            kwarg=ast.arg(arg="props"),
            defaults=[],
        )
        definition = ast.FunctionDef(
            name="create",
            args=create_args,
            body=[
                ast.Expr(
                    value=ast.Constant(
                        value=self._generate_docstrings(all_classes, all_props)
                    )
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
            lineno=node.lineno if node is not None else None,
            returns=ast.Constant(value=_class.__name__),
        )
        return definition

    def _generate_docstrings(self, _classes, _props):
        props_comments = {}
        comments = []
        for _class in _classes:
            for _i, line in enumerate(inspect.getsource(_class).splitlines()):
                reached_functions = re.search("def ", line)
                if reached_functions:
                    # We've reached the functions, so stop.
                    break

                # Get comments for prop
                if line.strip().startswith("#"):
                    comments.append(line)
                    continue

                # Check if this line has a prop.
                match = re.search("\\w+:", line)
                if match is None:
                    # This line doesn't have a var, so continue.
                    continue

                # Get the prop.
                prop = match.group(0).strip(":")
                if prop in _props:
                    if not comments:  # do not include undocumented props
                        continue
                    props_comments[prop] = "\n".join(
                        [comment.strip().strip("#") for comment in comments]
                    )
                    comments.clear()
                    continue
                if prop in EXCLUDED_PROPS:
                    comments.clear()  # throw away comments for excluded props
        _class = _classes[0]
        new_docstring = []
        for _i, line in enumerate(_class.create.__doc__.splitlines()):
            new_docstring.append(line)
            if "*children" in line:
                for nline in [
                    f"{line.split('*')[0]}{n}:{c}" for n, c in props_comments.items()
                ]:
                    new_docstring.append(nline)
        return "\n".join(new_docstring)


class PyiGenerator:
    """A .pyi file generator that will scan all defined Component in Reflex and
    generate the approriate stub.
    """

    modules: list = []
    root: str = ""
    current_module: Any = {}
    default_typing_imports: set = DEFAULT_TYPING_IMPORTS

    def _write_pyi_file(self, module_path: Path, source: str):
        pyi_content = [
            f'"""Stub file for {module_path}"""',
            "# ------------------- DO NOT EDIT ----------------------",
            "# This file was generated by `scripts/pyi_generator.py`!",
            "# ------------------------------------------------------",
            "",
        ]

        for formatted_line in black.format_file_contents(
            src_contents=source,
            fast=True,
            mode=black.mode.Mode(is_pyi=True),
        ).splitlines():
            if formatted_line == "    def create(":
                pyi_content.append("    def create(  # type: ignore")
            else:
                pyi_content.append(formatted_line)

        pyi_path = module_path.with_suffix(".pyi")
        pyi_path.write_text("\n".join(pyi_content))

    def _scan_file(self, module_path: Path):
        module_import = str(module_path.with_suffix("")).replace("/", ".")
        module = importlib.import_module(module_import)

        class_names = {
            name: obj
            for name, obj in vars(module).items()
            if inspect.isclass(obj)
            and issubclass(obj, Component)
            and obj != Component
            and inspect.getmodule(obj) == module
        }
        if not class_names:
            return

        new_tree = StubGenerator(module, class_names).visit(
            ast.parse(inspect.getsource(module))
        )
        self._write_pyi_file(module_path, ast.unparse(new_tree))

    def _scan_folder(self, folder):
        for root, _, files in os.walk(folder):
            for file in files:
                if file in EXCLUDED_FILES:
                    continue
                if file.endswith(".py"):
                    self._scan_file(Path(root) / file)

    def scan_all(self, targets):
        """Scan all targets for class inheriting Component and generate the .pyi files.

        Args:
            targets: the list of file/folders to scan.
        """
        for target in targets:
            if target.endswith(".py"):
                self._scan_file(Path(target))
            else:
                self._scan_folder(target)


if __name__ == "__main__":
    targets = sys.argv[1:] if len(sys.argv) > 1 else ["reflex/components"]
    print(f"Running .pyi generator for {targets}")
    gen = PyiGenerator()
    gen.scan_all(targets)
