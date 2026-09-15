import type { ButtonHTMLAttributes, ReactNode } from "react";

import { cn } from "clsx-for-tailwind";

export type ButtonVariant =
  | "primary"
  | "success"
  | "primary-bordered"
  | "secondary"
  | "destructive"
  | "outline"
  | "ghost";
export type ButtonSize =
  | "xs"
  | "sm"
  | "md"
  | "lg"
  | "xl"
  | "icon-xs"
  | "icon-sm"
  | "icon-md"
  | "icon-lg";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  children: ReactNode;
  variant?: ButtonVariant;
  size?: ButtonSize;
  className?: string;
  nativeButton?: boolean;
}

export const focusRing =
  "focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ring";

const variants: Record<ButtonVariant, string> = {
  primary:
    "bg-primary text-primary-foreground shadow-none hover:bg-primary-hover",
  secondary:
    "border-0 bg-accent text-foreground shadow-none hover:bg-accent-hover",
  "primary-bordered":
    "bg-primary text-primary-foreground shadow-none hover:bg-primary-hover",
  success: "bg-success-9 text-white shadow-none hover:bg-success-10",
  destructive: "bg-red-strong text-gray-white hover:bg-red-deep",
  outline:
    "border border-border bg-card text-muted-foreground shadow-small hover:bg-accent",
  ghost:
    "bg-transparent text-foreground shadow-none hover:bg-accent hover:text-foreground",
};

const sizes: Record<ButtonSize, string> = {
  xs: "h-7 gap-1.5 px-3 text-xs",
  sm: "h-9 gap-2 px-4 text-sm leading-none",
  md: "h-11 gap-2 px-5 text-sm leading-none",
  lg: "h-12 gap-2 px-6 text-base leading-none",
  xl: "min-h-14 max-w-full gap-2.5 whitespace-normal px-8 py-3 text-center text-lg leading-6",
  "icon-xs": "size-7 p-0",
  "icon-sm": "size-9 p-0",
  "icon-md": "size-11 p-0",
  "icon-lg": "size-12 p-0",
};

/** A single variant API for buttons and link-shaped actions. */
export function buttonVariants({
  variant = "primary",
  size = "md",
  className,
}: {
  variant?: ButtonVariant;
  size?: ButtonSize;
  className?: string;
} = {}) {
  return cn(
    "relative inline-flex shrink-0 items-center justify-center whitespace-nowrap rounded-full font-medium transition-colors cursor-pointer box-border",
    focusRing,
    "disabled:pointer-events-none disabled:cursor-not-allowed disabled:bg-accent disabled:text-subtle-foreground disabled:shadow-none motion-reduce:transition-none [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
    variants[variant],
    sizes[size],
    className,
  );
}

/** Reusable action primitive; all visual states are Tailwind variants. */
export function GradientButton({
  children,
  variant = "primary",
  size = "md",
  className,
  nativeButton = true,
  ...props
}: ButtonProps) {
  const Component =
    nativeButton || props["aria-haspopup"] === "dialog" ? "button" : "div";
  const glow = variant === "primary";
  return (
    <Component
      {...props}
      onMouseMove={(event) => {
        props.onMouseMove?.(event);
        if (!glow || props.disabled) return;
        // The glow follows the pointer through CSS variables written straight
        // to the element, so tracking never re-renders the button.
        const bounds = event.currentTarget.getBoundingClientRect();
        event.currentTarget.style.setProperty(
          "--glow-x",
          `${event.clientX - bounds.left}px`,
        );
        event.currentTarget.style.setProperty(
          "--glow-y",
          `${event.clientY - bounds.top}px`,
        );
      }}
      data-slot="button"
      data-marketing-variant={variant}
      className={buttonVariants({
        variant,
        size,
        className: cn("overflow-hidden", glow && "group/glow", className),
      })}
    >
      {glow ? (
        <>
          {/* Visible only while hovered; `disabled:pointer-events-none` on the
              button means a disabled button never hovers. */}
          <span
            aria-hidden="true"
            className="pointer-events-none absolute size-11 -translate-x-1/2 -translate-y-1/2 rounded-full bg-gray-white/60 blur-[28px] opacity-0 transition-opacity duration-300 group-hover/glow:opacity-100 motion-reduce:hidden"
            style={{
              left: "var(--glow-x, 0px)",
              top: "var(--glow-y, 0px)",
            }}
          />
          <span className="relative z-10 inline-flex items-center gap-[inherit]">
            {children}
          </span>
        </>
      ) : (
        children
      )}
    </Component>
  );
}
