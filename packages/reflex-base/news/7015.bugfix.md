Fix hooks and imports being silently dropped from the compiled output when two
vars with the same value but different metadata were interpolated into the same
f-string. Var hashing is now derived from the same identity `Var.equals` uses,
which also fixes `Var.equals` raising `VarTypeError` for vars that carry
dependencies, and makes `NumberVar` and `BooleanVar` hashable.
