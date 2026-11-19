"""Tests for the towncrier template in reflex_release/templates/changelog.md."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from reflex_release.scaffold import towncrier_config_toml

FRAGMENTS = {
    "1.feature.md": "Trailing block:\n\n```python\ndef add():\n    pass\n\n\ndef sub():\n    pass\n```\n",
    "2.feature.md": "Nested fences:\n\n````md\n```\nx\n```\n````\n",
    "3.feature.md": "```\nonly code\n```\n",
    "4.bugfix.md": "Plain entry.\n",
    "5.bugfix.md": "Sublist:\n\n- a\n- b\n",
    "6.bugfix.md": "Code in the middle:\n\n~~~\nx\n~~~\n\nthen prose.\n",
    "7.bugfix.md": "Longer closing fence:\n\n~~~python\nx\n~~~~\n",
    "8.bugfix.md": "Two blocks:\n\n```\na\n```\n\n```\nb\n```\n",
    "9.bugfix.md": "Inline code:\n\n```foo``` is a span.\n\n~~~\nx\n~~~\n",
}

EXPECTED = """\
# Changelog

<!-- towncrier release notes start -->

## v1.0.0 (2026-11-18)

### Features

- Trailing block: ([#1](https://github.com/OWNER/REPO/issues/1))

  ```python
  def add():
      pass


  def sub():
      pass
  ```
- Nested fences: ([#2](https://github.com/OWNER/REPO/issues/2))

  ````md
  ```
  x
  ```
  ````
- ```
  only code
  ```

  ([#3](https://github.com/OWNER/REPO/issues/3))

### Bug Fixes

- Plain entry. ([#4](https://github.com/OWNER/REPO/issues/4))
- Sublist:

  - a
  - b

  ([#5](https://github.com/OWNER/REPO/issues/5))
- Code in the middle:

  ~~~
  x
  ~~~

  then prose. ([#6](https://github.com/OWNER/REPO/issues/6))
- Longer closing fence: ([#7](https://github.com/OWNER/REPO/issues/7))

  ~~~python
  x
  ~~~~
- Two blocks:

  ```
  a
  ```

  ```
  b
  ```

  ([#8](https://github.com/OWNER/REPO/issues/8))
- Inline code:

  ```foo``` is a span. ([#9](https://github.com/OWNER/REPO/issues/9))

  ~~~
  x
  ~~~
"""


def test_issue_links_above_trailing_code_block(tmp_path: Path) -> None:
    """An entry ending in a fenced code block gets its links after the prose."""
    (tmp_path / "pyproject.toml").write_text(towncrier_config_toml(tmp_path))
    (tmp_path / "CHANGELOG.md").write_text(
        "# Changelog\n\n<!-- towncrier release notes start -->\n"
    )
    news = tmp_path / "news"
    news.mkdir()
    for name, text in FRAGMENTS.items():
        (news / name).write_text(text)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "towncrier",
            "build",
            "--config",
            "pyproject.toml",
            "--dir",
            ".",
            "--version",
            "v1.0.0",
            "--date",
            "2026-11-18",
            "--yes",
        ],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    assert (tmp_path / "CHANGELOG.md").read_text() == EXPECTED
