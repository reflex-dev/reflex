A background event handler that overrides one from a mixin or a parent state can call it with `await super().handler()` again, instead of raising `ImmutableStateError`.
