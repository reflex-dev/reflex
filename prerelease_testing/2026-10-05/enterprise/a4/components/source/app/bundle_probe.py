"""Verify the fixed demo registers its real memo module after compiler resets."""

import inspect
import json
import os
from pathlib import Path

from components.formatter_demo import formatters
from reflex.components import dynamic
from reflex.utils.format import json_dumps
from reflex_enterprise.vars import get_bundled_libraries

dynamic.reset_bundled_libraries()
dynamic.bundle_library("@radix-ui/themes")
page = inspect.unwrap(formatters.formatter_page)()
memo_module = formatters.row_counter(rowid="").library
libraries = get_bundled_libraries()
assert memo_module in libraries, (memo_module, libraries)
imports = page._get_all_imports()
definitions = json_dumps(formatters.cols_defs)
assert imports
assert memo_module in definitions
evidence = {
    "passed": True,
    "memo_module": memo_module,
    "bundled_libraries": list(libraries),
    "serialized_column_definitions": definitions,
}
Path(os.environ["QA_BUNDLE_OUTPUT"]).write_text(json.dumps(evidence, indent=2) + "\n")
print("Memo module registered after reset:", memo_module)
