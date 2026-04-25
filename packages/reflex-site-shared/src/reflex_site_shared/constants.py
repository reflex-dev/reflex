"""Constants module."""

import os

CHANGELOG_URL = "https://github.com/reflex-dev/reflex/releases"
CONTRIBUTING_URL = "https://github.com/reflex-dev/reflex/blob/main/CONTRIBUTING.md"
DISCUSSIONS_URL = "https://github.com/orgs/reflex-dev/discussions"
GITHUB_STARS = 28000
GITHUB_URL = "https://github.com/reflex-dev/reflex"
JOBS_BOARD_URL = "https://www.ycombinator.com/companies/reflex/jobs"
REFLEX_ASSETS_CDN = "https://web.reflex-assets.dev/"
SCREENSHOT_BUCKET = "https://pub-c14a5dcf674640a6b73fded32bad72ca.r2.dev/"
INTEGRATIONS_IMAGES_URL = "https://raw.githubusercontent.com/reflex-dev/integrations-docs/refs/heads/main/images/logos/"
REFLEX_BUILD_URL = os.getenv("REFLEX_BUILD_URL", "https://build.reflex.dev/")
PIP_URL = "https://pypi.org/project/reflex"
GITHUB_URL = "https://github.com/reflex-dev/reflex"
LINKEDIN_URL = "https://www.linkedin.com/company/reflex-dev"
OLD_GITHUB_URL = "https://github.com/pynecone-io/pynecone"
GITHUB_DISCUSSIONS_URL = "https://github.com/orgs/reflex-dev/discussions"
FORUM_URL = "https://forum.reflex.dev"
TWITTER_URL = "https://twitter.com/getreflex"
DISCORD_URL = "https://discord.gg/T5WSbC2YtQ"
ROADMAP_URL = "https://github.com/reflex-dev/reflex/issues/2727"
STATUS_WEB_URL = "https://status.reflex.dev"

REFLEX_URL = "https://reflex.dev/"
REFLEX_DOMAIN_URL = "https://reflex.dev/"
REFLEX_DOMAIN = "reflex.dev"
TWITTER_CREATOR = "@getreflex"


API_BASE_URL_LOOPS: str = "https://app.loops.so/api/v1"
REFLEX_DEV_WEB_NEWSLETTER_FORM_WEBHOOK_URL: str = "https://hkdk.events/t0qopjbznnp2fr"
REFLEX_DEV_WEB_GENERAL_FORM_FEEDBACK_WEBHOOK_URL: str = os.environ.get(
    "REFLEX_DEV_WEB_GENERAL_FORM_FEEDBACK_WEBHOOK_URL", ""
)
RECENT_BLOGS_API_URL: str = os.environ.get(
    "RECENT_BLOGS_API_URL", "https://reflex.dev/api/v1/recent-blogs"
)


CHECKLY_API_BASE_URL: str = "https://api.checklyhq.com/v1"
CHECKLY_ACCOUNT_ID = os.environ.get("CHECKLY_ACCOUNT_ID", "")
CHECKLY_API_KEY = os.environ.get("CHECKLY_API_KEY", "")
CHECKLY_CHECK_GROUP_ID = os.environ.get("CHECKLY_CHECK_GROUP_ID", "")
