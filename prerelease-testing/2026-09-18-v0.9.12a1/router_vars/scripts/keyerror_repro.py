import reflex as rx, traceback
assert "/envs/" in rx.__file__, rx.__file__
for name in ["process", "json", "get_delta", "dirty_vars"]:
    src = f"""
import reflex as rx
class Boom_{name}(rx.State):
    {name}: int = 0
"""
    print(f"--- state var named {name!r} (real class stmt) ---")
    try:
        exec(compile(src, "<repro>", "exec"), {})
    except Exception as e:
        print(f"  {type(e).__name__}: {e}")
        if type(e).__name__ == "KeyError":
            traceback.print_exc()
