"""Memo support for vars and components."""

from __future__ import annotations

import contextlib
import dataclasses
import importlib
import inspect
from collections.abc import Callable, Iterator, Mapping, Sequence
from copy import copy
from enum import Enum
from functools import cache, update_wrapper
from typing import (
    Annotated,
    Any,
    ClassVar,
    TypeVar,
    get_args,
    get_origin,
    get_type_hints,
    overload,
)

from reflex_components_core.base.fragment import Fragment

from reflex_base import constants
from reflex_base.components.component import Component
from reflex_base.components.dynamic import bundled_libraries
from reflex_base.components.memoize_helpers import (
    MemoizationStrategy,
    get_memoization_strategy,
)
from reflex_base.constants.compiler import (
    MemoizationDisposition,
    MemoizationMode,
    SpecialAttributes,
)
from reflex_base.constants.state import CAMEL_CASE_MEMO_MARKER
from reflex_base.event import EventChain, EventHandler, no_args_event_spec, run_script
from reflex_base.utils import console, format
from reflex_base.utils.imports import ImportVar
from reflex_base.utils.types import safe_issubclass, typehint_issubclass
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


class MemoParamKind(str, Enum):
    """The role a memo parameter plays in the compiled component.

    Each kind owns its full behavior — annotation classification, call-site
    validation, placeholder construction, runtime binding, and JS signature
    emission — via the per-kind :class:`_MemoParamSpec` instance in
    :data:`_SPECS`. Adding a new kind means one new entry in :data:`_SPECS`
    and one extra step in :data:`_CLASSIFICATION_ORDER`; the rest of the
    module learns nothing else about the new kind.
    """

    VALUE = "value"
    CHILDREN = "children"
    REST = "rest"
    EVENT_TRIGGER = "event_trigger"


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class MemoParam:
    """Metadata about an analyzed memo parameter."""

    name: str
    kind: MemoParamKind
    annotation: Any
    parameter_kind: inspect._ParameterKind
    js_prop_name: str
    placeholder_name: str
    kind_data: Any = None
    default: Any = inspect.Parameter.empty

    @property
    def spec(self) -> _MemoParamSpec:
        """The per-kind behavior bundle for this parameter."""
        return _SPECS[self.kind]

    def make_placeholder(self) -> Any:
        """Build the value passed to the memo function during analysis.

        Returns:
            The placeholder value (a ``Var``, ``RestProp``, or plain callable).
        """
        return self.spec.make_placeholder(self)

    def bind_call_value(self, binding: _MemoCallBinding) -> None:
        """Route a user-provided value to props/event_triggers at instantiation.

        Args:
            binding: The call-site routing accumulator.
        """
        self.spec.bind_call_value(self, binding)

    def signature_field(self) -> str | None:
        """The destructured JSX signature entry, or ``None`` if emitted elsewhere.

        Returns:
            The destructured field (e.g. ``"event:eventRxMemo"``), or ``None``
            when this kind is emitted out-of-band by the compiler.
        """
        return self.spec.signature_field(self)


@dataclasses.dataclass(frozen=True, slots=True)
class _MemoParamSpec:
    """The role-owned behavior for one :class:`MemoParamKind`.

    Hooks (in classification + lifecycle order):
        ``classify``: ``(annotation, param_name) -> (matches, kind_data)``.
            Returns whether the annotation belongs to this kind, plus any
            kind-specific payload (the args spec for ``EVENT_TRIGGER``).
        ``validate``: ``(inspect.Parameter, fn_name, for_component) -> None``.
            Raise ``TypeError`` for misuses (no defaults on EH, ``children``
            naming, rest-on-var-memo, etc.).
        ``placeholder_name``: choose the destructured JS identifier (Var/EH
            use ``camelCase + RxMemo``; children/rest keep the bare name).
        ``make_placeholder``: build the analysis-time value passed to the memo
            body function (a ``Var``, a ``RestProp``, or a plain callable).
        ``bind_call_value``: at instantiation, pop the user value from kwargs
            and route it via ``_MemoCallBinding`` to props or event_triggers.
        ``signature_field``: the destructured JSX entry, or ``None`` for kinds
            emitted out-of-band (REST -> spread; CHILDREN -> hardcoded prefix).
    """

    kind: MemoParamKind
    classify: Callable[[Any, str], tuple[bool, Any]]
    validate: Callable[[inspect.Parameter, str, bool], None]
    placeholder_name: Callable[[str, str, bool], str]
    make_placeholder: Callable[[MemoParam], Any]
    bind_call_value: Callable[[MemoParam, _MemoCallBinding], None]
    signature_field: Callable[[MemoParam], str | None]


@dataclasses.dataclass(frozen=True, slots=True)
class MemoDefinition:
    """Base metadata for a memo."""

    fn: Callable[..., Any]
    python_name: str
    params: tuple[MemoParam, ...]


@dataclasses.dataclass(frozen=True, slots=True)
class MemoFunctionDefinition(MemoDefinition):
    """A memo that compiles to a JavaScript function."""

    function: ArgsFunctionOperation
    imported_var: FunctionVar


@dataclasses.dataclass(frozen=True, slots=True)
class MemoComponentDefinition(MemoDefinition):
    """A memo that compiles to a React component."""

    export_name: str
    component: Component
    # For passthrough wrappers built by the auto-memoize plugin: the
    # ``Bare``-wrapped ``{children}`` placeholder used when rendering the memo
    # body. The ``component`` keeps its ORIGINAL children so compile-time
    # walkers (``Form._get_form_refs`` etc.) can introspect the subtree; the
    # compiler swaps to this placeholder only for the JSX render and for
    # imports collection, so descendants emit their refs/imports/hooks in the
    # page scope rather than being duplicated inside the memo body.
    passthrough_hole_child: Component | None = None


class MemoComponent(Component):
    """A rendered instance of a memo component."""

    library = f"$/{constants.Dirs.COMPONENTS_PATH}"
    _memoization_mode = MemoizationMode(disposition=MemoizationDisposition.NEVER)

    # The user-authored component class this wrapper stands in for. Populated
    # on the dynamic subclass by ``_get_memo_component_class`` so
    # introspection (e.g. compile telemetry) can recover the underlying type
    # without parsing the wrapper's auto-generated class name.
    _wrapped_component_type: ClassVar[type[Component] | None] = None

    def _validate_component_children(self, children: list[Component]) -> None:
        """Skip direct parent/child validation for memo wrapper instances.

        Memos wrap an underlying compiled component definition.
        The runtime wrapper should not interpose on `_valid_parents` checks for
        the authored subtree because the wrapper itself is not the semantic
        parent in the user-authored component tree.

        Args:
            children: The children of the component (ignored).
        """

    def _post_init(self, **kwargs):
        """Initialize the memo component.

        Args:
            **kwargs: The kwargs to pass to the component.
        """
        definition = kwargs.pop("memo_definition")
        binding = _MemoCallBinding(kwargs)

        for param in definition.params:
            param.bind_call_value(binding)

        has_rest = _get_rest_param(definition.params) is not None
        rest_props = binding.take_rest(self.get_fields()) if has_rest else {}

        super()._post_init(**binding.build_super_kwargs())

        prop_names = binding.finalize(self, rest_props)
        object.__setattr__(self, "get_props", lambda: prop_names)


@cache
def _get_memo_component_class(
    export_name: str,
    wrapped_component_type: type[Component] = Component,
) -> type[MemoComponent]:
    """Get the component subclass for a memo export.

    Class-level metadata that the compiler reads via ``type(comp)._get_*()``
    (notably ``_get_app_wrap_components``, which carries providers like
    ``UploadFilesProvider`` that must reach the app root) is inherited from
    ``wrapped_component_type`` so the wrapper is a transparent substitute for
    the original in the compile tree.

    Args:
        export_name: The exported React component name.
        wrapped_component_type: The class of the component being memoized.
            Defaults to ``Component`` for memos that don't wrap a user
            component (e.g. function memos, raw passthroughs).

    Returns:
        A cached component subclass with the tag set at class definition time.
    """
    attrs: dict[str, Any] = {
        "__module__": __name__,
        "tag": export_name,
        # Point each memo at its own per-file module so pages import directly
        # from ``$/utils/components/<name>`` rather than through the index.
        # Per-file import paths give Vite distinct module boundaries per
        # memo, enabling actual code-split by page.
        "library": f"$/{constants.Dirs.COMPONENTS_PATH}/{export_name}",
        "_wrapped_component_type": wrapped_component_type,
    }
    if (
        wrapped_component_type._get_app_wrap_components
        is not Component._get_app_wrap_components
    ):
        attrs["_get_app_wrap_components"] = staticmethod(
            wrapped_component_type._get_app_wrap_components
        )
    return type(
        f"MemoComponent_{export_name}",
        (MemoComponent,),
        attrs,
    )


MEMOS: dict[str, MemoDefinition] = {}


def _memo_registry_key(definition: MemoDefinition) -> str:
    """Get the registry key for a memo.

    Args:
        definition: The memo definition.

    Returns:
        The registry key for the memo.
    """
    if isinstance(definition, MemoComponentDefinition):
        return definition.export_name
    return definition.python_name


def _is_memo_reregistration(
    existing: MemoDefinition,
    definition: MemoDefinition,
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


def _register_memo_definition(definition: MemoDefinition) -> None:
    """Register a memo definition.

    Args:
        definition: The memo definition to register.

    Raises:
        ValueError: If another memo already compiles to the same exported name.
    """
    key = _memo_registry_key(definition)
    if (existing := MEMOS.get(key)) is not None and (
        not _is_memo_reregistration(existing, definition)
    ):
        msg = (
            f"Memo name collision for `{key}`: "
            f"`{existing.fn.__module__}.{existing.python_name}` and "
            f"`{definition.fn.__module__}.{definition.python_name}` both compile "
            "to the same memo name."
        )
        raise ValueError(msg)

    MEMOS[key] = definition


def _annotation_inner_type(annotation: Any) -> Any:
    """Unwrap a Var-like annotation to its inner type.

    Args:
        annotation: The annotation to unwrap.

    Returns:
        The inner type for the annotation.
    """
    if _is_rest_annotation(annotation):
        return dict[str, Any]

    annotation = _strip_annotated(annotation)
    origin = get_origin(annotation) or annotation
    if safe_issubclass(origin, Var) and (args := get_args(annotation)):
        return args[0]
    return Any


def _strip_annotated(annotation: Any) -> Any:
    """Unwrap ``Annotated[X, ...]`` to ``X``; pass other annotations through.

    Args:
        annotation: The annotation to unwrap.

    Returns:
        The inner annotation, or the original if not ``Annotated``.
    """
    if get_origin(annotation) is Annotated:
        return get_args(annotation)[0]
    return annotation


def _is_rest_annotation(annotation: Any) -> bool:
    """Check whether an annotation is a RestProp.

    Args:
        annotation: The annotation to check.

    Returns:
        Whether the annotation is a RestProp.
    """
    annotation = _strip_annotated(annotation)
    origin = get_origin(annotation) or annotation
    return isinstance(origin, type) and issubclass(origin, RestProp)


def _is_var_annotation(annotation: Any) -> bool:
    """Check whether an annotation is a Var-like annotation.

    Args:
        annotation: The annotation to check.

    Returns:
        Whether the annotation is Var-like.
    """
    annotation = _strip_annotated(annotation)
    origin = get_origin(annotation) or annotation
    return isinstance(origin, type) and issubclass(origin, Var)


def _is_event_handler_annotation(annotation: Any) -> tuple[bool, Any]:
    """Detect ``EventHandler`` / ``EventHandler[spec]`` / ``EventHandler[s1, s2]``.

    ``EventHandler.__class_getitem__`` returns ``Annotated[EventHandler, spec]`` for a
    single spec and ``Annotated[EventHandler, (s1, s2)]`` (a tuple in the single
    metadata slot) for multiple specs.

    Args:
        annotation: The annotation to inspect.

    Returns:
        ``(is_event_handler, args_spec)`` — ``args_spec`` is ``no_args_event_spec`` for
        bare ``EventHandler``, a single spec callable for ``EventHandler[spec]``, or
        the tuple of specs for the multi-spec form.
    """
    if get_origin(annotation) is Annotated:
        inner, *metadata = get_args(annotation)
        if isinstance(inner, type) and safe_issubclass(inner, EventHandler):
            return True, metadata[0]
        return False, None
    if isinstance(annotation, type) and safe_issubclass(annotation, EventHandler):
        return True, no_args_event_spec
    return False, None


def _is_component_annotation(annotation: Any) -> bool:
    """Check whether an annotation is component-like.

    Args:
        annotation: The annotation to check.

    Returns:
        Whether the annotation resolves to Component.
    """
    annotation = _strip_annotated(annotation)
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
    return _is_var_annotation(annotation) and typehint_issubclass(
        _annotation_inner_type(annotation), Component
    )


def _get_children_param(params: tuple[MemoParam, ...]) -> MemoParam | None:
    return next((p for p in params if p.kind is MemoParamKind.CHILDREN), None)


def _get_rest_param(params: tuple[MemoParam, ...]) -> MemoParam | None:
    return next((p for p in params if p.kind is MemoParamKind.REST), None)


def _imported_function_var(name: str, return_type: Any) -> FunctionVar:
    """Create the imported FunctionVar for a memo.

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
            imports={
                f"$/{constants.Dirs.COMPONENTS_PATH}/{name}": [ImportVar(tag=name)]
            }
        ),
    )


def _component_import_var(name: str) -> Var:
    """Create the imported component var for a memo component.

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
                f"$/{constants.Dirs.COMPONENTS_PATH}/{name}": [ImportVar(tag=name)],
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
            f"Var-returning `@rx.memo` `{func_name}` cannot depend on hooks. "
            "Use a component-returning `@rx.memo` instead."
        )
        raise TypeError(msg)

    if var_data.components:
        msg = (
            f"Var-returning `@rx.memo` `{func_name}` cannot depend on embedded "
            "components, custom code, or dynamic imports. Use a component-returning "
            "`@rx.memo` instead."
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
            f"Var-returning `@rx.memo` `{func_name}` cannot import `{lib}` because "
            "it is not bundled. Use a component-returning `@rx.memo` instead."
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


def _event_handler_placeholder(placeholder_name: str, args_spec: Any) -> Callable:
    """Placeholder callable that compiles calls to the destructured JS prop.

    Returned as a plain callable (not an ``EventHandler``) so it flows through
    ``EventChain.create`` -> ``call_event_fn``, which actually invokes it.
    Wrapping in an ``EventHandler`` would skip the function body and bake the
    Python function name into the rendered ``ReflexEvent(...)`` payload.

    Args:
        placeholder_name: The destructured JS prop identifier (e.g. ``eventRxMemo``).
        args_spec: The user-declared spec, or a tuple of specs from
            ``EventHandler[s1, s2]``. Only the first spec shapes the placeholder's
            signature; the inner-trigger boundary handles the rest.

    Returns:
        A plain callable suitable as a memo-function placeholder.
    """
    prop_callback = Var(_js_expr=placeholder_name).to(FunctionVar)
    primary_spec = args_spec[0] if isinstance(args_spec, tuple) else args_spec

    def _placeholder(*args: Any) -> Any:
        return run_script(prop_callback.call(*args))

    _placeholder.__signature__ = inspect.signature(primary_spec)  # pyright: ignore[reportFunctionMemberAccess]
    return _placeholder


def _classify_value(annotation: Any, name: str) -> tuple[bool, Any]:
    # ``RestProp`` is a ``Var`` subclass, so guard against it here even though
    # ``_CLASSIFICATION_ORDER`` already tries REST first — keeping the classifier
    # self-exclusive removes the implicit ordering dependency.
    return (
        _is_var_annotation(annotation) and not _is_rest_annotation(annotation),
        None,
    )


def _classify_children(annotation: Any, name: str) -> tuple[bool, Any]:
    return (
        name == "children" and _children_annotation_is_valid(annotation),
        None,
    )


def _classify_rest(annotation: Any, name: str) -> tuple[bool, Any]:
    return _is_rest_annotation(annotation), None


def _classify_event_trigger(annotation: Any, name: str) -> tuple[bool, Any]:
    return _is_event_handler_annotation(annotation)


def _validate_noop(
    parameter: inspect.Parameter, fn_name: str, for_component: bool
) -> None:
    pass


def _validate_children(
    parameter: inspect.Parameter, fn_name: str, for_component: bool
) -> None:
    if parameter.name != "children":
        msg = (
            f"`rx.Var[rx.Component]` parameters in `{fn_name}` must be named "
            "`children`."
        )
        raise TypeError(msg)


def _validate_rest(
    parameter: inspect.Parameter, fn_name: str, for_component: bool
) -> None:
    if parameter.name == "children":
        msg = f"`children` in `{fn_name}` cannot be `rx.RestProp`."
        raise TypeError(msg)


def _validate_event_trigger(
    parameter: inspect.Parameter, fn_name: str, for_component: bool
) -> None:
    if not for_component:
        msg = (
            f"`rx.EventHandler` parameters are only supported on component-"
            f"returning memos. Got `{parameter.name}` in `{fn_name}`."
        )
        raise TypeError(msg)
    if parameter.name == "children":
        msg = (
            f"`children` in `{fn_name}` cannot be an `rx.EventHandler`; "
            "use `rx.Var[rx.Component]`."
        )
        raise TypeError(msg)
    if parameter.default is not inspect.Parameter.empty:
        msg = (
            f"`rx.EventHandler` parameter `{parameter.name}` in `{fn_name}` "
            "must not have a default value."
        )
        raise TypeError(msg)


def _placeholder_name_value(name: str, js_prop_name: str, for_component: bool) -> str:
    return js_prop_name + CAMEL_CASE_MEMO_MARKER if for_component else name


def _placeholder_name_passthrough(
    name: str, js_prop_name: str, for_component: bool
) -> str:
    return name


def _make_value_placeholder(param: MemoParam) -> Var:
    return _var_placeholder(param.placeholder_name, param.annotation)


def _make_rest_placeholder_spec(param: MemoParam) -> RestProp:
    return _rest_placeholder(param.placeholder_name)


def _make_event_trigger_placeholder(param: MemoParam) -> Callable[..., Any]:
    return _event_handler_placeholder(param.placeholder_name, param.kind_data)


def _bind_value(param: MemoParam, binding: _MemoCallBinding) -> None:
    if param.name in binding.raw_kwargs:
        binding.add_prop(param.js_prop_name, binding.take(param.name))


def _bind_children(param: MemoParam, binding: _MemoCallBinding) -> None:
    pass


def _bind_rest(param: MemoParam, binding: _MemoCallBinding) -> None:
    pass


def _bind_event_trigger(param: MemoParam, binding: _MemoCallBinding) -> None:
    if param.name in binding.raw_kwargs:
        binding.add_event_trigger(
            param.js_prop_name, binding.take(param.name), param.kind_data
        )


def _signature_destructured(param: MemoParam) -> str:
    return f"{param.js_prop_name}:{param.placeholder_name}"


def _signature_none(param: MemoParam) -> None:
    return None


_SPECS: dict[MemoParamKind, _MemoParamSpec] = {
    MemoParamKind.VALUE: _MemoParamSpec(
        kind=MemoParamKind.VALUE,
        classify=_classify_value,
        validate=_validate_noop,
        placeholder_name=_placeholder_name_value,
        make_placeholder=_make_value_placeholder,
        bind_call_value=_bind_value,
        signature_field=_signature_destructured,
    ),
    MemoParamKind.CHILDREN: _MemoParamSpec(
        kind=MemoParamKind.CHILDREN,
        classify=_classify_children,
        validate=_validate_children,
        placeholder_name=_placeholder_name_passthrough,
        make_placeholder=_make_value_placeholder,
        bind_call_value=_bind_children,
        signature_field=_signature_none,
    ),
    MemoParamKind.REST: _MemoParamSpec(
        kind=MemoParamKind.REST,
        classify=_classify_rest,
        validate=_validate_rest,
        placeholder_name=_placeholder_name_passthrough,
        make_placeholder=_make_rest_placeholder_spec,
        bind_call_value=_bind_rest,
        signature_field=_signature_none,
    ),
    MemoParamKind.EVENT_TRIGGER: _MemoParamSpec(
        kind=MemoParamKind.EVENT_TRIGGER,
        classify=_classify_event_trigger,
        validate=_validate_event_trigger,
        placeholder_name=_placeholder_name_value,
        make_placeholder=_make_event_trigger_placeholder,
        bind_call_value=_bind_event_trigger,
        signature_field=_signature_destructured,
    ),
}

# Order matters: REST and CHILDREN before VALUE (``Var[Component]`` matches
# VALUE's classifier, so children must be tried first). EVENT_TRIGGER is
# independent (``Annotated[EventHandler, ...]`` is not a Var), but listing it
# before VALUE makes the precedence explicit. VALUE is the open fallback.
_CLASSIFICATION_ORDER: tuple[MemoParamKind, ...] = (
    MemoParamKind.REST,
    MemoParamKind.CHILDREN,
    MemoParamKind.EVENT_TRIGGER,
    MemoParamKind.VALUE,
)


class _MemoCallBinding:
    """Accumulates routing decisions for one memo component instantiation.

    Role specs call :meth:`take`, :meth:`add_prop`, and :meth:`add_event_trigger`
    via ``param.bind_call_value(binding)``. The component then calls
    :meth:`build_super_kwargs` (what :meth:`Component._post_init` should see) and
    :meth:`finalize` (apply collected props as attributes after super returns).
    """

    __slots__ = ("_event_triggers", "_props", "raw_kwargs")

    def __init__(self, raw_kwargs: dict[str, Any]) -> None:
        self.raw_kwargs = raw_kwargs
        self._props: dict[str, Any] = {}
        self._event_triggers: dict[str, EventChain | Var] = {}

    def take(self, key: str) -> Any:
        return self.raw_kwargs.pop(key)

    def add_prop(self, js_prop_name: str, value: Any) -> None:
        self._props[js_prop_name] = LiteralVar.create(value)

    def add_event_trigger(self, js_prop_name: str, value: Any, args_spec: Any) -> None:
        self._event_triggers[js_prop_name] = EventChain.create(
            value=value, args_spec=args_spec, key=js_prop_name
        )

    def take_rest(self, component_fields: Mapping[str, Any]) -> dict[str, Any]:
        rest: dict[str, Any] = {}
        for key in list(self.raw_kwargs):
            if key in component_fields or SpecialAttributes.is_special(key):
                continue
            rest[format.to_camel_case(key)] = LiteralVar.create(
                self.raw_kwargs.pop(key)
            )
        return rest

    def build_super_kwargs(self) -> dict[str, Any]:
        """Merge collected event triggers into raw kwargs for ``super()._post_init``.

        Mutates ``raw_kwargs`` in place. Call once per instantiation.

        Returns:
            The kwargs to forward to ``Component._post_init``.
        """
        if self._event_triggers:
            self.raw_kwargs.setdefault("event_triggers", {}).update(
                self._event_triggers
            )
        return self.raw_kwargs

    def finalize(
        self, component: Component, rest_props: dict[str, Any]
    ) -> tuple[str, ...]:
        all_props = {**self._props, **rest_props}
        for key, value in all_props.items():
            setattr(component, key, value)
        return tuple(all_props)


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
        placeholder = param.make_placeholder()
        if param.parameter_kind in (
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

    if isinstance(value, Var) and typehint_issubclass(value._var_type, Component):
        from reflex_components_core.base.bare import Bare

        return Bare.create(value)

    return None


def _lift_rest_props(component: Component) -> Component:
    """Convert RestProp children into special props.

    Args:
        component: The component tree to rewrite.

    Returns:
        The rewritten component tree.
    """
    from reflex_components_core.base.bare import Bare

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
    hints: dict[str, Any] | None = None,
    defaulted_params: list[str] | None = None,
) -> tuple[MemoParam, ...]:
    """Analyze and validate memo parameters.

    Args:
        fn: The function to analyze.
        for_component: Whether the memo returns a component.
        hints: Pre-computed type hints with ``include_extras=True``; computed
            from ``fn`` when omitted.
        defaulted_params: When provided, parameters missing an annotation are
            defaulted (``Var[Component]`` for ``children``, otherwise
            ``Var[Any]``) and their names appended; when ``None``, a missing
            annotation raises ``TypeError``.

    Returns:
        The analyzed parameters.

    Raises:
        TypeError: If the function signature is not supported.
    """
    signature = inspect.signature(fn)
    if hints is None:
        hints = get_type_hints(fn, include_extras=True)

    params: list[MemoParam] = []
    rest_count = 0

    for parameter in signature.parameters.values():
        _check_parameter_kind(parameter, fn.__name__)

        annotation = hints.get(parameter.name, parameter.annotation)
        if annotation is inspect.Parameter.empty:
            if defaulted_params is None:
                msg = (
                    f"All parameters of `{fn.__name__}` must be annotated as `rx.Var[...]` "
                    f"or `rx.RestProp`. Missing annotation for `{parameter.name}`."
                )
                raise TypeError(msg)
            annotation = Var[Component] if parameter.name == "children" else Var[Any]
            defaulted_params.append(parameter.name)

        # Children parameters by name must match the children kind exactly —
        # otherwise we accept a value-typed `children` and emit confusing JSX.
        if (
            parameter.name == "children"
            and not _children_annotation_is_valid(annotation)
            and not _is_event_handler_annotation(annotation)[0]
        ):
            msg = (
                f"`children` in `{fn.__name__}` must be annotated as "
                "`rx.Var[rx.Component]`."
            )
            raise TypeError(msg)

        kind, kind_data = _classify_parameter(annotation, parameter.name, fn.__name__)
        spec = _SPECS[kind]
        spec.validate(parameter, fn.__name__, for_component)

        if kind is MemoParamKind.REST:
            rest_count += 1
            if rest_count > 1:
                msg = f"`@rx.memo` only supports one `rx.RestProp` in `{fn.__name__}`."
                raise TypeError(msg)

        js_prop_name = format.to_camel_case(parameter.name)
        placeholder_name = spec.placeholder_name(
            parameter.name, js_prop_name, for_component
        )

        params.append(
            MemoParam(
                name=parameter.name,
                kind=kind,
                kind_data=kind_data,
                annotation=annotation,
                parameter_kind=parameter.kind,
                default=parameter.default,
                js_prop_name=js_prop_name,
                placeholder_name=placeholder_name,
            )
        )

    return tuple(params)


def _check_parameter_kind(parameter: inspect.Parameter, fn_name: str) -> None:
    """Reject Python parameter kinds (``*args`` / ``**kwargs`` / positional-only)
    that memo does not support.

    Args:
        parameter: The parameter to check.
        fn_name: The function name for error messages.

    Raises:
        TypeError: If the parameter uses an unsupported kind.
    """
    if parameter.kind is inspect.Parameter.VAR_POSITIONAL:
        msg = f"`@rx.memo` does not support `*args` in `{fn_name}`."
        raise TypeError(msg)
    if parameter.kind is inspect.Parameter.VAR_KEYWORD:
        msg = f"`@rx.memo` does not support `**kwargs` in `{fn_name}`."
        raise TypeError(msg)
    if parameter.kind is inspect.Parameter.POSITIONAL_ONLY:
        msg = f"`@rx.memo` does not support positional-only parameters in `{fn_name}`."
        raise TypeError(msg)


def _classify_parameter(
    annotation: Any, param_name: str, fn_name: str
) -> tuple[MemoParamKind, Any]:
    """Walk ``_CLASSIFICATION_ORDER`` and return the first matching kind.

    Args:
        annotation: The parameter annotation.
        param_name: The parameter name (some kinds care, e.g. ``children``).
        fn_name: The function name for error messages.

    Returns:
        The matched ``(kind, kind_data)``.

    Raises:
        TypeError: If no kind matches.
    """
    for kind in _CLASSIFICATION_ORDER:
        matched, kind_data = _SPECS[kind].classify(annotation, param_name)
        if matched:
            return kind, kind_data
    msg = (
        f"All parameters of `{fn_name}` must be annotated as `rx.Var[...]` "
        f"or `rx.RestProp`, got `{annotation}` for `{param_name}`."
    )
    raise TypeError(msg)


def _build_args_function(
    params: tuple[MemoParam, ...], return_expr: Var
) -> ArgsFunctionOperation:
    """Build the JS ``ArgsFunctionOperation`` that wraps a memo's return expression.

    Args:
        params: The memo parameters.
        return_expr: The return expression of the memo body.

    Returns:
        The compiled function operation.
    """
    rest_param = _get_rest_param(params)
    if _get_children_param(params) is None and rest_param is None:
        return ArgsFunctionOperation.create(
            args_names=tuple(param.placeholder_name for param in params),
            return_expr=return_expr,
        )
    return ArgsFunctionOperation.create(
        args_names=(
            DestructuredArg(
                fields=tuple(
                    param.placeholder_name
                    for param in params
                    if param.kind is not MemoParamKind.REST
                ),
                rest=rest_param.placeholder_name if rest_param is not None else None,
            ),
        ),
        return_expr=return_expr,
    )


def _create_component_definition(
    fn: Callable[..., Any],
    return_annotation: Any,
) -> MemoComponentDefinition:
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
            f"Component-returning `@rx.memo` `{fn.__name__}` must return an "
            "`rx.Component` or `rx.Var[rx.Component]`."
        )
        raise TypeError(msg)

    return MemoComponentDefinition(
        fn=fn,
        python_name=fn.__name__,
        params=params,
        export_name=format.to_title_case(fn.__name__),
        component=_lift_rest_props(component),
    )


def _bind_function_runtime_args(
    definition: MemoFunctionDefinition,
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
        if param.kind not in (MemoParamKind.REST, MemoParamKind.CHILDREN)
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
        from reflex_components_core.base.fragment import Fragment

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
    """Check whether a value is valid as a memo child.

    Args:
        value: The value to check.

    Returns:
        Whether the value is a component child.
    """
    return isinstance(value, Component) or (
        isinstance(value, Var) and typehint_issubclass(value._var_type, Component)
    )


class _MemoFunctionWrapper:
    """Callable wrapper for a var-returning memo."""

    def __init__(self, definition: MemoFunctionDefinition):
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


class _MemoComponentWrapper:
    """Callable wrapper for a component-returning memo."""

    def __init__(self, definition: MemoComponentDefinition):
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
            if param.kind not in (MemoParamKind.CHILDREN, MemoParamKind.REST)
        ]
        update_wrapper(self, definition.fn)

    def __call__(self, *children: Any, **props: Any) -> MemoComponent:
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
        return _get_memo_component_class(
            definition.export_name, type(definition.component)
        )._create(
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
    definition: MemoFunctionDefinition,
) -> _MemoFunctionWrapper:
    """Create the Python wrapper for a var-returning memo.

    Args:
        definition: The function memo definition.

    Returns:
        The wrapper callable.
    """
    return _MemoFunctionWrapper(definition)


def _create_component_wrapper(
    definition: MemoComponentDefinition,
) -> _MemoComponentWrapper:
    """Create the Python wrapper for a component-returning memo.

    Args:
        definition: The component memo definition.

    Returns:
        The wrapper callable.
    """
    return _MemoComponentWrapper(definition)


def create_passthrough_component_memo(
    component: Component,
) -> tuple[
    Callable[..., MemoComponent],
    MemoComponentDefinition,
]:
    """Create an unregistered ``@rx.memo``-style passthrough component memo.

    This is used by compiler auto-memoization so generated wrappers compile
    through the memo pipeline instead of emitting ad-hoc page-local
    ``React.memo`` declarations.

    The exported memo name is derived from ``component._compute_memo_tag()``
    after the ``{children}`` hole has been substituted into the wrapped
    component's children (passthrough mode), so two call-sites differing only
    in their children — whose generated memo bodies are identical — collapse
    to one wrapper.

    Args:
        component: The component to wrap.

    Returns:
        The callable memo wrapper and its component definition.
    """
    # Snapshot-boundary components (see ``is_snapshot_boundary``) own their
    # subtree — the ``.children`` slot is internal machinery from the
    # subclass's ``.create`` (e.g. the dropzone Div built inside
    # ``Upload.create``), not a user content hole. The memoize plugin wraps
    # the boundary with no structural children on the page side, so the memo
    # body renders the full snapshot rather than a ``{children}``-holed
    # template.
    render_snapshot = (
        get_memoization_strategy(component) is MemoizationStrategy.SNAPSHOT
    )

    captured_hole_child: list[Component] = []

    def passthrough(children: Var[Component]) -> Component:
        new_component = copy(component)
        if render_snapshot:
            return new_component
        # Components with no original structural children own their own JSX
        # output (e.g. ``CodeBlock`` injects ``code`` as the ``children`` prop
        # in ``_render``). Substituting a ``{children}`` hole here would emit
        # ``jsx(Inner, {children: "..."}, hole)``, and an undefined hole at
        # call time clobbers the prop. Skip the substitution so the wrapper's
        # ``children`` parameter is present in the signature but unused.
        if not component.children:
            return new_component
        from reflex_components_core.base.bare import Bare

        hole_bare = Bare.create(children)
        captured_hole_child.append(hole_bare)
        # Substitute the ``{children}`` hole for the original descendants so
        # the memo body's hash and JSX both reflect the placeholder, not the
        # specific children at any given call site. Original descendants stay
        # reachable on the page-level wrapper via the plugin's
        # ``_get_all_refs`` delegation back to the source component.
        new_component.children = [hole_bare]
        # Compile-time walkers that need the real subtree (notably
        # ``Form._get_form_refs`` collecting id-based input refs into the
        # generated ``handleSubmit`` JS) call ``self._get_all_refs()`` while
        # the memo body's hooks are computed. With the hole substituted in,
        # that walk would return nothing and the form handler would emit an
        # empty ``field_ref_mapping``. Delegate ref collection back to the
        # source component so descendants behind the hole remain visible.
        object.__setattr__(new_component, "_get_all_refs", component._get_all_refs)
        return new_component

    # Evaluate once to compute the tag from the rendered memo body shape.
    # ``_create_component_definition`` will evaluate again internally; the
    # second pass overwrites ``captured_hole_child`` but the captured value
    # is identical.
    params = _analyze_params(passthrough, for_component=True)
    preview = _normalize_component_return(_evaluate_memo_function(passthrough, params))
    if preview is None:
        msg = (
            "`create_passthrough_component_memo` requires a component that "
            "normalizes to `rx.Component`."
        )
        raise TypeError(msg)
    tag = preview._compute_memo_tag()

    passthrough.__name__ = format.to_snake_case(tag)
    passthrough.__qualname__ = passthrough.__name__
    passthrough.__module__ = __name__

    definition = _create_component_definition(passthrough, Component)
    replacements: dict[str, Any] = {}
    if definition.export_name != tag:
        replacements["export_name"] = tag
    if captured_hole_child:
        replacements["passthrough_hole_child"] = captured_hole_child[0]
    if replacements:
        definition = dataclasses.replace(definition, **replacements)

    return _create_component_wrapper(definition), definition


@contextlib.contextmanager
def _bind_self_reference(fn: Callable[..., Any], wrapper: Any) -> Iterator[None]:
    """Bind ``wrapper`` to ``fn.__name__`` so the body can self-reference.

    Python only assigns the decorated name after the decorator returns, but
    memo bodies are evaluated during decoration (and ``rx.foreach`` eagerly
    invokes its render function once). The binding is installed at both the
    module-global slot and the matching free-variable cell so recursion works
    for module-level memos and for memos defined inside another function.
    """
    fn_name = fn.__name__
    fn_globals = fn.__globals__
    sentinel = object()
    previous_global = fn_globals.get(fn_name, sentinel)
    fn_globals[fn_name] = wrapper

    cell = None
    previous_cell_value: Any = sentinel
    free_vars = fn.__code__.co_freevars
    if fn_name in free_vars and fn.__closure__:
        cell = fn.__closure__[free_vars.index(fn_name)]
        # An unset cell stays in the ``sentinel`` state; the decorator's
        # eventual return assigns the wrapper to the same cell anyway, so
        # leaving our temporary write in place is a no-op.
        with contextlib.suppress(ValueError):
            previous_cell_value = cell.cell_contents
        cell.cell_contents = wrapper

    try:
        yield
    finally:
        if previous_global is sentinel:
            fn_globals.pop(fn_name, None)
        else:
            fn_globals[fn_name] = previous_global
        if cell is not None and previous_cell_value is not sentinel:
            cell.cell_contents = previous_cell_value


_MemoVarT = TypeVar("_MemoVarT")


_PUBLIC_NAMESPACES: tuple[tuple[str, str], ...] = (
    # (display prefix, dotted attribute path to walk). Order matters — the
    # shortest user-facing name wins. ``rxe`` only resolves when the optional
    # ``reflex_enterprise`` package is installed.
    ("rx.el", "reflex.el"),
    ("rx", "reflex"),
    ("rxe.dnd", "reflex_enterprise.dnd"),
    ("rxe.flow", "reflex_enterprise.flow"),
    ("rxe.components.dnd", "reflex_enterprise.components.dnd"),
    ("rxe.components.flow", "reflex_enterprise.components.flow"),
    ("rxe", "reflex_enterprise"),
)


def _resolve_namespace(dotted: str) -> Any:
    """Walk a dotted path of attribute accesses rooted at an importable module.

    Args:
        dotted: e.g. ``"reflex.el"`` or ``"reflex_enterprise.components.flow"``.

    Returns:
        The resolved namespace object, or ``None`` if any step fails.
    """
    head, *rest = dotted.split(".")
    try:
        ns: Any = importlib.import_module(head)
    except ImportError:
        return None
    for attr in rest:
        ns = getattr(ns, attr, None)
        if ns is None:
            return None
    return ns


def _resolve_component_qualname(cls: type) -> str | None:
    """Find the shortest public ``rx``/``rxe`` qualname under which ``cls`` lives.

    Args:
        cls: The class to resolve.

    Returns:
        The qualname (e.g. ``"rxe.dnd.Draggable"``), or ``None`` when no public
        path is found.
    """
    name = cls.__name__
    for display_prefix, dotted in _PUBLIC_NAMESPACES:
        ns = _resolve_namespace(dotted)
        if ns is not None and getattr(ns, name, None) is cls:
            return f"{display_prefix}.{name}"
    return None


def _suggest_return_annotation(result: Any, is_component: bool) -> str | None:
    """Infer a copy-pasteable return annotation from a memo body's eval result.

    Args:
        result: The value the body returned during memo eval.
        is_component: Whether the memo was treated as component-returning.

    Returns:
        A suggestion like ``"rxe.dnd.Draggable"`` or ``"rx.Var[str]"``, or
        ``None`` when the result doesn't map cleanly to a public name.
    """
    if is_component:
        body = _normalize_component_return(result)
        if body is None:
            return None
        return _resolve_component_qualname(type(body))
    if isinstance(result, Var):
        inner = result._var_type
        if isinstance(inner, type):
            qual = _resolve_component_qualname(inner)
            if qual is not None:
                return f"rx.Var[{qual}]"
            if inner.__module__ == "builtins":
                return f"rx.Var[{inner.__name__}]"
    return None


def _warn_missing_annotations(
    fn_name: str,
    missing_return: bool,
    defaulted_params: Sequence[str],
    suggested_return: str | None = None,
) -> None:
    """Emit a deprecation warning for ``@rx.memo`` without explicit annotations.

    Args:
        fn_name: Name of the decorated function (for the warning text).
        missing_return: Whether the return annotation was missing.
        defaulted_params: Names of parameters whose annotation was defaulted.
        suggested_return: Inferred return type (e.g. ``"rxe.dnd.Draggable"``)
            to surface in the message. When ``None``, the generic hint is used.
    """
    parts: list[str] = []
    if missing_return:
        if suggested_return is not None:
            parts.append(f"a return annotation `-> {suggested_return}`")
        else:
            parts.append("a return annotation (`-> rx.Component` or `-> rx.Var[...]`)")
    if defaulted_params:
        joined = ", ".join(f"`{name}`" for name in defaulted_params)
        parts.append(f"annotations on parameter(s) {joined} (`rx.Var[...]`)")
    console.deprecate(
        feature_name=f"`@rx.memo` on `{fn_name}` without explicit annotations",
        reason=(
            f"Add {' and '.join(parts)}. Missing annotations now default to "
            "`rx.Component` / `rx.Var[Any]`"
        ),
        deprecation_version="0.9.3",
        removal_version="1.0",
    )


@overload
def memo(fn: Callable[..., Component]) -> _MemoComponentWrapper: ...
@overload
def memo(fn: Callable[..., Var[_MemoVarT]]) -> _MemoFunctionWrapper: ...
def memo(fn: Callable[..., Any]) -> _MemoComponentWrapper | _MemoFunctionWrapper:
    """Create a memo from a function.

    Args:
        fn: The function to memoize.

    Returns:
        The wrapped function or component factory.

    Raises:
        TypeError: If the return type is not supported.
    """
    hints = get_type_hints(fn, include_extras=True)
    return_annotation = hints.get("return", inspect.Signature.empty)
    missing_return = return_annotation is inspect.Signature.empty
    if missing_return:
        return_annotation = Component
        hints["return"] = Component

    is_component = _is_component_annotation(return_annotation)
    if not is_component and not _is_var_annotation(return_annotation):
        msg = (
            f"`@rx.memo` on `{fn.__name__}` must return `rx.Component` or "
            f"`rx.Var[...]`, got `{return_annotation}`."
        )
        raise TypeError(msg)

    defaulted_params: list[str] = []
    params = _analyze_params(
        fn,
        for_component=is_component,
        hints=hints,
        defaulted_params=defaulted_params,
    )

    # Construct the wrapper against a placeholder body so the user's body can
    # self-reference the memo during eager evaluation; the real body is patched
    # in after eval completes (see `_bind_self_reference`).
    definition: MemoComponentDefinition | MemoFunctionDefinition
    if is_component:
        definition = MemoComponentDefinition(
            fn=fn,
            python_name=fn.__name__,
            params=params,
            export_name=format.to_title_case(fn.__name__),
            component=Fragment.create(),
        )
        wrapper = _create_component_wrapper(definition)
    else:
        definition = MemoFunctionDefinition(
            fn=fn,
            python_name=fn.__name__,
            params=params,
            function=ArgsFunctionOperation.create(
                args_names=(), return_expr=LiteralVar.create(None)
            ),
            imported_var=_imported_function_var(
                fn.__name__, _annotation_inner_type(return_annotation)
            ),
        )
        wrapper = _create_function_wrapper(definition)

    with _bind_self_reference(fn, wrapper):
        result = _evaluate_memo_function(fn, params)

    if missing_return or defaulted_params:
        _warn_missing_annotations(
            fn.__name__,
            missing_return,
            defaulted_params,
            suggested_return=_suggest_return_annotation(result, is_component)
            if missing_return
            else None,
        )

    if is_component:
        body = _normalize_component_return(result)
        if body is None:
            msg = (
                f"Component-returning `@rx.memo` `{fn.__name__}` must return an "
                "`rx.Component` or `rx.Var[rx.Component]`."
            )
            raise TypeError(msg)
        object.__setattr__(definition, "component", _lift_rest_props(body))
    else:
        return_expr = Var.create(result)
        _validate_var_return_expr(return_expr, fn.__name__)
        object.__setattr__(
            definition, "function", _build_args_function(params, return_expr)
        )

    _register_memo_definition(definition)
    return wrapper


__all__ = [
    "MEMOS",
    "MemoComponent",
    "MemoComponentDefinition",
    "MemoDefinition",
    "MemoFunctionDefinition",
    "create_passthrough_component_memo",
    "memo",
]
