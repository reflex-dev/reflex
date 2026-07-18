"""Unit tests for SSR compile output and configuration."""

from __future__ import annotations

import json

from pytest_mock import MockerFixture

import reflex as rx
from reflex.constants import SsrMode
from reflex.utils.frontend_skeleton import (
    _compile_package_json,
    _update_react_router_config,
)


class TestPackageJsonProdCommand:
    """Tests for the package.json prod command based on ssr_mode config."""

    def test_prod_command_ssr(self, mocker: MockerFixture):
        """With ssr_mode=bot_only, prod command is 'node ssr-serve.js'."""
        conf = rx.Config(app_name="test", ssr_mode=SsrMode.BOT_ONLY)
        mocker.patch("reflex.utils.frontend_skeleton.get_config", return_value=conf)

        result = _compile_package_json()
        pkg = json.loads(result)

        assert pkg["scripts"]["prod"] == "node ssr-serve.js"

    def test_prod_command_static(self, mocker: MockerFixture):
        """With ssr_mode=off, prod command is sirv static server."""
        conf = rx.Config(app_name="test", ssr_mode=SsrMode.OFF)
        mocker.patch("reflex.utils.frontend_skeleton.get_config", return_value=conf)

        result = _compile_package_json()
        pkg = json.loads(result)

        assert pkg["scripts"]["prod"].startswith("sirv")
        assert "node ssr-serve.js" not in pkg["scripts"]["prod"]

    def test_ssr_deps_only_when_enabled(self, mocker: MockerFixture):
        """SSR-specific deps are only included when ssr_mode != OFF."""
        ssr_only_deps = ("@react-router/express", "express", "compression")

        for mode in (SsrMode.BOT_ONLY, SsrMode.OFF):
            conf = rx.Config(app_name="test", ssr_mode=mode)
            mocker.patch("reflex.utils.frontend_skeleton.get_config", return_value=conf)
            pkg = json.loads(_compile_package_json())
            deps = pkg["dependencies"]
            for dep in ssr_only_deps:
                if mode != SsrMode.OFF:
                    assert dep in deps, f"{dep} should be present when ssr_mode={mode}"
                else:
                    assert dep not in deps, (
                        f"{dep} should NOT be present when ssr_mode=off"
                    )

    def test_dev_and_export_commands_unchanged(self, mocker: MockerFixture):
        """Dev and export commands are the same regardless of ssr_mode."""
        results = {}
        for mode in (SsrMode.BOT_ONLY, SsrMode.OFF):
            conf = rx.Config(app_name="test", ssr_mode=mode)
            mocker.patch("reflex.utils.frontend_skeleton.get_config", return_value=conf)
            results[mode] = json.loads(_compile_package_json())

        assert (
            results[SsrMode.BOT_ONLY]["scripts"]["dev"]
            == results[SsrMode.OFF]["scripts"]["dev"]
        )
        assert (
            results[SsrMode.BOT_ONLY]["scripts"]["export"]
            == results[SsrMode.OFF]["scripts"]["export"]
        )


class TestReactRouterConfig:
    """Tests for react-router.config.js based on ssr_mode config."""

    def test_ssr_true_in_config(self):
        """With ssr_mode=bot_only, config has ssr: true."""
        conf = rx.Config(app_name="test", ssr_mode=SsrMode.BOT_ONLY)
        result = _update_react_router_config(conf)

        parsed = json.loads(result.removeprefix("export default ").removesuffix(";"))
        assert parsed["ssr"] is True

    def test_ssr_false_in_config(self):
        """With ssr_mode=off, config has ssr: false."""
        conf = rx.Config(app_name="test", ssr_mode=SsrMode.OFF)
        result = _update_react_router_config(conf)

        parsed = json.loads(result.removeprefix("export default ").removesuffix(";"))
        assert parsed["ssr"] is False

    def test_ssr_with_prerender(self):
        """ssr_mode and prerender can coexist."""
        conf = rx.Config(app_name="test", ssr_mode=SsrMode.BOT_ONLY)
        result = _update_react_router_config(conf, prerender_routes=True)

        parsed = json.loads(result.removeprefix("export default ").removesuffix(";"))
        assert parsed["ssr"] is True
        assert parsed["prerender"] is True

    def test_default_ssr_is_false(self):
        """Default config has ssr: false."""
        conf = rx.Config(app_name="test")
        result = _update_react_router_config(conf)

        parsed = json.loads(result.removeprefix("export default ").removesuffix(";"))
        assert parsed["ssr"] is False

    def test_always_mode_enables_ssr(self):
        """With ssr_mode=always, config has ssr: true."""
        conf = rx.Config(app_name="test", ssr_mode=SsrMode.ALWAYS)
        result = _update_react_router_config(conf)

        parsed = json.loads(result.removeprefix("export default ").removesuffix(";"))
        assert parsed["ssr"] is True


class TestTemplateOutput:
    """Tests for the generated template content based on ssr_mode."""

    @staticmethod
    def _set_ssr_mode(mocker: MockerFixture, ssr_mode: SsrMode) -> None:
        """Patch the config the ssr module reads so templates see ``ssr_mode``.

        Args:
            mocker: The pytest-mock fixture.
            ssr_mode: The server-side rendering mode to configure.
        """
        conf = rx.Config(app_name="test", ssr_mode=ssr_mode)
        mocker.patch("reflex.ssr.get_config", return_value=conf)

    @staticmethod
    def _render_root() -> str:
        """Render root template with minimal valid params.

        Returns:
            Rendered template string.
        """
        from reflex.compiler.templates import app_root_template

        return app_root_template(
            imports=[],
            custom_codes=[],
            hooks={},
            window_libraries=[],
            render={"contents": "children"},
            dynamic_imports=set(),
        )

    def test_root_template_has_loader_when_ssr_enabled(self, mocker: MockerFixture):
        """With ssr_mode=bot_only, root.jsx template contains the SSR loader."""
        self._set_ssr_mode(mocker, SsrMode.BOT_ONLY)
        result = self._render_root()

        assert "export async function loader" in result
        assert "useLoaderData" in result
        assert "getBackendURL" in result
        assert "ssrState" in result
        assert "SSR_DATA" in result

    def test_root_template_loader_checks_shell_gen_header(self, mocker: MockerFixture):
        """The SSR loader short-circuits for shell generation requests."""
        self._set_ssr_mode(mocker, SsrMode.BOT_ONLY)
        result = self._render_root()

        assert "x-reflex-shell-gen" in result
        assert "state: null" in result
        # isbot check should NOT be in the loader — bot routing is in ssr-serve.js.
        assert "isbot" not in result

    def test_root_template_no_loader_when_ssr_off(self, mocker: MockerFixture):
        """With ssr_mode=off, root.jsx template has no SSR loader."""
        self._set_ssr_mode(mocker, SsrMode.OFF)
        result = self._render_root()

        assert "export async function loader" not in result
        assert "useLoaderData" not in result
        assert "getBackendURL" not in result
        assert "ssrState" not in result

    def test_context_template_has_ssr_context_when_ssr_enabled(
        self, mocker: MockerFixture
    ):
        """With ssr_mode=bot_only, context.js has SSRContext and ssrHydrated."""
        from reflex.compiler.templates import context_template

        self._set_ssr_mode(mocker, SsrMode.BOT_ONLY)
        result = context_template(
            initial_state={"test_state": {"field_rx_state_": "value"}},
            state_name="test_state",
            client_storage=None,
            is_dev_mode=False,
            default_color_mode='"system"',
        )

        assert "SSRContext" in result
        assert "ssrHydrated" in result
        assert "ssrState = null" in result
        assert "SSRContext.Provider" in result

    def test_context_template_no_ssr_context_when_ssr_off(self, mocker: MockerFixture):
        """With ssr_mode=off, context.js has no SSR-related code."""
        from reflex.compiler.templates import context_template

        self._set_ssr_mode(mocker, SsrMode.OFF)
        result = context_template(
            initial_state={"test_state": {"field_rx_state_": "value"}},
            state_name="test_state",
            client_storage=None,
            is_dev_mode=False,
            default_color_mode='"system"',
        )

        assert "SSRContext" not in result
        assert "ssrHydrated" not in result
        assert "ssrState" not in result

    def test_context_template_ssr_reducer_uses_ssr_state(self, mocker: MockerFixture):
        """With ssr_mode=bot_only, useReducer initializers check ssrState."""
        from reflex.compiler.templates import context_template

        self._set_ssr_mode(mocker, SsrMode.BOT_ONLY)
        result = context_template(
            initial_state={"my_app.state": {"count_rx_state_": 0}},
            state_name="my_app.state",
            client_storage=None,
            is_dev_mode=False,
            default_color_mode='"system"',
        )

        # The SSR-aware reducer initialization pattern.
        assert 'ssrState !== null && ssrState["my_app.state"]' in result

    def test_context_template_static_reducer_no_ssr_state(self, mocker: MockerFixture):
        """With ssr_mode=off, useReducer uses initialState directly."""
        from reflex.compiler.templates import context_template

        self._set_ssr_mode(mocker, SsrMode.OFF)
        result = context_template(
            initial_state={"my_app.state": {"count_rx_state_": 0}},
            state_name="my_app.state",
            client_storage=None,
            is_dev_mode=False,
            default_color_mode='"system"',
        )

        assert 'useReducer(applyDelta, initialState["my_app.state"]' in result
        assert "ssrState" not in result


class TestExtractRouteParams:
    """Tests for the extract_route_params utility function."""

    def test_simple_dynamic_route(self):
        """Single dynamic segment is extracted correctly."""
        from reflex.route import extract_route_params

        result = extract_route_params("/blog/hello-world", "blog/[slug]")
        assert result == {"slug": "hello-world"}

    def test_multiple_dynamic_segments(self):
        """Multiple dynamic segments are extracted correctly."""
        from reflex.route import extract_route_params

        result = extract_route_params("/users/42/posts/99", "users/[id]/posts/[pid]")
        assert result == {"id": "42", "pid": "99"}

    def test_no_dynamic_segments(self):
        """Static route returns empty dict."""
        from reflex.route import extract_route_params

        result = extract_route_params("/about", "about")
        assert result == {}

    def test_root_path(self):
        """Root path with no segments returns empty dict."""
        from reflex.route import extract_route_params

        result = extract_route_params("/", "/")
        assert result == {}

    def test_leading_slash_handling(self):
        """Leading slashes on both path and route are handled."""
        from reflex.route import extract_route_params

        result = extract_route_params("/blog/my-post", "/blog/[slug]")
        assert result == {"slug": "my-post"}

    def test_optional_segment(self):
        """Optional dynamic segment ([[param]]) is extracted."""
        from reflex.route import extract_route_params

        result = extract_route_params("/docs/intro", "docs/[[section]]")
        assert result == {"section": "intro"}

    def test_no_match_shorter_path(self):
        """When path has fewer segments than route, missing params are skipped."""
        from reflex.route import extract_route_params

        result = extract_route_params("/blog", "blog/[slug]")
        assert result == {}

    def test_preserves_special_characters_in_value(self):
        """Values with hyphens and other URL-safe chars are preserved."""
        from reflex.route import extract_route_params

        result = extract_route_params("/blog/my-great-post-2024", "blog/[slug]")
        assert result == {"slug": "my-great-post-2024"}
