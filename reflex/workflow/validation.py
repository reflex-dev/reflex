"""One validation semantics for every boundary that accepts run data.

Python starts, HTTP starts, webhooks, signal deliveries, and worker dispatch
all answer the same two questions -- are these the arguments the handler
declares, and do the values fit its types -- and they used to answer them
in different places with different strictness. A payload one boundary
admitted could then suspend at dispatch, or worse, run wrong. Every boundary
now asks this module, so "does this payload fit" has exactly one answer.

The rule for where errors land: a boundary refuses *before* anything is
written, so an invalid payload creates nothing; dispatch -- which judges
payloads recorded before a redeploy changed the code -- suspends the run for
an operator instead, and never consumes retry attempts, because retrying
cannot change what the code declares.
"""

from __future__ import annotations

import functools
import importlib.util
from typing import TYPE_CHECKING, Any, Final

from reflex_base.utils.exceptions import WorkflowRuntimeError

from reflex.workflow.definition import channels_of, unbound_params

if TYPE_CHECKING:
    from reflex.workflow.definition import HandlerDefinition

__all__ = [
    "canonical_payload",
    "channels_of",
    "missing_args",
    "mistyped_args",
    "require_pydantic",
]

WORKFLOWS_EXTRA: Final = 'pip install "reflex[workflows]"'


def require_pydantic() -> None:
    """Refuse to run workflows without the validation library they rest on.

    pydantic is an optional extra of Reflex, and the workflow engine validates
    every payload with it -- degrading to "no validation" when it is absent
    would silently void the contract's boundary rules. Failing here, once,
    with the install line beats a ``ModuleNotFoundError`` from inside the
    first admission.

    Raises:
        WorkflowRuntimeError: If pydantic is not importable.
    """
    if importlib.util.find_spec("pydantic") is None:
        msg = (
            "Reflex Workflows need pydantic, which Reflex does not install by "
            f"default: {WORKFLOWS_EXTRA}"
        )
        raise WorkflowRuntimeError(msg)


@functools.lru_cache(maxsize=1024)
def _adapter(hint: Any):
    """Build (once) the pydantic adapter for a type hint.

    Args:
        hint: The handler parameter's declared type.

    Returns:
        The cached ``TypeAdapter``, or None for a hint pydantic cannot adapt.
    """
    from pydantic import TypeAdapter

    try:
        return TypeAdapter(hint)
    except Exception:
        # An exotic hint is the author's business, never the caller's fault.
        return None


def mistyped_args(handler: HandlerDefinition, args: dict[str, Any]) -> list[str]:
    """Check supplied arguments against the handler's declared types.

    Args:
        handler: The resolved handler definition.
        args: The caller-supplied arguments.

    Returns:
        One message per argument that cannot validate, empty when all fit.
    """
    from pydantic import ValidationError

    problems: list[str] = []
    for name, value in args.items():
        if name.startswith("__"):
            continue
        hint = handler.type_hints.get(name)
        try:
            adapter = _adapter(hint) if hint is not None else None
        except TypeError:
            # An unhashable hint (Annotated with dict metadata, say) cannot be
            # cached and is the author's business; it does not fail callers.
            adapter = None
        if adapter is None:
            continue
        try:
            adapter.validate_python(value)
        except ValidationError:
            problems.append(
                f"{name!r} does not validate as {getattr(hint, '__name__', hint)}"
            )
        except Exception:
            pass
    return problems


def missing_args(handler: HandlerDefinition, args: dict[str, Any]) -> list[str]:
    """Required parameters the supplied arguments leave unbound.

    Args:
        handler: The resolved handler definition.
        args: The caller-supplied arguments.

    Returns:
        The unbound required parameter names, sorted.
    """
    return sorted(unbound_params(handler, set(args)))


def canonical_payload(model: type, payload: Any) -> Any:
    """Validate a payload against a model and return its canonical form.

    Validating and then passing the *raw* payload onward throws the
    validation away: coercions, defaults, and alias resolution never happen,
    so the handler receives something subtly different from what the model
    promised. The canonical form is the validated object dumped back to
    JSON-compatible data -- what the model says the payload *is*.

    Args:
        model: The declared payload model.
        payload: The decoded payload to validate.

    Returns:
        The validated payload in JSON-canonical form.

    Raises:
        pydantic.ValidationError: If the payload does not satisfy the model.
    """
    from pydantic import TypeAdapter

    adapter = TypeAdapter(model)
    validated = adapter.validate_python(payload)
    return adapter.dump_python(validated, mode="json")
