"""Memo support for vars and components."""

from __future__ import annotations

import dataclasses
import inspect
import sys
from collections.abc import Callable, Mapping, Sequence
from copy import copy
from enum import Enum
from functools import cache, partial, update_wrapper
from types import UnionType
from typing import (
    Annotated,
    Any,
    ClassVar,
    Generic,
    Protocol,
    TypeVar,
    Union,
    cast,
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
from reflex_base.utils import console, format, memo_paths
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

# A `Var[Component]` default for memo `children` slots (and any prop typed
# `rx.Var[rx.Component]`), mirroring `EMPTY_VAR_STR` / `EMPTY_VAR_INT`. It lives
# here rather than in ``component.py`` because materializing a component var
# eagerly imports ``Bare`` (and thus ``reflex_base.environment``); defining it
# in the always-early ``component.py`` would cycle when ``environment`` is the
# entry point. ``memo.py`` is imported lazily, after ``environment`` is ready.
EMPTY_VAR_COMPONENT: Var[Component] = LiteralVar.create(Component.create())

# The default JS wrapper applied to a compiled component memo's function
# definition: React's ``memo``, carrying its own import. ``@rx.memo`` accepts a
# ``wrapper=`` override to swap it for another helper, or ``None`` to export
# the bare function component.
DEFAULT_MEMO_WRAPPER: FunctionVar = FunctionStringVar.create(
    "memo",
    _var_data=VarData(imports={"react": [ImportVar(tag="memo")]}),
)

# Base ``Component`` props a memo accepts without an ``rx.RestProp`` (with a
# deprecation warning). Only ``key`` qualifies: React consumes it at the
# reconciliation layer, so it takes effect on the rendered element even though
# the compiled memo function destructures only its declared params. The legacy
# custom-component use case this restores is setting ``key`` under ``rx.foreach``.
#
# Other base props (``id``, ``class_name``, ``style``, ``custom_attrs``,
# ``ref``) are deliberately NOT forwardable: without a ``RestProp`` the memo
# function emits no ``...rest`` spread, so they would be silently dropped rather
# than reaching the root. They raise like any unknown prop, and the error points
# at ``rx.RestProp`` — which compiles to a ``...rest`` spread that genuinely
# forwards them.
_FORWARDABLE_BASE_PROPS: frozenset[str] = frozenset({"key"})


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


_BodyT = TypeVar("_BodyT")


class _LazyBody(Generic[_BodyT]):
    """A memo body computed once, on first read.

    ``@rx.memo`` registers a definition without running the decorated body; the
    body is built by ``thunk`` on the first :meth:`get` and cached thereafter,
    so decoration has no import-time side effects. A re-entrant read during that
    evaluation — a component memo that instantiates itself via recursive
    ``rx.foreach`` — returns the ``placeholder`` instead of recursing. Var memos
    never re-enter (recursion resolves through the imported function var), so
    they pass no placeholder. Eagerly built definitions use :meth:`ready`.

    Not thread-safe: the re-entrancy guard is a plain flag, which is sufficient
    because memo bodies are only ever evaluated during single-threaded compile.
    """

    __slots__ = ("_busy", "_placeholder", "_ready", "_thunk", "_value")
    _value: _BodyT

    def __init__(
        self, thunk: Callable[[], _BodyT], placeholder: _BodyT | None = None
    ) -> None:
        """Defer ``thunk`` until first read.

        Args:
            thunk: Builds and returns the body on first :meth:`get`.
            placeholder: Stand-in returned if the body is read while ``thunk``
                is still running (the recursive component-memo case).
        """
        self._thunk = thunk
        self._placeholder = placeholder
        self._ready = False
        self._busy = False

    @classmethod
    def ready(cls, value: _BodyT) -> _LazyBody[_BodyT]:
        """Wrap an already-computed body.

        Args:
            value: The precomputed body.

        Returns:
            A lazy body that yields ``value`` without running a thunk.
        """
        body = cls(lambda: value)
        body._value = value
        body._ready = True
        return body

    def get(self) -> _BodyT:
        """Return the body, running and caching ``thunk`` on first read.

        Returns:
            The cached body, or the placeholder when read mid-evaluation.

        Raises:
            RuntimeError: If the body re-enters its own evaluation but carries
                no placeholder (only component memos re-enter, and they always
                provide one — so this signals a broken invariant, not a missing
                body).
        """
        if self._ready:
            return self._value
        if self._busy:
            if self._placeholder is None:
                msg = "Re-entrant memo body read before its evaluation finished."
                raise RuntimeError(msg)
            return self._placeholder
        self._busy = True
        try:
            self._value = self._thunk()
            self._ready = True
        finally:
            self._busy = False
        return self._value


@dataclasses.dataclass(frozen=True, slots=True)
class MemoDefinition:
    """Base metadata for a memo."""

    fn: Callable[..., Any]
    python_name: str
    params: tuple[MemoParam, ...]
    # The Python module that defined this memo. When set, the memo's compiled
    # JSX is emitted to a path mirroring that module and the page-side import
    # resolves there instead of the per-name ``utils/components/<name>`` path
    # used for memos that can't be mirrored. ``kw_only`` so subclasses can keep
    # their own required fields.
    source_module: str | None = dataclasses.field(default=None, kw_only=True)


@dataclasses.dataclass(frozen=True, slots=True)
class MemoFunctionDefinition(MemoDefinition):
    """A memo that compiles to a JavaScript function."""

    _function: _LazyBody[ArgsFunctionOperation]
    imported_var: FunctionVar

    @property
    def function(self) -> ArgsFunctionOperation:
        """The compiled function body, evaluated on first access.

        Returns:
            The compiled ``ArgsFunctionOperation`` for this memo.
        """
        return self._function.get()


@dataclasses.dataclass(frozen=True, slots=True)
class MemoComponentDefinition(MemoDefinition):
    """A memo that compiles to a React component."""

    export_name: str
    _component: _LazyBody[Component]
    _runtime_param_values: dict[str, Any] = dataclasses.field(
        default_factory=dict, repr=False, compare=False
    )
    # For passthrough wrappers built by the auto-memoize plugin: the
    # ``Bare``-wrapped ``{children}`` placeholder used when rendering the memo
    # body. The ``component`` keeps its ORIGINAL children so compile-time
    # walkers (``Form._get_form_refs`` etc.) can introspect the subtree; the
    # compiler swaps to this placeholder only for the JSX render and for
    # imports collection, so descendants emit their refs/imports/hooks in the
    # page scope rather than being duplicated inside the memo body.
    passthrough_hole_child: Component | None = None
    # The JS function the compiled function component is wrapped in — React's
    # ``memo`` by default. ``None`` exports the bare function component. The
    # wrapper's ``VarData`` supplies its imports, so a custom wrapper brings
    # its own and ``None`` pulls in nothing.
    wrapper: Var | None = DEFAULT_MEMO_WRAPPER

    @property
    def component(self) -> Component:
        """The compiled component body, evaluated on first access.

        Returns:
            The compiled ``Component`` for this memo.
        """
        return self._component.get()


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
    source_module: str | None = None,
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
        source_module: The user-app Python module that defined this memo. When
            set, the wrapper imports from a path mirroring that module instead
            of the per-name ``utils/components/<name>`` path.

    Returns:
        A cached component subclass with the tag set at class definition time.
    """
    # With a source module the memo is grouped into a file mirroring its
    # Python module; otherwise each memo gets its own per-file module so Vite
    # has distinct module boundaries per memo, enabling code-split by page.
    library, symbol = memo_paths.library_and_symbol(source_module, export_name)
    attrs: dict[str, Any] = {
        "__module__": __name__,
        "tag": symbol,
        "library": library,
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
        f"MemoComponent_{symbol}",
        (MemoComponent,),
        attrs,
    )


def reset_memo_component_classes() -> None:
    """Clear the cached memo wrapper classes.

    Called at the start of each compile so a memo's ``library`` is recomputed
    from the current module layout. Without this, a module that switches to a
    package (or back) between hot-reload compiles would keep serving the
    library specifier resolved on the first compile, pointing pages at an
    output path the compiler no longer writes.
    """
    _get_memo_component_class.cache_clear()


MEMOS: dict[tuple[str, str | None], MemoDefinition] = {}


def _memo_registry_key(definition: MemoDefinition) -> tuple[str, str | None]:
    """Get the registry key for a memo.

    The key pairs the compiled name with the source module: two memos with the
    same name in different modules compile to distinct files (and distinct JS
    symbols), so they must register as separate entries rather than colliding.

    Args:
        definition: The memo definition.

    Returns:
        The ``(name, source_module)`` registry key for the memo.
    """
    if isinstance(definition, MemoComponentDefinition):
        return definition.export_name, definition.source_module
    return definition.python_name, definition.source_module


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
            f"Memo name collision for `{key[0]}`: "
            f"`{existing.fn.__module__}.{existing.python_name}` and "
            f"`{definition.fn.__module__}.{definition.python_name}` both compile "
            "to the same memo name in the same module."
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


_UNION_ORIGINS = (Union, UnionType)

# Python <=3.10's ``get_type_hints`` rewrites a parameter with a ``= None``
# default into ``Optional[...]``, hiding the real annotation from the param
# classifiers; 3.11 dropped that behavior. Only those versions need the
# ``_strip_optional`` normalization, so newer interpreters skip it entirely
# rather than pay ``get_origin`` per parameter for a problem they don't have.
_GET_TYPE_HINTS_WRAPS_NONE_DEFAULT = sys.version_info < (3, 11)


def _strip_optional(annotation: Any) -> Any:
    """Unwrap ``Optional[X]`` / ``X | None`` down to ``X``.

    Restores the annotation the classifiers expect after Python <=3.10's
    ``get_type_hints`` wraps a ``= None``-defaulted parameter in ``Optional``
    (see ``_GET_TYPE_HINTS_WRAPS_NONE_DEFAULT``).

    Args:
        annotation: The annotation to normalize.

    Returns:
        The sole non-``None`` member of an ``Optional`` union, else the
        annotation unchanged.
    """
    if get_origin(annotation) in _UNION_ORIGINS:
        non_none = [arg for arg in get_args(annotation) if arg is not type(None)]
        if len(non_none) == 1:
            return non_none[0]
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


def _is_memo_annotation(annotation: Any) -> bool:
    """Check whether an annotation is already a recognized memo annotation.

    Recognized annotations are ``rx.Var[...]`` (including ``rx.RestProp``, a
    ``Var`` subclass) and ``rx.EventHandler[...]``. Anything else is a legacy
    bare Python type that the public :func:`memo` decorator coerces into
    ``rx.Var[...]`` for backwards compatibility.

    Args:
        annotation: The annotation to check.

    Returns:
        Whether the annotation is already a valid memo parameter annotation.
    """
    return _is_var_annotation(annotation) or _is_event_handler_annotation(annotation)[0]


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


def _imported_function_var(
    name: str, return_type: Any, source_module: str | None = None
) -> FunctionVar:
    """Create the imported FunctionVar for a memo.

    Args:
        name: The exported function name.
        return_type: The return type of the function.
        source_module: The Python module that defined the memo. When set, the
            import resolves to the mirrored module file instead of the per-name
            ``utils/components/<name>`` path.

    Returns:
        The imported FunctionVar.
    """
    library, symbol = memo_paths.library_and_symbol(source_module, name)
    return FunctionStringVar.create(
        symbol,
        _var_type=ReflexCallable[Any, return_type],
        _var_data=VarData(imports={library: [ImportVar(tag=symbol)]}),
    )


def _component_import_var(name: str, source_module: str | None = None) -> Var:
    """Create the imported component var for a memo component.

    Args:
        name: The exported component name.
        source_module: The Python module that defined the memo. When set, the
            import resolves to the mirrored module file instead of the per-name
            ``utils/components/<name>`` path.

    Returns:
        The component var.
    """
    library, symbol = memo_paths.library_and_symbol(source_module, name)
    return Var(
        symbol,
        _var_type=type[Component],
        _var_data=VarData(
            imports={
                library: [ImportVar(tag=symbol)],
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


def _var_placeholder(
    name: str,
    annotation: Any,
    runtime_value: Any | None = None,
) -> Var:
    """Create a placeholder Var for a memo parameter.

    Args:
        name: The JavaScript identifier.
        annotation: The parameter annotation.
        runtime_value: Optional runtime value used to infer unannotated params.

    Returns:
        The placeholder Var.
    """
    if _annotation_inner_type(annotation) is Any and runtime_value is not None:
        runtime_type = (
            runtime_value._var_type if isinstance(runtime_value, Var) else type(runtime_value)
        )
        return Var(_js_expr=name, _var_type=runtime_type).guess_type()
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
    runtime_values: Mapping[str, Any] | None = None,
) -> Any:
    """Evaluate a memo function with placeholder vars.

    Args:
        fn: The function to evaluate.
        params: The memo parameters.
        runtime_values: Optional runtime values keyed by parameter name.

    Returns:
        The return value from the function.
    """
    positional_args = []
    keyword_args = {}

    for param in params:
        if param.kind is MemoParamKind.VALUE:
            placeholder = _var_placeholder(
                param.placeholder_name,
                param.annotation,
                runtime_values.get(param.name) if runtime_values is not None else None,
            )
        else:
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
        defaulted_params: When provided, parameters that are missing an
            annotation or carry a legacy bare-type annotation are coerced to
            ``Var[...]`` (``Var[Component]`` for ``children``, ``Var[Any]`` for
            a missing annotation, otherwise ``Var[<bare type>]``) and their
            names appended; when ``None`` (strict mode, used by internal
            callers) either case raises ``TypeError``.

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
        if _GET_TYPE_HINTS_WRAPS_NONE_DEFAULT and parameter.default is None:
            annotation = _strip_optional(annotation)
        is_missing = annotation is inspect.Parameter.empty
        # Legacy `@rx.memo` (the old `custom_component`) accepted missing and
        # bare Python-type annotations and auto-wrapped them in a `Var`. Coerce
        # both into `rx.Var[...]` and flag the parameter, so one deprecation
        # warning points the user at the params that still need an explicit
        # annotation. Strict callers (`defaulted_params is None`) reject a
        # missing annotation here; a bare type falls through to
        # `_classify_parameter`, which rejects it.
        is_legacy = defaulted_params is not None and not _is_memo_annotation(annotation)
        if is_missing or is_legacy:
            if defaulted_params is None:
                msg = (
                    f"All parameters of `{fn.__name__}` must be annotated as `rx.Var[...]` "
                    f"or `rx.RestProp`. Missing annotation for `{parameter.name}`."
                )
                raise TypeError(msg)
            if parameter.name == "children":
                annotation = Var[Component]
            elif is_missing:
                annotation = Var[Any]
            else:
                annotation = Var[annotation]
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


def _evaluate_component_body(
    fn: Callable[..., Any],
    params: tuple[MemoParam, ...],
    runtime_values: Mapping[str, Any] | None = None,
) -> Component:
    """Run a component memo's body and return its compiled component.

    Args:
        fn: The decorated function.
        params: The analyzed memo parameters.
        runtime_values: Optional runtime values keyed by parameter name.

    Returns:
        The wrapped component the body returned.

    Raises:
        TypeError: If the body does not return a component.
    """
    body = _normalize_component_return(
        _evaluate_memo_function(fn, params, runtime_values)
    )
    if body is None:
        msg = (
            f"Component-returning `@rx.memo` `{fn.__name__}` must return an "
            "`rx.Component` or `rx.Var[rx.Component]`."
        )
        raise TypeError(msg)
    return _lift_rest_props(body)


def _evaluate_function_body(
    fn: Callable[..., Any], params: tuple[MemoParam, ...]
) -> ArgsFunctionOperation:
    """Run a var memo's body and build its compiled function.

    Args:
        fn: The decorated function.
        params: The analyzed memo parameters.

    Returns:
        The compiled ``ArgsFunctionOperation`` for the memo body.
    """
    return_expr = Var.create(_evaluate_memo_function(fn, params))
    _validate_var_return_expr(return_expr, fn.__name__)
    return _build_args_function(params, return_expr)


def _create_component_definition(
    fn: Callable[..., Any],
    return_annotation: Any,
    source_module: str | None = None,
) -> MemoComponentDefinition:
    """Create a definition for a component-returning memo.

    Args:
        fn: The function to analyze.
        return_annotation: The return annotation.
        source_module: The user-app Python module that defined the memo.

    Returns:
        The component memo definition.

    Raises:
        TypeError: If the function does not return a component.
    """
    params = _analyze_params(fn, for_component=True)
    runtime_param_values: dict[str, Any] = {}
    return MemoComponentDefinition(
        fn=fn,
        python_name=fn.__name__,
        params=params,
        source_module=source_module,
        export_name=format.to_title_case(fn.__name__),
        _component=_LazyBody(
            lambda: _evaluate_component_body(fn, params, runtime_param_values)
        ),
        _runtime_param_values=runtime_param_values,
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
        # Forwardable-base-prop name sets already warned about, keyed per
        # wrapper. ``console.deprecate`` walks and path-resolves the call stack
        # before its own dedupe check, so a keyed memo under ``rx.foreach``
        # would pay that walk on every row. Gating here keeps it to the first.
        self._warned_base_props: set[frozenset[str]] = set()
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

        # Reject unknown props unless a rest prop is declared. ``key`` is the
        # one exception (see ``_FORWARDABLE_BASE_PROPS``); every other undeclared
        # prop raises with a message that points at ``rx.RestProp``.
        if remaining_props and rest_param is None:
            unknown = [
                name for name in remaining_props if name not in _FORWARDABLE_BASE_PROPS
            ]
            if unknown:
                msg = (
                    f"`{definition.python_name}` does not accept prop `{unknown[0]}`. "
                    "Only declared props may be passed when no `rx.RestProp` is present."
                )
                raise TypeError(msg)
            warned_key = frozenset(remaining_props)
            if warned_key not in self._warned_base_props:
                self._warned_base_props.add(warned_key)
                _warn_legacy_base_props(definition.python_name, list(remaining_props))

        # Reading ``component`` materializes the deferred body, so ``type(...)``
        # reflects the real wrapped class rather than the placeholder.
        definition._runtime_param_values.clear()
        definition._runtime_param_values.update(explicit_values)
        try:
            component_type = type(definition.component)
        finally:
            definition._runtime_param_values.clear()
        return _get_memo_component_class(
            definition.export_name,
            component_type,
            definition.source_module,
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
        return _component_import_var(
            self._definition.export_name, self._definition.source_module
        )


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
    source_module: str | None = None,
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
        source_module: The user-app Python module that triggered creation of
            this memo (typically the page that contained the wrapped subtree).

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

    definition = _create_component_definition(passthrough, Component, source_module)
    replacements: dict[str, Any] = {}
    if definition.export_name != tag:
        replacements["export_name"] = tag
    if captured_hole_child:
        replacements["passthrough_hole_child"] = captured_hole_child[0]
    if replacements:
        definition = dataclasses.replace(definition, **replacements)

    return _create_component_wrapper(definition), definition


def create_component_memo(component: Component, name: str) -> MemoComponentDefinition:
    """Create an unregistered component memo that renders a standalone component.

    Unlike `create_passthrough_component_memo`, the memo body renders the full
    component (no `{children}` hole), so it works where the memo is referenced
    without children — e.g. re-exported as a route's `HydrateFallback`. Register
    the returned definition (e.g. in `CompileContext.auto_memo_components`) so it
    compiles to its own JS module under `$/{components}/{export_name}`.

    Args:
        component: The component to render in the memo body.
        name: The Python name used to derive the exported React component name.

    Returns:
        The component memo definition.
    """

    def snapshot() -> Component:
        return component

    snapshot.__name__ = name
    snapshot.__qualname__ = name
    snapshot.__module__ = __name__
    return _create_component_definition(snapshot, Component)


_MemoVarT = TypeVar("_MemoVarT")


def _warn_missing_annotations(
    fn_name: str,
    missing_return: bool,
    defaulted_params: Sequence[str],
) -> None:
    """Emit a deprecation warning for ``@rx.memo`` without explicit annotations.

    Args:
        fn_name: Name of the decorated function (for the warning text).
        missing_return: Whether the return annotation was missing.
        defaulted_params: Names of parameters whose annotation was missing or a
            legacy bare type and so was coerced to ``rx.Var[...]``.
    """
    parts: list[str] = []
    if missing_return:
        parts.append("a return annotation `-> rx.Component` (or `-> rx.Var[...]`)")
    if defaulted_params:
        joined = ", ".join(f"`{name}`" for name in defaulted_params)
        parts.append(f"`rx.Var[...]` annotations on parameter(s) {joined}")
    console.deprecate(
        feature_name=f"`@rx.memo` on `{fn_name}` without explicit annotations",
        reason=(
            f"Add {' and '.join(parts)}. Until removal, a missing return "
            "defaults to `rx.Component` and missing or bare-type parameters are "
            "coerced to `rx.Var[...]`"
        ),
        deprecation_version="0.9.3",
        removal_version="1.0",
    )


def _warn_legacy_base_props(fn_name: str, prop_names: Sequence[str]) -> None:
    """Warn that base-``Component`` props on a ``RestProp``-less memo are deprecated.

    ``prop_names`` is effectively always ``["key"]`` — the only forwardable prop.

    Args:
        fn_name: Name of the memo (for the warning text).
        prop_names: The base-component prop names passed at the call site.
    """
    joined = ", ".join(f"`{name}`" for name in prop_names)
    console.deprecate(
        feature_name=(
            f"Passing base-component prop(s) {joined} to `@rx.memo` `{fn_name}` "
            "without an `rx.RestProp`"
        ),
        reason=(
            "Declare an `rx.RestProp` parameter to keep passing base props like "
            "`key` to the rendered component"
        ),
        deprecation_version="0.9.3",
        removal_version="1.0",
    )


def _memo_impl(
    fn: Callable[..., Any],
    wrapper: Var | None,
) -> _MemoComponentWrapper | _MemoFunctionWrapper:
    """Analyze and register a memo definition for a decorated function.

    Args:
        fn: The function to memoize.
        wrapper: The JS wrapper for a component-returning memo, or ``None``
            for no wrapper.

    Returns:
        The wrapped function or component factory.

    Raises:
        TypeError: If the return annotation is not supported, or a non-default
            ``wrapper`` is given for a var-returning memo.
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
    if not is_component and wrapper is not DEFAULT_MEMO_WRAPPER:
        msg = (
            "`@rx.memo` only supports `wrapper=` on component-returning memos; "
            f"`{fn.__name__}` returns `rx.Var[...]`, which compiles to a plain "
            "function."
        )
        raise TypeError(msg)

    defaulted_params: list[str] = []
    params = _analyze_params(
        fn,
        for_component=is_component,
        hints=hints,
        defaulted_params=defaulted_params,
    )

    source_module = memo_paths.capture_source_module(fn)

    if missing_return or defaulted_params:
        _warn_missing_annotations(fn.__name__, missing_return, defaulted_params)

    # Build the definition with a deferred body: the decorated function runs on
    # first read of ``.component`` / ``.function`` (see ``_LazyBody``), not here,
    # so decoration has no import-time side effects. The component placeholder
    # stands in for re-entrant reads during a recursive memo's own evaluation,
    # where the name resolves to ``memo_callable`` (already bound by first use).
    definition: MemoComponentDefinition | MemoFunctionDefinition
    memo_callable: _MemoComponentWrapper | _MemoFunctionWrapper
    if is_component:
        runtime_param_values: dict[str, Any] = {}
        definition = MemoComponentDefinition(
            fn=fn,
            python_name=fn.__name__,
            params=params,
            source_module=source_module,
            export_name=format.to_title_case(fn.__name__),
            _component=_LazyBody(
                lambda: _evaluate_component_body(fn, params, runtime_param_values),
                placeholder=Fragment.create(),
            ),
            _runtime_param_values=runtime_param_values,
            wrapper=wrapper,
        )
        memo_callable = _create_component_wrapper(definition)
    else:
        definition = MemoFunctionDefinition(
            fn=fn,
            python_name=fn.__name__,
            params=params,
            source_module=source_module,
            _function=_LazyBody(lambda: _evaluate_function_body(fn, params)),
            imported_var=_imported_function_var(
                fn.__name__,
                _annotation_inner_type(return_annotation),
                source_module=source_module,
            ),
        )
        memo_callable = _create_function_wrapper(definition)

    _register_memo_definition(definition)
    return memo_callable


class _MemoDecorator(Protocol):
    """The decorator returned by ``rx.memo()`` called with no arguments."""

    @overload
    def __call__(self, fn: Callable[..., Component]) -> _MemoComponentWrapper: ...
    @overload
    def __call__(self, fn: Callable[..., Var[_MemoVarT]]) -> _MemoFunctionWrapper: ...


@overload
def memo(fn: Callable[..., Component]) -> _MemoComponentWrapper: ...
@overload
def memo(fn: Callable[..., Var[_MemoVarT]]) -> _MemoFunctionWrapper: ...
@overload
def memo() -> _MemoDecorator: ...
@overload
def memo(
    *, wrapper: Var | None
) -> Callable[[Callable[..., Component]], _MemoComponentWrapper]: ...
def memo(
    fn: Callable[..., Any] | None = None,
    *,
    wrapper: Var | None = DEFAULT_MEMO_WRAPPER,
) -> (
    _MemoComponentWrapper
    | _MemoFunctionWrapper
    | _MemoDecorator
    | Callable[[Callable[..., Component]], _MemoComponentWrapper]
):
    """Create a memo from a function.

    The decorated function's body is **not** executed here. Only signature-level
    analysis — return annotation, parameter kinds, name-collision registration,
    and the deprecation warning for missing annotations — runs at decoration
    time. The body is compiled lazily on first read of ``.component`` /
    ``.function`` — when the component wrapper is instantiated, or when the
    compiler reads the memo (see ``_LazyBody``). Deferring the body keeps
    ``@rx.memo`` free of import-time side effects, so a memo whose body
    references another module no longer forces that module to load during
    import — sidestepping circular-import ordering issues.

    Args:
        fn: The function to memoize. When omitted, returns a decorator that
            applies the given keyword arguments (``@rx.memo(wrapper=...)``).
        wrapper: The JS function the compiled function component is wrapped in.
            Defaults to React's ``memo``; pass another ``Var`` (typically an
            ``rx.vars.FunctionStringVar`` carrying its own imports) to swap the
            wrapper, or ``None`` to export the bare function component. Only
            supported on component-returning memos.

    Returns:
        The wrapped function or component factory, or — when ``fn`` is omitted
        — a decorator applying the keyword arguments.

    Raises:
        TypeError: If the return annotation is not supported, or a non-default
            ``wrapper`` is given for a var-returning memo.
    """
    if fn is None:
        return cast("_MemoDecorator", partial(_memo_impl, wrapper=wrapper))
    return _memo_impl(fn, wrapper)


__all__ = [
    "DEFAULT_MEMO_WRAPPER",
    "EMPTY_VAR_COMPONENT",
    "MEMOS",
    "MemoComponent",
    "MemoComponentDefinition",
    "MemoDefinition",
    "MemoFunctionDefinition",
    "create_component_memo",
    "create_passthrough_component_memo",
    "memo",
]
