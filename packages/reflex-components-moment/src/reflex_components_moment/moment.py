"""Moment component for humanized date rendering."""

from __future__ import annotations

import dataclasses
import datetime
from typing import Any

from reflex_base.components.component import (
    Component,
    MemoizationLeaf,
    NoSSRComponent,
    field,
)
from reflex_base.event import EventHandler, passthrough_event_spec
from reflex_base.utils.imports import ImportDict, ImportVar
from reflex_base.vars.base import LiteralVar, Var


@dataclasses.dataclass(frozen=True)
class MomentDelta:
    """A delta used for add/subtract prop in Moment."""

    years: int | None = dataclasses.field(default=None)
    quarters: int | None = dataclasses.field(default=None)
    months: int | None = dataclasses.field(default=None)
    weeks: int | None = dataclasses.field(default=None)
    days: int | None = dataclasses.field(default=None)
    hours: int | None = dataclasses.field(default=None)
    minutes: int | None = dataclasses.field(default=None)
    seconds: int | None = dataclasses.field(default=None)
    milliseconds: int | None = dataclasses.field(default=None)


def _locale_module(locale: Var[str] | None) -> str | None:
    """Return the moment locale module that a locale prop requires.

    Args:
        locale: The locale prop, if set.

    Returns:
        The locale module, or None when the built-in English locale suffices.
    """
    if isinstance(locale, LiteralVar):
        if locale._var_value == "en":
            return None
        return f"moment/locale/{locale._var_value}"
    return None if locale is None else "moment/min/locales"


def _locale_timezone_imports(
    locale: Var[str] | None, timezone: Var[str] | None
) -> ImportDict:
    """Return the locale and timezone imports required by Moment props.

    Args:
        locale: The locale prop, if set.
        timezone: The timezone prop, if set.

    Returns:
        The locale and timezone module imports, plus moment itself for
        _restore_global_locale when a locale module is imported.
    """
    imports: ImportDict = {}
    if (module := _locale_module(locale)) is not None:
        imports[""] = module
        imports["moment@2.31.0"] = ImportVar(tag="moment", is_default=True)
    if timezone is not None:
        imports["moment-timezone@0.6.5"] = ""
    return imports


def _restore_global_locale(locale: Var[str] | None) -> list[str]:
    """Return code that resets moment's global locale after a locale import.

    Importing a locale module also makes it moment's global locale, which
    Moment components without a locale or provider use.

    Args:
        locale: The locale prop, if set.

    Returns:
        The reset code, or nothing when no locale module is imported.
    """
    return [] if _locale_module(locale) is None else ['moment.locale("en");']


class MomentProvider(Component):
    """Provide shared defaults and timer pooling for descendant Moment components."""

    tag: str | None = "MomentProvider"
    library: str | None = "react-moment@2.0.2"
    lib_dependencies: list[str] = ["moment@2.31.0"]

    pool: Var[bool] = field(doc="Use one timer for all descendant Moment components.")
    interval: Var[int] = field(doc="The interval in milliseconds for the pooled timer.")
    locale: Var[str] = field(doc="The default locale for descendant Moment components.")
    local: Var[bool] = field(doc="Display descendant dates in local time by default.")
    format: Var[str] = field(doc="The default date format for descendants.")
    parse: Var[str | list[str]] = field(
        doc="The default date parse format for descendants."
    )
    filters: Var[list[Var[Any]]] = field(
        doc="JavaScript content filters applied to descendant Moment components."
    )
    renderers: Var[list[Var[Any]]] = field(
        doc="JavaScript content renderers tried for descendant Moment components."
    )
    element: Var[str] = field(doc="The default HTML element for descendant components.")
    timezone: Var[str] = field(doc="The default timezone for descendant components.")

    def add_imports(self) -> ImportDict:
        """Import the locale and timezone modules required by the defaults.

        Returns:
            The locale and timezone module imports.
        """
        return _locale_timezone_imports(self.locale, self.timezone)

    def add_custom_code(self) -> list[str]:
        """Keep moment's global locale English after the locale import.

        Returns:
            The global locale reset, if a locale module is imported.
        """
        return _restore_global_locale(self.locale)


class Moment(NoSSRComponent, MemoizationLeaf):
    """The Moment component."""

    tag: str | None = "Moment"
    is_default = True
    library: str | None = "react-moment@2.0.2"
    lib_dependencies: list[str] = ["moment@2.31.0"]

    interval: Var[int] = field(
        doc="How often the date update (how often time update / 0 to disable)."
    )

    format: Var[str] = field(
        doc="Formats the date according to the given format string."
    )

    trim: Var[bool | str] = field(
        doc='When formatting duration time, the largest-magnitude tokens are automatically trimmed when they have no value. Also accepts a trim template: "large", "small", "both", "all", "final", "left" or "right".'
    )

    parse: Var[str | list[str]] = field(
        doc=" Use the parse attribute to tell moment how to parse the given date when non-standard. Accepts a single format string or a list of formats to try."
    )

    utc: Var[bool] = field(doc="Parses and displays the date in UTC.")

    calendar: Var[bool | dict[str, str]] = field(
        doc="Displays the date using Moment's calendar format, optionally with custom calendar strings."
    )

    from_: Var[
        str | datetime.datetime | datetime.date | datetime.time | datetime.timedelta
    ] = field(doc="Displays the interval from this date to the component's date.")

    to: Var[
        str | datetime.datetime | datetime.date | datetime.time | datetime.timedelta
    ] = field(doc="Displays the interval from the component's date to this date.")

    ago: Var[bool] = field(
        doc='Omits the "ago" or "in" suffix from relative-time output.'
    )

    element: Var[str] = field(
        doc="The HTML element used to render the formatted date (defaults to time)."
    )

    fallback: Var[str | int] = field(
        doc="Content to render when the date input is invalid."
    )

    filters: Var[list[Var[Any]]] = field(
        doc="JavaScript functions applied in order to the rendered content."
    )

    renderers: Var[list[Var[Any]]] = field(
        doc="JavaScript renderer functions tried before the built-in output modes."
    )

    add: Var[MomentDelta] = field(
        doc='Add a delta to the base date (keys are "years", "quarters", "months", "weeks", "days", "hours", "minutes", "seconds")'
    )

    subtract: Var[MomentDelta] = field(
        doc='Subtract a delta to the base date (keys are "years", "quarters", "months", "weeks", "days", "hours", "minutes", "seconds")'
    )

    from_now: Var[bool] = field(
        doc='Displays the date as the time from now, e.g. "5 minutes ago".'
    )

    from_now_short: Var[bool] = field(
        doc='Displays the relative time in a short format using abbreviated units (e.g., "1h", "2d", "3mo", "1y" instead of "1 hour ago", "2 days ago", etc.).'
    )

    from_now_during: Var[int] = field(
        doc="Setting fromNowDuring will display the relative time as with fromNow but just during its value in milliseconds, after that format will be used instead."
    )

    to_now: Var[bool] = field(
        doc="Similar to fromNow, but gives the opposite interval."
    )

    with_title: Var[bool] = field(
        doc="Adds a title attribute to the element with the complete date."
    )

    title_format: Var[str] = field(
        doc="How the title date is formatted when using the withTitle attribute."
    )

    diff: Var[str] = field(
        doc="Show the different between this date and the rendered child."
    )

    decimal: Var[bool] = field(doc="Display the diff as decimal.")

    unit: Var[str] = field(doc="Display the diff in given unit.")

    duration: Var[str] = field(
        doc="Shows the duration (elapsed time) between two dates. duration property should be behind date property time-wise."
    )

    date: Var[
        str | datetime.datetime | datetime.date | datetime.time | datetime.timedelta
    ] = field(doc="The date to display (also work if passed as children).")

    duration_from_now: Var[bool] = field(
        doc="Shows the duration (elapsed time) between now and the provided datetime."
    )

    unix: Var[bool] = field(
        doc="Tells Moment to parse the given date value as a unix timestamp."
    )

    local: Var[bool] = field(doc="Outputs the result in local time.")

    tz: Var[str] = field(doc="Display the date in the given timezone.")

    locale: Var[str] = field(
        doc="The locale for this component. Defaults to the nearest rx.moment_provider locale, or English.",
    )

    on_change: EventHandler[passthrough_event_spec(str)] = field(
        doc="Fires when the component mounts and when the date changes, including when interval is 0. React Strict Mode can invoke the mount event twice in development."
    )

    def add_imports(self) -> ImportDict:
        """Add the imports for the Moment component.

        Returns:
            The import dict for the component.
        """
        imports = _locale_timezone_imports(self.locale, self.tz)
        if self.duration is not None or self.duration_from_now is not None:
            imports["moment-duration-format@2.3.2"] = ImportVar(tag=None)

        return imports

    def add_custom_code(self) -> list[str]:
        """Keep moment's global locale English after the locale import.

        Returns:
            The global locale reset, if a locale module is imported.
        """
        return _restore_global_locale(self.locale)
