import reflex as rx, sys
print("reflex", rx.constants.Reflex.VERSION)
print("type(rx.State) =", type(rx.State))
print("MRO of metaclass:", [c.__name__ for c in type(rx.State).__mro__])
import reflex_enterprise  # noqa
from reflex_enterprise.auth.oidc import state as _  # may fail
