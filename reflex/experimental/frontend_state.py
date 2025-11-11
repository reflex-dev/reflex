"""Experimental frontend state cache/sync implementation.

Can we implement reflex outside of the core using just plugins?

Lets get there.
"""

import asyncio
import dataclasses
import functools
import inspect
import time
from collections.abc import (
    AsyncGenerator,
    Callable,
    Coroutine,
    Generator,
    Iterator,
    Mapping,
    Sequence,
)
from contextvars import ContextVar, Token, copy_context
from dataclasses import _MISSING_TYPE, MISSING
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, TypeVar, Unpack, overload

from reflex.compiler.templates import generic_var_template
from reflex.components.component import FIELD_TYPE
from reflex.constants import Hooks
from reflex.constants.compiler import Ext
from reflex.plugins.base import CommonContext, Plugin
from reflex.utils import console
from reflex.utils.format import to_snake_case
from reflex.utils.imports import ImportVar
from reflex.utils.types import GenericType
from reflex.vars.base import Field, Var, VarData, dispatch, figure_out_type
from reflex.vars.function import (
    ArgsFunctionOperation,
    FunctionArgs,
    FunctionStringVar,
    FunctionVar,
)
from reflex.vars.object import ObjectVar

ZUSTAND_USE_STORE_IMPORT = {"zustand": "useStore"}
ZUSTAND_CREATE = FunctionStringVar(
    "zustand_create",
    _var_data=VarData(
        imports={"zustand": ImportVar(tag="create", alias="zustand_create")},
    ),
)


@functools.lru_cache
def get_name(cls: type | Callable) -> str:
    """Get the name of the state/func.

    Returns:
        The name of the state/func.
    """
    module = cls.__module__.replace(".", "___")
    qualname = getattr(cls, "__qualname__", cls.__name__).replace(".", "___")
    return to_snake_case(f"{module}___{qualname}")


@dataclasses.dataclass(frozen=True, kw_only=True)
class EventContext:
    """The context for an event."""

    token: str
    enqueue: Callable[["EventHandler"], None]
    emit_delta: (
        Callable[[Mapping[str, Mapping[str, Any]]], Coroutine[Any, Any, None]] | None
    ) = None
    dirty_vars: set[tuple[type, str]] = dataclasses.field(
        default_factory=set, init=False
    )
    accessed_vars: set[tuple[type, str]] = dataclasses.field(
        default_factory=set, init=False
    )
    cached_states: dict[type, Any] = dataclasses.field(default_factory=dict, init=False)

    async def get_state(self, object_cls: type[T]) -> T:
        if (obj := self.cached_states.get(object_cls)) is not None:
            return obj
        obj = object_cls()
        self.clean(object_cls)
        self.cached_states[object_cls] = obj
        return obj

    def clean(self, object_cls: type) -> None:
        """Clean the dirty vars for the given class.

        Args:
            object_cls: The class to clean.
        """
        for cls, name in list(self.dirty_vars):
            if cls == object_cls:
                self.dirty_vars.remove((cls, name))
        for cls, name in list(self.accessed_vars):
            if cls == object_cls:
                self.accessed_vars.remove((cls, name))


event_context: ContextVar[EventContext] = ContextVar("event_context")


T = TypeVar("T")


@dataclasses.dataclass
class RegisteredState:
    """A class registered as a state class."""

    registered_class: type
    state_fields: list["StateField"]
    state_name: str
    compiled_module_path: str
    compiled_store_name: str


def register_state_class(cls: type[T]) -> type[T]:
    """Register a class as a state class.

    Args:
        cls: The class to register

    Returns:
        The registered class.
    """
    if cls in _REGISTERED_STATE_CLASSES:
        return cls

    original_setattr = cls.__setattr__
    original_getattribute = cls.__getattribute__

    def _registered_state_setattr(self: T, name: str, value: Any) -> None:
        """Set an attribute on the state.

        Args:
            name: The name of the attribute.
            value: The value of the attribute.
        """
        try:
            ctx = event_context.get()
        except LookupError:
            pass
        else:
            ctx.dirty_vars.add((cls, name))
        original_setattr(self, name, value)

    def _registered_state_getattribute(self: T, name: str) -> Any:
        """Get an attribute on the state.

        Args:
            name: The name of the attribute.

        Returns:
            The value of the attribute.
        """
        try:
            ctx = event_context.get()
        except LookupError:
            pass
        else:
            ctx.accessed_vars.add((cls, name))
        return original_getattribute(self, name)

    cls.__setattr__ = _registered_state_setattr
    cls.__getattribute__ = _registered_state_getattribute

    state_name = get_name(cls)

    _REGISTERED_STATE_NAMES[state_name] = _REGISTERED_STATE_CLASSES[cls] = (
        RegisteredState(
            registered_class=cls,
            state_fields=[],
            state_name=state_name,
            compiled_module_path=f"state/{state_name}",
            compiled_store_name=f"{state_name}_store",
        )
    )
    return cls


def state_imports(state: RegisteredState) -> dict[str, str]:
    return {state.compiled_module_path: state.compiled_store_name}


def set_state(state: RegisteredState, setter: Any) -> FunctionVar:
    """Set the state fields to the new values.

    Args:
        state: The state class.
        setter: The new state or a function of the state that returns the new state.

    Returns:
        The function var to set the state.
    """
    return ArgsFunctionOperation.create(
        args_names=(),
        return_expr=ObjectVar(
            state.compiled_store_name,
            _var_type=dict,
        )
        .setState.to(FunctionVar)
        .call(setter),
        _var_data=VarData(
            imports=state_imports(state),
        ),
    )


class SettableVarMixin(Var[FIELD_TYPE]):
    registered_state: ClassVar[RegisteredState]
    name: ClassVar[str]

    def set(self, value: FIELD_TYPE | Var[FIELD_TYPE]) -> FunctionVar:
        """Set the value of the field.

        Args:
            value: The value to set.

        Returns:
            The function var to set the value.
        """
        return set_state(
            self.registered_state,
            ArgsFunctionOperation.create(
                args_names=("state",),
                return_expr=ObjectVar("state", _var_type=dict).merge(
                    Var.create({self.name: value}),
                ),
            ),
        )


class StateField(Field[FIELD_TYPE]):
    """A field in the frontend state."""

    if TYPE_CHECKING:
        name: str
        owner_class: type

    @classmethod
    def create(
        cls,
        default: FIELD_TYPE | _MISSING_TYPE = MISSING,
        *,
        default_factory: Callable[[], FIELD_TYPE] | None = None,
        is_var: bool = True,
    ) -> "StateField[FIELD_TYPE] | FIELD_TYPE":
        """Create a field for a state.

        Args:
            default: The default value for the field.
            default_factory: The default factory for the field.
            is_var: Whether the field is a Var.

        Returns:
            The field for the state.

        Raises:
            ValueError: If both default and default_factory are specified.
        """
        return super().create(
            default,
            default_factory=default_factory,
            is_var=is_var,
        )

    def __init__(
        self,
        default: FIELD_TYPE | _MISSING_TYPE = MISSING,
        default_factory: Callable[[], FIELD_TYPE] | None = None,
        is_var: bool = True,
        annotated_type: GenericType  # pyright: ignore [reportRedeclaration]
        | _MISSING_TYPE = MISSING,
    ) -> None:
        """Initialize the field.

        Args:
            default: The default value for the field.
            default_factory: The default factory for the field.
            is_var: Whether the field is a Var.
            annotated_type: The annotated type for the field.
        """
        if annotated_type is MISSING and default is not MISSING:
            annotated_type = figure_out_type(default)
        super().__init__(default, default_factory, is_var, annotated_type)

    def __set_name__(self, owner: type[T], name: str):
        """Set the name of the field.

        Args:
            owner: The owner class.
            name: The name of the field.
        """
        self.name = name
        self.owner_class = owner
        self.registered_state.state_fields.append(self)

    @property
    def registered_state(self) -> RegisteredState:
        """Get the registered state class.

        Returns:
            The registered state class.
        """
        register_state_class(self.owner_class)
        return _REGISTERED_STATE_CLASSES[self.owner_class]

    @property
    def attribute_name(self) -> str:
        """Get the attribute name for the field.

        Returns:
            The attribute name for the field.
        """
        return f"_reflex_state_field_{self.name}"

    @property
    def js_const_name(self) -> str:
        """Get the JS constant name for the field.

        Returns:
            The JS constant name for the field.
        """
        return f"{self.registered_state.state_name}___{self.name}"

    @property
    def imports(self) -> dict[str, str]:
        """Get the imports for the field.

        Returns:
            The imports for the field.
        """
        return {
            **state_imports(self.registered_state),
            **ZUSTAND_USE_STORE_IMPORT,
        }

    def get_is_dirty(self) -> bool:
        """Get whether the field is dirty.

        Returns:
            Whether the field is dirty.
        """
        return (self.owner_class, self.attribute_name) in event_context.get().dirty_vars

    def set_is_dirty(self, is_dirty: bool) -> None:
        """Set whether the field is dirty.

        Args:
            is_dirty: Whether the field is dirty.

        Returns:
            Whether the field was dirty before setting.
        """
        if is_dirty:
            event_context.get().dirty_vars.add((self.owner_class, self.name))
        else:
            event_context.get().dirty_vars.discard((self.owner_class, self.name))

    @overload
    def __get__(
        self, instance: None, owner: type[T]
    ) -> SettableVarMixin[FIELD_TYPE]: ...

    @overload
    def __get__(self, instance: T, owner: type[T]) -> FIELD_TYPE: ...

    def __get__(
        self, instance: T, owner: type[T]
    ) -> FIELD_TYPE | SettableVarMixin[FIELD_TYPE]:
        """Get the value of the field.

        Args:
            instance: The instance of the owner class.
            owner: The owner class.

        Returns:
            The value of the field.
        """
        if instance is None:
            # Get the Var representation when accessed on the class.
            registered_state = _REGISTERED_STATE_CLASSES[owner]
            getter = ArgsFunctionOperation.create(
                args_names=("state",),
                return_expr=Var("state").to(dict)[self.name],
            )
            state_var = dispatch(
                field_name=self.js_const_name,
                var_data=VarData(
                    state=owner.__module__.replace(".", "___"),
                    field_name=self.name,
                    hooks={
                        f"const {self.js_const_name} = "
                        f"useStore({registered_state.compiled_store_name}, {getter!s});": VarData(
                            position=Hooks.HookPosition.INTERNAL
                        ),
                    },
                    imports=self.imports,
                ),
                result_var_type=self.outer_type_,
            )

            class SettableVar(SettableVarMixin, type(state_var)):
                registered_state: ClassVar[RegisteredState] = self.registered_state
                name: ClassVar[str] = self.name

            new_var_name = f"SettableVar_{self.owner_class.__name__}_{self.name}"
            SettableVar.__qualname__ = new_var_name
            SettableVar.__name__ = new_var_name

            return SettableVar(**{
                f.name: getattr(state_var, f.name)
                for f in dataclasses.fields(state_var)
            })

        return getattr(instance, self.attribute_name, self.default)

    def __set__(self, instance: T, value: FIELD_TYPE):
        """Set the value of the field.

        Args:
            instance: The instance of the owner class.
            value: The value to set.
        """
        if isinstance(value, SettableVarMixin):
            # Never set the Var to the instance.
            return
        print(f"Setting {self.owner_class.__name__}.{self.name} to {value!r}")
        setattr(instance, self.attribute_name, value)


def get_dict(state: Any) -> dict[str, Any]:
    """Get the dict representation of the state class.

    Args:
        state_class: The state class.

    Returns:
        The dict representation of the state class.
    """
    try:
        registered_state_class = _REGISTERED_STATE_CLASSES[state.__class__]
    except KeyError as ke:
        raise ValueError(
            f"State class {state.__class__.__name__} is not registered."
        ) from ke
    return {
        field.name: getattr(state, field.name)
        for field in registered_state_class.state_fields
    }


def get_delta(state: Any) -> dict[str, Any]:
    """Get the delta representation of the state class.

    Args:
        state: The state class.

    Returns:
        The delta representation of the state class.
    """
    try:
        registered_state_class = _REGISTERED_STATE_CLASSES[state.__class__]
    except KeyError as ke:
        raise ValueError(
            f"State class {state.__class__.__name__} is not registered."
        ) from ke
    dirty_fields = [
        field for field in registered_state_class.state_fields if field.get_is_dirty()
    ]
    delta = {field.name: getattr(state, field.name) for field in dirty_fields}
    event_context.get().clean(state.__class__)
    return delta


async def print_delta(delta: Mapping[str, Mapping[str, Any]]) -> None:
    """Print the delta.

    Args:
        delta: The delta to print.
    """
    if delta:
        console.print(f"Delta: {delta}")


_REGISTERED_STATE_CLASSES: dict[type, RegisteredState] = {}
_REGISTERED_STATE_NAMES: dict[str, RegisteredState] = {}


class FrontendStatePlugin(Plugin):
    """Compile the stores and initial state for new style States."""

    def get_static_assets(
        self, **context: Unpack[CommonContext]
    ) -> Sequence[tuple[Path, str | bytes]]:
        """Get the static assets required by the plugin.

        Args:
            context: The context for the plugin.

        Returns:
            A list of static assets required by the plugin.
        """
        return [
            (
                Path("state", registered_state_class.state_name).with_suffix(Ext.JS),
                generic_var_template(
                    content=Var(
                        f"export const {registered_state_class.compiled_store_name} = "
                        f"{ZUSTAND_CREATE(ArgsFunctionOperation.create(args_names=(), return_expr=Var.create(get_dict(cls()))))};"
                    ),
                ),
            )
            for cls, registered_state_class in _REGISTERED_STATE_CLASSES.items()
        ]


class InvalidEventHandlerReturnError(Exception):
    """An error raised when an event handler returns an EventHandler."""

    def __init__(self, msg: str | None = None) -> None:
        super().__init__(
            msg
            or (
                "Chained EventHandler must be yielded, not returned; "
                "or use `await` to get the result of an EventHandler."
            )
        )


@dataclasses.dataclass(frozen=True, kw_only=True, slots=True)
class EventHandler(ArgsFunctionOperation):
    fn: Callable[..., Any]
    args: tuple[Any, ...] = ()
    kwargs: dict[str, Any] = dataclasses.field(default_factory=dict)

    name: str | None = None
    owner_class: type | None = None

    @classmethod
    def create(
        cls,
        fn: Callable[..., Any],
        /,
        *args: Any,
        **kwargs: Any,
    ) -> "EventHandler":
        """Create an EventHandler.

        Args:
            fn: The function to create the EventHandler for.
            args: The args to pass to the function.
            kwargs: The kwargs to pass to the function.

        Returns:
            The created EventHandler.
        """
        return cls(
            fn=fn,
            args=args,
            kwargs=kwargs,
            _js_expr="",
            _var_type=Callable,
            _var_data=None,
        )

    def __post_init__(self):
        registered_name = Var.create(get_name(self.fn))
        payload = {
            "args": (
                *self.args,
                Var("...args"),
            ),
            "kwargs": self.kwargs,
        }
        object.__setattr__(
            self,
            "_args",
            FunctionArgs(args=(), rest="args"),
        )
        object.__setattr__(
            self,
            "_return_expr",
            Var(f"addEvent({registered_name}, {Var.create(payload)})"),
        )
        super().__post_init__()

    def __set_name__(self, owner: type[RegisteredState], name: str):
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "owner_class", owner)

    @property
    def registered_state(self) -> RegisteredState:
        """Get the registered state class.

        Returns:
            The registered state class.
        """
        if self.owner_class is None:
            msg = "EventHandler is not bound to a class."
            raise ValueError(msg)
        register_state_class(self.owner_class)
        return _REGISTERED_STATE_CLASSES[self.owner_class]

    def __get__(
        self, instance: RegisteredState | None, owner: type[RegisteredState]
    ) -> "EventHandler":
        return self

    def partial(self, *args: Any, **kwargs: Any) -> Any:
        return dataclasses.replace(
            self,
            args=self.args + args,
            kwargs={**self.kwargs, **kwargs},
        )

    __call__ = partial

    def __await_args_kwargs__(
        self, ctx: EventContext | None = None
    ) -> Generator[Any, None, tuple[tuple[Any, ...], dict[str, Any]]]:
        args = []
        kwargs = {}
        self_arg = ()
        if self.owner_class is not None and ctx is not None:
            self_arg = (ctx.get_state(self.owner_class),)
        for arg in (*self_arg, *self.args):
            if inspect.isawaitable(arg):
                resolved_arg = yield from arg.__await__()
                if isinstance(arg, EventHandler):
                    # The return value from an EventHandler is always the last value.
                    args.append(resolved_arg[-1])
                else:
                    args.append(resolved_arg)
            else:
                args.append(arg)
        for k, v in self.kwargs.items():
            if inspect.isawaitable(v):
                resolved_v = yield from v.__await__()
                if isinstance(v, EventHandler):
                    # The return value from an EventHandler is always the last value.
                    kwargs[k] = resolved_v[-1]
                else:
                    kwargs[k] = resolved_v
            else:
                kwargs[k] = v
        return tuple(args), kwargs

    def __await_emit_delta__(self) -> Generator[Any, None, None]:
        ctx = event_context.get()
        if ctx.emit_delta is not None:
            yield from ctx.emit_delta({
                _REGISTERED_STATE_CLASSES[dirty_cls].state_name: delta
                for dirty_cls in sorted(
                    {cls for cls, _ in ctx.dirty_vars}, key=lambda c: c.__name__
                )
                if (delta := get_delta(ctx.cached_states[dirty_cls]))
            }).__await__()

    def __await__(self) -> Generator[Any, None, list[Any]]:
        """Invoke the event handler, capturing chained events in the context."""
        queue: asyncio.Queue[EventHandler] | None = None
        ctx_token: Token | None = None
        try:
            ctx = event_context.get()
        except LookupError:
            ctx = None
            queue = asyncio.Queue()
            ctx_token = event_context.set(
                ctx := EventContext(
                    token="",
                    enqueue=queue.put_nowait,
                    emit_delta=print_delta,
                )
            )
        args, kwargs = yield from self.__await_args_kwargs__(ctx)
        coro_gen_result = self.fn(*args, **kwargs)
        results = []
        if inspect.iscoroutinefunction(self.fn):
            await_iter = coro_gen_result.__await__()
            try:
                while update := next(await_iter):
                    yield update
            except StopIteration as final:
                if isinstance(final.value, EventHandler):
                    raise InvalidEventHandlerReturnError from None
                results.append(final.value)
        elif inspect.isasyncgenfunction(self.fn):
            try:
                while update_gen := anext(coro_gen_result):
                    await_iter = update_gen.__await__()
                    try:
                        while update := next(await_iter):
                            yield update
                    except StopIteration as final:
                        if final.value is not None:
                            if isinstance(final.value, EventHandler):
                                ctx.enqueue(final.value)
                            else:
                                results.append(final.value)
                    # Send interim update.
                    yield from self.__await_emit_delta__()
            except StopAsyncIteration:
                pass
        elif inspect.isgeneratorfunction(self.fn):
            try:
                while update := next(coro_gen_result):
                    if update is not None:
                        if isinstance(update, EventHandler):
                            ctx.enqueue(update)
                        else:
                            results.append(update)
                    # Send interim update.
                    yield from self.__await_emit_delta__()
            except StopIteration as final:
                if isinstance(final.value, EventHandler):
                    raise InvalidEventHandlerReturnError from None
                results.append(final.value)
        else:
            if isinstance(coro_gen_result, EventHandler):
                raise InvalidEventHandlerReturnError from None
            results.append(coro_gen_result)
        if queue is not None:
            # Drain the queue since the context above us didn't provide one.
            while not queue.empty():
                sub_result = yield from queue.get_nowait().__await__()
                results.insert(len(results) - 2, sub_result)
        # Get the final delta of all dirty vars.
        yield from self.__await_emit_delta__()
        if ctx_token is not None:
            event_context.reset(ctx_token)
        print(f"{self.fn.__name__} final: {results}")
        return results


event = EventHandler.create


if __name__ == "__main__":

    @event
    async def coro(v: int = 42) -> int:
        await asyncio.sleep(1)
        return v

    @event
    async def agen(
        it: int = 3, requeue: bool = False
    ) -> AsyncGenerator[int | EventHandler]:
        for i in range(it):
            await asyncio.sleep(1)
            yield i
            print("calculated inline: ", await coro(i * 10))
            yield coro(i)
        if requeue:
            yield agen(it=it - 1, requeue=it > 1)

    @event
    def printerrr(v: Any) -> str:
        print(f"printerr: {v}")
        return str(v)

    @event
    def dispatcher() -> Iterator[EventHandler]:
        yield coro(67)
        yield printerrr(some_shiz("hello"))
        yield agen(2)
        yield agen(8)
        yield coro(420)
        yield doubler(coro(21))

    @event
    def doubler(v: int) -> int:
        return v * 2

    @event
    async def some_shiz(x: str) -> str:
        await asyncio.sleep(1)
        return x + " world"

    @register_state_class
    @dataclasses.dataclass
    class Foo:
        _bar: str = "hello"
        _baz: int = 42
        myf: StateField[int] = StateField(100)

        @event
        async def bar(self) -> str:
            self._bar += "!"
            o = await event_context.get().get_state(Other)
            o.friends_with_your_mom = True
            yield
            o.friends_with_your_mom = False
            yield
            self.myf += 4
            yield f"{self._bar} {self._baz} {'yes' if o.friends_with_your_mom else 'no'}"

        @event
        async def print_bar(self) -> None:
            self._bar += "?"
            b = await self.bar()
            print(f"Foo.bar: {b[-1]}")

    @register_state_class
    @dataclasses.dataclass
    class Other:
        friends_with_your_mom: StateField[bool] = StateField(False)

    def event_runner(event: EventHandler) -> asyncio.Task:
        async def event_awaiter() -> Any:
            return await event

        return asyncio.create_task(
            event_awaiter(), name=f"reflex_event|{event.fn.__name__}|{time.time()}"
        )

    def event_processor(
        token: str,
        event: EventHandler,
        enqueue: Callable[[tuple[str, EventHandler]], None],
    ) -> [asyncio.Task, EventContext]:
        ctx = copy_context()
        ctx_event_context = EventContext(
            token=token, enqueue=lambda e, token=token: enqueue((token, e))
        )
        ctx.run(event_context.set, ctx_event_context)
        return ctx.run(event_runner, event), ctx_event_context

    async def event_loop(
        q: asyncio.Queue[tuple[str, EventHandler]], concurrency: int = 5
    ):
        outstanding: dict[asyncio.Task, tuple[str, EventHandler, ContextVar]] = {}
        # When a token is already being processed, queue up events per token.
        per_token_queues: dict[str, asyncio.Queue[EventHandler]] = {}

        def clean_task(task: asyncio.Task):
            token, event, ctx = outstanding[task]
            print(
                f"[{token}] {event.fn.__name__}(*{event.args!r}, **{event.kwargs!r}) -> {task.result()!r}"
            )
            print(ctx)
            if token in per_token_queues:
                try:
                    next_event = per_token_queues[token].get_nowait()
                except asyncio.QueueEmpty:
                    print(f"[{token}] No more queued events, clearing.")
                    token_queue = per_token_queues.pop(token, None)
                    if token_queue is not None:
                        token_queue.shutdown()
                        while not token_queue.empty():
                            # Race condition: so put these back on the main queue.
                            q.put_nowait((token, token_queue.get_nowait()))
                else:
                    print(f"[{token}] Dequeuing next event {next_event.fn.__name__}")
                    new_task, new_context = event_processor(
                        token, next_event, q.put_nowait
                    )
                    outstanding[new_task] = (token, next_event, new_context)
                    new_task.add_done_callback(clean_task)
            outstanding.pop(task, None)

        while True:
            if len(outstanding) >= concurrency:
                print(
                    f"Queue is full ({len(outstanding)} tasks), waiting for one to complete..."
                )
                # Wait for one task to complete.
                done, pending = await asyncio.wait(
                    outstanding.keys(),
                    return_when=asyncio.FIRST_COMPLETED,
                )
                continue
            try:
                token, event = q.get_nowait()
            except asyncio.QueueEmpty:
                if not outstanding:
                    print(
                        "Queue is empty and no outstanding tasks, exiting event loop."
                    )
                    break
                await asyncio.sleep(0.1)
                continue
            if token in per_token_queues:
                # This token is already being processed, so priority wait for next available slot.
                print(f"[{token}] Queueing event {event.fn.__name__} to run later")
                per_token_queues[token].put_nowait(event)
                continue
            per_token_queues[token] = asyncio.Queue()
            task, ctx = event_processor(token, event, q.put_nowait)
            outstanding[task] = (token, event, ctx)
            task.add_done_callback(clean_task)

    async def main():
        q = asyncio.Queue()
        # q.put_nowait(("token1", agen))
        # q.put_nowait(("token2", coro))
        # q.put_nowait(("token3", dispatcher))
        # q.put_nowait(("token4", doubler(coro(99))))
        # q.put_nowait(("token5", printerrr(v=some_shiz("hello"))))
        q.put_nowait(("token67", Foo.print_bar))
        # await event_loop(q)
        await Foo.print_bar
        print(Foo.print_bar("baz"))
        print(agen(3))

    breakpoint()
    asyncio.run(main())
