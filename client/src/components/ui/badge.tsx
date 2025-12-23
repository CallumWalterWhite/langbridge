import * as React from 'react';

import { cn } from '@/lib/utils';

type BadgeVariant = 'default' | 'success' | 'destructive' | 'secondary' | 'warning';

const VARIANT_MAP: Record<BadgeVariant, string> = {
  default: 'bg-[color:var(--accent)] text-white',
  success: 'border border-emerald-500/20 bg-emerald-500/10 text-emerald-600 dark:text-emerald-200',
  destructive: 'border border-rose-500/25 bg-rose-500/15 text-rose-600 dark:text-rose-100',
  secondary: 'border border-[color:var(--panel-border)] bg-[color:var(--chip-bg)] text-[color:var(--text-secondary)]',
  warning: 'border border-amber-500/20 bg-amber-500/10 text-amber-600 dark:text-amber-200',
};

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
}

export const Badge = React.forwardRef<HTMLSpanElement, BadgeProps>(
  function Badge({ className, variant = 'default', ...props }, ref) {
    return (
      <span
        ref={ref}
        className={cn(
          'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold',
          VARIANT_MAP[variant],
          className,
        )}
        {...props}
      />
    );
  },
);
