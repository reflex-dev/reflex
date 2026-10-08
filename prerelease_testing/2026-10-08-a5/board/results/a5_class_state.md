(structured report of the a5_class_state agent; full detail in ../../a5_class_state/NOTES.md)

REVERIFIED on a5 (positive controls first): F-004, N-005 (e2e dev + prod/Redis 28/28 via set_default), N-039 (204/204,
210 with downstream), N-008, N-004 (schema hash a5 == a4 == a3; a4 <-> a5 interchange), A3-01, A3-02, A3-04 all fixed.
A4-01 / A4-02 still open (message text changed only). set_default forms, docs samples, error owner naming, hot reload,
AppHarness, 22-package sweep = a4.
ISSUES (pending verification): (1) MEDIUM regression vs 0.9.12 and a4: a mutable class-body default populated after the
class statement is snapshotted empty at class definition (rx.field(...) still sees later additions); (2) LOW: frontend var
with a non-deep-copyable default loses the clear VarTypeError (opaque pickle TypeError); (3) LOW: backend var with a
non-deep-copyable default now fails at import without naming the var (a4 failed on access; 0.9.12 on every session);
(4) LOW perf: large mutable defaults copied once more at import and kept resident (+75-780 ms, +12-50 MB); (5) LOW docs:
upgrade guide says `.default = []` was safe on 0.9 — false for frontend vars on 0.9.12.
