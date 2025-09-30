import type { HTMLAttributes } from 'react';
import { cn } from '@/lib/utils';

export function Spinner({ className, ...props }: HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      role="status"
      aria-live="polite"
      className={cn('inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent align-middle', className)}
      {...props}
    />
  );
}
