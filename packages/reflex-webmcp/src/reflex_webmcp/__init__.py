"""Reflex plugin that exposes bound backend events through the WebMCP API."""

from __future__ import annotations

import dataclasses
import datetime
import hashlib
import inspect
import json
import logging
import pathlib
import types
import uuid
from collections.abc import Mapping, Sequence
from enum import Enum
from functools import partial
from typing import TYPE_CHECKING, Annotated, Any, Literal, Union, get_args, get_origin

from reflex_base.components.component import BaseComponent, Component
from reflex_base.components.memoize_helpers import (
    MemoizationStrategy,
    get_memoization_strategy,
)
from reflex_base.constants.compiler import Imports
from reflex_base.constants.event import EventTriggers
from reflex_base.event import EventChain, EventHandler, EventSpec
from reflex_base.plugins.base import HookOrder
from reflex_base.plugins.base import Plugin as PluginBase
from reflex_base.utils.format import format_event_handler
from reflex_base.vars.base import LiteralVar
from typing_extensions import is_typeddict

if TYPE_CHECKING:
    from reflex_base.plugins.compiler import CompileContext, PageContext

logger = logging.getLogger(__name__)

_REGISTRATION_MARKER = "// Reflex WebMCP event:"
_LIFECYCLE_TRIGGERS = {
    EventTriggers.ON_MOUNT,
    EventTriggers.ON_UNMOUNT,
}
_ARRAY_ORIGINS = {list, set, frozenset, Sequence}
_MAPPING_ORIGINS = {dict, Mapping}


def _json(value: Any) -> str:
    """Serialize a value as compact JavaScript-compatible JSON.

    Args:
        value: Value to serialize.

    Returns:
        Compact JSON source.
    """
    return json.dumps(
        value,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _tool_name(state_name: str, handler: EventHandler) -> str:
    """Build a short ASCII tool name from the state class and handler function.

    Args:
        state_name: Name of the state class owning the handler.
        handler: Backend event handler.

    Returns:
        A WebMCP tool name of the form ``reflex_<StateClass>_<handler>``.
    """
    fn = handler.fn.func if isinstance(handler.fn, partial) else handler.fn
    parts: list[str] = ["reflex_"]
    for byte in f"{state_name}_{fn.__name__}".encode():
        character = chr(byte)
        if character.isascii() and (character.isalnum() or character in "_-"):
            parts.append(character)
        else:
            parts.append(f"_{byte:02x}_")
    return "".join(parts)


def _literal_schema(values: tuple[Any, ...]) -> dict[str, Any]:
    """Build a JSON Schema for a ``Literal`` annotation.

    Args:
        values: Literal values accepted by the annotation.

    Returns:
        A JSON Schema containing the literal enumeration.
    """
    schema: dict[str, Any] = {"enum": list(values)}
    value_types = {type(value) for value in values}
    if len(value_types) == 1:
        schema.update(_annotation_schema(next(iter(value_types))))
    return schema


def _object_schema(annotation: type[Any]) -> dict[str, Any]:
    """Build an object schema for a dataclass or typed dictionary.

    Args:
        annotation: Structured Python type.

    Returns:
        Object JSON Schema derived from annotated fields.
    """
    try:
        annotations = inspect.get_annotations(annotation, eval_str=True)
    except (NameError, TypeError):
        return {}
    properties = {
        name: _annotation_schema(field_type) for name, field_type in annotations.items()
    }
    required: list[str]
    if is_typeddict(annotation):
        required = sorted(annotation.__required_keys__)
    else:
        defaults = {
            field.name
            for field in dataclasses.fields(annotation)
            if field.default is not dataclasses.MISSING
            or field.default_factory is not dataclasses.MISSING
        }
        required = [name for name in properties if name not in defaults]
    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
    }
    if required:
        schema["required"] = required
    return schema


def _annotation_schema(annotation: Any) -> dict[str, Any]:
    """Convert a Python event-argument annotation to a JSON Schema fragment.

    Args:
        annotation: Resolved Python annotation.

    Returns:
        The best lossless JSON Schema fragment supported without optional
        dependencies, or an empty fragment for unconstrained values.
    """
    if (
        annotation is Any
        or annotation is inspect.Parameter.empty
        or annotation is object
    ):
        return {}
    if supertype := getattr(annotation, "__supertype__", None):
        return _annotation_schema(supertype)

    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin is Annotated:
        return _annotation_schema(args[0])
    if origin in {Union, types.UnionType}:
        return {"anyOf": [_annotation_schema(arg) for arg in args]}
    if origin is Literal:
        return _literal_schema(args)
    if origin in _ARRAY_ORIGINS:
        return {
            "type": "array",
            "items": _annotation_schema(args[0]) if args else {},
        }
    if origin is tuple:
        if len(args) == 2 and args[1] is Ellipsis:
            return {"type": "array", "items": _annotation_schema(args[0])}
        return {
            "type": "array",
            "prefixItems": [_annotation_schema(arg) for arg in args],
            "minItems": len(args),
            "maxItems": len(args),
        }
    if origin in _MAPPING_ORIGINS:
        return {
            "type": "object",
            "additionalProperties": _annotation_schema(args[1]) if args else {},
        }

    if annotation is str:
        return {"type": "string"}
    if annotation is bool:
        return {"type": "boolean"}
    if annotation is int:
        return {"type": "integer"}
    if annotation is float:
        return {"type": "number"}
    if annotation is None or annotation is type(None):
        return {"type": "null"}
    if annotation in _MAPPING_ORIGINS:
        return {"type": "object"}
    if annotation is tuple or annotation in _ARRAY_ORIGINS:
        return {"type": "array"}
    if annotation is datetime.datetime:
        return {"type": "string", "format": "date-time"}
    if annotation in (datetime.date, datetime.time):
        return {"type": "string", "format": annotation.__name__}
    if annotation is uuid.UUID:
        return {"type": "string", "format": "uuid"}
    if inspect.isclass(annotation) and issubclass(annotation, pathlib.PurePath):
        return {"type": "string"}
    if inspect.isclass(annotation) and issubclass(annotation, Enum):
        return _literal_schema(tuple(member.value for member in annotation))
    if inspect.isclass(annotation) and (
        dataclasses.is_dataclass(annotation) or is_typeddict(annotation)
    ):
        return _object_schema(annotation)
    return {}


def _handler_schema(handler: EventHandler, event_name: str) -> dict[str, Any] | None:
    """Build the object payload schema accepted by a Reflex event handler.

    Args:
        handler: Backend event handler.
        event_name: Qualified name used in diagnostics.

    Returns:
        An object JSON Schema, or ``None`` when the handler cannot be represented.
    """
    parameters = list(handler.get_parameters().values())
    if handler.state is not None and parameters:
        parameters = parameters[1:]
    unsupported_parameter = next(
        (
            parameter
            for parameter in parameters
            if parameter.kind
            in {
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            }
        ),
        None,
    )
    if unsupported_parameter is not None:
        logger.warning(
            "Cannot expose Reflex event %s with non-keyword parameter %r as a WebMCP tool.",
            event_name,
            unsupported_parameter.name,
        )
        return None

    type_hints = handler._get_type_hints()
    properties: dict[str, Any] = {}
    required: list[str] = []
    for parameter in parameters:
        schema = _annotation_schema(
            type_hints.get(parameter.name, parameter.annotation)
        )
        if parameter.default is inspect.Parameter.empty:
            required.append(parameter.name)
        else:
            try:
                _json(parameter.default)
            except (TypeError, ValueError):
                pass
            else:
                schema["default"] = parameter.default
        properties[parameter.name] = schema

    result: dict[str, Any] = {
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
    }
    if required:
        result["required"] = required
    return result


def _handler_description(handler: EventHandler, event_name: str) -> str:
    """Get an agent-facing description from a Reflex handler.

    Args:
        handler: Backend event handler.
        event_name: Qualified fallback name.

    Returns:
        The handler's docstring summary or a generated fallback.
    """
    fn = handler.fn.func if isinstance(handler.fn, partial) else handler.fn
    doc = inspect.getdoc(fn)
    return doc.splitlines()[0] if doc else f"Invoke the Reflex event {event_name}."


def _fixed_payload(event_spec: EventSpec) -> dict[str, Any]:
    """Extract compile-time literal arguments already bound to an EventSpec.

    Args:
        event_spec: Existing component-bound event specification.

    Returns:
        JSON-compatible payload values that the generated tool must preserve.
    """
    payload: dict[str, Any] = {}
    for name, value in event_spec.args:
        if not isinstance(value, LiteralVar) or value._get_all_var_data() is not None:
            continue
        try:
            decoded = value._decode()
            _json(decoded)
        except (TypeError, ValueError):
            continue
        payload[name._js_expr] = decoded
    return payload


def _specialize_schema(
    schema: dict[str, Any], fixed_payload: Mapping[str, Any]
) -> dict[str, Any]:
    """Remove tool inputs already fixed by the component's EventSpec.

    Args:
        schema: Full backend handler payload schema.
        fixed_payload: Compile-time arguments already bound to the event.

    Returns:
        Input schema for only the values an agent still controls.
    """
    properties = {
        name: value
        for name, value in schema["properties"].items()
        if name not in fixed_payload
    }
    result = {
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
    }
    required = [
        name for name in schema.get("required", ()) if name not in fixed_payload
    ]
    if required:
        result["required"] = required
    return result


def _compile_registration(event_spec: EventSpec) -> str | None:
    """Compile one backend EventSpec into an automatic WebMCP registration.

    Args:
        event_spec: Existing component-bound Reflex event specification.

    Returns:
        JavaScript registration source, or ``None`` for unsupported events.
    """
    if event_spec.client_handler_name:
        return None
    handler = event_spec.handler
    state = handler.state
    if state is None:
        return None
    event_name = format_event_handler(handler)
    if event_name.startswith("_"):
        return None
    handler_schema = _handler_schema(handler, event_name)
    if handler_schema is None:
        return None

    fixed_payload = _fixed_payload(event_spec)
    input_schema = _specialize_schema(handler_schema, fixed_payload)
    generated_name = _tool_name(state.__name__, handler)
    event_actions = event_spec.event_actions
    if fixed_payload or event_actions:
        identity = {"payload": fixed_payload, "event_actions": event_actions}
        digest = hashlib.sha256(_json(identity).encode()).hexdigest()[:8]
        generated_name = f"{generated_name}_{digest}"
    name = _json(generated_name)
    qualified_name = _json(event_name)
    description_text = _handler_description(handler, event_name)
    if fixed_payload:
        description_text += f" Bound inputs: {_json(fixed_payload)}."
    description = _json(description_text)
    schema = _json(input_schema)
    fixed = _json(fixed_payload)
    actions = _json(event_actions)
    return f"""{_REGISTRATION_MARKER} {event_name}
if (
  typeof document !== \"undefined\" &&
  typeof document.modelContext?.registerTool === \"function\"
) {{
  globalThis[Symbol.for(\"reflex.webmcp.registeredTools\")] ??= new Set();
  if (!globalThis[Symbol.for(\"reflex.webmcp.registeredTools\")].has({name})) {{
    globalThis[Symbol.for(\"reflex.webmcp.registeredTools\")].add({name});
    try {{
      await document.modelContext.registerTool({{
        name: {name},
        description: {description},
        inputSchema: {schema},
        annotations: {{ readOnlyHint: false }},
        execute: async (input) => {{
          const payload = {{ ...input, ...{fixed} }};
          addEvents([ReflexEvent({qualified_name}, payload, {actions})], [], {{}});
          return {{ queued: true, event: {qualified_name}, payload }};
        }},
      }});
    }} catch (error) {{
      globalThis[Symbol.for(\"reflex.webmcp.registeredTools\")].delete({name});
      console.warn(\"Failed to register Reflex WebMCP event:\", {qualified_name}, error);
    }}
  }}
}}"""


@dataclasses.dataclass(frozen=True, slots=True)
class WebMCPPlugin(PluginBase):
    """Automatically expose backend events bound to compiled components.

    Every inspectable backend ``EventSpec`` already used by a page becomes a
    WebMCP tool. Tool metadata comes from the handler name, docstring, Python
    annotations, and defaults. Invocations enqueue the same ``ReflexEvent`` via
    ``addEvents`` that the normal UI trigger uses.
    """

    _compiler_enter_component_order = HookOrder.PRE
    _compiler_can_replace_enter_component = False

    def enter_component(
        self,
        comp: BaseComponent,
        /,
        *,
        page_context: PageContext,
        compile_context: CompileContext,
        in_prop_tree: bool = False,
    ) -> None:
        """Collect backend EventSpecs before memoization rewrites triggers.

        Args:
            comp: Component whose bound triggers are being inspected.
            page_context: Page receiving generated registrations.
            compile_context: Active app compilation context.
            in_prop_tree: Whether the component appears in a prop subtree.
        """
        del compile_context, in_prop_tree
        if not isinstance(comp, Component):
            return
        self._collect(comp, page_context)
        # Snapshot-memoized subtrees (``Foreach`` bodies, MemoizationLeaf-style
        # components) are sealed by the memoize pass, so the walker never
        # descends into them. Visit them here; ``module_code`` deduplicates
        # anything the walker also reaches.
        if get_memoization_strategy(comp) is MemoizationStrategy.SNAPSHOT:
            stack = list(self._descendants(comp))
            while stack:
                child = stack.pop()
                if isinstance(child, Component):
                    self._collect(child, page_context)
                    stack.extend(self._descendants(child))

    @staticmethod
    def _descendants(comp: Component) -> list[BaseComponent]:
        """List direct children and prop-embedded components of a component.

        Args:
            comp: Parent component.

        Returns:
            Components one level below ``comp``.
        """
        return [*comp.children, *comp._get_components_in_props()]

    @staticmethod
    def _collect(comp: Component, page_context: PageContext) -> None:
        """Register tools for the backend EventSpecs bound to one component.

        Args:
            comp: Component whose bound triggers are being inspected.
            page_context: Page receiving generated registrations.
        """
        for trigger_name, event in comp.event_triggers.items():
            if trigger_name in _LIFECYCLE_TRIGGERS or not isinstance(event, EventChain):
                continue
            for chain_event in event.events:
                if not isinstance(chain_event, EventSpec):
                    continue
                try:
                    registration = _compile_registration(chain_event)
                except (NameError, TypeError, ValueError, RecursionError) as err:
                    logger.warning(
                        "Cannot expose Reflex event %s as a WebMCP tool: %s",
                        format_event_handler(chain_event.handler),
                        err,
                    )
                    continue
                if registration:
                    page_context.module_code[registration] = None

    def compile_page(self, page_ctx: PageContext, /, **kwargs: Any) -> None:
        """Add Reflex event runtime imports when tools were discovered.

        Args:
            page_ctx: Compiled page context.
            kwargs: Additional compiler-specific context.
        """
        del kwargs
        if any(code.startswith(_REGISTRATION_MARKER) for code in page_ctx.module_code):
            page_ctx.imports.append(Imports.EVENTS)


Plugin = WebMCPPlugin


__all__ = ["Plugin", "WebMCPPlugin"]
