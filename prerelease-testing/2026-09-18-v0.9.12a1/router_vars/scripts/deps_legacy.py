import reflex as rx
assert "/envs/shared/" in rx.__file__, rx.__file__

class S(rx.State):
    @rx.var(deps=["router"])
    def legacy(self) -> str:
        return self.router.url.path

print("--- class created, now inspecting deps ---")
cv = S.computed_vars["legacy"]
print("deps:", cv._deps(objclass=S))
print("static_deps:", getattr(cv, "_static_deps", None))
