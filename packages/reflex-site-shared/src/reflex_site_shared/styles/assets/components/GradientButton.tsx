"use client";

import { cn } from "clsx-for-tailwind";
import React from "react";

type ButtonVariant = "primary" | "destructive" | "outline" | "ghost";
type ButtonSize =
  | "xs"
  | "sm"
  | "md"
  | "lg"
  | "icon-xs"
  | "icon-sm"
  | "icon-md"
  | "icon-lg";

interface GradientButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  children: React.ReactNode;
  variant?: ButtonVariant;
  size?: ButtonSize;
  className?: string;
  nativeButton?: boolean;
}

const BASE_CLASSES =
  'relative inline-flex items-center justify-center whitespace-nowrap rounded-control transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring disabled:cursor-not-allowed disabled:bg-muted disabled:text-muted-foreground [&_svg]:pointer-events-none [&_svg:not([class*="size-"])]:size-4 shrink-0 [&_svg]:shrink-0 cursor-pointer box-border font-medium';

const VARIANT_CLASSES: Record<ButtonVariant, string> = {
  primary: "bg-primary text-primary-foreground hover:bg-primary-hover shadow-none",
  destructive: "bg-destructive hover:bg-destructive/90 text-white",
  outline: "border border-border bg-background hover:bg-accent text-foreground shadow-small",
  ghost: "text-foreground hover:bg-accent shadow-none",
};

const SIZE_CLASSES: Record<ButtonSize, string> = {
  xs: "px-1.5 h-7 rounded-control gap-1.5 text-sm",
  sm: "px-4 h-9 rounded-control gap-2 text-sm leading-none",
  md: "px-2.5 h-9 rounded-control gap-2 text-sm",
  lg: "px-3 h-10 rounded-control gap-2.5 text-base",
  "icon-xs": "size-7 rounded-control",
  "icon-sm": "size-9 rounded-control",
  "icon-md": "size-9 rounded-control",
  "icon-lg": "size-10 rounded-control",
};

export function GradientButton({
  children,
  variant = "primary",
  size = "md",
  className,
  nativeButton = true,
  ...props
}: GradientButtonProps) {
  const Component = nativeButton || props["aria-haspopup"] === "dialog" ? "button" : "div";

  return (
    <Component
      {...props}
      className={cn(
        BASE_CLASSES,
        VARIANT_CLASSES[variant],
        SIZE_CLASSES[size],
        className,
      )}
    >
      {children}
    </Component>
  );
}

export default GradientButton;
