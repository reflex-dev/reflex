'use client'

import { cn } from 'clsx-for-tailwind'
import React, { useCallback, useState } from 'react'

type ButtonVariant = 'primary' | 'destructive' | 'outline' | 'ghost'
type ButtonSize = 'xs' | 'sm' | 'md' | 'lg' | 'icon-xs' | 'icon-sm' | 'icon-md' | 'icon-lg'

interface GradientButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  children: React.ReactNode
  variant?: ButtonVariant
  size?: ButtonSize
  className?: string
  nativeButton?: boolean
}

const BASE_CLASSES =
  'relative inline-flex items-center justify-center whitespace-nowrap transition-colors disabled:cursor-not-allowed disabled:border disabled:border-m-slate-4/80 disabled:bg-m-slate-3 disabled:text-m-slate-8 [&_svg]:pointer-events-none [&_svg:not([class*="size-"])]:size-4 shrink-0 [&_svg]:shrink-0 cursor-pointer box-border font-[525] overflow-hidden'

const VARIANT_CLASSES: Record<ButtonVariant, string> = {
  primary:
    'bg-primary-9 text-primary-2 dark:text-primary-contrast hover:bg-primary-10 shadow-[0_0_1px_var(--primary-9,#6E56CF)_inset,0_2px_0_0_rgba(255,255,255,0.22)_inset]',
  destructive: 'bg-destructive-9 hover:bg-destructive-10 text-primary-contrast',
  outline:
    'shadow-[0_-1px_0_0_rgba(0,0,0,0.08)_inset,0_0_0_1px_rgba(0,0,0,0.08)_inset,0_1px_2px_0_rgba(0,0,0,0.02),0_1px_4px_0_rgba(0,0,0,0.02)] dark:shadow-[0_1px_0_0_rgba(255,255,255,0.16)_inset] bg-white dark:bg-m-slate-10 hover:bg-m-slate-2 dark:hover:bg-m-slate-9 text-m-slate-12 dark:text-m-slate-3',
  ghost: 'text-m-slate-12 dark:text-m-slate-3 hover:text-primary-10 dark:hover:text-primary-9',
}

const SIZE_CLASSES: Record<ButtonSize, string> = {
  xs: 'px-1.5 h-7 rounded-lg gap-1.5 text-sm',
  sm: 'px-2 h-8 rounded-lg gap-2 text-sm',
  md: 'px-2.5 h-9 rounded-[0.625rem] gap-2 text-sm',
  lg: 'px-3 h-10 rounded-[0.625rem] gap-2.5 text-base',
  'icon-xs': 'size-7 rounded-lg',
  'icon-sm': 'size-8 rounded-lg',
  'icon-md': 'size-9 rounded-[0.625rem]',
  'icon-lg': 'size-10 rounded-[0.625rem]',
}

export function GradientButton({
  children,
  variant = 'primary',
  size = 'md',
  className,
  nativeButton = true,
  ...props
}: GradientButtonProps) {
  const [isMouseOver, setIsMouseOver] = useState(false)
  const [x, setX] = useState(0)
  const [y, setY] = useState(0)

  const handleMouseMove = useCallback<
    React.MouseEventHandler<HTMLButtonElement>
  >((e) => {
    const button = e.currentTarget
    const rect = button.getBoundingClientRect()
    setX(e.clientX - rect.left)
    setY(e.clientY - rect.top)
  }, [])

  const handleMouseEnter = useCallback(() => {
    setIsMouseOver(true)
  }, [])

  const handleMouseLeave = useCallback(() => {
    setIsMouseOver(false)
  }, [])

  const Component = nativeButton ? 'button' : 'div'

  return (
    <Component
      {...props}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      onMouseMove={handleMouseMove}
      className={cn(
        BASE_CLASSES,
        VARIANT_CLASSES[variant],
        SIZE_CLASSES[size],
        className
      )}
    >
      {variant === 'primary' ? (
        <>
          <span
            className="block absolute rounded-full pointer-events-none"
            style={{
              width: '2.75rem',
              height: '2.75rem',
              left: x,
              top: y,
              transform: 'translate(-50%, -50%) translateZ(0)',
              background: '#EB8E90',
              mixBlendMode: 'plus-lighter',
              filter: 'blur(28px)',
              opacity: isMouseOver ? 1 : 0,
              transition: 'opacity 0.3s ease',
              willChange: 'transform, opacity',
            }}
          />
          <span className="inline-flex z-10 relative items-center gap-[inherit]">{children}</span>
        </>
      ) : (
        children
      )}
    </Component>
  )
}

export default GradientButton
