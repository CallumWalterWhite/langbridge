import * as React from 'react';

import { cn } from '@/lib/utils';

type BadgeVariant = 'default' | 'success' | 'destructive' | 'secondary' | 'warning';

const VARIANT_MAP: Record<BadgeVariant, string> = {
  default: 'bg-[color:var(--accent)] text-white',
  success: 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-200',
  destructive: 'bg-red-500/15 text-red-600 dark:text-red-200',
  secondary: 'bg-[color:var(--chip-bg)] text-[color:var(--text-secondary)]',
  warning: 'bg-amber-500/15 text-amber-600 dark:text-amber-200',
};

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
}

export const Badge = React.forwardRef<HTMLSpanElement, BadgeProps>(
  function Badge({ className, variant = 'default', ...props }, ref) {
    return (
      <span
        ref={ref}
        className={cn('inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold', VARIANT_MAP[variant], className)}
        {...props}
      />
    );
  },
);
