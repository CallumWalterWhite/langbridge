import * as React from 'react';

import { cn } from '@/lib/utils';

export type InputProps = React.InputHTMLAttributes<HTMLInputElement>;

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  function Input({ className, type = 'text', ...props }, ref) {
    return (
      <input
        type={type}
        ref={ref}
        className={cn('flex h-10 w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-900 focus-visible:ring-offset-1 disabled:cursor-not-allowed disabled:opacity-50', className)}
        {...props}
      />
    );
  },
);
