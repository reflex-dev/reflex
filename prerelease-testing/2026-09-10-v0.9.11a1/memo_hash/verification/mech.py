import reflex as rx
assert "/envs/" in rx.__file__, rx.__file__
from reflex_base.utils import format
i = rx.Var("i_rx_state_", _var_type=int)
s = f"row-{i}"
print("REPR   :", repr(s))
print("TYPE   :", type(s))
print("REF    :", format.format_ref(s))
print("hash(i):", hash(i))
