"""Breakpoints utility."""

from typing import Optional, Tuple, TypeVar, Union

breakpoints_values = ["30em", "48em", "62em", "80em", "96em"]
breakpoint_names = ["xs", "sm", "md", "lg", "xl"]


def set_breakpoints(values: Tuple[str, str, str, str, str]):
    """Overwrite default breakpoint values.

    Args:
        values: CSS values in order defining the breakpoints of responsive layouts
    """
    breakpoints_values.clear()
    breakpoints_values.extend(values)


K = TypeVar("K")
V = TypeVar("V")


class Breakpoints(dict[K, V]):
    """A responsive styling helper."""

    def factorize(self):
        """Removes references to breakpoints names and instead replaces them with their corresponding values.

        Returns:
            The factorized breakpoints.
        """
        return Breakpoints(
            {
                (
                    breakpoints_values[breakpoint_names.index(k)]
                    if k in breakpoint_names
                    else ("0px" if k == "initial" else k)
                ): v
                for k, v in self.items()
                if v is not None
            }
        )

    @classmethod
    def create(
        cls,
        custom: Optional[dict[K, V]] = None,
        initial: Optional[V] = None,
        xs: Optional[V] = None,
        sm: Optional[V] = None,
        md: Optional[V] = None,
        lg: Optional[V] = None,
        xl: Optional[V] = None,
    ):
        """Create a new instance of the helper. Only provide a custom component OR use named props.

        Args:
            custom: Custom mapping using CSS values or variables.
            initial: Styling when in the inital width
            xs: Styling when in the extra-small width
            sm: Styling when in the small width
            md: Styling when in the medium width
            lg: Styling when in the large width
            xl: Styling when in the extra-large width

        Raises:
            ValueError: If both custom and any other named parameters are provided.

        Returns:
            The responsive mapping.
        """
        thresholds = [initial, xs, sm, md, lg, xl]

        if custom is not None:
            if any((threshold is not None for threshold in thresholds)):
                raise ValueError("Named props cannot be used with custom thresholds")

            return Breakpoints(custom)
        else:
            return Breakpoints(
                {
                    k: v
                    for k, v in zip(["initial", *breakpoint_names], thresholds)
                    if v is not None
                }
            )


breakpoints = Breakpoints.create

T = TypeVar("T")

Responsive = Union[T, Breakpoints[str, T]]
