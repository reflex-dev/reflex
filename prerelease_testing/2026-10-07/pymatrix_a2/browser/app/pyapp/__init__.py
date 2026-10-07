"""Guard the fixture against importing framework sources from the checkout."""

import os

import reflex

assert f"/envs/{os.environ['REFLEX_TEST_ENV']}/" in reflex.__file__, reflex.__file__
