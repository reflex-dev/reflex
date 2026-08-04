import React from "react";
import { interpolate, spring, useVideoConfig } from "remotion";

import { c, font, shadow } from "../theme";

/** Ease a value in with a spring, for slide-and-fade reveals. */
const useReveal = (frame: number, delay: number) => {
  const { fps } = useVideoConfig();
  return spring({
    frame: frame - delay,
    fps,
    config: { damping: 200, mass: 0.6, stiffness: 90 },
  });
};

export const Reveal: React.FC<{
  frame: number;
  delay?: number;
  /** Distance in px the child travels on the way in. */
  y?: number;
  x?: number;
  scale?: number;
  children: React.ReactNode;
  style?: React.CSSProperties;
}> = ({ frame, delay = 0, y = 26, x = 0, scale = 1, children, style }) => {
  const p = useReveal(frame, delay);
  return (
    <div
      style={{
        opacity: interpolate(p, [0, 0.6], [0, 1], {
          extrapolateRight: "clamp",
        }),
        transform: `translate(${interpolate(p, [0, 1], [x, 0])}px, ${interpolate(
          p,
          [0, 1],
          [y, 0],
        )}px) scale(${interpolate(p, [0, 1], [scale, 1])})`,
        ...style,
      }}
    >
      {children}
    </div>
  );
};

export const Eyebrow: React.FC<{
  children: React.ReactNode;
  color?: string;
}> = ({ children, color = c.slate9 }) => (
  <div
    style={{
      fontFamily: font.sans,
      fontSize: 23,
      fontWeight: 600,
      letterSpacing: "0.18em",
      textTransform: "uppercase",
      color,
    }}
  >
    {children}
  </div>
);

export const Headline: React.FC<{
  children: React.ReactNode;
  size?: number;
  color?: string;
  weight?: number;
}> = ({ children, size = 72, color = c.slate12, weight = 600 }) => (
  <div
    style={{
      fontFamily: font.sans,
      fontSize: size,
      fontWeight: weight,
      letterSpacing: size > 60 ? "-0.04em" : "-0.028em",
      lineHeight: 1.06,
      color,
    }}
  >
    {children}
  </div>
);

export const Body: React.FC<{
  children: React.ReactNode;
  size?: number;
  color?: string;
}> = ({ children, size = 30, color = c.slate11 }) => (
  <div
    style={{
      fontFamily: font.sans,
      fontSize: size,
      fontWeight: 400,
      lineHeight: 1.45,
      letterSpacing: "-0.011em",
      color,
    }}
  >
    {children}
  </div>
);

export const Card: React.FC<{
  children: React.ReactNode;
  style?: React.CSSProperties;
  padding?: number;
}> = ({ children, style, padding = 34 }) => (
  <div
    style={{
      background: c.white,
      border: `1px solid ${c.slate5}`,
      borderRadius: 18,
      boxShadow: shadow.card,
      padding,
      ...style,
    }}
  >
    {children}
  </div>
);

export const Chip: React.FC<{
  children: React.ReactNode;
  variant?: "violet" | "slate" | "jade";
  size?: number;
  /** Set for chips holding code — env vars, package names. */
  mono?: boolean;
}> = ({ children, variant = "violet", size = 24, mono = false }) => {
  const palette = {
    violet: { bg: c.violet3, fg: c.violet11, br: c.violet6 },
    slate: { bg: c.slate2, fg: c.slate11, br: c.slate5 },
    jade: { bg: "rgba(86, 186, 159, 0.14)", fg: "#217f6d", br: "#a9ddcf" },
  }[variant];

  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 10,
        fontFamily: mono ? font.mono : font.sans,
        fontSize: size,
        fontWeight: 550,
        letterSpacing: "-0.01em",
        color: palette.fg,
        background: palette.bg,
        border: `1px solid ${palette.br}`,
        borderRadius: 10,
        padding: `${size * 0.34}px ${size * 0.62}px`,
        whiteSpace: "nowrap",
      }}
    >
      {children}
    </span>
  );
};

/** A single filled block from the wordmark's lattice, used as a bullet. */
export const PixelBullet: React.FC<{ size?: number; color?: string }> = ({
  size = 14,
  color = c.violet9,
}) => (
  <span
    style={{
      width: size,
      height: size,
      background: color,
      borderRadius: 2,
      flexShrink: 0,
      display: "inline-block",
    }}
  />
);

export const Check: React.FC<{ size?: number }> = ({ size = 30 }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    style={{ flexShrink: 0 }}
  >
    <circle cx="12" cy="12" r="11" fill="rgba(86, 186, 159, 0.16)" />
    <path
      d="M7.4 12.4 10.6 15.6 16.8 9"
      stroke="#2a8871"
      strokeWidth="2.4"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

/** Slice a string for a typewriter effect. */
export const typed = (text: string, progress: number) =>
  text.slice(0, Math.round(interpolate(progress, [0, 1], [0, text.length])));

export const Cursor: React.FC<{ frame: number; color?: string }> = ({
  frame,
  color = c.violet9,
}) => (
  <span
    style={{
      display: "inline-block",
      width: 13,
      height: 30,
      marginLeft: 3,
      transform: "translateY(4px)",
      background: color,
      opacity: Math.floor(frame / 8) % 2 === 0 ? 1 : 0.16,
    }}
  />
);

/**
 * A terminal surface matching the site's code blocks: hairline border, muted
 * header strip, mono body.
 */
export const Terminal: React.FC<{
  label?: string;
  children: React.ReactNode;
  width?: number;
  style?: React.CSSProperties;
}> = ({ label = "bash", children, width, style }) => (
  <div
    style={{
      width,
      background: c.white,
      border: `1px solid ${c.slate5}`,
      borderRadius: 16,
      boxShadow: shadow.card,
      overflow: "hidden",
      ...style,
    }}
  >
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 12,
        padding: "16px 22px",
        borderBottom: `1px solid ${c.slate4}`,
        background: c.slate2,
      }}
    >
      <span
        style={{ width: 11, height: 11, borderRadius: 6, background: c.slate6 }}
      />
      <span
        style={{ width: 11, height: 11, borderRadius: 6, background: c.slate6 }}
      />
      <span
        style={{ width: 11, height: 11, borderRadius: 6, background: c.slate6 }}
      />
      <span
        style={{
          marginLeft: 8,
          fontFamily: font.mono,
          fontSize: 20,
          color: c.slate9,
          letterSpacing: "-0.01em",
        }}
      >
        {label}
      </span>
    </div>
    <div style={{ padding: "30px 34px 34px" }}>{children}</div>
  </div>
);
