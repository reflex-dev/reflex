import reflex as rx

from reflex_docs.pages.docs import hosting as hosting_page
from reflex_docs.pages.docs_landing.views.link_item import faded_borders, link_item


def hosting_section() -> rx.Component:
    return rx.el.section(
        rx.el.div(
            rx.el.h2(
                "Cloud",
                class_name="text-m-slate-12 dark:text-m-slate-3 text-3xl font-[575]",
            ),
            rx.el.p(
                "Learn how to host your applications with Reflex Hosting.",
                class_name="text-m-slate-7 dark:text-m-slate-6 text-sm font-[475]",
            ),
            class_name="flex flex-col gap-4",
        ),
        rx.el.div(
            faded_borders(),
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
            class_name="grid grid-cols-1 lg:grid-cols-2 border-t border-m-slate-4 dark:border-m-slate-10 relative",
        ),
        class_name="flex flex-col gap-10 max-lg:text-center relative max-w-(--landing-layout-max-width) mx-auto w-full justify-start max-xl:px-6 lg:mb-24 overflow-hidden",
    )
