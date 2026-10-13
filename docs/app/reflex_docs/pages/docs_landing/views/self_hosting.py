import reflex as rx

from reflex_docs.pages.docs import hosting as hosting_page
from reflex_docs.pages.docs_landing.views.layout import SECTION
from reflex_docs.pages.docs_landing.views.link_item import link_item


def self_hosting_section() -> rx.Component:
    return rx.el.section(
        rx.el.div(
            rx.el.h2(
                "Self-Hosting",
                class_name="font-heading text-3xl font-light leading-[1.12] tracking-[-0.035em] text-foreground sm:text-4xl",
            ),
            rx.el.p(
                "Learn how to self-host your applications with Reflex.",
                class_name="max-w-lg text-base font-normal leading-7 text-muted-foreground",
            ),
            class_name="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between lg:gap-12",
        ),
        rx.el.div(
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
            class_name="grid grid-cols-1 gap-4 lg:grid-cols-2",
        ),
        class_name=f"{SECTION} flex flex-col gap-8 border-t border-border-subtle sm:gap-10",
    )
