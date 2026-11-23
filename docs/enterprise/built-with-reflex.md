# Built with Reflex Badge

The "Built with Reflex" badge appears in the bottom right corner of apps using reflex-enterprise components.

## Removing the Badge

To remove the badge, you need the Pro tier or above when deploying to Reflex Cloud, or the Team tier or above when self-hosting.

## Configuration

```python
import reflex_enterprise as rxe

config = rxe.Config(
    show_built_with_reflex=False,  # Requires paid tier
)
```