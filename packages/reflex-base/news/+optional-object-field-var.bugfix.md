ty now reads an optional model, dataclass or mapping field (`rx.Field[X | None]`) on the state class as `ObjectVar[X]`, as pyright already did, instead of `ObjectVar[X | None]`.
