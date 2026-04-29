from ..state import SideBarItem
from .item import create_item


def get_sidebar_items_ai_builder_overview():
    from reflex_docs.pages.docs import ai_builder

    return [
        create_item(
            "Overview",
            children=[
                ai_builder.overview.best_practices,
                ai_builder.overview.what_is_reflex_build,
                ai_builder.overview.tutorial,
                ai_builder.overview.templates,
            ],
        ),
        create_item(
            "Features",
            children=[
                ai_builder.features.ide,
                ai_builder.features.editor_modes,
                ai_builder.features.file_tree,
                ai_builder.features.restore_checkpoint,
                ai_builder.features.secrets,
                ai_builder.features.installing_external_packages,
                ai_builder.features.integration_shortcut,
                ai_builder.features.connect_to_github,
                ai_builder.features.knowledge,
                ai_builder.features.image_as_prompt,
                # ai_builder.features.automated_testing,
                ai_builder.features.customization,
            ],
        ),
        create_item(
            "App Lifecycle",
            children=[
                ai_builder.app_lifecycle.general,
                ai_builder.app_lifecycle.fork_app,
                ai_builder.app_lifecycle.deploy_app,
                ai_builder.app_lifecycle.download_app,
                ai_builder.app_lifecycle.copy_app,
                ai_builder.app_lifecycle.share_app,
            ],
        ),
        # create_item(
        #     "Integrations",
        #     children=[
        #         ai_builder.integrations.overview,
        #         ai_builder.integrations.github,
        #         ai_builder.integrations.database,
        #         ai_builder.integrations.databricks,
        #         ai_builder.integrations.azure_auth,
        #         ai_builder.integrations.okta_auth,
        #         ai_builder.integrations.google_auth,
        #         ai_builder.integrations.open_ai,
        #     ],
        # ),
    ]


def get_ai_builder_integrations():
    from reflex_docs.pages.docs import ai_builder

    return [
        create_item(
            "First Class Integrations",
            children=[
                ai_builder.integrations.overview,
                ai_builder.integrations.anthropic,
                ai_builder.integrations.aws,
                ai_builder.integrations.azure_auth,
                ai_builder.integrations.cartesia,
                ai_builder.integrations.cohere,
                ai_builder.integrations.database,
                ai_builder.integrations.databricks,
                ai_builder.integrations.descope,
                ai_builder.integrations.gemini,
                ai_builder.integrations.github,
                ai_builder.integrations.google_auth,
                ai_builder.integrations.groq,
                ai_builder.integrations.hubspot,
                ai_builder.integrations.hugging_face,
                ai_builder.integrations.langchain,
                ai_builder.integrations.linear,
                ai_builder.integrations.notion,
                ai_builder.integrations.okta_auth,
                ai_builder.integrations.openai,
                ai_builder.integrations.perplexity,
                ai_builder.integrations.replicate,
                ai_builder.integrations.resend,
                ai_builder.integrations.roboflow,
                ai_builder.integrations.stripe,
                ai_builder.integrations.supabase,
                ai_builder.integrations.twilio,
            ],
        ),
        create_item(
            "Python Libraries",
            children=[
                ai_builder.python_libraries,
            ],
        ),
        create_item(
            "APIs",
            children=[
                ai_builder.apis,
            ],
        ),
        create_item(
            "Webhooks",
            children=[
                ai_builder.webhooks,
            ],
        ),
        create_item(
            "URLs",
            children=[
                ai_builder.urls,
            ],
        ),
        create_item(
            "Databases",
            children=[
                ai_builder.integrations.database,
            ],
        ),
        create_item(
            "Files",
            children=[
                ai_builder.files,
            ],
        ),
        create_item(
            "Images",
            children=[
                ai_builder.images,
            ],
        ),
        create_item(
            "Figma",
            children=[
                ai_builder.figma,
            ],
        ),
    ]


def get_sidebar_items_ai_onboarding():
    from reflex_docs.pages.docs import ai_builder

    return [
        SideBarItem(
            names="AI Onboarding",
            link=ai_builder.integrations.ai_onboarding.path,
        ),
    ]


def get_sidebar_items_mcp():
    from reflex_docs.pages.docs import ai_builder

    return [
        SideBarItem(
            names="Overview",
            link=ai_builder.integrations.mcp_overview.path,
        ),
        SideBarItem(
            names="Installation",
            link=ai_builder.integrations.mcp_installation.path,
        ),
    ]


def get_sidebar_items_skills():
    from reflex_docs.pages.docs import ai_builder

    return [
        SideBarItem(
            names="Overview",
            link=ai_builder.integrations.skills.path,
        ),
    ]


ai_builder_overview_items = get_sidebar_items_ai_builder_overview()
ai_builder_integrations = get_ai_builder_integrations()
ai_onboarding_items = get_sidebar_items_ai_onboarding()
mcp_items = get_sidebar_items_mcp()
skills_items = get_sidebar_items_skills()
