# reflex-docs-bundle

The Reflex documentation bundled as a redistributable Python wheel. Built on
demand; not published to PyPI.

```python
from reflex_docs_bundle import DOCS_DIR, get_doc, list_docs

list_docs()  # ["vars/custom_vars.md", ...]
get_doc("vars/custom_vars.md")  # markdown source as a string
DOCS_DIR / "vars" / "custom_vars.md"
```
