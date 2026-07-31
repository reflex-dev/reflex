# Custom Domains

Add a domain you control to a deployed Reflex Cloud app.

```python exec
import reflex as rx
```

## Add the Domain

1. Open **Deployments** and select the app.
2. Select **Custom Domain**.
3. Enter the domain, such as `app.example.com`.
4. Select **Add domain**.

```python eval
rx.image(
    src="https://web.reflex-assets.dev/docs-preview/hosting/custom_domain.webp",
    alt="Custom domain configuration and DNS records for a hosted app",
    class_name="rounded-md h-auto mb-4",
    border=f"0.81px solid {rx.color('slate', 5)}",
)
```

## Change DNS Records

After the domain is added, Reflex shows the exact DNS records required for that app. Add every displayed record at the DNS provider that manages the domain.

- Copy the host and value exactly.
- Some DNS providers automatically append the root domain; avoid entering it twice.
- Remove or update an existing conflicting record only after confirming it belongs to the same hostname.

Use the records shown in the current dashboard rather than values from an example or an older deployment.

## Verify

Return to **Custom Domain** and check verification. DNS propagation can take from a few minutes to several hours.

If verification fails:

- Confirm the record type, host, and value.
- Check for a duplicate or conflicting record.
- Verify that the DNS provider did not append the domain twice.
- Wait for propagation and retry.

Once verified, the domain appears on the app's **Deployment** page.
