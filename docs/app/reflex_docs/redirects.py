"""Redirect mappings for the docs site."""

from collections.abc import Iterable

from reflex_site_shared.route import Route


def get_redirects(routes: Iterable[Route]) -> list[tuple[str, str]]:
    """Return static redirects and aliases generated from registered routes.

    Args:
        routes: Route subset used to generate ``/ai-builder/`` aliases.

    Returns:
        All static redirects plus aliases for the supplied route subset.
    """
    return [
        ("/ai/integrations/ai-onboarding/", "/ai/integrations/agent-toolkit/"),
        ("/ai-builder/integrations/ai-onboarding/", "/ai/integrations/agent-toolkit/"),
        *[
            (route.path.replace("/ai/", "/ai-builder/", 1), route.path)
            for route in routes
            if route.path.startswith("/ai/")
        ],
        ("/ai/features/ide/", "/ai/features/editor-modes/"),
        ("/ai-builder/features/ide/", "/ai/features/editor-modes/"),
        ("/ai/features/customization/", "/ai/features/design-systems/"),
        ("/ai-builder/features/customization/", "/ai/features/design-systems/"),
        ("/hosting/adding-members/", "/hosting/project-members/"),
        ("/hosting/projects/", "/hosting/project-members/"),
        ("/authentication/authentication-overview/", "/enterprise/auth/overview/"),
        ("/substates/overview/", "/state-structure/overview/"),
        ("/substates/component-state/", "/state-structure/component-state/"),
    ]
