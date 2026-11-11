import asyncio, sys
import reflex
assert "envs/new" in reflex.__file__
import reflex as rx
async def main():
    try:
        async with rx.asession() as s:
            print(await s.execute(__import__("sqlalchemy").text("select 1")))
    except Exception as e:
        print("ERR", type(e).__name__, e)
asyncio.run(main())
