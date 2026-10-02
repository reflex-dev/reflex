"""Plain chat integration for customer support.

This module provides integration with Plain.com chat widget for live customer support.
See: https://plain.support.site/article/chat-customization
"""

import os
from typing import Any

import reflex as rx
from reflex.components.tags.tag import Tag

PLAIN_APP_ID = os.getenv("PLAIN_APP_ID", "liveChatApp_01KGG4JD5JHG8JY8X5CCN7811V")


class PlainChat(rx.Component):
    """Plain chat widget component."""

    tag = "PlainChat"

    full_name: rx.Var[str] = rx.Var.create("User")
    short_name: rx.Var[str] = rx.Var.create("User")
    chat_avatar_url: rx.Var[str] = rx.Var.create("")
    external_id: rx.Var[str] = rx.Var.create("")
    hide_launcher: rx.Var[bool] = rx.Var.create(True)

    # Optional email authentication
    email: rx.Var[str] = rx.Var.create("")
    email_hash: rx.Var[str] = rx.Var.create("")

    # Optional built-in email verification
    require_authentication: rx.Var[bool] = rx.Var.create(False)

    # Optional tier ID for thread details
    tier_id: rx.Var[str] = rx.Var.create("")

    # Entry point options
    # Type is either 'default' or 'chat'. 'default' opens intro screen, 'chat' opens straight into chat
    entry_point_type: rx.Var[str] = rx.Var.create("")
    # The external ID of which chat to open. If not provided it defaults to the last conversation
    entry_point_external_id: rx.Var[str] = rx.Var.create("")
    # Prevents the user from going back to the intro screen to start a new chat
    single_chat_mode: rx.Var[bool] = rx.Var.create(False)

    def add_imports(self) -> dict:
        """Add React imports.

        Returns:
            The component.
        """
        return {"react": ["useEffect"]}

    def add_hooks(self) -> list[str | rx.Var]:
        """Add hooks to initialize Plain chat widget.

        Returns:
            The component.
        """
        return [
            rx.Var(
                f"""useEffect(() => {{
  if (typeof window === 'undefined') return;

  const customerDetails = {{}};

  // Add fullName and shortName if provided
  if ({self.full_name!s}) {{
    customerDetails.fullName = {self.full_name!s};
  }}
  if ({self.short_name!s}) {{
    customerDetails.shortName = {self.short_name!s};
  }}

  // Add chatAvatarUrl if provided
  if ({self.chat_avatar_url!s}) {{
    customerDetails.chatAvatarUrl = {self.chat_avatar_url!s};
  }}

  // Add email if provided
  if ({self.email!s}) {{
    customerDetails.email = {self.email!s};
  }}
  if ({self.email_hash!s}) {{
    customerDetails.emailHash = {self.email_hash!s};
  }}

  const initOptions = {{
    appId: '{PLAIN_APP_ID}',
    hideLauncher: {self.hide_launcher!s},
    hideBranding: true,
    theme: 'auto',
    customerDetails: customerDetails,
  }};

  // Add threadDetails if externalId or tierId is provided
  if ({self.external_id!s} || {self.tier_id!s}) {{
    initOptions.threadDetails = {{}};
    if ({self.external_id!s}) {{
      initOptions.threadDetails.externalId = {self.external_id!s};
    }}
    if ({self.tier_id!s}) {{
      initOptions.threadDetails.tierIdentifier = {{ tierId: {self.tier_id!s} }};
    }}
  }}

  // Add requireAuthentication if true
  if ({self.require_authentication!s}) {{
    initOptions.requireAuthentication = true;
  }}

  // Add entryPoint if type, externalId, or singleChatMode is provided
  if ({self.entry_point_type!s} || {self.entry_point_external_id!s} || {self.single_chat_mode!s}) {{
    initOptions.entryPoint = {{}};
    if ({self.entry_point_type!s}) {{
      initOptions.entryPoint.type = {self.entry_point_type!s};
    }}
    if ({self.entry_point_external_id!s}) {{
      initOptions.entryPoint.externalId = {self.entry_point_external_id!s};
    }}
    if ({self.single_chat_mode!s}) {{
      initOptions.entryPoint.singleChatMode = true;
    }}
  }}

  if (window.Plain) {{
    if (Plain.isInitialized()) {{
      // Already initialized, update in-place
      // Exclude appId from update - it's only valid for init()
      const {{ appId, ...updateOptions }} = initOptions;
      Plain.update(updateOptions);
    }} else {{
      Plain.init(initOptions);
    }}
    return;
  }}

  const script = document.createElement('script');
  script.async = false;
  script.src = 'https://chat.cdn-plain.com/index.js';
  script.onload = () => Plain.init(initOptions);
  document.head.appendChild(script);
}}, [{self.full_name!s}, {self.short_name!s}, {self.chat_avatar_url!s}, {self.external_id!s}, {self.tier_id!s}, {self.entry_point_type!s}, {self.entry_point_external_id!s}, {self.single_chat_mode!s}, {self.email!s}, {self.email_hash!s}])"""
            )
        ]

    def _render(self, props: dict[str, Any] | None = None) -> Tag:
        """Render empty tag.

        Returns:
            The component.
        """
        return Tag("")


plain_chat = PlainChat.create


def open_plain_chat() -> rx.event.EventSpec:
    """Open the Plain chat widget.

    Returns:
        The component.
    """
    return rx.call_script(
        "try { Plain.open(); } catch (e) { console.error('Plain chat not available:', e); }"
    )
