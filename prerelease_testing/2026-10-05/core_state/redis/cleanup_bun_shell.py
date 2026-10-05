"""Remove only the Bun installer append owned by this isolated campaign."""

import hashlib
import json
import sys
from pathlib import Path


def main() -> None:
    """Restore unrelated shell configuration byte-for-byte around our append."""
    shell_file = Path("/Users/masenf/.zshrc")
    owned_runtime = b"/private/tmp/reflex-alpha-core-state/runtime/bun"
    block = (
        b'\n# bun\nexport BUN_INSTALL="'
        + owned_runtime
        + b'"\nexport PATH="$BUN_INSTALL/bin:$PATH"\n'
    )
    previous = shell_file.read_bytes()
    assert previous.count(owned_runtime) == 1
    assert previous.count(block) == 1
    updated = previous.replace(block, b"", 1)
    assert len(previous) - len(updated) == len(block)
    assert owned_runtime not in updated
    shell_file.write_bytes(updated)
    assert shell_file.read_bytes() == updated
    checked = []
    for relative in (
        ".zshrc",
        ".zprofile",
        ".bashrc",
        ".bash_profile",
        ".profile",
        ".config/fish/config.fish",
    ):
        candidate = Path("/Users/masenf") / relative
        if candidate.is_file():
            assert owned_runtime not in candidate.read_bytes(), relative
            checked.append(relative)
    result = {
        "status": "passed",
        "side_effect": "Published Reflex's fresh Bun installation appended a persistent PATH block to ~/.zshrc",
        "owned_runtime": owned_runtime.decode(),
        "removed_bytes": len(block),
        "removed_lines": block.decode().splitlines(),
        "before_sha256": hashlib.sha256(previous).hexdigest(),
        "after_sha256": hashlib.sha256(updated).hexdigest(),
        "preserved_unrelated_content": True,
        "remaining_owned_runtime_references_in_shell_files": 0,
        "checked_shell_files": checked,
    }
    Path(sys.argv[1]).write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps({
            "status": result["status"],
            "removed_bytes": len(block),
            "remaining_owned_references": 0,
        })
    )


if __name__ == "__main__":
    main()
