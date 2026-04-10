"""Cal.com integration components for Reflex UI."""

import os

import reflex as rx

DEFAULT_CAL_FORM = os.getenv(
    "DEFAULT_CAL_FORM", "forms/f87bd9b2-b339-4915-b4d4-0098e2db4394"
)


def get_cal_attrs(cal_form: str = DEFAULT_CAL_FORM, **kwargs):
    """Get Cal.com attributes for embedding.

    Args:
        cal_form: The Cal.com form link
        **kwargs: Additional attributes to include

    Returns:
        Dictionary of Cal.com attributes
    """
    attrs = {
        "data-cal-link": cal_form,
        "data-cal-namespace": "talk",
        "data-cal-config": rx.color_mode_cond(
            '{"theme":"light","layout":"month_view"}',
            '{"theme":"dark","layout":"month_view"}',
        ),
    }
    attrs.update(kwargs)
    return attrs


class CalcomPopupEmbed(rx.Fragment):
    """Cal.com popup embed component using React hooks."""

    def add_imports(self) -> rx.ImportDict:
        """Add required imports for Cal.com embed.

        Returns:
            Dictionary of imports needed for the component
        """
        return {
            "react": rx.ImportVar("useEffect"),
            "@calcom/embed-react@1.5.3": rx.ImportVar("getCalApi"),
        }

    def add_hooks(self) -> list[str | rx.Var[object]]:
        """Add React hooks for Cal.com API initialization.

        Returns:
            List of hook code strings to initialize Cal.com
        """
        return [
            """
useEffect(() => {
  (async function () {
    const cal = await getCalApi({ namespace: "talk" });
    cal("ui", {
      hideEventTypeDetails: false,
      layout: "month_view",
      styles: {
        branding: { brandColor: "#6F56CF" },
      },
    });
  })();
}, []);
""",
        ]


calcom_popup_embed = CalcomPopupEmbed.create


class CalEmbed(rx.Component):
    """Cal.com embed component using the Cal React component."""

    library = "@calcom/embed-react@1.5.3"
    tag = "Cal"
    is_default = True

    cal_link: rx.Var[str]

    config: rx.Var[dict]

    @classmethod
    def create(
        cls,
        cal_link: str = DEFAULT_CAL_FORM,
        config: dict | None = None,
        **props,
    ):
        """Create a Cal.com embed component.

        Args:
            cal_link: The Cal.com link (e.g., "forms/...")
            config: Configuration object for Cal.com (e.g., {"theme": "light"})
            **props: Additional props to pass to the component

        Returns:
                The component.
        """
        return super().create(
            cal_link=cal_link,
            config=config,
            **props,
        )


cal_embed = CalEmbed.create
