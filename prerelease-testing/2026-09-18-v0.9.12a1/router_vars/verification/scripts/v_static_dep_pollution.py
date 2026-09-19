import reflex as rx
assert "/envs/" in rx.__file__, rx.__file__

def body(self) -> str:
    return self.router.url.path

cv = rx.var(deps=["router"])(body)
print("BEFORE attach/_deps -> _static_deps =", {k: sorted(v) for k, v in cv._static_deps.items()})

class S(rx.State):
    legacy = cv

cvs = S.computed_vars["legacy"]
print("AFTER  class creation -> _static_deps =", {k: sorted(v) for k, v in cvs._static_deps.items()})
print("same object as pre-attach cv?", cvs is cv)
