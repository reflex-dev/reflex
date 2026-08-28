"""User-side pyright checks against the *installed* reflex package.

Targets PR #6846: builtin-named class members (Var.bool, BaseState.dict,
PropsBase.dict, ...) shadowed builtins in same-class annotations, which made
pyright infer Var.create(anything) as LiteralBooleanVar and degrade
Var.to/guess_type/to_string. Every assignment below errors under pyright if
Var.create collapses to LiteralBooleanVar, and the reveal_type output shows
the actual inferred overload.

Run: pyright --pythonpath <venv>/bin/python --outputjson main.py
"""

import reflex as rx

x_int: rx.Var[int] = rx.Var.create(5)
x_str: rx.Var[str] = rx.Var.create("hello")
x_float: rx.Var[float] = rx.Var.create(3.14)
x_list: rx.Var[list[int]] = rx.Var.create([1, 2, 3])
x_dict: rx.Var[dict[str, int]] = rx.Var.create({"a": 1})
x_bool: rx.Var[bool] = rx.Var.create(True)

reveal_type(rx.Var.create(5))  # pyright: ignore[reportUndefinedVariable]  # noqa: F821
reveal_type(rx.Var.create("hello"))  # pyright: ignore[reportUndefinedVariable]  # noqa: F821
reveal_type(rx.Var.create([1, 2, 3]))  # pyright: ignore[reportUndefinedVariable]  # noqa: F821

# Var.to / to_string / guess_type were degraded the same way.
v = rx.Var.create(5)
v_str: rx.Var[str] = v.to_string()
v_to: rx.Var[float] = v.to(float)
v_guessed: rx.Var = rx.Var("expr")._var_type and rx.Var("expr").guess_type()


class MyState(rx.State):
    """A user state class."""

    n: int = 0

    @rx.event
    def bump(self):
        """Increment n."""
        self.n += 1
        d: dict = self.dict()  # BaseState.dict must still return a real dict
        assert isinstance(d, dict)


class MyProps(rx.PropsBase):
    """User props class."""

    foo: int = 0


props_dict: dict = MyProps(foo=1).dict()

toast_props_ok = rx.toast("hi", duration=5000)
