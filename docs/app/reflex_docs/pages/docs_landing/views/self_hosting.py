import reflex as rx

from reflex_docs.pages.docs import hosting as hosting_page
from reflex_docs.pages.docs_landing.views.link_item import faded_borders, link_item


def self_hosting_section() -> rx.Component:
    return rx.el.section(
        rx.el.div(
            rx.el.h2(
                "Self-Hosting",
                class_name="text-foreground text-3xl font-medium",
            ),
            rx.el.p(
                "Learn how to self-host your applications with Reflex.",
                class_name="text-muted-foreground text-sm font-[475]",
            ),
            class_name="flex flex-col gap-4",
        ),
        rx.el.div(
            faded_borders(),
            link_item(
                "ServerStack01Icon",
                "Run Reflex App in Dockerized Environment",
                "Build and deploy Reflex apps in Docker containers.",
                hosting_page.self_hosting.path,
            ),
            link_item(
                "BrowserIcon",
                "Deploy to Databricks and Snowflake",
                "Integrate and deploy Reflex apps to Databricks or Snowflake.",
                hosting_page.databricks.path,
                has_padding_left=True,
            ),
            class_name="grid grid-cols-1 lg:grid-cols-2 border-t border-border-subtle relative",
        ),
        class_name="flex flex-col gap-10 max-lg:text-center relative max-w-(--landing-layout-max-width) mx-auto w-full justify-start lg:mb-24 mb-10 max-xl:px-6 overflow-hidden max-lg:pt-10",
    )
