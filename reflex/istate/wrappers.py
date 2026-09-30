"""Wrappers for the state manager."""

from typing import Any

from reflex_base.event.context import EventContext
from reflex_base.state.token import BaseStateToken

from reflex.state import BaseState, State, _split_substate_key


async def get_state(token: str, state_cls: Any | None = None) -> BaseState:
    """Get the instance of a state for a token, read-only outside of `async with` it.

    Args:
        token: The token for the state.
        state_cls: The class of the state.

    Returns:
        The state instance.
    """
    ctx = EventContext.get()
    mng = ctx.state_manager
    if state_cls is not None:
        root_state = await mng.get_state(BaseStateToken(ident=token, cls=state_cls))
    else:
        root_state = await mng.get_state(BaseStateToken(ident=token, cls=State))
        _, state_path = _split_substate_key(token)
        state_cls = root_state.get_class_substate(tuple(state_path.split(".")))
    # Loaded without the lock: read-only until entered, which locks its token.
    root_state._event_context = ctx if token == ctx.token else ctx.fork(token=token)
    return await root_state.get_state(state_cls)
