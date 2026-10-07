# Published component wheel comparison

All four requested new wheels have **byte-identical Python sources** and identical substantive non-Python files to their stated predecessors. No wheels were installed, and no shared environment was modified. Wheel files remain in scratch storage, not in the repository.

| Package | Before → after | Python files checked | Runtime metadata changes |
|---|---|---:|---|
| reflex-components-dataeditor | 0.9.3.post1 → 0.10.0a1 | 2 | Python >=3.10→>=3.11; reflex-base >=0.9.12→>=0.10.0a2; core >=0.9.0→>=0.10.0a2 |
| reflex-components-react-player | 0.9.2 → 0.10.0a1 | 4 | Python >=3.10→>=3.11; reflex-base/core >=0.9.0→>=0.10.0a2 |
| reflex-components-sonner | 0.9.4 → 0.10.0a1 | 2 | Python >=3.10→>=3.11; reflex-base >=0.9.0→>=0.10.0a2; lucide >=0.9.0→>=1.1.0a1 |
| reflex-components-lucide | 1.0.4 → 1.1.0a1 | 2 | Python >=3.10→>=3.11; reflex-base >=0.9.0→>=0.10.0a2 |

Thus the package metadata changes include sibling dependency floors in addition to the Python floor. All `.dist-info` files are excluded from the substantive file comparison; the selected METADATA fields and SHA-256 for each complete wheel are retained in `summary.json`. The intentionally empty `*.py.diff` files mean zero source changes, not a skipped check. Download logs retain the exact PyPI package/version resolution.

Reproduce from a neutral scratch directory with the campaign driver environment containing pip:

```bash
SB=/private/tmp/reflex-prerelease-macos-pass2
ART=/Users/masen/.codex/worktrees/3564/reflex/prerelease_testing/2026-10-07/dataeditor/wheel_diff
cd "$SB"
UV_CACHE_DIR="$SB/uv-cache" uv --no-config run --no-project --python "$SB/envs/driver/bin/python" \
  python "$ART/compare_wheels.py" \
  --downloads "$SB/downloads/macos_lifecycle_component_wheels" --out "$SB/component-wheel-comparison"
```

`compare_wheels.py` invokes `python -m pip download --index-url https://pypi.org/simple --no-deps --only-binary=:all:` for each exact version, reads wheel ZIP members without executing them, compares every `.py` byte sequence, and compares all other members outside `.dist-info`. Python is executed only from the isolated driver environment and neutral scratch cwd.
