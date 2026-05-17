"""msgpack packing helpers for IR trees.

The spike (§0 of ``RUST_REWRITE_PLAN.md``) measured that one ``msgpack.packb``
call on a tree-of-lists is **5-7% faster** than streaming via
``msgpack.Packer.pack_array_header`` per node, because ``msgpack-python``
descends the structure in C and we'd pay Python-call overhead at every
header otherwise. So this module is intentionally thin — one call per blob.
"""

from __future__ import annotations

import msgpack


def pack_page(page_ir: list) -> bytes:
    """Pack a page IR (as built by :mod:`reflex.compiler.ir.builder`) to bytes.

    Args:
        page_ir: the list-of-lists IR.

    Returns:
        msgpack-encoded bytes ready for ``CompilerSession.compile_page``.
    """
    return msgpack.packb(page_ir, use_bin_type=True)


def pack_theme(theme_ir: list) -> bytes:
    return msgpack.packb(theme_ir, use_bin_type=True)


def pack_global_state(state_ir: list) -> bytes:
    return msgpack.packb(state_ir, use_bin_type=True)


def pack_plugin_manifest(manifest_ir: list) -> bytes:
    return msgpack.packb(manifest_ir, use_bin_type=True)
