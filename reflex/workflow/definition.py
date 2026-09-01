"""Compile a registered workflow class into an immutable definition.

The compiler validates the workflow authoring contract and produces the
versioned structure the kernel executes: stable handler identities, resolved
retry/timeout policies, the run-state field schema, and a content digest that
pins runs to the exact definition they were admitted under.
"""

from __future__ import annotations

import ast
import dataclasses
import hashlib
import inspect
import json
import textwrap
from typing import TYPE_CHECKING, Any, get_type_hints

from reflex_base.utils.exceptions import WorkflowDefinitionError
from reflex_base.workflow import (
    BUG_EXCEPTIONS,
    Debounce,
    DurableEventConfig,
    RateLimit,
    Retry,
    ScheduleTrigger,
    Signal,
    Singleton,
    Throttle,
    Trigger,
    WorkflowConfig,
    default_retry_for_effect,
    get_durable_config,
    parse_duration,
)

from reflex.workflow.cron import CronSchedule
from reflex.workflow.serde import to_run_data

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from reflex.state import BaseState

RESERVED_HANDLER_NAMES = frozenset(("setvar",))


@dataclasses.dataclass(frozen=True, slots=True)
class FieldSchema:
    """Schema of one run-scoped state field.

    Attributes:
        name: The field name.
        annotated_type: The declared annotation, used to coerce loaded values.
        default: The JSON-compatible default value.
    """

    name: str
    annotated_type: Any
    default: Any


@dataclasses.dataclass(frozen=True, slots=True)
class HandlerDefinition:
    """Compiled definition of one durable handler.

    Attributes:
        id: Stable handler identity.
        name: Python method name on the workflow class.
        fn: The undecorated handler function.
        effect: Declared effect class.
        trigger: Root trigger specification, or None for internal handlers.
        retry: Fully resolved retry policy.
        timeout: Per-attempt execution timeout in seconds, or None.
        queue: Resolved admission queue name, or None.
        on_failure: Handler id run after final failure, or None.
        on_timeout: Handler id run after final timeout, or None.
        singleton: At most one active run per key, if declared.
        rate_limit: Start-rate cap that drops the excess, if declared.
        throttle: Start-rate cap that delays the excess, if declared.
        debounce: Burst collapsing window, if declared.
        params: Payload parameter names, excluding ``self``.
        type_hints: Resolved type hints for payload coercion.
        is_async: Whether the handler is a coroutine function.
    """

    id: str
    name: str
    fn: Callable
    effect: str
    trigger: Trigger | None
    retry: Retry
    timeout: float | None
    queue: str | None
    on_failure: str | None
    on_timeout: str | None
    singleton: Singleton | None
    rate_limit: RateLimit | None
    throttle: Throttle | None
    debounce: Debounce | None
    params: tuple[str, ...]
    type_hints: Mapping[str, Any]
    is_async: bool


@dataclasses.dataclass(frozen=True, slots=True)
class WorkflowDefinition:
    """Immutable compiled definition of one workflow class.

    Attributes:
        workflow_id: Stable workflow identity from ``WorkflowConfig.id``.
        state_cls: The registered workflow-focused state class.
        config: The authoring configuration.
        digest: Content digest pinning runs to this exact definition.
        run_timeout: Whole-run deadline in seconds, or None.
        max_steps: Upper bound on scheduled steps per run.
        handlers: Handler definitions keyed by stable handler id.
        handler_ids_by_name: Map from Python method name to handler id.
        roots: Handler ids that declare a trigger and may start runs.
        fields: Run-state field schemas in declaration order.
        channels: Signal channels the class declares, keyed by channel name.
    """

    workflow_id: str
    state_cls: type[BaseState]
    config: WorkflowConfig
    digest: str
    run_timeout: float | None
    max_steps: int
    handlers: Mapping[str, HandlerDefinition]
    handler_ids_by_name: Mapping[str, str]
    roots: tuple[str, ...]
    fields: tuple[FieldSchema, ...]
    channels: Mapping[str, Signal]


def _error(workflow_cls: type, msg: str) -> WorkflowDefinitionError:
    """Build a definition error prefixed with the workflow class name.

    Args:
        workflow_cls: The class being compiled.
        msg: The error detail.

    Returns:
        The exception to raise.
    """
    return WorkflowDefinitionError(f"Workflow {workflow_cls.__name__}: {msg}")


def _validate_class_shape(workflow_cls: type[BaseState]) -> WorkflowConfig:
    """Validate the class-level workflow contract.

    Args:
        workflow_cls: The candidate workflow class.

    Returns:
        The class's workflow configuration.

    Raises:
        WorkflowDefinitionError: If the class violates the authoring contract.
    """
    from reflex.state import BaseState, ComponentState, State

    if not (isinstance(workflow_cls, type) and issubclass(workflow_cls, BaseState)):
        msg = f"add_workflow() expects an rx.State subclass, got {workflow_cls!r}."
        raise WorkflowDefinitionError(msg)
    config = workflow_cls.__dict__.get("__workflow__")
    if config is None:
        raise _error(
            workflow_cls,
            "missing __workflow__ = rx.WorkflowConfig(id=...) on the class body.",
        )
    if not isinstance(config, WorkflowConfig):
        raise _error(
            workflow_cls,
            f"__workflow__ must be an rx.WorkflowConfig, got {type(config).__name__}.",
        )
    if issubclass(workflow_cls, ComponentState):
        raise _error(workflow_cls, "ComponentState classes cannot be workflows.")
    if workflow_cls._mixin:
        raise _error(workflow_cls, "state mixins cannot be workflows.")
    if workflow_cls.get_parent_state() is not State:
        raise _error(
            workflow_cls,
            "workflow classes must subclass rx.State directly; nested substates "
            "are not supported.",
        )
    if workflow_cls.get_substates():
        names = ", ".join(sorted(s.__name__ for s in workflow_cls.get_substates()))
        raise _error(
            workflow_cls,
            f"workflow classes cannot have substates (found {names}).",
        )
    if config.allow_mixed_scopes:
        raise _error(
            workflow_cls,
            "mixed-scope workflow classes are not supported yet; move session "
            "fields and handlers to a separate unregistered rx.State class.",
        )
    own_backend_vars = [
        name
        for name in workflow_cls.backend_vars
        if name not in workflow_cls.inherited_backend_vars
    ]
    if own_backend_vars:
        raise _error(
            workflow_cls,
            "backend-only fields are unavailable to durable handlers; declare "
            f"ordinary typed fields instead of: {', '.join(sorted(own_backend_vars))}.",
        )
    return config


def _compile_fields(workflow_cls: type[BaseState]) -> tuple[FieldSchema, ...]:
    """Build and validate the run-state field schema.

    Args:
        workflow_cls: The workflow class.

    Returns:
        Field schemas in declaration order.

    Raises:
        WorkflowDefinitionError: If a field default is not serializable.
    """
    fields = []
    class_fields = workflow_cls.get_fields()
    for name in workflow_cls.base_vars:
        field = class_fields[name]
        default = field.default_value()
        try:
            default_json = to_run_data(default)
        except (TypeError, ValueError) as err:
            raise _error(
                workflow_cls,
                f"field {name!r} default is not serializable run data: {err}",
            ) from None
        fields.append(
            FieldSchema(
                name=name,
                annotated_type=field.annotated_type,
                default=default_json,
            )
        )
    return tuple(fields)


def _resolve_retry(retry: Retry | None, effect: str) -> Retry:
    """Materialize the effective retry policy for a handler.

    A policy that does not name retryable exception types retries on any
    ``Exception``, so ``Retry(max_attempts=5)`` means five attempts. Narrow it
    with ``do_not_retry_on`` to fail fast on specific errors. A
    ``non_idempotent_write`` never retries: the runtime cannot prove the
    external effect did not already land.

    Every policy also excludes ``BUG_EXCEPTIONS``, because a retry re-runs the
    handler against the same committed state: a ``TypeError`` fails the same
    way every attempt, so retrying one only delays the operator seeing it. A
    handler that genuinely wants one retried names it in ``retry_on``, and
    then it is left alone.

    Args:
        retry: The explicit policy, if the handler declared one.
        effect: The handler's effect class.

    Returns:
        The fully resolved policy.
    """
    if retry is None:
        retry = default_retry_for_effect(effect)
    if not retry.retry_on and effect != "non_idempotent_write":
        retry = dataclasses.replace(retry, retry_on=(Exception,))
    bugs = tuple(
        bug
        for bug in BUG_EXCEPTIONS
        if not any(issubclass(wanted, bug) for wanted in retry.retry_on)
        and not any(issubclass(bug, known) for known in retry.do_not_retry_on)
    )
    if not bugs:
        return retry
    return dataclasses.replace(retry, do_not_retry_on=retry.do_not_retry_on + bugs)


def _compile_handlers(
    workflow_cls: type[BaseState], config: WorkflowConfig
) -> dict[str, HandlerDefinition]:
    """Compile every public handler on the class into a handler definition.

    Args:
        workflow_cls: The workflow class.
        config: The class's workflow configuration.

    Returns:
        Handler definitions keyed by stable handler id.

    Raises:
        WorkflowDefinitionError: If a handler violates the durable contract.
    """
    from reflex.state import State

    handlers: dict[str, HandlerDefinition] = {}
    inherited = State.event_handlers
    for name, handler in workflow_cls.event_handlers.items():
        if name in RESERVED_HANDLER_NAMES or inherited.get(name) is handler:
            continue
        durable: DurableEventConfig | None = get_durable_config(handler.fn)
        if durable is None:
            raise _error(
                workflow_cls,
                f"handler {name!r} is not durable. Every public handler on a "
                "workflow class must declare @rx.event(durable=True, effect=...); "
                "move session handlers to a separate unregistered rx.State class.",
            )
        handler_id = durable.id or name
        if handler_id in handlers:
            raise _error(
                workflow_cls,
                f"duplicate handler id {handler_id!r} on {name!r} and "
                f"{handlers[handler_id].name!r}; stable ids must be unique.",
            )
        fn = handler.fn
        params = tuple(inspect.signature(fn).parameters)[1:]
        handlers[handler_id] = HandlerDefinition(
            id=handler_id,
            name=name,
            fn=fn,
            effect=durable.effect,
            trigger=durable.trigger,
            retry=_resolve_retry(durable.retry, durable.effect),
            timeout=durable.timeout,
            queue=durable.queue or config.default_queue,
            on_failure=durable.on_failure,
            on_timeout=durable.on_timeout,
            singleton=durable.singleton,
            rate_limit=durable.rate_limit,
            throttle=durable.throttle,
            debounce=durable.debounce,
            params=params,
            type_hints=get_type_hints(fn),
            is_async=inspect.iscoroutinefunction(fn),
        )
    return handlers


def _handler_body(fn: Callable) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    """Parse a handler's source into its function definition node.

    Args:
        fn: The undecorated handler function.

    Returns:
        The parsed node, or None when the source is unavailable (a handler
        built by exec or defined in a REPL).
    """
    try:
        source = textwrap.dedent(inspect.getsource(fn))
    except (OSError, TypeError):
        return None
    try:
        module = ast.parse(source)
    except SyntaxError:
        return None
    node = module.body[0] if module.body else None
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return node
    return None


def _validate_branches(
    workflow_cls: type[BaseState],
    defn: HandlerDefinition,
    handlers: Mapping[str, HandlerDefinition],
) -> None:
    """Reject fan-outs whose branches are handlers of this same workflow.

    A branch becomes a child run with its own fresh state, so naming a sibling
    handler produces a child that cannot see anything the parent has done --
    silently, and only at runtime. Fan out to another workflow class instead.

    Args:
        workflow_cls: The workflow class being compiled.
        defn: The handler to check.
        handlers: Every durable handler on this class.

    Raises:
        WorkflowDefinitionError: If a branch names a handler of this class.
    """
    node = _handler_body(defn.fn)
    if node is None:
        return
    for child in ast.walk(node):
        if not (
            isinstance(child, ast.Call)
            and isinstance(child.func, ast.Name)
            and child.func.id == "parallel"
        ) and not (
            isinstance(child, ast.Call)
            and isinstance(child.func, ast.Attribute)
            and child.func.attr == "parallel"
        ):
            continue
        for branch in child.args:
            target = branch.func if isinstance(branch, ast.Call) else branch
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == workflow_cls.__name__
                and target.attr in {h.name for h in handlers.values()}
            ):
                raise _error(
                    workflow_cls,
                    f"handler {defn.name!r} fans out to {target.attr!r} on its "
                    "own class. Each branch runs as a child run with fresh "
                    "state, so it would not see this run's state. Move the "
                    "branch to its own workflow class.",
                )


def _validate_flow_key(
    workflow_cls: type[BaseState], defn: HandlerDefinition, key: str
) -> None:
    """Check that a start policy's grouping key is resolvable and unambiguous.

    A key may name a parameter, or a field inside a parameter typed as a
    model -- the common case for webhook roots, whose whole payload is one
    typed argument. Two parameters exposing the same field would make the
    grouping silently depend on iteration order, so that is rejected here
    rather than discovered in production.

    Args:
        workflow_cls: The workflow class being compiled.
        defn: The root handler declaring the policy.
        key: The declared grouping key.

    Raises:
        WorkflowDefinitionError: If the key resolves to nothing, or to more
            than one place.
    """
    if key in defn.params:
        return
    sources = []
    for param in defn.params:
        hint = defn.type_hints.get(param)
        fields = getattr(hint, "model_fields", None)
        if fields is not None and key in fields:
            sources.append(f"{param}.{key}")
    if len(sources) == 1:
        return
    if not sources:
        raise _error(
            workflow_cls,
            f"handler {defn.name!r} groups runs by {key!r}, which is neither a "
            f"parameter ({', '.join(defn.params) or 'none'}) nor a field of a "
            "model parameter.",
        )
    raise _error(
        workflow_cls,
        f"handler {defn.name!r} groups runs by {key!r}, which is ambiguous: "
        f"{' and '.join(sources)} both carry it. Rename one field, or key on "
        "a parameter directly.",
    )


def _validate_handler_body(
    workflow_cls: type[BaseState],
    defn: HandlerDefinition,
    durable_names: frozenset[str],
) -> None:
    """Reject handler bodies that silently break the durability boundary.

    Args:
        workflow_cls: The workflow class being compiled.
        defn: The handler definition to check.
        durable_names: Method names of every durable handler on the class.

    Raises:
        WorkflowDefinitionError: If the body calls another durable handler
            directly, or returns a value that is not a durable transition.
    """
    node = _handler_body(defn.fn)
    if node is None:
        return
    self_name = next(iter(inspect.signature(defn.fn).parameters), None)

    def durable_self_reference(value: ast.expr) -> str | None:
        """Name the durable handler an expression reaches through ``self``.

        Args:
            value: The expression to inspect.

        Returns:
            The handler name, or None if this is not such a reference.
        """
        if (
            isinstance(value, ast.Attribute)
            and isinstance(value.value, ast.Name)
            and value.value.id == self_name
            and value.attr in durable_names
        ):
            return value.attr
        return None

    called: set[int] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Call) and durable_self_reference(child.func):
            called.add(id(child.func))
    for child in ast.walk(node):
        if isinstance(child, ast.Call) and (name := durable_self_reference(child.func)):
            raise _error(
                workflow_cls,
                f"handler {defn.name!r} calls {name!r} directly, which "
                "runs it inline and loses its retries, timeout, and effect "
                f"tracking. Return it as a transition instead: "
                f"return {workflow_cls.__name__}.{name}(...)",
            )
        if (
            isinstance(child, ast.Attribute)
            and id(child) not in called
            and (name := durable_self_reference(child))
        ):
            raise _error(
                workflow_cls,
                f"handler {defn.name!r} refers to {name!r} as self.{name}, which "
                "is a bound method, not a transition the engine can route. "
                f"Name the class instead: {workflow_cls.__name__}.{name}",
            )
        if (
            isinstance(child, ast.Return)
            and isinstance(child.value, ast.Constant)
            and child.value.value is not None
        ):
            raise _error(
                workflow_cls,
                f"handler {defn.name!r} returns {child.value.value!r}. A durable "
                "handler returns the next transition, not a value: return the "
                "next handler, rx.after(...), rx.complete(result=...), "
                "rx.fail(...), rx.needs_attention(...), or None.",
            )


def _resolve_hooks(
    workflow_cls: type[BaseState], handlers: dict[str, HandlerDefinition]
) -> dict[str, HandlerDefinition]:
    """Resolve lifecycle hook names to stable handler ids.

    Args:
        workflow_cls: The workflow class.
        handlers: Compiled handler definitions keyed by id.

    Returns:
        Handler definitions with hooks rewritten to handler ids.

    Raises:
        WorkflowDefinitionError: If a hook does not resolve to another durable
            handler on the same class.
    """
    ids_by_name = {defn.name: defn.id for defn in handlers.values()}
    resolved = {}
    for handler_id, defn in handlers.items():
        hook_ids = {}
        for param in ("on_failure", "on_timeout"):
            hook_name = getattr(defn, param)
            if hook_name is None:
                hook_ids[param] = None
                continue
            hook_id = ids_by_name.get(
                hook_name, hook_name if hook_name in handlers else None
            )
            if hook_id is None:
                raise _error(
                    workflow_cls,
                    f"handler {defn.name!r} {param}={hook_name!r} does not match "
                    "a durable handler on the same class.",
                )
            if hook_id == handler_id:
                raise _error(
                    workflow_cls,
                    f"handler {defn.name!r} cannot use itself as {param}.",
                )
            if handlers[hook_id].params:
                raise _error(
                    workflow_cls,
                    f"{param} handler {handlers[hook_id].name!r} cannot take "
                    "payload arguments; it reads context from run state.",
                )
            hook_ids[param] = hook_id
        resolved[handler_id] = dataclasses.replace(defn, **hook_ids)
    return resolved


def _canonical_retry(retry: Retry) -> dict[str, Any]:
    """Canonicalize a retry policy for the definition digest.

    Args:
        retry: The resolved policy.

    Returns:
        A JSON-compatible representation.
    """
    return {
        "max_attempts": retry.max_attempts,
        "initial_delay": parse_duration(retry.initial_delay),
        "max_delay": parse_duration(retry.max_delay),
        "multiplier": retry.multiplier,
        "jitter": retry.jitter,
        "retry_on": sorted(exc.__qualname__ for exc in retry.retry_on),
        "do_not_retry_on": sorted(exc.__qualname__ for exc in retry.do_not_retry_on),
    }


def _canonical_trigger(trigger: Trigger | None) -> dict[str, Any] | None:
    """Canonicalize a trigger for the definition digest.

    Args:
        trigger: The trigger specification, if any.

    Returns:
        A JSON-compatible representation, or None.
    """
    if trigger is None:
        return None
    canonical: dict[str, Any] = {"kind": trigger.kind}
    for attr in ("topic", "cron", "dedupe_by"):
        value = getattr(trigger, attr, None)
        if value is not None:
            canonical[attr] = value
    model = getattr(trigger, "model", None)
    if model is not None:
        canonical["model"] = model.__qualname__
    return canonical


def _compute_digest(
    config: WorkflowConfig,
    handlers: Mapping[str, HandlerDefinition],
    fields: tuple[FieldSchema, ...],
) -> str:
    """Compute the content digest of a compiled definition.

    Args:
        config: The workflow configuration.
        handlers: Compiled handler definitions.
        fields: The run-state field schema.

    Returns:
        A hex sha256 digest over the canonical definition structure.
    """
    canonical = {
        "workflow_id": config.id,
        "run_timeout": (
            parse_duration(config.run_timeout)
            if config.run_timeout is not None
            else None
        ),
        "max_steps": config.max_steps,
        "default_queue": config.default_queue,
        "handlers": [
            {
                "id": defn.id,
                "effect": defn.effect,
                "trigger": _canonical_trigger(defn.trigger),
                "retry": _canonical_retry(defn.retry),
                "timeout": defn.timeout,
                "queue": defn.queue,
                "on_failure": defn.on_failure,
                "on_timeout": defn.on_timeout,
                "params": list(defn.params),
            }
            for defn in sorted(handlers.values(), key=lambda d: d.id)
        ],
        "fields": [
            {"name": f.name, "type": str(f.annotated_type), "default": f.default}
            for f in fields
        ],
    }
    payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def channels_of(state_cls: type) -> dict[str, Signal]:
    """Collect the signal channels a workflow class declares.

    Args:
        state_cls: The workflow class.

    Returns:
        Declared channels keyed by channel name.

    Raises:
        WorkflowDefinitionError: If two declarations share one channel name.
    """
    channels: dict[str, Signal] = {}
    for klass in reversed(state_cls.__mro__):
        for value in vars(klass).values():
            if not isinstance(value, Signal):
                continue
            existing = channels.get(value.name)
            if existing is not None and existing is not value:
                msg = (
                    f"Workflow {state_cls.__name__}: two rx.Signal declarations "
                    f"share the channel name {value.name!r}; a delivery could "
                    "not say which one it means."
                )
                raise WorkflowDefinitionError(msg)
            channels[value.name] = value
    return channels


def discover_workflows(module: Any) -> list[type]:
    """Find the workflow classes a module defines.

    A workflow is an ``rx.State`` subclass declaring ``__workflow__`` on its
    own class body; inherited declarations are not re-registered.

    Args:
        module: The imported module.

    Returns:
        The workflow classes, in definition order.
    """
    return [
        value
        for value in vars(module).values()
        if isinstance(value, type) and "__workflow__" in vars(value)
    ]


def unbound_params(handler: HandlerDefinition, supplied: set[str]) -> set[str]:
    """Parameters a handler requires that a recorded payload cannot fill.

    A parameter with a default binds without help, and ``*args``/``**kwargs``
    absorb anything, so only names that must be passed and are not present
    count. This is what makes "the code changed under an in-flight run" a
    compatibility decision rather than a TypeError from inside the handler.

    Args:
        handler: The current definition of the handler.
        supplied: Payload argument names the step recorded.

    Returns:
        The required parameter names that nothing would bind.
    """
    signature = inspect.signature(handler.fn)
    required: set[str] = set()
    for index, (name, param) in enumerate(signature.parameters.items()):
        if index == 0 or param.default is not inspect.Parameter.empty:
            continue
        if param.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            continue
        required.add(name)
    return required - supplied


def compile_workflow(workflow_cls: type[BaseState]) -> WorkflowDefinition:
    """Compile a workflow class into an immutable definition.

    Args:
        workflow_cls: A workflow-focused ``rx.State`` subclass with a
            ``__workflow__`` configuration.

    Returns:
        The compiled definition.

    Raises:
        WorkflowDefinitionError: If the class violates the authoring contract.
    """
    config = _validate_class_shape(workflow_cls)
    fields = _compile_fields(workflow_cls)
    handlers = _resolve_hooks(workflow_cls, _compile_handlers(workflow_cls, config))
    for defn in handlers.values():
        _validate_branches(workflow_cls, defn, handlers)
        policy = defn.singleton or defn.rate_limit or defn.throttle or defn.debounce
        key = getattr(policy, "key", None)
        if key is not None:
            _validate_flow_key(workflow_cls, defn, key)
        if isinstance(defn.trigger, ScheduleTrigger):
            CronSchedule(defn.trigger.cron)
    durable_names = frozenset(defn.name for defn in handlers.values())
    for defn in handlers.values():
        _validate_handler_body(workflow_cls, defn, durable_names)
    for defn in handlers.values():
        if isinstance(defn.trigger, ScheduleTrigger):
            unfillable = sorted(unbound_params(defn, set()))
            if unfillable:
                # A schedule fires with no caller to supply arguments, so a
                # required parameter here means every occurrence would admit
                # and immediately suspend. That is an authoring error, and
                # authoring errors surface at compile, not at 2am.
                raise _error(
                    workflow_cls,
                    f"schedule root {defn.name!r} requires parameters "
                    f"{unfillable}, which a schedule occurrence cannot "
                    "supply; give them defaults.",
                )
    roots = tuple(
        defn.id
        for defn in sorted(handlers.values(), key=lambda d: d.id)
        if defn.trigger is not None
    )
    if not roots:
        raise _error(
            workflow_cls,
            "no root handler declares a trigger; add trigger=rx.manual() (or "
            "rx.webhook/rx.schedule) to at least one durable handler.",
        )
    return WorkflowDefinition(
        workflow_id=config.id,
        state_cls=workflow_cls,
        config=config,
        digest=_compute_digest(config, handlers, fields),
        run_timeout=(
            parse_duration(config.run_timeout)
            if config.run_timeout is not None
            else None
        ),
        max_steps=config.max_steps,
        handlers=handlers,
        handler_ids_by_name={defn.name: defn.id for defn in handlers.values()},
        roots=roots,
        fields=fields,
        channels=channels_of(workflow_cls),
    )
