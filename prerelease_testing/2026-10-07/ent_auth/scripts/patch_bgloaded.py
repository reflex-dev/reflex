"""Add ListWorker.fill_loaded (loads AuthUserState inside every `async with self` block) + a button to entauth.

Run once:  $SB/envs/driver/bin/python -I scripts/patch_bgloaded.py <path/to/entauth/entauth/entauth.py>
"""
import sys

p = sys.argv[1]
s = open(p).read()
if "fill_loaded" not in s:
    s = s.replace('''    @rxe.event
    def add_item(self, value: str):''', '''    @rxe.event(background=True)
    async def fill_loaded(self):
        """Like fill, but loads AuthUserState inside EVERY `async with self` block."""
        for i in range(5):
            async with self:
                auth_user = await self.get_state(AuthUserState)
                sub = auth_user.userinfo.get("sub", "anon")
                self.items.append(f"{sub}-bgl-{i}")
                self.progress = i + 1
            await asyncio.sleep(0.25)

    @rxe.event
    def add_item(self, value: str):''')
    s = s.replace('''        rx.button("fill", id="fill", on_click=ListWorker.fill),''', '''        rx.button("fill", id="fill", on_click=ListWorker.fill),
        rx.button("fill loaded", id="fill-loaded", on_click=ListWorker.fill_loaded),''')
    open(p, "w").write(s)
print("fill_loaded" in open(p).read())
