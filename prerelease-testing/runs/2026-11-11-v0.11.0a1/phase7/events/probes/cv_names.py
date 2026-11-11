"""#7804 extras: name-as-default hint on the migration trap, name validation, collision-free identifiers."""
import os
import warnings

import reflex as rx

assert os.environ["EXPECT_VENV"] in rx.__file__, rx.__file__
warnings.simplefilter("ignore")


def hooks(v):
    return list(v._get_all_var_data().hooks)


try:
    rx.ClientStateVar.create("user_input").push(1)
except ValueError as e:
    print("trap push:", str(e)[-170:])
for bad in ["a-b", "cs$0", "1abc", "", "ünï"]:
    try:
        v = rx.client_state("x", name=bad)
        print(f"name={bad!r}: accepted, hooks={hooks(v)}")
    except Exception as e:
        print(f"name={bad!r}: {type(e).__name__}: {str(e)[:150]}")
for n in ["item", "Item", "prev0", "searchQuery", "searchquery"]:
    print(n, hooks(rx.client_state("d", name=n)))
try:
    legacy = rx._x.client_state("legacy_name", "dflt")
    print("rx._x.client_state legacy:", legacy._is_global, hooks(legacy))
except Exception as e:
    print("rx._x legacy:", type(e).__name__, e)
