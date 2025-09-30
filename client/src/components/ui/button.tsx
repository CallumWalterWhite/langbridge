'use client';

import * as React from 'react';
import type { ButtonHTMLAttributes } from 'react';

import { cn } from '@/lib/utils';
import { Spinner } from '@/components/ui/spinner';

type ButtonVariant = 'default' | 'secondary' | 'outline' | 'ghost';
type ButtonSize = 'sm' | 'md' | 'lg' | 'icon';

const VARIANT_CLASSES: Record<ButtonVariant, string> = {
  default: 'bg-slate-900 text-white hover:bg-slate-900/90 focus-visible:ring-slate-900',
  secondary: 'bg-white text-slate-900 border border-slate-200 hover:bg-slate-100 focus-visible:ring-slate-200',
  outline: 'border border-slate-200 text-slate-900 hover:bg-slate-100 focus-visible:ring-slate-200',
  ghost: 'text-slate-700 hover:bg-slate-100 focus-visible:ring-slate-200',
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
          'inline-flex items-center justify-center gap-2 rounded-md font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50',
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
