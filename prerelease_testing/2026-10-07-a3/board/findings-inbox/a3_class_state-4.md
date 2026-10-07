ITEM: a3_class_state
KIND: reverify
REF: N-006
TITLE: BackendVarFormatError now names default_value()/ClassVar/state var; the silent str()/%s/!s paths and the cryptic id= error are unchanged
SEVERITY: low
STATUS: changed
REGRESSION_VS_0.9.12: no
REGRESSION_VS_0.10.0a2: no
REPRO: $SB/envs/a3/bin/python $P/reverify_core/scripts/derive_e_format.py a3 (from a neutral dir):
  f"{S._size}px" -> "BackendVarFormatError: Backend var 'S._size' exists only on the server ... Use S._size.default_value() for its default
  value, declare it as ClassVar[...] for a constant shared by all sessions, or use a regular state var ..." (fixed part).
  Still: f"{S._size!s}px", str(S._size)+"px", "%s px" % S._size -> silently "Field(default=16, is_var=True, annotated_type=<class 'int'>)px";
  rx.box(id=S._label) -> "TypeError: expected string or bytes-like object, got 'Field'" (no var name). Identical to a2 apart from the message.
EVIDENCE: prerelease_testing/2026-10-07-a3/a3_class_state/logs/py/a3/derive_e_format.txt vs logs/py/alpha2/derive_e_format.txt
ROOT_CAUSE_GUESS: message: reflex_base/vars/base.py Field.__format__ (~4185); silent paths: Field.__str__/__repr__ not guarded (only __format__ raises)
