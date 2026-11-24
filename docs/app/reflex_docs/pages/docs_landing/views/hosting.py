import reflex as rx

from reflex_docs.pages.docs import hosting as hosting_page
from reflex_docs.pages.docs_landing.views.layout import SECTION, section_heading
from reflex_docs.pages.docs_landing.views.link_item import link_item


def hosting_section() -> rx.Component:
    return rx.el.section(
        section_heading(
            "Cloud", "Learn how to host your applications with Reflex Hosting."
        ),
        rx.el.div(
            link_item(
                "CloudServerIcon",
                "Deployment",
                "Step-by-step instructions to deploy your Reflex application to the cloud, including configuration and setup guides.",
                hosting_page.deploy_quick_start.path,
            ),
            link_item(
                "LockKeyIcon",
                "Secret Management",
                "How to securely manage sensitive environment variables, API keys, and secrets in Reflex Hosting.",
                hosting_page.secrets_environment_vars.path,
                has_padding_left=True,
            ),
            link_item(
                "EyeIcon",
                "Observability",
                "Monitor your application's health, view logs, and gain insights using Reflex Hosting's integrated observability tools.",
                hosting_page.logs.path,
            ),
            link_item(
                "CodeIcon",
                "Custom Headers and Advanced Options",
                "Configure custom HTTP headers, set caching policies, and explore advanced hosting settings for your Reflex app.",
                hosting_page.deploy_quick_start.path,
                has_padding_left=True,
            ),
            class_name="grid grid-cols-1 gap-4 lg:grid-cols-2",
        ),
        class_name=f"{SECTION} border-t border-border-subtle",
    )
