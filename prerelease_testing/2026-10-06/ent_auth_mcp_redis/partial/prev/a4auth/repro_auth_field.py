"""Reproduce enterprise auth fields failing to become state vars on Reflex 0.10."""

import importlib.metadata
import json

import reflex as rx
import reflex_enterprise as rxe


class AuthFieldState(rx.State):
    """Use the documented field annotation and the enterprise field helper."""

    public_count: rx.Field[int] = rxe.field(0, auth=False)
    secret_count: rx.Field[int] = rxe.field(1, auth=True)
    core_count: rx.Field[int] = rx.field(2)
    public_simple: int = rxe.field(3, auth=False)


def main() -> None:
    """Print types and attempt to render each field independently."""
    print(
        json.dumps(
            {
                "reflex_version": importlib.metadata.version("reflex"),
                "enterprise_version": importlib.metadata.version("reflex-enterprise"),
                "reflex_origin": rx.__file__,
                "enterprise_origin": rxe.__file__,
            }
        )
    )
    failures = []
    for name in ("public_count", "secret_count", "core_count", "public_simple"):
        value = getattr(AuthFieldState, name)
        try:
            rx.text(value)
            result = {
                "field": name,
                "value_type": f"{type(value).__module__}.{type(value).__name__}",
                "rendered": True,
            }
        except Exception as error:
            result = {
                "field": name,
                "value_type": f"{type(value).__module__}.{type(value).__name__}",
                "rendered": False,
                "error": f"{type(error).__name__}: {error}",
            }
            failures.append(name)
        print(json.dumps(result))
    assert not failures, f"Fields failed to render: {failures}"


if __name__ == "__main__":
    main()
