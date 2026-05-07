# Snowflake

Snowflake is a cloud-based data warehousing platform that enables users to store, manage, and analyze large volumes of data. It provides a scalable and flexible architecture that separates storage and compute resources, allowing for efficient data processing and querying.

## Step 1: Create an OAuth Integration in Snowflake

To enable OAuth for your Snowflake account, an administrator must first register the connected app.

```python exec
import reflex as rx
from flexgen.ui.components.markdown import get_base_component_map

try:
    from flexgen.integrations.snowflake import SnowflakeAuthState
except ImportError:
    redirect_uri = (
        "https://build.reflex.dev/_reflex_oidc_snowflake/authorization-code/callback"
    )
else:
    redirect_uri = SnowflakeAuthState.redirect_uri
```

```python eval
# Actually render the real redirect_uri for copy/paste
get_base_component_map()["pre"](
    f"""CREATE SECURITY INTEGRATION oauth_reflex_build_int
  TYPE = OAUTH
  ENABLED = TRUE
  OAUTH_CLIENT = CUSTOM
  OAUTH_CLIENT_TYPE = 'PUBLIC'
  OAUTH_REDIRECT_URI = '{redirect_uri}'
  OAUTH_ISSUE_REFRESH_TOKENS = TRUE
  OAUTH_REFRESH_TOKEN_VALIDITY = 86400;""",
    language="sql",
)
```

## Step 2: Log in via OAuth

NOTE: you must use a non-admin account to complete the OAuth flow.

# Roadmap 

In the future, this integration will be extended to support external OAuth
flows, service principal authentication, and external network access.