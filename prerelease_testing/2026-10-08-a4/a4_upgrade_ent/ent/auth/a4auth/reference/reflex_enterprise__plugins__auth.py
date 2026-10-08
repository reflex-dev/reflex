"""The ``AuthPlugin``: secure-by-default auth wiring.

Registered in ``rxe.Config(plugins=[...])``. The work is split across the real
compile lifecycle:

- ``pre_compile`` (no app): set the provider/endpoint registries, forward
  ``extra_scopes``, and run the secure-by-default protection sweep.
- ``post_compile`` (gets the app): install the per-event ``AuthMiddleware`` gate.
- ``register_routes`` (called by ``AppEnterprise`` at construction, before the
  compiler snapshots pages): add the friendly ``/login`` / ``/logout`` /
  ``/callback`` / ``/forbidden`` routes so they are compiled, and wire the
  provider registry so compile-time surfaces (``AuthUserState.name`` etc.) bind
  to the configured providers (page builders are evaluated before
  ``pre_compile`` runs).
"""

from __future__ import annotations

import importlib
import os
from typing import TYPE_CHECKING, Any, Callable, Sequence

from reflex.plugins.base import Plugin
from reflex.utils.exceptions import ConfigError

if TYPE_CHECKING:
    from typing import Protocol, TypedDict

    from reflex.components.component import Component
    from typing_extensions import Unpack

    from reflex_enterprise.auth.audit import AuditHook
    from reflex_enterprise.auth.oidc.state import OIDCAuthState
    from reflex_enterprise.auth.types import AuthValue

    class PageBuilderContext(TypedDict):
        """The build context passed to an ``AuthPlugin`` page builder."""

        plugin: AuthPlugin
        providers: Sequence[type[OIDCAuthState]]

    class PageBuilder(Protocol):
        """A page-builder callable for an ``AuthPlugin`` friendly route.

        The build context is passed as keyword arguments. Take all of it with
        ``**context: Unpack[PageBuilderContext]``, or name the entries you need
        and add ``**context: Any`` to ignore the rest (as the default builders
        do).
        """

        __name__: str

        def __call__(self, **context: Unpack[PageBuilderContext]) -> Component: ...


__all__ = ["AuthPlugin"]


def _resolve_import_path(import_path: str) -> Any:
    """Resolve a ``module.attribute`` import path to the named object.

    Args:
        import_path: The dotted path, e.g. ``"my_app.auth.MyOIDCProvider"``.

    Returns:
        The resolved module attribute.
    """
    module_name, _, attr_name = import_path.rpartition(".")
    return getattr(importlib.import_module(module_name), attr_name)


def _call_page_builder(
    fn: PageBuilder, **context: Unpack[PageBuilderContext]
) -> Component:
    """Call a page builder with the plugin build context.

    Args:
        fn: The page builder (custom or default).
        **context: The build context — ``plugin`` and ``providers``.

    Returns:
        The built page component.
    """
    return fn(**context)


class AuthPlugin(Plugin):
    """Secure-by-default OIDC auth plugin."""

    def __init__(
        self,
        *,
        auth: "AuthValue" = True,
        auth_providers: "Sequence[type[OIDCAuthState] | str] | None" = None,
        extra_scopes: Sequence[str] = (),
        login_endpoint: str = "/login",
        logout_endpoint: str = "/logout",
        auth_callback_endpoint: str = "/callback",
        forbidden_endpoint: str = "/forbidden",
        login_page: PageBuilder | str | None = None,
        logout_page: PageBuilder | str | None = None,
        callback_page: PageBuilder | str | None = None,
        forbidden_page: PageBuilder | str | None = None,
        audit: "AuditHook | str | None" = None,
    ) -> None:
        """Configure the plugin.

        Args:
            auth: The secure-by-default value applied to every untagged state
                field, computed var, event handler, and protected page. ``True``
                (the default) requires an authenticated user; ``False`` makes
                everything public; a callable runs as an org-wide authorization
                check (``check(ctx) -> bool | Awaitable[bool]``) after
                authentication succeeds. Explicit per-object ``rxe.*(auth=...)``
                values always override this default. Page-level callable checks
                use this default too (the per-page ``auth=`` argument stays
                bool-only); an authenticated-but-unauthorized page visit is
                redirected to the forbidden endpoint.
            auth_providers: Provider State classes implementing the auth-provider
                Protocol, or ``"module.ClassName"`` import-path strings resolved
                lazily. Defaults to ``[GenericOIDCAuthState]``. The active
                provider is the first with valid ``userinfo``. Use strings in
                ``rxconfig.py``: provider modules cannot be imported there
                (they call ``get_config()`` at import, which loads rxconfig).
            extra_scopes: Forwarded to each provider via ``_set_extra_scopes``.
            login_endpoint: Route that renders the login palette / redirects.
            logout_endpoint: Route that chains the active provider's logout.
            auth_callback_endpoint: Route the IdP redirects back to; chains the
                initiating provider's ``auth_callback``. Register this exact URI
                with your IdP.
            forbidden_endpoint: Route shown when an authenticated user lacks
                permission to view a page.
            login_page: Custom builder for the login page component, or a
                ``"module.function"`` import-path string resolved lazily at
                compile time. The builder receives the ``PageBuilderContext`` as
                keyword arguments — ``plugin`` (this plugin instance) and
                ``providers`` (the resolved provider classes); type it as a
                ``PageBuilder`` (take ``**context: Unpack[PageBuilderContext]``,
                or name the entries you need plus ``**context: Any``). Defaults to
                ``reflex_enterprise.auth.pages.default_login_page``. Only the
                rendered component is customizable — the route's ``on_load``
                wiring stays plugin-owned.
            logout_page: Custom builder for the logout page component (same
                contract as ``login_page``). Defaults to ``default_logout_page``.
            callback_page: Custom builder for the auth-callback page component
                (same contract as ``login_page``). Defaults to
                ``default_callback_page``.
            forbidden_page: Custom builder for the forbidden page component (same
                contract as ``login_page``). Defaults to
                ``default_forbidden_page``.
            audit: An observe-only audit hook called as
                ``audit(action, outcome, context)`` for every auth lifecycle
                action (login started/completed, logout, token refresh, session
                expiry) and every access decision made by the event gate and
                the page guard (field/computed-var withholding is not audited).
                Sync and async callables are both accepted; the return value is
                ignored (the hook can never veto or alter a decision) and a
                raising hook is logged at ERROR while the auth flow proceeds.
                Hooks are awaited inline at the decision point, so they must be
                fast; heavy sinks (HTTP/DB) should enqueue internally and flush
                out-of-band — and note ``event_handler``/``allowed`` fires once
                per protected handler per event, so a busy app emits a lot of
                allows: filter by action/outcome before any I/O. The context's
                ``payload``/``userinfo`` are forwarded verbatim (may contain
                PII/secrets); redaction is the hook's responsibility. Accepts
                the callable or a ``"module.function"`` import-path string
                (use strings in ``rxconfig.py``, same reason as
                ``auth_providers``); strings resolve at compile time and a bad
                path fails startup rather than the first audited event. See
                ``reflex_enterprise.auth.audit`` for the hook contract and a
                worked example. Defaults to ``None`` (auditing disabled).
        """
        # Providers resolve lazily: ``__init__`` runs while ``rxconfig`` is
        # still being assigned, and importing a provider here would pull in
        # modules that call ``get_config()`` before the config exists.
        self._auth_providers = (
            list(auth_providers) if auth_providers is not None else None
        )
        self.auth = auth
        self.extra_scopes = list(extra_scopes)
        self.login_endpoint = login_endpoint
        self.logout_endpoint = logout_endpoint
        self.auth_callback_endpoint = auth_callback_endpoint
        self.forbidden_endpoint = forbidden_endpoint
        self.login_page = login_page
        self.logout_page = logout_page
        self.callback_page = callback_page
        self.forbidden_page = forbidden_page
        # Resolved lazily like ``auth_providers``: an import-path string cannot
        # be imported while ``rxconfig.py`` is still being assigned.
        self._audit = audit

    @property
    def audit_hook(self) -> "AuditHook | None":
        """The configured audit hook, or ``None`` when auditing is disabled.

        An import-path string is resolved (and cached) on first access, at
        wiring time — never during ``rxconfig.py`` assignment.
        """
        if isinstance(self._audit, str):
            self._audit = _resolve_import_path(self._audit)
        return self._audit

    def _validate_audit_config(self) -> None:
        """Resolve and validate the audit hook eagerly, at wiring time.

        A typo'd import path or a non-callable must fail startup with a clear
        message — resolved lazily it would surface (repeatedly, and fatally in
        ``snapshot_identity``'s pre-reset call) at the first audited action.

        Raises:
            ValueError: The ``audit=`` import path could not be resolved.
            TypeError: The resolved ``audit=`` value is not callable.
        """
        try:
            hook = self.audit_hook
        except Exception as resolve_error:
            raise ValueError(
                f"AuthPlugin(audit={self._audit!r}) could not be resolved: "
                f"{resolve_error}"
            ) from resolve_error
        if hook is not None and not callable(hook):
            msg = (
                "AuthPlugin(audit=...) must be a callable or a "
                f"'module.function' import-path string, got {hook!r}."
            )
            raise TypeError(msg)

    @property
    def auth_providers(self) -> "list[type[OIDCAuthState]]":
        """The configured providers, defaulting to ``[GenericOIDCAuthState]``."""
        if self._auth_providers is None:
            from reflex_enterprise.auth.enforcement import _default_providers

            resolved = _default_providers()
        else:
            resolved = [
                _resolve_import_path(p) if isinstance(p, str) else p
                for p in self._auth_providers
            ]
        # Cache so identity is stable across calls (sweeps, routes, registries).
        self._auth_providers = resolved
        return resolved

    def _wire_runtime(self) -> None:
        """Install the runtime enforcement wiring (idempotent).

        Sets the provider/endpoint registries and the secure-by-default
        ``auth`` value, forwards ``extra_scopes``, points the providers' OAuth
        redirect URI at the friendly callback, and runs the protection sweep.
        """
        from reflex_enterprise.auth.enforcement import (
            bind_auth_plugin,
            install_delta_prune,
        )

        # Validate before binding, so a misconfig fails without leaving the
        # enforcement layer pointing at a half-configured plugin.
        self._validate_provider_config()
        self._validate_audit_config()
        # Bind before the sweep: ``default_protect_state`` reads ``get_default_auth()``
        # and ``resolve_userinfo`` reads ``auth_providers`` through the plugin.
        bind_auth_plugin(self)
        self._point_providers_at_friendly_callback()
        # Ensure the delta-resolution chokepoint drops async-check guard
        # coroutines that deny (no-op when the installed reflex prunes natively).
        install_delta_prune()

        if self.extra_scopes:
            for provider in self.auth_providers:
                provider._set_extra_scopes(self.extra_scopes)

        self._sweep_default_protection()
        self._reregister_auth_states()

    def _reregister_auth_states(self) -> None:
        """Re-register the auth framework states in the active registration context.

        State classes register their event handlers at class-creation time, into
        whatever ``RegistrationContext`` is active then. A context created later
        (a fresh test harness, dev hot reload) only sees states created after it,
        leaving the framework auth handlers (e.g. ``enforce_login``) unresolvable
        at event dispatch. Registration raises on a repeat, so only states the
        context doesn't know yet are added.
        """
        from reflex_base.registry import RegistrationContext

        from reflex_enterprise.auth.oidc.state import IsIframedState
        from reflex_enterprise.auth.page_guard import PageGuardState
        from reflex_enterprise.auth.replay import PendingEventState
        from reflex_enterprise.auth.routes import AuthRouteState
        from reflex_enterprise.auth.user_state import AuthUserState

        reg_ctx = RegistrationContext.ensure_context()
        for state_cls in (
            PageGuardState,
            AuthRouteState,
            IsIframedState,
            AuthUserState,
            PendingEventState,
            *self.auth_providers,
        ):
            if state_cls.get_full_name() not in reg_ctx.base_states:
                RegistrationContext.register_base_state(state_cls)

    def pre_compile(self, **context: Any) -> None:
        """App-independent setup: registries, scope forwarding, protection sweep.

        ``pre_compile`` is NOT passed the app (and runs after pages are
        snapshotted), so it does no app-touching work. The gate is installed in
        ``post_compile`` and the routes are registered by ``AppEnterprise`` at
        construction.

        Args:
            **context: The reflex ``PreCompileContext`` (ignored here).
        """
        self._wire_runtime()

    def post_compile(self, **context: Any) -> None:
        """Wire the runtime enforcement and install the per-event gate.

        ``post_compile`` runs unconditionally when the ASGI app is constructed
        (``App.__call__``) — including backend-only processes started with
        ``REFLEX_SKIP_COMPILE``, where the compiler's ``pre_compile`` loop is
        skipped entirely. The full runtime wiring therefore happens here too
        (it is idempotent); relying on ``pre_compile`` alone would leave the
        production backend without field/var protection.

        This is also the plugin's only contact with the app object, so it is
        where the ``rxe.App`` requirement is enforced (see
        ``_require_enterprise_app``).

        Args:
            **context: The reflex ``PostCompileContext`` (includes ``app``).
        """
        self._wire_runtime()
        app = context.get("app")
        if app is None:
            return
        self._require_enterprise_app(app)
        from reflex_enterprise.auth.enforcement import AuthMiddleware

        app.add_middleware(AuthMiddleware())

    def _require_enterprise_app(self, app: Any) -> None:
        """Fail fast when the app is a plain ``rx.App`` rather than ``rxe.App``.

        The friendly ``/login`` / ``/logout`` / ``/callback`` / ``/forbidden``
        routes and the secure-by-default page guards are wired by
        ``AppEnterprise`` at construction (``register_routes`` and the
        ``add_page`` override). A plain ``reflex.App`` never runs that wiring, yet
        ``pre_compile`` / ``post_compile`` still install the runtime enforcement —
        so a protected page redirects to a route that was never compiled and the
        visitor hits a 404 far from the real cause. Detect the wrong app class
        while the ASGI app is built and raise an actionable error instead.

        Args:
            app: The app passed to ``post_compile``.

        Raises:
            ConfigError: When ``app`` is not an ``AppEnterprise`` instance.
        """
        # Imported lazily: ``reflex_enterprise.app`` imports this module at top
        # level, so importing it here at module scope would be circular.
        from reflex_enterprise.app import AppEnterprise

        if not isinstance(app, AppEnterprise):
            raise ConfigError(
                "AuthPlugin requires the app to be a `reflex_enterprise.App`, but "
                "a plain `reflex.App` was used. Replace `reflex.App(...)` with "
                "`reflex_enterprise.App(...)`."
            )

    def _sweep_default_protection(self) -> None:
        """Default-protect every field/var on each non-exempt state class.

        Records protection for non-exempt states and installs the delta filter so
        protected fields/vars are dropped from the delta for unauthorized callers.

        Iterates the states registered in the active ``RegistrationContext`` rather
        than walking the interpreter-global ``rx.State.__subclasses__()``. The
        registry is per-app, so the sweep stays scoped to this app's states and
        apps sharing an interpreter — including separate test harnesses — don't
        protect each other's states.
        """
        from reflex_base.registry import RegistrationContext

        from reflex_enterprise.auth.enforcement import (
            default_protect_state,
            install_delta_filter,
        )

        for state_cls in RegistrationContext.get().base_states.values():
            # Both callees no-op for exempt (framework) states.
            default_protect_state(state_cls)
            install_delta_filter(state_cls)

    def _validate_provider_config(self) -> None:
        """Fail when several providers would share the generic ``OIDC_*`` config.

        Each provider reads its issuer URI / client id from ``{PROVIDER}_*`` env
        vars, falling back to the shared ``OIDC_*`` keys (see
        ``ConfigMixin._get_config_value``). That fallback is a single-provider
        convenience: with two or more providers resolving the same required key
        through it, distinct identity providers silently collapse onto one
        issuer/client, and the misconfiguration surfaces far away as an opaque
        ``invalid_client`` error from the IdP. Catch it at wiring time instead,
        naming the offending providers and the exact var to set for each.

        Raises:
            ConfigError: When two or more providers resolve a required key only
                through the shared ``OIDC_*`` fallback.
        """
        providers = self.auth_providers
        if len(providers) < 2:
            return

        problems: list[str] = []
        for key in ("ISSUER_URI", "CLIENT_ID"):
            _, fallback_key = providers[0]._env_keys(key)
            if not os.environ.get(fallback_key):
                continue
            sharing = []
            for provider in providers:
                own_key, _ = provider._env_keys(key)
                # A provider relies on the shared fallback when it has no
                # distinct key of its own (``__provider__ == "oidc"`` collapses
                # the two) or that key is unset/empty — matching the truthiness
                # ``_get_config_value`` and ``_issuer_uri`` apply at runtime.
                if own_key == fallback_key or not os.environ.get(own_key):
                    sharing.append((provider, own_key))
            if len(sharing) > 1:
                fixes = ", ".join(
                    f"{provider.__name__} → {own_key}" for provider, own_key in sharing
                )
                problems.append(f"{fallback_key}: shared by {fixes}")

        if problems:
            raise ConfigError(
                "Multiple auth providers fall back to the shared OIDC_* config, "
                "so distinct identity providers would use the same value. "
                + "; ".join(problems)
                + ". Set a provider-specific {PROVIDER}_{KEY} env var for each."
            )

    def _point_providers_at_friendly_callback(self) -> None:
        """Make every provider's OAuth redirect URI path the friendly callback.

        The redirect URI sent in the authorization request (and registered with
        the IdP) must be the plugin's ``auth_callback_endpoint``, where the
        dispatcher demuxes the response to the initiating provider.
        """
        for provider in self.auth_providers:
            provider._auth_callback_route = self.auth_callback_endpoint

    def _page_component(
        self, spec: PageBuilder | str | None, default: PageBuilder
    ) -> Callable[[], Component]:
        """Wrap a page spec into the zero-arg callable ``add_page`` evaluates.

        The builder (custom or default) is resolved and called lazily at
        compile time, so import-path strings never import user modules during
        app construction.

        Args:
            spec: The configured builder, import-path string, or None.
            default: The default builder used when ``spec`` is None.

        Returns:
            A zero-argument callable returning the page component.
        """

        def page() -> Component:
            fn = (
                default
                if spec is None
                else _resolve_import_path(spec)
                if isinstance(spec, str)
                else spec
            )
            return _call_page_builder(fn, plugin=self, providers=self.auth_providers)

        # Surface a meaningful name in duplicate-route errors (the signal a
        # user gets when trying to register their own page on a plugin route).
        page.__name__ = page.__qualname__ = default.__name__
        return page

    def register_routes(self, app: Any) -> None:
        """Register the friendly auth routes.

        Called by ``AppEnterprise`` at construction (before compile snapshots
        pages). ``/login`` renders a palette of login buttons (even with a
        single provider the visitor clicks to start the flow instead of being
        bounced to a third-party login automatically). ``/logout`` and
        ``/callback`` chain the dispatcher, which resolves the active /
        initiating provider. ``/forbidden`` renders the denied page for
        authenticated users. Each provider's popup endpoints are registered too
        (the friendly callback replaces only the provider's own callback route).
        The rendered components honor the configured ``login_page`` /
        ``logout_page`` / ``callback_page`` / ``forbidden_page`` builders.

        Args:
            app: The app to add the routes to.
        """
        from reflex_enterprise.auth.enforcement import (
            LogoutCSRFMiddleware,
            bind_auth_plugin,
            reserve_agent_hidden_route,
        )
        from reflex_enterprise.auth.pages import (
            default_callback_page,
            default_forbidden_page,
            default_login_page,
            default_logout_page,
        )
        from reflex_enterprise.auth.routes import AuthRouteState

        # Reject an empty provider list here, at app construction: the compiler
        # evaluates the page closures before any ``pre_compile`` hook runs, so the
        # only way to preempt the ``providers[0]`` IndexError in
        # ``default_callback_page`` / ``default_logout_page`` is to fail now.
        providers = self.auth_providers
        if not providers:
            raise ConfigError(
                "AuthPlugin was given an empty auth_providers list, but at least "
                "one provider is required. Omit auth_providers to use the default "
                "GenericOIDCAuthState, or pass one or more provider classes."
            )
        # Bind early: page builders are evaluated before ``pre_compile`` runs, and
        # compile-time surfaces (``AuthUserState.name`` etc.) resolve
        # ``get_auth_providers()`` during page evaluation.
        bind_auth_plugin(self)
        self._point_providers_at_friendly_callback()

        app.add_page(
            self._page_component(self.login_page, default_login_page),
            route=self.login_endpoint,
            auth=False,
            title="Login",
        )
        app.add_page(
            self._page_component(self.callback_page, default_callback_page),
            route=self.auth_callback_endpoint,
            auth=False,
            on_load=AuthRouteState.do_callback,
            title="Auth Callback",
        )
        app.add_page(
            self._page_component(self.logout_page, default_logout_page),
            route=self.logout_endpoint,
            auth=False,
            on_load=AuthRouteState.do_logout,
            title="Logout",
        )
        app.add_page(
            self._page_component(self.forbidden_page, default_forbidden_page),
            route=self.forbidden_endpoint,
            auth=False,
            title="Forbidden",
        )
        # Hide the friendly auth pages from the agent-facing page listing (MCP
        # instructions / EventHandlerAPI OpenAPI): they are human-interactive
        # login/logout/consent plumbing an agent neither drives nor should be
        # pointed at. The providers reserve their own popup routes below.
        for internal_route in (
            self.login_endpoint,
            self.auth_callback_endpoint,
            self.logout_endpoint,
            self.forbidden_endpoint,
        ):
            reserve_agent_hidden_route(app, internal_route)
        for provider in providers:
            provider._register_auth_endpoints(app)
        # Pass the raw route; the middleware applies the frontend-path prefix
        # lazily on first request. Resolving it here would call get_config() while
        # rxconfig is still importing (app construction runs during that import).
        app._api.add_middleware(
            LogoutCSRFMiddleware, logout_endpoint=self.logout_endpoint
        )
