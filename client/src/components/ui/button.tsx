'use client';

import * as React from 'react';
import type { ButtonHTMLAttributes } from 'react';

import { cn } from '@/lib/utils';
import { Spinner } from '@/components/ui/spinner';

type ButtonVariant = 'default' | 'secondary' | 'outline' | 'ghost';
type ButtonSize = 'sm' | 'md' | 'lg' | 'icon';

const VARIANT_CLASSES: Record<ButtonVariant, string> = {
  default: 'bg-[color:var(--accent)] text-white hover:bg-[color:var(--accent-strong)] focus-visible:ring-[color:var(--accent)]',
  secondary: 'border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] text-[color:var(--text-primary)] hover:bg-[color:var(--panel-alt)] focus-visible:ring-[color:var(--border-strong)]',
  outline: 'border border-[color:var(--border-strong)] bg-transparent text-[color:var(--text-primary)] hover:bg-[color:var(--panel-alt)] focus-visible:ring-[color:var(--border-strong)]',
  ghost: 'bg-transparent text-[color:var(--text-secondary)] hover:bg-[color:var(--panel-alt)] focus-visible:ring-[color:var(--border-strong)]',
};

const SIZE_CLASSES: Record<ButtonSize, string> = {
  sm: 'h-9 px-3 text-sm',
  md: 'h-10 px-4 text-sm',
  lg: 'h-12 px-6 text-base',
  icon: 'h-10 w-10 p-0',
};

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  isLoading?: boolean;
  loadingText?: string;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  function Button(
    {
      className,
      variant = 'default',
      size = 'md',
      isLoading = false,
      children,
      disabled,
      loadingText,
      ...props
    },
    ref,
  ) {
    const content = isLoading && loadingText ? loadingText : children;

    return (
      <button
        ref={ref}
        className={cn(
          'inline-flex items-center justify-center gap-2 rounded-md font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--app-bg)] disabled:pointer-events-none disabled:opacity-50',
          VARIANT_CLASSES[variant],
          SIZE_CLASSES[size],
          className,
        )}
        aria-busy={isLoading || undefined}
        disabled={disabled || isLoading}
        {...props}
      >
        {isLoading ? <Spinner className="h-4 w-4" /> : null}
        {content}
      </button>
    );
  },
);
