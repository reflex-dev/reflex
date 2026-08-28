"""Prove root cause: restore dynamic.bundled_libraries and see rxe validation work again."""

import reflex as rx
from reflex.components import dynamic
from reflex_base.registry import RegistrationContext

dynamic.bundled_libraries = RegistrationContext.ensure_context().bundled_libraries
print("shim installed; bundled:", dynamic.bundled_libraries)

from reflex_enterprise.vars import LiteralLambdaVar

try:
    v = LiteralLambdaVar.create(lambda params: rx.text(params.value, color="tomato"))
    print("create OK, js:", str(v)[:120])
except AttributeError as e:
    print("STILL AttributeError:", e)
except ValueError as e:
    print("intended rxe validation ValueError:", e)
