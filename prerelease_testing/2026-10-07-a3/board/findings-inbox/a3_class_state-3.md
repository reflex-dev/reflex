ITEM: a3_class_state
KIND: reverify
REF: N-008
TITLE: Dev SetUndefinedStateVarError guard rejects undeclared `_x__y` names again; own/base/mixin mangled names still allowed
SEVERITY: low
STATUS: fixed
REGRESSION_VS_0.9.12: no
REGRESSION_VS_0.10.0a2: no
REPRO: REFLEX_ENV_MODE=dev $SB/envs/a3/bin/python $P/reverify_core/scripts/derive_f_dunder.py a3 (copied to a neutral dir):
  `d._sneaky__name = 1` -> SetUndefinedStateVarError (a2: accepted); mixin `_Mx__mx`, base `_Base2__from_base`, `_Under` class, own
  `_D__typo__x` accepted; everything else identical to a2. Extra probe a3_class_state/probes/guard7495.py (dev/prod) and
  probes/guard_local_rename.py: own/mixin/base/_GUnder/__GDunderName/ComponentState-template/local and clash-renamed local
  (`Loc_0`, via __original_name__) mangled names accepted; a non-state helper class's mangled name (`_Helper__h`) and `_OtherState__x`
  now raise in dev (as on 0.9.12; a2 accepted); `_State__x`/`_BaseState__x`/`_object__x` accepted (framework classes are in the MRO);
  a state whose __name__ the user changed after creation raises for its own `self.__r` (same on 0.9.12). Prod: no guard (since a1).
EVIDENCE: prerelease_testing/2026-10-07-a3/a3_class_state/logs/py/a3/derive_f_dunder.{dev,prod}.txt, logs/adv/guard7495.{a3,alpha2,stable}.{dev,prod}.txt, logs/adv/guard_local_rename.txt
ROOT_CAUSE_GUESS: fixed by reflex/state.py:358-394 _plain_private_prefixes/_is_plain_private_name
