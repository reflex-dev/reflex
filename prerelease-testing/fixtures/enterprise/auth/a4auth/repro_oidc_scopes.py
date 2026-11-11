"""Reproduce OIDC extra-scope setup against a removed State metadata attribute."""

import importlib.metadata
import json

from reflex_enterprise.auth.oidc.state import GenericOIDCAuthState


def main() -> None:
    """Attempt the same extra-scope setup that AuthPlugin performs at compile."""
    print(
        json.dumps(
            {
                "reflex": importlib.metadata.version("reflex"),
                "enterprise": importlib.metadata.version("reflex-enterprise"),
            }
        )
    )
    print(
        json.dumps(
            {
                name: hasattr(GenericOIDCAuthState, name)
                for name in ("backend_vars", "base_vars", "computed_vars")
            }
        )
    )
    GenericOIDCAuthState._set_extra_scopes(["offline_access"])
    print("OIDC scope setup passed")


if __name__ == "__main__":
    main()
