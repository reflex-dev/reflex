(structured report of the a4_class_state agent, 2026-10-08; full detail in ../../a4_class_state/NOTES.md)

REVERIFIED: A3-01 / A3-02 / A3-04 moot (assignment raises the documented TypeError at the assignment line, field intact;
a3 positive controls reproduced first: 4F/4P, 4F/16P, None/int drop storage, thread stress count=21369). A3-03 docs fixed.
N-005 / N-039 fixed through the field API (e2e dev + prod/Redis 9 workers 28/28; 170/170 + downstream 176/176 field
patch round trips on 3.11/3.12/3.14). N-008 unchanged-fixed. N-004 as documented (schema hash a4 == a3; a3 <-> a4
interchangeable on pickle, disk and Redis).
ISSUES (pending verification): (1) substate `add_var` of a name a parent got via `add_var` raises the #7516 TypeError
(a3 / 0.9.12 accept); (2) `state_auto_setters=True` + parent var `set_<x>` + child var `<x>` fails with the #7516 message
(a3 also raised, differently; 0.9.12 created the class); (3) reflex-clerk 1.0.3 writes backend vars through the class
(documented breaking change; package already broken on every 0.10 alpha).
ANOMALIES: inherited-var mock.patch.object surfaces the cleanup's "deleting" TypeError with the "assigning" one as
__context__ (cosmetic); bare threading.Thread state instantiation LookupError (pre-existing on 0.9.12).
