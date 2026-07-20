---
tags: Organization
description: Set up single sign-on (SSO) so your team signs in to Reflex through your company identity provider using SAML or OIDC.
---

# Single Sign-On (SSO)

```python exec
import reflex as rx
```

**Single sign-on (SSO)** lets your team sign in to Reflex through your company's identity provider, using the same login as your other work tools. People don't manage separate Reflex credentials, and your IT team controls access from one place.

Reflex supports **SAML** and **OIDC**, so it works with providers such as Okta, Microsoft Entra ID, and Google Workspace. SSO is set up on the **Domains** page (Settings → Domains), where it appears as a Single sign-on card once a domain is verified. It's part of the **Enterprise** plan.

```python eval
rx.image(
    src="https://web.reflex-assets.dev/docs-preview/organization/sso/sso_card.webp",
    alt="The Single sign-on settings card showing an Enable SSO button and status badge",
    class_name="rounded-md h-auto",
)
```

## Before you begin

SSO requires a [verified domain](/docs/ai/organization/domains/). Reflex uses the domain to route the right sign-ins to your provider, so verify it first.

## Setting up SSO

1. Verify your domain (see [Verified domains & auto-join](/docs/ai/organization/domains/)).
2. On the Domains page, find the **Single sign-on** card and select **Enable SSO**.
3. Select **Configure identity provider** and follow the steps to connect your provider and exchange configuration details.

Once configured, the card shows an **Enabled** badge, and members on your verified domain sign in through your provider.

```md alert info
# Who can set up SSO
Only organization admins can enable, configure, or disable single sign-on.
```

## How members sign in

With SSO enabled, people on your verified domain are sent to your provider to sign in. Access is governed there, so removing someone in your provider also removes their access to Reflex.

## Disabling SSO

Use **Disable** on the Single sign-on card. Members go back to signing in with their usual method, and your provider configuration is removed from Reflex.

Disabling SSO doesn't remove anyone; existing members keep their access. You can disable SSO even after a plan change, so your organization is never locked into a provider.

## Related

- [Verified domains & auto-join](/docs/ai/organization/domains/) — the prerequisite for SSO.
- [Members & seats](/docs/ai/organization/members/) — manage who belongs to the organization.
