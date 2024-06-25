from typing import Self


breakpoints_values = ["520px", "768px", "1024px", "1280px", "1640px"]


def set_breakpoints(values: tuple[str, str, str, str, str]):
    breakpoints_values.clear()
    breakpoints_values.extend(values)


class Breakpoints(dict):
    """A responsive styling helper."""

    def __init__(self, mapping: dict):
        super().__init__(mapping)

    @classmethod
    def create(
        cls,
        custom: dict | None = None,
        initial=None,
        xs=None,
        sm=None,
        md=None,
        lg=None,
        xl=None,
    ) -> Self:
        """Create a new instance of the helper. Only provide a custom component OR use named props.

        Args:
            custom: Custom mapping using CSS values or variables.
            initial: Styling when in the inital width
            xs: Styling when in the extra-small width
            sm: Styling when in the small width
            md: Styling when in the medium width
            lg: Styling when in the large width
            xl: Styling when in the extra-large width

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
                    for k, v in zip(["0px", *breakpoints_values], thresholds)
                    if v is not None
                }
            )


breakpoints = Breakpoints.create
