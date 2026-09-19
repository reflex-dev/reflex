import sys, os
import reflex as rx
print("REFLEX:", reflex_path := rx.__file__)
assert "/envs/" in rx.__file__, rx.__file__
print("VERSION:", rx.constants.Reflex.VERSION)

# 1. form.message without match -> should not emit forceMatch
m = rx.form.message("Required")
s = str(m)
print("--- form.message(no match) ---")
print(s)
print("HAS_forceMatch:", "forceMatch" in s)
m2 = rx.form.message("Required", match="valueMissing")
s2 = str(m2)
print("--- form.message(match) ---")
print(s2)
print("HAS_forceMatch:", "forceMatch" in s2)
