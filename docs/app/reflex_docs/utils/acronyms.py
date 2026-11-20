"""Acronym and brand casing shared by docs page titles, sidebar and breadcrumbs."""

import re

# Title-cased words and the spelling the docs show for them.
ACRONYMS: dict[str, str] = {
    "Ag": "AG",
    "Ai": "AI",
    "Api": "API",
    "Apis": "APIs",
    "Aws": "AWS",
    "Cli": "CLI",
    "Css": "CSS",
    "Gcp": "GCP",
    "Github": "GitHub",
    "Html": "HTML",
    "Hubspot": "HubSpot",
    "Id": "ID",
    "Ide": "IDE",
    "Mcp": "MCP",
    "Oidc": "OIDC",
    "Openai": "OpenAI",
    "Sdk": "SDK",
    "Sso": "SSO",
    "Svg": "SVG",
    "Ui": "UI",
    "Url": "URL",
    "Urls": "URLs",
}

_ACRONYM_WORD = re.compile(r"\b(" + "|".join(ACRONYMS) + r")\b")


def uppercase_acronyms(label: str) -> str:
    """Spell the acronyms and brands among a label's words, such as ``Api`` as ``API``.

    Args:
        label: A title-cased label, such as ``Deploy With Github Actions``.

    Returns:
        The label with each listed word replaced, such as
        ``Deploy With GitHub Actions``.
    """
    return _ACRONYM_WORD.sub(lambda match: ACRONYMS[match.group(0)], label)
