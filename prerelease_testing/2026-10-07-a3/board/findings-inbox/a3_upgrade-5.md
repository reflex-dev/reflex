ITEM: a3_upgrade
KIND: new
REF: N-024 (related), #7312
TITLE: Upgrade guide misses a background-task break: writing a var INHERITED from a parent state outside `async with self` (directly, or via a handler declared on the same state) worked on 0.9.12 and now raises ImmutableStateError
SEVERITY: low
STATUS: new
REGRESSION_VS_0.9.12: yes (behaviour change; the new behaviour is the safe one, the gap is that the guide/changelog do not describe it)
REGRESSION_VS_0.10.0a2: no (a2 behaves like a3)
REPRO: app `a3_upgrade/apps/guide/app` (`class Parent(rx.State): count: int = 0`; `class Child2(Parent): own: int = 0` with background tasks), `a3_upgrade/bin/seq_guide2.sh`
  (0.9.12 dev then a3 dev on 3214/8214; driver `scripts/drive_guide.py <url> <out> <tag>` clicks each button and reads Parent.count / Child2.own). Results:
    background task body                                   0.9.12                          a3 (and a2)
    self.count += 100   (inherited var, no handler)        no error, count 14 -> 114        ImmutableStateError, unchanged
    self.own += 100     (own var, no handler)              ImmutableStateError              ImmutableStateError
    self.own_bump()     (handler on Child2 writing count)   no error, count 4 -> 14          ImmutableStateError
    self.own_var_bump() (handler on Child2 writing own)     ImmutableStateError              ImmutableStateError
    self.bump()         (inherited handler, guide sample)   no error, count +1               ImmutableStateError
  The guide section "Calling inherited handlers from background tasks" (and the a3 changelog's #7312 entry) attribute the 0.9 hole to inherited HANDLERS and say "A handler
  declared on the same state was already called through that proxy"; on 0.9.12 the actual hole is any write to an inherited VAR through the proxy (0.9.12
  `StateProxy.__setattr__` lets names in `get_skip_vars()` through, and inherited vars are delegated to the parent state). An app that does `self.count += 1` on a parent's
  var in a background task outside `async with self` (silently unlocked on 0.9.12) gets `ImmutableStateError` on 0.10 and the guide does not mention that case.
  Suggested doc line: "Writing a var inherited from a parent state outside `async with self` — directly or through any handler — also raises `ImmutableStateError` now; 0.9 wrote it without the lock."
EVIDENCE: a3_upgrade/shots/guide/guide3-{stable,a3}-dev.json (notes: direct_inherited, direct_own, own_outside, own_var_outside, outside), guide2-*.json, logs/guide3-*.server.log
ROOT_CAUSE_GUESS: 0.9.12 reflex/istate/proxy.py:322-329 StateProxy.__setattr__ lets `name in self.__wrapped__.get_skip_vars()` through without the mutability check, and 0.9.12 reflex/state.py:1455-1456 `get_skip_vars()` starts with `set(cls.inherited_vars)` — so every inherited-var write through a background-task proxy was unlocked; fixed on the 0.10 line by #7312's descriptor rework; docs: docs/changelog/upgrading/upgrading-to-0-10.md "Calling inherited handlers from background tasks".
