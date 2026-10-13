import reflex as rx

from reflex_docs.pages.docs import hosting as hosting_page
from reflex_docs.pages.docs_landing.views.layout import SECTION
from reflex_docs.pages.docs_landing.views.link_item import link_item


def hosting_section() -> rx.Component:
    return rx.el.section(
        rx.el.div(
            rx.el.h2(
                "Cloud",
                class_name="font-heading text-3xl font-light leading-[1.12] tracking-[-0.035em] text-foreground sm:text-4xl",
            ),
            rx.el.p(
                "Learn how to host your applications with Reflex Hosting.",
                class_name="max-w-lg text-base font-normal leading-7 text-muted-foreground",
            ),
            class_name="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between lg:gap-12",
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
        class_name=f"{SECTION} flex flex-col gap-8 border-t border-border-subtle sm:gap-10",
    )
