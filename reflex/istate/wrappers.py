"""Wrappers for the state manager."""

from typing import Any

from reflex.istate.manager import get_state_manager
from reflex.istate.manager.token import BaseStateToken
from reflex.istate.proxy import ReadOnlyStateProxy
from reflex.state import State, _split_substate_key


async def get_state(token: str, state_cls: Any | None = None) -> ReadOnlyStateProxy:
    """Get the instance of a state for a token.

    Args:
        token: The token for the state.
        state_cls: The class of the state.

    Returns:
        A read-only proxy of the state instance.
    """
    if state_cls is None:
        _, state_path = _split_substate_key(token)
        state_cls = State.get_class_substate(tuple(state_path.split(".")))
    ctx = get_state_manager()._state_context(token)
    instance = await ctx.get_state(BaseStateToken(ident=token, cls=state_cls))
    return ReadOnlyStateProxy(instance)
