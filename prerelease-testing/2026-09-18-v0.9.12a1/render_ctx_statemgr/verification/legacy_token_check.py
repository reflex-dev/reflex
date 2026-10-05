import sys, traceback
import reflex
assert "/envs/" in reflex.__file__, reflex.__file__
print("REFLEX", reflex.__file__)
from reflex.state import _split_substate_key, BaseState
from reflex.istate.manager.token import BaseStateToken

class RootTest(BaseState):
    pass

tok = "28e5629b-ec73-4320-aa7b-88532f582a73"
print("split(bare uuid) ->", _split_substate_key(tok))
try:
    print("from_legacy_token(bare) ->", BaseStateToken.from_legacy_token(tok, root_state=reflex.State))
except Exception as e:
    print("from_legacy_token(bare) RAISED:", type(e).__name__, e)
legacy = f"{tok}_{reflex.State.get_full_name()}"
print("legacy full form:", legacy)
try:
    print("from_legacy_token(full) ->", BaseStateToken.from_legacy_token(legacy, root_state=reflex.State))
except Exception as e:
    print("from_legacy_token(full) RAISED:", type(e).__name__, e)
# a token WITH an underscore but no state suffix
try:
    print("from_legacy_token('abc_def') ->", BaseStateToken.from_legacy_token("abc_def", root_state=reflex.State))
except Exception as e:
    print("from_legacy_token('abc_def') RAISED:", type(e).__name__, e)
