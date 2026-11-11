import os

import reflex

# Every probe in this directory must import reflex from the venv named by EXPECT_VENV.
assert f"/envs/{os.environ['EXPECT_VENV']}/" in reflex.__file__, reflex.__file__
