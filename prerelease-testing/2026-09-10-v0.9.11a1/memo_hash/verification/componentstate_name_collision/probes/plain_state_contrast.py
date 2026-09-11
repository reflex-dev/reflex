"""Contrast: plain rx.State subclasses with the same name in two modules ARE
module-qualified (issue #3214) and coexist; ComponentState's dynamic subclass
is not, and collides.

Usage: <venv>/bin/python probes/plain_state_contrast.py <venv-name>
"""

import sys

import reflex

VENV = sys.argv[1] if len(sys.argv) > 1 else "smoke"
assert f"/envs/{VENV}/" in reflex.__file__, reflex.__file__
print("reflex", reflex.constants.Reflex.VERSION)

from st_one.s import Foo as FooOne  # noqa: E402
from st_two.s import Foo as FooTwo  # noqa: E402

print("plain rx.State, same class name, two modules:")
print("  ", FooOne.get_full_name())
print("  ", FooTwo.get_full_name())
print("   coexist:", FooOne.get_full_name() != FooTwo.get_full_name())
