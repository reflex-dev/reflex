"""The intended differences between rx.ui and the Radix components.

Every check of the harness reads ``allowlist.toml``: a difference listed there,
with its reason, passes, and an entry no difference matches any more fails, so
the file stays the complete list. The migration guide is generated from it.
"""

from __future__ import annotations

import dataclasses
import fnmatch
import tomllib
from pathlib import Path
from typing import Any

from ui_parity.systems import CANDIDATE, SYSTEMS

ALLOWLIST = Path(__file__).parents[1] / "allowlist.toml"

API_KINDS = ("prop", "type", "event")
LOOK_CHECKS = ("pixels", "style", "a11y")


class AllowlistError(ValueError):
    """An entry of the allowlist is not one the harness understands."""


@dataclasses.dataclass(frozen=True)
class ApiEntry:
    """Props or event triggers that differ on purpose.

    Attributes:
        component: The component.
        kind: What differs: whether a ``prop`` exists, the ``type`` of one, or
            whether an ``event`` trigger exists.
        names: The props or event triggers.
        reason: Why, for a reader of the migration guide.
    """

    component: str
    kind: str
    names: tuple[str, ...]
    reason: str


@dataclasses.dataclass(frozen=True)
class ContractEntry:
    """A step of a behaviour contract one system does not pass, on purpose.

    Attributes:
        component: The component.
        step: The name of the step.
        system: The system that does not pass it.
        engines: The browser engines it does not pass in: all when empty.
        reason: Why, for a reader of the migration guide.
    """

    component: str
    step: str
    system: str
    engines: tuple[str, ...]
    reason: str

    def covers(self, component: str, step: str, system: str, engine: str) -> bool:
        """Check whether the entry is about one run of a step.

        Args:
            component: The component the step belongs to.
            step: The name of the step.
            system: The name of the system it ran against.
            engine: The browser engine it ran in.

        Returns:
            Whether the step is expected to fail there.
        """
        return (
            self.component == component
            and self.step == step
            and self.system == system
            and (not self.engines or engine in self.engines)
        )


@dataclasses.dataclass(frozen=True)
class LookEntry:
    """A visible difference from the Radix component, on purpose.

    Attributes:
        component: The component.
        check: What differs: the ``pixels``, the computed ``style`` or the
            ``a11y`` tree.
        cells: The cells it differs in, as a shell pattern over the cell id.
        properties: The computed properties that differ, for ``style``.
        engines: The browser engines it differs in: all when empty.
        reason: Why, for a reader of the migration guide.
    """

    component: str
    check: str
    cells: str
    properties: tuple[str, ...]
    engines: tuple[str, ...]
    reason: str

    def covers(self, component: str, check: str, cell: str, engine: str) -> bool:
        """Check whether the entry is about one check of a cell.

        Args:
            component: The component of the cell.
            check: The check that found a difference.
            cell: The id of the cell.
            engine: The browser engine it was rendered in.

        Returns:
            Whether a difference is expected there.
        """
        return (
            self.component == component
            and self.check == check
            and (not self.engines or engine in self.engines)
            and fnmatch.fnmatchcase(cell, self.cells)
        )


@dataclasses.dataclass(frozen=True)
class Allowlist:
    """Every intended difference.

    Attributes:
        api: Differences of props and event triggers.
        contract: Differences of behaviour.
        look: Differences of pixels, computed style and accessibility tree.
    """

    api: tuple[ApiEntry, ...] = ()
    contract: tuple[ContractEntry, ...] = ()
    look: tuple[LookEntry, ...] = ()


def _entry(table: str, raw: dict[str, Any], defaults: dict[str, Any]) -> dict[str, Any]:
    """Validate the keys of one entry.

    Args:
        table: The table the entry is in.
        raw: The entry as the file has it.
        defaults: The keys an entry may leave out, and their values. A key
            without a default is required.

    Returns:
        The entry with its defaults, lists as tuples.

    Raises:
        AllowlistError: If a key is unknown or missing, or the reason is empty.
    """
    required = {"component", "reason", *defaults}
    if unknown := sorted(set(raw) - required):
        msg = f"[[{table}]] entry {raw} has unknown keys: {unknown}."
        raise AllowlistError(msg)
    entry = {**defaults, **raw}
    if missing := sorted(key for key in required if entry.get(key) is None):
        msg = f"[[{table}]] entry {raw} is missing: {missing}."
        raise AllowlistError(msg)
    if not entry["reason"].strip():
        msg = f"[[{table}]] entry {raw} needs a reason."
        raise AllowlistError(msg)
    return {
        key: tuple(value) if isinstance(value, list) else value
        for key, value in entry.items()
    }


def _one_of(table: str, key: str, value: str, choices: tuple[str, ...]) -> None:
    """Reject a value outside the ones a key takes.

    Args:
        table: The table the entry is in.
        key: The key.
        value: Its value.
        choices: The values the key takes.

    Raises:
        AllowlistError: If the value is not one of them.
    """
    if value not in choices:
        msg = f'[[{table}]] {key} = "{value}" is not one of {list(choices)}.'
        raise AllowlistError(msg)


def parse(document: dict[str, Any]) -> Allowlist:
    """Read an allowlist from its parsed TOML.

    Args:
        document: The tables of the file.

    Returns:
        The entries.

    Raises:
        AllowlistError: If a table or an entry is not understood.
    """
    if unknown := sorted(set(document) - {"api", "contract", "look"}):
        msg = f"Unknown allowlist tables: {unknown}."
        raise AllowlistError(msg)
    api = []
    for raw in document.get("api", []):
        entry = ApiEntry(**_entry("api", raw, {"kind": None, "names": None}))
        _one_of("api", "kind", entry.kind, API_KINDS)
        api.append(entry)
    contract = []
    systems = tuple(system.name for system in SYSTEMS)
    for raw in document.get("contract", []):
        entry = ContractEntry(
            **_entry(
                "contract",
                raw,
                {"step": None, "system": CANDIDATE.name, "engines": ()},
            )
        )
        _one_of("contract", "system", entry.system, systems)
        contract.append(entry)
    look = []
    for raw in document.get("look", []):
        entry = LookEntry(
            **_entry(
                "look",
                raw,
                {"check": None, "cells": "*", "properties": (), "engines": ()},
            )
        )
        _one_of("look", "check", entry.check, LOOK_CHECKS)
        look.append(entry)
    return Allowlist(api=tuple(api), contract=tuple(contract), look=tuple(look))


def load(path: Path = ALLOWLIST) -> Allowlist:
    """Read an allowlist file.

    Args:
        path: The TOML file.

    Returns:
        The entries.
    """
    return parse(tomllib.loads(path.read_text(encoding="utf-8")))


def differences_markdown(allowlist: Allowlist) -> str:
    """Write the intended differences as a document section.

    Args:
        allowlist: The entries.

    Returns:
        A markdown list per component, in name order: what differs and why.
    """
    lines: dict[str, list[str]] = {}
    for entry in allowlist.api:
        names = ", ".join(f"`{name}`" for name in entry.names)
        lines.setdefault(entry.component, []).append(
            f"- {entry.kind} {names}: {entry.reason}"
        )
    for entry in allowlist.contract:
        engines = f" in {', '.join(entry.engines)}" if entry.engines else ""
        lines.setdefault(entry.component, []).append(
            f'- behaviour, `{entry.system}`{engines}, "{entry.step}": {entry.reason}'
        )
    for entry in allowlist.look:
        engines = f" in {', '.join(entry.engines)}" if entry.engines else ""
        what = ", ".join(f"`{name}`" for name in entry.properties) or entry.cells
        lines.setdefault(entry.component, []).append(
            f"- {entry.check}{engines}, {what}: {entry.reason}"
        )
    return "\n\n".join(
        "\n".join([f"### {component}", "", *lines[component]])
        for component in sorted(lines)
    )
