---
title: Deploying to Production
---

_New in reflex-enterprise v0.9.1._

# Deploying to Production

The [quickstart](/docs/enterprise/auth/overview/) works on `localhost` out of
the box, but moving the same app to a real deployment against a real identity
provider (IdP) introduces a few hard requirements: the app must be served over
HTTPS, the callback URL you register at the IdP must match exactly, and behind a
reverse proxy the public origin must be reported correctly. This page covers
each requirement and ends with a troubleshooting reference keyed on the literal
errors you'll see.

## HTTPS is required

All four auth cookies — access token, ID token, refresh token, and granted
scopes — are issued `Secure; SameSite=Strict; HttpOnly`. These attributes are
fixed and **not configurable**. Because browsers drop `Secure` cookies sent over
plain HTTP, the app **must** be served to the browser over HTTPS in any
non-localhost deployment. Local `reflex run` works without TLS only because
browsers exempt `localhost` from the `Secure` rule.

```md alert warning
# Symptom: an apparent login loop
If the app is served over plain HTTP on a non-localhost host, the IdP redirect to `/callback` completes, but the browser silently discards the `Secure` auth cookies. The user is never authenticated and is bounced straight back to `/login`. The root cause is the dropped cookie, **not** a misconfigured IdP — serve the app over HTTPS to fix it.
```

Behind a TLS-terminating reverse proxy, terminate TLS at the proxy and ensure
the browser-facing origin is `https`. The browser — not the backend — enforces
`Secure`, so the connection the browser sees is what matters.

## Registering the callback URL

The OAuth redirect URI is built at runtime from the browser-visible page URL,
with the path replaced by the plugin's `auth_callback_endpoint` (`/callback` by
default). It is **not** a config value: its scheme, host, and port follow the
request origin. This is the concrete version of step 3 in the
[overview](/docs/enterprise/auth/overview/).

Register the **full** callback URL — scheme, host, port, and path — as an
allowed redirect URI in your IdP's client settings, and register every origin
you actually use:

```bash
http://localhost:3000/callback      # dev
https://your-app.com/callback       # prod
```

A redirect URI that doesn't exactly match a registered value produces the IdP's
most common error, `redirect_uri_mismatch`.

```md alert info
# Behind a TLS-terminating proxy
Make sure the app perceives the request as `https` (correct forwarded-proto handling at the proxy). Otherwise it builds an `http://...` redirect URI that won't match the `https://...` value you registered, and the IdP rejects it.
```

## Behind a reverse proxy / at scale

Two properties of the auth model determine how it behaves behind a proxy or
across multiple replicas.

**The public origin must be correct.** Both the redirect URI and the post-login
index URI are derived from the browser-visible request origin, so a reverse
proxy must forward the real public scheme and host. If the proxy reports
`http` or an internal hostname, the runtime redirect URI won't match what's
registered at the IdP. The backend (`api_url`) must also be reachable from the
browser: after login the client makes a credentialed request to
`/_reflex/cookies/sync` to persist the auth cookies.

**No sticky sessions are needed.** Auth secrets live entirely in client-side
HTTP cookies (a LocalStorage flag signals other tabs to re-pull the cookies) —
there is no server-side session store. You can therefore run multiple backend replicas
behind a load balancer with no sticky-session configuration; just give every
replica the same OIDC client configuration (the same `OIDC_*` / `{PROVIDER}_*`
environment variables).

## Connecting a real identity provider

Every provider is discovered from its issuer's
`.well-known/openid-configuration`, always runs the Authorization Code flow with
PKCE (`S256`), and requests `openid email profile` by default. The
`client_secret` is optional, so each IdP client can be either **public** (PKCE
only, no secret) or **confidential** (PKCE plus a secret). The mechanics are the
same for every IdP — only the issuer URL changes.

A worked example with Google:

1. In the Google Cloud console, create an **OAuth 2.0 Client ID** of type **Web
   application**.
2. Add your callback URLs (see
   [registering the callback URL](#registering-the-callback-url)) as **Authorized
   redirect URIs**, e.g. `https://your-app.com/callback`.
3. Configure the app. Google issues a client secret, so run the client as
   confidential by setting all three variables (omit `OIDC_CLIENT_SECRET` to run
   PKCE-public instead):

```bash
OIDC_ISSUER_URI=https://accounts.google.com
OIDC_CLIENT_ID=your-client-id.apps.googleusercontent.com
OIDC_CLIENT_SECRET=your-client-secret
```

4. To receive group claims for authorization checks, add the relevant scope via
   `extra_scopes` (see
   [providers](/docs/enterprise/auth/providers/#scopes-and-refresh-tokens)).

Other IdPs follow the same pattern with their own issuer URL:

| IdP | `OIDC_ISSUER_URI` form |
| --- | --- |
| Google | `https://accounts.google.com` |
| Azure AD | `https://login.microsoftonline.com/<tenant>/v2.0` |
| Auth0 | `https://<tenant>.auth0.com` |
| Okta | `https://<org>.okta.com` |

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| `redirect_uri_mismatch` (from the IdP) | The redirect URI is derived from the request scheme + host + `auth_callback_endpoint`; the value registered at the IdP doesn't match it exactly. | Register the exact callback URL; behind a proxy, make sure the app sees the public scheme and host. |
| `invalid_client` (from the IdP at token exchange) | The IdP client is confidential, but `OIDC_CLIENT_SECRET` is unset — it silently defaults to empty, so there's no local error. | Set the client secret, or switch the IdP client to public / PKCE. |
| Logged in but bounced back to `/login` (login loop) | `Secure; SameSite=Strict` cookies are dropped over plain HTTP on a non-localhost host. | Serve the app over HTTPS (`localhost` is exempt). |
| `ConfigError` at startup | Either a plain `rx.App()` was used with the plugin, or two or more providers both fall back to the shared `OIDC_*` config for issuer or client id. | Use `rxe.App()`; for multiple providers, set provider-specific `{PROVIDER}_*` variables (see [providers](/docs/enterprise/auth/providers/#multiple-providers)). |

## Related

- [Authentication overview](/docs/enterprise/auth/overview/) — the quickstart and the end-to-end login flow.
- [Secure by default](/docs/enterprise/auth/secure-by-default/) — the enforcement model and authorization checks.
- [Providers](/docs/enterprise/auth/providers/) — provider config, environment variables, scopes, and multi-provider setups.
- [Custom pages](/docs/enterprise/auth/custom-pages/) — replace the login / callback / logout / forbidden page builders.
- [Testing](/docs/enterprise/auth/testing/) — exercise guarded surfaces and the full OIDC flow against a mock IdP.
