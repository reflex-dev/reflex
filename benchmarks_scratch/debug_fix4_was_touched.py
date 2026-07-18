"""Trace _was_touched behavior through app.modify_state (debug for PR #6757)."""

import asyncio
from unittest.mock import AsyncMock


def main():
    from reflex.app import App
    from reflex.istate.manager.token import BaseStateToken
    from reflex.state import BaseState

    class DebugBase(BaseState):
        count: int = 0
        _backend: int = 0

    class DebugSub(DebugBase):
        sub_count: int = 0

    app = App(_state=DebugBase)
    app._event_namespace = AsyncMock()

    orig_update = BaseState._update_was_touched
    orig_clean = BaseState._clean
    orig_get = BaseState._get_was_touched

    def traced_update(self):
        before = self.__dict__.get("_was_touched")
        orig_update(self)
        print(
            f"  _update_was_touched({type(self).__name__}) dirty={self.dirty_vars} "
            f"was_before={before} was_after={self.__dict__.get('_was_touched')}"
        )

    def traced_clean(self):
        print(f"  _clean({type(self).__name__}) dirty={self.dirty_vars}")
        orig_clean(self)

    def traced_get(self):
        result = orig_get(self)
        print(f"  _get_was_touched({type(self).__name__}) -> {result}")
        return result

    BaseState._update_was_touched = traced_update
    BaseState._clean = traced_clean
    BaseState._get_was_touched = traced_get

    async def run():
        async with app.modify_state(
            token=BaseStateToken(ident="tok-debug-123", cls=DebugSub)
        ) as root:
            root.count = 1
            print(f"mutated: dirty={root.dirty_vars}")
        print(
            f"after ctx: dirty={root.dirty_vars} "
            f"was_touched={root.__dict__.get('_was_touched')}"
        )
        assert root._was_touched, "REPRO: _was_touched is falsy after modify_state"
        print("NO REPRO: _was_touched is set")

    asyncio.run(run())


main()
