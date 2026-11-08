An `EventHandler` stored outside a state, e.g. in a dataclass field, now reads back as the handler for type checkers instead of `Any`; read through a state instance it is the bound function.
