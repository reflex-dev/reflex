"""SEO metadata helpers for docs routes."""

GENERIC_DESCRIPTION_TEMPLATE = "{subject}: documentation, examples, and reference for building Python web applications with Reflex."

# Summaries for generated catalogs, reference pages, and pages without usable prose.
PAGE_DESCRIPTIONS = {
    "library": "Browse Reflex UI components for forms, layouts, data display, charts, and media, with Python examples and prop references.",
    "custom-components": "Explore community-built Reflex components and discover reusable Python interfaces for React libraries and custom UI elements.",
    "recipes": "Find reusable Reflex recipes for page layouts, content, and authentication, with examples you can adapt for your Python app.",
    "api-reference/app": "Configure rx.App, register pages, and customize application behavior with the App class attributes and methods reference.",
    "api-reference/component": "Explore the Component API for creating Reflex UI elements, managing props, and customizing component rendering and behavior.",
    "api-reference/componentstate": "Use ComponentState to pair reusable Reflex components with their own state. Explore its class attributes and methods.",
    "api-reference/event": "Explore the Event API for Reflex event instances, including event names, payloads, and client tokens.",
    "api-reference/eventspec": "Explore EventSpec, the representation of a Reflex event handler invocation, including its arguments and event actions.",
    "api-reference/eventhandler": "Explore EventHandler attributes and methods for wrapping Python functions as Reflex event handlers.",
    "api-reference/statemanager": "Explore StateManager methods for retrieving and managing Reflex state associated with client sessions.",
    "api-reference/config": "Reference Reflex configuration fields, defaults, and environment variable overrides for running and deploying your app.",
    "api-reference/importvar": "Explore ImportVar fields for describing JavaScript imports used by Reflex components, including aliases and default imports.",
    "api-reference/state": "Explore the State class API for managing reactive app data, computed values, event handlers, and state updates in Reflex.",
    "api-reference/var": "Explore the Var API for representing frontend expressions and working with typed reactive values in Reflex.",
    "api-reference/environment-variables": "Look up Reflex environment variables, their types, and defaults to configure development, builds, and application runtime behavior.",
    "hosting/cli/deploy": "Reference the Reflex Cloud deploy command and its options for publishing an application from your terminal.",
    "hosting/cli/projects": "Reference Reflex Cloud CLI project commands and options for organizing hosted applications into projects.",
    "hosting/cli/scan": "Run a Reflex-aware security review of your app source with the Cloud CLI scan command. Reference its options and output controls.",
    "hosting/cli/apps": "Reference Reflex Cloud CLI app commands and options for managing your hosted applications from the terminal.",
    "hosting/cli/config": "Reference Reflex Cloud CLI configuration commands and options for managing your local hosting configuration.",
    "hosting/cli/secrets": "Reference Reflex Cloud CLI secret commands and options for managing sensitive values used by hosted applications.",
    "hosting/cli/regions": "Reference Reflex Cloud CLI region commands to explore available deployment locations for your applications.",
    "hosting/cli/providers": "Reference Reflex Cloud CLI provider commands and options for working with supported cloud providers.",
    "hosting/cli/login": "Reference Reflex Cloud CLI login options for authenticating your terminal with your hosting account.",
    "hosting/cli/vmtypes": "Reference Reflex Cloud CLI VM type commands to explore compute options for hosted applications.",
    "overview": "Explore Reflex Cloud hosting and find guides for deploying applications, managing secrets, and monitoring your apps.",
    "ai/figma": "Check the status of the planned Figma integration for Reflex Build. This integration is coming soon.",
    "ai/integrations/overview": "Browse Reflex Build integrations for databases, AI services, and external tools, and find setup guides for connecting your app.",
    "enterprise/components": "Explore enterprise Reflex components for advanced data grids, charts, editors, and interactive workflows, with guides and examples.",
    "library/typography/em": "Add semantic emphasis to inline text with rx.text.em. See a Python example of emphasizing words within a Reflex text component.",
    "library/typography/quote": "Mark short inline quotations with rx.text.quote. See how to include quoted text within a Reflex text component.",
    "wrapping-react/step-by-step": "Wrap a React color picker in Reflex, declare typed props and events, connect Python state, and troubleshoot imports and browser-only rendering.",
}


def truncate_meta_description(description: str, max_len: int = 155) -> str:
    """Return a search-snippet-safe meta description.

    Args:
        description: The candidate description.
        max_len: The maximum output length.

    Returns:
        The original description when it fits, otherwise a word-boundary
        truncation with a trailing ellipsis.
    """
    description = " ".join(description.split()).strip()
    if len(description) <= max_len:
        return description
    # Reserve one character for the trailing ellipsis so the result never
    # exceeds max_len, even when the leading slice has no word boundary.
    truncated = description[: max_len - 1].rsplit(" ", 1)[0].rstrip(",.;:")
    return f"{truncated}…"


def docs_metadata(path: str, title: str, description: str | None) -> tuple[str, str]:
    """Build distinct search snippets using the page's product hierarchy.

    Args:
        path: The app-relative documentation route.
        title: The page heading.
        description: A summary extracted from the document, when available.

    Returns:
        The search title and description.
    """
    acronyms = {
        "ai": "AI",
        "api": "API",
        "cli": "CLI",
        "html": "HTML",
        "css": "CSS",
        "mcp": "MCP",
        "sdk": "SDK",
    }
    parents = [
        " ".join(acronyms.get(word, word.capitalize()) for word in part.split("-"))
        for part in path.strip("/").split("/")[:-1]
    ]
    if title.lower() == "index" and parents:
        title = " ".join(
            acronyms.get(word, word.capitalize())
            for word in path.strip("/").split("/")[-1].split("-")
        )
    title = " ".join(acronyms.get(word.lower(), word) for word in title.split())
    context = [
        parent for parent in reversed(parents) if parent.lower() != title.lower()
    ]
    subject = " · ".join([title, *context])
    route = path.strip("/")
    if route == "changelog" or route.startswith("changelog/"):
        package = route.removeprefix("changelog/") if "/" in route else "reflex"
        fallback = f"Read {package} release notes, including new features, bug fixes, and breaking changes, before upgrading your project."
    else:
        fallback = PAGE_DESCRIPTIONS.get(route)
    summary = (
        description or fallback or GENERIC_DESCRIPTION_TEMPLATE.format(subject=subject)
    )
    return f"{subject} · Reflex Docs", truncate_meta_description(summary)
