Key access on a var typed as a subclass of a specialized generic `TypedDict`, such as `class R(P[str])`, now resolves the inherited field types instead of failing with `Unsupported type ~T`.
