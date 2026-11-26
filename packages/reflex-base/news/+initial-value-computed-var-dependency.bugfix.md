Reading a computed var declared with `initial_value` from another computed var's getter now yields the initial value while the initial state dict is built, instead of running its getter.
