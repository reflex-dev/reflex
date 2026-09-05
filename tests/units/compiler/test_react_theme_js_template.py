"""Regression tests for the react-theme.js frontend template."""

from pathlib import Path

REACT_THEME_JS_TEMPLATE = (
    Path(__file__).parents[3]
    / "packages/reflex-base/src/reflex_base/.templates/web/utils/react-theme.js"
)


def _theme_provider_body() -> str:
    """Return the source of the ``ThemeProvider`` component.

    Returns:
        The ``ThemeProvider`` function body.
    """
    content = REACT_THEME_JS_TEMPLATE.read_text()
    start = content.index("export function ThemeProvider")
    end = content.index("export function useTheme", start)
    return content[start:end]


def test_theme_provider_memoizes_context_values() -> None:
    """The provider values must be memoized.

    Every consumer of ``ColorModeContext`` re-renders when the context value
    identity changes, so a freshly built object on each ``ThemeProvider``
    render fans a re-render out across the whole app. Regression guard for
    https://github.com/reflex-dev/reflex/pull/6180.
    """
    body = _theme_provider_body()

    assert "const themeContextValue = useMemo(" in body, (
        "ThemeContext value should be memoized."
    )
    assert "const colorModeContextValue = useMemo(" in body, (
        "ColorModeContext value should be memoized."
    )
    assert "[themeContextValue, colorModeContextValue, children]" in body, (
        "ThemeProvider should return a memoized element keyed on its context values."
    )


def test_theme_provider_color_mode_setters_are_stable() -> None:
    """``setColorMode``/``toggleColorMode`` must not be rebuilt on every render.

    They are handed to consumers through ``ColorModeContext``, so an unstable
    identity defeats the memoization of the context value itself.
    """
    body = _theme_provider_body()

    assert "const setColorMode = useCallback(" in body
    assert "const toggleColorMode = useCallback(" in body


def test_theme_provider_media_query_listener_is_mount_only() -> None:
    """The system-preference listener must be attached once on mount.

    Without a dependency array the effect tore down and re-added the
    ``matchMedia`` listener on every render of ``ThemeProvider``.
    """
    body = _theme_provider_body()

    listener_effect = body[
        body.index('window.matchMedia("(prefers-color-scheme: dark)")') :
    ]
    cleanup_end = listener_effect.index("mediaQuery.removeEventListener")
    assert (
        listener_effect[cleanup_end:]
        .lstrip()
        .startswith(
            'mediaQuery.removeEventListener("change", handleChange);\n    };\n  }, []);'
        )
    ), "the media-query effect should declare an empty dependency array."
