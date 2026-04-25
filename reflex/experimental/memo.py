"""Experimental memo support for vars and components."""

from __future__ import annotations

import dataclasses
import inspect
from collections.abc import Callable
from functools import cache, update_wrapper
from typing import Any, get_args, get_origin, get_type_hints

from reflex_base import constants
from reflex_base.components.component import Component
from reflex_base.components.dynamic import bundled_libraries
from reflex_base.constants.compiler import SpecialAttributes
from reflex_base.constants.state import CAMEL_CASE_MEMO_MARKER
from reflex_base.utils import format
from reflex_base.utils.imports import ImportVar
from reflex_base.utils.types import safe_issubclass
from reflex_base.vars import VarData
from reflex_base.vars.base import LiteralVar, Var
from reflex_base.vars.function import (
    ArgsFunctionOperation,
    DestructuredArg,
    FunctionStringVar,
    FunctionVar,
    ReflexCallable,
)
from reflex_base.vars.object import RestProp
from reflex_components_core.base.bare import Bare
from reflex_components_core.base.fragment import Fragment

from reflex.utils import types as type_utils


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
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

        props: dict[str, Any] = {}
        for key, value in {**declared_props, **rest_props}.items():
            camel_cased_key = format.to_camel_case(key)
            literal_value = LiteralVar.create(value)
            props[camel_cased_key] = literal_value
            setattr(self, camel_cased_key, literal_value)

        prop_names = tuple(props)
        object.__setattr__(self, "get_props", lambda: prop_names)


@cache
def _get_experimental_memo_component_class(
    export_name: str,
) -> type[ExperimentalMemoComponent]:
    """Get the component subclass for an experimental memo export.

    Args:
        export_name: The exported React component name.

    Returns:
        A cached component subclass with the tag set at class definition time.
    """
    return type(
        f"ExperimentalMemoComponent_{export_name}",
        (ExperimentalMemoComponent,),
        {
            "__module__": __name__,
            "tag": export_name,
        },
    )


EXPERIMENTAL_MEMOS: dict[str, ExperimentalMemoDefinition] = {}


def _memo_registry_key(definition: ExperimentalMemoDefinition) -> str:
    """Get the registry key for an experimental memo.

    Args:
        definition: The memo definition.

    Returns:
        The registry key for the memo.
    """
    if isinstance(definition, ExperimentalMemoComponentDefinition):
        return definition.export_name
    return definition.python_name


def _is_memo_reregistration(
    existing: ExperimentalMemoDefinition,
    definition: ExperimentalMemoDefinition,
) -> bool:
    """Check whether a memo definition replaces the same memo during reload.

    Args:
        existing: The currently registered memo definition.
        definition: The new memo definition being registered.

    Returns:
        Whether the new definition should replace the existing one.
    """
    return (
        type(existing) is type(definition)
        and existing.python_name == definition.python_name
        and existing.fn.__module__ == definition.fn.__module__
        and existing.fn.__qualname__ == definition.fn.__qualname__
    )


def _register_memo_definition(definition: ExperimentalMemoDefinition) -> None:
    """Register an experimental memo definition.

    Args:
        definition: The memo definition to register.

    Raises:
        ValueError: If another memo already compiles to the same exported name.
    """
    key = _memo_registry_key(definition)
    if (existing := EXPERIMENTAL_MEMOS.get(key)) is not None and (
        not _is_memo_reregistration(existing, definition)
    ):
        msg = (
            f"Experimental memo name collision for `{key}`: "
            f"`{existing.fn.__module__}.{existing.python_name}` and "
            f"`{definition.fn.__module__}.{definition.python_name}` both compile "
            "to the same memo name."
        )
        raise ValueError(msg)

    EXPERIMENTAL_MEMOS[key] = definition


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
    return isinstance(origin, type) and (
        safe_issubclass(origin, Component)
        or bool(
            safe_issubclass(origin, Var)
            and (args := get_args(annotation))
            and safe_issubclass(args[0], Component)
        )
    )


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


def _normalize_component_return(value: Any) -> Component | None:
    """Normalize a component-like memo return value into a Component.

    Args:
        value: The value returned from the memo function.

    Returns:
        The normalized component, or ``None`` if the value is not component-like.
    """
    if isinstance(value, Component):
        return value

    if isinstance(value, Var) and type_utils.typehint_issubclass(
        value._var_type, Component
    ):
        return Bare.create(value)

    return None


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
    component = _normalize_component_return(_evaluate_memo_function(fn, params))
    if component is None:
        msg = (
            f"Component-returning `@rx._x.memo` `{fn.__name__}` must return an "
            "`rx.Component` or `rx.Var[rx.Component]`."
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

    # Validate positional children usage and reserved keywords.
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

    # Bind declared props before collecting any rest props.
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

    # Reject unknown props unless a rest prop is declared.
    if remaining_props and rest_param is None:
        unexpected_prop = next(iter(remaining_props))
        msg = (
            f"`{definition.python_name}` does not accept prop `{unexpected_prop}`. "
            "Only declared props may be passed when no `rx.RestProp` is present."
        )
        raise TypeError(msg)

    # Return ordered explicit args when no packed props object is needed.
    if children_param is None and rest_param is None:
        return tuple(explicit_values[param.name] for param in explicit_params)

    # Build the props object passed to the imported FunctionVar.
    children_value: Any | None = None
    if children_param is not None:
        children_value = args[0] if len(args) == 1 else Fragment.create(*args)

    # Convert rest-prop keys to camelCase to match component memo behavior.
    camel_cased_remaining_props = {
        format.to_camel_case(key): value for key, value in remaining_props.items()
    }

    bound_props = {}
    if children_param is not None:
        bound_props[children_param.name] = children_value
    bound_props.update(explicit_values)
    bound_props.update(camel_cased_remaining_props)
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


class _ExperimentalMemoFunctionWrapper:
    """Callable wrapper for a var-returning experimental memo."""

    def __init__(self, definition: ExperimentalMemoFunctionDefinition):
        """Initialize the wrapper.

        Args:
            definition: The function memo definition.
        """
        self._definition = definition
        self._imported_var = definition.imported_var
        update_wrapper(self, definition.fn)

    def __call__(self, *args: Any, **kwargs: Any) -> Var:
        """Call the wrapped memo and return a var.

        Args:
            *args: Positional children, if supported.
            **kwargs: Explicit props and rest props.

        Returns:
            The function call var.
        """
        return self.call(*args, **kwargs)

    def call(self, *args: Any, **kwargs: Any) -> Var:
        """Call the imported memo function.

        Args:
            *args: Positional children, if supported.
            **kwargs: Explicit props and rest props.

        Returns:
            The function call var.
        """
        return self._imported_var.call(
            *_bind_function_runtime_args(self._definition, *args, **kwargs)
        )

    def partial(self, *args: Any, **kwargs: Any) -> FunctionVar:
        """Partially apply the imported memo function.

        Args:
            *args: Positional children, if supported.
            **kwargs: Explicit props and rest props.

        Returns:
            The partially applied function var.
        """
        return self._imported_var.partial(
            *_bind_function_runtime_args(self._definition, *args, **kwargs)
        )

    def _as_var(self) -> FunctionVar:
        """Expose the imported function var.

        Returns:
            The imported function var.
        """
        return self._imported_var


class _ExperimentalMemoComponentWrapper:
    """Callable wrapper for a component-returning experimental memo."""

    def __init__(self, definition: ExperimentalMemoComponentDefinition):
        """Initialize the wrapper.

        Args:
            definition: The component memo definition.
        """
        self._definition = definition
        self._children_param = _get_children_param(definition.params)
        self._rest_param = _get_rest_param(definition.params)
        self._explicit_params = [
            param
            for param in definition.params
            if not param.is_children and not param.is_rest
        ]
        update_wrapper(self, definition.fn)

    def __call__(self, *children: Any, **props: Any) -> ExperimentalMemoComponent:
        """Call the wrapped memo and return a component.

        Args:
            *children: Positional children passed to the memo.
            **props: Explicit props and rest props.

        Returns:
            The rendered memo component.
        """
        definition = self._definition
        rest_param = self._rest_param

        # Validate positional children usage and reserved keywords.
        if "children" in props:
            msg = f"`{definition.python_name}` only accepts children positionally."
            raise TypeError(msg)
        if rest_param is not None and rest_param.name in props:
            msg = (
                f"`{definition.python_name}` captures rest props from extra keyword "
                f"arguments. Do not pass `{rest_param.name}=` directly."
            )
            raise TypeError(msg)
        if children and self._children_param is None:
            msg = f"`{definition.python_name}` only accepts keyword props."
            raise TypeError(msg)
        if any(not _is_component_child(child) for child in children):
            msg = (
                f"`{definition.python_name}` only accepts positional children that are "
                "`rx.Component` or `rx.Var[rx.Component]`."
            )
            raise TypeError(msg)

        # Bind declared props before collecting any rest props.
        explicit_values = {}
        remaining_props = props.copy()
        for param in self._explicit_params:
            if param.name in remaining_props:
                explicit_values[param.name] = remaining_props.pop(param.name)
            elif param.default is not inspect.Parameter.empty:
                explicit_values[param.name] = param.default
            else:
                msg = f"`{definition.python_name}` is missing required prop `{param.name}`."
                raise TypeError(msg)

        # Reject unknown props unless a rest prop is declared.
        if remaining_props and rest_param is None:
            unexpected_prop = next(iter(remaining_props))
            msg = (
                f"`{definition.python_name}` does not accept prop `{unexpected_prop}`. "
                "Only declared props may be passed when no `rx.RestProp` is present."
            )
            raise TypeError(msg)

        # Build the component props passed into the memo wrapper.
        return _get_experimental_memo_component_class(definition.export_name)._create(
            children=list(children),
            memo_definition=definition,
            **explicit_values,
            **remaining_props,
        )

    def _as_var(self) -> Var:
        """Expose the imported component var.

        Returns:
            The imported component var.
        """
        return _component_import_var(self._definition.export_name)


def _create_function_wrapper(
    definition: ExperimentalMemoFunctionDefinition,
) -> _ExperimentalMemoFunctionWrapper:
    """Create the Python wrapper for a var-returning memo.

    Args:
        definition: The function memo definition.

    Returns:
        The wrapper callable.
    """
    return _ExperimentalMemoFunctionWrapper(definition)


def _create_component_wrapper(
    definition: ExperimentalMemoComponentDefinition,
) -> _ExperimentalMemoComponentWrapper:
    """Create the Python wrapper for a component-returning memo.

    Args:
        definition: The component memo definition.

    Returns:
        The wrapper callable.
    """
    return _ExperimentalMemoComponentWrapper(definition)


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
        _register_memo_definition(definition)
        return _create_component_wrapper(definition)

    if _is_var_annotation(return_annotation):
        definition = _create_function_definition(fn, return_annotation)
        _register_memo_definition(definition)
        return _create_function_wrapper(definition)

    msg = (
        f"`@rx._x.memo` on `{fn.__name__}` must return `rx.Component` or `rx.Var[...]`, "
        f"got `{return_annotation}`."
    )
    raise TypeError(msg)
