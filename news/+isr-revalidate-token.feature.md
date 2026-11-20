The `reflex.isr` page server serves `POST /_isr/revalidate` only when the `REFLEX_ISR_REVALIDATE_TOKEN` environment variable is set, and requires that token in the `X-Reflex-ISR-Token` header.
