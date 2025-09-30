import * as React from 'react';

import { cn } from '@/lib/utils';

type BadgeVariant = 'default' | 'success' | 'destructive' | 'secondary' | 'warning';

const VARIANT_MAP: Record<BadgeVariant, string> = {
  default: 'bg-slate-900 text-white',
  success: 'bg-emerald-100 text-emerald-700',
  destructive: 'bg-red-100 text-red-700',
  secondary: 'bg-slate-200 text-slate-800',
  warning: 'bg-amber-100 text-amber-700',
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
