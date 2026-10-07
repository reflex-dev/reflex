"""Application model intentionally not imported by the negative fixtures."""

from dataclasses import dataclass


@dataclass
class InventoryItem:
    """A small application model declared before any State uses it."""

    sku: str
    stock: int
