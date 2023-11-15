"""The pyi generator module."""

import ast
import contextlib
import importlib
import inspect
import logging
import os
import re
import sys
import textwrap
from inspect import getfullargspec
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Iterable, Type, get_args

import black
import black.mode

from nextpy.components.component import Component
from nextpy.utils import types as xt_types
from nextpy.core.vars import Var

logger = logging.getLogger("pyi_generator")

EXCLUDED_FILES = [
    "__init__.py",
    "component.py",
    "bare.py",
    "foreach.py",
    "cond.py",
    "multiselect.py",
    "literals.py",
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
            if xt_types.is_literal(value)
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
        *ast.parse(  # type: ignore
            textwrap.dedent(
                """
                from nextpy.core.vars import Var, BaseVar, ComputedVar
                from nextpy.core.event import EventChain, EventHandler, EventSpec
                from nextpy.core.style import Style"""
            )
        ).body,
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
            for nline in [
                f"{indent}{n}:{' '.join(c)}" for n, c in props_comments.items()
            ]:
                new_docstring.append(nline)
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
        # Import from the target class to ensure type hints are resolvable.
        exec(f"from {target_class.__module__} import *", type_hint_globals)
        for name, value in target_class.__annotations__.items():
            if name in spec.kwonlyargs or name in EXCLUDED_PROPS or name in all_props:
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
                        default = default._decode()  # type: ignore

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


def _generate_component_create_functiondef(
    node: ast.FunctionDef | None,
    clz: type[Component],
    type_hint_globals: dict[str, Any],
) -> ast.FunctionDef:
    """Generate the create function definition for a Component.

    Args:
        node: The existing create functiondef node from the ast
        clz: The Component class to generate the create functiondef for.
        type_hint_globals: The globals to use to resolving a type hint str.

    Returns:
        The create functiondef node for the ast.
    """
    # kwargs defined on the actual create function
    kwargs = _extract_func_kwargs_as_ast_nodes(clz.create, type_hint_globals)

    # kwargs associated with props defined in the class and its parents
    all_classes = [c for c in clz.__mro__ if issubclass(c, Component)]
    prop_kwargs = _extract_class_props_as_ast_nodes(
        clz.create, all_classes, type_hint_globals
    )
    all_props = [arg[0].arg for arg in prop_kwargs]
    kwargs.extend(prop_kwargs)

    # event handler kwargs
    kwargs.extend(
        (
            ast.arg(
                arg=trigger,
                annotation=ast.Name(
                    id="Optional[Union[EventHandler, EventSpec, List, function, BaseVar]]"
                ),
            ),
            ast.Constant(value=None),
        )
        for trigger in sorted(clz().get_event_triggers().keys())
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
    definition = ast.FunctionDef(
        name="create",
        args=create_args,
        body=[
            ast.Expr(
                value=ast.Constant(value=_generate_docstrings(all_classes, all_props))
            ),
            ast.Expr(
                value=ast.Ellipsis(),
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
        returns=ast.Constant(value=clz.__name__),
    )
    return definition


class StubGenerator(ast.NodeTransformer):
    """A node transformer that will generate the stubs for a given module."""

    def __init__(self, module: ModuleType, classes: dict[str, Type[Component]]):
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
        self.typing_imports = DEFAULT_TYPING_IMPORTS
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

    def visit_Module(self, node: ast.Module) -> ast.Module:
        """Visit a Module node and remove docstring from body.

        Args:
            node: The Module node to visit.

        Returns:
            The modified Module node.
        """
        self.generic_visit(node)
        return self._remove_docstring(node)  # type: ignore

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
            return _generate_imports(self.typing_imports) + [node]
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
        self.generic_visit(node)  # Visit child nodes.
        if not node.body:
            # We should never return an empty body.
            node.body.append(ast.Expr(value=ast.Ellipsis()))
        if (
            not any(
                isinstance(child, ast.FunctionDef) and child.name == "create"
                for child in node.body
            )
            and self.current_class in self.classes
        ):
            # Add a new .create FunctionDef since one does not exist.
            node.body.append(
                _generate_component_create_functiondef(
                    node=None,
                    clz=self.classes[self.current_class],
                    type_hint_globals=self.type_hint_globals,
                )
            )
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
            if node.name.startswith("_"):
                return None  # remove private methods

            # Blank out the function body for public functions.
            node.body = [ast.Expr(value=ast.Ellipsis())]
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
        return None

    def visit_AnnAssign(self, node: ast.AnnAssign) -> ast.AnnAssign | None:
        """Visit an AnnAssign node (Annotated assignment).

        Remove private target and remove the assignment value in the stub.

        Args:
            node: The AnnAssign node to visit.

        Returns:
            The modified AnnAssign node (or None).
        """
        if isinstance(node.target, ast.Name) and node.target.id.startswith("_"):
            return None
        if self.current_class in self.classes:
            # Remove annotated assignments in Component classes (props)
            return None
        # Blank out assignments in type stubs.
        node.value = None
        return node


class PyiGenerator:
    """A .pyi file generator that will scan all defined Component in nextpy and
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
            # Bit of a hack here, since the AST cannot represent comments.
            if formatted_line == "    def create(":
                pyi_content.append("    def create(  # type: ignore")
            else:
                pyi_content.append(formatted_line)

        pyi_path = module_path.with_suffix(".pyi")
        pyi_path.write_text("\n".join(pyi_content))
        logger.info(f"Wrote {pyi_path}")

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
    logging.basicConfig(level=logging.DEBUG)
    logging.getLogger("blib2to3.pgen2.driver").setLevel(logging.INFO)

    targets = sys.argv[1:] if len(sys.argv) > 1 else ["nextpy/components"]
    logger.info(f"Running .pyi generator for {targets}")
    gen = PyiGenerator()
    gen.scan_all(targets)