import reflex as rx
import reflex.state  # what reflex-enterprise relies on for rx.state.<attr>
print("reflex:", rx.constants.Reflex.VERSION)
print("rx.state._override_base_method:", rx.state._override_base_method)
print("public export in reflex namespace?", hasattr(rx, "_override_base_method"))
import reflex.state as _s
print("in reflex.state.__all__?", "_override_base_method" in getattr(_s, "__all__", []) )

class Filtered(rx.State):
    visible: bool = False
    n: int = 0

    @rx.var(cache=False)
    def secret(self) -> str:
        return f"secret-{self.n}"

    @rx.state._override_base_method
    def get_delta(self):
        d = super().get_delta()
        if not self.visible:
            for k in list(d):
                inner = d[k]
                if isinstance(inner, dict):
                    inner.pop("secret_rx_state_", None)
        return d

i = Filtered(_reflex_internal_init=True)
i.n = 1
print("hidden delta:", dict(i.get_delta()))
i._clean()
i.visible = True
print("visible delta:", dict(i.get_delta()))
print("get_delta is an EventHandler?", type(Filtered.__dict__["get_delta"]).__name__)
print("in event_handlers?", "get_delta" in Filtered.event_handlers)
