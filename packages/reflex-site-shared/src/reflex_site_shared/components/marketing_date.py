"""Publication dates using the browser's built-in formatter instead of Moment."""

import reflex as rx


class MarketingDate(rx.Component):
    """Format publication dates consistently in the browser."""

    library = "$/public/components/marketing-date"
    tag = "MarketingDate"
    value: rx.Var[str]
    compact: rx.Var[bool] = False


marketing_date = MarketingDate.create
