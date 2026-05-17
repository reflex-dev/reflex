"""Spike-stage Python package. The Rust extension is at `._native`."""

from . import _native  # noqa: F401

__all__ = ["_native"]
