```python exec
from pcweb.pages.docs import vars
```

# Authentication Overview

Many apps require authentication to manage users. There are a few different ways to accomplish this in Reflex:

We have solutions that currently exist outside of the core framework:

1. Local Auth: Uses your own database: https://github.com/masenf/reflex-local-auth
2. Google Auth: Uses sign in with Google: https://github.com/masenf/reflex-google-auth
3. Captcha: Generates tests that humans can pass but automated systems cannot: https://github.com/masenf/reflex-google-recaptcha-v2
4. Magic Link Auth: A passwordless login method that sends a unique, one-time-use URL to a user's email: https://github.com/masenf/reflex-magic-link-auth
5. Clerk Auth: A community member wrapped this component and hooked it up in this app: https://github.com/TimChild/reflex-clerk-api
6. Descope Auth: Enables authentication with Descope, supporting passwordless, social login, SSO, and MFA: https://github.com/descope-sample-apps/reflex-descope-auth

If you're using the AI Builder, you can also use the built-in [Authentication Integrations](/docs/ai-builder/integrations/overview) which include Azure Auth, Google Auth, Okta Auth, and Descope.

## Guidance for Implementing Authentication

- Store sensitive user tokens and information in [backend-only vars]({vars.base_vars.path}#backend-only-vars).
- Validate user session and permissions for each event handler that performs an authenticated action and all computed vars or loader events that access private data.
- All content that is statically rendered in the frontend (for example, data hardcoded or loaded at compile time in the UI) will be publicly available, even if the page redirects to a login or uses `rx.cond` to hide content.
- Only data that originates from state can be truly private and protected.
- When using cookies or local storage, a signed JWT can detect and invalidate any local tampering.

More auth documentation on the way. Check back soon!
