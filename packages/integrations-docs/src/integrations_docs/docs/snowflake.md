# Snowflake

Snowflake is a cloud-based data warehousing platform that enables users to store, manage, and analyze large volumes of data. It provides a scalable and flexible architecture that separates storage and compute resources, allowing for efficient data processing and querying.

The integration supports two authentication methods: **OAuth** (each user logs in with their own Snowflake account) and **Key Pair** (the app authenticates as a shared service user with an RSA key pair — no browser login, tokens never expire mid-session).

## OAuth

### Step 1: Create an OAuth Integration in Snowflake

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

### Step 2: Log in via OAuth

NOTE: you must use a non-admin account to complete the OAuth flow.

## Key Pair

Key-pair authentication connects as a Snowflake service user with a registered RSA public key. Use it when the app should have its own identity instead of a user's OAuth session.

### Step 1: Generate an RSA key pair

```bash
# Private key (unencrypted PKCS#8)
openssl genrsa 2048 | openssl pkcs8 -topk8 -inform PEM -out rsa_key.p8 -nocrypt

# — or encrypted, if your organization requires passphrase-protected keys at rest
openssl genrsa 2048 | openssl pkcs8 -topk8 -v2 aes256 -inform PEM -out rsa_key.p8

# Public key
openssl rsa -in rsa_key.p8 -pubout -out rsa_key.pub
```

### Step 2: Register the public key on a Snowflake user

Run as an administrator, pasting the contents of `rsa_key.pub` without the `BEGIN/END PUBLIC KEY` lines:

```sql
CREATE USER IF NOT EXISTS svc_reflex TYPE = SERVICE DEFAULT_ROLE = <role>;
GRANT ROLE <role> TO USER svc_reflex;

ALTER USER svc_reflex SET RSA_PUBLIC_KEY='MIIBIjANBgkq...';
```

To print the `ALTER USER` statement with the key already formatted on a single line:

```bash
echo "ALTER USER svc_reflex SET RSA_PUBLIC_KEY='$(grep -v '^-----' rsa_key.pub | tr -d '\n')';"
```

The `GRANT ROLE` is required — `DEFAULT_ROLE` only sets a preference and does not grant the role. The role needs `USAGE` on the warehouse, database, and schema the app will query. To verify the registration, compare `RSA_PUBLIC_KEY_FP` from `DESC USER svc_reflex` (Snowflake prefixes it with `SHA256:`) against the output of:

```bash
openssl rsa -pubin -in rsa_key.pub -outform DER | openssl dgst -sha256 -binary | openssl enc -base64
```

### Step 3: Fill in the Key Pair tab

- `SNOWFLAKE_USER`: the user the public key is registered on (e.g. `svc_reflex`)
- `SNOWFLAKE_PRIVATE_KEY`: paste the full contents of `rsa_key.p8` (mangled newlines from copy/paste are fine)
- `SNOWFLAKE_PRIVATE_KEY_PASSPHRASE`: only if the private key is encrypted. It is stored with the integration secrets and used to decrypt the key at connect time. To strip a passphrase from an existing key instead: `openssl pkcs8 -topk8 -in rsa_key.p8 -nocrypt -out rsa_key_plain.p8`

The warehouse and database dropdowns populate once the key pair authenticates, which doubles as a connection check.

If a private key is ever lost or leaked, generate a new pair and re-run the `ALTER USER ... SET RSA_PUBLIC_KEY` — Snowflake also supports `RSA_PUBLIC_KEY_2` for zero-downtime rotation.

# Roadmap 

In the future, this integration will be extended to support external OAuth
flows, service principal authentication, and external network access.
