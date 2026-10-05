"""Remove only this test's unexpected shell-profile installer suffix."""

import sys
from pathlib import Path

profile = Path(sys.argv[1])
suffix = (
    '\n# bun\n'
    'export BUN_INSTALL="/private/tmp/reflex-pre-js-runtime-20261005/bun"\n'
    'export PATH="$BUN_INSTALL/bin:$PATH"\n'
)
content = profile.read_text()
if content.count(suffix) != 1 or not content.endswith(suffix):
    raise RuntimeError("The exact installer suffix is not unique and last")
profile.write_text(content.removesuffix(suffix))
print("Removed only the neutral-runtime installer suffix from the shell profile")
