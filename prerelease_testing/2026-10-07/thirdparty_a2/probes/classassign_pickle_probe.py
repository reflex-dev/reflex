"""Class-level assignment to a backend var (reflex-clerk style) and a pickle round trip.

Usage: <venv>/bin/python classassign_pickle_probe.py <expected-venv-name>
"""
import pickle
import sys

import reflex as rx

assert f"/scratchpad/envs/{sys.argv[1]}/" in rx.__file__, rx.__file__


class ClerkLike(rx.State):
    _secret_key: str | None = None
    _fetch_user: bool = True

    @classmethod
    def configure(cls, key: str, fetch: bool) -> None:
        cls._secret_key = key
        cls._fetch_user = fetch


ClerkLike.configure("sk_test_123", False)
root = rx.State(_reflex_internal_init=True)
inst = root.get_substate(ClerkLike.get_full_name().split(".")[1:])
print("class-level      :", repr(ClerkLike._secret_key), repr(ClerkLike._fetch_user))
print("instance (fresh) :", repr(inst._secret_key), repr(inst._fetch_user))
inst2 = pickle.loads(pickle.dumps(inst))
print("instance (pickle):", repr(inst2._secret_key), repr(inst2._fetch_user))
print("get_fields has _secret_key:", "_secret_key" in ClerkLike.get_fields())
