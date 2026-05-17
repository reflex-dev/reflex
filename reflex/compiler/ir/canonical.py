"""Canonical hashing for IR nodes. See RUST_REWRITE_PLAN.md §1 ("IR identity").

Each Component carries a stable ``NodeId = hash(canonical_bytes)``. The
canonical form is the IR list-of-lists serialized via the same packer the
wire format uses — two semantically-equivalent IR subtrees hash to the same
NodeId regardless of who built them.

The Rust side uses ``xxh3_64`` (see ``crates/reflex_db/src/lib.rs``). The
Python side prefers ``xxhash.xxh3_64_intdigest`` when available (so the same
content hashes identically on both sides for debug builds) and falls back to
``hashlib.blake2b(digest_size=8)`` otherwise. The two are not interchangeable
across the Rust/Python boundary — but the wire format only carries the
already-computed NodeId, so Rust trusts whatever Python ships. The mismatch
only matters for the (debug-only) Pitfall 14 collision check, which is
gated on the xxhash library being present.

Collision probability at our use case (≤10⁶ unique nodes per running app)
is negligible for any 64-bit hash; either implementation is fine.
"""

from __future__ import annotations

import hashlib

import msgpack

try:  # pragma: no cover - import guard
    import xxhash

    _USE_XXHASH = True
except ImportError:  # pragma: no cover - fallback path
    xxhash = None  # type: ignore[assignment]
    _USE_XXHASH = False


def _hash_bytes(b: bytes) -> int:
    if _USE_XXHASH:
        return xxhash.xxh3_64_intdigest(b)  # type: ignore[union-attr]
    return int.from_bytes(hashlib.blake2b(b, digest_size=8).digest(), "big")


def hash_canonical_bytes(canonical: bytes) -> int:
    """Hash already-packed canonical bytes.

    Args:
        canonical: msgpack-packed canonical form of an IR subtree.

    Returns:
        The 64-bit content hash.
    """
    return _hash_bytes(canonical)


def hash_ir_subtree(subtree: list) -> int:
    """Pack ``subtree`` to msgpack and hash the result.

    Convenience helper for tests and the IR builder. Hot paths should call
    :func:`hash_canonical_bytes` on bytes they already have.

    Args:
        subtree: any IR list-of-lists structure.

    Returns:
        The 64-bit content hash of the canonical packed bytes.
    """
    packed = msgpack.packb(subtree, use_bin_type=True)
    return _hash_bytes(packed)
