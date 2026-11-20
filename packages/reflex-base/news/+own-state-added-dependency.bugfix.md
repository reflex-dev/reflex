A computed var whose `deps` are declared keeps them when `add_dependency` adds a var of its own state, so it still recomputes on the declared vars after a hot reload.
