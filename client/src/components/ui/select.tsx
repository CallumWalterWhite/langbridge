'use client';

import * as React from 'react';

import { cn } from '@/lib/utils';

export interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  placeholder?: string;
}

export const Select = React.forwardRef<HTMLSelectElement, SelectProps>(
  function Select({ className, children, placeholder, defaultValue, value, ...props }, ref) {
    const isControlled = value !== undefined;
    const resolvedDefault = defaultValue ?? '';

    return (
      <select
        ref={ref}
        value={isControlled ? value : undefined}
        defaultValue={isControlled ? undefined : resolvedDefault}
        className={cn(
          'flex h-10 w-full appearance-none rounded-xl border border-[color:var(--panel-border)] bg-[color:var(--panel-bg)] px-3 py-2 text-sm text-[color:var(--text-primary)] shadow-sm transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--accent)] focus-visible:ring-offset-2 focus-visible:ring-offset-[color:var(--app-bg)] disabled:cursor-not-allowed disabled:opacity-50',
          className,
        )}
        {...props}
      >
        {placeholder ? (
          <option value="" disabled>
            {placeholder}
          </option>
        ) : null}
        {children}
      </select>
    );
  },
);
