"""Tests for sharing prepared event wrappers within a registration context."""

import dataclasses

import pytest
from reflex_base.components.component import Component
from reflex_base.components.memoize_helpers import get_memoized_event_triggers
from reflex_base.event import EventChain, EventHandler, no_args_event_spec
from reflex_base.registry import RegistrationContext
from reflex_base.utils.imports import ImportVar
from reflex_base.vars.base import LiteralVar, Var, VarData


def test_event_wrappers_are_reused_and_reset_with_context():
    """Identical wrappers share work only within their owning context."""
    component = Component._create(
        children=(), event_triggers={"on_click": Var("handler", EventChain)}
    )
    with RegistrationContext.ensure_context().fork() as context:
        first = get_memoized_event_triggers(component)["on_click"]
        assert get_memoized_event_triggers(component)["on_click"] is first
        with context.fork() as fork:
            assert not fork._memoized_event_triggers
            assert get_memoized_event_triggers(component)["on_click"] is not first
        context._memoized_event_triggers.clear()
        assert get_memoized_event_triggers(component)["on_click"] is not first


@pytest.mark.parametrize(
    ("first_data", "second_data"),
    [
        (VarData(state="first"), VarData(state="second")),
        (
            VarData(hooks=["const first = useFirst()"]),
            VarData(hooks=["const second = useSecond()"]),
        ),
        (
            VarData(imports={"first": [ImportVar("value")]}),
            VarData(imports={"second": [ImportVar("value")]}),
        ),
        (VarData(deps=[Var("first")]), VarData(deps=[Var("second")])),
    ],
)
def test_event_wrapper_cache_preserves_dependencies(
    first_data: VarData, second_data: VarData
):
    """Identical expressions with different metadata must keep their dependencies."""
    with RegistrationContext.ensure_context().fork():
        first = get_memoized_event_triggers(
            Component._create(
                children=(),
                event_triggers={"on_click": Var("handler", EventChain, first_data)},
            )
        )["on_click"]
        second = get_memoized_event_triggers(
            Component._create(
                children=(),
                event_triggers={"on_click": Var("handler", EventChain, second_data)},
            )
        )["on_click"]
        assert first is not second
        assert repr(first._get_all_var_data()) != repr(second._get_all_var_data())


def test_event_wrapper_cache_preserves_provider_identity():
    """Providers sharing a role can still carry distinct component props."""
    first_provider = Component._create(
        children=(), tag="Provider", custom_attrs={"value": "first"}
    )
    second_provider = Component._create(
        children=(), tag="Provider", custom_attrs={"value": "second"}
    )
    with RegistrationContext.ensure_context().fork():
        for provider in (first_provider, second_provider):
            event = Var("handler", EventChain, VarData(app_wraps=[(10, provider)]))
            wrapper = get_memoized_event_triggers(
                Component._create(children=(), event_triggers={"on_click": event})
            )["on_click"]
            data = wrapper._get_all_var_data()
            assert data is not None
            assert data.app_wraps[0][1] is provider


def test_event_wrapper_cache_does_not_compare_vars_as_python_booleans():
    """Equivalent dependency expressions may belong to different Var objects."""
    with RegistrationContext.ensure_context().fork():
        for _ in range(2):
            event = Var("handler", EventChain, VarData(deps=[Var("dependency")]))
            wrapper = get_memoized_event_triggers(
                Component._create(children=(), event_triggers={"on_click": event})
            )["on_click"]
            data = wrapper._get_all_var_data()
            assert data is not None
            assert {str(dep) for dep in data.deps} == {"dependency"}


def test_event_wrapper_reflects_captured_arguments_and_actions():
    """Chains differing in nested data compile to different wrappers."""

    def handler(value: str):
        """Accept an event argument."""

    def chain(argument: str, **actions: bool) -> EventChain:
        """Build a chain for one handler call.

        Args:
            argument: The captured handler argument.
            **actions: Event actions applied to the nested event.

        Returns:
            The chain wrapping the handler call.
        """
        spec = EventHandler(fn=handler)(argument)
        if actions:
            spec = dataclasses.replace(spec, event_actions=actions)
        return EventChain(events=[spec], args_spec=no_args_event_spec)

    component = Component._create(children=(), event_triggers={})
    with RegistrationContext.ensure_context().fork():
        rendered = []
        for event in (
            chain("first"),
            dataclasses.replace(chain("first"), event_actions={"preventDefault": True}),
            chain("first", stopPropagation=True),
            chain("second"),
        ):
            component.event_triggers["on_click"] = event
            rendered.append(str(get_memoized_event_triggers(component)["on_click"]))
        assert len(set(rendered)) == len(rendered)


def test_event_wrappers_are_shared_by_chain_identity(monkeypatch):
    """Components bound to one chain object share one wrapper without rendering it."""
    chain = Var("handler", EventChain)
    first = Component._create(children=(), event_triggers={"on_click": chain})
    second = Component._create(children=(), event_triggers={"on_click": chain})
    other_trigger = Component._create(children=(), event_triggers={"on_blur": chain})
    with RegistrationContext.ensure_context().fork():
        wrapper = get_memoized_event_triggers(first)["on_click"]
        monkeypatch.setattr(LiteralVar, "create", pytest.fail)
        assert get_memoized_event_triggers(second)["on_click"] is wrapper
        monkeypatch.undo()
        assert get_memoized_event_triggers(other_trigger)["on_blur"] is not wrapper
