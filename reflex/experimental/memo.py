"""Experimental memo support for vars and components."""

from __future__ import annotations

import dataclasses
import inspect
from collections.abc import Callable
from functools import wraps
from typing import Any, get_args, get_origin, get_type_hints

from reflex import constants
from reflex.components.base.bare import Bare
from reflex.components.base.fragment import Fragment
from reflex.components.component import Component
from reflex.components.dynamic import bundled_libraries
from reflex.constants.compiler import SpecialAttributes
from reflex.constants.state import CAMEL_CASE_MEMO_MARKER
from reflex.utils import format
from reflex.utils import types as type_utils
from reflex.utils.imports import ImportVar
from reflex.vars import VarData
from reflex.vars.base import LiteralVar, Var
from reflex.vars.function import (
    ArgsFunctionOperation,
    DestructuredArg,
    FunctionStringVar,
    FunctionVar,
    ReflexCallable,
)
from reflex.vars.object import RestProp


@dataclasses.dataclass(frozen=True, slots=True)
class MemoParam:
    """Metadata about a memo parameter."""

    name: str
    annotation: Any
    kind: inspect._ParameterKind
    default: Any = inspect.Parameter.empty
    js_prop_name: str | None = None
    placeholder_name: str = ""
    is_children: bool = False
    is_rest: bool = False


@dataclasses.dataclass(frozen=True, slots=True)
class ExperimentalMemoDefinition:
    """Base metadata for an experimental memo."""

    fn: Callable[..., Any]
    python_name: str
    params: tuple[MemoParam, ...]


@dataclasses.dataclass(frozen=True, slots=True)
class ExperimentalMemoFunctionDefinition(ExperimentalMemoDefinition):
    """A memo that compiles to a JavaScript function."""

    function: ArgsFunctionOperation
    imported_var: FunctionVar


@dataclasses.dataclass(frozen=True, slots=True)
class ExperimentalMemoComponentDefinition(ExperimentalMemoDefinition):
    """A memo that compiles to a React component."""

    export_name: str
    component: Component


class ExperimentalMemoComponent(Component):
    """A rendered instance of an experimental memo component."""

    library = f"$/{constants.Dirs.COMPONENTS_PATH}"

    def _post_init(self, **kwargs):
        """Initialize the experimental memo component.

        Args:
            **kwargs: The kwargs to pass to the component.
        """
        definition = kwargs.pop("memo_definition")

        explicit_props = {
            param.name
            for param in definition.params
            if not param.is_children and not param.is_rest
        }
        component_fields = self.get_fields()

        declared_props = {
            key: kwargs.pop(key) for key in list(kwargs) if key in explicit_props
        }

        rest_props = {}
        if _get_rest_param(definition.params) is not None:
            rest_props = {
                key: kwargs.pop(key)
                for key in list(kwargs)
                if key not in component_fields and not SpecialAttributes.is_special(key)
            }

        super()._post_init(**kwargs)

        self.tag = definition.export_name

        props: dict[str, Any] = {}
        for key, value in {**declared_props, **rest_props}.items():
            camel_cased_key = format.to_camel_case(key)
            literal_value = LiteralVar.create(value)
            props[camel_cased_key] = literal_value
            setattr(self, camel_cased_key, literal_value)

        prop_names = dict.fromkeys(props)
        object.__setattr__(self, "get_props", lambda: prop_names)


EXPERIMENTAL_MEMOS: dict[str, ExperimentalMemoDefinition] = {}


def _annotation_inner_type(annotation: Any) -> Any:
    """Unwrap a Var-like annotation to its inner type.

    Args:
        annotation: The annotation to unwrap.

    Returns:
        The inner type for the annotation.
    """
    if _is_rest_annotation(annotation):
        return dict[str, Any]

    origin = get_origin(annotation) or annotation
    if type_utils.safe_issubclass(origin, Var) and (args := get_args(annotation)):
        return args[0]
    return Any


def _is_rest_annotation(annotation: Any) -> bool:
    """Check whether an annotation is a RestProp.

    Args:
        annotation: The annotation to check.

    Returns:
        Whether the annotation is a RestProp.
    """
    origin = get_origin(annotation) or annotation
    return isinstance(origin, type) and issubclass(origin, RestProp)


def _is_var_annotation(annotation: Any) -> bool:
    """Check whether an annotation is a Var-like annotation.

    Args:
        annotation: The annotation to check.

    Returns:
        Whether the annotation is Var-like.
    """
    origin = get_origin(annotation) or annotation
    return isinstance(origin, type) and issubclass(origin, Var)


def _is_component_annotation(annotation: Any) -> bool:
    """Check whether an annotation is component-like.

    Args:
        annotation: The annotation to check.

    Returns:
        Whether the annotation resolves to Component.
    """
    origin = get_origin(annotation) or annotation
    return isinstance(origin, type) and issubclass(origin, Component)


def _children_annotation_is_valid(annotation: Any) -> bool:
    """Check whether an annotation is valid for children.

    Args:
        annotation: The annotation to check.

    Returns:
        Whether the annotation is valid for children.
    """
    return _is_var_annotation(annotation) and type_utils.typehint_issubclass(
        _annotation_inner_type(annotation), Component
    )


def _get_children_param(params: tuple[MemoParam, ...]) -> MemoParam | None:
    return next((param for param in params if param.is_children), None)


def _get_rest_param(params: tuple[MemoParam, ...]) -> MemoParam | None:
    return next((param for param in params if param.is_rest), None)


def _imported_function_var(name: str, return_type: Any) -> FunctionVar:
    """Create the imported FunctionVar for an experimental memo.

    Args:
        name: The exported function name.
        return_type: The return type of the function.

    Returns:
        The imported FunctionVar.
    """
    return FunctionStringVar.create(
        name,
        _var_type=ReflexCallable[Any, return_type],
        _var_data=VarData(
            imports={f"$/{constants.Dirs.COMPONENTS_PATH}": [ImportVar(tag=name)]}
        ),
    )


def _component_import_var(name: str) -> Var:
    """Create the imported component var for an experimental memo component.

    Args:
        name: The exported component name.

    Returns:
        The component var.
    """
    return Var(
        name,
        _var_type=type[Component],
        _var_data=VarData(
            imports={
                f"$/{constants.Dirs.COMPONENTS_PATH}": [ImportVar(tag=name)],
                "@emotion/react": [ImportVar(tag="jsx")],
            }
        ),
    )


def _validate_var_return_expr(return_expr: Var, func_name: str) -> None:
    """Validate that a var-returning memo can compile safely.

    Args:
        return_expr: The return expression.
        func_name: The function name for error messages.

    Raises:
        TypeError: If the return expression depends on unsupported features.
    """
    var_data = VarData.merge(return_expr._get_all_var_data())
    if var_data is None:
        return

    if var_data.hooks:
        msg = (
            f"Var-returning `@rx._x.memo` `{func_name}` cannot depend on hooks. "
            "Use a component-returning `@rx._x.memo` instead."
        )
        raise TypeError(msg)

    if var_data.components:
        msg = (
            f"Var-returning `@rx._x.memo` `{func_name}` cannot depend on embedded "
            "components, custom code, or dynamic imports. Use a component-returning "
            "`@rx._x.memo` instead."
        )
        raise TypeError(msg)

    for lib in dict(var_data.imports):
        if not lib:
            continue
        if lib.startswith((".", "/", "$/", "http")):
            continue
        if format.format_library_name(lib) in bundled_libraries:
            continue
        msg = (
            f"Var-returning `@rx._x.memo` `{func_name}` cannot import `{lib}` because "
            "it is not bundled. Use a component-returning `@rx._x.memo` instead."
        )
        raise TypeError(msg)


def _rest_placeholder(name: str) -> RestProp:
    """Create the placeholder RestProp.

    Args:
        name: The JavaScript identifier.

    Returns:
        The placeholder rest prop.
    """
    return RestProp(_js_expr=name, _var_type=dict[str, Any])


def _var_placeholder(name: str, annotation: Any) -> Var:
    """Create a placeholder Var for a memo parameter.

    Args:
        name: The JavaScript identifier.
        annotation: The parameter annotation.

    Returns:
        The placeholder Var.
    """
    return Var(_js_expr=name, _var_type=_annotation_inner_type(annotation)).guess_type()


def _placeholder_for_param(param: MemoParam) -> Var:
    """Create a placeholder var for a parameter.

    Args:
        param: The parameter metadata.

    Returns:
        The placeholder var.
    """
    if param.is_rest:
        return _rest_placeholder(param.placeholder_name)
    return _var_placeholder(param.placeholder_name, param.annotation)


def _evaluate_memo_function(
    fn: Callable[..., Any],
    params: tuple[MemoParam, ...],
) -> Any:
    """Evaluate a memo function with placeholder vars.

    Args:
        fn: The function to evaluate.
        params: The memo parameters.

    Returns:
        The return value from the function.
    """
    positional_args = []
    keyword_args = {}

    for param in params:
        placeholder = _placeholder_for_param(param)
        if param.kind in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        ):
            positional_args.append(placeholder)
        else:
            keyword_args[param.name] = placeholder

    return fn(*positional_args, **keyword_args)


def _lift_rest_props(component: Component) -> Component:
    """Convert RestProp children into special props.

    Args:
        component: The component tree to rewrite.

    Returns:
        The rewritten component tree.
    """
    special_props = list(component.special_props)
    rewritten_children = []

    for child in component.children:
        if isinstance(child, Bare) and isinstance(child.contents, RestProp):
            special_props.append(child.contents)
            continue

        if isinstance(child, Component):
            child = _lift_rest_props(child)

        rewritten_children.append(child)

    component.children = rewritten_children
    component.special_props = special_props
    return component


def _analyze_params(
    fn: Callable[..., Any],
    *,
    for_component: bool,
) -> tuple[MemoParam, ...]:
    """Analyze and validate memo parameters.

    Args:
        fn: The function to analyze.
        for_component: Whether the memo returns a component.

    Returns:
        The analyzed parameters.

    Raises:
        TypeError: If the function signature is not supported.
    """
    signature = inspect.signature(fn)
    hints = get_type_hints(fn)

    params: list[MemoParam] = []
    rest_count = 0

    for parameter in signature.parameters.values():
        if parameter.kind is inspect.Parameter.VAR_POSITIONAL:
            msg = f"`@rx._x.memo` does not support `*args` in `{fn.__name__}`."
            raise TypeError(msg)
        if parameter.kind is inspect.Parameter.VAR_KEYWORD:
            msg = f"`@rx._x.memo` does not support `**kwargs` in `{fn.__name__}`."
            raise TypeError(msg)
        if parameter.kind is inspect.Parameter.POSITIONAL_ONLY:
            msg = (
                f"`@rx._x.memo` does not support positional-only parameters in "
                f"`{fn.__name__}`."
            )
            raise TypeError(msg)

        annotation = hints.get(parameter.name, parameter.annotation)
        if annotation is inspect.Parameter.empty:
            msg = (
                f"All parameters of `{fn.__name__}` must be annotated as `rx.Var[...]` "
                f"or `rx.RestProp`. Missing annotation for `{parameter.name}`."
            )
            raise TypeError(msg)

        is_rest = _is_rest_annotation(annotation)
        is_children = parameter.name == "children" and _children_annotation_is_valid(
            annotation
        )

        if parameter.name == "children" and not is_children:
            msg = (
                f"`children` in `{fn.__name__}` must be annotated as "
                "`rx.Var[rx.Component]`."
            )
            raise TypeError(msg)

        if not is_rest and not _is_var_annotation(annotation):
            msg = (
                f"All parameters of `{fn.__name__}` must be annotated as `rx.Var[...]` "
                f"or `rx.RestProp`, got `{annotation}` for `{parameter.name}`."
            )
            raise TypeError(msg)

        if is_rest:
            rest_count += 1
            if rest_count > 1:
                msg = (
                    f"`@rx._x.memo` only supports one `rx.RestProp` in `{fn.__name__}`."
                )
                raise TypeError(msg)

        js_prop_name = format.to_camel_case(parameter.name)
        placeholder_name = (
            parameter.name
            if is_children or is_rest or not for_component
            else js_prop_name + CAMEL_CASE_MEMO_MARKER
        )

        params.append(
            MemoParam(
                name=parameter.name,
                annotation=annotation,
                kind=parameter.kind,
                default=parameter.default,
                js_prop_name=js_prop_name,
                placeholder_name=placeholder_name,
                is_children=is_children,
                is_rest=is_rest,
            )
        )

    return tuple(params)


def _create_function_definition(
    fn: Callable[..., Any],
    return_annotation: Any,
) -> ExperimentalMemoFunctionDefinition:
    """Create a definition for a var-returning memo.

    Args:
        fn: The function to analyze.
        return_annotation: The return annotation.

    Returns:
        The function memo definition.
    """
    params = _analyze_params(fn, for_component=False)
    return_expr = Var.create(_evaluate_memo_function(fn, params))
    _validate_var_return_expr(return_expr, fn.__name__)

    children_param = _get_children_param(params)
    rest_param = _get_rest_param(params)
    if children_param is None and rest_param is None:
        function = ArgsFunctionOperation.create(
            args_names=tuple(param.placeholder_name for param in params),
            return_expr=return_expr,
        )
    else:
        function = ArgsFunctionOperation.create(
            args_names=(
                DestructuredArg(
                    fields=tuple(
                        param.placeholder_name for param in params if not param.is_rest
                    ),
                    rest=(
                        rest_param.placeholder_name if rest_param is not None else None
                    ),
                ),
            ),
            return_expr=return_expr,
        )

    return ExperimentalMemoFunctionDefinition(
        fn=fn,
        python_name=fn.__name__,
        params=params,
        function=function,
        imported_var=_imported_function_var(
            fn.__name__, _annotation_inner_type(return_annotation)
        ),
    )


def _create_component_definition(
    fn: Callable[..., Any],
    return_annotation: Any,
) -> ExperimentalMemoComponentDefinition:
    """Create a definition for a component-returning memo.

    Args:
        fn: The function to analyze.
        return_annotation: The return annotation.

    Returns:
        The component memo definition.

    Raises:
        TypeError: If the function does not return a component.
    """
    params = _analyze_params(fn, for_component=True)
    component = _evaluate_memo_function(fn, params)
    if not isinstance(component, Component):
        msg = (
            f"Component-returning `@rx._x.memo` `{fn.__name__}` must return an "
            f"`rx.Component`, got `{type(component).__name__}`."
        )
        raise TypeError(msg)

    return ExperimentalMemoComponentDefinition(
        fn=fn,
        python_name=fn.__name__,
        params=params,
        export_name=format.to_title_case(fn.__name__),
        component=_lift_rest_props(component),
    )


def _bind_function_runtime_args(
    definition: ExperimentalMemoFunctionDefinition,
    *args: Any,
    **kwargs: Any,
) -> tuple[Any, ...]:
    """Bind runtime args for a var-returning memo.

    Args:
        definition: The function memo definition.
        *args: Positional arguments.
        **kwargs: Keyword arguments.

    Returns:
        The ordered arguments for the imported FunctionVar.

    Raises:
        TypeError: If the provided arguments are invalid.
    """
    children_param = _get_children_param(definition.params)
    rest_param = _get_rest_param(definition.params)
    if "children" in kwargs:
        msg = f"`{definition.python_name}` only accepts children positionally."
        raise TypeError(msg)

    if rest_param is not None and rest_param.name in kwargs:
        msg = (
            f"`{definition.python_name}` captures rest props from extra keyword "
            f"arguments. Do not pass `{rest_param.name}=` directly."
        )
        raise TypeError(msg)

    if args and children_param is None:
        msg = f"`{definition.python_name}` only accepts keyword props."
        raise TypeError(msg)

    if any(not _is_component_child(child) for child in args):
        msg = (
            f"`{definition.python_name}` only accepts positional children that are "
            "`rx.Component` or `rx.Var[rx.Component]`."
        )
        raise TypeError(msg)

    explicit_params = [
        param
        for param in definition.params
        if not param.is_rest and not param.is_children
    ]
    explicit_values = {}
    remaining_props = kwargs.copy()
    for param in explicit_params:
        if param.name in remaining_props:
            explicit_values[param.name] = remaining_props.pop(param.name)
        elif param.default is not inspect.Parameter.empty:
            explicit_values[param.name] = param.default
        else:
            msg = f"`{definition.python_name}` is missing required prop `{param.name}`."
            raise TypeError(msg)

    if remaining_props and rest_param is None:
        unexpected_prop = next(iter(remaining_props))
        msg = (
            f"`{definition.python_name}` does not accept prop `{unexpected_prop}`. "
            "Only declared props may be passed when no `rx.RestProp` is present."
        )
        raise TypeError(msg)

    if children_param is None and rest_param is None:
        return tuple(explicit_values[param.name] for param in explicit_params)

    children_value: Any | None = None
    if children_param is not None:
        children_value = args[0] if len(args) == 1 else Fragment.create(*args)

    bound_props = {}
    if children_param is not None:
        bound_props[children_param.name] = children_value
    bound_props.update(explicit_values)
    bound_props.update(remaining_props)
    return (bound_props,)


def _is_component_child(value: Any) -> bool:
    """Check whether a value is valid as an experimental memo child.

    Args:
        value: The value to check.

    Returns:
        Whether the value is a component child.
    """
    return isinstance(value, Component) or (
        isinstance(value, Var)
        and type_utils.typehint_issubclass(value._var_type, Component)
    )


def _create_function_wrapper(
    definition: ExperimentalMemoFunctionDefinition,
) -> Callable[..., Var]:
    """Create the Python wrapper for a var-returning memo.

    Args:
        definition: The function memo definition.

    Returns:
        The wrapper callable.
    """
    imported_var = definition.imported_var

    @wraps(definition.fn)
    def wrapper(*args: Any, **kwargs: Any) -> Var:
        return imported_var.call(
            *_bind_function_runtime_args(definition, *args, **kwargs)
        )

    def call(*args: Any, **kwargs: Any) -> Var:
        return imported_var.call(
            *_bind_function_runtime_args(definition, *args, **kwargs)
        )

    def partial(*args: Any, **kwargs: Any) -> FunctionVar:
        return imported_var.partial(
            *_bind_function_runtime_args(definition, *args, **kwargs)
        )

    object.__setattr__(wrapper, "call", call)
    object.__setattr__(wrapper, "partial", partial)
    object.__setattr__(wrapper, "_as_var", lambda: imported_var)
    return wrapper


def _create_component_wrapper(
    definition: ExperimentalMemoComponentDefinition,
) -> Callable[..., ExperimentalMemoComponent]:
    """Create the Python wrapper for a component-returning memo.

    Args:
        definition: The component memo definition.

    Returns:
        The wrapper callable.
    """
    children_param = _get_children_param(definition.params)
    rest_param = _get_rest_param(definition.params)
    explicit_params = [
        param
        for param in definition.params
        if not param.is_children and not param.is_rest
    ]

    @wraps(definition.fn)
    def wrapper(*children: Any, **props: Any) -> ExperimentalMemoComponent:
        if "children" in props:
            msg = f"`{definition.python_name}` only accepts children positionally."
            raise TypeError(msg)
        if rest_param is not None and rest_param.name in props:
            msg = (
                f"`{definition.python_name}` captures rest props from extra keyword "
                f"arguments. Do not pass `{rest_param.name}=` directly."
            )
            raise TypeError(msg)
        if children and children_param is None:
            msg = f"`{definition.python_name}` only accepts keyword props."
            raise TypeError(msg)
        if any(not _is_component_child(child) for child in children):
            msg = (
                f"`{definition.python_name}` only accepts positional children that are "
                "`rx.Component` or `rx.Var[rx.Component]`."
            )
            raise TypeError(msg)

        explicit_values = {}
        remaining_props = props.copy()
        for param in explicit_params:
            if param.name in remaining_props:
                explicit_values[param.name] = remaining_props.pop(param.name)
            elif param.default is not inspect.Parameter.empty:
                explicit_values[param.name] = param.default
            else:
                msg = f"`{definition.python_name}` is missing required prop `{param.name}`."
                raise TypeError(msg)

        if remaining_props and rest_param is None:
            unexpected_prop = next(iter(remaining_props))
            msg = (
                f"`{definition.python_name}` does not accept prop `{unexpected_prop}`. "
                "Only declared props may be passed when no `rx.RestProp` is present."
            )
            raise TypeError(msg)

        return ExperimentalMemoComponent._create(
            children=list(children),
            memo_definition=definition,
            **explicit_values,
            **remaining_props,
        )

    object.__setattr__(
        wrapper, "_as_var", lambda: _component_import_var(definition.export_name)
    )
    return wrapper


def memo(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Create an experimental memo from a function.

    Args:
        fn: The function to memoize.

    Returns:
        The wrapped function or component factory.

    Raises:
        TypeError: If the return type is not supported.
    """
    hints = get_type_hints(fn)
    return_annotation = hints.get("return", inspect.Signature.empty)
    if return_annotation is inspect.Signature.empty:
        msg = (
            f"`@rx._x.memo` requires a return annotation on `{fn.__name__}`. "
            "Use `-> rx.Component` or `-> rx.Var[...]`."
        )
        raise TypeError(msg)

    if _is_component_annotation(return_annotation):
        definition = _create_component_definition(fn, return_annotation)
        EXPERIMENTAL_MEMOS[definition.export_name] = definition
        return _create_component_wrapper(definition)

    if _is_var_annotation(return_annotation):
        definition = _create_function_definition(fn, return_annotation)
        EXPERIMENTAL_MEMOS[definition.python_name] = definition
        return _create_function_wrapper(definition)

    msg = (
        f"`@rx._x.memo` on `{fn.__name__}` must return `rx.Component` or `rx.Var[...]`, "
        f"got `{return_annotation}`."
    )
    raise TypeError(msg)
