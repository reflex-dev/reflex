import reflex as rx

from reflex_docs.pages.docs import hosting as hosting_page
from reflex_docs.pages.docs_landing.views.layout import SECTION, section_heading
from reflex_docs.pages.docs_landing.views.link_item import link_item


def self_hosting_section() -> rx.Component:
    return rx.el.section(
        section_heading(
            "Self-Hosting", "Learn how to self-host your applications with Reflex."
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
        class_name=f"{SECTION} border-t border-border-subtle",
    )
