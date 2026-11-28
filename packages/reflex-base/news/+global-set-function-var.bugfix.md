`ClientStateVar.global_set` is typed as the `FunctionVar` it returns, so `cs.global_set.call(value)` type-checks without `.to(FunctionVar)`.
