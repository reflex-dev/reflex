/**
 * Reflex brand tokens.
 *
 * Values mirror the live site's design system so the video matches reflex.dev:
 *   packages/reflex-site-shared/src/reflex_site_shared/styles/assets/custom-colors.css
 *   packages/reflex-site-shared/src/reflex_site_shared/styles/shadows.py
 */

export const c = {
  // Slate — surfaces, borders, text.
  slate1: "#fcfcfd",
  slate2: "#f9f9fb",
  slate3: "#f0f0f3",
  slate4: "#e8e8ec",
  slate5: "#e0e1e6",
  slate6: "#d9d9e0",
  slate7: "#cdced6",
  slate8: "#b9bbc6",
  slate9: "#8b8d98",
  slate10: "#80838d",
  slate11: "#60646c",
  slate12: "#1c2024",

  // Violet — the accent.
  violet1: "#fdfcfe",
  violet2: "#fafbff",
  violet3: "#f4f0fe",
  violet4: "#ebe4ff",
  violet5: "#e1d9ff",
  violet6: "#d4cafe",
  violet7: "#c2b5f5",
  violet8: "#aa99ec",
  violet9: "#6e56cf",
  violet10: "#654dc4",
  violet11: "#6550b9",
  violet12: "#2f265f",

  jade8: "#56ba9f",
  red9: "#e5484d",

  white: "#ffffff",
  glow: "#ebe4ff",
  waveLine1: "#d4cafe",
  waveLine2: "#ebe4ff",

  /** The wordmark ink, straight from docs/images/reflex.svg. */
  ink: "#110F1F",
} as const;

export const font = {
  sans: "'Instrument Sans Variable', system-ui, sans-serif",
  mono: "'JetBrains Mono Variable', ui-monospace, monospace",
} as const;

export const shadow = {
  small: "0px 2px 4px 0px rgba(28, 32, 36, 0.05)",
  medium: "0px 4px 8px 0px rgba(28, 32, 36, 0.04)",
  large:
    "0px 24px 12px 0px rgba(28, 32, 36, 0.02), 0px 8px 8px 0px rgba(28, 32, 36, 0.02), 0px 2px 6px 0px rgba(28, 32, 36, 0.02)",
  /** The site's primary button: inset hairline + top highlight. */
  primaryButton:
    "0 0 1px #6E56CF inset, 0 2px 0 0 rgba(255, 255, 255, 0.22) inset",
  card: "0px 24px 12px 0px rgba(28, 32, 36, 0.02), 0px 8px 8px 0px rgba(28, 32, 36, 0.03), 0px 2px 6px 0px rgba(28, 32, 36, 0.04), 0 0 0 1px rgba(28, 32, 36, 0.05)",
} as const;

export const VIDEO = {
  fps: 30,
  width: 1920,
  height: 1080,
} as const;
