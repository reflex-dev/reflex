import reflex
assert "/envs/shared/" in reflex.__file__, reflex.__file__
import reflex as rx
from reflex.state import State
import inspect
# what module holds reserved name validation
import reflex.istate as istate, pkgutil, os
print("reflex file:", reflex.__file__)
from reflex_base.utils import console
import reflex.state as st
print([n for n in dir(st) if "Reserved" in n or "Shadow" in n])
try:
    from reflex.istate.validation import *  # noqa
    print("validation module exists")
except Exception as e:
    print("no validation module:", e)
