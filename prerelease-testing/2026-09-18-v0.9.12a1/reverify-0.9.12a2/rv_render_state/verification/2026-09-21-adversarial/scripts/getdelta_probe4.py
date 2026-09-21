import reflex as rx
print("reflex:", rx.constants.Reflex.VERSION)
METHODS = ["get_delta", "_get_resolved_delta", "get_value", "reset", "setvar",
           "_clean", "_mark_dirty", "dict", "get_state", "_process_event"]
for i, m in enumerate(METHODS):
    src = (
        f"import reflex as rx\n"
        f"class K{i}(rx.State):\n"
        f"    n: int = 0\n"
        f"    def {m}(self, *a, **k):\n"
        f"        return None\n"
    )
    g = {}
    try:
        exec(src, g)
        print(f"class-body override `{m}`: ALLOWED")
    except Exception as e:
        print(f"class-body override `{m}`: {type(e).__name__}: {str(e)[:95]}")
