"""Probe: what is the public handle on a @rx.memo component's compiled library?"""
import reflex as rx

assert "/envs/verify2_ent_aggrid_0/" in rx.__file__, rx.__file__

from reflex.components.dynamic import bundle_library
from reflex_base.registry import RegistrationContext


@rx.memo
def row_counter(rowid: rx.Var[str]) -> rx.Component:
    return rx.text(rowid)


print("type(row_counter) =", type(row_counter))
print("row_counter.library =", getattr(row_counter, "library", "<no attr>"))
inst = row_counter(rowid="x")
print("type(inst) =", type(inst))
print("inst.library =", getattr(inst, "library", "<no attr>"))

ctx = RegistrationContext.ensure_context()
print("bundled before:", list(ctx.bundled_libraries))
bundle_library(inst)
print("bundled after bundle_library(inst):", list(ctx.bundled_libraries))
